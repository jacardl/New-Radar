@echo off
chcp 65001 >nul 2>&1
set SCRIPT_DIR=%~dp0
cd /d "%SCRIPT_DIR%"

set API_PORT=8642

echo.
echo New Radar - Hermes Agent Startup
echo.

where docker >nul 2>&1
if errorlevel 1 (
    echo [ERROR] Docker is not running
    exit /b 1
)

if not exist ".env" (
    echo [INFO] Copying .env.example to .env
    copy .env.example .env
)

set MODE=%1
if "%MODE%"=="" set MODE=auto

if "%MODE%"=="radar" goto rebuild_radar
if "%MODE%"=="backend" goto rebuild_radar
if "%MODE%"=="env" goto restart_only
if "%MODE%"=="none" goto start_only
if "%MODE%"=="auto" goto auto_detect
goto auto_detect

:rebuild_radar
echo [INFO] Rebuilding radar (backend code changed)...
docker-compose up -d --build radar
goto done

:restart_only
echo [INFO] Restarting services (env changed, no rebuild)...
docker-compose restart radar
goto done

:start_only
echo [INFO] Starting existing containers...
docker-compose start
goto done

:auto_detect
echo [INFO] Checking what needs to be rebuilt...

docker image inspect newradar-radar >nul 2>&1
if errorlevel 1 (
    echo [INFO] Image not found, full build needed
    docker-compose up -d --build
) else (
    echo [INFO] Image exists, restarting services
    docker-compose up -d
)
goto done

:done
echo.
echo [OK] Services started
echo.
echo   API:       http://localhost:%API_PORT%
echo   Adminer:   http://localhost:8080
echo.
echo Usage: start.bat [radar^|backend^|env^|none]
echo   radar      - rebuild radar (for backend code changes)
echo   env        - restart only (for .env changes)
echo   none       - start existing containers
echo   (no arg)   - auto-detect