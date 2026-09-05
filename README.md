# Sirius Schedule Sync

Сервис синхронизации расписания Университета Сириус с Apple Calendar / Google Calendar.

Отдаёт ICS-фид по HTTP для подписки в любом календарном приложении.

## Группы и порты

| Группа    | Порт | URL расписания             |
|-----------|------|----------------------------|
| К0609-23  | 8080 | `http://<IP>:8080/schedule.ics` |
| К0409-24  | 8081 | `http://<IP>:8081/schedule.ics` |

## Быстрый старт на VPS

### 1. Установить Docker и Docker Compose

```bash
curl -fsSL https://get.docker.com | sh
```

### 2. Склонировать репозиторий

```bash
git clone https://github.com/Ya-Pedro/Sirius-Student-Calendar.git
cd Sirius-Student-Calendar
```

### 3. Настроить конфиги

Файлы `.env` и `.env.k0409` уже настроены. При необходимости отредактировать:

```bash
nano .env
nano .env.k0409
```

### 4. Запустить

```bash
docker-compose up -d
```

### 5. Проверить

```bash
curl http://localhost:8080/
curl http://localhost:8081/
```

## Подписка на календарь

### iPhone / iPad

1. Настройки → Календарь → Учётные записи
2. Добавить учётную запись → Другое
3. Подписной календарь
4. Вставить URL: `http://<IP>:8080/schedule.ics` (К0609-23) или `http://<IP>:8081/schedule.ics` (К0409-24)

### Google Calendar

1. Открыть calendar.google.com
2. Слева: Другие календари → + → По URL
3. Вставить URL: `http://<IP>:8080/schedule.ics` или `http://<IP>:8081/schedule.ics`

### macOS Calendar

1. Файл → Новая подписка на календарь
2. Вставить URL

## API

| Метод | URL             | Описание                          |
|-------|-----------------|-----------------------------------|
| GET   | `/`             | Информация о сервисе              |
| GET   | `/schedule.ics` | ICS-файл для подписки             |
| GET   | `/health`       | Healthcheck                       |
| GET   | `/status`       | Статус последнего обновления      |
| POST  | `/refresh`      | Принудительное обновление         |

## Управление

```bash
docker-compose up -d
docker-compose down
docker-compose logs -f schedule-sync
docker-compose logs -f schedule-sync-k0409
docker-compose restart schedule-sync
docker-compose restart schedule-sync-k0409
```

## Добавление новой группы

1. Создать файл `.env.<имя>` с нужным `GROUP_NAME`
2. Добавить сервис в `docker-compose.yml` с новым портом и ссылкой на этот env-файл
3. `docker-compose up -d`

## Параметры .env

| Параметр                | Значение по умолчанию | Описание                              |
|-------------------------|-----------------------|---------------------------------------|
| `GROUP_NAME`            | К0609-23              | Название группы                       |
| `WEEKS_AHEAD`           | 4                     | Недель вперёд                         |
| `WEEKS_BEHIND`          | 1                     | Недель назад                          |
| `UPDATE_INTERVAL_MINUTES` | 30                  | Интервал обновления (мин)             |
| `SERVER_HOST`           | 0.0.0.0               | Хост сервера                          |
| `SERVER_PORT`           | 8080                  | Порт внутри контейнера                |
| `TIMEZONE`              | Europe/Moscow         | Часовой пояс                          |
| `LOG_LEVEL`             | INFO                  | Уровень логов                         |
| `REQUEST_TIMEOUT`       | 60                    | Таймаут запросов (сек)                |
