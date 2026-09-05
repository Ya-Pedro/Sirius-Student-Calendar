# Sirius Schedule Sync

Сервис синхронизации расписания Университета Сириус с Apple Calendar / Google Calendar.

## Группы и URL

| Группа   | URL                                              |
|----------|--------------------------------------------------|
| К0609-23 | `https://pedro.ittori.ru:8080/schedule.ics`      |
| К0409-24 | `https://pedro.ittori.ru:8081/schedule.ics`      |

## Установка на сервер

### 1. Установить Docker

```bash
curl -fsSL https://get.docker.com | sh
```

### 2. Склонировать репозиторий

```bash
git clone https://github.com/Ya-Pedro/Sirius-Student-Calendar.git
cd Sirius-Student-Calendar
```

### 3. Настроить .env файлы

```bash
nano .env
nano .env.k0409
```

### 4. Проброс портов на роутере

| Внешний порт | Внутренний порт | Протокол | Назначение        |
|--------------|-----------------|----------|--------------------|
| 80           | 80              | TCP      | Let's Encrypt      |
| 8080         | 8080            | TCP      | HTTPS К0609-23     |
| 8081         | 8081            | TCP      | HTTPS К0409-24     |

### 5. Получить SSL-сертификат и запустить

```bash
chmod +x init-ssl.sh
./init-ssl.sh
```

### 6. Продление сертификата

```bash
docker-compose run --rm certbot renew
docker-compose restart nginx
```

## Подписка на календарь

### iPhone / iPad

1. Настройки → Календарь → Учётные записи
2. Добавить учётную запись → Другое
3. Подписной календарь
4. URL: `https://pedro.ittori.ru:8080/schedule.ics` или `https://pedro.ittori.ru:8081/schedule.ics`

### Google Calendar

1. calendar.google.com
2. Другие календари → + → По URL
3. Вставить URL

### macOS Calendar

1. Файл → Новая подписка на календарь
2. Вставить URL

## API

| Метод | URL             | Описание                     |
|-------|-----------------|------------------------------|
| GET   | `/`             | Информация о сервисе         |
| GET   | `/schedule.ics` | ICS-файл для подписки        |
| GET   | `/health`       | Healthcheck                  |
| GET   | `/status`       | Статус последнего обновления |
| POST  | `/refresh`      | Принудительное обновление    |

## Управление

```bash
docker-compose up -d
docker-compose down
docker-compose logs -f nginx
docker-compose logs -f schedule-sync
docker-compose logs -f schedule-sync-k0409
docker-compose restart
```

## Добавление новой группы

1. Создать `.env.<имя>` с нужным `GROUP_NAME`
2. Добавить сервис в `docker-compose.yml`
3. Добавить блок `server` в `nginx.conf` с новым портом
4. Пробросить порт на роутере
5. `docker-compose up -d && docker-compose restart nginx`

## Параметры .env

| Параметр                  | По умолчанию  | Описание                |
|---------------------------|---------------|-------------------------|
| `GROUP_NAME`              | К0609-23      | Название группы         |
| `WEEKS_AHEAD`             | 4             | Недель вперёд           |
| `WEEKS_BEHIND`            | 1             | Недель назад            |
| `UPDATE_INTERVAL_MINUTES` | 30            | Интервал обновления     |
| `SERVER_HOST`             | 0.0.0.0       | Хост сервера            |
| `SERVER_PORT`             | 8080          | Порт внутри контейнера  |
| `TIMEZONE`                | Europe/Moscow | Часовой пояс            |
| `LOG_LEVEL`               | INFO          | Уровень логов           |
| `REQUEST_TIMEOUT`         | 60            | Таймаут запросов (сек)  |
