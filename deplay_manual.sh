#!/bin/bash

# Автоматический скрипт развертывания для Reverse Proxy Control Center
# Этот скрипт устанавливает все зависимости и настраивает приложение на Ubuntu 20.04+

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

print_header "Начало развертывания Reverse Proxy Control Center"

# Создаем каталог для приложения
APP_DIR="/opt/reverse-proxy-control-center"
print_header "Создание каталога приложения в $APP_DIR"
sudo mkdir -p "$APP_DIR"
sudo chown $USER:$USER "$APP_DIR"

# Получение исходного кода
print_header "Клонирование репозитория из GitHub"
if [ ! -d "$APP_DIR/.git" ]; then
    git clone https://github.com/globalduckmac/revers_proxy_control_center_v3.git "$APP_DIR" 
    cd "$APP_DIR"
else
    cd "$APP_DIR"
    git pull
fi

# Обновление системных пакетов
print_header "Обновление системных пакетов"
sudo apt-get update
sudo apt-get upgrade -y

# Установка необходимых системных пакетов
print_header "Установка системных зависимостей"
sudo apt-get install -y python3 python3-pip python3-venv nginx postgresql postgresql-contrib certbot python3-certbot-nginx git

# Настройка PostgreSQL
print_header "Настройка PostgreSQL"
if ! sudo -u postgres psql -tAc "SELECT 1 FROM pg_database WHERE datname='reverse_proxy_manager'" | grep -q 1; then
    # Создаем пользователя и базу данных PostgreSQL
    sudo -u postgres psql -c "CREATE USER proxy_manager WITH PASSWORD 'secure_password';"
    sudo -u postgres psql -c "CREATE DATABASE reverse_proxy_manager WITH OWNER proxy_manager;"
    sudo -u postgres psql -c "GRANT ALL PRIVILEGES ON DATABASE reverse_proxy_manager TO proxy_manager;"
    echo "База данных PostgreSQL и пользователь созданы"
else
    echo "База данных уже существует, пропускаем создание"
fi

# Настройка Python-окружения
print_header "Настройка Python-окружения"
cd "$APP_DIR"
python3 -m venv venv
source venv/bin/activate

# Установка Python-зависимостей
print_header "Установка Python-зависимостей"
pip install --upgrade pip
pip install gunicorn psycopg2-binary cryptography dnspython email-validator flask flask-login flask-sqlalchemy flask-wtf jinja2 paramiko python-telegram-bot pytz requests sqlalchemy werkzeug pymysql

# Исправление конфигурации базы данных
print_header "Исправление конфигурации базы данных"
echo "Изменение значения по умолчанию для SQLALCHEMY_DATABASE_URI в config.py..."
sed -i "s|'mysql://root:password@localhost/reverse_proxy_manager'|'postgresql://proxy_manager:secure_password@localhost/reverse_proxy_manager'|" "$APP_DIR/config.py"
echo "Файл config.py успешно обновлен"

# Настройка переменных окружения
print_header "Настройка переменных окружения"
cat > "$APP_DIR/.env" <<EOF
FLASK_APP=main.py
FLASK_ENV=production
FLASK_CONFIG=production
SESSION_SECRET=$(python3 -c "import secrets; print(secrets.token_hex(24))")
DATABASE_URL=postgresql://proxy_manager:secure_password@localhost/reverse_proxy_manager

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
sudo tee /etc/systemd/system/reverse-proxy-control-center.service > /dev/null <<EOF
[Unit]
Description=Reverse Proxy Control Center
After=network.target postgresql.service

[Service]
User=$USER
WorkingDirectory=$APP_DIR
ExecStart=$APP_DIR/venv/bin/gunicorn --workers 4 --bind 0.0.0.0:5000 --reuse-port main:app
Restart=always
RestartSec=10
Environment=PYTHONUNBUFFERED=1
EnvironmentFile=$APP_DIR/.env

[Install]
WantedBy=multi-user.target
EOF

# Создание скрипта для инициализации базы данных
print_header "Создание скрипта инициализации базы данных"
cat > "$APP_DIR/init_db.py" <<EOF
from app import app, db
from models import User
import os

def create_admin_user():
    """Создание администратора если его нет"""
    with app.app_context():
        # Убедимся, что таблицы созданы
        db.create_all()
        
        # Проверяем наличие администратора
        if not User.query.filter_by(username='admin').first():
            user = User(username='admin', 
                      email='admin@example.com', 
                      is_admin=True)
            user.set_password('admin123')  # Установите свой надежный пароль
            db.session.add(user)
            db.session.commit()
            print("Администратор создан")
        else:
            print("Администратор уже существует")

if __name__ == '__main__':
    # Инициализация базы данных
    with app.app_context():
        db.create_all()
        print("База данных инициализирована")
    
    # Создание администратора
    create_admin_user()
EOF

# Инициализация базы данных и создание админа
print_header "Инициализация базы данных"
source "$APP_DIR/venv/bin/activate"
python "$APP_DIR/init_db.py"

# Настройка Nginx в качестве обратного прокси
print_header "Настройка Nginx обратного прокси"
sudo tee /etc/nginx/sites-available/reverse-proxy-control-center > /dev/null <<EOF
server {
    listen 80;
    server_name _;  # Замените на ваше доменное имя для продакшена

    access_log /var/log/nginx/reverse-proxy-control-center.access.log;
    error_log /var/log/nginx/reverse-proxy-control-center.error.log;

    location / {
        proxy_pass http://127.0.0.1:5000;
        proxy_set_header Host \$host;
        proxy_set_header X-Real-IP \$remote_addr;
        proxy_set_header X-Forwarded-For \$proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto \$scheme;
    }

    location /static {
        alias $APP_DIR/static;
        expires 30d;
    }
}
EOF

# Включаем сайт и перезапускаем Nginx
sudo ln -sf /etc/nginx/sites-available/reverse-proxy-control-center /etc/nginx/sites-enabled/
sudo rm -f /etc/nginx/sites-enabled/default  # Удаляем дефолтный сайт
sudo systemctl restart nginx

# Включаем и запускаем сервис
print_header "Запуск сервиса"
sudo systemctl daemon-reload
sudo systemctl enable reverse-proxy-control-center
sudo systemctl start reverse-proxy-control-center

# Проверка статуса сервиса
echo "Статус сервиса:"
sudo systemctl status reverse-proxy-control-center --no-pager

print_header "Развертывание завершено!"
echo -e "Reverse Proxy Control Center работает по адресу http://$(hostname -I | awk '{print $1}'):80"
echo -e "\nУчетные данные администратора:"
echo "  Логин: admin"
echo "  Пароль: admin123"

print_warning "Пожалуйста, измените пароль администратора после первого входа!"
echo -e "\nДля безопасности вашего сервера, рекомендуется:"
echo "  1. Настроить SSL с помощью certbot: sudo certbot --nginx"
echo "  2. Настроить брандмауэр (ufw): sudo ufw allow 'Nginx Full' && sudo ufw enable"
echo "  3. Обновить данные Telegram бота в файле $APP_DIR/.env для отправки уведомлений"
echo -e "\nЕсли вам нужно изменить пароль администратора, выполните:"
echo "cd $APP_DIR && source venv/bin/activate && python change_admin_password.py"

# Добавляем инструкции для доступа к файлу журнала
echo -e "\nДля просмотра журнала приложения выполните:"
echo "sudo journalctl -u reverse-proxy-control-center -f"
