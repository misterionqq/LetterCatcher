# Развёртывание LetterCatcher с Telegram-ботом

Пошаговый гайд по запуску LetterCatcher на сервере в режиме `CLIENT_MODE=telegram` --- только Telegram-бот без веб-интерфейса.

---

## Содержание

- [Что вы получите](#что-вы-получите)
- [Требования](#требования)
- [Шаг 1. Создание Telegram-бота](#шаг-1-создание-telegram-бота)
- [Шаг 2. Настройка почтового ящика](#шаг-2-настройка-почтового-ящика)
- [Шаг 3. Получение ключа OpenRouter](#шаг-3-получение-ключа-openrouter)
- [Шаг 4. Подготовка сервера](#шаг-4-подготовка-сервера)
- [Шаг 5. Конфигурация .env](#шаг-5-конфигурация-env)
- [Шаг 6. Запуск через Docker](#шаг-6-запуск-через-docker)
- [Шаг 7. Проверка работы](#шаг-7-проверка-работы)
- [Альтернатива: запуск без Docker](#альтернатива-запуск-без-docker)
- [Настройка Webhook (опционально)](#настройка-webhook-опционально)
- [Команды бота](#команды-бота)
- [Мониторинг и логи](#мониторинг-и-логи)
- [Обновление](#обновление)
- [Устранение неполадок](#устранение-неполадок)

---

## Что вы получите

- Бот мониторит ваш почтовый ящик каждые 30 секунд
- Важные письма приходят в Telegram с указанием причины важности
- Управление ключевыми словами и настройками прямо через бота
- Работает на минимальном VPS (1 vCPU, 512 МБ RAM)

---

## Требования

| Требование | Минимум |
|-----------|---------|
| Сервер | VPS с 1 vCPU, 512 МБ RAM, 1 ГБ диска |
| ОС | Ubuntu 22.04+ / Debian 12+ (любой Linux с Docker) |
| Docker | Docker Engine 24+ и Docker Compose v2 |
| Сеть | Исходящий доступ к портам 443 (OpenRouter API) и 993 (IMAP SSL) |

---

## Шаг 1. Создание Telegram-бота

1. Откройте Telegram и найдите [@BotFather](https://t.me/BotFather)
2. Отправьте `/newbot`
3. Введите имя бота (например, `My LetterCatcher Bot`)
4. Введите username бота (например, `my_lettercatcher_bot`)
5. Скопируйте **токен** --- строка вида `7123456789:AAH...`
6. Настройте команды бота (необязательно, но удобно):

```
/setcommands
```

Отправьте BotFather список:

```
start - Запустить бота
profile - Мой профиль
add - Добавить ключевое слово
remove - Удалить ключевое слово
dnd - Режим "Не беспокоить"
sensitivity - Чувствительность AI
history - История писем
stats - Статистика
email - Привязать email
link - Привязать веб-аккаунт
```

7. Узнайте свой Telegram ID --- напишите боту [@userinfobot](https://t.me/userinfobot) и скопируйте число из поля `Id`

---

## Шаг 2. Настройка почтового ящика

Для подключения к почте по IMAP нужен **пароль приложения** (App Password), а не обычный пароль.

### Gmail

1. Включите двухфакторную аутентификацию: [myaccount.google.com/security](https://myaccount.google.com/security)
2. Создайте пароль приложения: [myaccount.google.com/apppasswords](https://myaccount.google.com/apppasswords)
3. Выберите "Другое", введите имя `LetterCatcher`, нажмите "Создать"
4. Скопируйте 16-символьный пароль (вида `abcd efgh ijkl mnop`)

IMAP-сервер: `imap.gmail.com`

### Яндекс

1. Перейдите в [id.yandex.ru/security/app-passwords](https://id.yandex.ru/security/app-passwords)
2. Создайте пароль приложения для "Почта"
3. Скопируйте пароль

IMAP-сервер: `imap.yandex.ru`

### Mail.ru

1. Перейдите в настройки почты -> Пароли приложений
2. Создайте пароль для IMAP-клиента

IMAP-сервер: `imap.mail.ru`

### Office 365 (HSE, корпоративная почта)

IMAP-сервер: `outlook.office365.com`

> Настройки зависят от политик организации. Обратитесь к IT-отделу, если IMAP заблокирован.

---

## Шаг 3. Получение ключа OpenRouter

1. Зарегистрируйтесь на [openrouter.ai](https://openrouter.ai/)
2. Перейдите в [openrouter.ai/keys](https://openrouter.ai/keys)
3. Создайте API-ключ и скопируйте его

**Выбор модели:**

| Модель | Стоимость | Рекомендация |
|--------|-----------|-------------|
| `google/gemini-2.5-flash-preview-05-20` | Бесплатно | Для начала работы |
| `meta-llama/llama-3-8b-instruct:free` | Бесплатно | Альтернатива |
| `openai/gpt-4o-mini` | ~$0.15/1M токенов | Высокое качество |
| `anthropic/claude-3-haiku` | ~$0.25/1M токенов | Высокое качество |

> При чувствительности `low` нейросеть не вызывается --- работают только ключевые слова. Бесплатные модели подходят для personal-режима.

---

## Шаг 4. Подготовка сервера

```bash
# Подключение к серверу
ssh user@your-server-ip

# Установка Docker (если не установлен)
curl -fsSL https://get.docker.com | sh
sudo usermod -aG docker $USER
# Перелогиньтесь для применения группы
exit
ssh user@your-server-ip

# Проверка
docker --version
docker compose version

# Клонирование репозитория
git clone https://github.com/misterionqq/LetterCatcher.git
cd LetterCatcher
```

---

## Шаг 5. Конфигурация .env

```bash
cp .env.example .env
nano .env
```

Заполните **только необходимые** поля (остальное --- значения по умолчанию):

```env
# === ОБЯЗАТЕЛЬНЫЕ ===

CLIENT_MODE=telegram
APP_MODE=personal
ADMIN_TG_ID=123456789              # Ваш Telegram ID из @userinfobot

IMAP_SERVER=imap.gmail.com         # Ваш IMAP-сервер
EMAIL_USER=your-email@gmail.com    # Ваш email
EMAIL_PASSWORD=abcd efgh ijkl mnop # Пароль приложения

TELEGRAM_BOT_TOKEN=7123456789:AAH...  # Токен из BotFather

OPENROUTER_API_KEY=sk-or-...       # Ключ OpenRouter
LLM_MODEL=google/gemini-2.5-flash-preview-05-20

# === РЕКОМЕНДУЕТСЯ ИЗМЕНИТЬ ===

JWT_SECRET_KEY=сгенерируйте-случайную-строку
# Генерация: python3 -c "import secrets; print(secrets.token_urlsafe(32))"
```

> **Режим `centralized`:** если вы хотите мониторить общий ящик для нескольких пользователей, установите `APP_MODE=centralized`. В этом режиме пользователи пересылают свою почту на `EMAIL_USER`, а система определяет адресата по заголовкам пересылки.

---

## Шаг 6. Запуск через Docker

```bash
# Сборка и запуск в фоне
docker compose up -d --build

# Проверка статуса
docker compose ps

# Ожидаемый вывод:
# NAME              STATUS                   PORTS
# lettercatcher-db  Up (healthy)
# lettercatcher-bot Up (healthy)             0.0.0.0:8000->8000/tcp
```

При первом запуске автоматически:
- Создаётся база PostgreSQL
- Применяются миграции Alembic
- Запускается бот в режиме polling

---

## Шаг 7. Проверка работы

### Проверка API

```bash
curl http://localhost:8000/api/v1/health
# {"status":"ok","database":"ok","scanner":"running"}
```

### Проверка бота

1. Откройте Telegram и найдите вашего бота по username
2. Отправьте `/start` --- бот должен зарегистрировать вас и ответить приветствием
3. Отправьте `/profile` --- проверьте, что ваш Telegram ID совпадает с `ADMIN_TG_ID`
4. Отправьте `/add` и добавьте ключевое слово (например, `дедлайн`)
5. Отправьте тестовое письмо со словом "дедлайн" на мониторимый ящик
6. Через ~30 секунд бот должен прислать уведомление

---

## Альтернатива: запуск без Docker

Если на сервере нет Docker или вы хотите минимальную конфигурацию:

```bash
# Установка Python 3.12
sudo apt update
sudo apt install python3.12 python3.12-venv

# Подготовка проекта
cd LetterCatcher
python3.12 -m venv venv
source venv/bin/activate
pip install -r requirements.txt

# Конфигурация
cp .env.example .env
nano .env
# Для SQLite (без PostgreSQL):
# DATABASE_URL=sqlite+aiosqlite:///app.db

# Миграции
alembic upgrade head

# Запуск
python main.py
```

### Запуск как systemd-сервис

Создайте файл `/etc/systemd/system/lettercatcher.service`:

```ini
[Unit]
Description=LetterCatcher Email Monitor
After=network.target

[Service]
Type=simple
User=lettercatcher
WorkingDirectory=/opt/LetterCatcher
Environment=PATH=/opt/LetterCatcher/venv/bin:/usr/bin
ExecStart=/opt/LetterCatcher/venv/bin/python main.py
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
```

```bash
sudo systemctl daemon-reload
sudo systemctl enable lettercatcher
sudo systemctl start lettercatcher
sudo systemctl status lettercatcher
```

---

## Настройка Webhook (опционально)

По умолчанию бот работает в режиме **polling** (сам опрашивает Telegram). Для продакшена с высокой нагрузкой можно переключиться на **webhook**:

1. Настройте SSL (нужен домен с HTTPS)
2. Добавьте в `.env`:

```env
WEBHOOK_URL=https://your-domain.com
WEBHOOK_PATH=/webhook/telegram
```

3. Перезапустите: `docker compose restart bot`

> Webhook требует, чтобы сервер был доступен из интернета по HTTPS. Для personal-режима polling работает отлично.

---

## Команды бота

| Команда | Описание |
|---------|---------|
| `/start` | Регистрация и приветствие |
| `/profile` | Текущие настройки профиля |
| `/add` | Добавить триггерное ключевое слово |
| `/remove` | Удалить ключевое слово |
| `/dnd` | Переключить режим "Не беспокоить" |
| `/sensitivity` | Изменить чувствительность AI (low/medium/high) |
| `/history` | Последние обработанные письма |
| `/stats` | Статистика обработки |
| `/email` | Привязать email к профилю |
| `/link` | Привязать веб-аккаунт к Telegram |

---

## Мониторинг и логи

### Просмотр логов

```bash
# Docker
docker compose logs -f bot          # Логи приложения (live)
docker compose logs -f db           # Логи PostgreSQL
docker compose logs --tail=100 bot  # Последние 100 строк

# Без Docker
tail -f logs/bot.log
```

### Типичные записи в логах

```
INFO - LetterCatcher запущен! Режим: telegram (polling), API порт: 8000
INFO - Сканер: проверка новых писем...
INFO - Найдено 3 непрочитанных письма
INFO - Письмо от boss@company.com: важное (AI: горящий дедлайн)
INFO - Уведомление отправлено в Telegram: user_id=123456789
```

### Health check

```bash
# Статус сервера
curl http://localhost:8000/api/v1/health

# Статус контейнеров
docker compose ps
```

---

## Обновление

```bash
cd LetterCatcher

# Получение обновлений
git pull origin main

# Пересборка и перезапуск
docker compose up -d --build

# Миграции применяются автоматически через entrypoint.sh
```

---

## Устранение неполадок

### Бот не отвечает

```bash
# Проверьте логи
docker compose logs --tail=50 bot

# Проверьте, что токен верный
# В логах будет ошибка "Unauthorized" при неверном токене

# Проверьте, что бот запущен
docker compose ps
```

### Не подключается к почте

```bash
# Проверьте IMAP-сервер вручную
python3 -c "
import imaplib
m = imaplib.IMAP4_SSL('imap.gmail.com')
m.login('your-email@gmail.com', 'app-password')
print('OK')
m.logout()
"
```

Частые причины:
- Используется обычный пароль вместо пароля приложения
- Не включена двухфакторная аутентификация (Gmail)
- IMAP отключён в настройках почты
- Блокировка порта 993 на сервере

### Нет уведомлений о письмах

1. Проверьте `/profile` --- ключевые слова должны быть добавлены
2. Проверьте, что DND выключен (`/dnd`)
3. Убедитесь, что письмо непрочитанное в ящике (сканер обрабатывает только UNSEEN)
4. При `sensitivity=low` --- AI не вызывается, работают только ключевые слова

### База данных не запускается

```bash
# Проверьте, что порт 5432 не занят
docker compose logs db

# Пересоздание БД (ВНИМАНИЕ: данные будут удалены)
docker compose down -v
docker compose up -d --build
```
