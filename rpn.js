#!/usr/bin/env node
/**
 * RPN Evaluator with variables, SimVars, functions, history, conditionals, and rich step display.
 *
 * Features
 * - Persistent vars:  s0..s9  (write) / l0..l9 (read) — sN POPS top and stores it; lN pushes stored value
 * - Temp regs:        sp0..sp9 (write) / lp0..lp9 (read) — spN stores TOP (no pop); lpN pushes stored value
 * - SimVars:          (A:NAME,Unit) read,  (>A:NAME,Unit) write (persisted in ~/.simvars.json or --sim)
 * - Functions:        operator-like by default (pop args, run body as sub-postfix, push result);
 *                     --precompile/-p replaces function tokens upfront with body **without pN** (recursive)
 * - History recall:   r / rN[,k] (recall last stacks, up to 8) from ~/.rpnstack.json or --stack
 * - Conditionals:     if{ ... } [else{ ... }] — pops 1 value; executes branch iff value != 0 (truthy)
 * - Step mode:        --step/-s prints reductions with inline highlight; --endstep also shows postfix after each step
 * - Colors:           --nocolor/-c disables ANSI colors; --mark/-m uses yellow background & black text highlights
 * - Params:           p1..pN get prompted unless provided via --ctx; --noprompt hides labels only
 * - Admin:            --print prints s0..s9; --reset resets s0..s9  (works without <expr>)
 *
 * Short flags: -s == --step, -p == --precompile, -c/-n == --nocolor, -m == --mark, -? == --help
 */
const fs = require('fs');
const path = require('path');
const os = require('os');
const readline = require('readline');

/* ---------- ANSI colors (configurable) ---------- */
const ANSI = {
  reset: '\x1b[0m',
  red: '\x1b[31m',
  yellow: '\x1b[33m',
  markOn: '\x1b[43m\x1b[30m', // bg yellow, fg black
  markOff: '\x1b[0m',
};
function applyNoColor() {
  ANSI.reset = '';
  ANSI.red = '';
  ANSI.yellow = '';
  ANSI.markOn = '';
  ANSI.markOff = '';
}

/* ---------- persistence helpers ---------- */
function resolveArgPath(argv, flag, env, defName) {
  const i = argv.indexOf(`--${flag}`);
  if (i !== -1 && argv[i + 1]) return path.resolve(argv[i + 1]);
  if (process.env[env]) return path.resolve(process.env[env]);
  return path.join(os.homedir(), defName);
}
function atomicWrite(filePath, data) {
  const dir = path.dirname(filePath);
  if (!fs.existsSync(dir)) fs.mkdirSync(dir, { recursive: true });
  const tmp = path.join(dir, `.tmp-${Date.now()}-${Math.random().toString(16).slice(2)}.json`);
  fs.writeFileSync(tmp, data, 'utf8');
  fs.renameSync(tmp, filePath);
}
function loadJSON(p, def) { try { return JSON.parse(fs.readFileSync(p, 'utf8')); } catch { return def; } }
function saveJSON(p, obj) { try { atomicWrite(p, JSON.stringify(obj, null, 2)); } catch (e) { console.error('Warn:', e.message); } }
function loadVars(p) { const o = loadJSON(p, { vars: Array(10).fill(0) }); return Array.isArray(o.vars) ? o.vars.slice(0,10).map(Number) : Array(10).fill(0); }
function saveVars(p, vars) { saveJSON(p, { vars }); }
function loadSimvars(p) { const o = loadJSON(p, { simvars: {} }); return o.simvars || {}; }
function saveSimvars(p, simvars) { saveJSON(p, { simvars }); }
function loadFuncs(p) { const a = loadJSON(p, []); return Array.isArray(a) ? a.filter(f => f && typeof f.name==='string' && Number.isFinite(f.params) && typeof f.rpn==='string') : []; }
function loadResults(p) { const o = loadJSON(p, { results: [] }); return Array.isArray(o.results) ? o.results.filter(Array.isArray) : []; }
function saveResults(p, results) { saveJSON(p, { results: results.slice(0,8) }); }

/* ---------- tokenizer & utils ---------- */
function tokenize(src) {
  const tokens = [];
  let i = 0;
  while (i < src.length) {
    const ch = src[i];
    if (/\s/.test(ch)) { i++; continue; }
    if (ch === '(') { let d=1, j=i+1; while (j<src.length && d>0){ if (src[j]==='(') d++; else if (src[j]===')') d--; j++; } tokens.push(src.slice(i,j)); i=j; continue; }
    if (src.startsWith('if{', i)) { tokens.push('if{'); i+=3; continue; }
    if (src.startsWith('else{', i)) { tokens.push('else{'); i+=5; continue; }
    if (ch === '}') { tokens.push('}'); i++; continue; }
    let j = i; while (j < src.length && !/\s/.test(src[j]) && !'(){}'.includes(src[j])) j++; tokens.push(src.slice(i, j)); i = j;
  }
  return tokens.filter(Boolean);
}
function isNumberToken(t) { return /^[-+]?\d+(?:[.,]\d+)?$/.test(t); }
function parseNumber(t) { return parseFloat(t.replace(',', '.')); }
function toNum(v){ return typeof v === 'boolean' ? (v?1:0) : Number(v); }
function truthy(v){ return !!toNum(v); }
function fmt(v){ const n = Number(v); if (Number.isFinite(n) && Math.abs(n - Math.round(n)) < 1e-12) return String(Math.round(n)); return String(n); }
function isPureRTokenExpression(src){ const toks = tokenize(src || ''); return toks.length === 1 && /^r(\d+)?(,\d+)?$/.test(toks[0]); }

/* ---------- helper: find matching '}' from an opening token index ---------- */
function findBlockEnd(toks, openIndex){
  let depth = 1;
  for (let i = openIndex + 1; i < toks.length; i++) {
    const t = toks[i];
    if (t === 'if{' || t === 'else{') depth++;
    else if (t === '}') {
      depth--;
      if (depth === 0) return i; // index of closing brace
    }
  }
  throw new Error("Fehlende schließende '}' für Block ab Index " + openIndex);
}

/* ---------- precompile (replace function tokens with body without pN) ---------- */
function precompileTokens(tokens, functions) {
  const funcMap = new Map(functions.map(f => [f.name, f]));
  let changed = true;
  let out = tokens.slice();
  while (changed) {
    changed = false;
    const next = [];
    for (const t of out) {
      const f = funcMap.get(t);
      if (!f) { next.push(t); continue; }
      const body = tokenize(f.rpn).filter(x => !/^p\d+$/.test(x));
      const expandedBody = precompileTokens(body, functions);
      next.push(...expandedBody);
      changed = true;
    }
    out = next;
  }
  return out;
}

/* ---------- evaluator (operator-like functions by default) ---------- */
function evaluateRPN(src, options = {}) {
  const tokens = tokenize(src || '');
  const stack = [];
  const regs = Array(10).fill(0);           // temp registers (session-local)
  const vars = options.vars || Array(10).fill(0); // persistent vars
  const simvars = options.simvars || {};
  const params = options.params || {};
  const functions = options.functions || [];
  const fnMap = new Map(functions.map(f => [f.name, f]));
  const results = options.results || [];
  const expandedTokens = tokens.slice(); // use original tokens for step view (so conditionals are visible)
  let simvarsDirty = false;

  function pushValue(val) { stack.push(val); }
  function pop(){ if (!stack.length) throw new Error('stack underflow'); return stack.pop(); }
  function pop2(){ if (stack.length<2) throw new Error('stack underflow'); const b=pop(), a=pop(); return [a,b]; }
  function runTokens(toks){ let i=0; while(i<toks.length) i = resolveToken(toks[i], i, toks); }

  function resolveToken(t, idx, toks) {
    // numbers
    if (isNumberToken(t)) { pushValue(parseNumber(t)); return idx+1; }

    // top-level params
    if (/^p\d+$/.test(t)) { const v = params[t] ?? 0; pushValue(v); return idx+1; }

    // results recall
    if (/^r(\d+)?(,\d+)?$/.test(t)) {
      const m=/^r(\d+)?(,\d+)?$/.exec(t);
      const ri=m[1]?parseInt(m[1],10):1;
      const si=m[2]?parseInt(m[2].slice(1),10):null;
      const res=results[ri-1];
      if (!res) throw new Error(`r: kein gespeichertes Ergebnis r${ri}`);
      if (si==null){ res.forEach(v=> pushValue(v) ); }
      else { if (res[si-1]==null) throw new Error(`r: kein Wert an Position ${si}`); pushValue(res[si-1]); }
      return idx+1;
    }

    // persistent vars
    if (/^s\d+$/.test(t))  { const n=parseInt(t.slice(1),10); const val=pop(); vars[n] = toNum(val); return idx+1; }
    if (/^l\d+$/.test(t))  { const n=parseInt(t.slice(1),10); const val = vars[n] ?? 0; pushValue(val); return idx+1; }

    // temp regs (session)
    if (/^sp\d+$/.test(t)) { const n=parseInt(t.slice(2),10); const valTop = stack.length?stack[stack.length-1]:0; regs[n]=toNum(valTop); return idx+1; }
    if (/^lp\d+$/.test(t)) { const n=parseInt(t.slice(2),10); const val = regs[n] ?? 0; pushValue(val); return idx+1; }

    // SimVars
    if (t.startsWith('(A:') && t.endsWith(')')) { const key=t.slice(3,-1).trim(); const val=simvars[key]??0; pushValue(val); return idx+1; }
    if (t.startsWith('(>A:') && t.endsWith(')')){ const key=t.slice(4,-1).trim(); const val=pop(); simvars[key]=toNum(val); simvarsDirty=true; return idx+1; }

    // Conditionals if{ ... } [else{ ... }]
    if (t === 'if{') {
      const endIf = findBlockEnd(toks, idx);
      let hasElse = false, elseStart = -1, endElse = -1;
      if (toks[endIf + 1] === 'else{') { hasElse = true; elseStart = endIf + 1; endElse = findBlockEnd(toks, elseStart); }
      const cond = pop();
      if (truthy(cond)) {
        const body = toks.slice(idx + 1, endIf);
        runTokens(body);
        return (hasElse ? endElse + 1 : endIf + 1);
      } else {
        if (hasElse) {
          const elseBody = toks.slice(elseStart + 1, endElse);
          runTokens(elseBody);
          return endElse + 1;
        } else {
          return endIf + 1;
        }
      }
    }
    if (t === 'else{') {
      const endElse = findBlockEnd(toks, idx);
      return endElse + 1;
    }

    // custom function as operator
    const func = fnMap.get(t);
    if (func) {
      if (stack.length < func.params) throw new Error(`function '${func.name}' benötigt ${func.params} Parameter`);
      const ps = Array(func.params);
      for (let k = func.params-1; k >= 0; k--) ps[k] = stack.pop();
      const bodyToks = tokenize(func.rpn).map(tok => /^p(\d+)$/.test(tok) ? String(ps[parseInt(tok.slice(1),10)-1] ?? 0) : tok);
      const subExpr = bodyToks.join(' ');
      const sub = evaluateRPN(subExpr, { vars, simvars, functions, results });
      sub.stack.forEach(v => stack.push(v));
      return idx+1;
    }

    // operators
    switch (t) {
      case '+': { const [a,b]=pop2(); pushValue(toNum(a)+toNum(b)); break; }
      case '-': { const [a,b]=pop2(); pushValue(toNum(a)-toNum(b)); break; }
      case '*': { const [a,b]=pop2(); pushValue(toNum(a)*toNum(b)); break; }
      case '/': { const [a,b]=pop2(); pushValue(toNum(a)/toNum(b)); break; }
      case '%': { const [a,b]=pop2(); pushValue(toNum(a)%toNum(b));  break; }
      case '^': { const [a,b]=pop2(); pushValue(Math.pow(toNum(a),toNum(b))); break; }

      case '>':  { const [a,b]=pop2(); pushValue(toNum(a)> toNum(b)?1:0);  break; }
      case '<':  { const [a,b]=pop2(); pushValue(toNum(a)< toNum(b)?1:0);  break; }
      case '>=': { const [a,b]=pop2(); pushValue(toNum(a)>=toNum(b)?1:0); break; }
      case '<=': { const [a,b]=pop2(); pushValue(toNum(a)<=toNum(b)?1:0); break; }
      case '==': { const [a,b]=pop2(); pushValue(toNum(a)===toNum(b)?1:0); break; }
      case '!=': { const [a,b]=pop2(); pushValue(toNum(a)!==toNum(b)?1:0); break; }

      case 'and': { const [a,b]=pop2(); pushValue(truthy(a)&&truthy(b)?1:0); break; }
      case 'or':  { const [a,b]=pop2(); pushValue(truthy(a)||truthy(b)?1:0);  break; }
      case 'not': { const a=pop();     pushValue(truthy(a)?0:1);              break; }

      case 'round':{ const a=pop(); pushValue(Math.round(toNum(a))); break; }
      case 'floor':{ const a=pop(); pushValue(Math.floor(toNum(a))); break; }
      case 'ceil': { const a=pop(); pushValue(Math.ceil(toNum(a)));  break; }
      case 'abs':  { const a=pop(); pushValue(Math.abs(toNum(a)));   break; }
      case 'sqrt': { const a=pop(); pushValue(Math.sqrt(toNum(a)));  break; }
      case 'sin':  { const a=pop(); pushValue(Math.sin(toNum(a)));   break; }
      case 'cos':  { const a=pop(); pushValue(Math.cos(toNum(a)));   break; }
      case 'tan':  { const a=pop(); pushValue(Math.tan(toNum(a)));   break; }
      case 'log':  { const a=pop(); pushValue(Math.log(toNum(a)));   break; }
      case 'exp':  { const a=pop(); pushValue(Math.exp(toNum(a)));   break; }
      case 'min':  { const [a,b]=pop2(); pushValue(Math.min(toNum(a),toNum(b))); break; }
      case 'max':  { const [a,b]=pop2(); pushValue(Math.max(toNum(a),toNum(b))); break; }
      case 'clamp':{ const minVal=pop(), maxVal=pop(), val=pop();
                     pushValue(Math.max(toNum(minVal), Math.min(toNum(maxVal), toNum(val)))); break; }

      case 'dnor':{ const a=pop(); const x=toNum(a); pushValue(((x % 360) + 360) % 360); break; }

      case 'Boolean': case 'Number': case ',': return idx + 1;

      default: throw new Error('Unknown token: ' + t);
    }
    return idx + 1;
  }

  runTokens(tokens);
  return { stack, regs, vars, simvars, originalTokens: expandedTokens, simvarsDirty, functions };
}

/* ---------- step-by-step (inline highlight, incl. conditionals) ---------- */
function stepVerbose(tokensInput, context = {}){
  let toks = tokensInput.slice();
  const vars = context.vars || Array(10).fill(0);
  const regs = context.regs || Array(10).fill(0);
  const simvars = context.simvars || {};
  const functions = context.functions || [];
  const fnMap = new Map(functions.map(f => [f.name, f]));

  const noColor = !!context.noColor;
  const marker = !!context.marker;
  const endStep = !!context.endStep;

  if (noColor) {
    ANSI.reset = ANSI.red = ANSI.yellow = ANSI.markOn = ANSI.markOff = '';
  }

  const isNum = (t)=>/^[-+]?\d+(?:[.,]\d+)?$/.test(String(t));

  function tokenIsValue(t){
    if (isNum(t)) return true;
    if (/^l\d+$/.test(t)) return true;
    if (/^lp\d+$/.test(t)) return true;
    if (String(t).startsWith('(A:') && String(t).endsWith(')')) return true;
    return false;
  }
  function tokenValue(t){
    if (isNum(t)) return parseFloat(String(t).replace(',','.'));
    if (/^l\d+$/.test(t)) return vars[parseInt(String(t).slice(1),10)]||0;
    if (/^lp\d+$/.test(t)) return regs[parseInt(String(t).slice(2),10)]||0;
    if (String(t).startsWith('(A:') && String(t).endsWith(')')){ const key=String(t).slice(3,-1).trim(); return simvars[key]??0; }
    throw new Error("Token not a value: "+t);
  }
  const UN_OPS = new Set(['not','round','floor','ceil','abs','sqrt','sin','cos','tan','log','exp','dnor']);
  const BIN_OPS = new Set(['+','-','*','/','%','^','>','<','>=','<=','==','!=','and','or','min','max']);
  function arity(op){
    if (UN_OPS.has(op)) return 1;
    if (BIN_OPS.has(op)) return 2;
    if (op === 'clamp') return 3;
    if (op === 'if{') return 1; // conditional pops 1 value
    const f = fnMap.get(op);
    if (f) return f.params;
    return 0;
  }
  function apply(op, arr){
    switch(op){
      case '+': return arr[0]+arr[1];
      case '-': return arr[0]-arr[1];
      case '*': return arr[0]*arr[1];
      case '/': return arr[0]/arr[1];
      case '%': return arr[0]%arr[1];
      case '^': return Math.pow(arr[0],arr[1]);
      case '>': return arr[0]>arr[1]?1:0;
      case '<': return arr[0]<arr[1]?1:0;
      case '>=': return arr[0]>=arr[1]?1:0;
      case '<=': return arr[0]<=arr[1]?1:0;
      case '==': return arr[0]===arr[1]?1:0;
      case '!=': return arr[0]!==arr[1]?1:0;
      case 'and': return (arr[0]?1:0)&&(arr[1]?1:0)?1:0;
      case 'or' : return (arr[0]?1:0)||(arr[1]?1:0)?1:0;
      case 'not': return arr[0]?0:1;
      case 'round': return Math.round(arr[0]);
      case 'floor': return Math.floor(arr[0]);
      case 'ceil' : return Math.ceil(arr[0]);
      case 'abs'  : return Math.abs(arr[0]);
      case 'sqrt' : return Math.sqrt(arr[0]);
      case 'sin'  : return Math.sin(arr[0]);
      case 'cos'  : return Math.cos(arr[0]);
      case 'tan'  : return Math.tan(arr[0]);
      case 'log'  : return Math.log(arr[0]);
      case 'exp'  : return Math.exp(arr[0]);
      case 'min'  : return Math.min(arr[0],arr[1]);
      case 'max'  : return Math.max(arr[0],arr[1]);
      case 'clamp': return Math.max(arr[2], Math.min(arr[1], arr[0]));
      case 'dnor' : return ((arr[0]%360)+360)%360;
      default: throw new Error("Unsupported op in step: "+op);
    }
  }

  function colorize(text, style) {
    if (noColor) return text;
    if (style === 'Y') return ANSI.yellow + text + ANSI.reset;
    if (style === 'R') return ANSI.red + text + ANSI.reset;
    if (style === 'M') return ANSI.markOn + text + ANSI.markOff;
    return text;
  }
  function highlightRange(tokens, start, end, styleMid) {
    const prefix = tokens.slice(0, start).join(' ');
    const mid = tokens.slice(start, end + 1).join(' ');
    const suffix = tokens.slice(end + 1).join(' ');
    let out = '';
    if (prefix) out += colorize(prefix, 'R') + (mid ? ' ' : '');
    if (mid) out += colorize(mid, styleMid);
    if (suffix) out += (mid ? ' ' : '') + colorize(suffix, 'R');
    return out;
  }
  function highlightSingleToken(tokens, idx, style) {
    const prefix = tokens.slice(0, idx).join(' ');
    const tok = tokens[idx];
    const suffix = tokens.slice(idx + 1).join(' ');
    let out = '';
    if (prefix) out += prefix + ' ';
    out += colorize(tok, style);
    if (suffix) out += ' ' + suffix;
    return out;
  }

  console.log(toks.join(' '));

  let step = 1;
  while (true){
    const segStack = [];
    let highlightStart = -1;
    let highlightEnd = -1;
    let opIndex = -1;
    let argsForLog = [];
    let numsForApply = [];
    let chosenOp = null;

    // find next reducible segment
    for (let i=0;i<toks.length;i++){
      const t = toks[i];
      if (tokenIsValue(t)){
        segStack.push({start:i,end:i,val:tokenValue(t),text:String(t)});
        continue;
      }
      let k = arity(t);
      if (k===0) continue;

      // special preview for if{ to compute the block range
      if (t === 'if{') {
        if (segStack.length < 1) continue;
        // find block end and optional else
        const endIf = findBlockEnd(toks, i);
        let hasElse = false, elseStart = -1, endElse = -1;
        if (toks[endIf + 1] === 'else{') { hasElse = true; elseStart = endIf + 1; endElse = findBlockEnd(toks, elseStart); }
        const args = segStack.splice(segStack.length-1, 1);
        argsForLog = args;
        numsForApply = args.map(a=>a.val);
        highlightStart = args[0].start;
        highlightEnd = hasElse ? endElse : endIf; // include entire branch structure
        opIndex = i;
        chosenOp = t;
        break;
      }

      if (segStack.length >= k){
        const args = segStack.splice(segStack.length-k, k);
        argsForLog = args;
        numsForApply = args.map(a=>a.val);
        highlightStart = args[0].start;
        highlightEnd = i; // include operator
        opIndex = i;
        chosenOp = t;
        break;
      }
    }

    if (highlightStart === -1){
      break;
    }

    const styleMid = marker ? 'M' : 'Y';
    console.log(`Schritt ${step}: ${highlightRange(toks, highlightStart, highlightEnd, styleMid)}`);

    // compute result / branch
    let newToks;
    if (chosenOp === 'if{') {
      const endIf = findBlockEnd(toks, opIndex);
      let hasElse = false, elseStart = -1, endElse = -1;
      if (toks[endIf + 1] === 'else{') { hasElse = true; elseStart = endIf + 1; endElse = findBlockEnd(toks, elseStart); }
      const cond = numsForApply[0] || 0;
      const takeIf = cond !== 0;
      const ifBody = toks.slice(opIndex + 1, endIf);
      const elseBody = hasElse ? toks.slice(elseStart + 1, endElse) : [];
      const body = takeIf ? ifBody : elseBody;
      // evaluate body
      const sub = evaluateRPN(body.join(' '), { vars: vars.slice(), simvars: {...simvars}, functions: Array.from(fnMap.values()), results: [] });
      const outVals = sub.stack.map(v => String(Number.isFinite(v) && Math.abs(v - Math.round(v))<1e-12 ? Math.round(v) : v));
      const which = takeIf ? 'IF' : (hasElse ? 'ELSE' : 'NONE');

      // Build semantic preview line:
      // cond if{ visibleIf } else{ visibleElse } -> Zweig: WHICH -> outputs
      const visibleIf = takeIf ? ifBody.join(' ') : '...';
      const visibleElse = hasElse ? (takeIf ? '...' : elseBody.join(' ')) : null;
      const preview = `${argsForLog[0].text} if{ ${visibleIf} }${hasElse ? ` else{ ${visibleElse} }` : ''} → Zweig: ${which} → ${outVals.join(' ')}`;
      console.log(`${noColor ? '' : ANSI.yellow}${preview}${noColor ? '' : ANSI.reset}`);

      // replace [cond, if{...} [else{...}]] with outVals
      newToks = [];
      newToks.push(...toks.slice(0, highlightStart));
      newToks.push(...outVals);
      newToks.push(...toks.slice(highlightEnd + 1));
      toks = newToks;

      if (endStep) {
        const insertIdx = highlightStart + Math.max(outVals.length - 1, 0);
        const style = marker ? 'M' : 'Y';
        if (outVals.length) {
          console.log(`Schritt ${step} Ende: ${highlightSingleToken(toks, insertIdx, style)}`);
        } else {
          console.log(`Schritt ${step} Ende: ${toks.join(' ')}`);
        }
      }
    } else {
      // normal operator or function
      let res;
      const f = fnMap.get(chosenOp);
      if (f){
        const subToks = tokenize(f.rpn).map(tok => /^p(\d+)$/.test(tok) ? String(numsForApply[parseInt(tok.slice(1),10)-1] ?? 0) : tok);
        const subExpr = subToks.join(' ');
        const sub = evaluateRPN(subExpr, { vars: vars.slice(), simvars: {...simvars}, functions: Array.from(fnMap.values()), results: [] });
        res = sub.stack.length ? sub.stack[sub.stack.length-1] : 0;
      } else {
        res = apply(chosenOp, numsForApply);
      }
      const resStr = String(Number.isFinite(res) && Math.abs(res - Math.round(res))<1e-12 ? Math.round(res) : res);
      console.log(`${noColor ? '' : ANSI.yellow}${argsForLog.map(a=>a.text).join(' ')} ${chosenOp} = ${resStr}${noColor ? '' : ANSI.reset}`);

      newToks=[];
      newToks.push(...toks.slice(0, highlightStart));
      newToks.push(resStr);
      newToks.push(...toks.slice(opIndex+1));
      toks = newToks;

      if (endStep) {
        const resultIndex = highlightStart;
        const style = marker ? 'M' : 'Y';
        console.log(`Schritt ${step} Ende: ${highlightSingleToken(toks, resultIndex, style)}`);
      }
    }

    step++;
    if (toks.length===1) break;
  }
  console.log(toks.join(' '));
}

/* ---------- prompts for pN ---------- */
function question(rl, q){ return new Promise(resolve => rl.question(q, answer => resolve(answer))); }
async function promptParamsIfNeeded(expr, initialParams = {}, { noPrompt = false } = {}){
  const toks = tokenize(expr);
  const used = new Set(toks.filter(t => /^p\d+$/.test(t)));
  const missing = [...used].filter(k => !(k in initialParams)).sort((a,b)=>parseInt(a.slice(1)) - parseInt(b.slice(1)));
  if (missing.length === 0) return initialParams;
  const rl = readline.createInterface({ input: process.stdin, output: process.stdout });
  const params = { ...initialParams };
  for (const key of missing) {
    const label = noPrompt ? '' : `Wert für ${key}: `;
    const ans = await question(rl, label);
    const raw = String(ans).trim().replace(',', '.'); const val = Number(raw);
    params[key] = Number.isFinite(val) ? val : 0;
  }
  rl.close();
  return params;
}

/* ---------- CLI ---------- */
(function cli(){
  if (require.main !== module) return;

  const argv = process.argv.slice(2);

  const doHelp = argv.includes('--help') || argv.includes('-?');
  const doStep = argv.includes('--step') || argv.includes('-s');
  const doPre  = argv.includes('--precompile') || argv.includes('-p');
  const noPrompt = argv.includes('--noprompt');

  const noColor = argv.includes('--nocolor') || argv.includes('-c') || argv.includes('-n');
  const marker = argv.includes('--mark') || argv.includes('-m');
  const endStep = argv.includes('--endstep');

  const statePath = resolveArgPath(argv, 'state', 'RPN_STATE', '.rpn_state.json');
  const simPath   = resolveArgPath(argv, 'sim',   'RPN_SIMVARS', '.simvars.json');
  const funcPath  = resolveArgPath(argv, 'func',  'RPN_FUNCS', '.rpnfunc.json');
  const stackPath = resolveArgPath(argv, 'stack', 'RPN_STACK', '.rpnstack.json');

  // ---------- Reset/Print BEFORE help/expr checks ----------
  if (argv.includes('--reset')) {
    saveVars(statePath, Array(10).fill(0));
    console.log('Variablen s0..s9 zurückgesetzt.');
    console.log('State-Datei:', statePath);
    return;
  }
  if (argv.includes('--print')) {
    const vars = loadVars(statePath);
    console.log('Persistente Variablen (s0..s9):', vars);
    console.log('State-Datei:', statePath);
    return;
  }

  const ctxIdx = argv.indexOf('--ctx');
  let inlineCtx = {};
  if (ctxIdx !== -1 && argv[ctxIdx + 1]) {
    try { inlineCtx = JSON.parse(argv[ctxIdx + 1]); }
    catch (e) { console.error('Error: --ctx ist kein gültiges JSON:', e.message); process.exit(1); }
  }

  // expression detection AFTER admin flags
  const hasExpr = argv.length && !argv[0].startsWith('--') && !argv[0].startsWith('-');
  const expr = hasExpr ? argv[0] : '';

  if (doHelp || !hasExpr) {
    console.log(`Usage:
  node rpn.js "<expr>" [options]

Options:
  --step, -s         Step mode (inline highlight); use --endstep to also show postfix after each step
  --endstep          Also print postfix after each step and highlight the new result token
  --precompile, -p   Expand functions upfront (remove pN)
  --nocolor, -c/-n   Disable ANSI colors
  --mark, -m         Use yellow background (marker style) for highlights
  --noprompt         Hide pN prompt labels (input still required)
  --state FILE       Persistent vars (s0..s9)
  --sim FILE         SimVars file (A:... / (>A:...))
  --func FILE        Functions file (array of {name,params,rpn})
  --stack FILE       Result history file (r1..r8)
  --ctx JSON         Inline context (e.g., simvars, params)
  --print            Print persistent vars (works without <expr>)
  --reset            Reset persistent vars (works without <expr>)
  --help, -?         This help

Examples:
  node rpn.js "1 2 3 4 + + +" --endstep
  node rpn.js "1 if{ 2 + }"
  node rpn.js "0 if{ 2 + } else{ 5 + }"
  node rpn.js --print
  node rpn.js --reset
`);
    if (!hasExpr) return;
  }

  const vars = loadVars(statePath);
  const functions = loadFuncs(funcPath);
  const fileSimvars = loadSimvars(simPath);
  const runtimeSimvars = { ...fileSimvars, ...(inlineCtx.simvars || {}) };
  const resultsHistory = loadResults(stackPath);

  (async () => {
    const providedParams = inlineCtx.params || {};
    const finalParams = await promptParamsIfNeeded(expr, providedParams, { noPrompt });

    try {
      let evalExpr = expr;
      if (doPre) {
        const pre = precompileTokens(tokenize(expr), functions);
        evalExpr = pre.join(' ');
      }

      const { stack, regs, vars: outVars, simvars: outSimvars, originalTokens, simvarsDirty, functions: outFunctions } =
        evaluateRPN(evalExpr, { vars, params: finalParams, simvars: runtimeSimvars, functions, results: resultsHistory });

      // Persist
      saveVars(statePath, outVars);
      if (simvarsDirty) saveSimvars(simPath, outSimvars);

      // History (unless pure r recall)
      if (!isPureRTokenExpression(expr)) {
        const newHistory = [ [...stack], ...resultsHistory ].slice(0,8);
        saveResults(stackPath, newHistory);
      }

      const doStepEffective = (endStep || (argv.includes('--step') || argv.includes('-s')));
      if (doStepEffective) {
        stepVerbose(originalTokens, { vars: outVars, regs, simvars: outSimvars, functions: outFunctions, noColor, marker, endStep });
      } else {
        console.log(stack.join(' '));
      }

    } catch (e) {
      console.error('Error:', e.message);
      process.exit(1);
    }
  })();
})();

module.exports = { evaluateRPN, precompileTokens };
