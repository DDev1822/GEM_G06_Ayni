@echo off
cd /d "%~dp0"
set /p ALIAS=Alias breve (sin nombre completo ni DNI): 
python scripts\lab01\kai_lab01_v2.py iniciar --alias "%ALIAS%"
pause
