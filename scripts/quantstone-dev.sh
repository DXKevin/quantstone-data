#!/usr/bin/env bash

set -euo pipefail

PROJECT_ROOT="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
LOG_DIR="$PROJECT_ROOT/var/logs"
BACKEND_LOG="$LOG_DIR/backend.log"
FRONTEND_LOG="$LOG_DIR/frontend.log"
BACKEND_UNIT="quantstone-data-backend.service"
FRONTEND_UNIT="quantstone-data-frontend.service"
BACKEND_PORT="${QUANTSTONE_BACKEND_PORT:-8000}"
FRONTEND_PORT="${QUANTSTONE_FRONTEND_PORT:-5173}"

unit_is_active() {
    systemctl --user is-active --quiet "$1"
}

require_runtime() {
    command -v systemd-run >/dev/null 2>&1 || {
        echo "当前系统缺少 systemd-run，无法持久运行服务。" >&2
        exit 1
    }
    systemctl --user show-environment >/dev/null 2>&1 || {
        echo "用户级 systemd 不可用，请先确认用户会话状态。" >&2
        exit 1
    }
    [[ -x "$PROJECT_ROOT/.venv/bin/uvicorn" ]] || {
        echo "缺少后端环境，请先安装 Python 依赖。" >&2
        exit 1
    }
    [[ -x "$PROJECT_ROOT/web/node_modules/.bin/vite" ]] || {
        echo "缺少前端环境，请先在 web 目录运行 npm install。" >&2
        exit 1
    }
    [[ -f "$PROJECT_ROOT/.env" ]] || {
        echo "缺少 $PROJECT_ROOT/.env。" >&2
        exit 1
    }
}

wait_for_url() {
    local name="$1"
    local url="$2"
    local unit="$3"
    for _ in {1..40}; do
        if curl --fail --silent --output /dev/null "$url"; then
            return 0
        fi
        if ! unit_is_active "$unit"; then
            break
        fi
        sleep 0.5
    done
    echo "$name 启动失败，最近日志：" >&2
    if [[ "$unit" == "$BACKEND_UNIT" ]]; then
        tail -n 30 "$BACKEND_LOG" >&2 || true
    else
        tail -n 30 "$FRONTEND_LOG" >&2 || true
    fi
    return 1
}

print_access_urls() {
    local found=0
    local address
    for address in $(hostname -I 2>/dev/null || true); do
        case "$address" in
            10.* | 192.168.*)
                ;;
            172.*)
                local second_octet="${address#172.}"
                second_octet="${second_octet%%.*}"
                if ((second_octet < 16 || second_octet > 31)); then
                    continue
                fi
                ;;
            *)
                continue
                ;;
        esac
        echo "局域网访问：http://$address:$FRONTEND_PORT"
        found=1
    done
    if [[ "$found" -eq 0 ]]; then
        echo "局域网访问：http://<服务器内网IP>:$FRONTEND_PORT"
    fi
}

start_backend() {
    if unit_is_active "$BACKEND_UNIT"; then
        return
    fi
    systemctl --user reset-failed "$BACKEND_UNIT" 2>/dev/null || true
    systemd-run --user \
        --unit "$BACKEND_UNIT" \
        --collect \
        --property "Description=QuantStone Data backend" \
        --property "WorkingDirectory=$PROJECT_ROOT" \
        --property "Restart=on-failure" \
        --property "RestartSec=2s" \
        --property "StandardOutput=append:$BACKEND_LOG" \
        --property "StandardError=append:$BACKEND_LOG" \
        "$PROJECT_ROOT/.venv/bin/uvicorn" quantstone_data.main:app \
        --env-file "$PROJECT_ROOT/.env" \
        --host 0.0.0.0 \
        --port "$BACKEND_PORT" \
        >/dev/null
}

start_frontend() {
    if unit_is_active "$FRONTEND_UNIT"; then
        return
    fi
    systemctl --user reset-failed "$FRONTEND_UNIT" 2>/dev/null || true
    systemd-run --user \
        --unit "$FRONTEND_UNIT" \
        --collect \
        --property "Description=QuantStone Data frontend" \
        --property "WorkingDirectory=$PROJECT_ROOT/web" \
        --property "Restart=on-failure" \
        --property "RestartSec=2s" \
        --property "StandardOutput=append:$FRONTEND_LOG" \
        --property "StandardError=append:$FRONTEND_LOG" \
        "$PROJECT_ROOT/web/node_modules/.bin/vite" \
        --host 0.0.0.0 \
        --port "$FRONTEND_PORT" \
        --strictPort \
        >/dev/null
}

start_services() {
    require_runtime
    mkdir -p "$LOG_DIR"
    start_backend
    if ! wait_for_url "后端" "http://127.0.0.1:$BACKEND_PORT/health" "$BACKEND_UNIT"; then
        stop_services
        exit 1
    fi
    start_frontend
    if ! wait_for_url "前端" "http://127.0.0.1:$FRONTEND_PORT" "$FRONTEND_UNIT"; then
        stop_services
        exit 1
    fi
    echo "QuantStone Data 已启动。"
    echo "本机前端：http://127.0.0.1:$FRONTEND_PORT"
    echo "后端接口：http://127.0.0.1:$BACKEND_PORT/docs"
    print_access_urls
}

stop_unit() {
    local name="$1"
    local unit="$2"
    if unit_is_active "$unit"; then
        systemctl --user stop "$unit"
        echo "$name 已停止。"
    else
        echo "$name 未运行。"
    fi
    systemctl --user reset-failed "$unit" 2>/dev/null || true
}

stop_services() {
    stop_unit "前端" "$FRONTEND_UNIT"
    stop_unit "后端" "$BACKEND_UNIT"
}

show_unit_status() {
    local name="$1"
    local unit="$2"
    local port="$3"
    if unit_is_active "$unit"; then
        local pid
        pid="$(systemctl --user show "$unit" --property MainPID --value)"
        echo "$name：运行中，PID $pid，端口 $port"
    else
        echo "$name：未运行"
    fi
}

show_status() {
    show_unit_status "后端" "$BACKEND_UNIT" "$BACKEND_PORT"
    show_unit_status "前端" "$FRONTEND_UNIT" "$FRONTEND_PORT"
    if unit_is_active "$FRONTEND_UNIT"; then
        print_access_urls
    fi
}

show_logs() {
    echo "后端日志：$BACKEND_LOG"
    tail -n 30 "$BACKEND_LOG" 2>/dev/null || true
    echo
    echo "前端日志：$FRONTEND_LOG"
    tail -n 30 "$FRONTEND_LOG" 2>/dev/null || true
}

case "${1:-start}" in
    start)
        start_services
        ;;
    stop)
        stop_services
        ;;
    restart)
        stop_services
        start_services
        ;;
    status)
        show_status
        ;;
    logs)
        show_logs
        ;;
    *)
        echo "用法：$0 {start|stop|restart|status|logs}" >&2
        exit 2
        ;;
esac
