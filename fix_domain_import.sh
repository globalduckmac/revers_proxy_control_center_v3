#!/bin/bash

# Скрипт для исправления ошибки с импортом routes.domain
# Копировать на сервер и запустить с правами root

# Путь к приложению
APP_DIR="/opt/reverse_proxy_control_center"

# Функция для вывода цветного текста
print_info() {
    echo -e "\033[0;32m[INFO]\033[0m $1"
}

print_error() {
    echo -e "\033[0;31m[ERROR]\033[0m $1"
}

print_info "Начинаем исправление ошибки импорта routes.domain"

# Проверяем наличие файла app.py
if [ ! -f "$APP_DIR/app.py" ]; then
    print_error "Файл app.py не найден в $APP_DIR"
    exit 1
fi

# Создаем резервную копию
cp "$APP_DIR/app.py" "$APP_DIR/app.py.backup_$(date +%Y%m%d_%H%M%S)"
print_info "Создана резервная копия app.py"

# Получаем содержимое всего файла register_blueprints и находим неверный импорт
REGISTER_FUNCTION=$(grep -A 25 "def register_blueprints" "$APP_DIR/app.py")
print_info "Текущее содержание функции register_blueprints:"
echo "$REGISTER_FUNCTION"

# Исправляем ошибку импорта (если domain -> domains, и если точно так)
sed -i 's/from routes\.domain import/from routes.domains import/g' "$APP_DIR/app.py"
print_info "Исправлен импорт routes.domain на routes.domains в app.py"

# Проверяем, что изменения применились
FIXED_FUNCTION=$(grep -A 25 "def register_blueprints" "$APP_DIR/app.py")
print_info "Исправленное содержание функции register_blueprints:"
echo "$FIXED_FUNCTION"

# Перезапускаем сервис
print_info "Перезапускаем сервис"
systemctl restart reverse_proxy_control_center

# Проверяем статус сервиса после перезапуска
sleep 3
STATUS=$(systemctl is-active reverse_proxy_control_center)
if [ "$STATUS" = "active" ]; then
    print_info "Сервис успешно запущен!"
else
    print_error "Сервис не запустился. Статус: $STATUS"
    print_info "Проверьте логи: journalctl -u reverse_proxy_control_center -n 50"
fi

print_info "Сценарий исправления завершен"
