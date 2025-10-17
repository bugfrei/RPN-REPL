#!/usr/bin/env node
/**
 * RPN Evaluator (Mobiflight/MSFS flavored)
 * - Prints expanded postfix (functions inlined) in cyan, then result stack
 * - Optional interactive prompts for p1, p2, ... (disable via --noprompt)
 * - Persistenz: s0..s9 → ~/.rpn_state.json (oder --state)
 * - Flüchtig:   sp0..sp9 / lp0..lp9
 * - SimVars:    (A:NAME,Type) lesen | (>A:NAME,Type) schreiben → ~/.simvars.json (oder --sim)
 * - Funktionen: ~/.rpnfunc.json (oder --func), inline-Expansion ohne doppelte Argumente
 * - History:    ~/.rpnstack.json (oder --stack), max 8; r[position][,stackpos]; r-only überschreibt nicht
 */

const fs = require('fs');
const path = require('path');
const os = require('os');
const readline = require('readline');

const COLOR_POSTFIX = '\x1b[36m'; // cyan
const COLOR_RESET   = '\x1b[0m';

/* ---------- Pfade & Persistenz ---------- */
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
function loadJSON(p, def) {
  try { return JSON.parse(fs.readFileSync(p, 'utf8')); } catch { return def; }
}
function saveJSON(p, obj) {
  try { atomicWrite(p, JSON.stringify(obj, null, 2)); } catch (e) { console.error('Warn:', e.message); }
}
function loadVars(p) { const o = loadJSON(p, { vars: Array(10).fill(0) }); return Array.isArray(o.vars) ? o.vars.slice(0,10).map(Number) : Array(10).fill(0); }
function saveVars(p, vars) { saveJSON(p, { vars }); }
function loadSimvars(p) { const o = loadJSON(p, { simvars: {} }); return o.simvars || {}; }
function saveSimvars(p, simvars) { saveJSON(p, { simvars }); }
function loadFuncs(p) { const a = loadJSON(p, []); return Array.isArray(a) ? a.filter(f => f && typeof f.name==='string' && Number.isFinite(f.params) && typeof f.rpn==='string') : []; }
function loadResults(p) { const o = loadJSON(p, { results: [] }); return Array.isArray(o.results) ? o.results.filter(Array.isArray) : []; }
function saveResults(p, results) { saveJSON(p, { results: results.slice(0,8) }); }

/* ---------- Tokenizer ---------- */
function tokenize(src) {
  const tokens = [];
  let i = 0;
  while (i < src.length) {
    const ch = src[i];
    if (/\s/.test(ch)) { i++; continue; }
    if (ch === '(') { // (A:...) or (>A:...) single token
      let depth = 1, j = i + 1;
      while (j < src.length && depth > 0) {
        if (src[j] === '(') depth++;
        else if (src[j] === ')') depth--;
        j++;
      }
      tokens.push(src.slice(i, j));
      i = j;
      continue;
    }
    if (src.startsWith('if{', i)) { tokens.push('if{'); i += 3; continue; }
    if (src.startsWith('else{', i)) { tokens.push('else{'); i += 5; continue; }
    if (ch === '}') { tokens.push('}'); i++; continue; }
    let j = i;
    while (j < src.length && !/\s/.test(src[j]) && !'(){}'.includes(src[j])) j++;
    tokens.push(src.slice(i, j));
    i = j;
  }
  return tokens.filter(Boolean);
}

/* ---------- Helpers ---------- */
function isNumberToken(t) { return /^[-+]?\d+(?:[.,]\d+)?$/.test(t); }
function parseNumber(t) { return parseFloat(t.replace(',', '.')); }
function toNum(v){ return typeof v === 'boolean' ? (v?1:0) : Number(v); }
function truthy(v){ return !!toNum(v); }
function fmt(v){ const n = Number(v); if (Number.isFinite(n) && Math.abs(n - Math.round(n)) < 1e-12) return String(Math.round(n)); return String(n); }
function isPureRTokenExpression(src){
  const toks = tokenize(src || '');
  return toks.length === 1 && /^r(\d+)?(,\d+)?$/.test(toks[0]);
}

/* ---------- Evaluator mit Emissions-Stack (korrekte Funktions-Expansion) ---------- */
function evaluateRPN(src, options = {}) {
  const tokens = tokenize(src || '');
  const stack = [];
  const emitStack = []; // { start: number }
  const regs = Array(10).fill(0);
  const vars = options.vars || Array(10).fill(0);
  const simvars = options.simvars || {};
  const params = options.params || {};
  const functions = options.functions || [];
  const results = options.results || []; // history
  let simvarsDirty = false;

  const expandedTokens = []; // finaler expandierter Postfix

  function pushValue(val, tokenForEmission) {
    stack.push(val);
    const start = expandedTokens.length;
    if (tokenForEmission) expandedTokens.push(tokenForEmission);
    emitStack.push({ start });
  }
  function pop(){ if (!stack.length) throw new Error('stack underflow'); emitStack.pop(); return stack.pop(); }
  function pop2(){ if (stack.length<2) throw new Error('stack underflow'); const b = pop(), a = pop(); return [a,b]; }

  function runTokens(toks){
    let i = 0;
    while (i < toks.length) i = resolveToken(toks[i], i, toks);
  }

  function resolveToken(t, idx, toks) {
    // Zahlen
    if (isNumberToken(t)) { const v = parseNumber(t); pushValue(v, fmt(v)); return idx + 1; }

    // r[position][,stackposition]
    if (/^r(\d+)?(,\d+)?$/.test(t)) {
      const m=/^r(\d+)?(,\d+)?$/.exec(t);
      const ri=m[1]?parseInt(m[1],10):1;
      const si=m[2]?parseInt(m[2].slice(1),10):null;
      if (ri<1||ri>8) throw new Error("r: Ergebnis-Index außerhalb 1..8");
      const res=results[ri-1]; if(!res) throw new Error(`r: kein gespeichertes Ergebnis r${ri}`);
      const start = expandedTokens.length;
      expandedTokens.push(t);
      if (si==null){
        res.forEach((v)=>{ stack.push(v); emitStack.push({ start }); });
      } else {
        stack.push(res[si-1]); emitStack.push({ start });
      }
      return idx + 1;
    }

    // Parameter pN
    if (/^p\d+$/.test(t)) {
      const v = params[t] ?? 0;
      pushValue(v, fmt(v));
      return idx + 1;
    }

    // spN / lpN
    if (/^sp\d+$/.test(t)) { const n=parseInt(t.slice(2),10); if(n<0||n>9) throw new Error('sp index'); regs[n]=stack.at(-1)??0; expandedTokens.push(t); return idx+1; }
    if (/^lp\d+$/.test(t)) { const n=parseInt(t.slice(2),10); if(n<0||n>9) throw new Error('lp index'); pushValue(regs[n], 'lp'+n); return idx+1; }

    // sN / lN
    if (/^s\d+$/.test(t)) { const n=parseInt(t.slice(1),10); if(n<0||n>9) throw new Error('s index'); if(!stack.length) throw new Error('stack underflow'); pop(); vars[n]=stack.at(-1)??vars[n]; expandedTokens.push(t); return idx+1; }
    if (/^l\d+$/.test(t)) { const n=parseInt(t.slice(1),10); if(n<0||n>9) throw new Error('l index'); pushValue(vars[n], 'l'+n); return idx+1; }

    // SimVar lesen/schreiben
    if (t.startsWith('(A:') && t.endsWith(')')) { const key=t.slice(3,-1).trim(); pushValue(simvars[key]??0, t); return idx+1; }
    if (t.startsWith('(>A:') && t.endsWith(')')){ const key=t.slice(4,-1).trim(); if(!stack.length) throw new Error('stack underflow on (>A:...)'); pop(); simvars[key]=stack.at(-1); simvarsDirty=true; expandedTokens.push(t); return idx+1; }

    // Custom-Funktion → inline expandieren
    const func = functions.find(f => f.name === t);
    if (func) {
      if (stack.length < func.params) throw new Error(`function '${func.name}' benötigt ${func.params} Parameter`);
      const ps = Array(func.params);
      const argStarts = [];
      for (let k = func.params - 1; k >= 0; k--) {
        ps[k] = stack.pop();
        const e = emitStack.pop();
        argStarts.push(e.start);
      }
      const start = Math.min(...argStarts);
      expandedTokens.length = start; // Tokens der Argumente entfernen

      const localParams = {};
      ps.forEach((v,i)=>{ localParams['p'+(i+1)] = v; });

      const sub = evaluateRPN(func.rpn, { vars, simvars, params: localParams, functions, results });
      expandedTokens.push(...sub.expandedTokens);
      sub.stack.forEach(v => { stack.push(v); emitStack.push({ start }); });
      if (sub.simvarsDirty) simvarsDirty = true;
      return idx + 1;
    }

    // Operatoren / Funktionen
    switch (t) {
      // Arithmetik
      case '+': { const [a,b]=pop2(); stack.push(toNum(a)+toNum(b)); expandedTokens.push('+'); emitStack.push({ start: expandedTokens.length - 1 }); break; }
      case '-': { const [a,b]=pop2(); stack.push(toNum(a)-toNum(b)); expandedTokens.push('-'); emitStack.push({ start: expandedTokens.length - 1 }); break; }
      case '*': { const [a,b]=pop2(); stack.push(toNum(a)*toNum(b)); expandedTokens.push('*'); emitStack.push({ start: expandedTokens.length - 1 }); break; }
      case '/': { const [a,b]=pop2(); stack.push(toNum(a)/toNum(b)); expandedTokens.push('/'); emitStack.push({ start: expandedTokens.length - 1 }); break; }
      case '%': { const [a,b]=pop2(); stack.push(toNum(a)%toNum(b)); expandedTokens.push('%'); emitStack.push({ start: expandedTokens.length - 1 }); break; }
      case '^': { const [a,b]=pop2(); stack.push(Math.pow(toNum(a),toNum(b))); expandedTokens.push('^'); emitStack.push({ start: expandedTokens.length - 1 }); break; }

      // Vergleiche
      case '>':  { const [a,b]=pop2(); stack.push(toNum(a)> toNum(b)?1:0); expandedTokens.push('>');  emitStack.push({ start: expandedTokens.length - 1 }); break; }
      case '<':  { const [a,b]=pop2(); stack.push(toNum(a)< toNum(b)?1:0); expandedTokens.push('<');  emitStack.push({ start: expandedTokens.length - 1 }); break; }
      case '>=': { const [a,b]=pop2(); stack.push(toNum(a)>=toNum(b)?1:0); expandedTokens.push('>='); emitStack.push({ start: expandedTokens.length - 1 }); break; }
      case '<=': { const [a,b]=pop2(); stack.push(toNum(a)<=toNum(b)?1:0); expandedTokens.push('<='); emitStack.push({ start: expandedTokens.length - 1 }); break; }
      case '==': { const [a,b]=pop2(); stack.push(toNum(a)===toNum(b)?1:0); expandedTokens.push('=='); emitStack.push({ start: expandedTokens.length - 1 }); break; }
      case '!=': { const [a,b]=pop2(); stack.push(toNum(a)!==toNum(b)?1:0); expandedTokens.push('!='); emitStack.push({ start: expandedTokens.length - 1 }); break; }

      // Logik
      case 'and': { const [a,b]=pop2(); stack.push(truthy(a)&&truthy(b)?1:0); expandedTokens.push('and'); emitStack.push({ start: expandedTokens.length - 1 }); break; }
      case 'or':  { const [a,b]=pop2(); stack.push(truthy(a)||truthy(b)?1:0); expandedTokens.push('or');  emitStack.push({ start: expandedTokens.length - 1 }); break; }
      case 'not': { const a=pop();     stack.push(truthy(a)?0:1);          expandedTokens.push('not'); emitStack.push({ start: expandedTokens.length - 1 }); break; }

      // Math
      case 'round':{ const a=pop(); stack.push(Math.round(toNum(a))); expandedTokens.push('round'); emitStack.push({ start: expandedTokens.length - 1 }); break; }
      case 'floor':{ const a=pop(); stack.push(Math.floor(toNum(a))); expandedTokens.push('floor'); emitStack.push({ start: expandedTokens.length - 1 }); break; }
      case 'ceil': { const a=pop(); stack.push(Math.ceil(toNum(a)));  expandedTokens.push('ceil');  emitStack.push({ start: expandedTokens.length - 1 }); break; }
      case 'abs':  { const a=pop(); stack.push(Math.abs(toNum(a)));   expandedTokens.push('abs');   emitStack.push({ start: expandedTokens.length - 1 }); break; }
      case 'sqrt': { const a=pop(); stack.push(Math.sqrt(toNum(a)));  expandedTokens.push('sqrt');  emitStack.push({ start: expandedTokens.length - 1 }); break; }
      case 'sin':  { const a=pop(); stack.push(Math.sin(toNum(a)));   expandedTokens.push('sin');   emitStack.push({ start: expandedTokens.length - 1 }); break; }
      case 'cos':  { const a=pop(); stack.push(Math.cos(toNum(a)));   expandedTokens.push('cos');   emitStack.push({ start: expandedTokens.length - 1 }); break; }
      case 'tan':  { const a=pop(); stack.push(Math.tan(toNum(a)));   expandedTokens.push('tan');   emitStack.push({ start: expandedTokens.length - 1 }); break; }
      case 'log':  { const a=pop(); stack.push(Math.log(toNum(a)));   expandedTokens.push('log');   emitStack.push({ start: expandedTokens.length - 1 }); break; }
      case 'exp':  { const a=pop(); stack.push(Math.exp(toNum(a)));   expandedTokens.push('exp');   emitStack.push({ start: expandedTokens.length - 1 }); break; }
      case 'min':  { const [a,b]=pop2(); stack.push(Math.min(toNum(a),toNum(b))); expandedTokens.push('min'); emitStack.push({ start: expandedTokens.length - 1 }); break; }
      case 'max':  { const [a,b]=pop2(); stack.push(Math.max(toNum(a),toNum(b))); expandedTokens.push('max'); emitStack.push({ start: expandedTokens.length - 1 }); break; }
      case 'clamp':{ const [minVal,maxVal,val]=[pop(),pop(),pop()];
                     stack.push(Math.max(toNum(minVal), Math.min(toNum(maxVal), toNum(val))));
                     expandedTokens.push('clamp'); emitStack.push({ start: expandedTokens.length - 1 }); break; }

      // Direction Normalize
      case 'dnor':{ const a=pop(); const x=toNum(a); stack.push(((x % 360) + 360) % 360); expandedTokens.push('dnor'); emitStack.push({ start: expandedTokens.length - 1 }); break; }

      // Blöcke
      case 'if{': {
        const cond = truthy(pop());
        const thenBlock=[], elseBlock=[];
        let depth=0, i=idx+1;
        for(; i<tokens.length; i++){
          const tok=tokens[i];
          if(tok==='if{'){ depth++; thenBlock.push(tok); continue; }
          if(tok==='}'){ if(depth===0){ i++; break; } depth--; thenBlock.push(tok); continue; }
          if(tok==='else{' && depth===0) break;
          thenBlock.push(tok);
        }
        let k = i;
        if(tokens[k]==='else{'){
          k++; let d=0;
          for(; k<tokens.length; k++){
            const tok=tokens[k];
            if(tok==='if{'){ d++; elseBlock.push(tok); continue; }
            if(tok==='}'){ if(d===0){ k++; break; } d--; elseBlock.push(tok); continue; }
            elseBlock.push(tok);
          }
        }
        if (cond) runTokens(thenBlock);
        else      runTokens(elseBlock);
        return k;
      }

      // No-op / Kompatibilität
      case 'Boolean': case 'Number': case ',': expandedTokens.push(t); return idx + 1;

      default:
        throw new Error('Unknown token: ' + t);
    }
    return idx + 1;
  }

  runTokens(tokens);
  return { stack, regs, vars, simvars, simvarsDirty, expandedTokens };
}

/* ---------- Parameter-Eingabe (p1, p2, ... ) ---------- */
function question(rl, q){
  return new Promise(resolve => rl.question(q, answer => resolve(answer)));
}
async function promptParamsIfNeeded(expr, initialParams = {}, { noPrompt = false } = {}){
  const toks = tokenize(expr);
  const used = new Set(toks.filter(t => /^p\d+$/.test(t)));
  const missing = [...used].filter(k => !(k in initialParams)).sort((a,b)=>parseInt(a.slice(1)) - parseInt(b.slice(1)));
  if (missing.length === 0 || noPrompt) return initialParams;

  const rl = readline.createInterface({ input: process.stdin, output: process.stdout });
  const params = { ...initialParams };
  for (const key of missing) {
    const ans = await question(rl, `Wert für ${key}: `);
    const raw = String(ans).trim().replace(',', '.');
    const val = Number(raw);
    params[key] = Number.isFinite(val) ? val : 0;
  }
  rl.close();
  return params;
}

/* ---------- CLI ---------- */
(async function cli(){
  if (require.main !== module) return;

  const argv = process.argv.slice(2);
  const statePath = resolveArgPath(argv, 'state', 'RPN_STATE', '.rpn_state.json');
  const simPath   = resolveArgPath(argv, 'sim',   'RPN_SIMVARS', '.simvars.json');
  const funcPath  = resolveArgPath(argv, 'func',  'RPN_FUNCS', '.rpnfunc.json');
  const stackPath = resolveArgPath(argv, 'stack', 'RPN_STACK', '.rpnstack.json');

  const noPrompt = argv.includes('--noprompt');

  // Inline-Kontext
  const ctxIdx = argv.indexOf('--ctx');
  let inlineCtx = {};
  if (ctxIdx !== -1 && argv[ctxIdx + 1]) {
    try { inlineCtx = JSON.parse(argv[ctxIdx + 1]); }
    catch (e) { console.error('Error: --ctx ist kein gültiges JSON:', e.message); process.exit(1); }
  }

  const hasExpr = argv.length && !argv[0].startsWith('--');
  const expr = hasExpr ? argv[0] : '';

  // Reset/Print handling (ohne Ausdruck)
  if (argv.includes('--reset') && !hasExpr) {
    saveVars(statePath, Array(10).fill(0));
    console.log('Variablen s0..s9 zurückgesetzt.');
    return;
  }
  if (argv.includes('--print') && !hasExpr) {
    const vars = loadVars(statePath);
    console.log('Persistente Variablen:', vars);
    console.log('State-Datei:', statePath);
    return;
  }

  if (!hasExpr) {
    console.log(`Usage:
  node rpn.js "<expr>" [--state FILE] [--print] [--reset]
               [--ctx '<json>'] [--sim FILE] [--func FILE] [--stack FILE] [--noprompt]

Ausgabe:
  1) Expandierter Postfix (Funktionen inline), in Farbe
  2) Ergebnis-Stack

Parameter p1..pN:
  - Standard: interaktive Abfrage, wenn Werte fehlen
  - Mit --noprompt: keine Abfrage (fehlende pN werden als 0 interpretiert)

Beispiele:
  node rpn.js "30 add90" --func ~/.rpnfunc.json
  node rpn.js "10 p1 + p2 *"            # fragt p1/p2 (ohne --noprompt)
  node rpn.js "10 p1 + p2 *" --noprompt # keine Prompts (gut für REPL)
`);
    return;
  }

  // Laufzeitzustand laden
  const vars = loadVars(statePath);
  const functions = loadFuncs(funcPath);
  const fileSimvars = loadSimvars(simPath);
  const runtimeSimvars = { ...fileSimvars, ...(inlineCtx.simvars || {}) };
  const resultsHistory = loadResults(stackPath);

  // Parameter ggf. abfragen (oder unterdrücken)
  const providedParams = inlineCtx.params || {};
  const finalParams = await promptParamsIfNeeded(expr, providedParams, { noPrompt });

  try {
    const { stack, vars: outVars, simvars: outSimvars, simvarsDirty, expandedTokens } =
      evaluateRPN(expr, { vars, params: finalParams, simvars: runtimeSimvars, functions, results: resultsHistory });

    // Persistenz
    saveVars(statePath, outVars);
    if (simvarsDirty) saveSimvars(simPath, outSimvars);

    // History aktualisieren (außer reiner r-Recall)
    if (!isPureRTokenExpression(expr)) {
      const newHistory = [ [...stack], ...resultsHistory ].slice(0,8);
      saveResults(stackPath, newHistory);
    }

    // Ausgabe
    const expandedStr = expandedTokens.join(' ');
    console.log(COLOR_POSTFIX + (expandedStr || expr) + COLOR_RESET);
    console.log(stack.join(' '));

  } catch (e) {
    console.error('Error:', e.message);
    process.exit(1);
  }
})();

module.exports = { evaluateRPN };
