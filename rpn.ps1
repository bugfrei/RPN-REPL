while($true) {
    Write-Host "Ausdruck (:q=ende, ?=VarList; !=VarReset): " -NoNewLine
    $a = Read-Host
    if ($a -eq ":q") {
        break
    }
    if ($a -eq "?") {
        node rpn.js --print
        continue
    }
    if ($a -eq "!") {
        node rpn.js --reset
        continue
    }

    node rpn.js $a
}
