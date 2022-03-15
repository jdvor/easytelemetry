"""
This module contains in-memory implementation for the telemetry.
It is useful for unit testing and NOT anywhere else where it would quickly
lead to OOM, because the implementations collect indefinatelly the logs
and metric entries unless explicitly told to clear them.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any, Callable, Dict, List, Optional, Tuple, Union

from easytelemetry.interface import (
    Level,
    Logger,
    Telemetry,
    get_app_version,
    get_environment_name,
    get_host_name,
)


class InMemoryTelemetry(Telemetry):
    def __init__(
        self,
        name: str,
        global_props: Dict[str, Any],
        min_level: Level = Level.INFO,
    ):
        self._name = name
        self._global_props = global_props
        self._min_level = min_level
        self._logs: List[LogEntry] = []
        self._rootlgr = InMemoryLogger(
            "_root",
            min_level,
            global_props,
            self._logs,
        )
        self._loggers: Dict[str, Logger] = {self._rootlgr.name: self._rootlgr}
        self._metrics: Dict[str, _Metric] = {}

    @property
    def root(self) -> Logger:
        return self._rootlgr

    @property
    def name(self) -> str:
        return self._name

    @property
    def logs(self) -> List[LogEntry]:
        return self._logs

    @property
    def metrics(self) -> Dict[str, _Metric]:
        return self._metrics

    def logger(
        self,
        name: str,
        level: Level = Level.INFO,
        props: Optional[Dict[str, Any]] = None,
    ) -> Logger:
        lgr = self._loggers.get(name)
        if not lgr:
            lvl = level if level else self._min_level
            extra = (
                {**self._global_props, **props} if props else self._global_props
            )
            lgr = InMemoryLogger(name, lvl, extra, self._logs)
            self._loggers[name] = lgr
        return lgr

    def metric(
        self,
        name: str,
        props: Optional[Dict[str, Any]] = None,
    ) -> Callable[[Union[int, float]], None]:
        m = self._metrics.get(name)
        if not m:
            m = _Metric(name, props)
            self._metrics[name] = m
        return m.track

    def describe(self) -> str:
        s = [
            f"name: {self._name}",
            f'loggers: {", ".join(self._loggers.keys())}',
            f'metrics: {", ".join(self._metrics.keys())}',
        ]
        return "\n".join(s)

    def clear(self) -> None:
        self._logs.clear()
        for m in self._metrics.values():
            m.clear()

    def print_data(self) -> None:
        print("--- Logs ---")
        for le in self._logs:
            print(le)
        print("--- Metrics ---")
        for name, mtr in self._metrics.items():
            print(f":: {name}")
            for time, value in mtr.data:
                print(f'\t[{time.strftime("%Y-%m-%d %T")}] {value}')


class InMemoryLogger(Logger):
    def __init__(
        self,
        name: str,
        min_level: Level,
        extra: Dict[str, Any],
        logs: List[LogEntry],
    ):
        self._name = name
        self._level = min_level
        self._extra = extra
        self._logs = logs

    @property
    def name(self) -> str:
        return self._name

    @property
    def level(self) -> Level:
        return self._level

    def debug(self, msg: str, *args: Any, **kwargs: Any) -> None:
        if self._level <= Level.DEBUG:
            self._logs.append(_log(self._name, Level.DEBUG, msg, args, kwargs))

    def info(self, msg: str, *args: Any, **kwargs: Any) -> None:
        if self._level <= Level.INFO:
            self._logs.append(_log(self._name, Level.INFO, msg, args, kwargs))

    def warn(self, msg: str, *args: Any, **kwargs: Any) -> None:
        if self._level <= Level.WARN:
            self._logs.append(_log(self._name, Level.WARN, msg, args, kwargs))

    def error(self, msg: str, *args: Any, **kwargs: Any) -> None:
        if self._level <= Level.ERROR:
            self._logs.append(_log(self._name, Level.ERROR, msg, args, kwargs))

    def critical(self, msg: str, *args: Any, **kwargs: Any) -> None:
        self._logs.append(_log(self._name, Level.CRITICAL, msg, args, kwargs))

    def exception(
        self,
        ex: BaseException,
        level: Level = Level.ERROR,
        **kwargs: Any,
    ) -> None:
        if self._level >= Level.ERROR:
            self._logs.append(_log(self._name, level, str(ex), (), kwargs, ex))

    def __str__(self) -> str:
        return f"{self._name}:{self._level}"


@dataclass(frozen=True)
class LogEntry:
    time: datetime
    level: Level
    source: str
    msg: str
    ex: Optional[BaseException]
    args: Optional[Tuple[Any]]
    kwargs: Optional[Dict[str, Any]]

    def __str__(self) -> str:
        m = self.msg % self.args if self.args else self.msg
        kw = " " + str(self.kwargs) if self.kwargs else ""
        return f'[{self.time.strftime("%Y-%m-%d %T")}] {self.level} {m}{kw}'


def _log(
    source: str,
    level: Level,
    msg: str,
    args: Any,
    kwargs: Any,
    ex: Optional[BaseException] = None,
) -> LogEntry:
    return LogEntry(
        time=datetime.now(),
        level=level,
        source=source,
        msg=msg,
        ex=ex,
        args=args,
        kwargs=kwargs,
    )


def build(app_name: str) -> InMemoryTelemetry:
    global_props = {
        "app": app_name,
        "host": get_host_name(),
        "env": get_environment_name(app_name),
        "ver": get_app_version(app_name),
    }
    return InMemoryTelemetry(app_name, global_props)


class _Metric:
    def __init__(self, name: str, props: Optional[Dict[str, Any]]):
        self._name = name
        self._props = props
        self._data: List[Tuple[datetime, float]] = []

    @property
    def name(self) -> str:
        return self._name

    @property
    def data(self) -> List[Tuple[datetime, float]]:
        return self._data

    def track(self, value: Union[int, float]) -> None:
        self._data.append((datetime.utcnow(), value))

    def clear(self) -> None:
        self._data.clear()

    def __str__(self) -> str:
        return self._name
