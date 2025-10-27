if (Test-Path "/Users/carstenschlegel/Downloads/rpn.js") {
    copy "/Users/carstenschlegel/Downloads/rpn.js" . -Force
    del "/Users/carstenschlegel/Downloads/rpn.js"
    Write-Host "rpn.js upgedated"
}

if (Test-Path "/Users/carstenschlegel/Downloads/rpn_repl.py") {
    copy "/Users/carstenschlegel/Downloads/rpn_repl.py" . -Force
    del "/Users/carstenschlegel/Downloads/rpn_repl.py"
    Write-Host "rpn_repl.py upgedated"
}

if (Test-Path "/Users/carstenschlegel/Downloads/readme.md") {
    copy "/Users/carstenschlegel/Downloads/readme.md" . -Force
    del "/Users/carstenschlegel/Downloads/readme.md"
    Write-Host "readme.md upgedated"
}

if (Test-Path "/Users/carstenschlegel/Downloads/rpn_calc.py") {
    copy "/Users/carstenschlegel/Downloads/rpn_calc.py" . -Force
    del "/Users/carstenschlegel/Downloads/rpn_calc.py"
    Write-Host "rpn_calc.py"
}
