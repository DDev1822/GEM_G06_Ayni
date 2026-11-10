@echo off
cd /d "%~dp0"
set /p ALIAS=Escribe tu alias (sin DNI ni nombre completo): 
python scripts\lab01\cierre_grupal_v2.py exportar-individual --alias "%ALIAS%" --salida "%~dp0..\GEM_G06_%ALIAS%_INDIVIDUAL.zip"
echo El ZIP aparece en la carpeta superior al proyecto. Entregaselo al representante.
pause
