#!/bin/bash

# Скрипт для удаления старых установочных скриптов
# и оставления только единого deploy_script.sh

# Цвета для вывода
GREEN='\033[0;32m'
RED='\033[0;31m'
NC='\033[0m' # No Color

echo -e "${GREEN}Очистка старых установочных скриптов...${NC}"

# Список скриптов для удаления
scripts=(
  "install.sh"
  "install_v2.sh"
  "quick_install.sh"
  "quick_install_v2.sh"
  "non_interactive_install.sh"
)

# Удаляем скрипты на GitHub, если они существуют
for script in "${scripts[@]}"; do
  if [ -f "$script" ]; then
    echo "Удаление $script..."
    git rm "$script" 2>/dev/null
    if [ $? -eq 0 ]; then
      echo -e "  ${GREEN}✓ Успешно удален${NC}"
    else
      echo -e "  ${RED}✗ Ошибка при удалении${NC}"
    fi
  else
    echo "Файл $script не найден, пропускаю"
  fi
done

# Добавляем сообщение в README о новом скрипте установки
if [ -f "README.md" ]; then
  if ! grep -q "## Простая установка" README.md; then
    cat >> README.md << EOF

## Простая установка

Для быстрой установки системы используйте следующую команду:

\`\`\`bash
wget https://raw.githubusercontent.com/globalduckmac/revers_proxy_control_center_v3/main/deploy_script.sh
chmod +x deploy_script.sh
sudo ./deploy_script.sh
\`\`\`

Скрипт автоматически настроит все необходимые компоненты и запустит систему.
После установки вы получите данные для входа в систему.
EOF
    echo -e "${GREEN}✓ Обновлена документация в README.md${NC}"
    git add README.md
  fi
fi

echo "Фиксация изменений в репозитории..."
git commit -m "Удалены устаревшие установочные скрипты, оставлен только единый deploy_script.sh"

echo -e "${GREEN}Готово!${NC}"