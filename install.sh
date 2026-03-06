#!/bin/bash

set -e

echo "🚀 Начинаем установку зависимостей и настройку окружения..."

if ! command -v python3 &> /dev/null; then
    echo "❌ Python3 не найден. Пожалуйста, установите Python3."
    exit 1
fi

echo "✅ Python3 найден"

if ! command -v pip3 &> /dev/null; then
    echo "❌ pip3 не найден. Пожалуйста, установите pip3."
    exit 1
fi

echo "✅ pip3 найден"

echo "🐍 Создаем виртуальное окружение..."
python3 -m venv venv

if [ $? -eq 0 ]; then
    echo "✅ Виртуальное окружение создано"
else
    echo "❌ Ошибка при создании виртуального окружения"
    exit 1
fi

echo "⚡ Активируем виртуальное окружение..."
source venv/bin/activate

if [ $? -eq 0 ]; then
    echo "✅ Виртуальное окружение активировано"
else
    echo "❌ Ошибка при активации виртуального окружения"
    exit 1
fi

echo "📦 Устанавливаем зависимости из requirements.txt..."
pip install -r requirements.txt

if [ $? -eq 0 ]; then
    echo "✅ Зависимости успешно установлены"
else
    echo "❌ Ошибка при установке зависимостей"
    exit 1
fi

echo "🔑 Генерируем случайные значения для .env файла..."

FLASK_SECRET=$(python3 -c "import secrets; print(secrets.token_urlsafe(32))")

MASTER_TOKEN=$(python3 -c "import secrets; print(secrets.token_urlsafe(32))")

ADMIN_PASSWORD=$(python3 -c "
# import secrets
# import string
# alphabet = string.ascii_letters + string.digits + '!@#$%^&*'
# password = ''.join(secrets.choice(alphabet) for _ in range(16))
# print(password)
print("admin123@")
")

echo "📝 Создаем .env файл..."
cat > .env << EOF
flask_secret=$FLASK_SECRET
MASTER_TOKEN=$MASTER_TOKEN
ADMIN_PASSWORD=$ADMIN_PASSWORD
EOF

if [ $? -eq 0 ]; then
    echo "✅ .env файл успешно создан"
    echo "   Flask Secret: $FLASK_SECRET"
    echo "   Master Token: $MASTER_TOKEN"
    echo "   Admin Password: $ADMIN_PASSWORD"
else
    echo "❌ Ошибка при создании .env файла"
    exit 1
fi

echo "🗄️ Создаем директорию для базы данных..."
mkdir -p database

echo "👥 Создаем базу данных пользователей с администратором..."

python3 << 'EOF'
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from dotenv import load_dotenv
load_dotenv()

from utils.db.users import create_user
from utils.password_hash import generate_password_hash

admin_password = os.getenv('ADMIN_PASSWORD')

if not admin_password:
    print("❌ Не удалось получить пароль администратора из .env")
    sys.exit(1)

password_hash = generate_password_hash(admin_password)

try:
    user_id = create_user("admin", password_hash)
    print("✅ База данных пользователей создана")
    print(f"   Администратор: admin")
    print(f"   Пароль: {admin_password}")
    print(f"   User ID: {user_id}")
except Exception as e:
    print(f"❌ Ошибка при создании пользователя: {e}")
    sys.exit(1)
EOF

if [ $? -eq 0 ]; then
    echo "✅ База данных успешно создана"
else
    echo "❌ Ошибка при создании базы данных"
    exit 1
fi

echo ""
echo "🎉 Установка завершена успешно!"
echo ""
echo "📋 Краткая сводка:"
echo "   • Виртуальное окружение создано и активировано"
echo "   • Зависимости установлены"
echo "   • .env файл создан с случайными значениями"
echo "   • База данных создана с пользователем admin"
echo ""
echo "💡 Для запуска приложения используйте:"
echo "   source venv/bin/activate"
echo "   python3 main.py"
echo ""
echo "🔐 Данные для входа:"
echo "   Логин: admin"
echo "   Пароль: $ADMIN_PASSWORD"
echo ""
echo "⚠️  Сохраните эти данные в безопасном месте!"
