#!/usr/bin/env python3
# RPN-REPL with Input Mode (:i) and Input Prompt (:ip), plus existing toggles.
import os, sys, json, subprocess, readline

HOME = os.path.expanduser("~")
RPN_JS = os.environ.get("RPN_JS", "rpn.js")
SIMVARS_PATH = os.path.expanduser("~/.simvars.json")
FUNCS_PATH   = os.path.expanduser("~/.rpnfunc.json")
STACK_PATH   = os.path.expanduser("~/.rpnstack.json")

step_mode = False
precompile_mode = False
nocolor_mode = False
mark_mode = False
endstep_mode = False
input_mode = False
input_prompt = False
last_postfix = ""
input_buffer = []

def clear_screen():
    sys.stdout.write("\033[2J\033[H"); sys.stdout.flush()

def load_json(path, default):
    try:
        with open(path, "r", encoding="utf-8") as f: return json.load(f)
    except Exception: return default

def save_json(path, obj):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f: json.dump(obj, f, indent=2, ensure_ascii=False)

def open_in_editor(path):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    if not os.path.exists(path):
        if path == SIMVARS_PATH: save_json(path, {"simvars": {}})
        elif path == FUNCS_PATH: save_json(path, [])
        else:
            with open(path, "w", encoding="utf-8") as f: f.write("")
    editor = os.environ.get("EDITOR", "vim")
    os.system(f'"{editor}" "{path}"')

def tokenize(s: str): return [t for t in s.strip().split() if t]

def run_rpn(expr, pass_ctx=True):
    global last_postfix; last_postfix = expr.strip()
    if last_postfix:
        try: readline.add_history(last_postfix)
        except Exception: pass
    cmd = ["node", RPN_JS, expr, "--noprompt"]
    if endstep_mode or step_mode: cmd.append("--step")
    if precompile_mode: cmd.append("--precompile")
    if nocolor_mode: cmd.append("--nocolor")
    if mark_mode: cmd.append("--mark")
    if endstep_mode: cmd.append("--endstep")
    if pass_ctx:
        ctx = {"simvars": load_json(SIMVARS_PATH, {}).get("simvars", {})}
        cmd += ["--ctx", json.dumps(ctx)]
    try: subprocess.run(cmd, check=False)
    except FileNotFoundError: print("Fehler: Node oder rpn.js nicht gefunden.")

def list_results():
    data = load_json(STACK_PATH, {"results": []}); results = data.get("results", [])
    if not results: print("(keine gespeicherten Result-Stacks)"); return
    for idx, stack in enumerate(results, start=1): print(f"r{idx}: {' '.join(map(str, stack))}")

def list_functions():
    funcs = load_json(FUNCS_PATH, [])
    if not funcs: print("(keine Funktionen definiert)"); return
    for f in funcs:
        print(f"- {f.get('name','<unnamed>')}  (params: {f.get('params','?')})")
        print(f"    {f.get('rpn','')}")

BIN_OPS = {"+","-","*","/","%","^",">","<",">=","<=","==","!=","and","or","min","max"}
UN_OPS = {"not","round","floor","ceil","abs","sqrt","sin","cos","tan","log","exp","dnor"}
TERN_OPS = {"clamp"}

def _tokenize_paren(src: str):
    out=[]; i=0
    while i<len(src):
        ch=src[i]
        if ch.isspace(): i+=1; continue
        if ch=='(':
            depth=1; j=i+1
            while j<len(src) and depth>0:
                if src[j]=='(' : depth+=1
                elif src[j]==')': depth-=1
                j+=1
            out.append(src[i:j]); i=j; continue
        j=i
        while j<len(src) and (not src[j].isspace()):
            if src[j] in "()": break
            j+=1
        out.append(src[i:j]); i=j
    return [t for t in out if t]

def postfix_to_infix(expr):
    toks=_tokenize_paren(expr); stack=[]
    for t in toks:
        if t in BIN_OPS:
            if len(stack)<2: raise ValueError("Zu wenige Operanden für "+t)
            b=stack.pop(); a=stack.pop(); stack.append(f"({a} {t} {b})")
        elif t in UN_OPS:
            if len(stack)<1: raise ValueError("Zu wenige Operanden für "+t)
            a=stack.pop(); stack.append(f"{t}({a})") if t!="not" else stack.append(f"(not {a})")
        elif t in TERN_OPS:
            if len(stack)<3: raise ValueError("Zu wenige Operanden für clamp")
            c=stack.pop(); b=stack.pop(); a=stack.pop(); stack.append(f"clamp({a}, {b}, {c})")
        else: stack.append(t)
    return stack[0] if len(stack)==1 else " ".join(stack)

def infix_to_postfix(infix_expr: str) -> str:
    js="const m=require('infix-rpn-eval');try{console.log(m.toPostfix("+json.dumps(infix_expr)+"));}catch(e){console.error('ERR:'+e.message);process.exit(2);}"
    out=subprocess.check_output(["node","-e",js],stderr=subprocess.STDOUT,text=True)
    return out.strip()

def print_help():
    print("RPN-REPL Befehle:")
    print("  :e        - ~/.simvars.json mit $EDITOR (vim) bearbeiten")
    print("  :fe       - ~/.rpnfunc.json mit $EDITOR (vim) bearbeiten")
    print("  :s        - SimVars anzeigen")
    print("  :l        - Persistente Variablen anzeigen (rpn.js --print)")
    print("  :r        - Persistente Variablen resetten (rpn.js --reset)")
    print("  :rl       - Result-Stacks (r1..r8) anzeigen")
    print("  :f        - Custom-Funktionen (Name, Parameter, RPN) anzeigen")
    print("  :?        - letzten Postfix-Ausdruck (Postfix) als Infix anzeigen")
    print("  := X      - INFIX X -> Postfix konvertieren und ausführen")
    print("  :step     - Step-Modus umschalten (wirkt als --step)")
    print("  :p        - Precompile umschalten (wirkt als --precompile)")
    print("  :color    - No-Color umschalten (wirkt als --nocolor)")
    print("  :mark     - Marker-Stil umschalten (wirkt als --mark)")
    print("  :end      - Endstep umschalten (wirkt als --endstep & --step)")
    print("  :i        - Input-Modus (Token-pro-Zeile) umschalten")
    print("  :ip       - Input-Prompt: zeigt aktuellen Buffer im Input-Modus an")
    print("  :q        - REPL beenden")
    print("")
    print("Beliebige Eingabe ohne ':' wird als RPN an rpn.js weitergereicht (mit --noprompt und aktiven Flags).")
    print("Im Input-Modus: '=' oder leere Zeile führt den aufgebauten Postfix aus.")
    print("")
    print(f"SimVars-Datei:     {SIMVARS_PATH}")
    print(f"Funktionen-Datei:  {FUNCS_PATH}")
    print(f"Result-Stack-Datei:{STACK_PATH}")

def banner():
    clear_screen(); print_help()

def prompt_label():
    flags = []
    flags.append('i' if input_mode else 'l')
    flags.append('S' if (step_mode or endstep_mode) else 's')
    flags.append('P' if precompile_mode else 'p')
    flags.append('C' if nocolor_mode else 'c')
    flags.append('M' if mark_mode else 'm')
    flags.append('E' if endstep_mode else 'e')
    return f"rpn[{''.join(flags)}]> "

def execute_buffer():
    global input_buffer
    if not input_buffer:
        print("(leer)"); return
    expr = " ".join(input_buffer)
    print(expr)
    run_rpn(expr, pass_ctx=True)
    try: readline.add_history(expr)
    except Exception: pass
    input_buffer = []

def handle_command(line: str):
    global step_mode, precompile_mode, nocolor_mode, mark_mode, endstep_mode, input_mode, input_prompt, last_postfix, input_buffer
    parts = line.split(maxsplit=1)
    cmd = parts[0]; arg = parts[1] if len(parts)>1 else ""

    if cmd == ":e": open_in_editor(SIMVARS_PATH)
    elif cmd == ":fe": open_in_editor(FUNCS_PATH)
    elif cmd == ":s": print(json.dumps(load_json(SIMVARS_PATH, {}), indent=2, ensure_ascii=False))
    elif cmd == ":l":
        try: subprocess.run(["node", RPN_JS, "--print"], check=False)
        except FileNotFoundError: print("node oder rpn.js nicht gefunden.")
    elif cmd == ":r":
        try: subprocess.run(["node", RPN_JS, "--reset"], check=False)
        except FileNotFoundError: print("node oder rpn.js nicht gefunden.")
    elif cmd == ":rl":
        data = load_json(STACK_PATH, {"results": []}); results = data.get("results", [])
        if not results: print("(keine gespeicherten Result-Stacks)")
        else:
            for idx, stack in enumerate(results, start=1): print(f"r{idx}: {' '.join(map(str, stack))}")
    elif cmd == ":f": list_functions()
    elif cmd == ":?":
        if not last_postfix: print("(kein zuletzt ausgeführter Postfix)")
        else:
            try: print(postfix_to_infix(last_postfix))
            except Exception as e: print("Fehler bei POSTFIX→INFIX:", e)
    elif cmd == ":=":
        if not arg: print("Verwendung: := <INFIX-AUSDRUCK>")
        else:
            try:
                pf = infix_to_postfix(arg); print(f"Als Postfix: {pf}"); run_rpn(pf, pass_ctx=True)
            except subprocess.CalledProcessError as e:
                print("Fehler bei INFIX→POSTFIX:", e.output.strip())
    elif cmd == ":step":
        step_mode = not step_mode; print(f"Step-Modus ist jetzt {'AN' if (step_mode or endstep_mode) else 'AUS'}.")
    elif cmd == ":p":
        precompile_mode = not precompile_mode; print(f"Precompile-Modus ist jetzt {'AN' if precompile_mode else 'AUS'}.")
    elif cmd == ":color":
        nocolor_mode = not nocolor_mode; print(f"No-Color ist jetzt {'AN' if nocolor_mode else 'AUS'}.")
    elif cmd == ":mark":
        mark_mode = not mark_mode; print(f"Marker-Stil ist jetzt {'AN' if mark_mode else 'AUS'}.")
    elif cmd == ":end":
        endstep_mode = not endstep_mode; print(f"Endstep ist jetzt {'AN' if endstep_mode else 'AUS'} (impliziert Step={'AN' if endstep_mode else ('AN' if step_mode else 'AUS')}).")
    elif cmd == ":i":
        input_mode = not input_mode; print(f"Input-Modus ist jetzt {'AN' if input_mode else 'AUS'}.")
        if input_mode: input_buffer.clear()
    elif cmd == ":ip":
        input_prompt = not input_prompt; print(f"Input-Prompt ist jetzt {'AN' if input_prompt else 'AUS'}.")
    elif cmd in (":q", ":quit", ":exit"):
        return False
    else:
        print("Unbekannter Befehl.")
    return True

def main():
    banner()
    while True:
        try:
            line = input(prompt_label()).strip()
        except (EOFError, KeyboardInterrupt):
            print(); break

        if not line:
            if input_mode:
                execute_buffer(); continue
            else:
                banner(); continue

        if line.startswith(":"):
            if handle_command(line) is False: break
            continue

        # Non-command
        if input_mode:
            tokens = tokenize(line)
            if not tokens: continue
            segment = []
            for tok in tokens:
                if tok == "=":
                    if segment: input_buffer.extend(segment); segment = []
                    execute_buffer()
                else:
                    segment.append(tok)
            if segment: input_buffer.extend(segment)
            if input_prompt and input_buffer:
                print(" ".join(input_buffer))
        else:
            run_rpn(line, pass_ctx=True)

if __name__ == "__main__":
    main()
