@echo off
REM Markdown State Tracker - Quick Start (Windows)

setlocal enabledelayedexpansion

echo.
echo ========================================
echo Markdown State Tracker - Quick Start
echo ========================================
echo.

REM Step 1: Check Conda
echo [1] Checking Conda installation...
conda --version >nul 2>&1
if errorlevel 1 (
    echo  [ERROR] Conda not found. Please install Miniconda or Anaconda
    pause
    exit /b 1
)
echo  [OK] Conda installed
echo.

REM Step 2: Create or activate environment
echo [2] Setting up Conda environment...
conda info --envs | findstr "markdown_tracker" >nul 2>&1
if errorlevel 1 (
    echo  - Creating new environment: markdown_tracker
    call conda create -n markdown_tracker python=3.11 -y
    if errorlevel 1 (
        echo  [ERROR] Failed to create environment
        pause
        exit /b 1
    )
) else (
    echo  [OK] Environment already exists
)
echo.

REM Step 3: Activate environment
echo [3] Activating environment...
call conda activate markdown_tracker
if errorlevel 1 (
    echo  [ERROR] Failed to activate environment
    pause
    exit /b 1
)
echo  [OK] Environment activated
echo.

REM Step 4: Install dependencies
echo [4] Installing dependencies...
pip install -r requirements.txt
if errorlevel 1 (
    echo  [ERROR] Failed to install dependencies
    pause
    exit /b 1
)
echo  [OK] Dependencies installed
echo.

REM Step 5: Verify imports
echo [5] Verifying module imports...
python -c "import openai; print('  [OK] OpenAI module')" || (
    echo  [ERROR] OpenAI module import failed
    pause
    exit /b 1
)
python -c "from dotenv import load_dotenv; print('  [OK] python-dotenv')" || (
    echo  [ERROR] python-dotenv import failed
    pause
    exit /b 1
)
echo.

REM Step 6: Check .env
echo [6] Checking API Key configuration...
if not exist ".env" (
    echo  - Creating .env file...
    copy .env.example .env >nul
    echo  [INFO] .env created (you need to fill in OPENAI_API_KEY)
) else (
    echo  [OK] .env file exists
)
echo.

REM Step 7: Quick test
echo [7] Running quick test...
python main.py --init
echo.
python main.py --skip-extraction
if errorlevel 1 (
    echo  [ERROR] Quick test failed
    pause
    exit /b 1
)
echo.

REM Step 8: Stats
echo [8] Checking stats...
python main.py --stats
echo.

REM Complete
echo ========================================
echo [SUCCESS] Quick start completed!
echo ========================================
echo.
echo Next steps:
echo 1. Edit .env file and add your OPENAI_API_KEY
echo 2. Run: python main.py
echo 3. View: output/status.md
echo.
pause
