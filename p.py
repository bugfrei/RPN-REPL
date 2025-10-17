#!/usr/bin/env python3
import readline
import subprocess
import os
import sys

# === Konfiguration ===
TARGET = os.path.join(os.path.dirname(__file__), "rpn.js")  # dein Node.js-Script
NODE = "node"  # Pfad zu node, falls nötig anpassen
HISTORY_FILE = os.path.expanduser("~/.repl_node_history")

# === History laden (persistente ↑/↓ Navigation) ===
if os.path.exists(HISTORY_FILE):
    readline.read_history_file(HISTORY_FILE)

readline.set_history_length(1000)
last = ""

print("Python REPL-Runner für Node.js – Strg+C oder Strg+D zum Beenden.")

while True:
    try:
        prompt = f"> " 
        line = input(prompt).strip()

        if not line:
            line = last
        if not line:
            continue  # falls leer am Anfang

        last = line
        readline.add_history(line)

        # Node.js-Skript mit dem Parameter ausführen
        subprocess.run([NODE, TARGET, line])

    except (EOFError, KeyboardInterrupt):
        print("\nBeende REPL.")
        break
    except Exception as e:
        print("Fehler:", e)

# === History speichern ===
try:
    readline.write_history_file(HISTORY_FILE)
except Exception:
    pass

