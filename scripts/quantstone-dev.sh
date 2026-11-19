#!/usr/bin/env bash

set -euo pipefail

PROJECT_ROOT="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
RUNTIME_DIR="$PROJECT_ROOT/var/run"
LOG_DIR="$PROJECT_ROOT/var/logs"
BACKEND_PID_FILE="$RUNTIME_DIR/backend.pid"
FRONTEND_PID_FILE="$RUNTIME_DIR/frontend.pid"
BACKEND_LOG="$LOG_DIR/backend.log"
FRONTEND_LOG="$LOG_DIR/frontend.log"
BACKEND_PORT="${QUANTSTONE_BACKEND_PORT:-8000}"
FRONTEND_PORT="${QUANTSTONE_FRONTEND_PORT:-5173}"

is_running() {
    local pid_file="$1"
    [[ -f "$pid_file" ]] || return 1
    local pid
    pid="$(<"$pid_file")"
    [[ "$pid" =~ ^[0-9]+$ ]] && kill -0 "$pid" 2>/dev/null
}

remove_stale_pid() {
    local pid_file="$1"
    if [[ -f "$pid_file" ]] && ! is_running "$pid_file"; then
        rm -f "$pid_file"
    fi
}

wait_for_url() {
    local name="$1"
    local url="$2"
    local pid_file="$3"
    local log_file="$4"
    for _ in {1..40}; do
        if curl --fail --silent --output /dev/null "$url"; then
            return 0
        fi
        if ! is_running "$pid_file"; then
            break
        fi
        sleep 0.5
    done
    echo "$name 启动失败，最近日志：" >&2
    tail -n 30 "$log_file" >&2 || true
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

start_services() {
    mkdir -p "$RUNTIME_DIR" "$LOG_DIR"
    remove_stale_pid "$BACKEND_PID_FILE"
    remove_stale_pid "$FRONTEND_PID_FILE"

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

    if ! is_running "$BACKEND_PID_FILE"; then
        (
            cd "$PROJECT_ROOT"
            nohup "$PROJECT_ROOT/.venv/bin/uvicorn" quantstone_data.main:app \
                --env-file "$PROJECT_ROOT/.env" \
                --host 0.0.0.0 \
                --port "$BACKEND_PORT" \
                >"$BACKEND_LOG" 2>&1 &
            echo "$!" >"$BACKEND_PID_FILE"
        )
    fi
    if ! wait_for_url "后端" "http://127.0.0.1:$BACKEND_PORT/health" "$BACKEND_PID_FILE" "$BACKEND_LOG"; then
        stop_services
        exit 1
    fi

    if ! is_running "$FRONTEND_PID_FILE"; then
        (
            cd "$PROJECT_ROOT/web"
            nohup "$PROJECT_ROOT/web/node_modules/.bin/vite" \
                --host 0.0.0.0 \
                --port "$FRONTEND_PORT" \
                --strictPort \
                >"$FRONTEND_LOG" 2>&1 &
            echo "$!" >"$FRONTEND_PID_FILE"
        )
    fi
    if ! wait_for_url "前端" "http://127.0.0.1:$FRONTEND_PORT" "$FRONTEND_PID_FILE" "$FRONTEND_LOG"; then
        stop_services
        exit 1
    fi

    echo "QuantStone Data 已启动。"
    echo "本机前端：http://127.0.0.1:$FRONTEND_PORT"
    echo "后端接口：http://127.0.0.1:$BACKEND_PORT/docs"
    print_access_urls
}

stop_process() {
    local name="$1"
    local pid_file="$2"
    if ! is_running "$pid_file"; then
        rm -f "$pid_file"
        echo "$name 未运行。"
        return
    fi
    local pid
    pid="$(<"$pid_file")"
    kill "$pid"
    for _ in {1..25}; do
        if ! kill -0 "$pid" 2>/dev/null; then
            rm -f "$pid_file"
            echo "$name 已停止。"
            return
        fi
        sleep 0.2
    done
    kill -KILL "$pid" 2>/dev/null || true
    rm -f "$pid_file"
    echo "$name 已强制停止。"
}

stop_services() {
    stop_process "前端" "$FRONTEND_PID_FILE"
    stop_process "后端" "$BACKEND_PID_FILE"
}

show_status() {
    if is_running "$BACKEND_PID_FILE"; then
        echo "后端：运行中，PID $(<"$BACKEND_PID_FILE")，端口 $BACKEND_PORT"
    else
        echo "后端：未运行"
    fi
    if is_running "$FRONTEND_PID_FILE"; then
        echo "前端：运行中，PID $(<"$FRONTEND_PID_FILE")，端口 $FRONTEND_PORT"
        print_access_urls
    else
        echo "前端：未运行"
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
