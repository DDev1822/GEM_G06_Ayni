@echo off
cd /d "%~dp0"
python scripts\lab01\exportar_recorrido_gem.py
if errorlevel 1 echo Revisa el mensaje de Kai; no se confirma ninguna entrega remota.
pause
