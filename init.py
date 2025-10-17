#!/usr/bin/env python3
# init.py — richtet RPN-CALC (Node) + RPN-REPL (Python) ein,
# erstellt Default-Dateien (mit Rückfrage) und führt Tests aus.

import json, os, subprocess, sys, shutil
from pathlib import Path

HOME = Path.home()
PROJECT = Path.cwd()

# Konfig-Dateien
SIMVARS_FILE   = HOME / ".simvars.json"
FUNCS_FILE     = HOME / ".rpnfunc.json"
STATE_FILE     = HOME / ".rpn_state.json"
STACK_FILE     = HOME / ".rpnstack.json"

RPN_JS         = PROJECT / "rpn.js"
RPN_REPL_PY    = PROJECT / "rpn_repl.py"
PKG_JSON       = PROJECT / "package.json"

# --- CLI Optionen ---
AUTO_YES = "--yes" in sys.argv or "-y" in sys.argv


def run(cmd, **popen_kwargs):
    """führt Kommando aus und liefert (rc, stdout, stderr)"""
    try:
        proc = subprocess.run(cmd, text=True, capture_output=True, **popen_kwargs)
        return proc.returncode, proc.stdout, proc.stderr
    except FileNotFoundError as e:
        return 127, "", str(e)


def ask_overwrite(path: Path) -> bool:
    """Fragt, ob eine Datei überschrieben werden soll"""
    if AUTO_YES:
        return True
    while True:
        ans = input(f"[?] {path} existiert bereits – überschreiben? [j/N] ").strip().lower()
        if ans in ("j", "y", "yes"):
            return True
        if ans in ("n", "no", "", None):
            print(f"[=] Datei beibehalten: {path}")
            return False


def ensure_node_npm():
    node = shutil.which("node")
    npm = shutil.which("npm")
    errs = []
    if not node:
        errs.append("node nicht gefunden (bitte Node.js installieren)")
    if not npm:
        errs.append("npm nicht gefunden (bitte Node.js / npm installieren)")
    if errs:
        print("[FEHLER] " + " & ".join(errs))
        sys.exit(1)
    print(f"[ok] Node: {node}")
    print(f"[ok] npm : {npm}")


def ensure_npm_deps():
    if not PKG_JSON.exists():
        print("[i] package.json nicht gefunden – führe 'npm init -y' aus...")
        rc, out, err = run(["npm", "init", "-y"])
        if rc != 0:
            print(out); print(err)
            print("[FEHLER] npm init -y fehlgeschlagen")
            sys.exit(1)
        print("[ok] package.json angelegt")

    print("[i] Installiere Abhängigkeiten: infix-rpn-eval ...")
    rc, out, err = run(["npm", "install", "infix-rpn-eval"])
    if rc != 0:
        print(out); print(err)
        print("[FEHLER] npm install fehlgeschlagen")
        sys.exit(1)
    print("[ok] npm dependencies installiert")


def write_file(path: Path, content: str):
    """Schreibt Datei mit Rückfrage"""
    if path.exists():
        if not ask_overwrite(path):
            return
    path.write_text(content, encoding="utf-8")
    print(f"[ok] Datei geschrieben: {path}")


def write_default_files():
    write_file(SIMVARS_FILE, json.dumps({
        "simvars": {
            "A:PLANE HEADING DEGREES, Degrees": 270,
            "A:GENERAL ENG THROTTLE LEVER POSITION:1, Percent": 50
        }
    }, indent=2, ensure_ascii=False) + "\n")

    write_file(FUNCS_FILE, json.dumps([
        {"name": "add90", "params": 1, "rpn": "p1 90 + dnor"},
        {"name": "wrap360", "params": 1, "rpn": "p1 360 % 360 + 360 %"},
        {"name": "angle_diff", "params": 2, "rpn": "p1 p2 - 360 + 360 %"}
    ], indent=2, ensure_ascii=False) + "\n")

    write_file(STATE_FILE, json.dumps({"vars": [0]*10}, indent=2) + "\n")
    write_file(STACK_FILE, json.dumps({"results": []}, indent=2) + "\n")


def check_sources_present():
    missing = []
    if not RPN_JS.exists():
        missing.append(str(RPN_JS))
    if not RPN_REPL_PY.exists():
        print(f"[!] Hinweis: {RPN_REPL_PY} nicht gefunden – REPL kann später ergänzt werden.")
    if missing:
        print("[FEHLER] Benötigte Datei(s) fehlen:")
        for m in missing:
            print("   -", m)
        print("Bitte lege die Datei(en) an (z. B. rpn.js) und starte init.py erneut.")
        sys.exit(1)
    print("[ok] rpn.js gefunden")


def smoke_tests():
    print("\n[¶] Starte Smoke-Tests mit rpn.js ...\n")
    tests = [
        ('"5 3 +"', "8"),
        ('"330 90 + dnor"', "60"),
        ('"1 2 3 +"', "1 5"),
        ('"r,2"', "5"),
    ]
    for expr, expected in tests:
        cmd = ["node", str(RPN_JS), expr]
        rc, out, err = run(cmd)
        out = (out or "").strip()
        ok = (expected in out) or (out == expected)
        status = "ok" if (rc == 0 and ok) else "FAIL"
        print(f"  - {status}: node rpn.js {expr}  -> '{out}'")
        if rc != 0:
            print("    stderr:", err.strip())

    print("\n[¶] Test: Custom-Funktion (add90) ...")
    rc, out, err = run(["node", str(RPN_JS), "330 add90", "--func", str(FUNCS_FILE)])
    print(f"  - {'ok' if (rc==0 and out.strip()=='60') else 'FAIL'}: 330 add90 -> '{out.strip()}'")


def final_message():
    print("\n✅ Setup abgeschlossen.\n")
    print("   • RPN-CALC:    node rpn.js \"5 3 +\"")
    print("   • RPN-REPL:    python3 rpn_repl.py")
    print("\n   Konfig-Dateien:")
    print(f"     - {SIMVARS_FILE}")
    print(f"     - {FUNCS_FILE}")
    print(f"     - {STATE_FILE}")
    print(f"     - {STACK_FILE}")
    print("\n🎉 RPN-CALC und (optional) RPN-REPL sind funktionsbereit. Viel Spaß!")


def main():
    ensure_node_npm()
    check_sources_present()
    ensure_npm_deps()
    write_default_files()
    smoke_tests()
    final_message()


if __name__ == "__main__":
    main()

