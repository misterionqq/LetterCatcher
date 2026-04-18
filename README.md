# LetterCatcher

**Поймай важное письмо.** Система интеллектуального мониторинга корпоративной электронной почты с уведомлениями через Telegram, WebSocket и push-нотификации.

---

## Проблема

Корпоративная почта генерирует десятки писем в день: дайджесты, рассылки, уведомления от внутренних сервисов, спам. Среди этого потока легко пропустить по-настоящему важное письмо --- дедлайн по проекту, срочный вызов от руководителя, подтверждение записи на курс. Стандартные правила фильтрации в почтовых клиентах не справляются: они не понимают контекст и смысл письма.

## Решение

LetterCatcher работает как фоновый сервис, который:

1. **Подключается к почтовому ящику** по IMAP и каждые 30 секунд проверяет новые письма
2. **Применяет гибридный фильтр** --- сначала пользовательские ключевые слова (триггеры и стоп-слова), затем нейросеть (LLM через OpenRouter) для оценки важности
3. **Мгновенно уведомляет** пользователя через Telegram-бот, WebSocket (веб-интерфейс) или Firebase push (мобильное приложение)

Результат --- пользователь получает только те письма, которые требуют его внимания, и не пропускает ничего критичного.

---

## Возможности

- **Три канала уведомлений** --- Telegram-бот, WebSocket (real-time в браузере), Firebase Cloud Messaging (мобильный push)
- **AI-анализ писем** --- LLM определяет важность с объяснением причины; три уровня чувствительности (`low` / `medium` / `high`)
- **Пользовательские ключевые слова** --- триггерные слова и стоп-слова для точной настройки фильтрации
- **Кэширование ответов AI** --- MD5-хэш тела письма предотвращает повторные запросы к LLM для массовых рассылок
- **Режим "Не беспокоить"** --- важные письма сохраняются в очередь и доставляются при отключении DND
- **Два режима работы** --- `personal` (личная почта одного пользователя) и `centralized` (общий ящик, куда пересылают корпоративную почту)
- **REST API** --- полноценное API для интеграции с веб- и мобильными клиентами
- **Верификация email** --- подтверждение через ссылку, сброс пароля
- **История и статистика** --- просмотр обработанных писем, процент важных, использование AI-кэша
- **HTML-санитизация** --- защита от XSS при отображении HTML-писем (библиотека `nh3`)

---

## Архитектура

Строгая **Clean Architecture** с четырьмя изолированными слоями:

```
src/
  core/               Сущности и интерфейсы. Без зависимостей от фреймворков
  infrastructure/     БД, IMAP, OpenRouter, SMTP, Firebase. Реализация интерфейсов
  use_cases/          Бизнес-логика. Зависит только от core/interfaces
  presentation/
    telegram/         Telegram-бот (aiogram 3.x)
    api/              REST API + WebSocket (FastAPI + uvicorn)
```

```
                     +-------------------+
                     |   Presentation    |
                     | Telegram  |  API  |
                     +-----+-----+------+
                           |
                     +-----v------------+
                     |    Use Cases     |
                     | MailScanner      |
                     | ManageUsers      |
                     +-----+------------+
                           |
                     +-----v------------+
                     |      Core        |
                     | Entities         |
                     | Interfaces       |
                     +------------------+
                           ^
                     +-----+------------+
                     | Infrastructure   |
                     | DB | IMAP | LLM  |
                     +------------------+
```

**Ключевое правило:** `use_cases/` импортирует только из `core/interfaces`, никогда из `infrastructure/`.

---

## Стек технологий

| Категория | Технологии |
|-----------|-----------|
| Язык | Python 3.12, полностью асинхронный (asyncio) |
| Telegram-бот | aiogram 3.x |
| REST API | FastAPI + uvicorn |
| ORM / БД | SQLAlchemy 2.0 async, Alembic (миграции) |
| БД (dev) | SQLite (aiosqlite) |
| БД (prod) | PostgreSQL 16 (asyncpg) |
| AI / LLM | OpenRouter API (aiohttp) |
| Email | imaplib (чтение), aiosmtplib (отправка) |
| Push | Firebase Cloud Messaging |
| Аутентификация | JWT (python-jose), bcrypt |
| Безопасность | nh3 (HTML-санитизация), slowapi (rate limiting) |
| Контейнеризация | Docker, Docker Compose |
| Тесты | pytest, pytest-asyncio, aioresponses |

---

## Производительность

| Метрика | Значение |
|---------|---------|
| Интервал сканирования | 30 сек (настраивается) |
| Время обработки одного письма | < 100 мс (без AI) / 1--3 сек (с запросом к LLM) |
| Кэширование AI-ответов | MD5-хэш тела письма; повторный запрос к LLM не выполняется |
| Параллельность | asyncio --- бот, API, сканер и WebSocket работают в одном event loop |
| Потоки для блокирующих операций | IMAP, FCM, HTML-санитизация вынесены в `asyncio.to_thread` |
| Retry-политика | OpenRouter: 3 попытки с экспоненциальной задержкой (2/4/8 сек) |
| Rate limiting API | 5 req/min (регистрация), 3 req/min (токены) |
| WebSocket | Неблокирующий broadcast, автоочистка отключённых клиентов |
| Логирование | RotatingFileHandler, 5 МБ на файл, 3 ротации |

### Экономия токенов AI

- При чувствительности `low` --- LLM **не вызывается вообще**, работают только ключевые слова
- При `medium` --- LLM вызывается только если сработало триггерное слово
- Кэш по MD5 --- массовая рассылка одного текста на N пользователей потребует только 1 запрос к LLM

---

## Требования к серверу

### Минимальные (personal-режим, до 3 пользователей)

| Ресурс | Значение |
|--------|---------|
| CPU | 1 vCPU |
| RAM | 512 МБ (приложение ~150 МБ + PostgreSQL ~200 МБ) |
| Диск | 1 ГБ (Docker-образ ~350 МБ + БД + логи) |
| ОС | Linux (Ubuntu 22.04+, Debian 12+) |
| Сеть | Доступ к IMAP-серверу (порт 993) и api.openrouter.ai (443) |

### Рекомендуемые (centralized-режим, 10+ пользователей)

| Ресурс | Значение |
|--------|---------|
| CPU | 2 vCPU |
| RAM | 1 ГБ |
| Диск | 5 ГБ (с учётом роста БД и логов) |

### Поддерживаемые почтовые провайдеры

| Провайдер | IMAP-сервер | Примечание |
|-----------|------------|------------|
| Gmail | `imap.gmail.com` | Требуется App Password |
| Яндекс | `imap.yandex.ru` | Требуется пароль приложения |
| Mail.ru | `imap.mail.ru` | Требуется пароль приложения |
| Office 365 | `outlook.office365.com` | Корпоративная почта HSE и др. |
| Любой IMAP | --- | Любой сервер с поддержкой IMAP SSL |

---

## Быстрый старт

### Docker (рекомендуется)

```bash
git clone https://github.com/misterionqq/LetterCatcher.git
cd LetterCatcher

# Скопируйте и заполните конфигурацию
cp .env.example .env
nano .env

# Запуск
docker compose up -d --build

# Проверка
curl http://localhost:8000/api/v1/health
```

### Локальная разработка

```bash
git clone https://github.com/misterionqq/LetterCatcher.git
cd LetterCatcher

python3.12 -m venv venv
source venv/bin/activate
pip install -r requirements.txt

cp .env.example .env
nano .env

# Применить миграции
alembic upgrade head

# Запуск
python main.py
```

### Тесты

```bash
source venv/bin/activate
pytest -v
pytest --cov=src --cov-report=term-missing
```

Проект содержит **133 теста** в 9 тестовых модулях, покрывающих репозитории, use cases, AI-клиент, аутентификацию и форматирование уведомлений.

---

## Режимы клиента (CLIENT_MODE)

| Режим | Telegram-бот | REST API | WebSocket | Что нужно |
|-------|:-----------:|:--------:|:---------:|-----------|
| `telegram` | + | + | + | `TELEGRAM_BOT_TOKEN` |
| `web` | --- | + | + | Токен не нужен |
| `all` | + | + | + | `TELEGRAM_BOT_TOKEN` |

Подробные гайды по развёртыванию:
- **[Развёртывание с Telegram](DEPLOY_TELEGRAM.md)** --- только Telegram-бот
- **[Развёртывание с веб-интерфейсом](DEPLOY_WEB.md)** --- веб + опционально Telegram

---

## Веб-интерфейс

Для проекта существует полноценный веб-интерфейс на Vue 3:

**[LetterCatcherWeb](https://github.com/misterionqq/LetterCatcherWeb)** --- SPA-приложение с поддержкой мобильных устройств (Capacitor).

Стек фронтенда: Vue 3 (Composition API) + Vite + Pinia + Tailwind CSS.

Возможности:
- Регистрация и вход по email/паролю
- Real-time уведомления через WebSocket
- История писем с фильтрацией
- Управление ключевыми словами и чувствительностью AI
- Статистика обработки
- Адаптивный mobile-first дизайн

---

## API-документация

При запущенном сервере доступна интерактивная документация:

- **Swagger UI:** `http://localhost:8000/docs`
- **ReDoc:** `http://localhost:8000/redoc`

Основные группы эндпоинтов:

| Группа | Prefix | Описание |
|--------|--------|---------|
| Auth | `/api/v1/auth/` | Регистрация, вход, верификация email, сброс пароля |
| Profile | `/api/v1/profile/` | Профиль, чувствительность AI, DND |
| Keywords | `/api/v1/keywords/` | Триггерные и стоп-слова |
| Emails | `/api/v1/emails/` | История, статистика |
| Notifications | `/api/v1/notifications/` | Отложенные уведомления (DND) |
| WebSocket | `/api/v1/ws` | Real-time push |
| Health | `/api/v1/health` | Статус сервера |

---

## Структура проекта

```
LetterCatcher/
  main.py                     Точка входа, wiring зависимостей
  docker-compose.yml          PostgreSQL + приложение
  Dockerfile                  python:3.12-slim
  entrypoint.sh               Миграции + запуск
  alembic/                    Миграции БД
  src/
    core/
      entities.py             User, Keyword, EmailMessage, PendingNotification
      interfaces.py           IUserRepository, IEmailRepository, IAIAnalyzer, ...
    infrastructure/
      config.py               Загрузка .env
      imap_client.py          Чтение почты (IMAP)
      openrouter_client.py    AI-анализ (OpenRouter)
      smtp_service.py         Отправка email (SMTP)
      fcm_service.py          Push-уведомления (Firebase)
      telegram_auth.py        Проверка Telegram Login Widget
      database/
        models.py             SQLAlchemy-модели
        setup.py              Инициализация движка БД
      repositories/           Реализация интерфейсов
    use_cases/
      mail_scanner.py         Пайплайн обработки писем
      manage_users.py         Управление пользователями
    presentation/
      telegram/
        handlers.py           Команды бота (/start, /profile, /dnd, ...)
        states.py             FSM-состояния
      api/
        app.py                Фабрика FastAPI
        routes.py             Эндпоинты
        security.py           JWT
        schemas.py            Pydantic-модели
        ws_manager.py         WebSocket-менеджер
        rate_limit.py         Rate limiting
        dependencies.py       DI
  tests/                      133 теста (pytest + pytest-asyncio)
```

---

## Лицензия

MIT
