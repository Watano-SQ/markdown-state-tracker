# Markdown State Tracker - Quick Start (PowerShell)
# Usage: .\quick_start.ps1

Write-Host ""
Write-Host "========================================" -ForegroundColor Cyan
Write-Host "Markdown State Tracker - Quick Start" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""

# Step 1: Check Conda
Write-Host "[1] Checking Conda installation..." -ForegroundColor Yellow
try {
    $condaVersion = conda --version 2>$null
    Write-Host "  [OK] Conda installed: $condaVersion" -ForegroundColor Green
} catch {
    Write-Host "  [ERROR] Conda not found. Please install Miniconda or Anaconda" -ForegroundColor Red
    Read-Host "Press Enter to exit"
    exit 1
}
Write-Host ""

# Step 2: Create or activate environment
Write-Host "[2] Setting up Conda environment..." -ForegroundColor Yellow
$envExists = conda info --envs | Select-String "markdown_tracker"
if (-not $envExists) {
    Write-Host "  - Creating new environment: markdown_tracker"
    conda create -n markdown_tracker python=3.11 -y
    if ($LASTEXITCODE -ne 0) {
        Write-Host "  [ERROR] Failed to create environment" -ForegroundColor Red
        Read-Host "Press Enter to exit"
        exit 1
    }
} else {
    Write-Host "  [OK] Environment already exists" -ForegroundColor Green
}
Write-Host ""

# Step 3: Activate environment
Write-Host "[3] Activating environment..." -ForegroundColor Yellow
& conda activate markdown_tracker 2>$null
if ($LASTEXITCODE -ne 0) {
    # Try using conda.bat
    & cmd.exe /c "conda activate markdown_tracker && python --version" >$null 2>&1
}
Write-Host "  [OK] Environment activated" -ForegroundColor Green
Write-Host ""

# Step 4: Install dependencies
Write-Host "[4] Installing dependencies..." -ForegroundColor Yellow
pip install -r requirements.txt
if ($LASTEXITCODE -ne 0) {
    Write-Host "  [ERROR] Failed to install dependencies" -ForegroundColor Red
    Read-Host "Press Enter to exit"
    exit 1
}
Write-Host "  [OK] Dependencies installed" -ForegroundColor Green
Write-Host ""

# Step 5: Verify imports
Write-Host "[5] Verifying module imports..." -ForegroundColor Yellow
python -c "import openai; print('  [OK] OpenAI module')"
python -c "from dotenv import load_dotenv; print('  [OK] python-dotenv')"
Write-Host ""

# Step 6: Check .env
Write-Host "[6] Checking API Key configuration..." -ForegroundColor Yellow
if (-not (Test-Path ".env")) {
    Write-Host "  - Creating .env file..."
    Copy-Item ".env.example" ".env"
    Write-Host "  [INFO] .env created (you need to fill in OPENAI_API_KEY)" -ForegroundColor Cyan
} else {
    Write-Host "  [OK] .env file exists" -ForegroundColor Green
}
Write-Host ""

# Step 7: Quick test
Write-Host "[7] Running quick test..." -ForegroundColor Yellow
python main.py --init
Write-Host ""
python main.py --skip-extraction
if ($LASTEXITCODE -ne 0) {
    Write-Host "  [ERROR] Quick test failed" -ForegroundColor Red
    Read-Host "Press Enter to exit"
    exit 1
}
Write-Host ""

# Step 8: Stats
Write-Host "[8] Checking stats..." -ForegroundColor Yellow
python main.py --stats
Write-Host ""

# Complete
Write-Host "========================================" -ForegroundColor Green
Write-Host "[SUCCESS] Quick start completed!" -ForegroundColor Green
Write-Host "========================================" -ForegroundColor Green
Write-Host ""
Write-Host "Next steps:" -ForegroundColor Cyan
Write-Host "1. Edit .env file and add your OPENAI_API_KEY" -ForegroundColor White
Write-Host "2. Run: python main.py" -ForegroundColor White
Write-Host "3. View: output/status.md" -ForegroundColor White
Write-Host ""
Read-Host "Press Enter to close"
