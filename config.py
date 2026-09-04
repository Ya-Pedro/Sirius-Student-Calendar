"""Конфигурация сервиса расписания Университета Сириус."""

import os
from dotenv import load_dotenv

load_dotenv()


class Config:
    """Настройки приложения, загружаемые из переменных окружения."""

    GROUP_NAME: str = os.getenv("GROUP_NAME", "К0609-23")

    WEEKS_AHEAD: int = int(os.getenv("WEEKS_AHEAD", "4"))
    WEEKS_BEHIND: int = int(os.getenv("WEEKS_BEHIND", "1"))

    UPDATE_INTERVAL_MINUTES: int = int(os.getenv("UPDATE_INTERVAL_MINUTES", "30"))

    SERVER_HOST: str = os.getenv("SERVER_HOST", "0.0.0.0")
    SERVER_PORT: int = int(os.getenv("SERVER_PORT", "8080"))

    TIMEZONE: str = os.getenv("TIMEZONE", "Europe/Moscow")

    LOG_LEVEL: str = os.getenv("LOG_LEVEL", "INFO")

    SCHEDULE_BASE_URL: str = "https://schedule.siriusuniversity.ru"
    LIVEWIRE_ENDPOINT: str = f"{SCHEDULE_BASE_URL}/livewire/message/main-grid"

    ICS_OUTPUT_PATH: str = os.getenv("ICS_OUTPUT_PATH", "schedule.ics")

    CALENDAR_NAME: str = os.getenv("CALENDAR_NAME", f"Сириус — {GROUP_NAME}")

    HTTP_PROXY: str = os.getenv("HTTP_PROXY", "")
    HTTPS_PROXY: str = os.getenv("HTTPS_PROXY", "")

    REQUEST_TIMEOUT: int = int(os.getenv("REQUEST_TIMEOUT", "60"))

    @property
    def requests_proxies(self) -> dict:
        """Словарь прокси для requests.Session."""
        proxies = {}
        if self.HTTP_PROXY:
            proxies["http"] = self.HTTP_PROXY
        if self.HTTPS_PROXY:
            proxies["https"] = self.HTTPS_PROXY
        return proxies
