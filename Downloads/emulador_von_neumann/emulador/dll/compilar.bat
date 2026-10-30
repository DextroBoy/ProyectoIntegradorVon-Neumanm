@echo off
REM ==================================================================
REM  compilar.bat  -  regenera suma.dll desde cero (Windows x64)
REM  Ejecutar desde esta carpeta:  compilar.bat
REM ==================================================================

REM Nos ubicamos en la carpeta donde vive este .bat para usar rutas relativas.
cd /d "%~dp0"

REM Paso 1: ensamblar suma.asm a un objeto COFF de 64 bits (suma.obj).
REM         -f win64  => formato de objeto para Windows x64.
nasm -f win64 suma.asm -o suma.obj
if errorlevel 1 goto error

REM Paso 2: enlazar el objeto y producir la DLL compartida (suma.dll).
REM         -shared   => genera una biblioteca dinamica (.dll).
gcc -shared suma.obj -o suma.dll
if errorlevel 1 goto error

echo.
echo  OK: suma.obj y suma.dll generados correctamente.
goto fin

:error
echo.
echo  ERROR: fallo la compilacion. Revisa que nasm y gcc esten en el PATH.
exit /b 1

:fin
