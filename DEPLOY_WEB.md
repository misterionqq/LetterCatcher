# Развёртывание LetterCatcher с веб-интерфейсом

Пошаговый гайд по запуску LetterCatcher с веб-интерфейсом ([LetterCatcherWeb](https://github.com/misterionqq/LetterCatcherWeb)). REST API + WebSocket обеспечивают real-time уведомления в браузере.

---

## Содержание

- [Что вы получите](#что-вы-получите)
- [Требования](#требования)
- [Шаг 1. Настройка почтового ящика](#шаг-1-настройка-почтового-ящика)
- [Шаг 2. Получение ключа OpenRouter](#шаг-2-получение-ключа-openrouter)
- [Шаг 3. Подготовка сервера](#шаг-3-подготовка-сервера)
- [Шаг 4. Запуск бэкенда](#шаг-4-запуск-бэкенда)
- [Шаг 5. Запуск фронтенда](#шаг-5-запуск-фронтенда)
- [Шаг 6. Настройка Nginx](#шаг-6-настройка-nginx)
- [Шаг 7. SSL-сертификат](#шаг-7-ssl-сертификат)
- [Шаг 8. Проверка работы](#шаг-8-проверка-работы)
- [Добавление Telegram-бота](#добавление-telegram-бота)
- [Мониторинг и логи](#мониторинг-и-логи)
- [Обновление](#обновление)
- [Устранение неполадок](#устранение-неполадок)

---

## Что вы получите

- Веб-интерфейс с регистрацией по email и паролю
- Real-time уведомления через WebSocket прямо в браузере
- История писем, статистика, управление ключевыми словами
- REST API для интеграции с мобильным приложением (Capacitor)
- Опционально --- параллельная работа Telegram-бота

---

## Требования

| Требование | Минимум |
|-----------|---------|
| Сервер | VPS с 1 vCPU, 512 МБ RAM, 2 ГБ диска |
| ОС | Ubuntu 22.04+ / Debian 12+ |
| Docker | Docker Engine 24+ и Docker Compose v2 |
| Node.js | 18+ (для сборки фронтенда) |
| Домен | Рекомендуется (для HTTPS и WebSocket) |
| Сеть | Порты 443, 993 (IMAP SSL) |

---

## Шаг 1. Настройка почтового ящика

Для подключения к почте по IMAP нужен **пароль приложения** (App Password).

### Gmail

1. Включите 2FA: [myaccount.google.com/security](https://myaccount.google.com/security)
2. Создайте пароль приложения: [myaccount.google.com/apppasswords](https://myaccount.google.com/apppasswords)
3. Скопируйте 16-символьный пароль

IMAP-сервер: `imap.gmail.com`

### Яндекс

1. [id.yandex.ru/security/app-passwords](https://id.yandex.ru/security/app-passwords) -> создайте пароль для "Почта"

IMAP-сервер: `imap.yandex.ru`

### Другие провайдеры

| Провайдер | IMAP-сервер |
|-----------|------------|
| Mail.ru | `imap.mail.ru` |
| Office 365 | `outlook.office365.com` |

---

## Шаг 2. Получение ключа OpenRouter

1. Зарегистрируйтесь на [openrouter.ai](https://openrouter.ai/)
2. Создайте API-ключ: [openrouter.ai/keys](https://openrouter.ai/keys)

Бесплатная модель для старта: `google/gemini-2.5-flash-preview-05-20`

---

## Шаг 3. Подготовка сервера

```bash
ssh user@your-server-ip

# Docker
curl -fsSL https://get.docker.com | sh
sudo usermod -aG docker $USER
exit
ssh user@your-server-ip

# Node.js (для сборки фронтенда)
curl -fsSL https://deb.nodesource.com/setup_20.x | sudo -E bash -
sudo apt install -y nodejs

# Nginx
sudo apt install -y nginx

# Структура проекта
mkdir -p /opt/lettercatcher
cd /opt/lettercatcher

# Бэкенд
git clone https://github.com/misterionqq/LetterCatcher.git backend
# Фронтенд
git clone https://github.com/misterionqq/LetterCatcherWeb.git frontend
```

---

## Шаг 4. Запуск бэкенда

### Конфигурация .env

```bash
cd /opt/lettercatcher/backend
cp .env.example .env
nano .env
```

Заполните:

```env
# === РЕЖИМ ===
CLIENT_MODE=web
APP_MODE=personal
ADMIN_EMAIL=your-email@gmail.com       # Email владельца (для personal-режима)

# === ПОЧТА ===
IMAP_SERVER=imap.gmail.com
EMAIL_USER=your-email@gmail.com
EMAIL_PASSWORD=abcd efgh ijkl mnop     # Пароль приложения

# === AI ===
OPENROUTER_API_KEY=sk-or-...
LLM_MODEL=google/gemini-2.5-flash-preview-05-20

# === API ===
API_PORT=8000
JWT_SECRET_KEY=ваша-случайная-строка
# Генерация: python3 -c "import secrets; print(secrets.token_urlsafe(32))"

# === CORS ===
# Укажите домен, на котором будет фронтенд
CORS_ORIGINS=https://your-domain.com,http://localhost:5173

# === SMTP (верификация email) ===
SMTP_SERVER=smtp.gmail.com
SMTP_PORT=587
APP_BASE_URL=https://your-domain.com   # Для ссылок в письмах верификации
```

> **`CLIENT_MODE=web`** --- Telegram-бот **не запускается**, токен бота не нужен. REST API и WebSocket работают.

### Запуск

```bash
docker compose up -d --build

# Проверка
docker compose ps
curl http://localhost:8000/api/v1/health
```

---

## Шаг 5. Запуск фронтенда

### Сборка

```bash
cd /opt/lettercatcher/frontend

# Установка зависимостей
npm install

# Конфигурация
cat > .env.production << 'EOF'
VITE_API_BASE_URL=https://your-domain.com/api/v1
EOF

# Сборка для продакшена
npm run build
```

Готовые файлы появятся в папке `dist/`.

### Размещение статики

```bash
# Копируем собранный фронтенд в директорию Nginx
sudo mkdir -p /var/www/lettercatcher
sudo cp -r dist/* /var/www/lettercatcher/
sudo chown -R www-data:www-data /var/www/lettercatcher
```

---

## Шаг 6. Настройка Nginx

Nginx выступает реверс-прокси: отдаёт статику фронтенда и проксирует API-запросы на бэкенд.

```bash
sudo nano /etc/nginx/sites-available/lettercatcher
```

```nginx
server {
    listen 80;
    server_name your-domain.com;

    # Фронтенд (статика)
    root /var/www/lettercatcher;
    index index.html;

    # SPA: все маршруты -> index.html
    location / {
        try_files $uri $uri/ /index.html;
    }

    # API проксирование
    location /api/ {
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }

    # WebSocket проксирование
    location /api/v1/ws {
        proxy_pass http://127.0.0.1:8000;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_read_timeout 86400;
    }
}
```

```bash
# Активация конфигурации
sudo ln -s /etc/nginx/sites-available/lettercatcher /etc/nginx/sites-enabled/
sudo rm -f /etc/nginx/sites-enabled/default
sudo nginx -t
sudo systemctl reload nginx
```

---

## Шаг 7. SSL-сертификат

HTTPS необходим для безопасной передачи JWT-токенов и работы WebSocket (`wss://`).

```bash
# Установка Certbot
sudo apt install -y certbot python3-certbot-nginx

# Получение сертификата (автоматически обновит конфиг Nginx)
sudo certbot --nginx -d your-domain.com

# Автопродление (проверка)
sudo certbot renew --dry-run
```

После этого Nginx автоматически будет использовать HTTPS и перенаправлять HTTP -> HTTPS.

---

## Шаг 8. Проверка работы

### API

```bash
curl https://your-domain.com/api/v1/health
# {"status":"ok","database":"ok","scanner":"running"}
```

### Фронтенд

1. Откройте `https://your-domain.com` в браузере
2. Зарегистрируйтесь с email и паролем
3. Подтвердите email (если настроен SMTP)
4. Добавьте ключевые слова в настройках
5. Отправьте тестовое письмо на мониторимый ящик
6. Через ~30 секунд должно появиться уведомление в реальном времени

### WebSocket

Откройте консоль разработчика (F12 -> Network -> WS) --- должно быть активное WebSocket-соединение на `/api/v1/ws`.

---

## Добавление Telegram-бота

> Если вы хотите получать уведомления и в Telegram, и через веб-интерфейс одновременно, измените `CLIENT_MODE` на `all`.

### Шаг 1. Создайте бота

1. [@BotFather](https://t.me/BotFather) -> `/newbot` -> скопируйте токен
2. Узнайте свой Telegram ID через [@userinfobot](https://t.me/userinfobot)

### Шаг 2. Обновите .env

```bash
cd /opt/lettercatcher/backend
nano .env
```

Измените и добавьте:

```env
CLIENT_MODE=all                            # Было "web", стало "all"
ADMIN_TG_ID=123456789                      # Ваш Telegram ID
TELEGRAM_BOT_TOKEN=7123456789:AAH...       # Токен бота
TELEGRAM_BOT_USERNAME=my_lettercatcher_bot # Username бота (без @)
```

### Шаг 3. Перезапустите

```bash
docker compose restart bot
```

### Шаг 4. Проверьте

1. Отправьте `/start` боту в Telegram
2. Бот и веб-интерфейс работают параллельно
3. Уведомления приходят в оба канала одновременно

### Webhook для Telegram (опционально)

Если на сервере уже настроен HTTPS, можно использовать webhook вместо polling:

```env
WEBHOOK_URL=https://your-domain.com
WEBHOOK_PATH=/webhook/telegram
```

Добавьте в конфиг Nginx:

```nginx
location /webhook/telegram {
    proxy_pass http://127.0.0.1:8000;
    proxy_set_header Host $host;
    proxy_set_header X-Real-IP $remote_addr;
}
```

```bash
sudo nginx -t && sudo systemctl reload nginx
docker compose restart bot
```

---

## Мониторинг и логи

### Логи бэкенда

```bash
# Docker
docker compose logs -f bot          # Live-поток
docker compose logs --tail=100 bot  # Последние 100 строк

# Файловые логи (через volume)
tail -f /opt/lettercatcher/backend/logs/bot.log
```

### Логи Nginx

```bash
sudo tail -f /var/log/nginx/access.log
sudo tail -f /var/log/nginx/error.log
```

### Health check

```bash
# Статус API
curl -s https://your-domain.com/api/v1/health | python3 -m json.tool

# Статус контейнеров
cd /opt/lettercatcher/backend && docker compose ps

# Статус Nginx
sudo systemctl status nginx
```

---

## Обновление

### Бэкенд

```bash
cd /opt/lettercatcher/backend
git pull origin main
docker compose up -d --build
# Миграции применяются автоматически
```

### Фронтенд

```bash
cd /opt/lettercatcher/frontend
git pull origin main
npm install
npm run build
sudo cp -r dist/* /var/www/lettercatcher/
```

---

## Устранение неполадок

### Фронтенд не загружается

```bash
# Проверьте, что файлы на месте
ls /var/www/lettercatcher/index.html

# Проверьте конфиг Nginx
sudo nginx -t

# Проверьте права
sudo chown -R www-data:www-data /var/www/lettercatcher
```

### WebSocket не подключается

1. Проверьте, что в конфиге Nginx есть секция для `/api/v1/ws` с `proxy_set_header Upgrade`
2. Проверьте, что CORS_ORIGINS включает домен фронтенда
3. В консоли браузера: ошибки WebSocket обычно связаны с HTTPS/WSS --- проверьте SSL

### API отвечает 502 Bad Gateway

```bash
# Бэкенд не запущен
cd /opt/lettercatcher/backend
docker compose ps
docker compose logs --tail=50 bot

# Перезапуск
docker compose restart bot
```

### CORS-ошибки в браузере

Убедитесь, что `CORS_ORIGINS` в `.env` содержит точный origin фронтенда:

```env
# Верно (с протоколом, без trailing slash):
CORS_ORIGINS=https://your-domain.com

# Неверно:
CORS_ORIGINS=your-domain.com
CORS_ORIGINS=https://your-domain.com/
```

После изменения: `docker compose restart bot`

### Не приходят письма верификации

1. Проверьте `SMTP_SERVER` и `SMTP_PORT` в `.env`
2. Для Gmail: используйте тот же App Password, что и для IMAP
3. Проверьте `APP_BASE_URL` --- должен содержать реальный домен (`https://your-domain.com`)
4. Проверьте папку "Спам" в почте получателя
