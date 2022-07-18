from __future__ import annotations

import logging
import os
import platform
import re
import socket
import time
from abc import ABC, abstractmethod
from enum import IntEnum
from types import TracebackType
from typing import Any, Callable, Dict, Iterable, Optional, TypeVar, Union


class Level(IntEnum):
    DEBUG = logging.DEBUG
    INFO = logging.INFO
    WARN = logging.WARNING
    ERROR = logging.ERROR
    CRITICAL = logging.CRITICAL


class Logger(ABC):
    """
    API definition for a logger simmilar to logging.Logger,
    but more opinionated.
    """

    @property
    @abstractmethod
    def name(self) -> str:
        pass

    @property
    @abstractmethod
    def level(self) -> Level:
        pass

    @abstractmethod
    def debug(self, msg: str, *args: Any, **kwargs: Any) -> None:
        pass

    @abstractmethod
    def info(self, msg: str, *args: Any, **kwargs: Any) -> None:
        pass

    @abstractmethod
    def warn(self, msg: str, *args: Any, **kwargs: Any) -> None:
        pass

    @abstractmethod
    def error(self, msg: str, *args: Any, **kwargs: Any) -> None:
        pass

    @abstractmethod
    def critical(self, msg: str, *args: Any, **kwargs: Any) -> None:
        pass

    @abstractmethod
    def exception(
        self,
        ex: BaseException,
        level: Level = Level.ERROR,
        **kwargs: Any,
    ) -> None:
        pass


class Telemetry(ABC):
    """
    Factory class that creates loggers and metrics with specific name
    and context.
    Also contains several utility methods and properties for most common tasks
    such as access to root logger and creating an activity.
    This is abstract base class for all further concrete implementations.
    """

    @property
    @abstractmethod
    def root(self) -> Logger:
        """Root logger."""
        pass

    @property
    @abstractmethod
    def name(self) -> str:
        """
        Telemetry name.
        This is usualy the same as application or service name.
        """
        pass

    @abstractmethod
    def logger(
        self,
        name: str,
        level: Level = Level.INFO,
        props: Optional[Dict[str, Any]] = None,
    ) -> Logger:
        """Get or create a logger of given name."""
        pass

    @abstractmethod
    def metric(
        self,
        name: str,
        props: Optional[Dict[str, Any]] = None,
    ) -> Callable[[Union[int, float]], None]:
        """Get or create a metric track function of given name."""
        pass

    @abstractmethod
    def describe(self) -> str:
        """Return short description for this telemetry."""
        pass

    def metric_incr(
        self,
        name: str,
        props: Optional[Dict[str, Any]] = None,
    ) -> Callable[[], None]:
        """
        Get or create a metric track function of given name,
        which increments the metric by 1 when executed.
        """
        metric_fn = self.metric(name, props)

        def inner() -> None:
            return metric_fn(1)

        return inner

    def activity(
        self,
        name: str,
        props: Optional[Dict[str, Any]] = None,
    ) -> Activity:
        """Create an activity context manager."""
        return Activity(self, name, props)


class Activity:
    """
    Utility context manager class which simplifies common task
    of measuring a code block execution time and tracking number of failed
    and successful executions.
    """

    def __init__(
        self,
        telemetry: Telemetry,
        name: str,
        props: Optional[Dict[str, Any]] = None,
    ):
        self._logger = telemetry.logger(name, props=props)
        self._elapsed = telemetry.metric(f"{name}_ms", props=props)
        self._success = telemetry.metric_incr(f"{name}_ok", props=props)
        self._error = telemetry.metric_incr(f"{name}_err", props=props)
        self._start: int = 0

    def __enter__(self) -> Activity:
        self._start = time.perf_counter_ns()
        return self

    def __exit__(
        self,
        exc_type: BaseException | None,
        exc_val: BaseException | None,
        exc_tb: TracebackType | None,
    ) -> None:
        elapsed_ms = (time.perf_counter_ns() - self._start) / 1000000
        if exc_type is None:
            self._success()
        else:
            self._error()
            self._logger.exception(exc_type)
        self._elapsed(elapsed_ms)


_safe_name_rgx = re.compile(r"^[a-z](_?[a-z]+)*[a-z]$")


def is_safe_name(name: str) -> bool:
    """
    Return if the name is deemed safe to function
    as logger or metric identifier.
    """
    return _safe_name_rgx.fullmatch(name) is not None


T = TypeVar("T")


def check_all(items: Iterable[T], condition: Callable[[T], bool]) -> bool:
    """Determine if the condition is valid for all items."""
    i = 0
    j = 0
    for item in items:
        i += 1
        if condition(item):
            j += 1
    return i == j


def get_host_name() -> str:
    """Try to determine current host name."""
    return os.environ.get("COMPUTERNAME") or platform.node() or "unknown"


def get_host_ip() -> str:
    try:
        return socket.gethostbyname(socket.gethostname())
    except RuntimeError:
        return ""


def get_environment_name(app_name: str) -> str:
    """
    Try to determine application or service environment name
    based on conventional environment variables.
    """
    s = (
        os.environ.get("AZURE_FUNCTIONS_ENVIRONMENT")
        or os.environ.get(f"{app_name.upper()}_ENVIRONMENT")
        or os.environ.get("ENVIRONMENT")
    )
    return normalize_environment_name(s)


def normalize_environment_name(name: Optional[str]) -> str:  # noqa: CFQ004
    """
    Normalize environment name, so slight deviations in conventions
    does not matter.
    For example: 'Production', 'production', 'prod', 'PROD' -> prod
    """
    if not name:
        return "prod"
    name = name.lower().strip()
    if name == "prod" or name == "production":
        return "prod"
    if name == "stage" or name == "staging":
        return "stage"
    if name == "test" or name == "testing":
        return "test"
    if name == "dev" or name == "development":
        return "dev"
    return "prod"


def get_app_version(app_name: str) -> str:
    return (
        os.environ.get(f"{app_name.upper()}_APP_VERSION")
        or os.environ.get("APP_VERSION")
        or "0.0.0.0"
    )
