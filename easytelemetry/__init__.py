"""
This module contains interfaces and utility methods deemed usefull
for all further concrete implementations.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from enum import IntEnum
import inspect
import logging
import os
import platform
import re
import socket
import time
from types import TracebackType
from typing import (
    Any,
    Callable,
    Dict,
    Iterable,
    Optional,
    TypeAlias,
    TypeVar,
    Union,
)
import uuid


PropsT: TypeAlias = Dict[str, Union[str, int, float, bool]]
MetricFuncT: TypeAlias = Callable[[Union[int, float]], None]
MetricFuncWithPropsT: TypeAlias = Callable[[Union[int, float], PropsT], None]
MetricCtrFuncT: TypeAlias = Callable[[], None]
MetricCtrFuncWithPropsT: TypeAlias = Callable[[PropsT], None]


class Level(IntEnum):
    """Logging level"""

    DEBUG = logging.DEBUG
    INFO = logging.INFO
    WARN = logging.WARNING
    ERROR = logging.ERROR
    CRITICAL = logging.CRITICAL


class Telemetry(ABC):
    """
    Factory class that creates loggers and metrics with specific name
    and context.
    Also contains several utility methods and properties for most common tasks
    such as access to root logger and creating an activity.
    This is an abstract base class for all further concrete implementations.
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

    @property
    @abstractmethod
    def min_level(self) -> Level:
        """
        Minimal loggin level. Everything below this level is ignored.
        """
        pass

    @abstractmethod
    def logger(
        self,
        name: str,
        level: Level = Level.INFO,
        props: Optional[PropsT] = None,
    ) -> Logger:
        """Get or create a logger of given name."""
        pass

    @abstractmethod
    def metric(
        self,
        name: str,
        props: Optional[PropsT] = None,
    ) -> MetricFuncT:
        """Get or create a metric track function of given name."""
        pass

    @abstractmethod
    def metric_extra(
        self,
        name: str,
        props: Optional[PropsT] = None,
    ) -> MetricFuncWithPropsT:
        """
        Get or create a metric track function of given name,
        which also allows for passing extra properties local to the execution.
        """
        pass

    @abstractmethod
    def describe(self) -> str:
        """Return short description for this telemetry."""
        pass

    def metric_incr(
        self,
        name: str,
        props: Optional[PropsT] = None,
    ) -> MetricCtrFuncT:
        """
        Get or create a metric track function of given name,
        which increments the metric by 1 when executed.
        """
        metric_fn = self.metric(name, props)

        def inner() -> None:
            return metric_fn(1)

        return inner

    def metric_incr_extra(
        self,
        name: str,
        props: Optional[PropsT],
    ) -> MetricCtrFuncWithPropsT:
        """
        Get or create a metric track function of given name,
        which increments the metric by 1 when executed and also allows to pass
        extra properties local to the incrementing call.
        """
        metric_fn = self.metric_extra(name, props)

        def inner(extra: PropsT) -> None:
            return metric_fn(1, extra)

        return inner

    def metric_timer(
        self,
        name: str,
        props: Optional[PropsT] = None,
    ) -> MetricCtrFuncT:
        """
        Get or create a metric track function of given name,
        which increments the metric by milliseconds elapsed calculated
        as a time interval between the function creation and execution
        or between consequtive executions if the result (callable) is executed
        more than once.
        """
        start = time.perf_counter_ns()
        metric_fn = self.metric(name, props)

        def inner() -> None:
            nonlocal start
            now = time.perf_counter_ns()
            elapsed_ms = (now - start) / 1000000
            start = now
            return metric_fn(elapsed_ms)

        return inner

    def metric_timer_extra(
        self,
        name: str,
        props: Optional[PropsT] = None,
    ) -> MetricCtrFuncWithPropsT:
        """
        Get or create a metric track function of given name,
        which increments the metric by milliseconds elapsed calculated
        as a time interval between the function creation and execution
        or between consequtive executions if the result (callable) is executed
        more than once. It allows to pass extra properties local
        to the measurement call.
        """
        start = time.perf_counter_ns()
        metric_fn = self.metric_extra(name, props)

        def inner(extra: PropsT) -> None:
            nonlocal start
            now = time.perf_counter_ns()
            elapsed_ms = (now - start) / 1000000
            start = now
            return metric_fn(elapsed_ms, extra)

        return inner

    def metric_reusable_timer(
        self,
        name: str,
        props: Optional[PropsT] = None,
    ) -> ReusableTimer:
        """
        Create reusable timer object with methods start and stop, which give
        more control over when the timer starts and when it stops.
        Also, it could be started more than once, and it will publish
        the metric on every matching stop call.
        """
        metric_fn = self.metric_extra(name, props)
        return ReusableTimer(metric_fn)

    def activity(self, name: str) -> Activity:
        """Create an activity context manager."""
        return Activity(self, name)


class Logger(ABC):
    """API definition for a logger simmilar to logging.Logger."""

    @property
    @abstractmethod
    def name(self) -> str:
        """Get logger name."""
        pass

    @property
    @abstractmethod
    def level(self) -> Level:
        """Get current minimal logging level for this logger."""
        pass

    @abstractmethod
    def debug(self, msg: str, *args: Any, **kwargs: Any) -> None:
        """Log message with DEBUG logging level."""
        pass

    @abstractmethod
    def info(self, msg: str, *args: Any, **kwargs: Any) -> None:
        """Log message with INFO logging level."""
        pass

    @abstractmethod
    def warn(self, msg: str, *args: Any, **kwargs: Any) -> None:
        """Log message with WARN logging level."""
        pass

    @abstractmethod
    def error(self, msg: str, *args: Any, **kwargs: Any) -> None:
        """Log message with ERROR logging level."""
        pass

    @abstractmethod
    def critical(self, msg: str, *args: Any, **kwargs: Any) -> None:
        """Log message with CRITICAL logging level."""
        pass

    @abstractmethod
    def exception(
        self,
        ex: BaseException,
        tb: Optional[TracebackType] = None,
        level: Level = Level.ERROR,
        **kwargs: Any,
    ) -> None:
        """Log exception. ERROR is default logging level."""
        pass


class Activity:
    """
    Utility context manager class which simplifies common task
    of measuring a code block execution time and tracking number of failed
    and successful executions.
    """

    def __init__(self, telemetry: Telemetry, name: str):
        """ """
        self._name = name
        self._id: Optional[uuid.UUID] = None
        self._start: int = 0
        self._props: Optional[PropsT] = None
        self._logger = telemetry.logger(name)
        self._elapsed = telemetry.metric_extra(f"{name}_ms")
        self._success = telemetry.metric_incr_extra(f"{name}_ok", None)
        self._error = telemetry.metric_incr_extra(f"{name}_err", None)

    @property
    def id(self) -> Optional[uuid.UUID]:
        """
        Get activity ID. The ID is present after the start method call
        until the stop method call.
        """
        return self._id

    @property
    def name(self) -> str:
        """Get activity name."""
        return self._name

    @property
    def logger(self) -> Logger:
        """Get logger created for the activity."""
        return self._logger

    def start(self, props: Optional[PropsT] = None) -> None:
        """Start the activity."""
        self._start = time.perf_counter_ns()
        self._id = uuid.uuid4()
        self._props = {
            "activity_id": str(self._id),
            "activity": self.name,
        }
        if props is not None:
            self._props.update(**props)

    def stop(self, ex: Optional[BaseException] = None) -> None:
        """
        Stop the activity and publish activity metrics
        such as succcess, error, elapsed time, etc.
        """
        if self._start <= 0:
            return
        try:
            elapsed_ms = (time.perf_counter_ns() - self._start) / 1000000
            if ex is None:
                self._success(self._props)
            else:
                self._error(self._props)
                self._logger.exception(ex, **self._props)
            self._elapsed(elapsed_ms, self._props)
        finally:
            self._start = 0
            self._id = None
            self._props = None

    def __enter__(self) -> Activity:
        self.start()
        return self

    def __exit__(
        self,
        exc_type: BaseException | None,
        exc_val: BaseException | None,
        exc_tb: TracebackType | None,
    ) -> None:
        self.stop(exc_val)


class ReusableTimer:
    """
    A timer which you can repeatedly start and stop and the elapsed time
    will be published on every matching stop call.
    This allows for greater control.
    The class also have context manager semantics for convenience.
    """

    def __init__(self, metric_fn: MetricFuncWithPropsT):
        self._start: int = 0
        self._stop: int = 0
        self._metric_fn = metric_fn
        self._published = False
        self._props: Optional[PropsT] = None

    @property
    def elapsed_ns(self) -> int:
        if self._start <= 0:
            return 0
        if self._stop > 0 and self._stop > self._start:
            return self._stop - self._start
        else:
            return time.perf_counter_ns() - self._start

    @property
    def elapsed_ms(self) -> int:
        return int(self.elapsed_ns / 1000000)

    def start(self, props: Optional[PropsT] = None) -> None:
        self._props = props
        self._start = time.perf_counter_ns()
        self._stop = 0
        self._published = False

    def stop(self):
        self._stop = time.perf_counter_ns()
        if not self._published and 0 < self._start < self._stop:
            self._metric_fn(self.elapsed_ms, self._props)
            self._published = True

    def __enter__(self) -> ReusableTimer:
        self.start()
        return self

    def __exit__(
        self,
        exc_type: BaseException | None,
        exc_val: BaseException | None,
        exc_tb: TracebackType | None,
    ) -> None:
        self.stop()

    def __str__(self) -> str:
        return f"{self.elapsed_ms} ms"


_safe_name_rgx = re.compile(r"^[a-z](_?[a-z]+)*[a-z]$")


def is_safe_name(name: str) -> bool:
    """Return if the name is deemed safe to be logger or metric identifier."""
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
    """
    Try to determine current host name.
    If not able to do so, return 'unknown'.
    """
    return os.environ.get("COMPUTERNAME") or platform.node() or "unknown"


def get_host_ip() -> str:
    """
    Try to determine IP address of a host.
    If not able to do so, return empty string.
    """
    try:
        return socket.gethostbyname(socket.gethostname())
    except RuntimeError:
        return ""


def get_environment_name(app_name: str) -> str:
    """
    Try to determine application or service environment name
    based on conventional environment variables. If none is present,
    return 'prod'.
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
    For example: 'Production', 'production', 'prod', 'PROD' -> prod.
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
    """
    Try to determine application semantic version based on conventional
    environment variables. Returns '0.0.0.0' if it could not be determined.
    """
    return os.environ.get(f"{app_name.upper()}_APP_VERSION") or os.environ.get("APP_VERSION") or "0.0.0.0"


# noinspection DuplicatedCode, false positive
def level_to_std_logging(level: Level) -> int:
    """
    Convert easytelemetry :class:`Level` into standard logging level
    (`logging.INFO`, etc.) from :mod:`logging` module.
    """
    if level == level.DEBUG:
        return logging.DEBUG
    if level == level.INFO:
        return logging.INFO
    if level == level.WARN:
        return logging.WARNING
    if level == level.ERROR:
        return logging.ERROR
    if level == level.CRITICAL:
        return logging.CRITICAL
    return logging.INFO


# noinspection DuplicatedCode, false positive
def std_logging_to_level(levelno: int) -> Level:
    """
    Convert standard logging level (`logging.INFO`, etc.)
    from :mod:`logging` module into easytelemetry :class:`Level`.

    :param levelno: logging level number such as `logging.INFO`
    """
    if levelno == logging.DEBUG:
        return Level.DEBUG
    if levelno == logging.INFO:
        return Level.INFO
    if levelno == logging.WARNING:
        return Level.WARN
    if levelno == logging.ERROR:
        return Level.ERROR
    if levelno == logging.CRITICAL:
        return Level.CRITICAL
    return Level.INFO


class StdLoggingHandler(logging.Handler):
    """Adapter for standard Python logging."""

    def __init__(self, telemetry: Telemetry):
        std_level = level_to_std_logging(telemetry.min_level)
        super().__init__(level=std_level)
        self._telemetry = telemetry

    def emit(self, record: logging.LogRecord) -> None:
        (props, ex) = _parse_record(record)
        logger = self._telemetry.root if record.name == "root" else self._telemetry.logger(record.name)
        if ex is not None:
            level = std_logging_to_level(record.levelno)
            logger.exception(ex, level=level, **props)
        else:
            match record.levelno:
                case logging.DEBUG:
                    logger.debug(record.msg, **props)
                case logging.INFO:
                    logger.info(record.msg, **props)
                case logging.WARNING:
                    logger.warn(record.msg, **props)
                case logging.ERROR:
                    logger.error(record.msg, **props)
                case logging.CRITICAL:
                    logger.critical(record.msg, **props)
                case _:
                    logger.info(record.msg, **props)

    def configure_std_logging(self, clear_handlers: bool = False) -> None:
        logging.basicConfig(
            level=self.level, force=clear_handlers, datefmt="%Y-%m-%d %H:%M:%S", format="%(message)s", handlers=[self]
        )


def _parse_record(r: logging.LogRecord) -> tuple[PropsT, Optional[BaseException]]:
    props = {
        "path": r.pathname,
        "line": r.lineno,
        "module": r.module,
    }
    if r.funcName and r.funcName != "<module>":
        props["func"] = r.funcName
    ex: Optional[BaseException] = None
    if r.exc_info is not None:
        (_, ex, _) = r.exc_info
    if ex is not None and r.stack_info:
        props["stack"] = r.stack_info
    if r.name and r.name != "root":
        props["logger"] = r.name
    return props, ex


def stack_to_props(frame_idx: int) -> PropsT:
    """
    Find stacktrace frame of given index
    and turn it into dictionary o properties.

    :param frame_idx: stack frame index
    """
    st = inspect.stack()
    if len(st) <= frame_idx:
        return {}
    frame = st[frame_idx]
    props = {
        "path": frame.filename,
        "line": frame.lineno,
    }
    modinfo = inspect.getmodule(frame[0])
    if modinfo is not None and modinfo.__name__ != "__main__":
        props["module"] = modinfo.__name__
    if frame.function and frame.function != "<module>":
        props["func"] = frame.function
    return props


def create_props(primer: Optional[PropsT], frame_idx: int) -> PropsT:
    """
    Create properties by merging (optional) original dictionary of properties
    with information derived from relevant stacktrace.

    :param primer: stack frame index
    :param frame_idx: stack frame index
    """
    if primer:
        if "line" in primer:
            return primer.copy()

        stack_props = stack_to_props(frame_idx)
        return {**stack_props, **primer}

    return stack_to_props(frame_idx)


def merge_props(*args: Optional[PropsT]) -> PropsT:
    """
    Merge any number of properties into one dictionary.
    Later ones silently overwrite earlier ones on matching keys.
    """
    props = {}
    for p in args:
        if p:
            props.update(**p)
    return props
