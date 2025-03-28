#!/bin/bash

# Скрипт для настройки базы данных и исправления подключения
# Создает пользователя и базу данных PostgreSQL
# Обновляет config.py и файл сервиса

# Цвета для вывода
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color

# Функции для вывода
info() {
    echo -e "${GREEN}[INFO]${NC} $1"
}

warn() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

DB_NAME="rpcc"
DB_USER="rpcc"
DB_PASSWORD=$(openssl rand -base64 12 | tr -dc 'a-zA-Z0-9')

info "Проверка и настройка базы данных PostgreSQL..."

# Проверяем статус PostgreSQL
if ! systemctl is-active --quiet postgresql; then
    info "PostgreSQL не запущен, запускаем..."
    systemctl start postgresql
    sleep 2
fi

# Проверяем существование пользователя и базы
info "Проверка пользователя и базы данных..."
if sudo -u postgres psql -tAc "SELECT 1 FROM pg_roles WHERE rolname='$DB_USER'" | grep -q 1; then
    info "Пользователь '$DB_USER' уже существует"
else
    info "Создаем пользователя '$DB_USER'..."
    sudo -u postgres psql -c "CREATE USER $DB_USER WITH PASSWORD '$DB_PASSWORD';"
fi

if sudo -u postgres psql -tAc "SELECT 1 FROM pg_database WHERE datname='$DB_NAME'" | grep -q 1; then
    info "База данных '$DB_NAME' уже существует"
else
    info "Создаем базу данных '$DB_NAME'..."
    sudo -u postgres psql -c "CREATE DATABASE $DB_NAME OWNER $DB_USER;"
fi

# Обновляем config.py чтобы использовать правильную строку подключения
info "Обновляем config.py для использования PostgreSQL..."
CONFIG_FILE="config.py"
if [ -f "$CONFIG_FILE" ]; then
    # Создаем резервную копию
    cp "$CONFIG_FILE" "${CONFIG_FILE}.backup"
    
    # Обновляем строку подключения к базе данных
    if grep -q "SQLALCHEMY_DATABASE_URI" "$CONFIG_FILE"; then
        # Заменяем строку подключения
        sed -i "s|SQLALCHEMY_DATABASE_URI = .*|SQLALCHEMY_DATABASE_URI = os.environ.get('DATABASE_URL', 'postgresql://$DB_USER:$DB_PASSWORD@localhost/$DB_NAME')|g" "$CONFIG_FILE"
        info "Строка подключения к базе данных обновлена в config.py"
    else
        warn "Строка SQLALCHEMY_DATABASE_URI не найдена в config.py"
    fi
else
    error "Файл config.py не найден!"
fi

# Создаем или обновляем файл сервиса
info "Обновляем файл сервиса с переменными окружения..."
SERVICE_FILE="reverse_proxy_control_center.service"

cat > "$SERVICE_FILE" << EOF
[Unit]
Description=Reverse Proxy Control Center v3
After=network.target postgresql.service

[Service]
User=www-data
Group=www-data
WorkingDirectory=/opt/reverse_proxy_control_center
Environment="DATABASE_URL=postgresql://$DB_USER:$DB_PASSWORD@localhost/$DB_NAME"
Environment="SESSION_SECRET=$(openssl rand -hex 32)"
ExecStartPre=/bin/sleep 2
ExecStart=/opt/reverse_proxy_control_center/venv/bin/gunicorn --workers 2 --bind 0.0.0.0:5000 --timeout 120 --access-logfile /var/log/reverse_proxy_control_center/access.log --error-logfile /var/log/reverse_proxy_control_center/error.log main:app
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
