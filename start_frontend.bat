@echo off
echo ========================================
echo Starting Frontend Web Server...
echo ========================================
echo.

cd /d "%~dp0\web"

echo Checking if node_modules exists...
if not exist "node_modules\" (
    echo Installing dependencies...
    call npm install
    if %errorlevel% neq 0 (
        echo Error: Failed to install dependencies
        pause
        exit /b 1
    )
)

echo.
echo Starting Vite dev server on http://localhost:3000
echo.

call npm run dev

pause
