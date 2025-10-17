# repl.ps1
$Last = ""
$History = New-Object System.Collections.Generic.List[string]

Write-Host "PS Mini-REPL – Strg+C zum Beenden."
while ($true) {
    $prompt = "Parameter"
    if ($Last) { $prompt += " [$Last]" }
    $input = Read-Host $prompt
    if ([string]::IsNullOrWhiteSpace($input)) { $input = $Last }
    if ($input) {
        $Last = $input
        $History.Insert(0, $input)
    }
    node .\rpn.js $input
}

