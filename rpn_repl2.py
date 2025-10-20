#!/usr/bin/env python3
# RPN-REPL with :step toggle to pass --step to rpn.js

import os, sys, json, subprocess, shlex, readline

HOME = os.path.expanduser("~")
RPN_JS = os.environ.get("RPN_JS", "rpn.js")
SIMVARS_PATH = os.path.expanduser("~/.simvars.json")
FUNCS_PATH   = os.path.expanduser("~/.rpnfunc.json")
STATE_PATH   = os.path.expanduser("~/.rpn_state.json")
STACK_PATH   = os.path.expanduser("~/.rpnstack.json")

step_mode = False           # toggled via :step
last_expr = ""

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
    os.system(f'${{EDITOR:-vim}} "{path}"')

def run_rpn(expr, pass_ctx=True):
    global last_expr
    last_expr = expr.strip()

    # Build command
    cmd = ["node", RPN_JS, expr, "--noprompt"]
    if step_mode:
        cmd.append("--step")

    # Pass simvars via --ctx (so rpn.js has the data without reading file)
    if pass_ctx:
        ctx = {"simvars": load_json(SIMVARS_PATH, {}).get("simvars", {})}
        cmd += ["--ctx", json.dumps(ctx)]

    # Inherit stdio so p1/p2 inputs can be typed directly (no prompt labels due to --noprompt)
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

def print_help():
    print("RPN-REPL Befehle:")
    print("  :e        - ~/.simvars.json mit $EDITOR (vim) bearbeiten")
    print("  :fe       - ~/.rpnfunc.json mit $EDITOR (vim) bearbeiten")
    print("  :s        - SimVars anzeigen")
    print("  :l        - Persistente Variablen anzeigen (ruft rpn.js --print)")
    print("  :r        - Persistente Variablen resetten (ruft rpn.js --reset)")
    print("  :rl       - Result-Stacks (r1..r8) anzeigen")
    print("  :step     - Step-Modus umschalten (wirkt als --step für rpn.js)")
    print("  (leer)    - diese Hilfe erneut anzeigen")
    print("Beliebige Eingabe ohne ':' wird als RPN an rpn.js weitergereicht (mit --noprompt und ggf. --step).")

def main():
    # initial help
    print_help()
    while True:
        try:
            line = input("rpn> ").strip()
        except (EOFError, KeyboardInterrupt):
            print()
            break

        if not line:
            print_help()
            continue

        if line.startswith(":"):
            cmd = line.strip()
            if cmd == ":e":
                open_in_vim(SIMVARS_PATH)
            elif cmd == ":fe":
                open_in_vim(FUNCS_PATH)
            elif cmd == ":s":
                print(json.dumps(load_json(SIMVARS_PATH, {}), indent=2, ensure_ascii=False))
            elif cmd == ":l":
                # show persistent vars via rpn.js --print
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
            elif cmd == ":step":
                global step_mode
                step_mode = not step_mode
                print(f"Step-Modus ist jetzt {'AN' if step_mode else 'AUS'}.")
            elif cmd in (":q", ":quit", ":exit"):
                break
            else:
                print("Unbekannter Befehl.")
            continue

        # otherwise: evaluate as RPN
        run_rpn(line, pass_ctx=True)

if __name__ == "__main__":
    main()
