# MarketTracker — Telegram-бот для мониторинга цен на маркетплейсах

Асинхронный Telegram-бот, который отслеживает цену товара по ссылке
(Авито, Яндекс Маркет, Ozon, Wildberries, Auto.ru), присылает уведомления
при падении/росте цены или достижении целевой цены и строит графики
истории цен по команде.

## Возможности

- Приём ссылки на товар и определение маркетплейса по URL.
- Парсинг названия и текущей цены (JSON-LD / OpenGraph / микроразметка).
- Кастомные условия уведомлений:
  - 🎯 целевая цена (`new_price <= target_price`);
  - 📉 падение на X % от предыдущей проверенной цены;
  - 📈 рост на Y % от предыдущей проверенной цены;
  - ⚠️ объявление удалено (404 / цена не определена) — трек деактивируется.
- Фоновая проверка цен каждые 15 минут (APScheduler `AsyncIOScheduler`).
- Защита от спама уведомлений: не чаще одного алерта по одному условию
  в течение `ALERT_COOLDOWN_HOURS` (по умолчанию 24 часа).
- График истории цены (последние 14 замеров) в PNG по команде `/history`.
- Полноценное веб-приложение (Telegram Mini App): список товаров с фото,
  графики, добавление и настройка треков.
- Graceful fallback на детерминированные mock-данные, если маркетплейс
  блокирует запрос (403/Cloudflare/таймаут) — бот не падает.

## Технологии

- Python 3.11+ (строгая типизация)
- aiogram 3.x
- SQLAlchemy 2.x + aiosqlite
- APScheduler 3.x (AsyncIOScheduler)
- httpx + curl_cffi + BeautifulSoup4 + lxml
- matplotlib (PNG-графики)
- FastAPI + uvicorn (Telegram Mini App)
- pydantic + pydantic-settings
- loguru (ротация логов)
- python-dotenv

## Структура проекта

```
.
├── bot/
│   ├── main.py              # точка входа
│   ├── handlers/            # start, track, commands, callbacks, states
│   ├── keyboards/           # inline + reply клавиатуры
│   └── middlewares/         # rate limiting, обработка ошибок
├── core/
│   ├── tracker_service.py   # бизнес-логика проверки условий алертов
│   └── history_service.py   # генерация графиков (matplotlib)
├── parser/
│   ├── base_parser.py       # ABC
│   ├── parser_factory.py    # фабрика парсеров
│   ├── avito_parser.py      # Авито
│   ├── yandex_parser.py     # Яндекс Маркет
│   ├── stub_parsers.py      # Ozon / WB / Auto.ru (заглушки с моками)
│   ├── http.py              # общие HTTP-клиенты (httpx + curl_cffi)
│   ├── extract.py           # общие хелперы извлечения данных
│   └── mock_data.py         # детерминированные mock-данные
├── db/
│   ├── database.py          # engine, sessionmaker, init_db
│   ├── enums.py             # Marketplace, AlertType
│   ├── models.py            # SQLAlchemy-модели
│   └── repositories/        # user_repo, track_repo, history_repo, alert_repo
├── scheduler/
│   └── jobs.py              # фоновая задача проверки цен
├── web/
│   ├── api.py               # FastAPI-бэкенд Mini App
│   ├── auth.py              # валидация Telegram initData
│   └── static/index.html    # фронтенд Mini App
├── utils/
│   ├── logger.py            # loguru
│   ├── url_validator.py     # валидация и классификация ссылок
│   └── formatting.py        # форматирование цен/процентов
├── config/
│   └── settings.py          # Pydantic BaseSettings
├── .env.example
├── Dockerfile
├── docker-compose.yml
└── requirements.txt
```

## Быстрый старт (локально)

1. Создайте виртуальное окружение и установите зависимости:

   ```bash
   python3.11 -m venv .venv
   source .venv/bin/activate
   pip install -r requirements.txt
   ```

2. Настройте переменные окружения:

   ```bash
   cp .env.example .env
   # отредактируйте .env и вставьте BOT_TOKEN от @BotFather
   ```

3. Запустите бота:

   ```bash
   python -m bot.main
   ```

## Запуск через Docker

```bash
cp .env.example .env   # впишите BOT_TOKEN
docker compose up --build -d
```

Логи и SQLite-база хранятся в смонтированных томах `./logs` и `./data`.

## Telegram Mini App (веб-приложение)

Бот включает веб-фронтенд (`web/static/index.html`) и FastAPI-бэкенд
(`web/api.py`), запускаемые тем же процессом на `http://127.0.0.1:8000`.

Telegram Mini Apps требуют **HTTPS**. Для локального запуска:

1. Поднимите публичный HTTPS-туннель к порту 8000, например cloudflared:
   ```bash
   cloudflared tunnel --url http://127.0.0.1:8000
   ```
   (или `ngrok http 8000`).
2. Полученный `https://...` укажите в `.env`:
   ```
   WEBAPP_URL=https://your-tunnel.trycloudflare.com
   ```
3. В BotFather у бота задайте **Menu Button** → Web App URL (тот же `WEBAPP_URL`).
   Бот установит кнопку меню автоматически при старте, если `WEBAPP_URL` задан.
4. Для отладки в обычном браузере (без Telegram):
   ```
   WEBAPP_DEV_MODE=true
   WEBAPP_DEV_USER_ID=ВАШ_TELEGRAM_ID
   ```
   и откройте `http://127.0.0.1:8000`.

## Переменные окружения

| Переменная | По умолчанию | Описание |
|---|---|---|
| `BOT_TOKEN` | — | Токен бота от @BotFather (обязателен) |
| `DB_URL` | `sqlite+aiosqlite:///data/market_tracker.db` | URL БД |
| `SCHEDULER_INTERVAL_MINUTES` | `15` | Интервал проверки цен |
| `REQUEST_TIMEOUT_SECONDS` | `15.0` | Таймаут HTTP-запросов парсера |
| `USER_AGENT` | Chrome UA | User-Agent парсера |
| `LOG_LEVEL` | `INFO` | Уровень логирования в консоль |
| `LOG_DIR` | `logs` | Папка логов |
| `LOG_ROTATION` | `10 MB` | Размер ротации логов |
| `LOG_RETENTION` | `7 days` | Срок хранения логов |
| `ALERT_COOLDOWN_HOURS` | `24` | Мин. интервал между алертами по одному условию |
| `WEBAPP_URL` | — | Публичный HTTPS-адрес Mini App (для кнопки меню) |
| `WEBAPP_HOST` | `127.0.0.1` | Хост веб-приложения |
| `WEBAPP_PORT` | `8000` | Порт веб-приложения |
| `WEBAPP_DEV_MODE` | `false` | Dev-режим: вход без initData (по `X-User-Id`) |
| `WEBAPP_DEV_USER_ID` | `0` | ID пользователя в dev-режиме |

## Команды бота

| Команда | Описание |
|---|---|
| `/start` | Приветствие и меню |
| `/help` | Справка |
| `/track` | Начать отслеживание (или просто отправьте ссылку) |
| `/list` | Список треков с inline-кнопками «Остановить» |
| `/history <id>` | PNG-график истории цены (последние 14 замеров) |
| `/settings` | Текущие настройки алертов |
| `/stop <id>` | Остановить трек |
| `/cancel` | Отменить настройку |

## Как это работает

1. Пользователь отправляет ссылку. `utils/url_validator` классифицирует
   маркетплейс, `ParserFactory` возвращает нужный парсер.
2. Парсер получает реальные данные: Авито — через мобильный API, Яндекс
   Маркет — через карточку товара (оба через `curl_cffi` с имитацией
   браузерного TLS). Название/цена извлекаются из JSON-LD/meta. При
   блокировке — fallback на детерминированные mock-данные.
3. Пользователь настраивает условия через inline-кнопки (FSM-диалог).
4. Каждые 15 минут `scheduler/jobs.py` обходит активные треки, сохраняет
   новую цену в `PriceHistory` и проверяет условия в `core/tracker_service`.
5. При срабатывании (и если не было алерта в течение кулдауна) бот шлёт
   уведомление и пишет запись в `AlertLog`.

## Деплой в облако (Render + PostgreSQL)

`render.yaml` — Blueprint: создаёт веб-сервис (бот + Mini App) и бесплатную
PostgreSQL-базу, а её строку подключения автоматически пробрасывает в
`DATABASE_URL` (приложение само переводит её в `postgresql+asyncpg`).

1. Запушьте: `git push origin main`.
2. На **render.com** → New → **Blueprint** → подключите репозиторий.
3. В дашборде задайте только секрет:
   - `BOT_TOKEN` — токен бота.
4. `WEBAPP_URL` задавать не нужно — берётся из `RENDER_EXTERNAL_URL`.
   Кнопка меню бота настраивается автоматически при старте.
5. `KEEP_ALIVE=true` уже прописан — приложение пингует своё `/healthz` каждые
   5 минут, чтобы бесплатный сервис Render не «засыпал» и бот продолжал
   проверять цены.

⚠️ На проде `WEBAPP_DEV_MODE=false` (уже прописан в `render.yaml`) — вход
строго через Telegram `initData`.

> Ограничения бесплатного тарифа Render: PostgreSQL живёт ~30 дней (потом
> данные сбросятся) и сервис спит без входящего трафика (отсюда keep-alive).
> Для долгосрочного хранения подойдёт внешняя БД Neon/Supabase — достаточно
> задать её строку в `DATABASE_URL`.

## Примечания и ограничения MVP

- **Парсинг Авито.** Используется мобильный API
  `m.avito.ru/api/1/card/items/{id}` через `curl_cffi` (имитация браузерного
  TLS) — отдаёт реальные название и цену. Резервно — парсинг HTML и mock.
- **Парсинг Яндекса.** Карточка товара через `curl_cffi` + JSON-LD/OpenGraph.
- **Парсинг прочих.** Ozon / WB / Auto.ru в MVP — заглушки (mock). Для
  массового парсинга может потребоваться резидентный прокси
  (`PARSER_PROXY_URL`) — поддержка уже добавлена в `parser/http.py`.
- **Хранилище FSM и БД.** FSM — в памяти (`MemoryStorage`), БД — SQLite
  локально / PostgreSQL в облаке (`DATABASE_URL`). Для многопользовательского
  продакшена FSM стоит перенести в Redis.
- **Графики.** Кириллица поддерживается шрифтом DejaVu Sans (входит в
  matplotlib); используется headless-бэкенд `Agg`.
- **Миграции.** В MVP таблицы создаются через `Base.metadata.create_all`;
  для продакшена рекомендуется Alembic.

## Демонстрация без реального парсинга

Бот полностью работоспособен даже если все реальные запросы блокируются:
каждый URL даёт стабильный mock-товар и медленно меняющуюся цену, поэтому
алерты и графики можно показать «вживую» без внешних сервисов.

## Лицензия

См. файл `LICENSE`.
