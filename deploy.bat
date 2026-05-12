@echo off
chcp 65001 >nul
::===============================================================================
:: New Radar Deployment Script (Windows Batch)
:: Run as Administrator for first deployment
:: Windows 10/11 + Docker Desktop
::===============================================================================

setlocal enabledelayedexpansion

set "SCRIPT_DIR=%~dp0"
cd /d "%SCRIPT_DIR%"

:: Container names (matches docker-compose.yml)
set "RADAR_CONTAINER=radar"
set "DB_CONTAINER=radar-db"
set "ADMINER_CONTAINER=radar-adminer"

:: Check Docker Compose
docker compose version >nul 2>&1
if errorlevel 1 (
    docker-compose --version >nul 2>&1
    if errorlevel 1 (
        echo [ERROR] Docker Compose is not installed
        exit /b 1
    )
    set "DC=docker-compose"
) else (
    set "DC=docker compose"
)

::===============================================================================
:: Helper Functions
::===============================================================================

:log_info
    echo [INFO]  %~1
    goto :eof

:log_ok
    echo [OK]    %~1
    goto :eof

:log_warn
    echo [WARN]  %~1
    goto :eof

:log_error
    echo [ERROR] %~1
    goto :eof

:get_container_status
    :: Args: container_name, variable_name (sets %~2)
    for /f "tokens=*" %%s in ('docker inspect --format "{{.State.Status}}" %~1 2^>nul') do (
        set "%~2=%%s"
    )
    goto :eof

:check_docker
    docker --version >nul 2>&1
    if errorlevel 1 (
        echo [ERROR] Docker not installed, please install Docker Desktop first
        exit /b 1
    )
    goto :eof

::===============================================================================
:: Progress Display - watches containers and shows real-time status
:: Args: container names to watch (space separated)
::===============================================================================
:show_progress
    setlocal
    echo.
    :wait_loop
    set "all_ready=1"
    for %%c in (%*) do (
        call :get_container_status %%c status
        if not "!status!"=="running" (
            if not "!status!"=="healthy" (
                set "all_ready=0"
            )
        )
    )
    if "!all_ready!"=="0" (
        call :log_info "Waiting for services..."
        for %%c in (%*) do (
            call :get_container_status %%c s
            if "!s!"=="running" (
                echo   [READY]   %%c
            ) else (
                if "!s!"=="healthy" (
                    echo   [READY]   %%c
                ) else (
                    echo   [WAIT]    %%c
                )
            )
        )
        timeout /t 3 /nobreak >nul
        goto :wait_loop
    )
    endlocal
    goto :eof

::===============================================================================
:: 1. init - First deployment
::===============================================================================
:do_init
    echo ================================================================================
    echo   First Deployment Initialization
    echo ================================================================================
    echo.

    call :check_docker

    :: Create required directories
    call :log_info "Creating runtime directories..."
    if not exist "logs" mkdir logs
    if not exist "final_reports" mkdir final_reports
    if not exist "storage\reports" mkdir storage\reports
    if not exist "MindSpider\DeepSentimentCrawling\MediaCrawler\browser_data" mkdir MindSpider\DeepSentimentCrawling\MediaCrawler\browser_data
    call :log_ok "Runtime directories created"

    :: Create .env if not exists
    if not exist ".env" (
        call :log_info "Creating .env config file..."
        (
            echo # ========== Database Configuration ==========
            echo DB_HOST=db
            echo DB_PORT=5432
            echo DB_USER=radar
            echo DB_PASSWORD=radar
            echo DB_NAME=radar
            echo DB_DIALECT=postgresql
            echo.
            echo POSTGRES_USER=radar
            echo POSTGRES_PASSWORD=radar
            echo POSTGRES_DB=radar
            echo POSTGRES_PORT=5444
            echo.
            echo # ========== Flask Configuration ==========
            echo FLASK_HOST=0.0.0.0
            echo FLASK_PORT=5000
            echo.
            echo # ========== LLM API Configuration ==========
            echo DEEPSEEK_API_KEY=your-deepseek-api-key-here
            echo DEEPSEEK_BASE_URL=https://api.deepseek.com
            echo DEEPSEEK_MODEL_NAME=deepseek-chat
            echo.
            echo QUERY_ENGINE_API_KEY=%%DEEPSEEK_API_KEY%%
            echo QUERY_ENGINE_BASE_URL=%%DEEPSEEK_BASE_URL%%
            echo QUERY_ENGINE_MODEL_NAME=%%DEEPSEEK_MODEL_NAME%%
            echo.
            echo INSIGHT_ENGINE_API_KEY=%%DEEPSEEK_API_KEY%%
            echo INSIGHT_ENGINE_BASE_URL=%%DEEPSEEK_BASE_URL%%
            echo INSIGHT_ENGINE_MODEL_NAME=%%DEEPSEEK_MODEL_NAME%%
            echo.
            echo MEDIA_ENGINE_API_KEY=%%DEEPSEEK_API_KEY%%
            echo MEDIA_ENGINE_BASE_URL=%%DEEPSEEK_BASE_URL%%
            echo MEDIA_ENGINE_MODEL_NAME=%%DEEPSEEK_MODEL_NAME%%
            echo.
            echo OPENAI_API_KEY=%%DEEPSEEK_API_KEY%%
            echo OPENAI_BASE_URL=%%DEEPSEEK_BASE_URL%%
            echo OPENAI_MODEL_NAME=%%DEEPSEEK_MODEL_NAME%%
            echo.
            echo # ========== Search Engine Configuration ==========
            echo TAVILY_API_KEY=
            echo BOCHA_API_KEY=
            echo ANSPIRE_API_KEY=
            echo FIRECRAWL_API_KEY=
            echo.
            echo ENABLE_TAVILY=False
            echo ENABLE_BOCHA=False
            echo ENABLE_ANSPIRE=False
            echo ENABLE_FIRECRAWL=False
            echo ENABLE_SENTIMENT_TOOL=False
            echo.
            echo # ========== Crawler Configuration ==========
            echo CRAWLER_OUTPUT_DIR=./output
            echo MAX_REFLECTIONS=2
            echo SAVE_INTERMEDIATE_STATES=True
            echo SEARCH_CONTENT_MAX_LENGTH=3000
            echo MAX_SEARCH_RESULTS_FOR_LLM=20
            echo DEFAULT_SEARCH_HOT_CONTENT_LIMIT=100
            echo DEFAULT_SEARCH_TOPIC_GLOBALLY_LIMIT_PER_TABLE=30
            echo DEFAULT_SEARCH_TOPIC_BY_DATE_LIMIT_PER_TABLE=30
            echo DEFAULT_SEARCH_TOPIC_ON_PLATFORM_LIMIT_PER_TABLE=30
            echo DEFAULT_GET_COMMENTS_FOR_TOPIC_LIMIT=100
            echo SEARCH_TOOL_TYPE=LocalDB
            echo.
            echo # ========== Embedding Model Configuration ==========
            echo EMBEDDING_MODEL=sentence-transformers/all-MiniLM-L6-v2
        ) > .env
        call :log_ok ".env file created, please edit it to fill in API keys"
    ) else (
        call :log_warn ".env already exists, skipping"
    )

    :: Build
    call :log_info "Building Docker image (first build may take 5-10 minutes)..."
    %DC% build --no-cache radar

    :: Start all services in background and watch progress
    call :log_info "Starting all services..."
    %DC% up -d
    call :show_progress radar-db radar radar-adminer

    :: Initialize pgvector
    call :log_info "Initializing pgvector extension..."
    docker exec %DB_CONTAINER% psql -U radar -d radar -c "CREATE EXTENSION IF NOT EXISTS vector;" >nul 2>&1

    call :log_ok "Deployment complete!"
    echo.
    echo ================================================================================
    echo   Service Access URLs
    echo ================================================================================
    echo.
    echo   New Radar API:     http://localhost:5000
    echo   API Health Check:  http://localhost:5000/v1/health
    echo   Adminer DB Manage: http://localhost:8080
    echo.
    goto :eof

::===============================================================================
:: 2. start / stop / restart
::===============================================================================
:do_start
    call :log_info "Starting all services..."
    %DC% up -d
    call :show_progress radar-db radar radar-adminer
    call :log_ok "All services started"
    goto :eof

:do_stop
    call :log_info "Stopping New Radar services..."
    %DC% stop
    call :log_ok "All services stopped"
    goto :eof

:do_restart
    call :do_stop
    timeout /t 2 /nobreak >nul
    call :do_start
    goto :eof

::===============================================================================
:: 3. update - Incremental update
::===============================================================================
:do_update
    echo ================================================================================
    echo   Incremental Update
    echo ================================================================================
    echo.

    if exist ".git" (
        call :log_info "Pulling latest code..."
        git pull
        call :log_ok "Code updated"
    ) else (
        call :log_warn "Not a Git repository, skipping code update"
    )

    call :log_info "Rebuilding radar image..."
    %DC% build radar

    call :log_info "Restarting radar service..."
    %DC% up -d --no-deps radar
    call :show_progress radar
    call :log_ok "Incremental update complete"
    goto :eof

::===============================================================================
:: 4. logs
::===============================================================================
:do_logs
    if "%~1"=="" (
        %DC% logs -f --tail=100
    ) else (
        docker logs -f %~1 %2 %3 %4
    )
    goto :eof

::===============================================================================
:: 5. status
::===============================================================================
:do_status
    echo ================================================================================
    echo   Service Status
    echo ================================================================================
    echo.

    for %%c in (radar-db radar radar-adminer) do (
        call :get_container_status %%c s
        if "!s!"=="running" (
            echo   [GREEN]%%c: running
        ) else (
            if "!s!"=="healthy" (
                echo   [GREEN]%%c: healthy
            ) else (
                if defined s (
                    echo   [YELLOW]%%c: !s!
                ) else (
                    echo   [RED]%%c: not found
                )
            )
        )
    )
    echo.
    goto :eof

::===============================================================================
:: 6. shell / db
::===============================================================================
:do_shell
    docker exec -it %RADAR_CONTAINER% cmd
    goto :eof

:do_db
    docker exec -it %DB_CONTAINER% psql -U radar -d radar
    goto :eof

::===============================================================================
:: 7. health
::===============================================================================
:do_health
    echo ================================================================================
    echo   Health Check
    echo ================================================================================
    echo.

    call :log_info "Flask API: "
    curl -s -o nul -w "HTTP %%{http_code}" http://localhost:5000/v1/health
    echo.

    call :log_info "PostgreSQL: "
    docker exec %DB_CONTAINER% pg_isready -U radar -d radar >nul 2>&1
    if errorlevel 1 (
        call :log_error "not responding
    ) else (
        call :log_ok "responding
    )
    goto :eof

::===============================================================================
:: 8. dbinit
::===============================================================================
:do_dbinit
    echo.
    call :log_info "Initializing database..."
    docker exec %DB_CONTAINER% psql -U radar -d radar -c "CREATE EXTENSION IF NOT EXISTS vector;" >nul 2>&1
    call :log_ok "pgvector extension created"
    call :log_info "Creating crawled_data table..."
    docker exec %DB_CONTAINER% psql -U radar -d radar -c "
        CREATE TABLE IF NOT EXISTS crawled_data (
            id SERIAL PRIMARY KEY,
            platform VARCHAR(50),
            content_type VARCHAR(50),
            content TEXT,
            source_url TEXT,
            source_keyword TEXT,
            create_time BIGINT,
            ip_location VARCHAR(255),
            user_id VARCHAR(255),
            nickname VARCHAR(255),
            liked_count INTEGER DEFAULT 0,
            collected_count INTEGER DEFAULT 0,
            comment_count INTEGER DEFAULT 0,
            share_count INTEGER DEFAULT 0,
            embedding TEXT,
            add_time BIGINT DEFAULT EXTRACT(EPOCH FROM NOW())::BIGINT * 1000
        );
        CREATE INDEX IF NOT EXISTS idx_crawled_data_platform ON crawled_data(platform);
        CREATE INDEX IF NOT EXISTS idx_crawled_data_create_time ON crawled_data(create_time DESC);
    " >nul 2>&1
    call :log_ok "Database initialized"
    goto :eof

::===============================================================================
:: 10. prune
::===============================================================================
:do_prune
    echo.
    call :log_warn "This will remove all unused Docker images, containers and networks..."
    set /p confirm="Confirm? (yes/no): "
    if "!confirm!"=="yes" (
        docker system prune -f
        call :log_ok "Cleanup complete"
    ) else (
        call :log_info "Cancelled"
    )
    goto :eof

::===============================================================================
:: Help
::===============================================================================
:show_help
    echo.
    echo New Radar Deployment Script
    echo.
    echo Usage:
    echo   deploy.bat [command]
    echo.
    echo Commands:
    echo   deploy.bat init       First deployment
    echo   deploy.bat start      Start all services
    echo   deploy.bat stop       Stop all services
    echo   deploy.bat restart    Restart all services
    echo   deploy.bat update     Incremental update (git pull + rebuild)
    echo   deploy.bat logs       View logs (option: service name)
    echo   deploy.bat status     Show service status
    echo   deploy.bat health     Health check
    echo   deploy.bat shell      Enter Flask container
    echo   deploy.bat db         Enter PostgreSQL terminal
    echo   deploy.bat dbinit     Initialize database
    echo   deploy.bat prune      Clean up unused Docker resources
    echo.
    goto :eof

::===============================================================================
:: Main Entry
::===============================================================================
if "%~1"=="" goto :show_help

set "CMD=%~1"

if "%CMD%"=="init"        goto :do_init
if "%CMD%"=="start"       goto :do_start
if "%CMD%"=="stop"        goto :do_stop
if "%CMD%"=="restart"    goto :do_restart
if "%CMD%"=="update"      goto :do_update
if "%CMD%"=="logs"        goto :do_logs
if "%CMD%"=="status"      goto :do_status
if "%CMD%"=="shell"        goto :do_shell
if "%CMD%"=="db"          goto :do_db
if "%CMD%"=="health"      goto :do_health
if "%CMD%"=="dbinit"       goto :do_dbinit
if "%CMD%"=="prune"       goto :do_prune
if "%CMD%"=="help"        goto :show_help

call :log_error "Unknown command: %CMD%"
echo.
goto :show_help
