#!/usr/bin/env python3
# RPN-REPL mit :p (Precompile umschalten) und :step (Step-Modus umschalten)
# - Leere Eingabe: Bildschirm leeren + Hilfe anzeigen
# - :step toggelt Step-Modus (übergibt --step an rpn.js)
# - :p toggelt Precompile-Modus (übergibt --precompile an rpn.js)
# - :? zeigt letzten POSTFIX als INFIX
# - := X konvertiert INFIX → POSTFIX via infix-rpn-eval (Node), zeigt & führt aus
# - :f listet Funktionen aus ~/.rpnfunc.json
# - :fe öffnet ~/.rpnfunc.json im Editor
# - :e / :s / :l / :r / :rl wie gehabt

import os, sys, json, subprocess, readline
from pathlib import Path

HOME = os.path.expanduser("~")
RPN_JS = os.environ.get("RPN_JS", "rpn.js")
SIMVARS_PATH = os.path.expanduser("~/.simvars.json")
FUNCS_PATH   = os.path.expanduser("~/.rpnfunc.json")
STATE_PATH   = os.path.expanduser("~/.rpn_state.json")
STACK_PATH   = os.path.expanduser("~/.rpnstack.json")

step_mode = False
precompile_mode = False
last_postfix = ""   # zuletzt ausgeführter Postfix

def clear_screen():
    if sys.stdout.isatty():
        print("\033[2J\033[H", end="")
    else:
        os.system("clear" if os.name != "nt" else "cls")

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

def open_in_vim(path):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    if not os.path.exists(path):
        if path == SIMVARS_PATH:
            save_json(path, {"simvars": {}})
        elif path == FUNCS_PATH:
            save_json(path, [])
        else:
            Path(path).write_text("", encoding="utf-8")
    os.system(f'${{EDITOR:-vim}} "{path}"')

def run_rpn(expr, pass_ctx=True):
    global last_postfix
    last_postfix = expr.strip()

    cmd = ["node", RPN_JS, expr, "--noprompt"]
    if step_mode:
        cmd.append("--step")
    if precompile_mode:
        cmd.append("--precompile")

    if pass_ctx:
        ctx = {"simvars": load_json(SIMVARS_PATH, {}).get("simvars", {})}
        cmd += ["--ctx", json.dumps(ctx)]

    try:
        proc = subprocess.Popen(cmd)
        proc.wait()
    except FileNotFoundError:
        print("node oder rpn.js nicht gefunden. Stelle sicher, dass Node.js installiert ist und rpn.js im Pfad liegt.")

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

# --- POSTFIX → INFIX (für :?) ---
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

# --- INFIX → POSTFIX via Node 'infix-rpn-eval' ---
def infix_to_postfix(infix_expr: str) -> str:
    js = "const m=require('infix-rpn-eval');" \
         "try{console.log(m.toPostfix(" + json.dumps(infix_expr) + "));}" \
         "catch(e){console.error('ERR:'+e.message);process.exit(2);}"
    try:
        out = subprocess.check_output(["node", "-e", js], stderr=subprocess.STDOUT, text=True)
        return out.strip()
    except subprocess.CalledProcessError as e:
        print("Fehler bei INFIX→POSTFIX:", e.output.strip())
        return ""

def print_help():
    print("Verfügbare Befehle:")
    print("  :e     – öffnet ~/.simvars.json im Editor")
    print("  :s     – zeigt SimVars aus der Datei an")
    print("  :l     – zeigt gespeicherte RPN-Variablen (s0..s9)")
    print("  :r     – setzt RPN-Variablen zurück")
    print("  :f     – listet Custom-Funktionen (Name, Parameter, RPN)")
    print("  :fe    – öffnet die Funktionsdatei im Editor (Standard: ~/.rpnfunc.json)")
    print("  :rl    – listet die gespeicherten Result-Stacks (r1 … r8)")
    print("  :?     – zeigt den letzten RPN-Ausdruck (Postfix) als Infix-Ausdruck")
    print("  := X   – wandelt den INFIX-Ausdruck X in Postfix um, zeigt ihn an und führt ihn aus")
    print("  :step  – Step-Modus umschalten (wirkt als --step für rpn.js)")
    print("  :p     – Precompile-Modus umschalten (wirkt als --precompile für rpn.js)")
    print("  :q     – beendet die REPL")
    print("")
    print("Weitere Eingaben:")
    print("  <POSTFIX> – führt den Postfix-Ausdruck direkt über rpn.js aus")
    print("  (leer)    – löscht den Bildschirm und zeigt diese Hilfe")
    print("")
    print(f"SimVars-Datei:     {SIMVARS_PATH}")
    print(f"Funktionen-Datei:  {FUNCS_PATH}")
    print(f"Result-Stack-Datei:{STACK_PATH}")

def start_banner():
    clear_screen()
    print_help()

def main():
    start_banner()
    global step_mode, precompile_mode, last_postfix

    while True:
        try:
            line = input("rpn> ").strip()
        except (EOFError, KeyboardInterrupt):
            print()
            break

        if not line:
            start_banner()
            continue

        if line.startswith(":"):
            parts = line.split(maxsplit=1)
            cmd = parts[0]
            arg = parts[1] if len(parts) > 1 else ""

            if cmd == ":e":
                open_in_vim(SIMVARS_PATH)

            elif cmd == ":fe":
                open_in_vim(FUNCS_PATH)

            elif cmd == ":s":
                print(json.dumps(load_json(SIMVARS_PATH, {}), indent=2, ensure_ascii=False))

            elif cmd == ":l":
                try:
                    subprocess.run(["node", RPN_JS, "--print"], check=False)
                except FileNotFoundError:
                    print("node oder rpn.js nicht gefunden.")

            elif cmd == ":r":
                try:
                    subprocess.run(["node", RPN_JS, "--reset"], check=False)
                except FileNotFoundError:
                    print("node oder rpn.js nicht gefunden.")

            elif cmd == ":rl":
                list_results()

            elif cmd == ":f":
                list_functions()

            elif cmd == ":?":
                if not last_postfix:
                    print("(kein zuletzt ausgeführter Postfix-Ausdruck)")
                else:
                    try:
                        infix = postfix_to_infix(last_postfix)
                        print(infix)
                    except Exception as e:
                        print("Fehler bei POSTFIX→INFIX:", e)

            elif cmd == ":=":
                if not arg:
                    print("Verwendung: := <INFIX-AUSDRUCK>")
                else:
                    pf = infix_to_postfix(arg)
                    if pf:
                        print(f"Als Postfix: {pf}")
                        run_rpn(pf, pass_ctx=True)

            elif cmd == ":step":
                step_mode = not step_mode
                print(f"Step-Modus ist jetzt {'AN' if step_mode else 'AUS'}.")

            elif cmd == ":p":
                precompile_mode = not precompile_mode
                print(f"Precompile-Modus ist jetzt {'AN' if precompile_mode else 'AUS'}.")

            elif cmd in (":q", ":quit", ":exit"):
                break

            else:
                print("Unbekannter Befehl.")
            continue

        # sonst: direkter Postfix-Ausdruck
        run_rpn(line, pass_ctx=True)

if __name__ == "__main__":
    main()
