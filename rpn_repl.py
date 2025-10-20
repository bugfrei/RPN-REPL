#!/usr/bin/env python3
# RPN-REPL with :p (precompile), :step (step mode), :color (toggle no-color),
# :mark (toggle marker style), :end (toggle endstep). Passes flags to rpn.js.
#
# Commands:
#   (empty) – clear + help
#   :e     – edit ~/.simvars.json
#   :fe    – edit ~/.rpnfunc.json
#   :s     – show simvars
#   :l     – print persistent vars via rpn.js --print
#   :r     – reset persistent vars via rpn.js --reset
#   :rl    – list result stacks
#   :f     – list functions
#   :?     – show last postfix as infix (best-effort converter)
#   := X   – infix -> postfix via infix-rpn-eval (Node) and run
#   :step  – toggle step mode (adds --step)
#   :p     – toggle precompile (adds --precompile)
#   :color – toggle no-color (adds --nocolor)
#   :mark  – toggle marker style (adds --mark)
#   :end   – toggle endstep (adds --endstep and implies --step)
#   :q     – quit
#
# Any other input is treated as a postfix expression and forwarded to rpn.js
# with --noprompt (so REPL doesn't show labels for p1, p2, ...) plus the
# active flags above.
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
endstep_mode = False  # implies step when true
last_postfix = ""

def clear_screen():
    # ANSI clear to avoid relying on external 'clear'
    sys.stdout.write("\033[2J\033[H")
    sys.stdout.flush()

def load_json(path, default):
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return default

def save_json(path, obj):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(obj, f, indent=2, ensure_ascii=False)

def open_in_editor(path):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    if not os.path.exists(path):
        if path == SIMVARS_PATH:
            save_json(path, {"simvars": {}})
        elif path == FUNCS_PATH:
            save_json(path, [])
        else:
            with open(path, "w", encoding="utf-8") as f:
                f.write("")
    editor = os.environ.get("EDITOR", "vim")
    os.system(f'"{editor}" "{path}"')

def run_rpn(expr, pass_ctx=True):
    global last_postfix
    last_postfix = expr.strip()
    cmd = ["node", RPN_JS, expr, "--noprompt"]
    # options from toggles
    if endstep_mode or step_mode:
        cmd.append("--step")
    if precompile_mode:
        cmd.append("--precompile")
    if nocolor_mode:
        cmd.append("--nocolor")
    if mark_mode:
        cmd.append("--mark")
    if endstep_mode:
        cmd.append("--endstep")
    if pass_ctx:
        ctx = {"simvars": load_json(SIMVARS_PATH, {}).get("simvars", {})}
        cmd += ["--ctx", json.dumps(ctx)]
    try:
        subprocess.run(cmd, check=False)
    except FileNotFoundError:
        print("Fehler: Node oder rpn.js nicht gefunden. Bitte sicherstellen, dass Node installiert ist und rpn.js im Pfad liegt.")

def list_results():
    data = load_json(STACK_PATH, {"results": []})
    results = data.get("results", [])
    if not results:
        print("(keine gespeicherten Result-Stacks)")
        return
    for idx, stack in enumerate(results, start=1):
        print(f"r{idx}: {' '.join(map(str, stack))}")

def list_functions():
    funcs = load_json(FUNCS_PATH, [])
    if not funcs:
        print("(keine Funktionen definiert)")
        return
    for f in funcs:
        name = f.get("name", "<unnamed>")
        params = f.get("params", "?")
        rpn = f.get("rpn", "")
        print(f"- {name}  (params: {params})")
        print(f"    {rpn}")

# Basic postfix->infix (best-effort) for :?
BIN_OPS = {"+","-","*","/","%","^",">","<",">=","<=","==","!=","and","or","min","max"}
UN_OPS = {"not","round","floor","ceil","abs","sqrt","sin","cos","tan","log","exp","dnor"}
TERN_OPS = {"clamp"}

def tokenize(src: str):
    out = []
    i = 0
    while i < len(src):
        ch = src[i]
        if ch.isspace():
            i += 1; continue
        if ch == '(':
            depth = 1; j = i + 1
            while j < len(src) and depth > 0:
                if src[j] == '(':
                    depth += 1
                elif src[j] == ')':
                    depth -= 1
                j += 1
            out.append(src[i:j]); i = j; continue
        j = i
        while j < len(src) and (not src[j].isspace()):
            if src[j] in "()":
                break
            j += 1
        out.append(src[i:j]); i = j
    return [t for t in out if t]

def postfix_to_infix(expr):
    toks = tokenize(expr)
    stack = []
    for t in toks:
        if t in BIN_OPS:
            if len(stack) < 2: raise ValueError("Zu wenige Operanden für " + t)
            b = stack.pop(); a = stack.pop()
            stack.append(f"({a} {t} {b})")
        elif t in UN_OPS:
            if len(stack) < 1: raise ValueError("Zu wenige Operanden für " + t)
            a = stack.pop()
            stack.append(f"{t}({a})") if t != "not" else stack.append(f"(not {a})")
        elif t in TERN_OPS:
            if len(stack) < 3: raise ValueError("Zu wenige Operanden für clamp")
            c = stack.pop(); b = stack.pop(); a = stack.pop()
            stack.append(f"clamp({a}, {b}, {c})")
        else:
            stack.append(t)
    return stack[0] if len(stack)==1 else " ".join(stack)

def infix_to_postfix(infix_expr: str) -> str:
    js = "const m=require('infix-rpn-eval');" \
         "try{console.log(m.toPostfix(" + json.dumps(infix_expr) + "));}" \
         "catch(e){console.error('ERR:'+e.message);process.exit(2);}"
    out = subprocess.check_output(["node", "-e", js], stderr=subprocess.STDOUT, text=True)
    return out.strip()

def print_help():
    print("RPN-REPL Befehle:")
    print("  :e        - ~/.simvars.json mit $EDITOR (vim) bearbeiten")
    print("  :fe       - ~/.rpnfunc.json mit $EDITOR (vim) bearbeiten")
    print("  :s        - SimVars anzeigen")
    print("  :l        - Persistente Variablen anzeigen (ruft rpn.js --print)")
    print("  :r        - Persistente Variablen resetten (ruft rpn.js --reset)")
    print("  :rl       - Result-Stacks (r1..r8) anzeigen")
    print("  :f        - Custom-Funktionen (Name, Parameter, RPN) anzeigen")
    print("  :?        - letzten RPN-Ausdruck (Postfix) als Infix anzeigen")
    print("  := X      - INFIX X -> Postfix konvertieren und ausführen")
    print("  :step     - Step-Modus umschalten (wirkt als --step für rpn.js)")
    print("  :p        - Precompile umschalten (wirkt als --precompile)")
    print("  :color    - No-Color umschalten (wirkt als --nocolor)")
    print("  :mark     - Marker-Stil umschalten (wirkt als --mark)")
    print("  :end      - Endstep umschalten (wirkt als --endstep & --step)")
    print("  :q        - REPL beenden")
    print("")
    print("Beliebige Eingabe ohne ':' wird als RPN an rpn.js weitergereicht (mit --noprompt und aktiven Flags).")
    print("")
    print(f"SimVars-Datei:     {SIMVARS_PATH}")
    print(f"Funktionen-Datei:  {FUNCS_PATH}")
    print(f"Result-Stack-Datei:{STACK_PATH}")

def banner():
    clear_screen()
    print_help()

def main():
    banner()
    global step_mode, precompile_mode, nocolor_mode, mark_mode, endstep_mode, last_postfix
    while True:
        try:
            line = input("rpn> ").strip()
        except (EOFError, KeyboardInterrupt):
            print()
            break
        if not line:
            banner()
            continue
        if line.startswith(":"):
            parts = line.split(maxsplit=1)
            cmd = parts[0]
            arg = parts[1] if len(parts) > 1 else ""

            if cmd == ":e":
                open_in_editor(SIMVARS_PATH)
            elif cmd == ":fe":
                open_in_editor(FUNCS_PATH)
            elif cmd == ":s":
                print(json.dumps(load_json(SIMVARS_PATH, {}), indent=2, ensure_ascii=False))
            elif cmd == ":l":
                try: subprocess.run(["node", RPN_JS, "--print"], check=False)
                except FileNotFoundError: print("node oder rpn.js nicht gefunden.")
            elif cmd == ":r":
                try: subprocess.run(["node", RPN_JS, "--reset"], check=False)
                except FileNotFoundError: print("node oder rpn.js nicht gefunden.")
            elif cmd == ":rl":
                # local listing
                data = load_json(STACK_PATH, {"results": []})
                results = data.get("results", [])
                if not results: print("(keine gespeicherten Result-Stacks)")
                else:
                    for idx, stack in enumerate(results, start=1):
                        print(f"r{idx}: {' '.join(map(str, stack))}")
            elif cmd == ":f":
                list_functions()
            elif cmd == ":?":
                if not last_postfix: print("(kein zuletzt ausgeführter Postfix)")
                else:
                    try: print(postfix_to_infix(last_postfix))
                    except Exception as e: print("Fehler bei POSTFIX→INFIX:", e)
            elif cmd == ":=":
                if not arg: print("Verwendung: := <INFIX-AUSDRUCK>")
                else:
                    try:
                        pf = infix_to_postfix(arg)
                        print(f"Als Postfix: {pf}")
                        run_rpn(pf, pass_ctx=True)
                    except subprocess.CalledProcessError as e:
                        print("Fehler bei INFIX→POSTFIX:", e.output.strip())
            elif cmd == ":step":
                step_mode = not step_mode
                print(f"Step-Modus ist jetzt {'AN' if (step_mode or endstep_mode) else 'AUS'}.")
            elif cmd == ":p":
                precompile_mode = not precompile_mode
                print(f"Precompile-Modus ist jetzt {'AN' if precompile_mode else 'AUS'}.")
            elif cmd == ":color":
                nocolor_mode = not nocolor_mode
                print(f"No-Color ist jetzt {'AN' if nocolor_mode else 'AUS'}.")
            elif cmd == ":mark":
                mark_mode = not mark_mode
                print(f"Marker-Stil ist jetzt {'AN' if mark_mode else 'AUS'}.")
            elif cmd == ":end":
                endstep_mode = not endstep_mode
                print(f"Endstep ist jetzt {'AN' if endstep_mode else 'AUS'} (impliziert Step={'AN' if endstep_mode else ('AN' if step_mode else 'AUS')}).")
            elif cmd in (":q", ":quit", ":exit"):
                break
            else:
                print("Unbekannter Befehl.")
            continue

        # otherwise treat as postfix
        run_rpn(line, pass_ctx=True)

if __name__ == "__main__":
    main()
