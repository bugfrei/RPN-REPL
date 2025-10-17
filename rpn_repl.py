#!/usr/bin/env python3
import subprocess, json, os, readline, shlex, platform

HOME = os.path.expanduser("~")
RPN_PATH = "rpn.js"                           # Pfad zu deinem Node-RPN
SIMVARS_FILE = os.path.join(HOME, ".simvars.json")
FUNC_FILE_JSON = os.path.join(HOME, ".rpnfunc.json")
FUNC_FILE_JS   = os.path.join(HOME, ".rpnfunc.js")
STACK_FILE     = os.path.join(HOME, ".rpnstack.json")

def resolve_func_path():
    # bevorzugt .json, fällt auf .js zurück, sonst .json als Standardpfad
    if os.path.exists(FUNC_FILE_JSON):
        return FUNC_FILE_JSON
    if os.path.exists(FUNC_FILE_JS):
        return FUNC_FILE_JS
    return FUNC_FILE_JSON

FUNC_FILE = resolve_func_path()

# ---------------- Clear Screen ----------------
def clear_screen():
    if platform.system() == "Windows":
        os.system("cls")
    else:
        os.system("clear")

# ---------------- Helper: SimVars I/O ----------------
def load_simvars():
    if os.path.exists(SIMVARS_FILE):
        try:
            with open(SIMVARS_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception as e:
            print(f"[WARN] Fehler beim Laden von {SIMVARS_FILE}: {e}")
    return {"simvars": {}}

def edit_simvars():
    editor = os.environ.get("EDITOR", "vim")
    # Datei anlegen, falls nicht vorhanden
    if not os.path.exists(SIMVARS_FILE):
        try:
            with open(SIMVARS_FILE, "w", encoding="utf-8") as f:
                f.write('{"simvars":{}}\n')
        except Exception as e:
            print(f"[ERROR] Konnte {SIMVARS_FILE} nicht anlegen: {e}")
            return
    subprocess.run([editor, SIMVARS_FILE])

def print_simvars():
    ctx = load_simvars()
    simvars = ctx.get("simvars", {})
    if not simvars:
        print("(keine SimVars vorhanden)")
        return
    for k, v in simvars.items():
        print(f"{k} = {v}")

# ---------------- Helper: Functions I/O ----------------
def load_functions():
    if not os.path.exists(FUNC_FILE):
        return []
    try:
        with open(FUNC_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception as e:
        print(f"[WARN] Fehler beim Laden der Funktionen aus {FUNC_FILE}: {e}")
        return []

def list_functions():
    funcs = load_functions()
    if not funcs:
        print(f"(keine Funktionen gefunden – Datei: {FUNC_FILE})")
        return
    print(f"Funktionen aus: {FUNC_FILE}")
    print("-" * 60)
    for f in funcs:
        name   = f.get("name", "<unnamed>")
        params = f.get("params", 0)
        rpn    = f.get("rpn", "")
        print(f"Name   : {name}")
        print(f"Params : {params}")
        print(f"RPN    : {rpn}")
        print("-" * 60)

def edit_functions():
    editor = os.environ.get("EDITOR", "vim")
    if not os.path.exists(FUNC_FILE):
        try:
            with open(FUNC_FILE, "w", encoding="utf-8") as f:
                f.write("[]\n")
        except Exception as e:
            print(f"[ERROR] Konnte {FUNC_FILE} nicht anlegen: {e}")
            return
    subprocess.run([editor, FUNC_FILE])

# ---------------- Helper: Result-Stacks I/O ----------------
def load_results():
    if not os.path.exists(STACK_FILE):
        return []
    try:
        with open(STACK_FILE, "r", encoding="utf-8") as f:
            obj = json.load(f)
        res = obj.get("results", [])
        if isinstance(res, list):
            # nur Listen aus Zahlen akzeptieren
            out = []
            for item in res:
                if isinstance(item, list):
                    clean = []
                    for v in item:
                        try:
                            n = float(v)
                            clean.append(n)
                        except Exception:
                            pass
                    out.append(clean)
            return out
    except Exception as e:
        print(f"[WARN] Fehler beim Laden von {STACK_FILE}: {e}")
    return []

def list_results():
    results = load_results()
    if not results:
        print(f"(keine gespeicherten Ergebnisse – Datei: {STACK_FILE})")
        return
    print(f"Gespeicherte Result-Stacks (neueste zuerst) aus: {STACK_FILE}")
    print("-" * 60)
    for i, stack in enumerate(results, start=1):
        print(f"r{i}: " + " ".join(format_number(x) for x in stack))
    print("-" * 60)

def format_number(x):
    # schöne Ausgabe ohne unnötige Nachkommastellen
    if float(x).is_integer():
        return str(int(x))
    return str(x)

# ---------------- Helper: rpn.js Aufrufe ----------------
def run_rpn(postfix_expr, extra_args=None):
    """Führt einen Postfix-Ausdruck über rpn.js aus; nutzt immer --ctx ~/.simvars.json und ggf. --func."""
    ctx = load_simvars()
    ctx_json = json.dumps(ctx)
    cmd = ["node", RPN_PATH, postfix_expr, "--ctx", ctx_json]
    if os.path.exists(FUNC_FILE):
        cmd += ["--func", FUNC_FILE]
    if extra_args:
        cmd += list(extra_args)
    try:
        result = subprocess.run(cmd, capture_output=True, text=True)
        if result.returncode == 0:
            out = result.stdout.strip()
            if out:
                print(out)
        else:
            err = result.stderr.strip()
            if err:
                print("[ERROR]", err)
    except FileNotFoundError:
        print("[ERROR] node oder rpn.js nicht gefunden")

def rpn_print_vars():
    subprocess.run(["node", RPN_PATH, "--print"])

def rpn_reset_vars():
    subprocess.run(["node", RPN_PATH, "--reset"])

# ---------------- Infix <-> Postfix Utilities ----------------
def to_postfix_with_node(infix_expr):
    js = (
        "const {toPostfix}=require('infix-rpn-eval');"
        "try{"
        "  const input=process.argv[1]||'';"
        "  const out=toPostfix(input);"
        "  console.log(out);"
        "}catch(e){"
        "  console.error('toPostfix error:', e.message);"
        "  process.exit(1);"
        "}"
    )
    try:
        result = subprocess.run(["node", "-e", js, infix_expr], capture_output=True, text=True)
    except FileNotFoundError:
        print("[ERROR] Node oder Modul 'infix-rpn-eval' nicht verfügbar.")
        return None
    if result.returncode != 0:
        err = result.stderr.strip()
        if err:
            print("[ERROR]", err)
        return None
    return result.stdout.strip()

def rpn_to_infix(postfix_expr):
    tokens = postfix_expr.split()
    BIN_OPS = {"+","-","*","/","%","^",">","<",">=","<=","==","!=","and","or"}
    UNARY_FUNCS = {"round","floor","ceil","abs","sqrt","sin","cos","tan","log","exp"}
    UNARY_WORDS = {"not"}
    stack = []
    for t in tokens:
        if t in BIN_OPS:
            if len(stack) < 2: return "(Fehler: zu wenige Operanden)"
            b = stack.pop(); a = stack.pop()
            stack.append(f"({a} {t} {b})")
        elif t in UNARY_FUNCS:
            if not stack: return f"(Fehler: kein Operand für {t})"
            a = stack.pop()
            stack.append(f"{t}({a})")
        elif t in UNARY_WORDS:
            if not stack: return "(Fehler: kein Operand für not)"
            a = stack.pop()
            stack.append(f"(not {a})")
        else:
            stack.append(t)
    return stack[0] if len(stack) == 1 else " ".join(stack)

# ---------------- Hilfe ----------------
def print_help():
    print("""
Verfügbare Befehle:
  :e     – öffnet ~/.simvars.json im Editor
  :s     – zeigt SimVars aus der Datei an
  :l     – zeigt gespeicherte RPN-Variablen (s0..s9)
  :r     – setzt RPN-Variablen zurück
  :f     – listet Custom-Funktionen (Name, Parameter, RPN)
  :fe    – öffnet die Funktionsdatei im Editor (Standard: ~/.rpnfunc.json)
  :rl    – listet die gespeicherten Result-Stacks (r1 … r8)
  :?     – zeigt den letzten RPN-Ausdruck (Postfix) als Infix-Ausdruck
  := X   – wandelt den INFIX-Ausdruck X in Postfix um, zeigt ihn an und führt ihn aus
  :q     – beendet die REPL

Weitere Eingaben:
  <POSTFIX> – führt den Postfix-Ausdruck direkt über rpn.js aus
  (leer)    – löscht den Bildschirm und zeigt diese Hilfe
""".strip())

# ---------------- REPL ----------------
def repl():
    clear_screen()  # Bildschirm sofort leeren beim Start

    print("RPN REPL gestartet – einfach RPN (Postfix) oder := <Infix> eingeben")
    print_help()
    print(f"\nSimVars-Datei:     {SIMVARS_FILE}")
    print(f"Funktionen-Datei:  {FUNC_FILE}")
    print(f"Result-Stack-Datei:{STACK_FILE}\n")

    last_postfix = None

    while True:
        try:
            line = input("rpn> ").strip()
        except (EOFError, KeyboardInterrupt):
            print()
            break

        # leere Eingabe → Clear + Hilfe
        if not line:
            clear_screen()
            print_help()
            continue

        # Commands
        if line in (":q", "quit", "exit"):
            break
        if line == ":e":
            edit_simvars(); continue
        if line == ":s":
            print_simvars(); continue
        if line == ":l":
            rpn_print_vars(); continue
        if line == ":r":
            rpn_reset_vars(); continue
        if line == ":f":
            list_functions(); continue
        if line == ":fe":
            edit_functions(); continue
        if line == ":rl":
            list_results(); continue
        if line == ":?":
            if not last_postfix:
                print("(kein letzter RPN/Postfix-Ausdruck vorhanden)")
            else:
                infix = rpn_to_infix(last_postfix)
                print(infix)
            continue

        # := <INFIX>  => mit toPostfix umwandeln, Postfix anzeigen, ausführen
        if line.startswith(":="):
            infix_expr = line[2:].strip()
            if not infix_expr:
                print("Verwendung: := <INFIX-AUSDRUCK>")
                continue
            postfix = to_postfix_with_node(infix_expr)
            if postfix is None:
                continue
            print(f"Als Postfix: {postfix}")
            last_postfix = postfix
            run_rpn(postfix)
            continue

        # ansonsten: POSTFIX ausführen
        last_postfix = line
        run_rpn(line)

if __name__ == "__main__":
    repl()
