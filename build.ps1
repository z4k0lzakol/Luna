# Budowanie Luna.exe z wbudowanymi kluczami OAuth (luna_oauth.json nie trafia do repozytorium – patrz .gitignore).
# Uruchomienie:  powershell -ExecutionPolicy Bypass -File build.ps1
$ErrorActionPreference = "Stop"
Set-Location $PSScriptRoot

if (-not (Get-Command pyinstaller -ErrorAction SilentlyContinue)) {
    python -m pip install pyinstaller
}

$opts = @("--noconfirm", "--noconsole", "--onefile", "--name", "Luna", "--icon", "luna.ico")
# blokada reklam: skrypty JS i zasoby zastępcze czytane w czasie działania; kompilator list działa w podprocesie
# (Luna.exe --luna-adblock-compile), więc jego moduł trzeba dołączyć jawnie
$opts += @("--add-data", "adblock\js;adblock\js", "--add-data", "adblock\res;adblock\res", "--hidden-import", "adblock.compiler")
if (Test-Path "luna_oauth.json") {
    $opts += @("--add-data", "luna_oauth.json;.")
    Write-Host "Klucze OAuth: wbudowane (luna_oauth.json)"
} else {
    Write-Host "UWAGA: brak luna_oauth.json – przyciski Połącz dla Google/Spotify/Discord nie zadziałają w tym pliku .exe"
}
# opcjonalne moduły (dołączane tylko, gdy są zainstalowane)
foreach ($pkg in @("winrt", "psutil", "keyring")) {
    $ok = $false
    try { python -c "import $pkg" *> $null; $ok = ($LASTEXITCODE -eq 0) } catch { }
    if ($ok) { $opts += @("--collect-all", $pkg) }
}

python -m PyInstaller @opts luna.py
Write-Host "Gotowe: dist\Luna.exe"
