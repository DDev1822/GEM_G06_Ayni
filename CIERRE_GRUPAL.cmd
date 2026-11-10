@echo off
setlocal EnableDelayedExpansion
cd /d "%~dp0"
:menu
cls
echo LAB01 G06 - Cierre de grupo
 echo 1 - Importar ZIP de un integrante
 echo 2 - Preparar cierre grupal
 echo 3 - Incorporar trabajos recibidos despues
 echo 4 - Revisar pendientes (sin bloquear)
 echo 5 - Crear ZIP docente (incluso incompleto)
 echo 6 - Crear UN commit local (solo si esta configurado Git)
 echo 0 - Salir
set /p OPCION=Opcion: 
if "%OPCION%"=="1" (
 set /p ARCHIVO=Ruta del ZIP individual: 
 call python scripts\lab01\cierre_grupal_v2.py importar --desde "!ARCHIVO!"
)
if "%OPCION%"=="2" call python scripts\lab01\cierre_grupal_v2.py preparar
if "%OPCION%"=="3" call python scripts\lab01\cierre_grupal_v2.py incorporar
if "%OPCION%"=="4" call python scripts\lab01\cierre_grupal_v2.py verificar --permitir-incompleta
if "%OPCION%"=="5" call python scripts\lab01\cierre_grupal_v2.py zip --salida "%~dp0..\GEM_G06_ENTREGA_20261111.zip"
if "%OPCION%"=="6" (
 echo Requiere que el docente haya preparado el repositorio privado y autorizado el commit.
 set /p AUTORIZA=Escribe SI para confirmar el commit (se hace una vez): 
 if /I "!AUTORIZA!"=="SI" call python scripts\lab01\cierre_grupal_v2.py commit --confirmar-representante
)
if "%OPCION%"=="0" exit /b 0
pause
goto menu
