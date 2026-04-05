#!/bin/bash
# Gold Dashboard 启动脚本

set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"
BACKEND_DIR="$PROJECT_DIR/backend"

# 配置
HOST="${HOST:-127.0.0.1}"
PORT="${PORT:-18000}"
LOG_FILE="${LOG_FILE:-$PROJECT_DIR/app.log}"

# 颜色
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

usage() {
    echo "用法: $0 [命令]"
    echo ""
    echo "命令:"
    echo "  start     启动服务 (默认)"
    echo "  stop      停止服务"
    echo "  restart   重启服务"
    echo "  status    查看状态"
    echo "  logs      查看日志"
    echo ""
    echo "环境变量:"
    echo "  HOST      监听地址 (默认: 127.0.0.1)"
    echo "  PORT      监听端口 (默认: 18000)"
    echo "  LOG_FILE  日志文件 (默认: ./app.log)"
}

is_running() {
    pgrep -f "uvicorn.*backend.main:app.*--port $PORT" > /dev/null 2>&1
}

start() {
    if is_running; then
        echo -e "${YELLOW}服务已在运行 (端口 $PORT)${NC}"
        return 1
    fi

    echo -e "${GREEN}启动 Gold Dashboard...${NC}"
    echo "  监听地址: $HOST:$PORT"
    echo "  日志文件: $LOG_FILE"
    echo ""

    cd "$PROJECT_DIR"

    # 启动服务
    nohup python3 -m uvicorn backend.main:app \
        --host "$HOST" \
        --port "$PORT" \
        --reload \
        >> "$LOG_FILE" 2>&1 &

    local pid=$!
    echo $pid > "$PROJECT_DIR/app.pid"

    # 等待启动
    sleep 2

    if is_running; then
        echo -e "${GREEN}✓ 服务已启动${NC}"
        echo "  PID: $pid"
        echo "  地址: http://$HOST:$PORT"
        echo ""
        echo "查看日志: $0 logs"
        echo "停止服务: $0 stop"
    else
        echo -e "${RED}✗ 启动失败${NC}"
        echo "查看日志排查问题: $0 logs"
        exit 1
    fi
}

stop() {
    if ! is_running; then
        echo -e "${YELLOW}服务未运行${NC}"
        return 1
    fi

    echo -e "${YELLOW}停止服务...${NC}"

    # 优雅关闭
    pkill -f "uvicorn.*backend.main:app.*--port $PORT" 2>/dev/null || true

    # 等待进程退出
    local count=0
    while is_running && [ $count -lt 10 ]; do
        sleep 0.5
        count=$((count + 1))
    done

    # 强制终止
    if is_running; then
        pkill -9 -f "uvicorn.*backend.main:app.*--port $PORT" 2>/dev/null || true
    fi

    rm -f "$PROJECT_DIR/app.pid"

    echo -e "${GREEN}✓ 服务已停止${NC}"
}

status() {
    if is_running; then
        echo -e "${GREEN}● 服务运行中${NC} (端口 $PORT)"
        if [ -f "$PROJECT_DIR/app.pid" ]; then
            echo "  PID: $(cat "$PROJECT_DIR/app.pid")"
        fi
    else
        echo -e "${RED}○ 服务未运行${NC}"
    fi
}

show_logs() {
    if [ -f "$LOG_FILE" ]; then
        tail -f "$LOG_FILE"
    else
        echo -e "${YELLOW}日志文件不存在: $LOG_FILE${NC}"
        echo "服务可能未启动"
    fi
}

# 主逻辑
case "${1:-start}" in
    start)
        start
        ;;
    stop)
        stop
        ;;
    restart)
        stop
        sleep 1
        start
        ;;
    status)
        status
        ;;
    logs)
        show_logs
        ;;
    -h|--help|help)
        usage
        ;;
    *)
        echo -e "${RED}未知命令: $1${NC}"
        usage
        exit 1
        ;;
esac
