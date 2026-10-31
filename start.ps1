$ErrorActionPreference = 'Stop'
Set-Location -LiteralPath $PSScriptRoot
$port = if ($env:PORT) { [int]$env:PORT } else { 8080 }
$url = "http://localhost:$port"
try {
    $response = Invoke-RestMethod "$url/api/listings" -TimeoutSec 3
    if ($null -ne $response.listings) {
        Write-Host "Bibi is already running: $url"
        Start-Process $url
        exit 0
    }
} catch { }
New-Item -ItemType Directory -Force -Path (Join-Path $PSScriptRoot 'data') | Out-Null
$python = (Get-Command python -ErrorAction Stop).Source
Start-Process -FilePath $python -ArgumentList '-u','server.py' -WorkingDirectory $PSScriptRoot -WindowStyle Hidden -RedirectStandardOutput (Join-Path $PSScriptRoot 'data/server.out.log') -RedirectStandardError (Join-Path $PSScriptRoot 'data/server.err.log')
for ($attempt = 0; $attempt -lt 10; $attempt++) {
    Start-Sleep -Milliseconds 500
    try {
        $response = Invoke-RestMethod "$url/api/listings" -TimeoutSec 1
        if ($null -ne $response.listings) {
            Write-Host "Bibi is ready: $url"
            Start-Process $url
            exit 0
        }
    } catch { }
}
throw 'Server did not start. Check data/server.err.log and whether the port is occupied.'
