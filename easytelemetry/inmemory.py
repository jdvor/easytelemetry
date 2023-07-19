"""
This module contains in-memory implementation for the telemetry.
It is useful for unit testing and NOT anywhere else where it would quickly
lead to OOM, because the implementations collect indefinatelly the logs
and metric entries unless explicitly told to clear them.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime
from typing import Any, TypeAlias

from easytelemetry import (
    Level,
    Logger,
    MetricFuncT,
    MetricFuncWithPropsT,
    PropsT,
    StdLoggingHandler,
    Telemetry,
    create_props,
    get_app_version,
    get_environment_name,
    get_host_name,
    merge_props,
)


@dataclass(frozen=True)
class LogEntry:
    time: datetime
    level: Level
    source: str
    msg: str
    ex: BaseException | None
    args: tuple[Any, ...] | None
    props: PropsT | None

    def __str__(self) -> str:
        m = self.msg % self.args if self.args else self.msg
        kw = " " + str(self.props) if self.props else ""
        return f'[{self.time.strftime("%Y-%m-%d %T")}] {self.level} {m}{kw}'


class Metric:
    def __init__(self, name: str, props: PropsT | None):
        self._name = name
        self._props = props
        self._data: list[MetricRecordT] = []

    @property
    def name(self) -> str:
        return self._name

    @property
    def data(self) -> list[MetricRecordT]:
        return self._data

    def track(self, value: int | float) -> None:
        self._data.append((datetime.utcnow(), value, None))

    def track_extra(self, value: int | float, extra: PropsT) -> None:
        self._data.append((datetime.utcnow(), value, extra))

    def clear(self) -> None:
        self._data.clear()

    def __str__(self) -> str:
        return self._name


MetricRecordT: TypeAlias = tuple[datetime, float, PropsT | None]
LogPredFuncT: TypeAlias = Callable[[LogEntry], bool]
MetricPredFuncT: TypeAlias = Callable[[Metric], bool]


def build(
    app_name: str,
    setup_std_logging: bool = True,
    clear_std_logging_handlers: bool = False,
) -> InMemoryTelemetry:
    """
    Build in-memory telemetry instance.

    :param app_name: Application name
    :param setup_std_logging: Setup in-memory telemetry
        as a logging record handler in standard :mod:`logging` module
    :param clear_std_logging_handlers: Clear all logging record handlers
        in standard :mod:`logging` module before the telemetry
        is registered as a handler too
    """
    global_props: PropsT = {
        "app": app_name,
        "host": get_host_name(),
        "env": get_environment_name(app_name),
        "ver": get_app_version(app_name),
    }
    imt = InMemoryTelemetry(app_name, global_props)
    if setup_std_logging:
        handler = StdLoggingHandler(imt)
        handler.configure_std_logging(clear_std_logging_handlers)
    return imt


class InMemoryTelemetry(Telemetry):
    def __init__(
        self,
        name: str,
        global_props: PropsT,
        min_level: Level = Level.INFO,
    ):
        self._name = name
        self._global_props = global_props
        self._min_level = min_level
        self._logs: list[LogEntry] = []
        self._rootlgr = InMemoryLogger(
            "_root",
            min_level,
            global_props,
            self._logs,
        )
        self._loggers: dict[str, Logger] = {self._rootlgr.name: self._rootlgr}
        self._metrics: dict[str, Metric] = {}

    @property
    def root(self) -> Logger:
        return self._rootlgr

    @property
    def name(self) -> str:
        return self._name

    @property
    def logs(self) -> list[LogEntry]:
        return self._logs

    @property
    def metrics(self) -> dict[str, Metric]:
        return self._metrics

    @property
    def min_level(self) -> Level:
        return self._min_level

    def logger(
        self,
        name: str,
        level: Level = Level.INFO,
        props: PropsT | None = None,
    ) -> Logger:
        lgr = self._loggers.get(name)
        if not lgr:
            lvl = level if level else self._min_level
            extra = (
                {**self._global_props, **props}
                if props
                else self._global_props
            )
            lgr = InMemoryLogger(name, lvl, extra, self._logs)
            self._loggers[name] = lgr
        return lgr

    def metric(
        self,
        name: str,
        props: PropsT | None = None,
    ) -> MetricFuncT:
        m = self._metrics.get(name)
        if not m:
            m = Metric(name, props)
            self._metrics[name] = m
        return m.track

    def metric_extra(
        self,
        name: str,
        props: PropsT | None = None,
    ) -> MetricFuncWithPropsT:
        """Get or create a metric track function of given name."""
        m = self._metrics.get(name)
        if not m:
            m = Metric(name, props)
            self._metrics[name] = m
        return m.track_extra

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
            for time, value, _ in mtr.data:
                print(f'\t[{time.strftime("%Y-%m-%d %T")}] {value}')

    def has_log(self, predicate: LogPredFuncT) -> bool:
        return any(predicate(le) for le in self._logs)

    def all_logs(self, predicate: LogPredFuncT) -> bool:
        return all(predicate(le) for le in self._logs)

    def has_metric(self, predicate: MetricPredFuncT) -> bool:
        return any(predicate(m) for m in self._metrics.values())

    def has_metric_name(self, name: str) -> bool:
        return name in self._metrics

    def all_metrics(self, predicate: MetricPredFuncT) -> bool:
        return all(predicate(m) for m in self._metrics.values())

    def log_count(self, predicate: LogPredFuncT | None = None) -> int:
        if predicate is None:
            return len(self._logs)
        acc = 0
        for le in self._logs:
            acc += int(predicate(le))
        return acc

    def metric_count(self, predicate: MetricPredFuncT | None = None) -> int:
        if predicate is None:
            return len(self._metrics)
        acc = 0
        for m in self._metrics.values():
            acc += int(predicate(m))
        return acc


class InMemoryLogger(Logger):
    def __init__(
        self,
        name: str,
        min_level: Level,
        props: PropsT,
        logs: list[LogEntry],
    ):
        self._name = name
        self._level = min_level
        self._props = props
        self._logs = logs

    @property
    def name(self) -> str:
        return self._name

    @property
    def level(self) -> Level:
        return self._level

    def debug(self, msg: str, *args: Any, **kwargs: Any) -> None:
        if self._level <= Level.DEBUG:
            props = create_props(kwargs, 3)
            self._enqueue(self._name, Level.DEBUG, msg, args, props)

    def info(self, msg: str, *args: Any, **kwargs: Any) -> None:
        if self._level <= Level.INFO:
            props = create_props(kwargs, 3)
            self._enqueue(self._name, Level.INFO, msg, args, props)

    def warn(self, msg: str, *args: Any, **kwargs: Any) -> None:
        if self._level <= Level.WARN:
            props = create_props(kwargs, 3)
            self._enqueue(self._name, Level.WARN, msg, args, props)

    def error(self, msg: str, *args: Any, **kwargs: Any) -> None:
        if self._level <= Level.ERROR:
            props = create_props(kwargs, 3)
            self._enqueue(self._name, Level.ERROR, msg, args, props)

    def critical(self, msg: str, *args: Any, **kwargs: Any) -> None:
        props = create_props(kwargs, 3)
        self._enqueue(self._name, Level.CRITICAL, msg, args, props)

    def exception(
        self,
        ex: BaseException,
        level: Level = Level.ERROR,
        **kwargs: Any,
    ) -> None:
        props = merge_props(self._props, kwargs)
        self._enqueue(self._name, level, str(ex), None, props, ex)

    def __str__(self) -> str:
        return f"{self._name}:{self._level}"

    def _enqueue(
        self,
        source: str,
        level: Level,
        msg: str,
        args: tuple[Any, ...] | None,
        props: PropsT,
        ex: BaseException | None = None,
    ) -> None:
        props = merge_props(self._props, props)
        entry = LogEntry(
            time=datetime.now(),
            level=level,
            source=source,
            msg=msg,
            ex=ex,
            args=args,
            props=props,
        )
        self._logs.append(entry)
