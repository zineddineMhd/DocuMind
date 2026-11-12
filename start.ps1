# DocuMind — démarrage local (Windows, sans Docker).
#   .\start.ps1          -> application complète sur http://localhost:8000
#   .\start.ps1 -Dev     -> backend (8000) + serveur Vite avec rechargement à chaud (5173)
param([switch]$Dev)

$ErrorActionPreference = "Stop"
$root = $PSScriptRoot
$py = Join-Path $root "backend\.venv\Scripts\python.exe"

if (-not (Test-Path (Join-Path $root ".env"))) {
    Copy-Item (Join-Path $root ".env.example") (Join-Path $root ".env")
    Write-Host "Fichier .env créé : renseignez GEMINI_API_KEY puis relancez." -ForegroundColor Yellow
    exit 1
}
if (-not (Test-Path $py)) {
    Write-Host "Création de l'environnement Python..." -ForegroundColor Cyan
    python -m venv (Join-Path $root "backend\.venv")
    & $py -m pip install -r (Join-Path $root "backend\requirements.txt")
}
if (-not (Test-Path (Join-Path $root "frontend\node_modules"))) {
    Write-Host "Installation des dépendances du frontend..." -ForegroundColor Cyan
    Push-Location (Join-Path $root "frontend"); npm install --no-audit --no-fund; Pop-Location
}

$env:HF_HUB_DISABLE_SYMLINKS_WARNING = "1"
$env:PYTHONIOENCODING = "utf-8"

if ($Dev) {
    Start-Process powershell -ArgumentList "-NoExit", "-Command", "cd '$root\frontend'; npm run dev"
    Write-Host "Interface (dev) : http://localhost:5173" -ForegroundColor Green
} else {
    if (-not (Test-Path (Join-Path $root "frontend\dist\index.html"))) {
        Write-Host "Compilation du frontend..." -ForegroundColor Cyan
        Push-Location (Join-Path $root "frontend"); npm run build; Pop-Location
    }
    Write-Host "DocuMind : http://localhost:8000   (API : http://localhost:8000/docs)" -ForegroundColor Green
}
Push-Location (Join-Path $root "backend")
try { & $py -m uvicorn app.main:app --host 127.0.0.1 --port 8000 } finally { Pop-Location }
