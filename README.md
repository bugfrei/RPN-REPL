# 🧮 RPN Calculator + REPL

A complete Reverse Polish Notation (RPN) calculator implemented in **Node.js** with a **Python-based REPL** shell.

It supports **persistent variables**, **temporary registers**, **functions**, **SimVars**, **history stacks**, and **step-by-step** or **precompile** evaluation modes.  
All features are accessible both from CLI and REPL.

---

## 🇩🇪 Übersicht (German)

### 🔧 Komponenten
- `rpn.js` – der eigentliche RPN-Interpreter (Node.js)
- `rpn_repl.py` – interaktive Shell (Python REPL)

Beide arbeiten zusammen:
- Der REPL ruft intern `rpn.js` mit passenden Parametern auf.
- Zustand, Variablen und Ergebnisse werden als JSON-Dateien im Home-Verzeichnis gespeichert.

### 📂 Standard-Dateien
| Datei | Zweck | Beispielpfad |
|--------|--------|--------------|
| `~/.rpn_state.json` | persistente Variablen (s0..s9) | `{"vars": [5, 0, 0, ...]}` |
| `~/.simvars.json` | Simulation-Variablen (A:NAME) | `{"simvars": {"ALT,ft": 1000}}` |
| `~/.rpnfunc.json` | Funktionsdefinitionen | `[{"name": "add90", "params": 1, "rpn": "p1 90 +"}]` |
| `~/.rpnstack.json` | Ergebnisse (r1..r8) | `{"results": [[5,10,15], [3,4]]}` |

---

### ▶️ Beispielaufrufe

#### Direkt über CLI
```bash
node rpn.js "5 s0 l0"
# Ausgabe: 5

node rpn.js "5 sp0 lp0"
# Ausgabe: 5
```

#### Mit Funktionen
```json
# ~/.rpnfunc.json
[
  { "name": "add90", "params": 1, "rpn": "p1 90 +" }
]
```

```bash
node rpn.js "0 add90 add90 add90"
# Ergebnis: 270
```

#### Mit Step-Modus
```bash
node rpn.js "0 add90 add90 add90" -s
```

#### Mit Precompile-Modus
```bash
node rpn.js "0 add90 add90 add90" -p
```

#### Mit Parametern via --ctx
```bash
node rpn.js "addmul" --ctx '{"params": {"p1": 10, "p2": 5}}'
# ~/.rpnfunc.json enthält:
# [{"name":"addmul","params":2,"rpn":"p1 p2 + 2 *"}]
# => Ergebnis: 30
```

#### Mit SimVars
```bash
node rpn.js "(A:ALT,ft) 10 + (>A:ALT,ft)" \
  --ctx '{"simvars": {"ALT,ft": 1000}}' --noprompt
# ALT wird zu 1010
```

---

### ⚙️ REPL-Befehle (Python)
Starte:
```bash
python3 rpn_repl.py
```

#### Wichtige Befehle
| Befehl | Beschreibung |
|--------|---------------|
| (leer) | Bildschirm löschen + Hilfe anzeigen |
| `:e` | öffnet `~/.simvars.json` im Editor |
| `:fe` | öffnet `~/.rpnfunc.json` im Editor |
| `:s` | zeigt SimVars an |
| `:l` | zeigt gespeicherte Variablen (s0..s9) |
| `:r` | setzt Variablen zurück |
| `:f` | listet Funktionen auf |
| `:rl` | zeigt gespeicherte Result-Stacks |
| `:?` | zeigt letzten Postfix als Infix |
| `:= X` | konvertiert Infix → Postfix und führt aus |
| `:step` | Step-Modus an/aus |
| `:p` | Precompile-Modus an/aus |
| `:q` | beendet die REPL |

---

### 💾 Speicherbereiche
| Typ | Kürzel | Verhalten |
|------|--------|------------|
| **Persistente Variablen** | `s0..s9` / `l0..l9` | `sN` speichert Stack-Top (POP), `lN` lädt |
| **Temporäre Register** | `sp0..sp9` / `lp0..lp9` | `spN` speichert Stack-Top (ohne POP), `lpN` lädt |
| **SimVars** | `(A:NAME,Unit)` / `(>A:NAME,Unit)` | Werte aus/zu `~/.simvars.json` |
| **Result-History** | `r1..r8` / `rN,k` | lädt vorherige Stack-Ergebnisse |
| **Parameter** | `p1..pN` | Werte via `--ctx` oder Prompt |

---

### 📘 Beispiel: Infix zu Postfix
Im REPL:
```text
:= (3 + 4) * 2
```
Ergebnis:
```text
Als Postfix: 3 4 + 2 *
14
```

---

## 🇬🇧 Overview (English)

### 🔧 Components
- `rpn.js` – main RPN evaluator (Node.js)
- `rpn_repl.py` – interactive REPL shell (Python)

Both work together:
- REPL invokes `rpn.js` with parameters
- State and variables are persisted as JSON files

### 📂 Default Files
| File | Purpose | Example |
|------|----------|----------|
| `~/.rpn_state.json` | persistent vars s0..s9 | `{"vars":[5,0,0,...]}` |
| `~/.simvars.json` | simulation vars (A:...) | `{"simvars":{"ALT,ft":1000}}` |
| `~/.rpnfunc.json` | function definitions | `[{"name":"add90","params":1,"rpn":"p1 90 +"}]` |
| `~/.rpnstack.json` | result stacks r1..r8 | `{"results":[[5,10,15],[3,4]]}` |

### ▶️ Examples

#### Direct CLI
```bash
node rpn.js "5 s0 l0"
# => 5

node rpn.js "5 sp0 lp0"
# => 5
```

#### With functions
```json
# ~/.rpnfunc.json
[
  {"name":"add90","params":1,"rpn":"p1 90 +"}
]
```

```bash
node rpn.js "0 add90 add90 add90"
# => 270
```

#### Step mode
```bash
node rpn.js "0 add90 add90 add90" -s
```

#### Precompile mode
```bash
node rpn.js "0 add90 add90 add90" -p
```

#### Passing parameters via --ctx
```bash
node rpn.js "addmul" --ctx '{"params":{"p1":10,"p2":5}}'
# => 30
```

#### Using SimVars
```bash
node rpn.js "(A:ALT,ft) 10 + (>A:ALT,ft)" \
  --ctx '{"simvars":{"ALT,ft":1000}}' --noprompt
# => sets ALT,ft = 1010
```

### ⚙️ REPL Commands
| Command | Description |
|----------|-------------|
| (empty) | clears screen and shows help |
| `:e` | edit `~/.simvars.json` |
| `:fe` | edit `~/.rpnfunc.json` |
| `:s` | show simvars |
| `:l` | show vars |
| `:r` | reset vars |
| `:f` | list functions |
| `:rl` | list result stacks |
| `:?` | show last postfix as infix |
| `:= X` | convert infix to postfix and evaluate |
| `:step` | toggle step mode |
| `:p` | toggle precompile mode |
| `:q` | quit REPL |

### 💾 Storage Types
| Type | Tokens | Behavior |
|------|---------|-----------|
| Persistent vars | `s0..s9`, `l0..l9` | `sN` stores top (POP), `lN` loads |
| Temp registers | `sp0..sp9`, `lp0..lp9` | `spN` stores top (no pop), `lpN` loads |
| SimVars | `(A:NAME)` / `(>A:NAME)` | read/write from `~/.simvars.json` |
| Result history | `r1..r8`, `rN,k` | recall last result stacks |
| Parameters | `p1..pN` | from `--ctx` or prompt |

---

**Author:** Carsten Suportis  
**Version:** October 2025
