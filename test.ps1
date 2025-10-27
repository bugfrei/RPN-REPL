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

Step "Setzen von Variablen (s0=1, s1=2)"
node rpn.js "1 s0 2 s1"
node rpn.js "l0 l1"
Erg "Ergebnis: 1 2"

Step "Ausgabe der Variablen (--print)"
node rpn.js --print
Erg "Variablenliste"

Step "Zurücksetzen der Variablen (--reset) und deren Ausgabe"
node rpn.js --reset
node rpn.js --print
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

Step "Testen von if{ else{"
node rpn.js "1 if{ 11 (>A:XXX) } else{ 21 (>A:XXX) }"
node rpn.js "(A:XXX)"
node rpn.js "0 if{ 11 (>A:XXX) } else{ 21 (>A:XXX) }"
node rpn.js "(A:XXX)"
Erg "Ergebnis: 11 `n 21"

Step "Testen von if{ else{ im Step Modus"
node rpn.js "1 if{ 2 (>A:XXX) 22 100 } else{ 3 (>A:XXX) 33 100 }" --step; node rpn.js "(A:XXX)"
Erg "Ergebnis: 22 100 `n 2"

Step "Testen von if{ else{ mit Funktionen im Step Modus"
node rpn.js "1 if{ 2 (>A:XXX) 22 100 add90 } else{ 3 (>A:XXX) 33 100 add90 } +" --step; node rpn.js "(A:XXX)"
Erg "Ergebnis 212`n 2"

Step "Testen von if{ else{ mit Funktionen im Step Modus und Precompile"
node rpn.js "1 if{ 2 (>A:XXX) 22 100 add90 } else{ 3 (>A:XXX) 33 100 add90 } +" --step --precompile; node rpn.js "(A:XXX)"
Erg "Ergebnis 212`n 2"

Step "Testen von Step und Infix (Berechnung als Infix z.B: 5 + 3 = 8 und nicht 5 3 + = 8)"
node rpn.js "5 3 + 2 *" --step --infix
Erg "Ergebnis: 5 + 3 = 8`n8 * 2 = 16"

Step "Testen von Operatoren +-*/%^ (Plus,Minus,Mal,Geteilt,Modulo,Potenz) 5 3 + 2 - 10 * 6 / 2 ^ 95 %"
node rpn.js "5 3 + 2 - 10 * 6 / 2 ^ 95 %"
Erg "Ergebnis: 5"

Step "Testen von Operatoren pow2,pow,sqrt2,sqrt. 7 pow2, 10 3 pow, 49 sqrt2, 1000 3 sqrt round"
node rpn.js "7 pow2 10 3 pow 49 sqrt2 1000 3 sqrt round"
Erg "Ergebnis: 49 1000 7 10"

Step "Testen von Operatoren >,<,>=,<=,== / =,!= / <>. Jeweilse mit 5 und 3"
node rpn.js "5 3 > 5 3 < 5 3 >= 5 3 <= 5 3 == 5 3 = 5 3 != 5 3 <>"
Erg "Ergebnis: 1 0 1 0 0 0 1 1"

Step "Testen von Operatoren and, or und not / !. Jeweils mit alles Varianten (0 0, 0 1, 1 0, 1 1)"
node rpn.js "0 0 and 0 1 and 1 0 and 1 1 and"
node rpn.js "0 0 or 0 1 or 1 0 or 1 1 or"
node rpn.js "0 not 1 not 0 ! 1 !"
Erg "Ergebnisse:`n 0 0 0 1`n 0 1 1 1`n 1 0 1 0"

Step "Testen Mathematischer Operatoren (5.6 round, 5.3 round, 5.8 floor, 5.3 ceil, 0 5 - abs"
node rpn.js "5.6 round 5.3 round 5.8 floor 5.3 ceil 0 5 - abs"
Erg "Ergebnis: 6 5 5 6 5"

Step "Testen von sin, cos, tan - jeweils mit 10"
node rpn.js "10 sin"
node rpn.js "10 cos"
node rpn.js "10 tan"
Erg "Ergebnisse:`n -0.5440211108893698`n -0.8390715290764524`n 0.6483608274590866"#

Step "Testen von exp, log (10 log, 1000 log 10 log /, 2 exp log)"
node rpn.js "10 log"
node rpn.js "1000 log 10 log /"
node rpn.js "2 exp log"
Erg "Ergebnisse:`n 2.302585092994046`n 2.999999999999996`n 2"

Step "Testen von min, max (jeweils mit 7 und 1)"
node rpn.js "7 1 min"
node rpn.js "7 1 max"
Erg "Ergebnisse:`n 1`n 7"

Step "Testen von clamp (10 20 5 clamp)"
node rpn.js "10 20 5 clamp"
Erg "Ergebniss: 10"

Step "Testen von dnor (400 dnor)"
node rpn.js "400 dnor"
Erg "Ergebniss: 40"





Write-Host "Fertig"

