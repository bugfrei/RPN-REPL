#!/usr/bin/env node
/**
 * RPN Evaluator (Mobiflight/MSFS-flavored) mit persistenten Variablen
 * - s0..s9  : speichern (persistent; pop vom Stack)
 * - l0..l9  : laden (persistent)
 * - sp0..sp9: speichern (flüchtig; keep auf Stack)
 * - lp0..lp9: laden (flüchtig)
 * - Mathe: + - * / % ^, round floor ceil abs min max clamp sqrt sin cos tan log exp
 * - Logik/Vergleich: and or not, > < >= <= == !=
 * - Blöcke: if{ } else{ }
 * - SimVar-Token: (A:NAME:idx, Type) aus options.simvars
 *
 * CLI:
 *   node rpn.js "<expr>" [--state ./state.json] [--print] [--reset]
 */

const fs = require('fs');
const path = require('path');
const os = require('os');

/* -------------- State / Persistenz -------------- */
function resolveStatePath(argv) {
  const i = argv.indexOf('--state');
  if (i !== -1 && argv[i + 1]) return path.resolve(argv[i + 1]);
  if (process.env.RPN_STATE) return path.resolve(process.env.RPN_STATE);
  return path.join(os.homedir(), '.rpn_state.json');
}
function loadVars(statePath) {
  try {
    const raw = fs.readFileSync(statePath, 'utf8');
    const obj = JSON.parse(raw);
    if (Array.isArray(obj.vars)) {
      const arr = obj.vars.map(Number);
      // nur s0..s9 verwenden
      const out = Array(10).fill(0);
      for (let i = 0; i < Math.min(10, arr.length); i++) out[i] = Number.isFinite(arr[i]) ? arr[i] : 0;
      return out;
    }
  } catch { /* first run or unreadable */ }
  return Array(10).fill(0);
}
function atomicWrite(filePath, data) {
  const dir = path.dirname(filePath);
  if (!fs.existsSync(dir)) fs.mkdirSync(dir, { recursive: true });
  const tmp = path.join(dir, `.tmp-${Date.now()}-${Math.random().toString(16).slice(2)}.json`);
  fs.writeFileSync(tmp, data, 'utf8');
  fs.renameSync(tmp, filePath);
}
function saveVars(statePath, vars) {
  const payload = JSON.stringify({ vars }, null, 2);
  try { atomicWrite(statePath, payload); }
  catch (e) { console.error('Warn: Konnte Variablen nicht speichern:', e.message); }
}

/* -------------- Tokenizer -------------- */
function tokenize(src) {
  const tokens = [];
  let i = 0;
  while (i < src.length) {
    if (/\s/.test(src[i])) { i++; continue; }
    if (src[i] === '(') { // SimVar/Parenthesis als ein Token
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
    if (src[i] === '}') { tokens.push('}'); i++; continue; }

    let j = i;
    while (j < src.length && !/\s/.test(src[j]) && !'(){}'.includes(src[j])) j++;
    tokens.push(src.slice(i, j));
    i = j;
  }
  return tokens.filter(Boolean);
}

/* -------------- Helpers -------------- */
function isNumber(t) { return /^[-+]?\d+(\.\d+)?$/.test(t); }
function toNum(v) { return typeof v === 'boolean' ? (v ? 1 : 0) : Number(v); }
function truthy(v) { return !!toNum(v); }

/* -------------- Evaluator -------------- */
function evaluateRPN(src, options = {}) {
  const tokens = tokenize(src || '');
  const stack = [];
  const regs = Array(10).fill(0);            // sp/lp: flüchtig
  const vars = options.vars || Array(10).fill(0); // s/l : persistent (Referenz)
  const params = options.params || {};
  const simvars = options.simvars || {};

  function pop() { if (!stack.length) throw new Error('stack underflow'); return stack.pop(); }
  function pop2() { if (stack.length < 2) throw new Error('stack underflow'); const b = stack.pop(); const a = stack.pop(); return [a, b]; }
  function runTokens(toks) { let i = 0; while (i < toks.length) i = resolveToken(toks[i], i); }

  function resolveToken(t, idx) {
    // Zahlen
    if (isNumber(t.replace(",","."))) { stack.push(parseFloat(t.replace(",","."))); return idx + 1; }

    // Parameter p0..p9
    if (/^p\d+$/.test(t)) { stack.push(params[t] ?? 0); return idx + 1; }

    // spN / lpN (flüchtig)
    if (/^sp\d+$/.test(t)) {
      const n = parseInt(t.slice(2), 10);
      if (n < 0 || n > 9) throw new Error('sp index out of range');
      regs[n] = stack.at(-1) ?? 0; return idx + 1;
    }
    if (/^lp\d+$/.test(t)) {
      const n = parseInt(t.slice(2), 10);
      if (n < 0 || n > 9) throw new Error('lp index out of range');
      stack.push(regs[n]); return idx + 1;
    }

    // sN (persistent store; pop) / lN (persistent load)
    if (/^s\d+$/.test(t)) {
      const n = parseInt(t.slice(1), 10);
      if (n < 0 || n > 9) throw new Error('s index out of range');
      if (!stack.length) throw new Error('stack underflow');
      vars[n] = stack.pop(); return idx + 1;
    }
    if (/^l\d+$/.test(t)) {
      const n = parseInt(t.slice(1), 10);
      if (n < 0 || n > 9) throw new Error('l index out of range');
      stack.push(vars[n]); return idx + 1;
    }

    // SimVar-Token (A: ... )
    if (t.startsWith('(A:') && t.endsWith(')')) {
      const key = t.slice(3, -1).trim();
      stack.push(simvars[key] ?? 0); return idx + 1;
    }

    // Operatoren & Funktionen
    switch (t) {
      // Arithmetik
      case '+': { const [a,b]=pop2(); stack.push(toNum(a)+toNum(b)); break; }
      case '-': { const [a,b]=pop2(); stack.push(toNum(a)-toNum(b)); break; }
      case '*': { const [a,b]=pop2(); stack.push(toNum(a)*toNum(b)); break; }
      case '.': { const [a,b]=pop2(); stack.push(toNum(a)*toNum(b)); break; }
      case '/': { const [a,b]=pop2(); stack.push(toNum(a)/toNum(b)); break; }
      case '%': { const [a,b]=pop2(); stack.push(toNum(a)%toNum(b)); break; }
      case '^': { const [a,b]=pop2(); stack.push(Math.pow(toNum(a),toNum(b))); break; }

      // Vergleiche
      case '>':  { const [a,b]=pop2(); stack.push(toNum(a)> toNum(b)?1:0); break; }
      case '<':  { const [a,b]=pop2(); stack.push(toNum(a)< toNum(b)?1:0); break; }
      case '>=': { const [a,b]=pop2(); stack.push(toNum(a)>=toNum(b)?1:0); break; }
      case '<=': { const [a,b]=pop2(); stack.push(toNum(a)<=toNum(b)?1:0); break; }
      case '==': { const [a,b]=pop2(); stack.push(toNum(a)===toNum(b)?1:0); break; }
      case '!=': { const [a,b]=pop2(); stack.push(toNum(a)!==toNum(b)?1:0); break; }

      // Logik
      case 'and': { const [a,b]=pop2(); stack.push(truthy(a)&&truthy(b)?1:0); break; }
      case 'or':  { const [a,b]=pop2(); stack.push(truthy(a)||truthy(b)?1:0); break; }
      case 'not': { const a=pop(); stack.push(truthy(a)?0:1); break; }

      // Mathe-Funktionen
      case 'round':{ const a=pop(); stack.push(Math.round(toNum(a))); break; }
      case 'floor':{ const a=pop(); stack.push(Math.floor(toNum(a))); break; }
      case 'ceil': { const a=pop(); stack.push(Math.ceil(toNum(a))); break; }
      case 'abs':  { const a=pop(); stack.push(Math.abs(toNum(a))); break; }
      case 'sqrt': { const a=pop(); stack.push(Math.sqrt(toNum(a))); break; }
      case 'sin':  { const a=pop(); stack.push(Math.sin(toNum(a))); break; }
      case 'cos':  { const a=pop(); stack.push(Math.cos(toNum(a))); break; }
      case 'tan':  { const a=pop(); stack.push(Math.tan(toNum(a))); break; }
      case 'log':  { const a=pop(); stack.push(Math.log(toNum(a))); break; }
      case 'exp':  { const a=pop(); stack.push(Math.exp(toNum(a))); break; }
      case 'min':  { const [a,b]=pop2(); stack.push(Math.min(toNum(a),toNum(b))); break; }
      case 'max':  { const [a,b]=pop2(); stack.push(Math.max(toNum(a),toNum(b))); break; }
      case 'clamp':{ const [minVal,maxVal,val]=[pop(),pop(),pop()];
                     stack.push(Math.max(toNum(minVal), Math.min(toNum(maxVal), toNum(val)))); break; }

      // Bedingte Blöcke
      case 'if{': {
        const cond = truthy(pop());
        const thenBlock=[], elseBlock=[];
        let depth=0, i=idx+1;
        for (; i<tokens.length; i++) {
          const tok=tokens[i];
          if (tok==='if{') { depth++; thenBlock.push(tok); continue; }
          if (tok==='}')   { if (depth===0) { i++; break; } depth--; thenBlock.push(tok); continue; }
          if (tok==='else{' && depth===0) break;
          thenBlock.push(tok);
        }
        let k=i;
        if (tokens[k]==='else{') {
          k++; let d=0;
          for (; k<tokens.length; k++) {
            const tok=tokens[k];
            if (tok==='if{') { d++; elseBlock.push(tok); continue; }
            if (tok==='}')   { if (d===0) { k++; break; } d--; elseBlock.push(tok); continue; }
            elseBlock.push(tok);
          }
        }
        runTokens(cond ? thenBlock : elseBlock);
        return k;
      }

      // no-op Tokens aus MSFS-Skripten
      case 'Boolean': case 'Number': case ',': return idx + 1;

      default:
        throw new Error('Unknown token: ' + t);
    }
    return idx + 1;
  }

  runTokens(tokens);
  return { stack, regs, vars };
}

/* -------------- CLI -------------- */
/* -------------- CLI -------------- */
(function cli() {
  if (require.main !== module) return;

  const fs = require('fs');
  const path = require('path');

  const argv = process.argv.slice(2);
  const statePath = resolveStatePath(argv);

  // Flags
  const hasExpr = argv.length && !argv[0].startsWith('--');
  const expr = hasExpr ? argv[0] : '';

  // Optionale Context-Quellen
  const ctxIdx = argv.indexOf('--ctx');
  const simIdx = argv.indexOf('--sim');

  let ctx = {};
  if (simIdx !== -1 && argv[simIdx + 1]) {
    try {
      const raw = fs.readFileSync(path.resolve(argv[simIdx + 1]), 'utf8');
      ctx = JSON.parse(raw);
    } catch (e) {
      console.error('Error: --sim konnte nicht gelesen/parsed werden:', e.message);
      process.exit(1);
    }
  }
  if (ctxIdx !== -1 && argv[ctxIdx + 1]) {
    try {
      const inline = JSON.parse(argv[ctxIdx + 1]);
      ctx = { ...ctx, ...inline }; // inline überschreibt Datei
    } catch (e) {
      console.error('Error: --ctx ist kein gültiges JSON:', e.message);
      process.exit(1);
    }
  }

  // Persistente Variablen laden
  let vars = loadVars(statePath);

  // Reset?
  if (argv.includes('--reset')) {
    vars = Array(10).fill(0);
    saveVars(statePath, vars);
    console.log('Variablen s0..s9 zurückgesetzt:', vars);
    if (!hasExpr) return;
  }

  // Print ohne Ausdruck?
  if (argv.includes('--print') && !hasExpr) {
    console.log('Persistente Variablen:', vars);
    console.log('State-Datei:', statePath);
    return;
  }

  if (!hasExpr) {
    console.log(`Usage:
  node rpn.js "<expr>" [--state ./state.json] [--print] [--reset] [--ctx '<json>'] [--sim ctx.json]

Beispiele:
  node rpn.js "(A:GENERAL ENG THROTTLE LEVER POSITION:1, Percent) 10 +" --ctx '{"simvars":{"GENERAL ENG THROTTLE LEVER POSITION:1, Percent":65}}'
  node rpn.js "(A:INDICATED ALTITUDE, feet) (A:RADIO ALTITUDE, feet) + 2 /" --sim sim.json
  node rpn.js "5 3 + s0"
  node rpn.js "l0 3 -"
`);
    return;
  }

  try {
    const { stack, vars: outVars } = evaluateRPN(expr, {
      vars,
      params: ctx.params || {},
      simvars: ctx.simvars || {}
    });
    // Speichern der persistenten Variablen
    saveVars(statePath, outVars);
    // Ergebnis ausgeben
    console.log(stack.join(' '));
  } catch (e) {
    console.error('Error:', e.message);
    process.exit(1);
  }
})();
