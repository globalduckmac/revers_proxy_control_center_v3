# Reverse Proxy Control Center v3

Система управления обратными прокси и мониторинга серверов с использованием Glances API.

## Особенности

- Мониторинг серверов через Glances API
- Управление доменами и обратными прокси
- Интеграция с Telegram для уведомлений
- Поддержка PostgreSQL для хранения данных
- Интуитивно понятный веб-интерфейс

## Требования

- Ubuntu 22.04 или новее
- Python 3.10+
- PostgreSQL
- Nginx
- Git

## Установка

Для установки выполните следующие команды:

```bash
# Клонировать репозиторий
git clone https://github.com/globalduckmac/revers_proxy_control_center_v3.git /tmp/rpcc

# Перейти в директорию с проектом
cd /tmp/rpcc

# Запустить скрипт установки
sudo bash deploy_script.sh
```

## Исправление проблем с импортами

Если у вас возникли проблемы с запуском приложения из-за ошибок импорта, выполните:

```bash
# Перейти в директорию с проектом
cd /opt/reverse_proxy_control_center

# Запустить скрипт исправления импортов
sudo bash fix_imports.sh

# Перезапустить сервис
sudo systemctl restart reverse_proxy_control_center
```

## Диагностика и устранение проблем

Для диагностики проблем используйте встроенный инструмент:

```bash
sudo rpcc-diagnose
```

Для проверки логов:

```bash
# Логи веб-приложения
sudo journalctl -u reverse_proxy_control_center -n 50

# Логи Nginx
sudo tail -f /var/log/nginx/error.log
```

## Настройка базы данных

Если у вас возникли проблемы с подключением к базе данных, можно воспользоваться скриптом:

```bash
# Перейти в директорию с проектом
cd /opt/reverse_proxy_control_center

# Запустить скрипт настройки базы данных
sudo bash fix_db.sh
```

## Контакты

При возникновении проблем создайте issue в этом репозитории.
