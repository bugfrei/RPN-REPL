# 🧮 RPN-CALC & RPN-REPL

Ein leistungsfähiger **Reverse Polish Notation (RPN)** Rechner mit erweiterter Unterstützung für **Mobiflight / MSFS SimVars**, benutzerdefinierte Funktionen, Variablen, History und Integration in einen Python-basierten REPL.

---

## 🚀 Überblick

**RPN-CALC (`rpn.js`)**  
Ein Node.js-Programm zur Auswertung von RPN-Ausdrücken mit folgenden Features:

- Standardarithmetik, Logik, Vergleiche, Math-Funktionen
- Temporäre (`sp0..sp9`) und persistente (`s0..s9`) Variablen
- Zugriff auf **SimVars** (`(A:VAR,Type)` lesen / ` (>A:VAR,Type)` schreiben)
- Benutzerdefinierte Funktionen aus `~/.rpnfunc.json`
- History-Stack (`~/.rpnstack.json`) mit Zugriff via `r`, `r1`, `r1,2`, etc.
- Farbliche Ausgabe des **expandierten Postfix**-Ausdrucks
- Interaktive **Parameterabfragen (`p1`, `p2`, …)**

**RPN-REPL (`rpn_repl.py`)**  
Ein Python-REPL zur komfortablen Nutzung von `rpn.js` mit folgenden Zusatzbefehlen:

| Befehl | Beschreibung |
|---------|---------------|
| `:e` | Öffnet `~/.simvars.json` in `vim` |
| `:fe` | Öffnet `~/.rpnfunc.json` in `vim` |
| `:l` | Zeigt aktuelle Variablen (aus `~/.rpn_state.json`) |
| `:s` | Zeigt SimVars (`~/.simvars.json`) |
| `:r` | Setzt Variablen zurück |
| `:rl` | Zeigt gespeicherte Result-Stacks (`~/.rpnstack.json`) |
| `:?` | Gibt den letzten Ausdruck als Postfix (via `infix-rpn-eval`) aus |
| `:= <AUSDRUCK>` | Erstellt Postfix aus Infix, gibt ihn aus und wertet ihn |
| *leere Eingabe* | Zeigt die Hilfe-Liste der Befehle |

---

## ⚙️ Installation & Initialisierung mit `init.py`

Das Python-Skript **`init.py`** bereitet die komplette Umgebung für `RPN-CALC` und `RPN-REPL` vor.

### Funktionen
- Prüft Node.js und npm
- Führt bei Bedarf `npm init -y` aus
- Installiert das Paket `infix-rpn-eval`
- Erstellt alle nötigen Dateien mit Standardwerten:
  - `~/.simvars.json`
  - `~/.rpnfunc.json`
  - `~/.rpn_state.json`
  - `~/.rpnstack.json`
- Führt erste Tests mit `rpn.js` durch
- Fragt bei vorhandenen Dateien, ob sie überschrieben werden sollen
- Gibt am Ende die Meldung aus:  
  **„RPN-CALC und RPN-REPL sind bereit“**

### Ausführung
```bash
python3 init.py
```

---

## 🧠 Parameterverwendung (`p1`, `p2`, …)

RPN-CALC unterstützt **dynamische Parameter**, die während der Ausführung abgefragt werden:

```bash
node rpn.js "p1 p2 +"
Wert für p1: 5
Wert für p2: 3
5 3 +
8
```

Mit `--noprompt` werden **keine Texte angezeigt**, aber die Eingabe erfolgt weiterhin:
```bash
node rpn.js "p1 p2 +" --noprompt
5
3
5 3 +
8
```

> ⚠️ **Hinweis:**  
> Wenn RPN-CALC über den Python-REPL verwendet wird, können **Darstellungsfehler** bei den Prompts auftreten  
> (z. B. erscheinen die Texte erst nach der Eingabe).  
> Dieses Verhalten ist rein visuell – die Eingaben funktionieren korrekt.

---

## 💾 JSON-Dateien & Formate

| Datei | Beschreibung | Beispiel |
|--------|----------------|-----------|
| `~/.simvars.json` | Enthält SimVar-Werte | `{ "simvars": { "A:NAV OBS:1, Degrees": 270 } }` |
| `~/.rpnfunc.json` | Enthält benutzerdefinierte Funktionen | `[{"name": "add90", "params": 1, "rpn": "p1 90 + dnor"}]` |
| `~/.rpn_state.json` | Enthält persistente Variablen s0..s9 | `{ "vars": [0,1,2,3,4,5,6,7,8,9] }` |
| `~/.rpnstack.json` | Enthält die letzten 8 Ergebnis-Stacks | `{ "results": [[8],[1,2,3]] }` |

---

## 🧩 Syntax-Beispiele

### Grundrechenarten
```
5 3 +        → 8
10 2 /       → 5
10 3 %       → 1
2 3 ^        → 8
```

### Vergleich & Logik
```
5 3 >        → 1
5 3 ==       → 0
1 0 and      → 0
1 0 or       → 1
not          → Negation (1 → 0)
```

### Math-Funktionen
```
5.7 round    → 6
9 sqrt       → 3
30 sin       → -0.988
330 90 + dnor → 60
```

### Funktionen & Parameter
```
# ~/.rpnfunc.json
[{"name": "add90", "params": 1, "rpn": "p1 90 + dnor"}]

# Nutzung:
node rpn.js "50 add90"
→ Postfix: 50 90 + dnor
→ Ergebnis: 140
```

---

## 🧾 Ergebnis-History

Bis zu 8 letzte Ergebnisse werden in `~/.rpnstack.json` gespeichert.

| Token | Beschreibung |
|--------|---------------|
| `r` oder `r1` | Letztes Ergebnis |
| `r2` | Zweitletztes Ergebnis |
| `r1,2` | Zweiter Wert des letzten Ergebnis-Stacks |
| `r,3` | Dritter Wert des letzten Ergebnis-Stacks |
| `:rl` im REPL | Listet alle gespeicherten Ergebnis-Stacks auf |

**Hinweis:**  
Wird ein Ausdruck ausgewertet, der nur aus `r`-Tokens besteht,  
wird die History **nicht überschrieben**.

---

## 🧰 Tipps & Hinweise

- Alle Pfade (`--state`, `--sim`, `--func`, `--stack`) sind über CLI oder Umgebungsvariablen konfigurierbar.  
- Mit `--ctx` kann ein JSON-Objekt mit `params` und `simvars` übergeben werden.
- Die **Farbige Postfix-Ausgabe** (cyan) kann bei Bedarf durch eine `--no-color`-Option erweitert werden.

---

## ✅ Beispiel-Session

```bash
$ node rpn.js "5 3 +"
5 3 +
8

$ node rpn.js "p1 p2 +" --noprompt
1
2
1 2 +
3

$ node rpn.js "330 90 + dnor"
330 90 + dnor
60
```

---

**Entwickelt für**: Mobiflight / MSFS Enthusiasten, Power-User, und alle, die RPN auf der Kommandozeile lieben ❤️

