"""
Веб-сервер сервиса расписания Университета Сириус.

Предоставляет ICS-фид по HTTP для подписки в Apple Calendar.
Автоматически обновляет расписание в фоновом режиме.

Эндпоинты:
  GET /               — информация о сервисе
  GET /schedule.ics   — ICS-файл для подписки в календаре
  GET /health         — healthcheck
  GET /status         — статус последнего обновления
  POST /refresh       — принудительное обновление расписания
"""

import os
import logging
import threading
from datetime import datetime
from typing import Optional

import uvicorn
from fastapi import FastAPI, Response
from fastapi.responses import JSONResponse, PlainTextResponse
from apscheduler.schedulers.background import BackgroundScheduler

from config import Config
from scraper import SiriusScheduleScraper, ScheduleEvent
from ics_generator import ICSGenerator

config = Config()
logging.basicConfig(
    level=getattr(logging, config.LOG_LEVEL.upper(), logging.INFO),
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger("server")

app = FastAPI(
    title="Sirius Schedule Sync",
    description="Сервис синхронизации расписания Университета Сириус с Apple Calendar",
    version="1.0.0",
)

_current_ics: str = ""
_last_update: Optional[datetime] = None
_last_error: Optional[str] = None
_events_count: int = 0
_update_lock = threading.Lock()

scraper = SiriusScheduleScraper(config)
ics_gen = ICSGenerator(config)


def update_schedule() -> None:
    """Обновить расписание: скачать с сайта и сгенерировать ICS."""
    global _current_ics, _last_update, _last_error, _events_count

    with _update_lock:
        logger.info("🔄 Начало обновления расписания...")
        try:
            fresh_scraper = SiriusScheduleScraper(config)
            events = fresh_scraper.fetch_schedule()

            if events:
                _current_ics = ics_gen.generate(events)
                _events_count = len(events)
                _last_update = datetime.now()
                _last_error = None
                logger.info(
                    "✅ Расписание обновлено: %d событий", len(events)
                )
            else:
                _last_update = datetime.now()
                _last_error = "Не найдено событий (возможно, расписание ещё не опубликовано)"
                logger.warning("⚠️ Событий не найдено")

        except Exception as e:
            _last_error = str(e)
            logger.error("❌ Ошибка обновления: %s", e, exc_info=True)




@app.get("/", response_class=JSONResponse)
async def root():
    """Информация о сервисе."""
    return {
        "service": "Sirius Schedule Sync",
        "group": config.GROUP_NAME,
        "calendar_name": config.CALENDAR_NAME,
        "subscribe_url": "/schedule.ics",
        "status": "running",
        "last_update": _last_update.isoformat() if _last_update else None,
        "events_count": _events_count,
        "update_interval_minutes": config.UPDATE_INTERVAL_MINUTES,
        "instructions": {
            "iPhone": (
                "Настройки → Календарь → Учётные записи → "
                "Добавить учётную запись → Другое → "
                "Подписной календарь → Вставить URL"
            ),
        },
    }


@app.get("/schedule.ics")
async def get_ics():
    """
    ICS-файл для подписки в Apple Calendar.

    Этот URL нужно добавить в настройках календаря на iPhone.
    """
    if not _current_ics:
        update_schedule()

    if not _current_ics:
        return PlainTextResponse(
            "Расписание пока не загружено. Попробуйте позже.",
            status_code=503,
        )

    return Response(
        content=_current_ics,
        media_type="text/calendar; charset=utf-8",
        headers={
            "Content-Disposition": 'attachment; filename="schedule.ics"',
            "Cache-Control": f"max-age={config.UPDATE_INTERVAL_MINUTES * 60}, public",
            "X-Events-Count": str(_events_count),
            "X-Last-Update": _last_update.isoformat() if _last_update else "",
        },
    )


@app.get("/health")
async def health():
    """Healthcheck для Docker и мониторинга."""
    return {"status": "ok", "timestamp": datetime.now().isoformat()}


@app.get("/status")
async def status():
    """Подробный статус последнего обновления."""
    return {
        "group": config.GROUP_NAME,
        "last_update": _last_update.isoformat() if _last_update else None,
        "events_count": _events_count,
        "last_error": _last_error,
        "update_interval_minutes": config.UPDATE_INTERVAL_MINUTES,
        "has_data": bool(_current_ics),
    }


@app.post("/refresh")
async def refresh():
    """Принудительно обновить расписание."""
    update_schedule()
    return {
        "status": "updated" if not _last_error else "error",
        "events_count": _events_count,
        "error": _last_error,
    }



def start_scheduler():
    """Запустить фоновое обновление расписания."""
    scheduler = BackgroundScheduler()
    scheduler.add_job(
        update_schedule,
        "interval",
        minutes=config.UPDATE_INTERVAL_MINUTES,
        id="schedule_update",
        name="Обновление расписания",
        max_instances=1,
        coalesce=True,
    )
    scheduler.start()
    logger.info(
        "⏰ Планировщик запущен: обновление каждые %d мин.",
        config.UPDATE_INTERVAL_MINUTES,
    )
    return scheduler


@app.on_event("startup")
async def on_startup():
    """Действия при запуске сервера."""
    logger.info("🚀 Запуск Sirius Schedule Sync")
    logger.info("   Группа: %s", config.GROUP_NAME)
    logger.info("   Интервал обновления: %d мин.", config.UPDATE_INTERVAL_MINUTES)
    logger.info("   Недель вперёд: %d, назад: %d", config.WEEKS_AHEAD, config.WEEKS_BEHIND)

    threading.Thread(target=update_schedule, daemon=True).start()

    start_scheduler()


if __name__ == "__main__":
    uvicorn.run(
        "server:app",
        host=config.SERVER_HOST,
        port=config.SERVER_PORT,
        reload=False,
        log_level=config.LOG_LEVEL.lower(),
    )
