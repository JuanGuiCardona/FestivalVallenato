@echo off
chcp 65001 >nul
cd /d "%~dp0"
title Sistema Web de Votaciones - Festival Vallenato 2027
echo.
echo  ==========================================================
echo   Sistema Web de Votaciones - Festival Vallenato 2027
echo   Demostracion local con SQLite (no necesita MySQL)
echo  ==========================================================
echo.

where python >nul 2>nul
if errorlevel 1 (
  echo  Necesitas Python 3.11 o superior: https://www.python.org/downloads/
  echo  Al instalarlo marca la casilla "Add python.exe to PATH".
  pause
  exit /b 1
)

if not exist ".venv\Scripts\python.exe" (
  echo  [1/4] Creando entorno virtual .venv ...
  python -m venv .venv || goto error
)
call ".venv\Scripts\activate.bat"

echo  [2/4] Instalando Django ...
python -m pip install --quiet --disable-pip-version-check "Django>=5.2,<6.2" "python-dotenv>=1.0" || goto error

if exist ".env" goto paso3
echo  Creando archivo .env de demostracion ...
python -c "from django.core.management.utils import get_random_secret_key as g; q=chr(39); n=chr(10); open('.env','w',encoding='utf-8').write('DJANGO_SECRET_KEY='+q+g()+q+n+'DJANGO_DEBUG=1'+n+'DB_ENGINE=sqlite'+n)" || goto error

:paso3
echo  [3/4] Creando la base de datos y cargando los datos de ejemplo ...
python manage.py migrate --noinput -v 0 || goto error
python manage.py cargar_datos_festival --demo || goto error

echo.
echo  [4/4] Listo. Abre en el navegador:  http://127.0.0.1:8000/
echo.
echo     Votante:        votante@demo.co  /  demo1234
echo     Administrador:  admin@demo.co    /  admin1234
echo.
echo  Para detener el servidor cierra esta ventana o presiona Ctrl + C.
echo.
start "" cmd /c "timeout /t 3 >nul & start http://127.0.0.1:8000/"
python manage.py runserver
goto :eof

:error
echo.
echo  Ocurrio un error. Revisa el mensaje de arriba.
pause
exit /b 1
