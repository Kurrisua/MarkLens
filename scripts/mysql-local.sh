#!/usr/bin/env bash

set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
MYSQL_HOME="${MYSQL_HOME:-/opt/homebrew/opt/mysql@8.4}"
MYSQL_PORT="${MYSQL_PORT:-3307}"
MYSQL_DATA_DIR="${MYSQL_DATA_DIR:-${ROOT_DIR}/data/mysql84-instance}"
MYSQL_SOCKET="${MYSQL_SOCKET:-/tmp/marklens-mysql.sock}"
MYSQL_PID_FILE="${MYSQL_PID_FILE:-/tmp/marklens-mysql.pid}"
MYSQL_LABEL="${MYSQL_LABEL:-com.marklens.mysql84}"
MYSQL_LOG="${MYSQL_DATA_DIR}/marklens.err"

MYSQL="${MYSQL_HOME}/bin/mysql"
MYSQLADMIN="${MYSQL_HOME}/bin/mysqladmin"
MYSQLD="${MYSQL_HOME}/bin/mysqld"

require_mysql() {
  if [[ ! -x "${MYSQLD}" ]]; then
    echo "未找到 MySQL 8.4。请先执行：brew install mysql@8.4" >&2
    exit 1
  fi
}

is_ready() {
  MYSQL_PWD=marklens "${MYSQLADMIN}" \
    --connect-timeout=2 \
    --protocol=TCP \
    --host=127.0.0.1 \
    --port="${MYSQL_PORT}" \
    --user=marklens \
    ping >/dev/null 2>&1
}

wait_for_exit() {
  for _ in {1..30}; do
    if [[ ! -f "${MYSQL_PID_FILE}" ]]; then
      return
    fi

    local pid
    pid="$(<"${MYSQL_PID_FILE}")"
    if [[ -z "${pid}" ]] || ! kill -0 "${pid}" >/dev/null 2>&1; then
      return
    fi
    sleep 1
  done

  echo "旧 MySQL 进程未能在 30 秒内退出" >&2
  exit 1
}

initialize() {
  if [[ -d "${MYSQL_DATA_DIR}/mysql" ]]; then
    return
  fi

  mkdir -p "${MYSQL_DATA_DIR}"
  "${MYSQLD}" \
    --no-defaults \
    --initialize-insecure \
    --basedir="${MYSQL_HOME}" \
    --datadir="${MYSQL_DATA_DIR}"
}

provision() {
  "${MYSQL}" \
    --protocol=TCP \
    --host=127.0.0.1 \
    --port="${MYSQL_PORT}" \
    --user=root <<'SQL'
CREATE DATABASE IF NOT EXISTS marklens
  CHARACTER SET utf8mb4
  COLLATE utf8mb4_0900_ai_ci;
CREATE USER IF NOT EXISTS 'marklens'@'localhost' IDENTIFIED BY 'marklens';
ALTER USER 'marklens'@'localhost' IDENTIFIED BY 'marklens';
GRANT ALL PRIVILEGES ON marklens.* TO 'marklens'@'localhost';
FLUSH PRIVILEGES;
SQL
}

start() {
  require_mysql
  if is_ready; then
    echo "MarkLens MySQL 已运行：127.0.0.1:${MYSQL_PORT}"
    return
  fi

  initialize
  launchctl remove "${MYSQL_LABEL}" >/dev/null 2>&1 || true
  wait_for_exit
  launchctl submit -l "${MYSQL_LABEL}" -- \
    "${MYSQLD}" \
    --no-defaults \
    --basedir="${MYSQL_HOME}" \
    --datadir="${MYSQL_DATA_DIR}" \
    --bind-address=127.0.0.1 \
    --port="${MYSQL_PORT}" \
    --socket="${MYSQL_SOCKET}" \
    --pid-file="${MYSQL_PID_FILE}" \
    --log-error="${MYSQL_LOG}" \
    --mysqlx=0

  for _ in {1..30}; do
    if "${MYSQLADMIN}" \
      --connect-timeout=1 \
      --protocol=TCP \
      --host=127.0.0.1 \
      --port="${MYSQL_PORT}" \
      --user=root \
      ping >/dev/null 2>&1; then
      provision
      echo "MarkLens MySQL 已启动：127.0.0.1:${MYSQL_PORT}"
      return
    fi
    sleep 1
  done

  echo "MySQL 启动超时，请检查 ${MYSQL_LOG}" >&2
  exit 1
}

stop() {
  launchctl remove "${MYSQL_LABEL}" >/dev/null 2>&1 || true
  wait_for_exit
  echo "MarkLens MySQL 已停止"
}

status() {
  require_mysql
  if is_ready; then
    MYSQL_PWD=marklens "${MYSQL}" \
      --protocol=TCP \
      --host=127.0.0.1 \
      --port="${MYSQL_PORT}" \
      --user=marklens \
      --batch \
      --skip-column-names \
      --execute='SELECT CONCAT("MarkLens MySQL ", VERSION(), " 已就绪，数据库时间：", NOW());'
  else
    echo "MarkLens MySQL 未运行"
    exit 1
  fi
}

case "${1:-start}" in
  start) start ;;
  stop) stop ;;
  restart) stop; start ;;
  status) status ;;
  *)
    echo "用法：$0 {start|stop|restart|status}" >&2
    exit 2
    ;;
esac
