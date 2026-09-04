"""
Парсер расписания Университета Сириус.

Работает через Livewire-протокол сайта schedule.siriusuniversity.ru.
Эмулирует выбор группы и навигацию по неделям,
извлекая все события (пары, экзамены и т.д.).
"""

import re
import json
import logging
import hashlib
from datetime import datetime, timedelta
from dataclasses import dataclass
from typing import Optional

import requests
from bs4 import BeautifulSoup

from config import Config

logger = logging.getLogger(__name__)


COLOR_TO_TYPE = {
    "teal": "Лекция",
    "yellow": "Семинар",
    "sky": "Практика",
    "purple": "Лабораторная",
    "pink": "Экзамен",
    "orange": "Прочее",
}

CODE_TO_TYPE = {
    "alt.lectures": "Лекция",
    "alt.seminars": "Семинар",
    "alt.practice": "Практика",
    "alt.laboratory": "Лабораторная",
    "alt.exam": "Экзамен",
    "alt.other": "Прочее",
}

GROUP_TYPE_TO_TYPE = {
    "Лекции": "Лекция",
    "Семинары": "Семинар",
    "Практические занятия": "Практика",
    "Лабораторные занятия": "Лабораторная",
    "Экзамены": "Экзамен",
    "Зачеты": "Экзамен",
}


@dataclass
class ScheduleEvent:
    """Одно событие расписания (пара, экзамен и т.д.)."""

    title: str
    event_type: str
    date: str
    time_start: str
    time_end: str
    teacher: str = ""
    classroom: str = ""
    group: str = ""
    address: str = ""
    number_pair: int = 0
    url_online: str = ""
    comment: str = ""

    @property
    def uid(self) -> str:
        """Уникальный ID события для ICS (стабильный при обновлениях)."""
        raw = f"{self.date}_{self.time_start}_{self.title}_{self.classroom}_{self.group}"
        return hashlib.md5(raw.encode()).hexdigest() + "@sirius-schedule"

    @property
    def start_datetime(self) -> datetime:
        """Дата и время начала как datetime."""
        return datetime.strptime(f"{self.date} {self.time_start}", "%d.%m.%Y %H:%M")

    @property
    def end_datetime(self) -> datetime:
        """Дата и время окончания как datetime."""
        return datetime.strptime(f"{self.date} {self.time_end}", "%d.%m.%Y %H:%M")


class SiriusScheduleScraper:
    """
    Парсер расписания через Livewire-протокол.

    Алгоритм:
    1. Загрузить главную страницу → получить CSRF-токен и начальное состояние Livewire
    2. Отправить Livewire-запрос на выбор группы → получить события текущей недели
    3. Навигировать по неделям (addWeek/minusWeek) → собрать все события
    """

    def __init__(self, config: Optional[Config] = None):
        self.config = config or Config()
        self.session = requests.Session()
        self.session.headers.update(
            {
                "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/120.0.0.0 Safari/537.36",
                "Accept": "text/html, application/xhtml+xml",
                "Accept-Language": "ru-RU,ru;q=0.9,en;q=0.8",
            }
        )

        if self.config.requests_proxies:
            self.session.proxies.update(self.config.requests_proxies)
            logger.info("Прокси настроен: %s", list(self.config.requests_proxies.keys()))

        self._timeout = self.config.REQUEST_TIMEOUT

        self._csrf_token: str = ""
        self._fingerprint: dict = {}
        self._server_memo: dict = {}
        self._initialized: bool = False

    def _init_session(self) -> None:
        """Загрузить главную страницу и извлечь Livewire-состояние и CSRF-токен."""
        logger.info("Инициализация сессии: загрузка %s", self.config.SCHEDULE_BASE_URL)

        resp = self.session.get(self.config.SCHEDULE_BASE_URL, timeout=self._timeout)
        resp.raise_for_status()

        token_match = re.search(r"livewire_token\s*=\s*'([^']+)'", resp.text)
        if not token_match:
            raise RuntimeError("Не удалось найти CSRF-токен на странице")
        self._csrf_token = token_match.group(1)
        logger.debug("CSRF-токен: %s...", self._csrf_token[:20])

        soup = BeautifulSoup(resp.text, "html.parser")
        wire_el = soup.find(attrs={"wire:initial-data": True})
        if not wire_el:
            raise RuntimeError("Не удалось найти Livewire-компонент на странице")

        initial_data = json.loads(wire_el["wire:initial-data"])
        self._fingerprint = initial_data["fingerprint"]
        self._server_memo = initial_data["serverMemo"]
        self._initialized = True

        logger.info(
            "Сессия инициализирована. Компонент: %s, ID: %s",
            self._fingerprint.get("name"),
            self._fingerprint.get("id"),
        )

    def _livewire_call(self, method: str, params: list = None) -> dict:
        """
        Выполнить Livewire-запрос (вызвать метод компонента).

        Args:
            method: Имя метода (set, addWeek, minusWeek, current и т.д.)
            params: Параметры метода

        Returns:
            Полный ответ Livewire
        """
        if not self._initialized:
            self._init_session()

        payload = {
            "fingerprint": self._fingerprint,
            "serverMemo": self._server_memo,
            "updates": [
                {
                    "type": "callMethod",
                    "payload": {
                        "id": self._fingerprint["id"],
                        "method": method,
                        "params": params or [],
                    },
                }
            ],
        }

        headers = {
            "Content-Type": "application/json",
            "X-Livewire": "true",
            "X-CSRF-TOKEN": self._csrf_token,
            "Referer": self.config.SCHEDULE_BASE_URL,
        }

        logger.debug("Livewire-запрос: метод=%s, параметры=%s", method, params)

        resp = self.session.post(
            self.config.LIVEWIRE_ENDPOINT,
            json=payload,
            headers=headers,
            timeout=self._timeout,
        )
        resp.raise_for_status()

        result = resp.json()

        if "serverMemo" in result:
            self._merge_server_memo(result["serverMemo"])

        if "fingerprint" in result:
            self._fingerprint.update(result["fingerprint"])

        return result

    def _merge_server_memo(self, new_memo: dict) -> None:
        """Слить обновлённый serverMemo с текущим."""
        for key, value in new_memo.items():
            if key == "data" and isinstance(value, dict):
                self._server_memo.setdefault("data", {}).update(value)
            else:
                self._server_memo[key] = value

    def _parse_events_from_data(self) -> list[ScheduleEvent]:
        """
        Извлечь события из serverMemo.data.events.

        Формат данных Livewire:
        events = {
            "2_2": [
                {
                    "date": "02.09.2026",
                    "dayWeek": "СР",
                    "startTime": "11:55",
                    "endTime": "13:15",
                    "discipline": "Английский язык для ИТ-специалистов",
                    "groupType": "Практические занятия",
                    "classroom": "1.35К_0 (стартап-лаборатория ИНТЦ)",
                    "teachers": {"uuid": {"fio": "Биккинина Элина Рамилевна", ...}},
                    "color": "sky",
                    "code": "alt.practice",
                    "numberPair": 3,
                    "group": "К0609-23",
                    "address": "Основной",
                    "comment": null,
                    "urlOnline": null
                },
                ...
            ],
            ...
        }
        """
        events_data = self._server_memo.get("data", {}).get("events", {})

        if not events_data:
            return []

        events: list[ScheduleEvent] = []

        if isinstance(events_data, dict):
            for slot_key, slot_events in events_data.items():
                if not isinstance(slot_events, list):
                    continue
                for raw in slot_events:
                    event = self._parse_raw_event(raw)
                    if event:
                        events.append(event)
        elif isinstance(events_data, list):
            for raw in events_data:
                event = self._parse_raw_event(raw)
                if event:
                    events.append(event)

        return events

    def _parse_raw_event(self, raw: dict) -> Optional[ScheduleEvent]:
        """Конвертировать сырые данные одного события в ScheduleEvent."""
        try:
            discipline = raw.get("discipline", "")
            if not discipline:
                return None

            date = raw.get("date", "")
            start_time = raw.get("startTime", "")
            end_time = raw.get("endTime", "")

            if not date or not start_time or not end_time:
                logger.warning("Событие без даты/времени: %s", discipline)
                return None

            event_type = "Прочее"
            group_type = raw.get("groupType", "")
            if group_type and group_type in GROUP_TYPE_TO_TYPE:
                event_type = GROUP_TYPE_TO_TYPE[group_type]
            elif raw.get("code") in CODE_TO_TYPE:
                event_type = CODE_TO_TYPE[raw["code"]]
            elif raw.get("color") in COLOR_TO_TYPE:
                event_type = COLOR_TO_TYPE[raw["color"]]

            teachers_data = raw.get("teachers", {})
            teacher_names = []
            if isinstance(teachers_data, dict):
                for teacher_info in teachers_data.values():
                    if isinstance(teacher_info, dict):
                        fio = teacher_info.get("fio", "")
                        if fio:
                            teacher_names.append(fio)
            teacher = ", ".join(teacher_names)

            classroom = raw.get("classroom", "") or ""
            group = raw.get("group", "") or self.config.GROUP_NAME
            address = raw.get("address", "") or ""
            number_pair = raw.get("numberPair", 0) or 0
            url_online = raw.get("urlOnline", "") or ""
            comment = raw.get("comment", "") or ""

            return ScheduleEvent(
                title=discipline,
                event_type=event_type,
                date=date,
                time_start=start_time,
                time_end=end_time,
                teacher=teacher,
                classroom=classroom,
                group=group,
                address=address,
                number_pair=number_pair,
                url_online=url_online,
                comment=comment,
            )

        except Exception as e:
            logger.warning("Ошибка парсинга события: %s — %s", raw.get("discipline", "?"), e)
            return None

    def fetch_schedule(self) -> list[ScheduleEvent]:
        """
        Получить полное расписание для настроенной группы.

        Returns:
            Список событий за указанный диапазон недель.
        """
        logger.info(
            "Начало получения расписания для группы %s", self.config.GROUP_NAME
        )

        self._init_session()

        logger.info("Выбираем группу: %s", self.config.GROUP_NAME)
        self._livewire_call("set", [self.config.GROUP_NAME])

        all_events: list[ScheduleEvent] = []

        current_events = self._parse_events_from_data()
        all_events.extend(current_events)

        week_info = self._server_memo.get("data", {}).get("date", "")
        num_week = self._server_memo.get("data", {}).get("numWeek", "?")
        logger.info(
            "Текущая неделя %s (%s): %d событий",
            num_week, week_info, len(current_events),
        )

        for i in range(self.config.WEEKS_AHEAD):
            self._livewire_call("addWeek")
            week_events = self._parse_events_from_data()
            all_events.extend(week_events)

            week_info = self._server_memo.get("data", {}).get("date", "")
            num_week = self._server_memo.get("data", {}).get("numWeek", "?")
            logger.info(
                "Неделя +%d (%s, нед. %s): %d событий",
                i + 1, week_info, num_week, len(week_events),
            )

        self._livewire_call("current")

        for i in range(self.config.WEEKS_BEHIND):
            self._livewire_call("minusWeek")
            week_events = self._parse_events_from_data()
            all_events.extend(week_events)

            week_info = self._server_memo.get("data", {}).get("date", "")
            num_week = self._server_memo.get("data", {}).get("numWeek", "?")
            logger.info(
                "Неделя -%d (%s, нед. %s): %d событий",
                i + 1, week_info, num_week, len(week_events),
            )

        seen_uids = set()
        unique_events = []
        for event in all_events:
            if event.uid not in seen_uids:
                seen_uids.add(event.uid)
                unique_events.append(event)

        unique_events.sort(key=lambda e: (e.date, e.time_start))

        logger.info(
            "Итого: %d уникальных событий (из %d)",
            len(unique_events), len(all_events),
        )

        return unique_events

    def fetch_schedule_safe(self) -> list[ScheduleEvent]:
        """Получить расписание с обработкой ошибок."""
        try:
            return self.fetch_schedule()
        except requests.exceptions.RequestException as e:
            logger.error("Сетевая ошибка при получении расписания: %s", e)
            return []
        except Exception as e:
            logger.error("Ошибка при получении расписания: %s", e, exc_info=True)
            return []


if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )

    scraper = SiriusScheduleScraper()
    events = scraper.fetch_schedule()

    print(f"\n{'='*70}")
    print(f" Расписание группы {Config.GROUP_NAME}: {len(events)} событий")
    print(f"{'='*70}")

    for event in events:
        print(
            f"  {event.date} ({event.time_start}-{event.time_end}) "
            f"[{event.event_type}] {event.title}"
        )
        if event.teacher:
            print(f"    👤 {event.teacher}")
        if event.classroom:
            print(f"    📍 {event.classroom}")
        print()
