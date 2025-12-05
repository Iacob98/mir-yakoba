#!/bin/bash
set -e

cd "$(dirname "$0")/.."

echo "=== Инициализация webseit ==="

# 1. Проверка .env файла
if [ ! -f .env ]; then
    echo "Создаю .env из .env.example..."
    cp .env.example .env
    echo "Отредактируйте .env и добавьте TELEGRAM_BOT_TOKEN"
    echo "Затем запустите скрипт снова"
    exit 1
fi

# Проверка что токен бота указан
if grep -q "your-telegram-bot-token" .env; then
    echo "ОШИБКА: Укажите TELEGRAM_BOT_TOKEN в .env"
    exit 1
fi

# 2. Запуск docker-compose
echo "Запуск контейнеров..."
docker compose up -d db redis

# 3. Ожидание готовности БД
echo "Ожидание готовности PostgreSQL..."
until docker compose exec -T db pg_isready -U blog -d blog > /dev/null 2>&1; do
    sleep 1
done
echo "PostgreSQL готов"

# 4. Запуск app для миграций
docker compose up -d app

# 5. Применение миграций
echo "Применение миграций..."
sleep 2
docker compose exec -T app alembic upgrade head

# 6. Запуск всех сервисов
echo "Запуск всех сервисов..."
docker compose up -d

echo ""
echo "=== Готово! ==="
echo "Приложение: http://localhost:8000"
echo "API docs:   http://localhost:8000/api/docs"
echo ""
echo "Для создания админа:"
echo "  1. Напишите боту /start в Telegram"
echo "  2. Выполните: docker compose exec app python scripts/make_admin.py <telegram_id>"
