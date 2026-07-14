#!/bin/bash
# ============================================================
# 销售情报系统服务 - 持久化启动脚本
# 用法:
#   ./start_server.sh start [all|web|mobile]
#   ./start_server.sh stop [all|web|mobile]
#   ./start_server.sh restart [all|web|mobile]
#   ./start_server.sh status [all|web|mobile]
#   ./start_server.sh log [web|mobile|all]
# ============================================================

# ---------- 配置区 ----------
PROJECT_DIR="/home/sylincom/sales-agent/get_data"
WEB_APP_ENTRY="webapp.server_fastapi:app"
MOBILE_APP_ENTRY="mobileapp.server_mobile:app"
HOST="0.0.0.0"
WEB_PORT=8103
MOBILE_PORT=8104
WORKERS=1
LOG_DIR="${PROJECT_DIR}/logs/api_server"
WEB_PID_FILE="${LOG_DIR}/server_fastapi.pid"
MOBILE_PID_FILE="${LOG_DIR}/server_mobile.pid"
WEB_LOG_FILE="${LOG_DIR}/server_fastapi_stdout.log"
MOBILE_LOG_FILE="${LOG_DIR}/server_mobile_stdout.log"

# Python 解释器（优先使用虚拟环境）
if [ -d "${PROJECT_DIR}/../venv" ]; then
    PYTHON="${PROJECT_DIR}/../venv/bin/python"
    UVICORN="${PROJECT_DIR}/../venv/bin/uvicorn"
elif [ -d "${PROJECT_DIR}/venv" ]; then
    PYTHON="${PROJECT_DIR}/venv/bin/python"
    UVICORN="${PROJECT_DIR}/venv/bin/uvicorn"
elif [ -d "${PROJECT_DIR}/.venv" ]; then
    PYTHON="${PROJECT_DIR}/.venv/bin/python"
    UVICORN="${PROJECT_DIR}/.venv/bin/uvicorn"
else
    PYTHON=$(which python3)
    UVICORN=$(which uvicorn)
fi

# ---------- 工具函数 ----------
ensure_dirs() {
    mkdir -p "${LOG_DIR}"
}

get_pid() {
    local pid_file="$1"
    if [ -f "${pid_file}" ]; then
        cat "${pid_file}"
    fi
}

is_running() {
    local pid_file="$1"
    local pid
    pid=$(get_pid "${pid_file}")
    if [ -n "${pid}" ] && kill -0 "${pid}" 2>/dev/null; then
        return 0
    fi
    return 1
}

wait_for_stop() {
    local name="$1"
    local pid_file="$2"
    local timeout=30
    local count=0
    while is_running "${pid_file}" && [ ${count} -lt ${timeout} ]; do
        sleep 1
        count=$((count + 1))
    done
    if is_running "${pid_file}"; then
        echo "[ERROR] ${name} 未能正常停止，强制终止..."
        kill -9 "$(get_pid "${pid_file}")" 2>/dev/null
        rm -f "${pid_file}"
    fi
}

# ---------- 命令实现 ----------
start_service() {
    local name="$1"
    local app_entry="$2"
    local port="$3"
    local pid_file="$4"
    local log_file="$5"
    local page_url="$6"
    local docs_url="$7"

    ensure_dirs

    if is_running "${pid_file}"; then
        echo "[WARN] ${name} 已在运行中 (PID: $(get_pid "${pid_file}"))"
        return 0
    fi

    if [ -z "${UVICORN}" ]; then
        echo "[ERROR] 未找到 uvicorn，请先安装依赖"
        return 1
    fi

    echo "[INFO] 正在启动 ${name}..."
    echo "[INFO] Python:  ${PYTHON}"
    echo "[INFO] Uvicorn: ${UVICORN}"
    echo "[INFO] 监听:    ${HOST}:${port}"
    echo "[INFO] 日志:    ${log_file}"

    cd "${PROJECT_DIR}" || return 1

    setsid nohup "${UVICORN}" "${app_entry}" \
        --host "${HOST}" \
        --port "${port}" \
        --workers ${WORKERS} \
        --log-level info \
        >> "${log_file}" 2>&1 < /dev/null &

    local pid=$!
    echo "${pid}" > "${pid_file}"

    sleep 3
    if is_running "${pid_file}"; then
        echo "[OK] ${name} 启动成功 (PID: ${pid})"
        echo "[OK] 访问地址: ${page_url}"
        if [ -n "${docs_url}" ]; then
            echo "[OK] API 文档:  ${docs_url}"
        fi
        return 0
    fi

    echo "[ERROR] ${name} 启动失败，请检查日志: ${log_file}"
    rm -f "${pid_file}"
    return 1
}

stop_service() {
    local name="$1"
    local pid_file="$2"

    if ! is_running "${pid_file}"; then
        echo "[WARN] ${name} 未在运行"
        rm -f "${pid_file}"
        return 0
    fi

    local pid
    pid=$(get_pid "${pid_file}")
    echo "[INFO] 正在停止 ${name} (PID: ${pid})..."
    kill -TERM "${pid}" 2>/dev/null
    wait_for_stop "${name}" "${pid_file}"

    if ! is_running "${pid_file}"; then
        echo "[OK] ${name} 已停止"
        rm -f "${pid_file}"
        return 0
    fi

    echo "[ERROR] ${name} 停止失败"
    return 1
}

status_service() {
    local name="$1"
    local port="$2"
    local pid_file="$3"
    local log_file="$4"

    if is_running "${pid_file}"; then
        local pid
        pid=$(get_pid "${pid_file}")
        echo "[OK] ${name} 运行中 (PID: ${pid})"
        echo "     监听: ${HOST}:${port}"
        echo "     日志: ${log_file}"

        if curl -s "http://127.0.0.1:${port}/" > /dev/null 2>&1; then
            echo "     状态: 正常响应"
        else
            echo "     状态: 端口未响应（可能正在启动中）"
        fi
    else
        echo "[INFO] ${name} 未运行"
        if [ -f "${pid_file}" ]; then
            echo "     存在残留 PID 文件: ${pid_file}"
        fi
    fi
}

start_web() {
    start_service \
        "Web 端服务" \
        "${WEB_APP_ENTRY}" \
        "${WEB_PORT}" \
        "${WEB_PID_FILE}" \
        "${WEB_LOG_FILE}" \
        "http://127.0.0.1:${WEB_PORT}/static/demo.html" \
        "http://127.0.0.1:${WEB_PORT}/docs"
}

start_mobile() {
    start_service \
        "手机端服务" \
        "${MOBILE_APP_ENTRY}" \
        "${MOBILE_PORT}" \
        "${MOBILE_PID_FILE}" \
        "${MOBILE_LOG_FILE}" \
        "http://127.0.0.1:${MOBILE_PORT}/" \
        ""
}

start_all() {
    start_web
    local web_code=$?
    start_mobile
    local mobile_code=$?
    if [ ${web_code} -ne 0 ] || [ ${mobile_code} -ne 0 ]; then
        return 1
    fi
}

stop_web() {
    stop_service "Web 端服务" "${WEB_PID_FILE}"
}

stop_mobile() {
    stop_service "手机端服务" "${MOBILE_PID_FILE}"
}

stop_all() {
    stop_mobile
    local mobile_code=$?
    stop_web
    local web_code=$?
    if [ ${web_code} -ne 0 ] || [ ${mobile_code} -ne 0 ]; then
        return 1
    fi
}

restart_target() {
    local target="$1"
    stop_target "${target}"
    sleep 2
    start_target "${target}"
}

status_all() {
    status_service "Web 端服务" "${WEB_PORT}" "${WEB_PID_FILE}" "${WEB_LOG_FILE}"
    status_service "手机端服务" "${MOBILE_PORT}" "${MOBILE_PID_FILE}" "${MOBILE_LOG_FILE}"
}

start_target() {
    case "$1" in
        all|"") start_all ;;
        web) start_web ;;
        mobile) start_mobile ;;
        *) usage; return 1 ;;
    esac
}

stop_target() {
    case "$1" in
        all|"") stop_all ;;
        web) stop_web ;;
        mobile) stop_mobile ;;
        *) usage; return 1 ;;
    esac
}

status_target() {
    case "$1" in
        all|"") status_all ;;
        web) status_service "Web 端服务" "${WEB_PORT}" "${WEB_PID_FILE}" "${WEB_LOG_FILE}" ;;
        mobile) status_service "手机端服务" "${MOBILE_PORT}" "${MOBILE_PID_FILE}" "${MOBILE_LOG_FILE}" ;;
        *) usage; return 1 ;;
    esac
}

log_target() {
    case "$1" in
        all|"") tail -f "${WEB_LOG_FILE}" "${MOBILE_LOG_FILE}" ;;
        web) tail -f "${WEB_LOG_FILE}" ;;
        mobile) tail -f "${MOBILE_LOG_FILE}" ;;
        *) usage; return 1 ;;
    esac
}

usage() {
    echo "用法: $0 {start|stop|restart|status|log} [all|web|mobile]"
}

# ---------- 主入口 ----------
command="$1"
target="${2:-all}"

case "${command}" in
    start) start_target "${target}" ;;
    stop) stop_target "${target}" ;;
    restart) restart_target "${target}" ;;
    status) status_target "${target}" ;;
    log) log_target "${target}" ;;
    *)
        usage
        exit 1
        ;;
esac
