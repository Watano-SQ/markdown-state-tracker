@echo off
cd /d "%~dp0"
call conda activate markdown_tracker 2>nul
python test_config.py
pause
