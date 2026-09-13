# Project context
`izbushka-web-core` — центральный веб-сервер робота-консультанта «Избушка» на FastAPI. Обеспечивает REST API, WebSocket-панель оператора, VoIP-мост, видеотрансляцию и маршрутизацию команд между реальным роботом (STM32) и Unity-симулятором.

## What to review and what to ignore
Ревьюить: `api/`, `transport/`, `services/`, `static/scripts` (JS), `main.py`, `settings.py`, `authorization.py`, шаблоны при изменении логики.
Игнорировать: `.github/`, CI-конфиги, сабмодуль `com_link_rt` (клиент протокола, живёт в своём репозитории `com_link_rt_client`), `__pycache__`, `logs/`, `database/` (бинарные/сгенерированные файлы), статические ассеты без логики (картинки, шрифты).
Если в диффе нет ревьюабельного кода — так и напиши в summary, не выдумывай замечания.

## Always read the PR description and comments
Перед ревью прочитай PR DESCRIPTION из PR / GIT CONTEXT и комментарии в pr-comments/others/. Не поднимай повторно то, что там уже решено или объяснено; объяснение снимает придирку, но не отменяет реальный баг.

## Stack
Python 3.12, FastAPI (+ uvicorn, websockets, slowapi), Pydantic-схемы, PyYAML для конфигов, OpenCV для видео, pyserial для связи со STM32, JS/AudioWorklet на фронтенде (voice.js, voice-capture/playback-processor.js).

## Code style
CI использует flake8: `flake8 . --max-line-length=120 --exclude=__pycache__,.git,com_link_rt` (см. `.github/workflows/lint.yml`). Значит: строки до 120 символов, сабмодуль `com_link_rt` не проверяется и не должен блокировать ревью по стилю. Асинхронный код — обработчики API и WS должны оставаться `async def` без блокирующих вызовов внутри event loop.

## Architecture and patterns
- `transport/bus.py` — шина `TransportBus` (Chain of Responsibility): подписчики `ComLinkSubscriber` (приоритет 10, реальное железо), `VirtualLinkSubscriber` (приоритет 50, Unity-симулятор через TCP), `ConsoleLoggerSubscriber` (приоритет 100, фоллбек-логирование).
- `api/` — REST/WS эндпоинты (`com_link_rt_api.py`, `voice_link.py`, `voice_broadcast.py`, `webcam_api.py`, `websockets.py`).
- `services/` — бизнес-логика (эмоции, датчики).
- Lifespan: при `production: true` в `settings.yml` сервер блокирует старт до подключения `VoiceLink` (таймаут 60 сек), иначе `RuntimeError`.

## Dependencies on other parts of the system
- COM-LINK-RT бинарный протокол по USB-Serial (115200) со STM32-прошивкой [COM-LINK-RT](https://github.com/Emeteil/COM-LINK-RT) через клиентскую библиотеку [com_link_rt_client](https://github.com/Emeteil/com_link_rt_client) (сабмодуль `com_link_rt`).
- TCP JSON-протокол VirtualLink на порт 5470 к [izbushka_simulation](https://github.com/Emeteil/izbushka_simulation) (Unity).
- WebSocket VoiceLink (`/api/voice/link`) и Broadcast VoIP (`/api/broadcast/voice`) — с [izbushka-voice-interface](https://github.com/Emeteil/izbushka-voice-interface).

## Review checklist
- Изменение формата команд/JSON-сообщений VirtualLink или событий VoiceLink (`voice.*`) без соответствующего изменения в `izbushka_simulation` или `izbushka-voice-interface` — обязательно отметить и напомнить синхронизировать другую сторону.
- Изменение `packetType`/структуры пакета в коде работы с `com_link_rt` без учёта версии протокола COM-LINK-RT v2 — потенциальная несовместимость с прошивкой STM32.
- Новый импорт без добавления зависимости в `requirements.txt`, либо удалённая зависимость, оставшаяся в файле.
- Новые ключи конфигурации без добавления в `settings.yml` / `.env` пример / `install.sh`.
- Блокирующие вызовы (синхронный I/O, `time.sleep`, тяжёлые вычисления) внутри async-обработчиков FastAPI/WS.
- Секреты/токены (MASTER_TOKEN и т.п.) в коде или логах.
- Новые REST/WS эндпоинты без проверки авторизации, если остальные защищены.
- Изменения в `voice.js`/AudioWorklet, ломающие таймингы буфера (`minBufferChunks`, размер чанка 320 байт / 20 мс).
