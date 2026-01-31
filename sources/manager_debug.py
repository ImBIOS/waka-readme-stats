from datetime import datetime
from logging import Logger, StreamHandler, getLogger
from string import Template
from typing import Dict

from humanize import precisedelta
from .manager_environment import EnvironmentManager as EM


def init_debug_manager():
    """
    Initialize download manager:
    - Setup headers for GitHub GraphQL requests.
    - Launch static queries in background.
    """
    if EM.DEBUG_LOGGING:
        level = "DEBUG"
    elif EM.LOG_LEVEL == "trace":
        level = "TRACE"
    elif EM.LOG_LEVEL == "debug":
        level = "DEBUG"
    else:
        level = "INFO"

    DebugManager.create_logger(level)


class DebugManager:
    _COLOR_RESET = "\u001b[0m"
    _COLOR_RED = "\u001b[31m"
    _COLOR_GREEN = "\u001b[32m"
    _COLOR_BLUE = "\u001b[34m"
    _COLOR_YELLOW = "\u001b[33m"
    _COLOR_GRAY = "\u001b[90m"

    _DATE_TEMPLATE = "date"
    _TIME_TEMPLATE = "time"

    _logger: Logger
    _last_log_time: datetime | None = None

    @staticmethod
    def create_logger(level: str):
        DebugManager._logger = getLogger(__name__)
        DebugManager._logger.setLevel(level)
        DebugManager._logger.addHandler(StreamHandler())
        DebugManager._last_log_time = datetime.now()

    @staticmethod
    def _timing_suffix() -> str:
        now = datetime.now()
        if DebugManager._last_log_time is None:
            DebugManager._last_log_time = now
            delta_ms = 0
        else:
            delta = now - DebugManager._last_log_time
            delta_ms = int(delta.total_seconds() * 1000)
            DebugManager._last_log_time = now

        return f"{DebugManager._COLOR_GRAY} ({delta_ms}ms){DebugManager._COLOR_RESET}"

    @staticmethod
    def _process_template(message: str, kwargs: Dict) -> str:
        if DebugManager._DATE_TEMPLATE in kwargs:
            kwargs[DebugManager._DATE_TEMPLATE] = f"{datetime.strftime(kwargs[DebugManager._DATE_TEMPLATE], '%d-%m-%Y %H:%M:%S:%f')}"
        if DebugManager._TIME_TEMPLATE in kwargs:
            kwargs[DebugManager._TIME_TEMPLATE] = precisedelta(kwargs[DebugManager._TIME_TEMPLATE], minimum_unit="microseconds")

        return Template(message).substitute(kwargs)

    @staticmethod
    def g(message: str, **kwargs):
        message = DebugManager._process_template(message, kwargs)
        DebugManager._logger.info(f"{DebugManager._COLOR_GREEN}{message}{DebugManager._COLOR_RESET}{DebugManager._timing_suffix()}")

    @staticmethod
    def i(message: str, **kwargs):
        message = DebugManager._process_template(message, kwargs)
        DebugManager._logger.debug(f"{DebugManager._COLOR_BLUE}{message}{DebugManager._COLOR_RESET}{DebugManager._timing_suffix()}")

    @staticmethod
    def w(message: str, **kwargs):
        message = DebugManager._process_template(message, kwargs)
        DebugManager._logger.warning(f"{DebugManager._COLOR_YELLOW}{message}{DebugManager._COLOR_RESET}{DebugManager._timing_suffix()}")

    @staticmethod
    def p(message: str, **kwargs):
        message = DebugManager._process_template(message, kwargs)
        DebugManager._logger.error(f"{message}{DebugManager._timing_suffix()}")
