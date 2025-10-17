# 🧮 RPN-CALC & RPN-REPL

## 🇩🇪 Deutsch

Ein umfassender, erweiterbarer **Reverse Polish Notation (RPN)** Rechner mit Integration in Mobiflight/MSFS und einer interaktiven REPL-Umgebung.  
Der RPN-CALC (`rpn.js`) bietet präzise Simulation von RPN-Operationen, Variablen, History, benutzerdefinierten Funktionen, SimVars, Parametern und mehr.

---

## ⚙️ Überblick

### Komponenten

| Komponente | Beschreibung |
|-------------|---------------|
| **RPN-CALC (`rpn.js`)** | Node.js-Anwendung zur Auswertung von RPN-Ausdrücken |
| **RPN-REPL (`rpn_repl.py`)** | Python-basierte interaktive Shell zur komfortablen Nutzung von `rpn.js` |
| **init.py** | Initialisierungsskript: installiert Abhängigkeiten, erstellt Standarddateien, führt Tests aus |

---

## 🧩 Installation

```bash
python3 init.py
```
`init.py` installiert automatisch:
- Node.js-Abhängigkeiten (`npm install infix-rpn-eval`)
- Erstellt Standarddateien im Benutzerverzeichnis:
  - `~/.simvars.json`
  - `~/.rpnfunc.json`
  - `~/.rpn_state.json`
  - `~/.rpnstack.json`
- Führt Funktionstests aus und meldet: **„RPN-CALC und RPN-REPL sind bereit“**

---

## 🧠 RPN-CALC (`rpn.js`)

### Eingabe & Ausgabe
```bash
node rpn.js "5 3 +"
→ Postfix: 5 3 +
→ Ergebnis: 8
```

### Operatoren

| Kategorie | Operator | Beschreibung |
|------------|-----------|--------------|
| Arithmetik | `+`, `-`, `*`, `/`, `%`, `^` | Grundrechenarten, Potenz, Modulo |
| Vergleich | `>`, `<`, `>=`, `<=`, `==`, `!=` | Vergleichsoperationen (1/0) |
| Logik | `and`, `or`, `not` | Logische Operatoren |
| Math | `round`, `floor`, `ceil`, `abs`, `sqrt`, `sin`, `cos`, `tan`, `log`, `exp`, `min`, `max`, `clamp` | Standardmathematik |
| Richtung | `dnor` | **Direction Normalize**: normalisiert auf 0–359° |
| Blöcke | `if{ ... } else{ ... }` | Bedingte Ausführung |

Beispiel:
```
330 90 + dnor → 60
```

---

### Variablen

| Typ | Name | Bereich | Persistenz | Beschreibung |
|------|------|----------|-------------|---------------|
| Temporär | `sp0..sp9` / `lp0..lp9` | Session | Nein | Speicherung/Laden innerhalb eines Ausdrucks |
| Persistent | `s0..s9` / `l0..l9` | Datei | Ja (`~/.rpn_state.json`) | Dauerhafte Speicherung |
| Parameter | `p1..p9` | Ausdruck | Nein | Vom Benutzer eingegebene Werte |
| History | `r`, `r1..r8`, `r1,2` | Datei | Ja (`~/.rpnstack.json`) | Zugriff auf vorherige Ergebnisse |

Beispiel:
```
5 3 + s0    → Speichert 8 in s0
l0 2 *      → Liest 8, ergibt 16
```

---

### Parameter (`p1`, `p2`, …)

```bash
node rpn.js "p1 p2 +"

Wert für p1: 5
Wert für p2: 3
→ Postfix: 5 3 +
→ Ergebnis: 8
```

Mit `--noprompt` erfolgt die Eingabe ohne Texte:
```
node rpn.js "p1 p2 +" --noprompt
5
3
→ 8
```

> Hinweis: In der Python-REPL können Eingabe-Prompts verzögert angezeigt werden.

---

### SimVars (Mobiflight / MSFS)

**Lesen:** `(A:Variable, Type)`  
**Schreiben:** `(>A:Variable, Type)`

Beispiel:
```
(A:GENERAL ENG THROTTLE LEVER POSITION:1, Percent) 0.5 (>A:AXIS_THROTTLE_SET, Number)
```
Alle Werte werden in `~/.simvars.json` gespeichert.

---

### Benutzerdefinierte Funktionen

Datei: `~/.rpnfunc.json`

```json
[
  { "name": "add90", "params": 1, "rpn": "p1 90 + dnor" },
  { "name": "double", "params": 1, "rpn": "p1 2 *" }
]
```

Beispiel:
```bash
node rpn.js "50 add90"
→ 50 90 + dnor
→ 140
```

---

### History-System (`r`)

Datei: `~/.rpnstack.json`  
Speichert bis zu 8 Ergebnisse (je Stack).

| Token | Bedeutung |
|--------|------------|
| `r` / `r1` | Letztes Ergebnis |
| `r2` | Zweitletztes Ergebnis |
| `r1,2` | Zweiter Wert des letzten Ergebnisses |
| `r,3` | Dritter Wert des letzten Ergebnisses |

> Wird nur ein `r`-Token verwendet, überschreibt das Ergebnis nicht die History.

---

### JSON-Dateiformate

| Datei | Zweck | Beispiel |
|--------|--------|-----------|
| `~/.rpn_state.json` | Persistente Variablen | `{ "vars": [0,1,2,3,4,5,6,7,8,9] }` |
| `~/.simvars.json` | Simulationsvariablen | `{ "simvars": { "A:NAV OBS:1, Degrees": 270 } }` |
| `~/.rpnfunc.json` | Benutzerdefinierte Funktionen | `[{"name": "add90","params":1,"rpn":"p1 90 + dnor"}]` |
| `~/.rpnstack.json` | History | `{ "results": [[8],[1,2,3]] }` |

---

## 💻 RPN-REPL (`rpn_repl.py`)

Interaktive Shell mit folgenden Befehlen:

| Befehl | Beschreibung |
|---------|---------------|
| `:e` | Öffnet `~/.simvars.json` in `vim` |
| `:fe` | Öffnet `~/.rpnfunc.json` in `vim` |
| `:s` | Zeigt SimVars |
| `:l` | Zeigt Variablen |
| `:r` | Setzt Variablen zurück |
| `:rl` | Zeigt gespeicherte History |
| `:?` | Zeigt letzten Ausdruck als Postfix |
| `:= <expr>` | Wandelt Infix in Postfix und wertet aus |
| *leer* | Zeigt Hilfe |

---

## 🇬🇧 English

### Overview

**RPN-CALC** is a feature-rich RPN calculator for Node.js, inspired by Mobiflight and MSFS scripting.

It supports variables, parameters, math operators, user functions, SimVar read/write, and a persistent history system.

---

### Operators

| Category | Symbol | Description |
|-----------|---------|-------------|
| Arithmetic | `+ - * / % ^` | Basic math operations |
| Comparison | `> < >= <= == !=` | Returns 1 or 0 |
| Logical | `and or not` | Boolean logic |
| Math | `round floor ceil abs sqrt sin cos tan log exp min max clamp` | Common math functions |
| Direction | `dnor` | Normalizes angles to 0–359° |
| Conditional | `if{ ... } else{ ... }` | Executes conditional blocks |

---

### Variables

| Type | Name | Persistent | Description |
|-------|------|-------------|--------------|
| Session | `sp0..sp9`, `lp0..lp9` | No | Temporary |
| Persistent | `s0..s9`, `l0..l9` | Yes | Saved to `~/.rpn_state.json` |
| Parameters | `p1..p9` | No | User input |
| History | `r`, `r1..r8`, `r1,2` | Yes | From previous results |

---

### Parameters

When using `p1`, `p2`, etc., the user is prompted for values.

With `--noprompt`, input occurs **without labels**, suitable for REPL integration.

---

### SimVars

SimVars are read and written using Mobiflight syntax:

```
(A:VAR, Type)         ← read
(>A:VAR, Type)        ← write
```

All stored in `~/.simvars.json`.

---

### Functions

Defined in `~/.rpnfunc.json`:

```json
[{ "name": "add90", "params": 1, "rpn": "p1 90 + dnor" }]
```

Inline-expanded when used.

---

### History

RPN-CALC remembers the last 8 result stacks.

Access them via `r`, `r2`, `r1,2`, etc.

They are stored in `~/.rpnstack.json`.

---

### JSON Files

| File | Purpose | Example |
|-------|----------|----------|
| `~/.rpn_state.json` | Persistent variables | `{ "vars": [0,1,2,3] }` |
| `~/.simvars.json` | SimVars | `{ "simvars": { "A:VAR": 123 } }` |
| `~/.rpnfunc.json` | User functions | `[{"name":"add90","params":1,"rpn":"p1 90 + dnor"}]` |
| `~/.rpnstack.json` | History | `{ "results": [[8],[1,2,3]] }` |

---

### RPN-REPL

| Command | Description |
|----------|-------------|
| `:e` | Edit `~/.simvars.json` |
| `:fe` | Edit `~/.rpnfunc.json` |
| `:l` | Show variables |
| `:s` | Show SimVars |
| `:r` | Reset variables |
| `:rl` | Show result history |
| `:?` | Show last expression as postfix |
| `:= expr` | Convert infix to postfix and evaluate |
| *(empty)* | Show help |

---

## 🧾 Example Session

```bash
$ node rpn.js "p1 p2 +" --noprompt
5
3
5 3 +
8

$ node rpn.js "330 90 + dnor"
330 90 + dnor
60

$ node rpn.js "50 add90"
50 90 + dnor
140
```

---

**Author:** Carsten — 2025  
**Languages:** 🇩🇪 German & 🇬🇧 English  
**License:** MIT
