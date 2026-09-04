"""
Генератор ICS-файлов из событий расписания.

Создаёт стандартный iCalendar-файл, совместимый с:
- Apple Calendar (iPhone, Mac)
- Google Calendar
- Outlook
- и любыми другими клиентами, поддерживающими iCal
"""

import logging
from datetime import datetime, timedelta
from typing import Optional

from icalendar import Calendar, Event, Alarm
import pytz

from config import Config
from scraper import ScheduleEvent

logger = logging.getLogger(__name__)


EVENT_TYPE_COLORS = {
    "Лекция": "teal",
    "Семинар": "yellow",
    "Практика": "blue",
    "Лабораторная": "purple",
    "Экзамен": "red",
    "Прочее": "orange",
}


class ICSGenerator:
    """
    Генератор ICS-файлов из событий расписания.

    Создаёт валидный iCalendar с:
    - Правильными часовыми поясами (Europe/Moscow)
    - Напоминаниями (15 минут до начала)
    - Категориями по типу пары
    - Стабильными UID для корректного обновления событий
    """

    def __init__(self, config: Optional[Config] = None):
        self.config = config or Config()
        self.tz = pytz.timezone(self.config.TIMEZONE)

    def generate(self, events: list[ScheduleEvent]) -> str:
        """
        Создать ICS-файл из списка событий.

        Args:
            events: Список событий расписания

        Returns:
            Строка с содержимым ICS-файла
        """
        cal = Calendar()

        cal.add("prodid", "-//Sirius University Schedule//sirius-schedule//RU")
        cal.add("version", "2.0")
        cal.add("calscale", "GREGORIAN")
        cal.add("method", "PUBLISH")
        cal.add("x-wr-calname", self.config.CALENDAR_NAME)
        cal.add("x-wr-timezone", self.config.TIMEZONE)

        cal.add("refresh-interval;value=duration", f"PT{self.config.UPDATE_INTERVAL_MINUTES}M")
        cal.add("x-published-ttl", f"PT{self.config.UPDATE_INTERVAL_MINUTES}M")

        events_added = 0
        for schedule_event in events:
            try:
                ical_event = self._create_event(schedule_event)
                if ical_event:
                    cal.add_component(ical_event)
                    events_added += 1
            except Exception as e:
                logger.warning(
                    "Ошибка создания ICS-события для '%s': %s",
                    schedule_event.title,
                    e,
                )

        logger.info("Создан ICS-файл с %d событиями", events_added)
        return cal.to_ical().decode("utf-8")

    def _create_event(self, schedule_event: ScheduleEvent) -> Optional[Event]:
        """
        Создать одно ICS-событие из ScheduleEvent.

        Args:
            schedule_event: Событие расписания

        Returns:
            iCalendar Event или None
        """
        if not schedule_event.date or not schedule_event.time_start:
            logger.warning(
                "Пропускаем событие без даты/времени: %s", schedule_event.title
            )
            return None

        event = Event()

        event.add("uid", schedule_event.uid)

        emoji = self._get_type_emoji(schedule_event.event_type)
        summary = f"{emoji} {schedule_event.title}"
        if schedule_event.event_type and schedule_event.event_type != "Прочее":
            summary += f" ({schedule_event.event_type})"
        event.add("summary", summary)

        try:
            dt_start = self.tz.localize(schedule_event.start_datetime)
            dt_end = self.tz.localize(schedule_event.end_datetime)
        except ValueError as e:
            logger.warning(
                "Некорректная дата/время для '%s': %s", schedule_event.title, e
            )
            return None

        event.add("dtstart", dt_start)
        event.add("dtend", dt_end)

        description_parts = []
        if schedule_event.teacher:
            description_parts.append(f"Преподаватель: {schedule_event.teacher}")
        if schedule_event.classroom:
            description_parts.append(f"Аудитория: {schedule_event.classroom}")
        if schedule_event.address:
            description_parts.append(f"Кампус: {schedule_event.address}")
        if schedule_event.group:
            description_parts.append(f"Группа: {schedule_event.group}")
        if schedule_event.number_pair:
            description_parts.append(f"Пара №{schedule_event.number_pair}")
        if schedule_event.event_type:
            description_parts.append(f"Тип: {schedule_event.event_type}")
        if schedule_event.url_online:
            description_parts.append(f"🔗 Онлайн: {schedule_event.url_online}")
        if schedule_event.comment:
            description_parts.append(f"{schedule_event.comment}")
        description_parts.append("")
        description_parts.append("Автообновление: schedule.siriusuniversity.ru")

        event.add("description", "\n".join(description_parts))

        if schedule_event.classroom:
            event.add("location", schedule_event.classroom)

        if schedule_event.event_type:
            event.add("categories", [schedule_event.event_type])

        event.add("status", "CONFIRMED")

        event.add("transp", "OPAQUE")

        now = datetime.now(self.tz)
        event.add("dtstamp", now)
        event.add("last-modified", now)

        alarm = Alarm()
        alarm.add("action", "DISPLAY")
        alarm.add(
            "description",
            f"{schedule_event.title} через 15 минут",
        )
        alarm.add("trigger", timedelta(minutes=-15))
        event.add_component(alarm)

        alarm2 = Alarm()
        alarm2.add("action", "DISPLAY")
        alarm2.add(
            "description",
            f"{schedule_event.title} через 5 минут",
        )
        alarm2.add("trigger", timedelta(minutes=-5))
        event.add_component(alarm2)

        return event

    @staticmethod
    def _get_type_emoji(event_type: str) -> str:
        """Получить эмодзи для типа события."""
        emoji_map = {
            "Лекция": "🐧",
            "Семинар": "💬",
            "Практика": "🐒",
            "Лабораторная": "🔬",
            "Экзамен": "🦖",
            "Прочее": "📌",
        }
        return emoji_map.get(event_type, "📅")

    def save_to_file(self, events: list[ScheduleEvent], path: Optional[str] = None) -> str:
        """
        Сохранить ICS-файл на диск.

        Args:
            events: Список событий
            path: Путь к файлу (по умолчанию из конфига)

        Returns:
            Путь к сохранённому файлу
        """
        output_path = path or self.config.ICS_OUTPUT_PATH
        ics_content = self.generate(events)

        with open(output_path, "w", encoding="utf-8") as f:
            f.write(ics_content)

        logger.info("ICS-файл сохранён: %s (%d событий)", output_path, len(events))
        return output_path


if __name__ == "__main__":
    logging.basicConfig(level=logging.DEBUG)

    test_events = [
        ScheduleEvent(
            title="Математический анализ",
            event_type="Лекция",
            date="03.09.2026",
            time_start="09:00",
            time_end="10:30",
            teacher="Иванов И.И.",
            classroom="А-101",
            group="К0609-23",
        ),
        ScheduleEvent(
            title="Программирование на Python",
            event_type="Лабораторная",
            date="03.09.2026",
            time_start="11:00",
            time_end="12:30",
            teacher="Петров П.П.",
            classroom="Б-205",
            group="К0609-23",
        ),
    ]

    generator = ICSGenerator()
    ics_content = generator.generate(test_events)
    print(ics_content)

    generator.save_to_file(test_events, "test_schedule.ics")
    print("\nФайл test_schedule.ics создан!")
