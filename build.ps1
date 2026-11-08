# Budowanie Luna.exe.
# Uruchomienie:  powershell -ExecutionPolicy Bypass -File build.ps1
$ErrorActionPreference = "Stop"
Set-Location $PSScriptRoot

if (-not (Get-Command pyinstaller -ErrorAction SilentlyContinue)) {
    python -m pip install pyinstaller
}

$opts = @("--noconfirm", "--noconsole", "--onefile", "--name", "Luna", "--icon", "luna.ico")
# blokada reklam: skrypty JS i zasoby zastępcze czytane w czasie działania; kompilator list działa w podprocesie
# (Luna.exe --luna-adblock-compile), więc jego moduł trzeba dołączyć jawnie
$opts += @("--add-data", "adblock\js;adblock\js", "--add-data", "adblock\res;adblock\res", "--add-data", "adblock\luna-filters.txt;adblock", "--hidden-import", "adblock.compiler")
# opcjonalne moduły (dołączane tylko, gdy są zainstalowane)
foreach ($pkg in @("winrt", "psutil")) {
    $ok = $false
    try { python -c "import $pkg" *> $null; $ok = ($LASTEXITCODE -eq 0) } catch { }
    if ($ok) { $opts += @("--collect-all", $pkg) }
}

python -m PyInstaller @opts luna.py
Write-Host "Gotowe: dist\Luna.exe"
