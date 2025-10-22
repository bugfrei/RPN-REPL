function Step {
    param([string]$text)
    Clear-Host
    Write-Host "Teste: $text" -ForegroundColor Black -BackgroundColor Yellow
}
function Erg {
    param([string]$output)
    $output = $output.Replace("Ergebnis:", "Ergebnis:`n")
    Write-Host "$output" -ForegroundColor Green
    Read-Host "Weiter..."
}
Step "Step Modus (--step)"
node rpn.js "1 2 + 3 4 + *" --step
Erg "Ergebnis: 21"

Step "Testen des Results"
node rpn.js "r"
node rpn.js "1 2 3 4 5"
node rpn.js "r1"
node rpn.js "r1,3"
node rpn.js "r2"
Erg "Ergebnis: 21 `n 1 2 3 4 5 `n 1 2 3 4 5 `n 3 `n 21"

Step "Step Modus (--step) mit Funktion, ohne Precompile"
node rpn.js "280 add90 add90" --step
Erg "Ergebnis: 100"

Step "Step Modus (--step) mit Funktion, mit Precompile (--precompile)"
node rpn.js "280 add90 add90" --step --precompile  
Erg "Ergebnis: 100"

Step "Step Modus (--step) mit Hervorhebung (--mark)"
node rpn.js "1 2 + 3 4 + *" --step --mark
Erg "Ergebnis: 21"

Step "Step Modus (--step) ohne Farben (--nocolor)"
node rpn.js "1 2 + 3 4 + *" --step --nocolor
Erg "Ergebnis: 21"

Step "Eingabe von Parameter (p1=1, p2=2)"
node rpn.js "p1 p2 +"
Erg "Bei Eingabe von 1 und 2 ist Ergebnis: 3"

Step "Eingabe von Paramter ohne Prompt (--noprompt) (p1=3, p2=4)"
node rpn.js "p1 p2 +" --noprompt
Erg "Ohne Prompt bei Eingabe von 3 und 4 ist Ergebnis: 7"

Step "Parameter aus cts JSON"
node rpn.js "p1 p2 +" --ctx '{ "params": { "p1": 10, "p2": 20 } }'
Erg "Ergebnis: 30"

Step "Ausgabe der Variablen (--print)"
node rpn.js --print
Erg "Variablenliste"

Step "Zurücksetzen der Variablen (--reset)"
node rpn.js --reset
Erg "Variablen zurückgesetzt"

Step "Testen der demo_func.json (add180)"
node rpn.js "90 add180" --func ./demo_func.json
Erg "Ergebnis: 270"

Step "Testen der demo_state.json (Variablen)"
node rpn.js "l0 l1 l2 l3 l4 + + + +" --state ./demo_state.json
Erg "Ergebnis: 54321"

Step "Testen der demo_simvars.json (SimVars)"
node rpn.js "(A:Variable1) (A:Size,number) (A:Drei) (A:Vier) (A:Fünf) + + + +" --sim ./demo_simvars.json
Erg "Ergebnis: 54321"

Step "Testen lesen und schreiben von SimVars (A:XXX)"
node rpn.js "10001 (>A:XXX)"
node rpn.js "(A:XXX)"
node rpn.js "10002 (>A:XXX)"
node rpn.js "(A:XXX)"
Erg "Ergebnis: 10001 `n 10002"

Step "Testen der demo_stack.json (Results)"
node rpn.js "r" --stack ./demo_stack.json
node rpn.js "r2" --stack ./demo_stack.json
node rpn.js "r2,3" --stack ./demo_stack.json
Erg "Ergebnis: 1 `n 1 2 3 4 5 `n 3"

Write-Host "Fertig"

