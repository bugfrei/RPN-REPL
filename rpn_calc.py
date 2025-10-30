#!/usr/bin/env python3
# rpn_calc.py
# Unified Python RPN Calculator + REPL
# Features: persistent s0..s9, session sp0..lp0, SimVars with prefixes (A legacy compat),
# functions with params pN, precompile, step (with optional infix + endstep + mark + nocolor),
# result history r1..r8 (and rX,Y), conditionals if{ } else{ }, input mode,
# readline history + tab completion, parameter prompting (labels in CLI & REPL by default),
# :noprompt toggle in REPL to hide labels.

import os, sys, json, re, math, subprocess, atexit
from pathlib import Path

# ----------- Paths / defaults -----------
HOME = Path.home()
STATE_PATH = Path(os.environ.get("RPN_STATE", str(HOME / ".rpn_state.json")))
SIM_PATH   = Path(os.environ.get("RPN_SIMVARS", str(HOME / ".simvars.json")))
FUNC_PATH  = Path(os.environ.get("RPN_FUNCS", str(HOME / ".rpnfunc.json")))
STACK_PATH = Path(os.environ.get("RPN_STACK", str(HOME / ".rpnstack.json")))
HIST_PATH  = Path(os.environ.get("RPN_REPL_HISTORY", str(HOME / ".rpn_repl_history")))
HIST_MAX   = 100

# ----------- ANSI -----------
ANSI = {
  "reset":"\x1b[0m",
  "red":"\x1b[31m",
  "yellow":"\x1b[33m",
  "mark_on":"\x1b[43m\x1b[30m",
  "mark_off":"\x1b[0m",
}
def apply_no_color():
  for k in list(ANSI.keys()):
    ANSI[k] = ""

# ----------- IO helpers -----------
def atomic_write(path: Path, data: str):
  path.parent.mkdir(parents=True, exist_ok=True)
  tmp = path.with_name(".tmp-"+path.name)
  tmp.write_text(data, encoding="utf-8")
  tmp.replace(path)

def load_json(path: Path, default):
  try:
    return json.loads(path.read_text(encoding="utf-8"))
  except Exception:
    return default

def save_json(path: Path, obj):
  try:
    atomic_write(path, json.dumps(obj, indent=2, ensure_ascii=False))
  except Exception as e:
    print("Warn:", e, file=sys.stderr)

# ----------- Persisted state -----------
def load_state_vars() -> list:
  o = load_json(STATE_PATH, {"vars":[0]*10})
  if isinstance(o, dict) and isinstance(o.get("vars"), list):
    a = [0]*10
    for i in range(min(10, len(o["vars"]))):
      try: a[i] = float(o["vars"][i])
      except: a[i] = 0
    return a
  return [0]*10

def save_state_vars(vars_list: list):
  save_json(STATE_PATH, {"vars": list(map(float, vars_list))})

# simvars structure stored as { "simvars": { "A": {...}, "L": {...}, ... } }
# compatibility: legacy top-level scalars inside "simvars" map to A:
def load_simvars() -> dict:
  o = load_json(SIM_PATH, {"simvars": {}})
  src = o.get("simvars", {})
  out = {}
  for k,v in src.items():
    if isinstance(v, dict):
      out[k] = dict(v)
  for k,v in src.items():
    if not isinstance(v, dict):
      out.setdefault("A", {})[k] = v
  return out

def save_simvars(sim: dict):
  save_json(SIM_PATH, {"simvars": sim})

def load_funcs() -> list:
  arr = load_json(FUNC_PATH, [])
  if not isinstance(arr, list): return []
  out = []
  for f in arr:
    if isinstance(f, dict) and "name" in f and "params" in f and "rpn" in f:
      out.append({"name":str(f["name"]), "params": int(f["params"]), "rpn": str(f["rpn"])})
  return out

def load_results() -> list:
  o = load_json(STACK_PATH, {"results": []})
  arr = o.get("results", [])
  return [r for r in arr if isinstance(r, list)]

def save_results(results: list):
  save_json(STACK_PATH, {"results": results[:8]})

# ----------- Tokenizer & param helpers -----------
def tokenize(src: str):
  tokens = []
  i = 0
  n = len(src)
  while i < n:
    ch = src[i]
    if ch.isspace():
      i += 1; continue
    if ch == '(':
      depth = 1; j = i+1
      while j < n and depth > 0:
        if src[j] == '(':
          depth += 1
        elif src[j] == ')':
          depth -= 1
        j += 1
      tokens.append(src[i:j])
      i = j; continue
    if src.startswith("if{", i):
      tokens.append("if{"); i += 3; continue
    if src.startswith("else{", i):
      tokens.append("else{"); i += 5; continue
    if ch == '}':
      tokens.append('}'); i += 1; continue
    j = i
    while j < n and (not src[j].isspace()) and src[j] not in "(){}":
      j += 1
    tokens.append(src[i:j])
    i = j
  return [t for t in tokens if t]

def is_number_token(t: str) -> bool:
  return re.fullmatch(r"[-+]?\d+(?:[.,]\d+)?", t or "") is not None

def parse_number(t: str) -> float:
  return float(t.replace(",", "."))

def to_num(v): 
  if isinstance(v, bool): return 1 if v else 0
  try: return float(v)
  except: return 0.0

def is_pure_r_token_expression(src: str) -> bool:
  toks = tokenize(src or "")
  return len(toks) == 1 and re.fullmatch(r"r(\d+)?(,\d+)?", toks[0]) is not None

def collect_missing_params(tokens, existing_params):
  needed = sorted({t for t in tokens if re.fullmatch(r"p\d+", t)}, key=lambda x:int(x[1:]))
  missing = [t for t in needed if t not in existing_params]
  return missing

def prompt_params(missing, *, silent=False):
  params = {}
  for name in missing:
    try:
      val_str = input("" if silent else f"Parameter {name}: ")
    except EOFError:
      val_str = "0"
    try:
      val = float(val_str.replace(",", ".")) if val_str.strip() != "" else 0.0
    except Exception:
      val = 0.0
    params[name] = val
  return params

# ----------- Block matching -----------
def find_block_end(toks, open_index):
  depth = 1
  i = open_index + 1
  while i < len(toks):
    t = toks[i]
    if t in ("if{", "else{"):
      depth += 1
    elif t == "}":
      depth -= 1
      if depth == 0:
        return i
    i += 1
  raise RuntimeError("Fehlende schließende '}' ab Index %d" % open_index)

# ----------- Precompile functions -----------
def precompile_tokens(tokens, functions):
  func_map = {f["name"]: f for f in functions}
  changed = True
  out = tokens[:]
  while changed:
    changed = False
    nxt = []
    for t in out:
      f = func_map.get(t)
      if not f:
        nxt.append(t); continue
      body = [x for x in tokenize(f["rpn"]) if not re.fullmatch(r"p\d+", x)]
      body = precompile_tokens(body, functions)
      nxt.extend(body)
      changed = True
    out = nxt
  return out

# ----------- Evaluator -----------
SIM_RE = re.compile(r"^\((>?)([A-Za-z]+):(.*)\)$")

def evaluate_rpn(src: str, *, vars_state=None, params=None, simvars=None, functions=None, results_history=None):
  tokens = tokenize(src or "")
  stack = []
  regs = [0.0]*10
  vars_state = list(vars_state or [0.0]*10)
  params = dict(params or {})
  simvars = dict(simvars or {})
  functions = list(functions or [])
  results_history = list(results_history or [])
  func_map = {f["name"]: f for f in functions}
  sim_dirty = False

  def push(v): stack.append(v)
  def pop():
    if not stack: raise RuntimeError("stack underflow")
    return stack.pop()
  def pop2():
    if len(stack) < 2: raise RuntimeError("stack underflow")
    b = stack.pop(); a = stack.pop(); return a,b
  def pop3():
    if len(stack) < 3: raise RuntimeError("stack underflow")
    c = stack.pop(); b = stack.pop(); a = stack.pop(); return a,b,c

  def get_sim(prefix, key):
    if prefix == "A":
      if prefix in simvars and key in simvars[prefix]:
        return simvars[prefix][key]
      if key in simvars and isinstance(simvars[key], (int,float)):
        return simvars[key]
      return 0.0
    return simvars.get(prefix, {}).get(key, 0.0)

  def set_sim(prefix, key, val):
    nonlocal sim_dirty
    simvars.setdefault(prefix, {})[key] = float(val)
    sim_dirty = True

  i = 0
  while i < len(tokens):
    t = tokens[i]
    if is_number_token(t):
      push(parse_number(t)); i += 1; continue

    # params pN (no prompting here; must be injected before evaluate_rpn)
    if re.fullmatch(r"p\d+", t):
      push(to_num(params.get(t, 0))); i += 1; continue

    m = re.fullmatch(r"r(\d+)?(,\d+)?", t)
    if m:
      ri = int(m.group(1)) if m.group(1) else 1
      si = int(m.group(2)[1:]) if m.group(2) else None
      if ri - 1 >= len(results_history) or ri <= 0:
        raise RuntimeError(f"r: kein gespeichertes Ergebnis r{ri}")
      res = results_history[ri-1]
      if si is None:
        for v in res: push(v)
      else:
        if si-1 < 0 or si-1 >= len(res):
          raise RuntimeError(f"r: kein Wert an Position {si}")
        push(res[si-1])
      i += 1; continue

    if re.fullmatch(r"s\d+", t):
      n = int(t[1:])
      val = pop()
      vars_state[n] = float(val)
      i += 1; continue
    if re.fullmatch(r"l\d+", t):
      n = int(t[1:])
      push(to_num(vars_state[n] if n < len(vars_state) else 0))
      i += 1; continue

    if re.fullmatch(r"sp\d+", t):
      n = int(t[2:])
      val = stack[-1] if stack else 0
      regs[n] = float(val)
      i += 1; continue
    if re.fullmatch(r"lp\d+", t):
      n = int(t[2:])
      push(to_num(regs[n] if n < len(regs) else 0))
      i += 1; continue

    m2 = SIM_RE.fullmatch(t)
    if m2:
      write = m2.group(1) == ">"
      prefix = m2.group(2)
      key = m2.group(3).strip()
      if write:
        val = pop()
        set_sim(prefix, key, val)
      else:
        push(get_sim(prefix, key))
      i += 1; continue

    if t == "if{":
      end_if = find_block_end(tokens, i)
      has_else = False; else_start = -1; end_else = -1
      if end_if + 1 < len(tokens) and tokens[end_if+1] == "else{":
        has_else = True; else_start = end_if + 1; end_else = find_block_end(tokens, else_start)
      cond = pop()
      if to_num(cond) != 0:
        body = tokens[i+1:end_if]
        evaluate_rpn(" ".join(body), vars_state=vars_state, params=params, simvars=simvars, functions=functions, results_history=[])
        i = (end_else + 1) if has_else else (end_if + 1)
      else:
        if has_else:
          body = tokens[else_start+1:end_else]
          evaluate_rpn(" ".join(body), vars_state=vars_state, params=params, simvars=simvars, functions=functions, results_history=[])
          i = end_else + 1
        else:
          i = end_if + 1
      continue
    if t == "else{":
      end_else = find_block_end(tokens, i)
      i = end_else + 1; continue

    f_map = {f["name"]: f for f in functions}
    f = f_map.get(t)
    if f:
      k = int(f["params"])
      if len(stack) < k: raise RuntimeError(f"function '{f['name']}' benötigt {k} Parameter")
      args = [0]*k
      for idx in range(k-1, -1, -1):
        args[idx] = stack.pop()
      sub_toks = []
      for tok in tokenize(f["rpn"]):
        m = re.fullmatch(r"p(\d+)", tok)
        if m:
          sub_toks.append(str(args[int(m.group(1))-1] if 1 <= int(m.group(1)) <= k else 0))
        else:
          sub_toks.append(tok)
      sub_expr = " ".join(sub_toks)
      sub = evaluate_rpn(sub_expr, vars_state=vars_state, params=params, simvars=simvars, functions=functions, results_history=[])
      for v in sub["stack"]:
        push(v)
      i += 1; continue

    def binop(fn):
      a,b = pop2(); push(fn(to_num(a), to_num(b)))
    def unop(fn):
      a = pop(); push(fn(to_num(a)))

    if t == "+": binop(lambda a,b:a+b)
    elif t == "-": binop(lambda a,b:a-b)
    elif t == "*": binop(lambda a,b:a*b)
    elif t == "/": binop(lambda a,b:a/b)
    elif t == "%": binop(lambda a,b:a%b)
    elif t == "^": binop(lambda a,b: a**b)
    elif t in ("==","="): binop(lambda a,b: 1.0 if a==b else 0.0)
    elif t in ("!=","<>"): binop(lambda a,b: 1.0 if a!=b else 0.0)
    elif t == ">": binop(lambda a,b: 1.0 if a>b else 0.0)
    elif t == "<": binop(lambda a,b: 1.0 if a<b else 0.0)
    elif t == ">=": binop(lambda a,b: 1.0 if a>=b else 0.0)
    elif t == "<=": binop(lambda a,b: 1.0 if a<=b else 0.0)
    elif t in ("and","&&"): binop(lambda a,b: 1.0 if (a!=0 and b!=0) else 0.0)
    elif t in ("or","||"): binop(lambda a,b: 1.0 if (a!=0 or b!=0) else 0.0)
    elif t in ("not","!"): unop(lambda a: 0.0 if a!=0 else 1.0)
    elif t == "round": unop(lambda a: float(round(a)))
    elif t == "floor": unop(lambda a: float(math.floor(a)))
    elif t == "ceil":  unop(lambda a: float(math.ceil(a)))
    elif t == "abs":   unop(lambda a: float(abs(a)))
    elif t == "sin":   unop(lambda a: float(math.sin(a)))
    elif t == "cos":   unop(lambda a: float(math.cos(a)))
    elif t == "tan":   unop(lambda a: float(math.tan(a)))
    elif t == "log":   unop(lambda a: float(math.log(a)))
    elif t == "exp":   unop(lambda a: float(math.exp(a)))
    elif t == "min":   binop(lambda a,b: float(min(a,b)))
    elif t == "max":   binop(lambda a,b: float(max(a,b)))
    elif t == "clamp":
      v = pop(); hi = pop(); lo = pop()
      push(float(max(lo, min(hi, v))))
    elif t == "pow2": unop(lambda a: float(a**2))
    elif t == "pow":  binop(lambda a,b: float(a**b))
    elif t == "sqrt2": unop(lambda a: float(math.sqrt(a)))
    elif t == "sqrt":  binop(lambda a,b: float(a ** (1.0/b)))
    elif t == "dnor": unop(lambda a: float(((a % 360.0) + 360.0) % 360.0))
    elif t in ("Number","Boolean",","):
      pass
    else:
      raise RuntimeError("Unknown token: "+t)
    i += 1

  return {
    "stack": stack,
    "regs": regs,
    "vars": vars_state,
    "simvars": simvars,
    "sim_dirty": sim_dirty,
    "functions": functions,
    "original_tokens": tokens
  }

# ----------- Step visualizer -----------
UN_OPS = {"not","!","round","floor","ceil","abs","sin","cos","tan","log","exp","sqrt2","pow2","dnor"}
BIN_OPS = {"+","-","*","/","%","^",">","<",">=","<=","==","=","!=","<>","and","&&","or","||","min","max","pow","sqrt"}

def fmt_num(v):
  if isinstance(v, (int,float)) and abs(v - round(v)) < 1e-12:
    return str(int(round(v)))
  try:
    f = float(v); 
    if abs(f - round(f)) < 1e-12: return str(int(round(f)))
    return str(f)
  except: return str(v)

SIM_RE = re.compile(r"^\((>?)([A-Za-z]+):(.*)\)$")

def step_verbose(tokens, *, vars_state, regs, simvars, functions, no_color=False, marker=False, endstep=False, infix=False):
  if no_color: apply_no_color()

  func_map = {f["name"]: f for f in functions}
  def token_is_value(t):
    if is_number_token(t): return True
    if re.fullmatch(r"l\d+", t): return True
    if re.fullmatch(r"lp\d+", t): return True
    if SIM_RE.fullmatch(t): return True
    return False

  def token_value(t):
    if is_number_token(t): return parse_number(t)
    if re.fullmatch(r"l\d+", t): return float(vars_state[int(t[1:])])
    if re.fullmatch(r"lp\d+", t): return float(regs[int(t[2:])])
    m = SIM_RE.fullmatch(t)
    if m:
      pref = m.group(2); key = m.group(3).strip()
      if pref == "A":
        if pref in simvars and key in simvars[pref]: return float(simvars[pref][key])
        if key in simvars and isinstance(simvars[key], (int,float)): return float(simvars[key])
        return 0.0
      return float(simvars.get(pref, {}).get(key, 0.0))
    raise RuntimeError("Token not a value: "+t)

  def color(text, style):
    if style == "Y": return ANSI["yellow"] + text + ANSI["reset"]
    if style == "R": return ANSI["red"] + text + ANSI["reset"]
    if style == "M": return ANSI["mark_on"] + text + ANSI["mark_off"]
    return text

  def highlight_range(toks, a, b, style_mid):
    prefix = " ".join(toks[:a])
    mid = " ".join(toks[a:b+1])
    suffix = " ".join(toks[b+1:])
    out = ""
    if prefix: out += color(prefix, "R") + (" " if mid or suffix else "")
    if mid: out += color(mid, style_mid) + (" " if suffix else "")
    if suffix: out += color(suffix, "R")
    return out

  def highlight_single(toks, idx, style):
    prefix = " ".join(toks[:idx])
    tok = toks[idx]
    suffix = " ".join(toks[idx+1:])
    out = ""
    if prefix: out += prefix + " "
    out += color(tok, style)
    if suffix: out += " " + suffix
    return out

  def apply_op(op, arr):
    if op in BIN_OPS or op in UN_OPS or op == "clamp" or op == "dnor":
      tmp_src = " ".join([fmt_num(v) for v in arr] + [op])
      sub = evaluate_rpn(tmp_src, vars_state=vars_state[:], params={}, simvars=json.loads(json.dumps(simvars)), functions=functions, results_history=[])
      return sub["stack"][-1] if sub["stack"] else 0.0
    raise RuntimeError("Unsupported op in step: "+op)

  toks = list(tokens)
  print(" ".join(toks))
  step = 1
  while True:
    seg = []
    highlight_a = -1; highlight_b = -1; op_idx = -1; args = []; num_args = []; chosen = None
    for i,t in enumerate(toks):
      if token_is_value(t):
        seg.append({"start":i,"end":i,"val":token_value(t),"text":t})
        continue
      if t == "if{":
        if len(seg) < 1: continue
        end_if = find_block_end(toks, i)
        has_else = (end_if + 1 < len(toks) and toks[end_if+1] == "else{")
        if has_else:
          end_else = find_block_end(toks, end_if+1)
          args = seg[-1:]
          num_args = [args[0]["val"]]
          highlight_a = args[0]["start"]; highlight_b = end_else
          op_idx = i; chosen = t; break
        else:
          args = seg[-1:]
          num_args = [args[0]["val"]]
          highlight_a = args[0]["start"]; highlight_b = end_if
          op_idx = i; chosen = t; break
      f_map = {f["name"]: f for f in functions}
      if t in f_map:
        k = f_map[t]["params"]
        if len(seg) >= k:
          args = seg[-k:]
          num_args = [a["val"] for a in args]
          highlight_a = args[0]["start"]; highlight_b = i
          op_idx = i; chosen = t; break
        else:
          continue
      k = 1 if t in UN_OPS else (2 if t in BIN_OPS else (3 if t=="clamp" else 0))
      if k and len(seg) >= k:
        args = seg[-k:]
        num_args = [a["val"] for a in args]
        highlight_a = args[0]["start"]; highlight_b = i
        op_idx = i; chosen = t; break

    if highlight_a == -1: break

    style_mid = "M" if marker else "Y"
    print(f"Schritt {step}: {highlight_range(toks, highlight_a, highlight_b, style_mid)}")

    if chosen == "if{":
      end_if = find_block_end(toks, op_idx)
      has_else = (end_if + 1 < len(toks) and toks[end_if+1] == "else{")
      if has_else:
        end_else = find_block_end(toks, end_if+1)
      cond = num_args[0]
      take_if = (cond != 0)
      if_body = toks[op_idx+1:end_if]
      else_body = toks[end_if+2:end_else] if has_else else []
      sub = evaluate_rpn(" ".join(if_body if take_if else else_body), vars_state=vars_state[:], params={}, simvars=json.loads(json.dumps(simvars)), functions=functions, results_history=[])
      out_vals = [fmt_num(v) for v in sub["stack"]]
      which = "IF" if take_if else ("ELSE" if has_else else "NONE")
      vis_if = "..." if not take_if else " ".join(if_body)
      vis_else = "..." if take_if else (" ".join(else_body) if has_else else None)
      preview = f"{args[0]['text']} if{{ {vis_if} }}"
      if has_else: preview += f" else{{ {vis_else} }}"
      preview += f" → Zweig: {which} → {' '.join(out_vals) if out_vals else ''}"
      print(ANSI["yellow"] + preview + ANSI["reset"])
      new_toks = toks[:highlight_a] + out_vals + toks[highlight_b+1:]
      toks = new_toks
      if endstep:
        if out_vals:
          idx = highlight_a + max(len(out_vals)-1,0)
          style = "M" if marker else "Y"
          print(f"Schritt {step} Ende: {highlight_single(toks, idx, style)}")
        else:
          print(f"Schritt {step} Ende: {' '.join(toks)}")
    else:
      f_map = {f["name"]: f for f in functions}
      if chosen in f_map:
        f = f_map[chosen]
        sub_toks = []
        for tok in tokenize(f["rpn"]):
          m = re.fullmatch(r"p(\d+)", tok)
          if m:
            pi = int(m.group(1))
            sub_toks.append(fmt_num(num_args[pi-1] if 1<=pi<=len(num_args) else 0))
          else:
            sub_toks.append(tok)
        sub = evaluate_rpn(" ".join(sub_toks), vars_state=vars_state[:], params={}, simvars=json.loads(json.dumps(simvars)), functions=functions, results_history=[])
        res = sub["stack"][-1] if sub["stack"] else 0.0
        left_txt = " ".join([a["text"] for a in args])
        print(ANSI["yellow"] + f"{left_txt} {chosen} = {fmt_num(res)}" + ANSI["reset"])
        new_toks = toks[:highlight_a] + [fmt_num(res)] + toks[op_idx+1:]
        toks = new_toks
        if endstep:
          style = "M" if marker else "Y"
          print(f"Schritt {step} Ende: {highlight_single(toks, highlight_a, style)}")
      else:
        tmp_src = " ".join([fmt_num(v) for v in num_args] + [chosen])
        sub = evaluate_rpn(tmp_src, vars_state=vars_state[:], params={}, simvars=json.loads(json.dumps(simvars)), functions=functions, results_history=[])
        res = sub["stack"][-1] if sub["stack"] else 0.0
        if infix and len(num_args)==2:
          print(ANSI["yellow"] + f"{args[0]['text']} {chosen} {args[1]['text']} = {fmt_num(res)}" + ANSI["reset"])
        elif infix and len(num_args)==1:
          print(ANSI["yellow"] + f"{chosen} {args[0]['text']} = {fmt_num(res)}" + ANSI["reset"])
        else:
          left_txt = " ".join([a["text"] for a in args])
          print(ANSI["yellow"] + f"{left_txt} {chosen} = {fmt_num(res)}" + ANSI["reset"])
        new_toks = toks[:highlight_a] + [fmt_num(res)] + toks[op_idx+1:]
        toks = new_toks
        if endstep:
          style = "M" if marker else "Y"
          print(f"Schritt {step} Ende: {highlight_single(toks, highlight_a, style)}")

    step += 1
    if len(toks) == 1: break
  print(" ".join(toks))

# ----------- CLI / REPL -----------
def clear_screen():
  os.system("cls" if os.name == "nt" else "clear")

def print_usage():
  print(f"""Usage:
  python rpn_calc.py "<expr>" [options]
  python rpn_calc.py  # startet REPL

Options:
  --step, -s         Step mode
  --endstep          Zeigt nach jedem Schritt den neuen Postfix und markiert das Ergebnis
  --infix, -i        Zeigt Schrittberechnung als Infix (z.B. "9 - 5 = 4")
  --precompile, -p   Funktionsnamen vorab durch deren Körper (ohne pN) ersetzen
  --nocolor, -c/-n   Farben aus
  --mark, -m         Markieren mit gelbem Hintergrund
  --noprompt         Unterdrückt Param-Prompt-Labels (Eingabe bleibt erforderlich)
  --ctx JSON         Inline-Kontext (params, simvars)
  --print            Persistente Variablen ausgeben (ohne <expr>)
  --reset            Persistente Variablen zurücksetzen (ohne <expr>)
  --help, -?         Hilfe

Persistenz-Dateien:
  State:  {STATE_PATH}
  SimVars:{SIM_PATH}
  Funcs:  {FUNC_PATH}
  Result: {STACK_PATH}
""")

# REPL globals (session toggles)
step_mode = False
precompile_mode = False
no_color = False
marker = False
endstep_mode = False
infix_mode = False
input_mode = False
input_prompt = False
input_buffer = []
# REPL prompts for params with labels by default; can be toggled silent with :noprompt
repl_param_silent = False
last_postfix = ""

# readline
_readline = None
def setup_readline():
  global _readline
  try:
    import readline as _readline  # *nix
  except Exception:
    try:
      import pyreadline3 as _readline  # Windows
    except Exception:
      _readline = None
  if _readline:
    try:
      _readline.read_history_file(str(HIST_PATH))
    except Exception:
      pass
    def completer(text, state):
      buffer = _readline.get_line_buffer()
      commands = [":e",":fe",":s",":l",":r",":rl",":f",":?",
                  ":step",":p",":color",":mark",":end",":infix",
                  ":si",":sp",":spi",":sip",":i",":ip",":noprompt",":q",":="]
      ops = ["+","-","*","/","%","^","and","or","not","&&","||","!",
             ">","<",">=","<=","==","=","!=","<>",
             "round","floor","ceil","abs","sin","cos","tan","log","exp",
             "min","max","clamp","pow2","pow","sqrt2","sqrt","dnor",
             "if{","else{","}"]
      regs = []
      for i in range(10): regs += [f"s{i}",f"l{i}",f"sp{i}",f"lp{i}"]
      regs += [f"p{i}" for i in range(1,10)] + [f"r{i}" for i in range(1,9)]
      funcs = [f["name"] for f in load_funcs()]
      sim = load_json(SIM_PATH, {"simvars": {}}).get("simvars", {})
      sv = set()
      prefixes = {k for k,v in sim.items() if isinstance(v, dict)}
      prefixes.add("A")
      for pref in prefixes:
        sv.add(f"({pref}:"); sv.add(f"(>{pref}:")
        for key in sim.get(pref, {}):
          sv.add(f"({pref}:{key})"); sv.add(f"(>{pref}:{key})")
      for k,v in sim.items():
        if not isinstance(v, dict):
          sv.add(f"(A:{k})"); sv.add(f"(>A:{k})")
      pool = set(ops) | set(regs) | set(funcs) | sv
      if buffer.strip().startswith(":"):
        cand = [c for c in commands if c.startswith(buffer.strip())]
      else:
        parts = buffer.split()
        prefix = parts[-1] if parts else ""
        cand = [c for c in pool if c.startswith(prefix)]
      cand = sorted(set(cand))
      if state < len(cand): return cand[state]
      return None
    try:
      if hasattr(_readline, "set_completer_delims"):
        delims = _readline.get_completer_delims()
        for ch in [":","(",")",">",","]:
          delims = delims.replace(ch, "")
        _readline.set_completer_delims(delims)
      if hasattr(_readline, "parse_and_bind"):
        _readline.parse_and_bind("tab: complete")
      _readline.set_completer(completer)
    except Exception:
      pass
    atexit.register(save_history_truncated)

def save_history_truncated():
  if not _readline: return
  try:
    n = _readline.get_current_history_length()
    start = max(1, n - HIST_MAX + 1)
    lines = []
    for i in range(start, n+1):
      it = _readline.get_history_item(i)
      if it is not None: lines.append(it)
    HIST_PATH.write_text("\n".join(lines) + ("\n" if lines else ""), encoding="utf-8")
  except Exception:
    pass

def print_help():
  clear_screen()
  print("RPN-REPL Befehle:")
  print("  :e        - ~/.simvars.json bearbeiten")
  print("  :fe       - ~/.rpnfunc.json bearbeiten")
  print("  :s        - SimVars anzeigen")
  print("  :l        - Persistente Variablen anzeigen")
  print("  :r        - Persistente Variablen zurücksetzen")
  print("  :rl       - Result-Stacks (r1..r8) anzeigen")
  print("  :f        - Funktionen auflisten")
  print("  :?        - Letzten Postfix anzeigen")
  print("  := <INFIX>- (kein Parser hier) wird direkt evaluiert wie eingegeben")
  print("  :step     - Step-Modus umschalten")
  print("  :p        - Precompile umschalten")
  print("  :color    - No-Color umschalten")
  print("  :mark     - Marker umschalten")
  print("  :end      - Endstep umschalten (impliziert Step)")
  print("  :infix    - Infix-Ausgabe im Step-Modus umschalten")
  print("  :si       - Step+Infix EIN (wenn AUS) / Step AUS (wenn AN)")
  print("  :sp       - Step+Precompile EIN (wenn AUS) / Step AUS (wenn AN)")
  print("  :spi/:sip - Step+Precompile+Infix EIN (wenn AUS) / Step AUS (wenn AN)")
  print("  :i        - Eingabe-Modus (tokenweise) umschalten")
  print("  :ip       - Im Eingabe-Modus Postfix-Puffer über jeder Eingabe anzeigen umschalten")
  print("  :noprompt - Parametereingabe ohne Labels (nur REPL) umschalten")
  print("  :q        - Beenden")
  print("")
  print("Eingaben ohne ':' werden als Postfix direkt ausgewertet. Leere Eingabe zeigt diese Hilfe.")

def call_calc(expr=None, admin=None):
  global step_mode, precompile_mode, no_color, marker, endstep_mode, infix_mode, repl_param_silent
  if admin == "--reset":
    save_state_vars([0]*10)
    print("Variablen s0..s9 zurückgesetzt.")
    print("State-Datei:", STATE_PATH)
    return 0
  if admin == "--print":
    print("Persistente Variablen (s0..s9):", load_state_vars())
    print("State-Datei:", STATE_PATH)
    return 0

  vars_state = load_state_vars()
  simvars = load_simvars()
  functions = load_funcs()
  results = load_results()

  params = {}

  try:
    eval_expr = expr or ""
    missing = collect_missing_params(tokenize(eval_expr), params)
    if missing:
      params.update(prompt_params(missing, silent=repl_param_silent))

    if precompile_mode:
      eval_expr = " ".join(precompile_tokens(tokenize(eval_expr), functions))

    result = evaluate_rpn(eval_expr, vars_state=vars_state, params=params, simvars=simvars, functions=functions, results_history=results)

    save_state_vars(result["vars"])
    if result["sim_dirty"]:
      save_simvars(result["simvars"])

    if not is_pure_r_token_expression(eval_expr):
      new_hist = [list(result["stack"])] + results
      save_results(new_hist[:8])

    if step_mode or endstep_mode:
      if no_color: apply_no_color()
      step_verbose(result["original_tokens"], vars_state=result["vars"], regs=result["regs"],
                   simvars=result["simvars"], functions=result["functions"],
                   no_color=no_color, marker=marker, endstep=endstep_mode, infix=infix_mode)
    else:
      print(" ".join(fmt_num(v) for v in result["stack"]))
    return 0
  except Exception as e:
    print("Error:", e)
    return 1

def repl():
  global step_mode, precompile_mode, no_color, marker, endstep_mode, infix_mode
  global input_mode, input_prompt, input_buffer, last_postfix, repl_param_silent

  print_help()
  while True:
    try:
      prompt = "rpn> " if not input_mode else "rpn✓> "
      line = input(prompt)
    except (EOFError, KeyboardInterrupt):
      print("")
      break
    if line is None: line = ""
    line = line.rstrip("\n")
    if input_mode:
      if line.strip()=="" or line.strip()=="=":
        if input_buffer:
          expr = " ".join(input_buffer); last_postfix = expr
          call_calc(expr)
          input_buffer = []
        else:
          print_help()
        continue
      input_buffer += line.strip().split()
      if input_prompt:
        print(" ".join(input_buffer))
      continue

    if not line.strip():
      print_help(); continue

    if line.startswith(":"):
      cmd = line.strip()
      if cmd == ":q": break
      elif cmd == ":e": subprocess.run([os.environ.get("EDITOR","vim"), str(SIM_PATH)])
      elif cmd == ":fe": subprocess.run([os.environ.get("EDITOR","vim"), str(FUNC_PATH)])
      elif cmd == ":s": print(json.dumps({"simvars": load_simvars()}, indent=2, ensure_ascii=False))
      elif cmd == ":l": call_calc(admin="--print")
      elif cmd == ":r": call_calc(admin="--reset")
      elif cmd == ":rl": print(json.dumps(load_json(STACK_PATH, {"results":[]}), indent=2, ensure_ascii=False))
      elif cmd == ":f": 
        arr = load_funcs()
        if not arr: print("(keine Funktionen)")
        for f in arr: print(f"- {f['name']}({f['params']}): {f['rpn']}")
      elif cmd == ":?": print(last_postfix or "(kein letzter Postfix)")
      elif cmd.startswith(":="):
        expr = cmd[2:].strip(); 
        if not expr: print("Verwendung: := <INFIX-AUSDRUCK>")
        else: last_postfix = expr; call_calc(expr)
      elif cmd == ":step": step_mode = not step_mode; print(f"Step-Modus: {'AN' if step_mode else 'AUS'}")
      elif cmd == ":p": precompile_mode = not precompile_mode; print(f"Precompile: {'AN' if precompile_mode else 'AUS'}")
      elif cmd == ":color": no_color = not no_color; print(f"No-Color: {'AN' if no_color else 'AUS'}")
      elif cmd == ":mark": marker = not marker; print(f"Marker: {'AN' if marker else 'AUS'}")
      elif cmd == ":end": endstep_mode = not endstep_mode; 
      elif cmd == ":infix": infix_mode = not infix_mode; print(f"Infix: {'AN' if infix_mode else 'AUS'}")
      elif cmd == ":si":
        if not step_mode: step_mode=True; infix_mode=True; print("Step: AN, Infix: AN")
        else: step_mode=False; print("Step: AUS")
      elif cmd == ":sp":
        if not step_mode: step_mode=True; precompile_mode=True; print("Step: AN, Precompile: AN")
        else: step_mode=False; print("Step: AUS")
      elif cmd in (":spi",":sip"):
        if not step_mode: step_mode=True; precompile_mode=True; infix_mode=True; print("Step: AN, Precompile: AN, Infix: AN")
        else: step_mode=False; print("Step: AUS")
      elif cmd == ":i": input_mode = not input_mode; input_buffer=[]; print(f"Eingabe-Modus (tokenweise): {'AN' if input_mode else 'AUS'}")
      elif cmd == ":ip": input_prompt = not input_prompt; print(f"Input-Prompt-Anzeige: {'AN' if input_prompt else 'AUS'}")
      elif cmd == ":noprompt": repl_param_silent = not repl_param_silent; print(f"REPL Param-Prompts ohne Label: {'AN' if repl_param_silent else 'AUS'}")
      else:
        print_help()
      continue

    last_postfix = line.strip()
    call_calc(last_postfix)

def main():
  args = sys.argv[1:]
  if not args:
    setup_readline()
    atexit.register(save_history_truncated)
    repl()
    return

  do_help = ("--help" in args) or ("-?" in args)
  do_step = ("--step" in args) or ("-s" in args)
  do_pre = ("--precompile" in args) or ("-p" in args)
  no_prompt = ("--noprompt" in args)
  no_col = ("--nocolor" in args) or ("-c" in args) or ("-n" in args)
  mark = ("--mark" in args) or ("-m" in args)
  endstep = ("--endstep" in args)
  infix = ("--infix" in args) or ("-i" in args)

  if "--reset" in args:
    save_state_vars([0]*10)
    print("Variablen s0..s9 zurückgesetzt.")
    print("State-Datei:", STATE_PATH)
    return

  if "--print" in args:
    print("Persistente Variablen (s0..s9):", load_state_vars())
    print("State-Datei:", STATE_PATH)
    return

  has_expr = len(args)>0 and not args[0].startswith("-")
  expr = args[0] if has_expr else ""

  if do_help or not has_expr:
    print_usage()
    if not has_expr: return

  inline_ctx = {}
  if "--ctx" in args:
    i = args.index("--ctx")
    if i+1 < len(args):
      try:
        inline_ctx = json.loads(args[i+1])
      except Exception as e:
        print("Error: --ctx ist kein gültiges JSON:", e)
        return

  vars_state = load_state_vars()
  simvars = load_simvars()
  functions = load_funcs()
  results = load_results()

  params = inline_ctx.get("params", {})
  ctx_sim = inline_ctx.get("simvars", {})
  merged_sim = json.loads(json.dumps(simvars))
  for pref, data in ctx_sim.items():
    if isinstance(data, dict):
      merged_sim.setdefault(pref, {}).update(data)

  try:
    ev_expr = expr
    # prompt for missing pN first (labels unless --noprompt given)
    missing_cli = collect_missing_params(tokenize(ev_expr), params)
    if missing_cli:
      params.update(prompt_params(missing_cli, silent=no_prompt))
    if do_pre:
      ev_expr = " ".join(precompile_tokens(tokenize(ev_expr), functions))
    result = evaluate_rpn(ev_expr, vars_state=vars_state, params=params, simvars=merged_sim, functions=functions, results_history=results)

    save_state_vars(result["vars"])
    if result["sim_dirty"]:
      save_simvars(result["simvars"])

    if not is_pure_r_token_expression(expr):
      save_results([list(result["stack"])] + results)

    if do_step or endstep:
      if no_col: apply_no_color()
      step_verbose(result["original_tokens"], vars_state=result["vars"], regs=result["regs"],
                   simvars=result["simvars"], functions=result["functions"],
                   no_color=no_col, marker=mark, endstep=endstep, infix=infix)
    else:
      print(" ".join(fmt_num(v) for v in result["stack"]))
  except Exception as e:
    print("Error:", e)

if __name__ == "__main__":
  main()
