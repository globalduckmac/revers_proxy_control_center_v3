#!/bin/bash

# Одностраничный скрипт для быстрой установки Reverse Proxy Control Center v3
# Для запуска: wget -O - https://raw.githubusercontent.com/globalduckmac/revers_proxy_control_center_v3/main/quick_install_v2.sh | sudo bash

# Цвета для вывода
GREEN='\033[0;32m'
YELLOW='\033[0;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color

echo -e "${GREEN}=== Быстрая установка Reverse Proxy Control Center v3 ===${NC}"

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
    echo -e "Выберите действие:"
    echo -e "1. Обновить существующую установку"
    echo -e "2. Удалить существующую установку и установить заново"
    echo -e "3. Отменить установку"
    
    read -p "Введите ваш выбор (1-3): " choice
    
    case "$choice" in
        1)
            echo -e "${GREEN}[INFO]${NC} Обновление существующей установки..."
            ;;
        2)
            echo -e "${YELLOW}[ВНИМАНИЕ]${NC} Удаление существующей установки..."
            systemctl stop reverse_proxy_control_center 2>/dev/null || true
            systemctl disable reverse_proxy_control_center 2>/dev/null || true
            rm -rf /opt/reverse_proxy_control_center
            rm -f /etc/systemd/system/reverse_proxy_control_center.service
            rm -rf /etc/systemd/system/reverse_proxy_control_center.service.d
            systemctl daemon-reload
            echo -e "${GREEN}[INFO]${NC} Существующая установка удалена."
            ;;
        3)
            echo -e "${YELLOW}[INFO]${NC} Установка отменена по запросу пользователя."
            exit 0
            ;;
        *)
            echo -e "${RED}[ОШИБКА]${NC} Неверный выбор. Выход."
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

# Создаем исполняемый файл установки v2
echo -e "${GREEN}[INFO]${NC} Создание нового установщика..."
cat > install_v2.sh <<'EOL'
#!/bin/bash

# Автоматический скрипт развертывания для Reverse Proxy Control Center v3
# Этот скрипт устанавливает все зависимости и настраивает приложение на Ubuntu

# Выход при любой ошибке
set -e

# Цвета для вывода
GREEN='\033[0;32m'
YELLOW='\033[0;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color

# Функция для вывода заголовков
print_header() {
    echo -e "\n${GREEN}=== $1 ===${NC}"
}

# Функция для вывода предупреждений
print_warning() {
    echo -e "${YELLOW}ВНИМАНИЕ: $1${NC}"
}

# Функция для вывода ошибок
print_error() {
    echo -e "${RED}ОШИБКА: $1${NC}"
}

# Обработка ошибок
handle_error() {
    print_error "Произошла ошибка при выполнении: $1"
    print_error "Строка: $2"
    exit 1
}

# Настраиваем перехват ошибок
trap 'handle_error "$BASH_COMMAND" "$LINENO"' ERR

# Начало установки
print_header "Начало развертывания Reverse Proxy Control Center v3"

# Создаем каталог для приложения
APP_DIR="/opt/reverse_proxy_control_center"
VENV_DIR="$APP_DIR/venv"
LOG_DIR="/var/log/reverse_proxy_control_center"
print_header "Создание каталога приложения в $APP_DIR"
sudo mkdir -p "$APP_DIR"
sudo mkdir -p "$LOG_DIR"
sudo chown $USER:$USER "$APP_DIR"
sudo chown $USER:$USER "$LOG_DIR"

# Настройка Git для безопасной работы с репозиторием
print_header "Настройка Git для безопасной работы с репозиторием"
git config --global --add safe.directory "$APP_DIR"
git config --global --add safe.directory "$(pwd)"

# Получение исходного кода
print_header "Клонирование репозитория из GitHub"
if [ ! -d "$APP_DIR/.git" ]; then
    git clone https://github.com/globalduckmac/revers_proxy_control_center_v3.git "$APP_DIR"
    cd "$APP_DIR"
else
    cd "$APP_DIR"
    # Добавляем директорию в безопасные перед использованием git pull
    git config --global --add safe.directory "$APP_DIR"
    git pull
fi

# Обновление системных пакетов
print_header "Обновление системных пакетов"
sudo apt-get update
sudo apt-get upgrade -y

# Установка необходимых системных пакетов
print_header "Установка системных зависимостей"
sudo apt-get install -y python3 python3-pip python3-venv nginx postgresql postgresql-contrib git curl net-tools lsof jq certbot python3-certbot-nginx

# Генерация случайных паролей
DB_PASSWORD=$(openssl rand -hex 8)
SESSION_SECRET=$(openssl rand -hex 16)
ADMIN_PASSWORD=$(openssl rand -hex 8)
SERVER_IP=$(hostname -I | awk '{print $1}')

# Настройка PostgreSQL
print_header "Настройка PostgreSQL"
if ! sudo -u postgres psql -tAc "SELECT 1 FROM pg_database WHERE datname='rpcc'" | grep -q 1; then
    # Создаем пользователя и базу данных PostgreSQL
    sudo -u postgres psql -c "CREATE USER rpcc WITH PASSWORD '$DB_PASSWORD';"
    sudo -u postgres psql -c "CREATE DATABASE rpcc WITH OWNER rpcc;"
    sudo -u postgres psql -c "GRANT ALL PRIVILEGES ON DATABASE rpcc TO rpcc;"
    sudo -u postgres psql -c "ALTER ROLE rpcc SET client_encoding TO 'utf8';"
    sudo -u postgres psql -c "ALTER ROLE rpcc SET default_transaction_isolation TO 'read committed';"
    sudo -u postgres psql -c "ALTER ROLE rpcc SET timezone TO 'UTC';"
    echo "База данных PostgreSQL и пользователь созданы"
else
    echo "База данных уже существует, обновляем пароль пользователя"
    sudo -u postgres psql -c "ALTER USER rpcc WITH PASSWORD '$DB_PASSWORD';"
fi

# Настройка Python-окружения
print_header "Настройка Python-окружения"
cd "$APP_DIR"
python3 -m venv venv
source venv/bin/activate

# Установка Python-зависимостей
print_header "Установка Python-зависимостей"
pip install --upgrade pip setuptools wheel
pip install psycopg2-binary cryptography dnspython email-validator flask flask-login flask-sqlalchemy flask-wtf "glances[web]<=5.0" gunicorn jinja2 paramiko python-telegram-bot pytz requests sqlalchemy werkzeug pymysql

# Конфигурация приложения
print_header "Настройка конфигурации приложения"
cat > "$APP_DIR/.env" <<EOF
# Настройки окружения для Reverse Proxy Control Center v3
FLASK_APP=main.py
FLASK_ENV=production
FLASK_CONFIG=production
SESSION_SECRET=$SESSION_SECRET
DATABASE_URL=postgresql://rpcc:$DB_PASSWORD@localhost/rpcc

# Настройки SSH
SSH_TIMEOUT=60
SSH_COMMAND_TIMEOUT=300

# Настройки электронной почты для SSL сертификатов
ADMIN_EMAIL=admin@example.com

# Настройки Telegram (необязательно)
# TELEGRAM_BOT_TOKEN=your_bot_token
# TELEGRAM_CHAT_ID=your_chat_id

# Настройки FFPanel (необязательно)
# FFPANEL_TOKEN=your_ffpanel_token

# Настройки GitHub (необязательно)
# GITHUB_TOKEN=your_github_token
EOF

# Создание systemd сервиса
print_header "Создание systemd сервиса"
sudo tee /etc/systemd/system/reverse_proxy_control_center.service > /dev/null <<EOF
[Unit]
Description=Reverse Proxy Control Center v3
After=network.target postgresql.service

[Service]
User=$USER
WorkingDirectory=$APP_DIR
ExecStart=$VENV_DIR/bin/gunicorn --workers 4 --bind 0.0.0.0:5000 --timeout 120 --access-logfile $LOG_DIR/access.log --error-logfile $LOG_DIR/error.log main:app
Restart=always
RestartSec=5
Environment="PATH=$VENV_DIR/bin"
Environment="SESSION_SECRET=$SESSION_SECRET"
Environment="DATABASE_URL=postgresql://rpcc:$DB_PASSWORD@localhost/rpcc"

[Install]
WantedBy=multi-user.target
EOF

# Создаем директорию для переопределений systemd
sudo mkdir -p /etc/systemd/system/reverse_proxy_control_center.service.d/
sudo tee /etc/systemd/system/reverse_proxy_control_center.service.d/override.conf > /dev/null <<EOF
[Service]
# Увеличиваем лимиты
LimitNOFILE=65536
# Добавляем задержку перед запуском для уверенности, что PostgreSQL полностью готов
ExecStartPre=/bin/sleep 2
EOF

# Создание скрипта для инициализации базы данных и администратора
print_header "Создание скрипта инициализации"
cat > "$APP_DIR/init_db.py" <<EOF
from app import app, db
from models import User
from werkzeug.security import generate_password_hash
import sys

def init_db():
    """Инициализация базы данных"""
    with app.app_context():
        # Создаем таблицы
        db.create_all()
        print("База данных инициализирована")
        return True

def create_admin():
    """Создание администратора если его нет"""
    with app.app_context():
        # Проверяем, существует ли пользователь admin
        admin = User.query.filter_by(username='admin').first()
        
        if admin:
            print("Администратор уже существует. Обновляем пароль...")
            admin.password_hash = generate_password_hash("$ADMIN_PASSWORD")
        else:
            print("Создаем нового администратора...")
            admin = User(
                username='admin',
                email='admin@example.com',
                password_hash=generate_password_hash("$ADMIN_PASSWORD"),
                is_admin=True
            )
            db.session.add(admin)
        
        db.session.commit()
        print("Администратор успешно создан/обновлен!")
        return True

if __name__ == "__main__":
    success = init_db() and create_admin()
    sys.exit(0 if success else 1)
EOF

# Инициализация базы данных и создание админа
print_header "Инициализация базы данных и создание администратора"
cd "$APP_DIR"
source "$VENV_DIR/bin/activate"
python "$APP_DIR/init_db.py"

# Настройка Nginx в качестве обратного прокси
print_header "Настройка Nginx обратного прокси"
sudo tee /etc/nginx/sites-available/reverse_proxy_control_center > /dev/null <<EOF
server {
    listen 80 default_server;
    listen [::]:80 default_server;
    server_name _;  # Замените на ваше доменное имя для продакшена

    # Логи
    access_log /var/log/nginx/rpcc_access.log;
    error_log /var/log/nginx/rpcc_error.log;

    # Основные настройки
    client_max_body_size 50m;
    
    # Таймауты для лучшей совместимости с долгими запросами
    proxy_connect_timeout 300s;
    proxy_send_timeout 300s;
    proxy_read_timeout 300s;

    location / {
        proxy_pass http://localhost:5000;
        proxy_set_header Host \$host;
        proxy_set_header X-Real-IP \$remote_addr;
        proxy_set_header X-Forwarded-For \$proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto \$scheme;
        
        # Параметры WebSocket (если используются)
        proxy_http_version 1.1;
        proxy_set_header Upgrade \$http_upgrade;
        proxy_set_header Connection "upgrade";
        
        # Буферизация ответов
        proxy_buffering on;
        proxy_buffer_size 8k;
        proxy_buffers 8 8k;
    }

    location /static {
        alias $APP_DIR/static;
        expires 7d;
        add_header Cache-Control "public";
    }
    
    # Статус Nginx для мониторинга
    location /nginx_status {
        stub_status on;
        access_log off;
        allow 127.0.0.1;  # Разрешить доступ только с localhost
        deny all;         # Запретить все остальные
    }
}
EOF

# Включаем сайт и перезапускаем Nginx
sudo ln -sf /etc/nginx/sites-available/reverse_proxy_control_center /etc/nginx/sites-enabled/
sudo rm -f /etc/nginx/sites-enabled/default  # Удаляем дефолтный сайт

# Проверяем конфигурацию Nginx
if sudo nginx -t; then
    sudo systemctl restart nginx
else
    print_error "Ошибка в конфигурации Nginx. Пожалуйста, проверьте и исправьте ошибки."
    exit 1
fi

# Настройка Glances для всех серверов
print_header "Создание скрипта установки Glances"
cat > "$APP_DIR/install_glances.sh" <<'EOF'
#!/bin/bash

# Скрипт для установки Glances на Ubuntu 22.04+ с поддержкой веб-интерфейса
# Запуск: sudo bash install_glances.sh

# Определение цветов для вывода
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color

# Функции для вывода
info() { echo -e "${GREEN}[INFO]${NC} $1"; }
warn() { echo -e "${YELLOW}[WARN]${NC} $1"; }
error() { echo -e "${RED}[ERROR]${NC} $1"; }

# Проверка, запущен ли скрипт от имени root
if [ "$(id -u)" != "0" ]; then
    error "Этот скрипт должен быть запущен с правами root (sudo)."
    exit 1
fi

# Проверяем, установлен ли Python 3
if ! command -v python3 &>/dev/null; then
    info "Python3 не найден. Устанавливаем..."
    apt-get update
    apt-get install -y python3 python3-pip
else
    info "Python3 уже установлен: $(python3 --version)"
fi

# Устанавливаем pip и зависимости
info "Установка Python3-pip и зависимостей..."
apt-get install -y python3-pip curl net-tools lsof jq

# Устанавливаем Glances через pip в совместимой версии
info "Установка Glances через pip..."
pip3 install --upgrade pip setuptools wheel
pip3 install "glances[web]<=5.0"

# Устанавливаем необходимые зависимости для веб-сервера
info "Установка веб-зависимостей..."
pip3 install fastapi uvicorn jinja2

# Создаем systemd сервис для Glances
info "Создание systemd сервиса..."
cat > /etc/systemd/system/glances.service << EOF
[Unit]
Description=Glances monitoring tool (web mode)
After=network.target

[Service]
ExecStart=/usr/local/bin/glances -w
Restart=always

[Install]
WantedBy=multi-user.target
EOF

# Перезагружаем systemd, включаем и запускаем сервис
info "Запуск сервиса..."
systemctl daemon-reload
systemctl enable glances.service
systemctl start glances.service

# Ждем немного для старта сервиса
info "Ожидание запуска сервиса (5 секунд)..."
sleep 5

# Проверяем статус сервиса
info "Проверка статуса сервиса..."
systemctl status glances.service --no-pager

# Проверяем доступность API и Web-интерфейса
info "Проверка доступности API (порт 61208)..."
if curl -s "http://localhost:61208/api/4/cpu" | grep -q "total"; then
    info "✅ API доступен и работает"
else
    warn "❌ API не отвечает. Проверьте журнал: journalctl -u glances.service"
    
    # Дополнительная информация о процессе
    info "Информация о процессе Glances:"
    ps aux | grep -v grep | grep glances || echo "Процесс не найден"
    
    # Информация о прослушиваемых портах
    info "Открытые порты:"
    ss -tulpn | grep 61208 || echo "Порт не прослушивается"
    
    # Пробуем перезапустить сервис
    info "Пробуем перезапустить сервис..."
    systemctl restart glances.service
    sleep 5
    
    # Проверяем еще раз
    if curl -s "http://localhost:61208/api/4/cpu" | grep -q "total"; then
        info "✅ После перезапуска API стал доступен"
    else
        warn "❌ API все еще недоступен"
    fi
fi

info "Проверка доступности Web-интерфейса..."
if curl -s "http://localhost:61208/" | grep -q "Glances"; then
    info "✅ Web-интерфейс доступен и работает"
else
    warn "❌ Web-интерфейс не отвечает"
fi

# Информация о сети для облегчения доступа извне
info "Внешние интерфейсы:"
ip -4 addr show | grep -v 127.0.0.1 | grep inet

info "======================================================"
info "Установка Glances завершена."
info "Web URL и API URL: http://IP_АДРЕС:61208/"
info "Журнал: journalctl -u glances.service -f"
info "======================================================"

exit 0
EOF

chmod +x "$APP_DIR/install_glances.sh"

# Создание инструмента для диагностики
print_header "Создание инструмента диагностики"
sudo tee /usr/local/bin/rpcc-diagnose > /dev/null <<'EOF'
#!/bin/bash

GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m'

echo -e "${GREEN}Диагностика Reverse Proxy Control Center${NC}"
echo -e "========================================"

# Проверка статуса сервисов
echo -e "\n${GREEN}Проверка статуса сервисов:${NC}"
echo -e "--------------------------------------"
systemctl is-active --quiet postgresql && echo -e "PostgreSQL: ${GREEN}активен${NC}" || echo -e "PostgreSQL: ${RED}не активен${NC}"
systemctl is-active --quiet nginx && echo -e "Nginx: ${GREEN}активен${NC}" || echo -e "Nginx: ${RED}не активен${NC}"
systemctl is-active --quiet reverse_proxy_control_center && echo -e "RPCC: ${GREEN}активен${NC}" || echo -e "RPCC: ${RED}не активен${NC}"

# Проверка работы портов
echo -e "\n${GREEN}Проверка сетевых портов:${NC}"
echo -e "--------------------------------------"
nc -z -v -w1 localhost 5000 2>/dev/null && echo -e "Порт 5000 (Gunicorn): ${GREEN}открыт${NC}" || echo -e "Порт 5000 (Gunicorn): ${RED}закрыт${NC}"
nc -z -v -w1 localhost 80 2>/dev/null && echo -e "Порт 80 (Nginx): ${GREEN}открыт${NC}" || echo -e "Порт 80 (Nginx): ${RED}закрыт${NC}"
nc -z -v -w1 localhost 5432 2>/dev/null && echo -e "Порт 5432 (PostgreSQL): ${GREEN}открыт${NC}" || echo -e "Порт 5432 (PostgreSQL): ${RED}закрыт${NC}"

# Проверка логов
echo -e "\n${GREEN}Последние ошибки в логах:${NC}"
echo -e "--------------------------------------"
echo -e "${YELLOW}Логи RPCC:${NC}"
if [ -f "/var/log/reverse_proxy_control_center/error.log" ]; then
    tail -n 5 /var/log/reverse_proxy_control_center/error.log
else
    echo "Лог-файл не найден"
fi

echo -e "\n${YELLOW}Логи Nginx:${NC}"
if [ -f "/var/log/nginx/rpcc_error.log" ]; then
    tail -n 5 /var/log/nginx/rpcc_error.log
else
    echo "Лог-файл не найден"
fi

echo -e "\n${YELLOW}Логи PostgreSQL:${NC}"
if [ -f "/var/log/postgresql/postgresql-$(psql --version | head -n 1 | awk '{print $3}' | cut -d. -f1-2)-main.log" ]; then
    tail -n 5 "/var/log/postgresql/postgresql-$(psql --version | head -n 1 | awk '{print $3}' | cut -d. -f1-2)-main.log"
else
    echo "Лог-файл не найден"
fi

# Проверка базы данных
echo -e "\n${GREEN}Проверка базы данных:${NC}"
echo -e "--------------------------------------"
if sudo -u postgres psql -tAc "SELECT 1 FROM pg_database WHERE datname='rpcc'" | grep -q 1; then
    echo -e "База данных 'rpcc': ${GREEN}существует${NC}"
else
    echo -e "База данных 'rpcc': ${RED}не существует${NC}"
fi

if sudo -u postgres psql -tAc "SELECT 1 FROM pg_roles WHERE rolname='rpcc'" | grep -q 1; then
    echo -e "Пользователь БД 'rpcc': ${GREEN}существует${NC}"
else
    echo -e "Пользователь БД 'rpcc': ${RED}не существует${NC}"
fi

# Советы по устранению неполадок
echo -e "\n${GREEN}Рекомендации по устранению неполадок:${NC}"
echo -e "--------------------------------------"
echo -e "1. Перезапустить сервисы: systemctl restart reverse_proxy_control_center nginx postgresql"
echo -e "2. Проверить полные логи: journalctl -u reverse_proxy_control_center -n 50"
echo -e "3. Проверить конфигурацию Nginx: nginx -t"
echo -e "4. Проверить разрешения файлов: ls -la /opt/reverse_proxy_control_center"
echo -e "5. Если проблемы сохраняются, выполните полную переустановку."
EOF

sudo chmod +x /usr/local/bin/rpcc-diagnose

# Включаем и запускаем сервис
print_header "Запуск сервиса"
sudo systemctl daemon-reload
sudo systemctl enable reverse_proxy_control_center
sudo systemctl restart reverse_proxy_control_center

# Сохраняем учетные данные в файл
sudo tee /root/rpcc_credentials.txt > /dev/null <<EOF
======================================================
REVERSE PROXY CONTROL CENTER - УЧЕТНЫЕ ДАННЫЕ
======================================================
URL: http://$SERVER_IP
Логин: admin
Пароль: $ADMIN_PASSWORD
======================================================
База данных PostgreSQL:
  - Имя базы: rpcc
  - Пользователь: rpcc
  - Пароль: $DB_PASSWORD
  - URL: postgresql://rpcc:$DB_PASSWORD@localhost/rpcc
======================================================
Секретный ключ сессии: $SESSION_SECRET
======================================================
Сохраните эту информацию в безопасном месте!
ЭТОТ ФАЙЛ БУДЕТ АВТОМАТИЧЕСКИ УДАЛЕН ЧЕРЕЗ 24 ЧАСА.
======================================================
EOF

sudo chmod 600 /root/rpcc_credentials.txt

# Создаем задачу cron для удаления файла с учетными данными через 24 часа
(sudo crontab -l 2>/dev/null; echo "$(date -d '24 hours' +'%M %H %d %m *') rm -f /root/rpcc_credentials.txt") | sudo crontab -

# Вывод информации об установке
clear
echo "======================================================="
echo "УСТАНОВКА УСПЕШНО ЗАВЕРШЕНА!"
echo "======================================================="
echo "Reverse Proxy Control Center доступен по адресу:"
echo "  http://$SERVER_IP"
echo ""
echo "Данные для входа:"
echo "  Логин: admin"
echo "  Пароль: $ADMIN_PASSWORD"
echo ""
echo "Данные сохранены в файле /root/rpcc_credentials.txt"
echo "Файл будет автоматически удален через 24 часа."
echo "======================================================="
echo "Статус сервиса: $(systemctl is-active reverse_proxy_control_center)"
echo ""
echo "Если возникнут проблемы, выполните команду:"
echo "  sudo rpcc-diagnose"
echo "======================================================="

# Проверяем доступность веб-приложения
echo "Выполняем проверку доступности веб-приложения..."
sleep 5
# Проверка через curl
if curl -s http://localhost > /dev/null; then
    echo -e "\n${GREEN}[УСПЕХ]${NC} Веб-приложение доступно! Сервер успешно запущен."
else
    echo -e "\n${YELLOW}[ПРЕДУПРЕЖДЕНИЕ]${NC} Веб-приложение пока недоступно."
    echo "Запускаем диагностику..."
    sudo /usr/local/bin/rpcc-diagnose
    
    echo -e "\n${YELLOW}[СОВЕТ]${NC} Если веб-приложение недоступно, возможно, ему требуется больше времени для запуска."
    echo "Проверьте статус через несколько минут: systemctl status reverse_proxy_control_center"
fi
EOL

# Делаем новый установщик исполняемым
chmod +x install_v2.sh

# Запускаем установщик
echo -e "${GREEN}[INFO]${NC} Запуск нового установщика..."
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