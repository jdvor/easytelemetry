"""This module contains telemetry implementations using Application Insights."""

from __future__ import annotations

import os
import platform
import posixpath
import re
import tempfile
from dataclasses import dataclass
from queue import Queue
from types import TracebackType
from typing import Any, Callable, Dict, Optional, Union

import easytelemetry.appinsights.protocol as p
from easytelemetry.interface import (
    Level,
    Logger,
    Telemetry,
    get_app_version,
    get_environment_name,
    get_host_name,
)


def build(
    app_name: str,
    options: Optional[Options] = None,
) -> AppInsightsTelemetry:
    """Create telemetry instance (factory method)."""
    global_props = {
        "app": app_name,
        "host": get_host_name(),
        "env": get_environment_name(app_name),
        "ver": get_app_version(app_name),
    }
    opts = options or Options.from_env(app_name)
    return AppInsightsTelemetry(app_name, global_props, opts)


@dataclass(frozen=True)
class Options:
    instrumentation_key: str
    ingestion_url: str
    local_storage_path: str
    min_level: Level = Level.INFO
    queue_maxsize: int = 10000
    batch_maxsize: int = 100

    DEFAULT_INGESTION_URL = "https://dc.services.visualstudio.com/v2/track"
    DEFAULT_ENV_VAR = "APPLICATIONINSIGHTS_CONNECTION_STRING"

    @staticmethod
    def from_env(app_name: str) -> Options:
        env_var = f"{app_name.upper()}_{Options.DEFAULT_ENV_VAR}"
        cs = os.environ.get(env_var) or os.environ.get(Options.DEFAULT_ENV_VAR)
        return Options.from_connection_string(app_name, cs)

    @staticmethod
    def from_connection_string(app_name: str, cs: str) -> Options:
        if not cs:
            raise ValueError("invalid connection string")
        pattern = r"^(InstrumentationKey\s*=\s*)?" + \
                  r"(?P<key>[0-9a-f]{8}-([0-9a-f]{4}-){3}[0-9a-f]{12})" + \
                  r"(\s*;\s*IngestionEndpoint\s*=\s*(?P<url>https://\S+))?$"
        m = re.match(pattern, cs.strip(), re.IGNORECASE)
        if not m:
            raise ValueError("invalid connection string")
        key = m.group("key")
        url = m.group("url")
        if not url:
            url = Options.DEFAULT_INGESTION_URL
        if not url.endswith("/v2/track"):
            url = posixpath.join(url, "v2/track")
        local_storage_path = Options._ensure_local_storage(app_name)
        return Options(key, url, local_storage_path)

    @staticmethod
    def _ensure_local_storage(app_name: str) -> str:
        """
        Find or create the best directory for storing temporary files required
        for uploading collected Application Insights traces and metrics.
        In Azure this storage path might be temporary and not meant
        as long-term storage.
        """
        ostype = platform.system()
        dirs = (
            [r"C:\home\LogFiles\Application", r"D:\WorkSpace", r"C:\WorkSpace"]
            if ostype == "Windows"
            else [r"/home/LogFiles/Application", r"/var/log"]
        )
        for d in dirs:
            if os.path.exists(d):
                storage_dir = os.path.join(d, app_name)
                if not os.path.exists(storage_dir):
                    os.mkdir(storage_dir)
                return storage_dir

        return tempfile.mkdtemp(prefix=app_name)


class AppInsightsTelemetry(Telemetry):
    def __init__(
        self,
        name: str,
        global_props: Dict[str, Any],
        options: Options
    ):
        self._name = name
        self._global_props = global_props
        self._options = options
        self._queue: Queue = Queue(maxsize=options.queue_maxsize)
        self._rootlgr = AppInsightsLogger(
            "_root",
            options.min_level,
            global_props,
            self._queue,
        )
        self._loggers: Dict[str, Logger] = {self._rootlgr.name: self._rootlgr}
        self._metrics: Dict[str, _Metric] = {}

    @property
    def root(self) -> Logger:
        return self._rootlgr

    @property
    def name(self) -> str:
        return self._name

    def logger(
        self,
        name: str,
        level: Level = Level.INFO,
        props: Optional[Dict[str, Any]] = None,
    ) -> Logger:
        lgr = self._loggers.get(name)
        if not lgr:
            min_level = level if level else self._options.min_level
            extra = (
                {**self._global_props, **props} if props else self._global_props
            )
            lgr = AppInsightsLogger(name, min_level, extra, self._queue)
            self._loggers[name] = lgr
        return lgr

    def metric(
        self,
        name: str,
        props: Optional[Dict[str, Any]] = None,
    ) -> Callable[[Union[int, float]], None]:
        metric = self._metrics.get(name)
        if not metric:
            extra = _merge_extra(self._global_props, props)
            metric = _Metric(name, extra, self._queue)
            self._metrics[name] = metric
        return metric.track

    def describe(self) -> str:
        logger_names = [str(x) for x in self._loggers.values()]
        metric_names = [str(x) for x in self._metrics.values()]
        s = [
            f"name: {self._name}",
            f'loggers: {", ".join(logger_names)}',
            f'metrics: {", ".join(metric_names)}',
            f"local_dir: {self._options.local_storage_path}",
        ]
        return "\n".join(s)

    def __enter__(self) -> AppInsightsTelemetry:
        return self

    def __exit__(
        self,
        exc_type: BaseException | None,
        exc_val: BaseException | None,
        exc_tb: TracebackType | None,
    ) -> None:
        pass

    def __str__(self) -> str:
        return f"AppInsightsTelemetry: name={self._name})"


class AppInsightsLogger(Logger):
    def __init__(
        self,
        name: str,
        min_level: Level,
        extra: Dict[str, Any],
        queue: Queue,
    ):
        self._name = name
        self._level = min_level
        self._extra = extra
        self._queue = queue

    @property
    def name(self) -> str:
        return self._name

    @property
    def level(self) -> Level:
        return self._level

    def _enqueue(
        self,
        severity: p.SeverityLevel,
        msg: str,
        args: Any,
        kwargs: Any,
    ) -> None:
        message = msg % args
        extra = _merge_extra(self._extra, kwargs)
        envelope = p.MessageData(
            message=message,
            severityLevel=severity,
            properties=extra,
        ).to_envelope()
        self._queue.put_nowait(envelope)

    def debug(self, msg: str, *args: Any, **kwargs: Any) -> None:
        if self._level <= Level.DEBUG:
            self._enqueue(p.SeverityLevel.VERBOSE, msg, args, kwargs)

    def info(self, msg: str, *args: Any, **kwargs: Any) -> None:
        if self._level <= Level.INFO:
            self._enqueue(p.SeverityLevel.INFORMATION, msg, args, kwargs)

    def warn(self, msg: str, *args: Any, **kwargs: Any) -> None:
        if self._level <= Level.WARN:
            self._enqueue(p.SeverityLevel.WARNING, msg, args, kwargs)

    def error(self, msg: str, *args: Any, **kwargs: Any) -> None:
        if self._level <= Level.ERROR:
            self._enqueue(p.SeverityLevel.ERROR, msg, args, kwargs)

    def critical(self, msg: str, *args: Any, **kwargs: Any) -> None:
        self._enqueue(p.SeverityLevel.CRITICAL, msg, args, kwargs)

    def exception(
        self,
        ex: BaseException,
        level: Level = Level.ERROR,
        **kwargs: Any,
    ) -> None:
        if self._level > level:
            return
        extra = _merge_extra(self._extra, kwargs)
        envelope = p.ExceptionData.create(
            ex=ex,
            level=_convert_level(level),
            properties=extra,
        ).to_envelope()
        self._queue.put_nowait(envelope)

    def __str__(self) -> str:
        return f"{self._name}:{self._level}"


class _Metric:
    def __init__(self, name: str, extra: Dict[str, Any], queue: Queue):
        self._name = name
        self._extra = extra
        self._queue = queue

    @property
    def name(self) -> str:
        return self._name

    def track(self, value: Union[int, float]) -> None:
        envelope = p.MetricData.create(
            name=self._name,
            value=value,
            properties=self._extra,
        ).to_envelope()
        self._queue.put_nowait(envelope)


def _merge_extra(
    parent_extra: Dict[str, Any],
    additional_extra: Optional[Dict[str, Any]],
) -> Dict[str, Any]:
    if additional_extra:
        return {"custom_dimensions": {**parent_extra, **additional_extra}}
    return {"custom_dimensions": parent_extra}


def _convert_level(level: Level) -> p.SeverityLevel:
    if level == level.DEBUG:
        return p.SeverityLevel.VERBOSE
    if level == level.INFO:
        return p.SeverityLevel.INFORMATION
    if level == level.WARN:
        return p.SeverityLevel.WARNING
    if level == level.ERROR:
        return p.SeverityLevel.ERROR
    if level == level.CRITICAL:
        return p.SeverityLevel.CRITICAL
    return p.SeverityLevel.INFORMATION
