#!/bin/bash

# Скрипт для исправления импортов в app.py
# Заменяет import routes.domain на import routes.domains
# и import routes.server на import routes.servers

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

# Путь к файлу
APP_FILE="app.py"

if [ ! -f "$APP_FILE" ]; then
    error "Файл $APP_FILE не найден"
    exit 1
fi

info "Создаем резервную копию $APP_FILE..."
cp "$APP_FILE" "${APP_FILE}.bak"

info "Исправляем импорты..."
sed -i 's/import routes\.domain/import routes.domains/g' "$APP_FILE"
sed -i 's/from routes\.domain import/from routes.domains import/g' "$APP_FILE"
sed -i 's/routes\.domain\./routes.domains./g' "$APP_FILE"

sed -i 's/import routes\.server/import routes.servers/g' "$APP_FILE"
sed -i 's/from routes\.server import/from routes.servers import/g' "$APP_FILE"
sed -i 's/routes\.server\./routes.servers./g' "$APP_FILE"

info "Проверка результата..."
if grep -q "routes\.domain" "$APP_FILE" || grep -q "routes\.server" "$APP_FILE"; then
    warn "Некоторые импорты могли остаться неисправленными. Проверьте файл вручную."
else
    info "Все импорты успешно исправлены!"
fi

info "Готово! Файл обновлен."
