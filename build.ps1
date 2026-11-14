# Budowanie Luny na Windows: dist\Luna\Luna.exe (folder z programem) i – jeśli jest Inno Setup 6 – instalator
# dist\Luna-<wersja>-Windows-Setup.exe. Wydania na wszystkie systemy buduje GitHub (.github\workflows\release.yml).
# Uruchomienie:  powershell -ExecutionPolicy Bypass -File build.ps1
$ErrorActionPreference = "Stop"
Set-Location $PSScriptRoot

python -m pip install -r packaging\requirements-build.txt   # stałe, sprawdzone wersje (Smart App Control)
python -m PyInstaller --noconfirm packaging\luna.spec
if ($LASTEXITCODE -ne 0) { throw "PyInstaller zakończył się błędem" }

$version = (Select-String -Path luna.py -Pattern '^VERSION = "([^"]+)"').Matches[0].Groups[1].Value
$iscc = Join-Path ${env:ProgramFiles(x86)} "Inno Setup 6\ISCC.exe"
if (Test-Path $iscc) {
    & $iscc "/DAppVersion=$version" "/DSourceDir=..\dist\Luna" packaging\luna.iss
    Write-Host "Gotowe: dist\Luna-$version-Windows-Setup.exe"
} else {
    Write-Host "Gotowe: dist\Luna\Luna.exe (instalator: zainstaluj Inno Setup 6 – https://jrsoftware.org/isdl.php)"
}
