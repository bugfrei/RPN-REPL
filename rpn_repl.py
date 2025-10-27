#!/usr/bin/env python3
# RPN-REPL wrapper for rpn.js
# - Step / Precompile / Infix toggles
# - Input (tokenwise) mode
# - Readline history with arrow keys
# - TAB completion for commands, functions, simvars, operators, registers
# - History limited to 100 lines

import os
import sys
import json
import shlex
import subprocess
from pathlib import Path

# ----- readline / history (arrow keys + completion) -----
_rl = None
try:
    import readline as _rl  # Linux/macOS
except Exception:
    try:
        import pyreadline3 as _rl  # Windows
    except Exception:
        _rl = None

HISTFILE = Path.home() / ".rpn_repl_history"
HIST_MAX = 100

def _load_history():
    if not _rl:
        return
    try:
        _rl.read_history_file(str(HISTFILE))
    except FileNotFoundError:
        pass
    except Exception:
        pass

def _save_history_truncated():
    if not _rl:
        return
    try:
        # extract last HIST_MAX entries
        n = _rl.get_current_history_length()
        start = max(1, n - HIST_MAX + 1)
        lines = []
        for i in range(start, n + 1):
            item = _rl.get_history_item(i)
            if item is not None:
                lines.append(item)
        # write manually
        with open(HISTFILE, "w", encoding="utf-8") as f:
            for line in lines:
                f.write(line + "\n")
    except Exception:
        # fallback: don't crash on history save
        pass

HOME = Path.home()
RPN_JS = os.environ.get("RPN_JS", "rpn.js")
STATE_PATH = os.environ.get("RPN_STATE", str(HOME / ".rpn_state.json"))
SIM_PATH   = os.environ.get("RPN_SIMVARS", str(HOME / ".simvars.json"))
FUNC_PATH  = os.environ.get("RPN_FUNCS", str(HOME / ".rpnfunc.json"))
STACK_PATH = os.environ.get("RPN_STACK", str(HOME / ".rpnstack.json"))

EDITOR = os.environ.get("EDITOR", "vim")

# session toggles
step_mode = False
precompile_mode = False
no_color = False
marker = False
endstep_mode = False
infix_mode = False

# input mode (token-per-line) and prompt of built postfix
input_mode = False
input_prompt = False
input_buffer = []

last_postfix = ""

# ----- helpers -----
def clear_screen():
    os.system('cls' if os.name == 'nt' else 'clear')

def read_json(path, default):
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return default

def list_simvars():
    data = read_json(SIM_PATH, {"simvars": {}})
    print(json.dumps(data, indent=2, ensure_ascii=False))

def list_functions():
    arr = read_json(FUNC_PATH, [])
    if not arr:
        print("(keine Funktionen definiert)")
        return
    for f in arr:
        name = f.get("name")
        params = f.get("params")
        rpn = f.get("rpn")
        print(f"- {name}({params}): {rpn}")

def list_results():
    data = read_json(STACK_PATH, {"results": []})
    results = data.get("results", [])
    if not results:
        print("(keine gespeicherten Result-Stacks)")
        return
    for i, st in enumerate(results, start=1):
        print(f"r{i}: {st}")

def print_help():
    clear_screen()
    print("RPN-REPL Befehle:")
    print("  :e        - ~/.simvars.json mit $EDITOR bearbeiten")
    print("  :fe       - ~/.rpnfunc.json mit $EDITOR bearbeiten")
    print("  :s        - SimVars anzeigen (aus Datei)")
    print("  :l        - Persistente Variablen anzeigen (ruft rpn.js --print)")
    print("  :r        - Persistente Variablen resetten (ruft rpn.js --reset)")
    print("  :rl       - Result-Stacks (r1..r8) anzeigen")
    print("  :f        - Funktionen auflisten (Name, Parameter, RPN)")
    print("  :?        - Letzten Postfix-Ausdruck anzeigen")
    print("  := <INFIX>- Infix-Ausdruck auswerten (an rpn.js weiterreichen)")
    print("  :step     - Step-Modus umschalten (wirkt als --step für rpn.js)")
    print("  :p        - Precompile-Modus umschalten (wirkt als --precompile für rpn.js)")
    print("  :color    - Farbmodus umschalten (No-Color an/aus -> --nocolor)")
    print("  :mark     - Marker-Stil umschalten (--mark)")
    print("  :end      - Endstep-Modus umschalten (impliziert Step)")
    print("  :infix    - Infix-Ausgabe im Step-Modus umschalten (--infix)")
    print("  :si       - Toggle: wenn Step AUS -> Step+Infix EIN; sonst Step AUS")
    print("  :sp       - Toggle: wenn Step AUS -> Step+Precompile EIN; sonst Step AUS")
    print("  :spi      - Toggle: wenn Step AUS -> Step+Precompile+Infix EIN; sonst Step AUS")
    print("  :sip      - Alias zu :spi")
    print("  :i        - Eingabe-Modus (tokenweise) umschalten")
    print("  :ip       - Im Eingabe-Modus den bisher aufgebauten Postfix über jeder Eingabe anzeigen umschalten")
    print("  :q        - Beenden")
    print("")
    print("Beliebige Eingabe ohne ':' wird als RPN an rpn.js weitergereicht (mit --noprompt und akt. Flags).")

# ----- completion -----
COMMANDS = [
    ":e", ":fe", ":s", ":l", ":r", ":rl", ":f", ":?",
    ":step", ":p", ":color", ":mark", ":end", ":infix",
    ":si", ":sp", ":spi", ":sip", ":i", ":ip", ":q", ":="
]

OPERATORS = [
    "+","-","*","/","%","^","and","or","not","&&","||","!",
    ">","<",">=","<=","==","=","!=","<>",
    "round","floor","ceil","abs","sin","cos","tan","log","exp",
    "min","max","clamp","pow2","pow","sqrt2","sqrt","dnor",
    "if{","else{","}"
]

def _gen_registers():
    t = []
    for i in range(10):
        t.append(f"s{i}")
        t.append(f"l{i}")
        t.append(f"sp{i}")
        t.append(f"lp{i}")
    for i in range(1,10):
        t.append(f"p{i}")
    for i in range(1,9):
        t.append(f"r{i}")
    return t
REGISTERS = _gen_registers()

def _simvar_suggestions():
    """Create suggestions like (A:   (>A:   (L:  (>L:  and with known keys: (A:KEY) (>A:KEY)"""
    sim = read_json(SIM_PATH, {"simvars": {}}).get("simvars", {})
    out = set()
    # base prefixes
    prefixes = set(k for k,v in sim.items() if isinstance(v, dict))
    if "A" not in prefixes:
        prefixes.add("A")
    for pref in prefixes:
        out.add(f"({pref}:")
        out.add(f"(>{pref}:")
        # keys
        for key in sim.get(pref, {}).keys():
            out.add(f"({pref}:{key})")
            out.add(f"(>{pref}:{key})")
    # legacy A: from top-level scalars
    for k,v in sim.items():
        if not isinstance(v, dict):
            out.add(f"(A:{k})")
            out.add(f"(>A:{k})")
    return sorted(out)

def _func_suggestions():
    arr = read_json(FUNC_PATH, [])
    names = [f.get("name") for f in arr if isinstance(f, dict) and f.get("name")]
    return sorted(set([str(n) for n in names if n]))

def _complete(text, state):
    """Global completer: suggests depending on leading ':' and token content."""
    buffer = _rl.get_line_buffer() if _rl else ""
    begidx = _rl.get_begidx() if hasattr(_rl, "get_begidx") else 0
    endidx = _rl.get_endidx() if hasattr(_rl, "get_endidx") else 0

    # decide namespace
    candidates = []
    if buffer.strip().startswith(":"):
        # commands + := don't split tokens
        candidates = [c for c in COMMANDS if c.startswith(buffer.strip())]
    else:
        # RPN tokens: merge all sources
        pool = set()
        pool.update(OPERATORS)
        pool.update(REGISTERS)
        pool.update(_func_suggestions())
        pool.update(_simvar_suggestions())
        # split on whitespace and take last token
        last = buffer[begidx:endidx] if begidx < endidx else (buffer.split()[-1] if buffer.split() else "")
        prefix = last if last else text
        candidates = [c for c in pool if c.startswith(prefix)]

    candidates = sorted(set(candidates))
    if state < len(candidates):
        return candidates[state]
    return None

def _setup_readline():
    if not _rl:
        return
    try:
        # Make ':' and parentheses part of words so completion works with (A: etc.
        if hasattr(_rl, "set_completer_delims"):
            delims = _rl.get_completer_delims()
            for ch in [":","(",")",">",","]:
                delims = delims.replace(ch, "")
            _rl.set_completer_delims(delims)
        if hasattr(_rl, "parse_and_bind"):
            _rl.parse_and_bind("tab: complete")
        _rl.set_completer(_complete)
    except Exception:
        pass

# ----- Node integration -----
def call_node_rpn(expr=None, admin_flag=None, extra_args=None):
    args = [RPN_JS]
    if expr:
        args.append(expr)
    if admin_flag:
        args.append(admin_flag)

    if step_mode or endstep_mode:
        args.append("--step")
    if endstep_mode:
        args.append("--endstep")
    if precompile_mode:
        args.append("--precompile")
    if no_color:
        args.append("--nocolor")
    if marker:
        args.append("--mark")
    if infix_mode:
        args.append("--infix")

    args.append("--noprompt")
    args += ["--state", STATE_PATH, "--sim", SIM_PATH, "--func", FUNC_PATH, "--stack", STACK_PATH]

    if extra_args:
        args += extra_args

    cmd = ["node"] + args
    try:
        proc = subprocess.run(cmd, text=True)
        return proc.returncode
    except FileNotFoundError:
        print("Fehler: Node.js nicht gefunden oder rpn.js Pfad falsch. Setze $RPN_JS oder installiere Node.")
        return 1

def edit_file(path):
    try:
        subprocess.run([EDITOR, path])
    except FileNotFoundError:
        print(f"Editor '{EDITOR}' nicht gefunden. Setze $EDITOR oder installiere {EDITOR}.")

# ----- REPL -----
def repl():
    global step_mode, precompile_mode, no_color, marker, endstep_mode, infix_mode
    global input_mode, input_prompt, input_buffer, last_postfix

    print_help()
    while True:
        try:
            prompt = "rpn> " if not input_mode else "rpn✓> "
            line = input(prompt)
            if line is None:
                line = ""
            else:
                line = line.rstrip("\n")
        except (EOFError, KeyboardInterrupt):
            print("")
            break

        if input_mode:
            if line.strip() == "":
                if input_buffer:
                    expr = " ".join(input_buffer)
                    last_postfix = expr
                    call_node_rpn(expr)
                    input_buffer = []
                else:
                    print_help()
                continue
            if line.strip() == "=":
                if input_buffer:
                    expr = " ".join(input_buffer)
                    last_postfix = expr
                    call_node_rpn(expr)
                    input_buffer = []
                continue
            parts = line.strip().split()
            input_buffer.extend(parts)
            if input_prompt:
                print(" ".join(input_buffer))
            continue

        if not line.strip():
            print_help()
            continue

        if line.startswith(":"):
            cmd = line.strip()
            if cmd == ":q":
                break
            elif cmd == ":e":
                edit_file(SIM_PATH)
            elif cmd == ":fe":
                edit_file(FUNC_PATH)
            elif cmd == ":s":
                list_simvars()
            elif cmd == ":l":
                call_node_rpn(admin_flag="--print")
            elif cmd == ":r":
                call_node_rpn(admin_flag="--reset")
            elif cmd == ":rl":
                list_results()
            elif cmd == ":f":
                list_functions()
            elif cmd == ":?":
                if last_postfix:
                    print(last_postfix)
                else:
                    print("(kein letzter Postfix gespeichert)")
            elif cmd.startswith(":="):
                expr = cmd[2:].strip()
                if not expr:
                    print("Verwendung: := <INFIX-AUSDRUCK>")
                else:
                    last_postfix = expr
                    call_node_rpn(expr)
            elif cmd == ":step":
                step_mode = not step_mode
                print(f"Step-Modus: {'AN' if step_mode else 'AUS'}")
            elif cmd == ":p":
                precompile_mode = not precompile_mode
                print(f"Precompile: {'AN' if precompile_mode else 'AUS'}")
            elif cmd == ":color":
                no_color = not no_color
                print(f"No-Color: {'AN' if no_color else 'AUS'}")
            elif cmd == ":mark":
                marker = not marker
                print(f"Marker: {'AN' if marker else 'AUS'}")
            elif cmd == ":end":
                endstep_mode = not endstep_mode
                if endstep_mode and not step_mode:
                    step_mode = True
                print(f"Endstep: {'AN' if endstep_mode else 'AUS'}  | Step: {'AN' if step_mode else 'AUS'}")
            elif cmd == ":infix":
                infix_mode = not infix_mode
                print(f"Infix: {'AN' if infix_mode else 'AUS'}")
            elif cmd == ":si":
                if not step_mode:
                    step_mode = True
                    infix_mode = True
                    print("Step: AN, Infix: AN")
                else:
                    step_mode = False
                    print("Step: AUS")
            elif cmd == ":sp":
                if not step_mode:
                    step_mode = True
                    precompile_mode = True
                    print("Step: AN, Precompile: AN")
                else:
                    step_mode = False
                    print("Step: AUS")
            elif cmd in (":spi", ":sip"):
                if not step_mode:
                    step_mode = True
                    precompile_mode = True
                    infix_mode = True
                    print("Step: AN, Precompile: AN, Infix: AN")
                else:
                    step_mode = False
                    print("Step: AUS")
            elif cmd == ":i":
                input_mode = not input_mode
                input_buffer = []
                print(f"Eingabe-Modus (tokenweise): {'AN' if input_mode else 'AUS'}")
            elif cmd == ":ip":
                input_prompt = not input_prompt
                print(f"Input-Prompt-Anzeige: {'AN' if input_prompt else 'AUS'}")
            else:
                print_help()
            continue

        last_postfix = line.strip()
        call_node_rpn(last_postfix)

if __name__ == "__main__":
    try:
        _load_history()
        _setup_readline()
        repl()
    except Exception as e:
        print(f"Fehler im REPL: {e}")
    finally:
        _save_history_truncated()
