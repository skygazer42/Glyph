@echo off
echo ========================================
echo Starting Backend API Server...
echo ========================================
echo.

cd /d "%~dp0"

echo Activating conda environment...
call conda activate gov
if %errorlevel% neq 0 (
    echo Error: Failed to activate conda environment 'gov'
    pause
    exit /b 1
)

echo.
echo Starting FastAPI server on http://localhost:8000
echo API Documentation: http://localhost:8000/docs
echo.

python api_server.py

pause
