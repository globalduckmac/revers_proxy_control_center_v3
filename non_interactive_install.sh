#!/bin/bash

# Неинтерактивный скрипт установки для Reverse Proxy Control Center v3
# Для запуска: wget -O - https://raw.githubusercontent.com/globalduckmac/revers_proxy_control_center_v3/main/non_interactive_install.sh | sudo bash
# Или можно использовать параметр для указания действия:
# wget -O - https://raw.githubusercontent.com/globalduckmac/revers_proxy_control_center_v3/main/non_interactive_install.sh | sudo bash -s -- --action=update
# Возможные действия: update, reinstall, uninstall

# Цвета для вывода
GREEN='\033[0;32m'
YELLOW='\033[0;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color

# Обработка параметров командной строки
ACTION="reinstall"  # Действие по умолчанию - переустановка
for i in "$@"; do
  case $i in
    --action=*)
      ACTION="${i#*=}"
      shift
      ;;
    *)
      # Неизвестный параметр
      echo -e "${YELLOW}[ВНИМАНИЕ]${NC} Неизвестный параметр: $i"
      ;;
  esac
done

echo -e "${GREEN}=== Неинтерактивная установка Reverse Proxy Control Center v3 ===${NC}"
echo -e "${GREEN}[INFO]${NC} Выбранное действие: $ACTION"

# Проверяем, запущен ли скрипт с правами root
if [ "$(id -u)" != "0" ]; then
    echo -e "${RED}[ОШИБКА]${NC} Этот скрипт должен быть запущен с правами root."
    echo "Используйте: sudo bash $0"
    exit 1
fi

# Проверяем наличие необходимых утилит
echo -e "${GREEN}[INFO]${NC} Проверка наличия необходимых утилит..."
for cmd in wget git curl apt-get; do
    if ! command -v $cmd &> /dev/null; then
        echo -e "${YELLOW}[ВНИМАНИЕ]${NC} $cmd не найден, устанавливаем..."
        apt-get update
        apt-get install -y $cmd
    fi
done

# Создаем временную директорию
TEMP_DIR=$(mktemp -d)
cd $TEMP_DIR

# Настраиваем Git для обхода проблемы с dubious ownership
echo -e "${GREEN}[INFO]${NC} Настройка Git для безопасной работы с репозиторием..."
git config --global --add safe.directory "$(pwd)"
git config --global --add safe.directory "/opt/reverse_proxy_control_center"

# Проверяем, есть ли уже установленное приложение
if [ -d "/opt/reverse_proxy_control_center" ]; then
    echo -e "${YELLOW}[ВНИМАНИЕ]${NC} Существующая установка обнаружена в /opt/reverse_proxy_control_center."
    
    case "$ACTION" in
        update)
            echo -e "${GREEN}[INFO]${NC} Обновление существующей установки..."
            ;;
        reinstall|force)
            echo -e "${YELLOW}[ВНИМАНИЕ]${NC} Удаление существующей установки..."
            systemctl stop reverse_proxy_control_center 2>/dev/null || true
            systemctl disable reverse_proxy_control_center 2>/dev/null || true
            rm -rf /opt/reverse_proxy_control_center
            rm -f /etc/systemd/system/reverse_proxy_control_center.service
            rm -rf /etc/systemd/system/reverse_proxy_control_center.service.d
            systemctl daemon-reload
            echo -e "${GREEN}[INFO]${NC} Существующая установка удалена."
            ;;
        uninstall)
            echo -e "${YELLOW}[ВНИМАНИЕ]${NC} Удаление существующей установки..."
            systemctl stop reverse_proxy_control_center 2>/dev/null || true
            systemctl disable reverse_proxy_control_center 2>/dev/null || true
            rm -rf /opt/reverse_proxy_control_center
            rm -f /etc/systemd/system/reverse_proxy_control_center.service
            rm -rf /etc/systemd/system/reverse_proxy_control_center.service.d
            rm -f /etc/nginx/sites-available/reverse_proxy_control_center
            rm -f /etc/nginx/sites-enabled/reverse_proxy_control_center
            systemctl daemon-reload
            systemctl restart nginx
            echo -e "${GREEN}[INFO]${NC} Установка полностью удалена."
            echo -e "${GREEN}[ГОТОВО]${NC} Удаление завершено."
            exit 0
            ;;
        *)
            echo -e "${RED}[ОШИБКА]${NC} Неизвестное действие: $ACTION"
            echo -e "Допустимые действия: update, reinstall, uninstall"
            exit 1
            ;;
    esac
fi

# Клонируем репозиторий
echo -e "${GREEN}[INFO]${NC} Загрузка установщика..."
git clone https://github.com/globalduckmac/revers_proxy_control_center_v3.git
cd revers_proxy_control_center_v3

# Добавляем директорию репозитория в безопасные
git config --global --add safe.directory "$(pwd)"

# Запускаем установщик
echo -e "${GREEN}[INFO]${NC} Запуск установщика..."
chmod +x install_v2.sh
./install_v2.sh

# Проверка статуса установки
echo -e "${GREEN}[INFO]${NC} Проверка статуса установки..."
sleep 3

# Проверка доступности системных сервисов
echo -e "\n${GREEN}[ПРОВЕРКА]${NC} Проверка состояния сервисов..."
systemctl is-active --quiet postgresql && echo -e "PostgreSQL: ${GREEN}активен${NC}" || echo -e "PostgreSQL: ${RED}не активен${NC}"
systemctl is-active --quiet nginx && echo -e "Nginx: ${GREEN}активен${NC}" || echo -e "Nginx: ${RED}не активен${NC}"
systemctl is-active --quiet reverse_proxy_control_center && echo -e "RPCC: ${GREEN}активен${NC}" || echo -e "RPCC: ${RED}не активен${NC}"

# Проверка сетевой доступности
echo -e "\n${GREEN}[ПРОВЕРКА]${NC} Проверка сетевых портов..."
nc -z -v -w1 localhost 5000 >/dev/null 2>&1 && echo -e "Порт 5000 (Gunicorn): ${GREEN}открыт${NC}" || echo -e "Порт 5000 (Gunicorn): ${RED}закрыт${NC}"
nc -z -v -w1 localhost 80 >/dev/null 2>&1 && echo -e "Порт 80 (Nginx): ${GREEN}открыт${NC}" || echo -e "Порт 80 (Nginx): ${RED}закрыт${NC}"
nc -z -v -w1 localhost 5432 >/dev/null 2>&1 && echo -e "Порт 5432 (PostgreSQL): ${GREEN}открыт${NC}" || echo -e "Порт 5432 (PostgreSQL): ${RED}закрыт${NC}"

echo -e "\n${GREEN}[СОВЕТ]${NC} Если у вас возникли проблемы с доступом к веб-интерфейсу, выполните команду:"
echo -e "  sudo rpcc-diagnose"
echo -e "Эта команда предоставит подробную информацию о состоянии системы и возможных проблемах.\n"

# Чистим за собой
cd /
rm -rf $TEMP_DIR

echo -e "${GREEN}[ГОТОВО]${NC} Установка завершена! Если у вас возникли проблемы, обратитесь к документации или выполните диагностику с помощью команды 'sudo rpcc-diagnose'."