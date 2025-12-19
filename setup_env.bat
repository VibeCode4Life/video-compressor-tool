@echo off
echo Creating Python virtual environment...
python -m venv venv

echo Activating virtual environment...
call venv\Scripts\activate.bat

echo Installing dependencies...
pip install -r requirements.txt

echo.
echo Environment setup complete!
echo To run the app, type:
echo venv\Scripts\activate
echo python app.py
pause
