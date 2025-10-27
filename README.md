# RPN Calculator & REPL

A powerful Reverse Polish Notation (RPN) calculator with persistent variables, local registers, SimVars, custom functions, step-by-step visualization, conditionals, and a full-featured REPL environment.

---

## 🇩🇪 Deutsch

### Installation

**Windows**

- Repository klonen
- Python 3 muss installiert sein (`choco install python -y` ¹) 
- Node.js >21 muss installiert sein (`choco install nodejs -y` ¹)
> ¹: Chocolatey installieren: https://chocolatey.org/install  
> Installation mit chocolatey auf der PowerShell als **Administrator** geöffnet!

- `readline`-Modul für Python muss installiert sein (`pip install pyreadline3`)
- `infix-rpn-eval`-Modul für Node.js muss installiert sein (`npm i infix-rpn-eval`)

Starten mit `py rpn_repl.py` oder über eine kleine Funktion im PowerShell-Profil `$profile`:

```powershell
function rpn { py <Pfad zur rpn_repl.py Datei> }
```

---

### Übersicht

Dieses Projekt besteht aus zwei Hauptkomponenten:

- **`rpn.js`** – Der eigentliche RPN-Interpreter (Node.js)
- **`rpn_repl.py`** – Ein interaktiver REPL für `rpn.js` (Python)

Mit beiden lassen sich komplexe Postfix-Ausdrücke, Variablen, Funktionen, Bedingungen und Simulationen ausführen und schrittweise nachvollziehen.

---

### Dateien & Speicherorte

| Datei | Zweck | Speicherort |
|-------|--------|--------------|
| `~/.rpn_state.json` | Persistente Variablen `s0..s9` | automatisch angelegt |
| `~/.simvars.json` | SimVars `(A:NAME,Unit)` | automatisch angelegt |
| `~/.rpnfunc.json` | Benutzerdefinierte Funktionen | automatisch angelegt |
| `~/.rpnstack.json` | Ergebnis-Historie (r1..r8) | automatisch angelegt |

---

### Grundprinzip

Der Rechner arbeitet **stackbasiert**:  
Operanden werden auf den Stack gelegt, Operatoren verarbeiten die obersten Werte.

```bash
node rpn.js "1 2 3 + *"
# -> (1 * (2 + 3)) = 5
```

---

### Optionen (`rpn.js`)

| Option | Kurzform | Beschreibung |
|---------|-----------|---------------|
| `--step` | `-s` | Schritt-für-Schritt-Modus |
| `--endstep` | – | Zeigt nach jedem Schritt den neuen Postfix mit markiertem Ergebnis |
| `--mark` | `-m` | Gelber Hintergrund (Textmarker) statt gelber Schrift |
| `--nocolor` | `-c` / `-n` | Deaktiviert alle Farben |
| `--precompile` | `-p` | Ersetzt Funktionsnamen vorab durch deren Körper (ohne Parameter `pN`) |
| `--noprompt` | – | Unterdrückt Eingabeaufforderungen für `p1..pN` |
| `--ctx` | – | Übergibt Parameter & SimVars als JSON |
| `--state` | – | Pfad zu persistenten Variablen |
| `--sim` | – | Pfad zu SimVars |
| `--func` | – | Pfad zu Funktionsdatei |
| `--stack` | – | Pfad zur History-Datei |
| `--help` | `-?` | Hilfe anzeigen |

---

### REPL-Befehle (`rpn_repl.py`)

| Befehl | Beschreibung |
|---------|---------------|
| `:i` | Eingabemodus (Einzeltoken) umschalten |
| `:ip` | Eingabe-Prompt (Postfixanzeige) umschalten |
| `:p` | Precompile-Modus umschalten |
| `:step` | Step-Modus umschalten |
| `:color` | Farbmodus umschalten |
| `:mark` | Marker-Stil umschalten |
| `:end` | Endstep-Modus umschalten (impliziert Step) |
| `:s` | SimVars anzeigen |
| `:e` | SimVars-Datei im Editor öffnen |
| `:fe` | Funktionsdatei im Editor öffnen |
| `:l` | Persistente Variablen anzeigen |
| `:r` | Persistente Variablen zurücksetzen |
| `:rl` | Ergebnis-Stacks anzeigen |
| `:f` | Funktionen auflisten |
| `:?` | Letzten Postfix-Ausdruck als Infix anzeigen |
| `:= <Infix>` | Infix-Ausdruck auswerten |
| `:q` | Beenden |

---

### Persistente Variablen und Register

| Befehl | Wirkung |
|---------|----------|
| `5 s0` | speichert 5 in `s0` (persistent) |
| `l0` | lädt den Wert aus `s0` auf den Stack |
| `5 sp0` | speichert 5 temporär in `sp0` (session-only) |
| `lp0` | lädt den Wert aus `sp0` |

---

### Parameter (Postfix-Kontext, nicht Funktionsparameter!)

Parameter wie `p1`, `p2` können direkt im Postfix gesetzt werden, entweder durch Eingabe oder über `--ctx`:

```bash
node rpn.js "p1 p2 +" --ctx '{"params":{"p1":10,"p2":20}}'
# -> 30
```

> ⚠️ Diese `pN`-Parameter gelten **nur für den Postfix selbst**, nicht für Funktionen (`f.rpn`), da Funktionsparameter intern rekursiv ersetzt werden.

---

### SimVars

SimVars simulieren externe Werte und können wie Variablen verwendet werden:

```bash
(>A:TEMP,C)    # schreibt in SimVar TEMP (Unit C)
(A:TEMP,C)     # liest TEMP
```

Beispiel:
```bash
20 (>A:TEMP,C)
(A:TEMP,C)
# -> 20
```

---

### Bedingungen (`if{ ... } else{ ... }`)

Bedingte Ausdrücke werden mit `if{}` und optional `else{}` geschrieben.
Der Ausdruck vor `if{}` wird als Bedingung ausgewertet:
- Ist der Wert ≠ 0 → **IF-Zweig** wird ausgeführt.
- Ist der Wert = 0 → **ELSE-Zweig** (falls vorhanden).

Syntax:
```bash
<cond> if{ <RPN bei wahr> } [else{ <RPN bei falsch> }]
```

Beispiel:
```bash
1 if{ 11 } else{ 22 }    # → 11
0 if{ 11 } else{ 22 }    # → 22
```

Schrittweise Ausgabe (`--step`):
```
1 if{ 11 } else{ 22 }
Schritt 1: 1 if{ 11 } else{ 22 }
1 if{ 11 } else{ ... } → Zweig: IF → 11
11

0 if{ 11 } else{ 22 }
Schritt 1: 0 if{ 11 } else{ 22 }
0 if{ ... } else{ 22 } → Zweig: ELSE → 22
22
```

Bedingungsblöcke können beliebige RPN-Ausdrücke enthalten, auch **SimVar-Zugriffe oder Funktionsaufrufe**.

---

### Funktionen

Benutzerdefinierte Funktionen stehen in `~/.rpnfunc.json` als Array:

```json
[
  {
    "name": "add90",
    "params": 1,
    "rpn": "p1 90 + dnor"
  }
]
```

Zwei Ausführungsmodi:

1. **Standardmodus (Operator-Logik)**  
   `add90` arbeitet wie ein Operator – es werden automatisch Parameter aus dem Stack geholt und das Ergebnis zurückgeschoben.

   ```bash
   node rpn.js "0 add90 add90 add90"
   # => 270
   ```

2. **Precompile-Modus (`--precompile`)**  
   Ersetzt Funktionsnamen **vor der Ausführung** durch ihren Körper ohne `pN`-Platzhalter.

   ```bash
   node rpn.js "0 add90 add90 add90" --precompile
   # ergibt denselben Endwert, aber rein als expandierter Postfix
   # 0 90 + dnor 90 + dnor 90 + dnor
   ```

---

### Schrittweises Debugging (`--step`, `--endstep`)

```bash
node rpn.js "1 2 3 4 + + +" --endstep
```

Ausgabe:
```
1 2 3 4 + + +
Schritt 1: 1 2 3 4 + + +
3 4 + = 7
Schritt 1 Ende: 1 2 7 + +
Schritt 2: 1 2 7 + +
2 7 + = 9
Schritt 2 Ende: 1 9 +
Schritt 3: 1 9 +
1 9 + = 10
Schritt 3 Ende: 10
10
```

Mit `--mark` werden hervorgehobene Bereiche als **gelber Hintergrund** angezeigt.  
Mit `--nocolor` wird jede Farbmarkierung deaktiviert.

---

### Ergebnisse und History

Die letzten bis zu 8 Ergebnisse werden in `~/.rpnstack.json` gespeichert und können mit `r1..r8` referenziert werden.

Beispiel:

```bash
r1    # ruft letztes Ergebnis auf
r2,1  # ruft den ersten Wert des vorletzten Stacks auf
```

---

### Beispielkonfiguration (`--ctx`)

```json
{
  "params": {
    "p1": 10,
    "p2": 20
  },
  "simvars": {
    "TEMP,C": 42,
    "ALT,ft": 1000
  }
}
```

Ausführung:
```bash
node rpn.js "p1 p2 + (A:TEMP,C) +" --ctx ctx.json
```

---

## 🇬🇧 English

### Overview

This project provides:

- **`rpn.js`** – core RPN calculator (Node.js)
- **`rpn_repl.py`** – interactive REPL wrapper (Python)

You can execute, debug, and visualize RPN expressions step-by-step with persistent variables, functions, SimVars, and conditional logic.

### Example (with conditionals)

```bash
node rpn.js "1 if{ 11 } else{ 22 }" --step
```
Output:
```
1 if{ 11 } else{ 22 }
Step 1: 1 if{ 11 } else{ 22 }
1 if{ 11 } else{ ... } -> Branch: IF -> 11
11
```

```bash
node rpn.js "0 if{ 11 } else{ 22 }" --step
```
Output:
```
0 if{ 11 } else{ 22 }
Step 1: 0 if{ 11 } else{ 22 }
0 if{ ... } else{ 22 } -> Branch: ELSE -> 22
22
```

---

© 2025 Suportis / Custom RPN System
