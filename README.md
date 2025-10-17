# 🧮 RPN System

Ein erweitertes **Reverse Polish Notation (RPN)**-System für CLI und Simulationen  
mit persistenter Speicherung, Funktions-Definitionen und REPL-Unterstützung.  

Bestehend aus:

- 🐍 **RPN-REPL** → interaktive Python-Shell (Frontend)
- ⚙️ **RPN-CALC** → Node.js-Interpreter (Backend)

---

## 🧭 Architektur

```
┌────────────────┐       ┌───────────────────┐
│ 🐍 RPN-REPL     │──────▶│ ⚙️ RPN-CALC        │
│ (Python Shell)  │       │ (Node.js Engine)  │
│ :e, :rl, := ... │       │ RPN Parser, Eval  │
└────────────────┘       └───────────────────┘
```

**Kommunikation:**  
RPN-REPL ruft `rpn.js` mit Kontextdateien auf (`--ctx`, `--func`, `--stack`).

---

## ⚙️ Installation

```bash
# Voraussetzung: Node.js & Python 3
npm install infix-rpn-eval

# Python REPL ausführbar machen
chmod +x rpn_repl.py
```

---

## 📂 Dateien & Speicherorte

| Datei | Zweck |
|--------|--------|
| `~/.simvars.json` | gespeicherte SimVars (z. B. MSFS Variablen) |
| `~/.rpnfunc.json` | benutzerdefinierte RPN-Funktionen |
| `~/.rpnstack.json` | gespeicherte Ergebnis-Stacks (max. 8) |
| `~/.rpn_state.json` | persistente Variablen (s0…s9) |
| `rpn.js` | Node.js-Interpreter (RPN-CALC) |
| `rpn_repl.py` | Python-Frontend (RPN-REPL) |

---

## 🐍 RPN-REPL

Die **interaktive Shell** für dein RPN-System.  
Sie verwaltet Kontexte, erlaubt das Bearbeiten von Dateien,  
zeigt Listen an und ruft `rpn.js` mit allen relevanten Daten auf.

### 🧑‍💻 Start

```bash
python3 rpn_repl.py
```

### 🧩 Befehle

| Befehl | Beschreibung |
|--------|---------------|
| `:e` | Öffnet `~/.simvars.json` im Editor (`vim` oder `$EDITOR`) |
| `:s` | Zeigt SimVars an |
| `:l` | Zeigt gespeicherte RPN-Variablen (s0…s9) |
| `:r` | Setzt RPN-Variablen zurück |
| `:f` | Listet Custom-Funktionen (`~/.rpnfunc.json`) |
| `:fe` | Öffnet Funktionsdatei im Editor |
| `:rl` | Listet gespeicherte Result-Stacks (`r1` … `r8`) |
| `:?` | Zeigt letzten RPN-Ausdruck (Postfix → Infix) |
| `:= <AUSDRUCK>` | Wandelt Infix → Postfix, zeigt & führt aus |
| `:q` | Beendet die REPL |
| *(leer)* | Bildschirm leeren & Hilfe anzeigen |

---

### 🧠 Beispiele

```text
rpn> 1 2 3 +
1 5

rpn> r,2
5

rpn> :rl
r1: 1 5

rpn> := 5 + 3
Als Postfix: 5 3 +
8
```

---

## ⚙️ RPN-CALC

Der **Node.js-Interpreter** (Backend).  
Er verarbeitet RPN-Ausdrücke, speichert Variablen und Funktionen,  
verwaltet SimVars und bietet eine Ergebnis-Historie.

### 🧑‍💻 Aufruf

```bash
node rpn.js "<RPN-Ausdruck>" [Optionen]
```

### 🔧 Optionen

| Parameter | Beschreibung |
|------------|---------------|
| `--state FILE` | Datei für Variablen (s0…s9) |
| `--sim FILE` | Datei für SimVars |
| `--ctx JSON` | Inline-Kontext, z. B. `--ctx '{"simvars":{}}'` |
| `--func FILE` | Datei mit Custom-Funktionen |
| `--stack FILE` | Datei mit Ergebnis-History |
| `--print` | Zeigt Variablen |
| `--reset` | Setzt Variablen zurück |

---

## 🗃️ Persistente Bereiche

| Bereich | Datei | Inhalt |
|----------|--------|--------|
| Variablen | `~/.rpn_state.json` | Werte von `s0…s9` |
| SimVars | `~/.simvars.json` | gespeicherte Flugsimulations-Variablen |
| Funktionen | `~/.rpnfunc.json` | benutzerdefinierte RPN-Makros |
| Ergebnisse | `~/.rpnstack.json` | letzte 8 Ergebnis-Stacks |

---

## 🔣 RPN-Syntax

### 🔢 Zahlen
```rpn
5
3.14
3,14   # Komma wird erkannt
```

### ➕ Arithmetik
```rpn
+  -  *  /  %  ^
```

### 🔍 Vergleiche & Logik
```rpn
>  <  >=  <=  ==  !=
and  or  not
```

### 🧮 Mathematische Funktionen
```rpn
round floor ceil abs sqrt sin cos tan log exp
min max clamp
```

### 🧭 Spezialfunktionen

| Token | Beschreibung |
|--------|---------------|
| `dnor` | Direction Normalize → Winkel auf [0, 360) begrenzen |
| `(A:NAME,TYPE)` | liest SimVar |
| `(>A:NAME,TYPE)` | schreibt SimVar |
| `if{ } else{ }` | Bedingungsblöcke |
| `Boolean`, `Number` | no-op (Kompatibilität zu Mobiflight) |

---

## 💾 Variablen

| Typ | Schreibweise | Bedeutung |
|------|----------------|--------------|
| persistent | `s0 … s9` | speichert oberstes Stack-Element |
| persistent | `l0 … l9` | lädt gespeicherten Wert |
| flüchtig | `sp0 … sp9` | temporär speichern |
| flüchtig | `lp0 … lp9` | temporär laden |

---

## ✈️ SimVars

Kompatibel zu **Mobiflight** / **MSFS RPN**-Notation.

| Beispiel | Bedeutung |
|-----------|------------|
| `(A:PLANE HEADING DEGREES, Degrees)` | liest den aktuellen Kurs |
| `(>A:AXIS_THROTTLE_SET, Percent)` | schreibt neuen Schubwert |

Beispiel:
```rpn
(A:THROTTLE:1, Percent) 0.5 + (>A:THROTTLE:1, Percent)
```

---

## 🧩 Custom-Funktionen

Definiert in `~/.rpnfunc.json`:

```json
[
  {
    "name": "add90",
    "params": 1,
    "rpn": "p1 90 + dnor"
  },
  {
    "name": "angle_diff",
    "params": 2,
    "rpn": "p1 p2 - 360 + 360 %"
  }
]
```

Verwendung:

```rpn
330 add90
# → 60

270 90 angle_diff
# → 180
```

---

## 🧠 Ergebnis-History (`r`-Token)

Nach jeder Berechnung wird der Stack gespeichert  
(max. 8 Stacks, neueste zuerst).

### Zugriff
| Token | Bedeutung |
|--------|------------|
| `r` oder `r1` | letzten Stack pushen |
| `r2` | zweitletzten Stack pushen |
| `r,3` | drittes Element aus letztem Stack |
| `r2,3` | drittes Element aus zweitletztem Stack |

Beispiel:
```rpn
1 2 3 +
# Stack: 1 5

r,2
# → 5
```

🛡️ **Sicherheitslogik:**  
Wenn ein Ausdruck nur ein `r`-Token enthält (`r`, `r2`, `r2,3` …),  
wird die gespeicherte History **nicht überschrieben**.

---

## 🧾 Beispiel-Dateien

### `~/.simvars.json`
```json
{
  "simvars": {
    "A:THROTTLE:1,Percent": 50,
    "A:PLANE HEADING DEGREES,Degrees": 270
  }
}
```

### `~/.rpnfunc.json`
```json
[
  { "name": "add90", "params": 1, "rpn": "p1 90 + dnor" },
  { "name": "wrap360", "params": 1, "rpn": "p1 360 % 360 + 360 %" }
]
```

### `~/.rpnstack.json`
```json
{
  "results": [
    [1, 5],
    [8],
    [60]
  ]
}
```

---

## 🧭 Typischer Workflow

```bash
python3 rpn_repl.py
```

```text
rpn> 330 90 + dnor
60

rpn> := 5 + 3
Als Postfix: 5 3 +
8

rpn> :rl
r1: 8
r2: 60

rpn> r,1
8

rpn> :q
```

---

## 🧩 Zusammenfassung

| Komponente | Zweck |
|-------------|--------|
| **RPN-REPL** | Python-Shell mit Befehlen, Editor-Integration & Infix-Support |
| **RPN-CALC** | Node-Interpreter mit Variablen, Funktionen & Ergebnis-History |

---

## 🧠 Merksatz

> „RPN denkt stapelweise.  
> Wer den Stack versteht, kontrolliert die Logik.“

---

© 2025 – Dein RPN-System für CLI & Simulation  
Lizenz: MIT
