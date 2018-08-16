REM https://stackoverflow.com/questions/45013771/issues-on-running-python-script-from-windows-batch-file

@ECHO OFF
COLOR 0A

title Control Drone Dashboard Server
REM Check if python is in path
WHERE python > nul
IF %ERRORLEVEL% NEQ 0 (
	ECHO ERROR: "python" wasn't found in the environment variable path.\n
	GOTO :TERMINATE
)

REM Detect python version/bit size
SET get_version=python -c "import sys, re; m = re.match('(\d\.\d).*', sys.version); print(m.group(1))"
SET get_bit=python -c "import sys; print('64-bit') if sys.maxsize > 2**32 else print('32-bit')"
FOR /F %%i IN (' %get_version% ') DO SET p_version=%%i
FOR /F %%i IN (' %get_bit% ') DO SET p_bit=%%i

ECHO Detected Python %p_version% (%p_bit%)
ECHO.
IF NOT "%p_version%" == "3.6" (
	IF NOT "%p_version%" == "3.5" (
		ECHO ERROR: This installer requires python version 3.5/3.6.
		GOTO :TERMINATE
	)
)


echo Setting up virtual environment
if exist "venv" (
	echo virtual environment already set up
	call "venv/Scripts/activate.bat"
) else (
	python -m venv venv
	call "venv/Scripts/activate.bat"
	python -m pip install --upgrade pip setuptools wheel
	pip install -r requirements.txt
	cd tf-openpose
	python setup.py install
	cd ..
)
start "Running Drone Dashboard Server..." python -m src.webapp.app
GOTO :TERMINATE

:TERMINATE
ECHO.
ECHO Closing this console...
ECHO.
PAUSE
EXIT /b

