@echo off
cd /d "%~dp0"
call conda activate markdown_tracker 2>nul
python -m tests.test_config
pause
