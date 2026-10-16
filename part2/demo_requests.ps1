param(
    [string]$BaseUrl = "http://127.0.0.1:5000"
)

Write-Output "=== GET /potions ==="
curl.exe -sS -i "$BaseUrl/potions"

$body = '{"name":"Moonlight Elixir","effect":"See clearly in darkness","ingredients":["moonwater","silverleaf"]}'
$bodyFile = Join-Path $env:TEMP "potions-demo-body.json"
Set-Content -LiteralPath $bodyFile -Value $body -Encoding utf8

try {
    Write-Output "`n=== POST /potions ==="
    curl.exe -sS -i -X POST "$BaseUrl/potions" -H "Content-Type: application/json" --data-binary "@$bodyFile"

    Write-Output "`n=== POST duplicate potion (409) ==="
    curl.exe -sS -i -X POST "$BaseUrl/potions" -H "Content-Type: application/json" --data-binary "@$bodyFile"

    Write-Output "`n=== POST without JSON Content-Type (415) ==="
    curl.exe -sS -i -X POST "$BaseUrl/potions" --data-binary "@$bodyFile"

    Write-Output "`n=== PUT /potions/1 (405) ==="
    curl.exe -sS -i -X PUT "$BaseUrl/potions/1" -H "Content-Type: application/json" --data-binary "@$bodyFile"
}
finally {
    Remove-Item -LiteralPath $bodyFile -Force -ErrorAction SilentlyContinue
}

Write-Output "`n=== GET /potions/1 ==="
curl.exe -sS -i "$BaseUrl/potions/1"

Write-Output "`n=== DELETE /potions/1 ==="
curl.exe -sS -i -X DELETE "$BaseUrl/potions/1"

Write-Output "`n=== GET /potions/999 (404) ==="
curl.exe -sS -i "$BaseUrl/potions/999"
