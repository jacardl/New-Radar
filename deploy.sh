#!/bin/bash
#===============================================================================
# New Radar 部署脚本
#
# 用法:
#   ./deploy.sh init       - 首次部署（创建 .env、构建镜像、启动服务）
#   ./deploy.sh start      - 启动所有服务
#   ./deploy.sh stop       - 停止所有服务
#   ./deploy.sh restart    - 重启所有服务
#   ./deploy.sh update     - 增量更新（git pull + 重建镜像）
#   ./deploy.sh logs       - 查看所有服务日志
#   ./deploy.sh status     - 查看服务状态
#   ./deploy.sh shell      - 进入 Flask 容器
#   ./deploy.sh db          - 进入数据库容器
#   ./deploy.sh health     - 健康检查
#
# Windows 用户: 使用 Git Bash / WSL / MSYS2 运行，或将脚本转为 .bat
#===============================================================================

set -e

# 颜色输出
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
NC='\033[0m' # No Color

# 项目根目录（脚本所在位置）
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

# 容器名称
RADAR_CONTAINER="radar"
DB_CONTAINER="radar-db"
ADMINER_CONTAINER="radar-adminer"

# Docker 网络
NETWORK_NAME="radar-net"

#-------------------------------------------------------------------------------
# 辅助函数
#-------------------------------------------------------------------------------

log_info()    { echo -e "${BLUE}[INFO]${NC}  $1"; }
log_success() { echo -e "${GREEN}[OK]${NC}   $1"; }
log_warn()    { echo -e "${YELLOW}[WARN]${NC}  $1"; }
log_error()   { echo -e "${RED}[ERROR]${NC} $1"; }

section() {
    echo ""
    echo -e "${CYAN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
    echo -e "${CYAN}  $1${NC}"
    echo -e "${CYAN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
}

check_docker() {
    if ! command -v docker &> /dev/null; then
        log_error "Docker 未安装，请先安装 Docker Desktop: https://www.docker.com/"
        exit 1
    fi
    if ! command -v docker compose &> /dev/null && ! docker compose version &> /dev/null; then
        log_error "Docker Compose 未安装"
        exit 1
    fi
    log_success "Docker 环境检查通过"
}

docker_compose() {
    if docker compose version &> /dev/null; then
        docker compose "$@"
    else
        docker-compose "$@"
    fi
}

# Show real-time progress of container startup
show_progress() {
    local containers="$*"
    echo ""
    log_info "Waiting for services to be ready..."
    while true; do
        local all_ready=1
        local ready_list=()
        local waiting_list=()
        for container in $containers; do
            local status=$(docker inspect --format '{{.State.Status}}' "$container" 2>/dev/null)
            if [ "$status" = "running" ] || [ "$status" = "healthy" ]; then
                ready_list+=("$container")
            else
                all_ready=0
                waiting_list+=("$container")
            fi
        done
        if [ "$all_ready" -eq 1 ]; then
            break
        fi
        echo "  Waiting: ${waiting_list[*]:-none}"
        sleep 3
    done
    log_success "All services ready"
}

#-------------------------------------------------------------------------------
# 1. init - 首次部署
#-------------------------------------------------------------------------------
do_init() {
    section "首次部署初始化"

    check_docker

    # 创建必要目录
    log_info "创建运行时目录..."
    mkdir -p logs final_reports storage/reports
    mkdir -p MindSpider/DeepSentimentCrawling/MediaCrawler/browser_data
    log_success "运行时目录创建完成"

    # 创建 .env 文件
    if [ ! -f .env ]; then
        log_info "创建 .env 配置文件..."
        cat > .env << 'EOF'
# ========== 数据库配置 ==========
DB_HOST=db
DB_PORT=5432
DB_USER=radar
DB_PASSWORD=radar
DB_NAME=radar
DB_DIALECT=postgresql

POSTGRES_USER=radar
POSTGRES_PASSWORD=radar
POSTGRES_DB=radar
POSTGRES_PORT=5444

# ========== Flask 配置 ==========
FLASK_HOST=0.0.0.0
FLASK_PORT=5000

# ========== LLM API 配置 ==========
# DeepSeek 示例
DEEPSEEK_API_KEY=your-deepseek-api-key-here
DEEPSEEK_BASE_URL=https://api.deepseek.com
DEEPSEEK_MODEL_NAME=deepseek-chat

# 通用的引擎配置（默认使用 DeepSeek）
QUERY_ENGINE_API_KEY=${DEEPSEEK_API_KEY}
QUERY_ENGINE_BASE_URL=${DEEPSEEK_BASE_URL}
QUERY_ENGINE_MODEL_NAME=${DEEPSEEK_MODEL_NAME}

INSIGHT_ENGINE_API_KEY=${DEEPSEEK_API_KEY}
INSIGHT_ENGINE_BASE_URL=${DEEPSEEK_BASE_URL}
INSIGHT_ENGINE_MODEL_NAME=${DEEPSEEK_MODEL_NAME}

MEDIA_ENGINE_API_KEY=${DEEPSEEK_API_KEY}
MEDIA_ENGINE_BASE_URL=${DEEPSEEK_BASE_URL}
MEDIA_ENGINE_MODEL_NAME=${DEEPSEEK_MODEL_NAME}

OPENAI_API_KEY=${DEEPSEEK_API_KEY}
OPENAI_BASE_URL=${DEEPSEEK_BASE_URL}
OPENAI_MODEL_NAME=${DEEPSEEK_MODEL_NAME}

# ========== 搜索引擎配置（可选，引擎现已默认只查本地库） ==========
TAVILY_API_KEY=
BOCHA_API_KEY=
ANSPIRE_API_KEY=
FIRECRAWL_API_KEY=

ENABLE_TAVILY=False
ENABLE_BOCHA=False
ENABLE_ANSPIRE=False
ENABLE_FIRECRAWL=False
ENABLE_SENTIMENT_TOOL=False

# ========== 爬虫配置 ==========
CRAWLER_OUTPUT_DIR=./output
MAX_REFLECTIONS=2
SAVE_INTERMEDIATE_STATES=True
SEARCH_CONTENT_MAX_LENGTH=3000
MAX_SEARCH_RESULTS_FOR_LLM=20
DEFAULT_SEARCH_HOT_CONTENT_LIMIT=100
DEFAULT_SEARCH_TOPIC_GLOBALLY_LIMIT_PER_TABLE=30
DEFAULT_SEARCH_TOPIC_BY_DATE_LIMIT_PER_TABLE=30
DEFAULT_SEARCH_TOPIC_ON_PLATFORM_LIMIT_PER_TABLE=30
DEFAULT_GET_COMMENTS_FOR_TOPIC_LIMIT=100
SEARCH_TOOL_TYPE=LocalDB

# ========== 向量模型配置 ==========
EMBEDDING_MODEL=sentence-transformers/all-MiniLM-L6-v2

# ========== Docker 内部访问地址 ==========
# 用于 Open WebUI 访问 New Radar API
RADAR_API_URL=http://host.docker.internal:5000
EOF
        log_success ".env 文件已创建，请编辑填写 API Key"
    else
        log_warn ".env 已存在，跳过创建"
    fi

    # 创建 Docker 网络
    log_info "创建 Docker 网络..."
    docker network create ${NETWORK_NAME} 2>/dev/null || log_info "网络 ${NETWORK_NAME} 已存在"

    # 构建并启动
    log_info "构建 Docker 镜像（首次构建可能需要 5-10 分钟）..."
    docker_compose build --no-cache radar

    log_info "启动所有服务..."
    docker_compose up -d

    show_progress radar-db radar radar-adminer

    if [ $retries -eq 0 ]; then
        log_error "数据库启动超时"
        exit 1
    fi

    # 初始化数据库扩展
    log_info "初始化数据库扩展..."
    docker exec ${DB_CONTAINER} psql -U radar -d radar -c "CREATE EXTENSION IF NOT EXISTS vector;" 2>/dev/null || true

    log_success "部署完成！"
    echo ""
    echo -e "${GREEN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
    echo -e "${GREEN}  服务访问地址${NC}"
    echo -e "${GREEN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
    echo -e "  New Radar API:     ${CYAN}http://localhost:5000${NC}"
    echo -e "  API 健康检查:      ${CYAN}http://localhost:5000/v1/health${NC}"
    echo -e "  Adminer DB管理:    ${CYAN}http://localhost:8080${NC}"
    echo ""
}

#-------------------------------------------------------------------------------
# 2. start - 启动服务
#-------------------------------------------------------------------------------
do_start() {
    section "启动所有服务"
    check_docker

    # 确保网络存在
    docker network create ${NETWORK_NAME} 2>/dev/null || true

    docker_compose up -d
    show_progress "radar-db" "radar" "radar-adminer"
    log_success "所有服务已启动"
}

#-------------------------------------------------------------------------------
# 3. stop - 停止服务
#-------------------------------------------------------------------------------
do_stop() {
    section "停止所有服务"
    log_info "停止 New Radar 服务..."
    docker_compose stop
    log_success "所有服务已停止"
}

#-------------------------------------------------------------------------------
# 4. restart - 重启服务
#-------------------------------------------------------------------------------
do_restart() {
    section "重启所有服务"
    do_stop
    sleep 2
    do_start
}

#-------------------------------------------------------------------------------
# 5. update - 增量更新
#-------------------------------------------------------------------------------
do_update() {
    section "增量更新"

    # 保存 .env 备份
    log_info "备份 .env 文件..."
    cp .env .env.backup.$(date +%Y%m%d%H%M%S)

    # Git pull
    if [ -d .git ]; then
        log_info "拉取最新代码..."
        git pull
        log_success "代码更新完成"
    else
        log_warn "非 Git 仓库，跳过代码更新"
    fi

    # 重建并重启 radar 服务（增量构建）
    log_info "重建 radar 镜像（使用缓存）..."
    docker_compose build --no-cache radar

    log_info "重启 radar 服务..."
    docker_compose up -d --no-deps radar
    show_progress radar

    log_success "增量更新完成"
}

#-------------------------------------------------------------------------------
# 6. logs - 查看日志
#-------------------------------------------------------------------------------
do_logs() {
    local service="${1:-}"
    if [ -n "$service" ]; then
        docker logs -f ${service}
    else
        docker_compose logs -f --tail=100
    fi
}

#-------------------------------------------------------------------------------
# 7. status - 服务状态
#-------------------------------------------------------------------------------
do_status() {
    section "服务状态"

    echo -e "  ${CYAN}New Radar (Flask):${NC}"
    if docker ps --format '{{.Names}}' | grep -q "^${RADAR_CONTAINER}$"; then
        local ip=$(docker inspect -f '{{range .NetworkSettings.Networks}}{{.IPAddress}}{{end}}' ${RADAR_CONTAINER} 2>/dev/null)
        echo -e "    容器:      ${GREEN}运行中${NC}"
        echo -e "    容器IP:   ${ip}"
        echo -e "    API地址:  http://localhost:5000"
    else
        echo -e "    容器:      ${RED}未运行${NC}"
    fi

    echo -e "  ${CYAN}PostgreSQL + pgvector:${NC}"
    if docker ps --format '{{.Names}}' | grep -q "^${DB_CONTAINER}$"; then
        echo -e "    容器:      ${GREEN}运行中${NC}"
        echo -e "    地址:      localhost:5444"
    else
        echo -e "    容器:      ${RED}未运行${NC}"
    fi

    echo -e "  ${CYAN}Adminer (数据库管理):${NC}"
    if docker ps --format '{{.Names}}' | grep -q "^${ADMINER_CONTAINER}$"; then
        echo -e "    容器:      ${GREEN}运行中${NC}"
        echo -e "    地址:      http://localhost:8080"
    else
        echo -e "    容器:      ${RED}未运行${NC}"
    fi

    echo ""
}

#-------------------------------------------------------------------------------
# 8. shell - 进入 Flask 容器
#-------------------------------------------------------------------------------
do_shell() {
    log_info "进入 Flask 容器（输入 exit 退出）..."
    docker exec -it ${RADAR_CONTAINER} /bin/bash
}

#-------------------------------------------------------------------------------
# 9. db - 进入数据库容器
#-------------------------------------------------------------------------------
do_db() {
    log_info "进入数据库容器（输入 exit 退出）..."
    docker exec -it ${DB_CONTAINER} psql -U radar -d radar
}

#-------------------------------------------------------------------------------
# 10. health - 健康检查
#-------------------------------------------------------------------------------
do_health() {
    section "健康检查"

    # Flask API
    log_info "检查 Flask API..."
    local http_code=$(curl -s -o /dev/null -w "%{http_code}" http://localhost:5000/v1/health 2>/dev/null || echo "000")
    if [ "$http_code" = "200" ]; then
        log_success "Flask API: 运行正常 (HTTP $http_code)"
        curl -s http://localhost:5000/v1/health 2>/dev/null | python3 -m json.tool 2>/dev/null || true
    else
        log_error "Flask API: 异常 (HTTP $http_code)"
    fi

    # 数据库
    log_info "检查数据库..."
    if docker exec ${DB_CONTAINER} pg_isready -U radar -d radar &>/dev/null; then
        log_success "PostgreSQL: 运行正常"
    else
        log_error "PostgreSQL: 异常"
    fi
}

#-------------------------------------------------------------------------------
# 11. dbinit - 初始化数据库
#-------------------------------------------------------------------------------
do_dbinit() {
    section "初始化数据库"
    log_info "执行数据库初始化..."

    # 检查初始化脚本
    if [ -f scripts/db/init_db.py ]; then
        log_info "执行 scripts/db/init_db.py ..."
        docker exec ${RADAR_CONTAINER} python scripts/db/init_db.py
    else
        log_info "创建 pgvector 扩展..."
        docker exec ${DB_CONTAINER} psql -U radar -d radar -c "CREATE EXTENSION IF NOT EXISTS vector;"
        log_info "创建 crawled_data 表..."
        docker exec ${DB_CONTAINER} psql -U radar -d radar -c "
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
        "
    fi
    log_success "数据库初始化完成"
}

#-------------------------------------------------------------------------------
# 15. prune - 清理
#-------------------------------------------------------------------------------
do_prune() {
    section "清理未使用的 Docker 资源"
    log_warn "这将删除所有未使用的镜像、容器和网络..."
    read -p "确认执行? (yes/no): " confirm
    if [ "$confirm" = "yes" ]; then
        docker system prune -f
        log_success "清理完成"
    else
        log_info "取消清理"
    fi
}

#-------------------------------------------------------------------------------
# 帮助信息
#-------------------------------------------------------------------------------
show_help() {
    echo ""
    echo -e "${CYAN}New Radar 部署脚本${NC}"
    echo ""
    echo -e "${GREEN}用法:${NC}"
    echo "  ./deploy.sh <命令>"
    echo ""
    echo -e "${GREEN}基础命令:${NC}"
    echo "  ./deploy.sh init       首次部署（创建配置 + 构建 + 启动）"
    echo "  ./deploy.sh start      启动所有服务"
    echo "  ./deploy.sh stop       停止所有服务"
    echo "  ./deploy.sh restart    重启所有服务"
    echo "  ./deploy.sh update     增量更新（git pull + 重建镜像）"
    echo "  ./deploy.sh logs       查看日志（可指定服务名）"
    echo "  ./deploy.sh status     查看服务状态"
    echo "  ./deploy.sh health     健康检查"
    echo ""
    echo -e "${GREEN}容器操作:${NC}"
    echo "  ./deploy.sh shell      进入 Flask 容器"
    echo "  ./deploy.sh db         进入数据库容器"
    echo "  ./deploy.sh dbinit     初始化数据库"
    echo ""
    echo -e "${GREEN}维护:${NC}"
    echo "  ./deploy.sh prune      清理未使用的 Docker 资源"
    echo "  ./deploy.sh help       显示本帮助信息"
    echo ""
    echo -e "${GREEN}日志查看示例:${NC}"
    echo "  ./deploy.sh logs                  # 所有服务日志"
    echo "  ./deploy.sh logs radar             # radar 服务日志"
    echo "  ./deploy.sh logs radar --tail=200  # 最近 200 行"
    echo ""
}

#-------------------------------------------------------------------------------
# 主入口
#-------------------------------------------------------------------------------
COMMAND="${1:-}"

case "$COMMAND" in
    init)           do_init ;;
    start)          do_start ;;
    stop)           do_stop ;;
    restart)        do_restart ;;
    update)         do_update ;;
    logs)           shift; do_logs "$@" ;;
    status)         do_status ;;
    shell)          do_shell ;;
    db)             do_db ;;
    health)         do_health ;;
    dbinit)         do_dbinit ;;
    prune)          do_prune ;;

    help|--help|-h) show_help ;;
    *)              log_error "未知命令: $COMMAND"; show_help; exit 1 ;;
esac
