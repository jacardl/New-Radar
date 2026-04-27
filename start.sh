#!/bin/bash
# =============================================================================
# New Radar - 智能启动脚本
# 自动检测变更，只重建需要更新的部分
# =============================================================================

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

CYAN='\033[0;36m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m'

API_PORT=8642
WEB_PORT=3010

log_info() { echo -e "${CYAN}[INFO]${NC} $1"; }
log_success() { echo -e "${GREEN}[OK]${NC} $1"; }
log_warn() { echo -e "${YELLOW}[WARN]${NC} $1"; }
log_error() { echo -e "${RED}[ERROR]${NC} $1"; }

echo ""
echo "New Radar - Hermes Agent"
echo ""

# 检查 Docker
if ! docker info >/dev/null 2>&1; then
    log_error "Docker 未运行"
    exit 1
fi

# 确保 .env 存在
[ -f .env ] || cp .env.example .env

# 解析参数
MODE="${1:-auto}"

# 智能检测函数
detect_changes() {
    local rebuild="none"

    # 检查镜像是否存在
    if ! docker image inspect newradar-radar >/dev/null 2>&1; then
        echo "  - 新安装，需要完整构建"
        echo "all"
        return
    fi

    # 检查后端代码是否比镜像新
    for f in backend/*.py; do
        if [ -f "$f" ]; then
            image_time=$(docker image inspect newradar-radar --format='{{.Created}}' 2>/dev/null)
            file_time=$(stat -c %y "$f" 2>/dev/null | cut -d'.' -f1)
            # 简单比较：如果文件修改时间更新
            if [ "$file_time" > "$image_time" ] 2>/dev/null; then
                echo "  - 后端代码变更，需要重建 radar"
                echo "radar"
                return
            fi
        fi
    done

    echo "none"
}

# 执行启动
case $MODE in
    radar)
        log_info "重建 radar (后端代码变更)..."
        docker-compose up -d --build radar
        ;;
    backend)
        log_info "重建 radar (后端代码变更)..."
        docker-compose up -d --build radar
        ;;
    open-webui)
        log_info "重建 open-webui..."
        docker-compose up -d --build open-webui
        ;;
    env)
        log_info "重启服务 (env 变更，无需重建)..."
        docker-compose restart radar open-webui
        ;;
    none)
        log_info "启动已有容器..."
        docker-compose start
        ;;
    auto|*)
        log_info "检查变更..."
        CHANGES=$(detect_changes)
        if [ "$CHANGES" == "all" ]; then
            log_info "完整构建..."
            docker-compose up -d --build
        elif [ "$CHANGES" == "radar" ]; then
            log_info "重建 radar..."
            docker-compose up -d --build radar
        else
            log_info "启动服务..."
            docker-compose up -d
        fi
        ;;
esac

log_success "服务已启动"
echo ""
echo "  API:       http://localhost:$API_PORT"
echo "  OpenWebUI: http://localhost:$WEB_PORT"
echo "  Adminer:   http://localhost:8080"
echo ""
echo "用法: start.sh [radar|backend|env|none]"
echo "  radar/backend  - 重建 radar (代码变更)"
echo "  env           - 重启服务 (env 变更)"
echo "  none          - 启动已有容器"
echo "  (默认)        - 自动检测"
