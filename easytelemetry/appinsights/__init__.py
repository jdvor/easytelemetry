"""This module contains telemetry implementation using Application Insights."""

from __future__ import annotations

import atexit
import concurrent.futures as cf
from dataclasses import dataclass
from datetime import datetime
import os
import platform
import posixpath
from queue import Empty, Queue
import re
import tempfile
import threading
import time
from types import TracebackType
from typing import (
    Any,
    Callable,
    Dict,
    Generator,
    List,
    Optional,
    Protocol,
    Sequence,
    Tuple,
    TypeAlias,
    Union,
)

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
    get_host_ip,
    get_host_name,
    merge_props,
)
import easytelemetry.appinsights.protocol as p


DEFAULT_INGESTION = "https://dc.services.visualstudio.com/v2/track"


def build(
    app_name: str,
    configure: Optional[Callable[[Options], None]] = None,
    options: Optional[Options] = None,
    publisher: Optional[Publisher] = None,
    executor: Optional[cf.ThreadPoolExecutor] = None,
) -> AppInsightsTelemetry:
    """
    Build telemetry instance based on Azure Application Insights service.

    :param app_name: Application name
    :param configure: Configuration method used to tweak options
        before the telemetry instance is created; this is used modify
        few properties on :class:`Options` while all others
        are kept with defaults
    :param options: If you do not want telemetry options to be created
        using conventions and defaults, you can pass your own instance
    :param publisher: A publisher to use for publishing to ingestion endpoint;
        if none is passed than :class:`DefaultPublisher` is created and used
    :param executor: If publisher is passed than this argument is ignored;
        otherwise used to create :class:`DefaultPublisher`
    """
    global_props = {
        "app": app_name,
        "env": get_environment_name(app_name),
    }
    tags = {
        p.TagKey.CLOUD_ROLE_INSTANCE: get_host_name(),
        p.TagKey.LOCATION_IP: get_host_ip(),
        p.TagKey.APP_VER: get_app_version(app_name),
    }
    opts = options or Options.from_env(app_name)
    if configure:
        configure(opts)
    pub = DefaultPublisher(opts, executor) if publisher is None else publisher
    ait = AppInsightsTelemetry(app_name, global_props, tags, opts, pub)
    if opts.setup_std_logging:
        handler = StdLoggingHandler(ait)
        handler.configure_std_logging()
        ait.register_std_logging_handler(handler)
    return ait


@dataclass(frozen=True)
class ConnectionString:
    instrumentation_key: str
    ingestion_endpoint: str = DEFAULT_INGESTION
    live_endpoint: Optional[str] = None

    _FULL_PATTERN = (
        r"^(InstrumentationKey\s*=\s*)?"
        + r"(?P<key>[0-9a-f]{8}-([0-9a-f]{4}-){3}[0-9a-f]{12})"
        + r"(\s*;\s*IngestionEndpoint\s*=\s*(?P<ingest>https://[^;\s]+))?"
        + r"(\s*;\s*LiveEndpoint\s*=\s*(?P<live>https://\S+))?$"
    )

    @staticmethod
    def from_str(cs: str) -> ConnectionString:
        """Parse string to get ingestion endpoint and instrumentation key."""
        if not cs:
            raise ValueError("invalid connection string")
        m = re.match(ConnectionString._FULL_PATTERN, cs.strip(), re.IGNORECASE)
        if not m:
            raise ValueError("invalid connection string")

        key = m.group("key")

        ingest = m.group("ingest")
        if ingest:
            if not ingest.endswith("/v2/track"):
                ingest = posixpath.join(ingest, "v2/track")
        else:
            ingest = DEFAULT_INGESTION

        live = m.group("live") or None

        return ConnectionString(key, ingest, live)


def get_env_var(app_name: str, var_name: str) -> Optional[str]:
    """
    Get environment variable with or even without application name prefix,
    whatever is present at the time.
    """
    prefixed_name = f"{app_name.upper()}_{var_name}"
    return os.environ.get(prefixed_name) or os.environ.get(var_name)


def ensure_local_storage(app_name: str) -> str:
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


@dataclass
class Options:
    connection: ConnectionString
    use_local_storage: bool = False
    local_storage_path: Optional[str] = None
    min_level: Level = Level.INFO
    queue_maxsize: int = 1000
    batch_maxsize: int = 100
    publish_interval_secs: float = 20
    publish_timeout_secs: float = 10
    max_publishing_workers: Optional[int] = None
    debug: bool = False
    setup_std_logging: bool = False
    clear_std_logging_handlers: bool = False
    use_atexit: bool = False

    CONNECTION_STRING_ENV_VAR = "APPLICATIONINSIGHTS_CONNECTION_STRING"
    USE_LOCAL_STORAGE_ENV_VAR = "APPLICATIONINSIGHTS_USE_LOCAL_STORAGE"
    _ERRMSG_ENVVAR = "Application Insights connection string environment " + "variable is not set"
    _ERRMSG_STORAGE = "Application Insights local storage " + "directory does not exist"

    @staticmethod
    def from_env(app_name: str) -> Options:
        """Create options from expected environment variables."""
        conn_str = get_env_var(app_name, Options.CONNECTION_STRING_ENV_VAR)
        if conn_str is None:
            raise EnvironmentError(Options._ERRMSG_ENVVAR)
        local = get_env_var(app_name, Options.USE_LOCAL_STORAGE_ENV_VAR)
        return Options.from_connection_str(app_name, conn_str, bool(local))

    @staticmethod
    def from_connection_str(
        app_name: str,
        conn_str: str,
        use_local: Union[bool, str] = False,
    ) -> Options:
        """
        Create options from connection string, which is only mandatory part
        and the rest is populated by defaults.
        """
        cs = ConnectionString.from_str(conn_str)

        if isinstance(use_local, bool):
            if use_local:
                storage_path = ensure_local_storage(app_name)
            else:
                storage_path = None
        else:
            if use_local:
                if not os.path.isdir(use_local):
                    raise EnvironmentError(Options._ERRMSG_STORAGE)
                storage_path = use_local
                use_local = True
            else:
                storage_path = None
                use_local = False

        return Options(cs, use_local, storage_path)


FlushT: TypeAlias = Tuple[Optional[bool], Optional[List[Exception]]]


class AppInsightsTelemetry(Telemetry):
    def __init__(self, name: str, global_props: PropsT, tags: Dict[str, str], options: Options, publisher: Publisher):
        self._name = name
        self._global_props = global_props
        self._tags = tags
        self._options = options
        self._publishing: Optional[threading.Timer] = None
        self._queue: Queue[p.Envelope] = Queue(maxsize=options.queue_maxsize)
        self._rootlgr = AppInsightsLogger(
            "_root",
            options.min_level,
            global_props,
            self._queue,
        )
        self._loggers: Dict[str, Logger] = {self._rootlgr.name: self._rootlgr}
        self._metrics: Dict[str, _Metric] = {}
        self._publisher = publisher
        self._std_logging_handler: Optional[StdLoggingHandler] = None

    @property
    def root(self) -> Logger:
        """Default logger; created automatically with the name '_root'."""
        return self._rootlgr

    @property
    def name(self) -> str:
        return self._name

    @property
    def min_level(self) -> Level:
        return self._options.min_level

    def logger(
        self,
        name: str,
        level: Level = Level.INFO,
        props: Optional[PropsT] = None,
    ) -> Logger:
        lgr = self._loggers.get(name)
        if lgr is None:
            min_level = level if level else self._options.min_level
            properties = merge_props(self._global_props, props)
            lgr = AppInsightsLogger(name, min_level, properties, self._queue)
            self._loggers[name] = lgr
        return lgr

    def metric(
        self,
        name: str,
        props: Optional[PropsT] = None,
    ) -> MetricFuncT:
        metric = self._metrics.get(name)
        if metric is None:
            properties = merge_props(self._global_props, props)
            metric = _Metric(name, properties, self._queue)
            self._metrics[name] = metric
        return metric.track

    def metric_extra(
        self,
        name: str,
        props: Optional[PropsT] = None,
    ) -> MetricFuncWithPropsT:
        metric = self._metrics.get(name)
        if metric is None:
            properties = merge_props(self._global_props, props)
            metric = _Metric(name, properties, self._queue)
            self._metrics[name] = metric
        return metric.track_extra

    def describe(self) -> str:
        logger_names = [str(x) for x in self._loggers.keys()]
        metric_names = [str(x) for x in self._metrics.keys()]
        pub = "no" if self._publishing is None else f"yes ({self._publishing.name})"
        s = [
            f"name: {self._name}",
            f'loggers: {", ".join(logger_names)}',
            f'metrics: {", ".join(metric_names)}',
            f"local_dir: {self._options.local_storage_path}",
            f"auto-publishing: {pub}",
        ]
        return "\n".join(s)

    def register_std_logging_handler(self, h: StdLoggingHandler) -> None:
        self._std_logging_handler = h

    def start_publishing(self) -> None:
        if self._publishing is not None:
            return
        self._publishing = threading.Timer(interval=self._options.publish_interval_secs, function=self.flush)
        if self._options.use_atexit:
            atexit.register(self.stop_publishing)
        self._publishing.start()

    def stop_publishing(self) -> None:
        if self._publishing is None:
            return
        self._publishing.cancel()
        self._publishing = None
        if self._options.use_atexit:
            atexit.unregister(self.stop_publishing)
        self.flush()
        if self._std_logging_handler is not None:
            self._std_logging_handler.close()
            self._std_logging_handler = None

    def flush(self) -> FlushT:
        try:
            if self._std_logging_handler is not None:
                self._std_logging_handler.flush()
            if self._queue.qsize() <= 0:
                return None, None
            results = self._publisher.publish(self._queue)
            success = all([x.success for x in results])
            errors = None if success else [x.exception for x in results if x.exception is not None]
            return success, errors
        except RuntimeError as e:
            _error("failed to publish telemetry data", e)
            return False, [e]

    def __enter__(self) -> AppInsightsTelemetry:
        self.start_publishing()
        return self

    def __exit__(
        self,
        exc_type: BaseException | None,
        exc_val: BaseException | None,
        exc_tb: TracebackType | None,
    ) -> None:
        self.stop_publishing()
        self._publisher.close()

    def __str__(self) -> str:
        return f"AppInsightsTelemetry: name={self._name})"


class AppInsightsLogger(Logger):
    def __init__(
        self,
        name: str,
        min_level: Level,
        props: PropsT,
        queue: Queue,
    ):
        self._name = name
        self._level = min_level
        self._props = props if name == "_root" else {"logger": name, **props}
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
        props: Optional[PropsT],
    ) -> None:
        message = msg % args
        properties = merge_props(self._props, props)
        data = p.MessageData(
            message=message,
            severityLevel=severity,
            properties=properties,
        )
        envelope = data.to_envelope()
        self._queue.put_nowait(envelope)

    def debug(self, msg: str, *args: Any, **kwargs: Any) -> None:
        if self._level <= Level.DEBUG:
            props = create_props(kwargs, 3)
            self._enqueue(p.SeverityLevel.VERBOSE, msg, args, props)

    def info(self, msg: str, *args: Any, **kwargs: Any) -> None:
        if self._level <= Level.INFO:
            props = create_props(kwargs, 3)
            self._enqueue(p.SeverityLevel.INFORMATION, msg, args, props)

    def warn(self, msg: str, *args: Any, **kwargs: Any) -> None:
        if self._level <= Level.WARN:
            props = create_props(kwargs, 3)
            self._enqueue(p.SeverityLevel.WARNING, msg, args, props)

    def error(self, msg: str, *args: Any, **kwargs: Any) -> None:
        if self._level <= Level.ERROR:
            props = create_props(kwargs, 3)
            self._enqueue(p.SeverityLevel.ERROR, msg, args, props)

    def critical(self, msg: str, *args: Any, **kwargs: Any) -> None:
        props = create_props(kwargs, 3)
        self._enqueue(p.SeverityLevel.CRITICAL, msg, args, props)

    def exception(
        self,
        ex: BaseException,
        level: Level = Level.ERROR,
        **kwargs: Any,
    ) -> None:
        if self._level > level:
            return
        props = merge_props(self._props, kwargs)
        data = p.ExceptionData.create(
            ex=ex,
            level=_level_to_severity(level),
            properties=props,
        )
        envelope = data.to_envelope()
        self._queue.put_nowait(envelope)

    def __str__(self) -> str:
        return f"{self._name}:{self._level}"


class _Metric:
    def __init__(self, name: str, props: PropsT, queue: Queue):
        self._name = name
        self._props = props
        self._queue = queue

    @property
    def name(self) -> str:
        return self._name

    def track_extra(self, value: Union[int, float], extra: PropsT) -> None:
        self._track(value, self._props | extra)

    def track(self, value: Union[int, float]) -> None:
        self._track(value, self._props)

    def _track(self, value: Union[int, float], props: PropsT) -> None:
        envelope = p.MetricData.create(
            name=self._name,
            value=value,
            properties=props,
        ).to_envelope()
        self._queue.put_nowait(envelope)

    def __str__(self) -> str:
        return self._name


def _level_to_severity(level: Level) -> p.SeverityLevel:  # noqa: CFQ004
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


class Publisher(Protocol):
    def publish(self, source: Queue[p.Envelope]) -> List[p.PublishResult]:
        pass

    def close(self) -> None:
        pass


class DefaultPublisher:
    """
    Publishes envelopes from the source (queue) and thus consuming them.
    Envelopes are packed in batches and published to ingestion endpoint.
    It can work using internal ThreadPoolExecutor or one passed from outside
    as means of dispatching HTTP requests to ingestion endpoint.
    """

    def __init__(self, options: Options, executor: Optional[cf.ThreadPoolExecutor] = None):
        self._options = options
        if executor:
            self._executor = executor
            self._owns_executor = False
        else:
            workers = (
                options.max_publishing_workers if options.max_publishing_workers else min(8, (os.cpu_count() or 1) + 1)
            )
            self._executor = cf.ThreadPoolExecutor(max_workers=workers)
            self._owns_executor = True

    def publish(self, source: Queue[p.Envelope]) -> List[p.PublishResult]:
        """
        Consume the source (queue) and publish everything collected
        upto this point to Application Insights ingestion endpoint.
        """
        batches = _create_batches(source, self._options)
        tasks = self._executor.map(self._send_batch, batches, timeout=self._options.publish_timeout_secs)
        result = [x for x in tasks]
        return result

    def _send_batch(self, batch: Sequence[p.Envelope]) -> p.PublishResult:
        url = self._options.connection.ingestion_endpoint
        result = p.send_batch(batch, url)
        if not result.success:
            self._on_failure(batch, result)
        return result

    def close(self) -> None:
        if self._owns_executor:
            self._executor.shutdown(wait=True)

    def _on_failure(self, batch: Sequence[p.Envelope], r: p.PublishResult) -> None:
        """Handle publishing failure."""
        attempts = "" if r.attempt < 1 else f" after {r.attempt} attempts"
        msg = f"Failed to publish {len(batch)} " + f"envelopes{attempts}; result: {r}"
        _error(msg)
        # TODO: saving batches to disk and sending them later


def _create_batches(
    source: Queue[p.Envelope],
    opts: Options,
) -> Generator[Sequence[p.Envelope], None, None]:
    """Consume the source (queue) and create batches to be published."""
    batch: List[p.Envelope] = []
    n = 0
    while True:
        try:
            envelope = source.get_nowait()
            envelope.iKey = opts.connection.instrumentation_key
            envelope.seq = str(time.time_ns() // 1_000_000)
            batch.append(envelope)
            n += 1
            if n == opts.batch_maxsize:
                yield batch
                batch.clear()
                n = 0
        except Empty:
            if n > 0:
                yield batch
            return


EnvelopePredicateT: TypeAlias = Callable[[p.Envelope], bool]


class MockPublisher:
    """
    Publisher for testing purposes. It will not send anything
    to ingestion endpoint.
    It will consume original queue and move all its items to its own
    internal collection, which can be used for test asserts.
    """

    def __init__(self, batch_maxsize: int = 100, result_fn: Optional[Callable[[], p.PublishResult]] = None):
        self._data: List[p.Envelope] = []
        self._batch_maxsize = batch_maxsize
        self._result_fn = lambda: p.PublishResult(True, 200) if result_fn is None else result_fn

    @property
    def data(self) -> List[p.Envelope]:
        return self._data

    def publish(self, source: Queue[p.Envelope]) -> List[p.PublishResult]:
        i = 0
        while True:
            try:
                envelope = source.get_nowait()
                envelope.iKey = "00000000-0000-0000-0000-000000000000"
                envelope.seq = str(time.time_ns() // 1_000_000)
                self._data.append(envelope)
                i += 1
            except Empty:
                n = -(i // -self._batch_maxsize)
                return [self._result_fn() for _ in range(0, n)]

    def close(self) -> None:
        # no-op
        pass

    def clear(self) -> None:
        self._data.clear()

    def any(self, predicate: EnvelopePredicateT) -> bool:
        for x in self._data:
            if predicate(x):
                return True
        return False

    def first(self, predicate: EnvelopePredicateT) -> bool:
        return False if len(self._data) == 0 else predicate(self._data[0])

    def last(self, predicate: EnvelopePredicateT) -> bool:
        length = len(self._data)
        return False if length == 0 else predicate(self._data[length - 1])

    def all(self, predicate: EnvelopePredicateT) -> bool:
        for x in self._data:
            if not predicate(x):
                return False
        return True

    def count(self, predicate: Optional[EnvelopePredicateT] = None) -> int:
        if predicate is None:
            return len(self._data)
        return sum((1 for x in self._data if predicate(x)))

    def is_empty(self) -> int:
        return len(self._data) == 0


_safe_print = threading.RLock()


def _error(msg: str, ex: Optional[RuntimeError] = None) -> None:
    """
    Do not use `logging.exception()` here or any other logging method,
    because telemetry can be hooked as handler in standard Python logging,
    and therefore it could very likely lead to aggravating the issue.
    """
    with _safe_print:
        now = datetime.now().strftime("%H:%M:%S.%f")
        e = "" if ex is None else f", {ex}"
        print(f"[{now}] {msg}{e}")