# easytelemetry

This package aims to provide easiest way how to use both logging
and metric telemetry for your python code with [Azure Application Insights][1]
SaaS as a backing store for telemetry.

The main motivation for creating this package is that [Open Census][2]
interface, which is recommended by Microsoft to use instead of their own
and now discontinued [applicationinsights][3], is simply overly and needlessly
[complicated][4]. The reason why Open Census is not a good client layer
for Application Insights is that its design is aimed towards optimizing
pre-aggregation of metrics and filtering/grouping by tags locally,
which is not needed for AI. In fact, it usually just complicates things
even further.

For testing purposes the package also includes in-memory implementation, which does not publish anything
and can be used in tests for assertion statements.

## 1. Quick Start

1) Create Application Insights resource in your Azure Portal
and obtain connection string for the client.

2) Set-up environment property `MYAPP_APPLICATION_INSIGHTS_CONNECTION_STRING`
or `APPLICATION_INSIGHTS_CONNECTION_STRING`.

3) Than:
```python
import time
from easytelemetry.appinsights import build
from easytelemetry import Telemetry

with build("myapp") as telemetry:
    telemetry: Telemetry
    exec_incr = telemetry.metric_incr("executions")
    elapsed = telemetry.metric_timer("elapsed_ms")

    for _ in range(0, 5):
        exec_incr()
        elapsed()
        time.sleep(1)

    telemetry.root.info("we are done")
```

## 2. Usage

### 2.1. Telemetry instance lifetime
`AppInsightsTelemetry` collects logs and metrics into internal queue and periodically publishes them
to Application Insights backend in (configurable) periodic interval. The default is 20 seconds.
The publishing is done in background using `concurrent.futures.ThreadPoolExecutor` and the publishing
does not start automatically when `AppInsightsTelemetry` is instantiated, but has to be explicitly started and stopped.
The easiest way how to achieve it is to use context manager semantics with `AppInsightsTelemetry`
or calling directly methods `start_publishing` and `stop_publishing`.

### 2.2. Advanced (beyond Quick Start) configuration
Most things can be configured on `AppInsightsTelemetry` by passing `easytelemetry.appinsights.Options` instance
to `easytelemetry.appinsights.build` build method.

Alternatively the same build method accepts configure function `Callable[[Options], None]` in which you can change
just one or two properties while all others are populated by defaults and derived from environment properties.

```python
from easytelemetry import Telemetry, Level
from easytelemetry.appinsights import build, Options

def configure(opts: Options) -> None:
    opts.publish_interval_secs = 10
    opts.min_level = Level.WARN

with build("myapp", configure=configure) as telemetry:
    telemetry: Telemetry

    # use telemetry
```

### 2.3. Setting up the telemetry as handler for standard logging subsystem
If you are used to use `logging.info()` or other calls to Python's standard logging subsytem, you can continue to do.
AppInsightsTelemetry could be added as a custom log record handler.

```python
import logging
from easytelemetry.appinsights import build, Options

def configure(opts: Options) -> None:
    opts.setup_std_logging = True
    opts.clear_std_logging_handlers = True

with build("myapp", configure=configure):
    logging.info("message using standard logging")
```

If you'd like the AppInsightsTelemetry to be the **only** handler in the logging subsystem,
pass `clear_std_logging_handlers=True` to build function.

### 2.4. Using custom dimensions
Custom dimensions are a way how to add metadata to any log or metric entry in Application Insights.
This allows them to be filtered, groupped or correlated with each other later on.

By default, these dimensions are added to every logger or metric:

| dimension           | tag name              | how it is determined                                                                    | default value |
|---------------------|-----------------------|-----------------------------------------------------------------------------------------|---------------|
| Application name    | app                   | passed to build function                                                                | -             |
| Environment name    | env                   | environment variables {AppName}_ENVIRONMENT, ENVIRONMENT or AZURE_FUNCTIONS_ENVIRONMENT | prod          |
| Host name           | ai.cloud.roleInstance | environment variable COMPUTERNAME or `platform.node()`                                  | -             |
| Host IP address     | ai.location.ip        | `socket.gethostbyname()`                                                                | -             |
| Application version | ai.application.ver    | environment variables {AppName}_APP_VERSION or APP_VERSION                              | 0.0.0.0       |

Methods for creating loggers, metrics or even individual entries have parameter props `Optional[Dict[str, Any]]`,
which you can use to enrich already defined custom dimensions. Global dimensions mentioned above are merged together
with local ones before the log entry or metric entry is published.

### 2.5. Using in-memory implementation for tests

**conftest.py**
```python
import pytest
from easytelemetry.inmemory import build, InMemoryTelemetry

@pytest.fixture()
def telemetry() -> InMemoryTelemetry:
    return build("tests")
```

**test_example.py**
```python
from easytelemetry import Level
from easytelemetry.inmemory import InMemoryTelemetry

def test_my_example(telemetry: InMemoryTelemetry):
    # execute some code using telemetry
    # ...
    assert telemetry.has_log(lambda x: x.level == Level.WARN and "deprecated" in x.msg)
    assert telemetry.metric_count() == 5
```

If convenience methods `has_log`, `has_metric`, `log_count` or `metric_count` are not enough you can make assertions
in tests using directly properties `inmem.metrics` and `inmem.logs`.

## 3. Examples

* [simple logging](examples/simple_logging.py)
* [exception logging](examples/exception_logging.py)
* [using metrics](examples/metrics.py)
* [using timers (specialized metric)](examples/timers.py)
* [using activity to correlate several logs and/or metrics together](examples/activity.py)
* [using easytelemetry as a custom logger in standard library logging system](examples/standard_logging.py)


[1]: https://learn.microsoft.com/en-us/azure/azure-monitor/app/app-insights-overview?tabs=net
[2]: https://learn.microsoft.com/en-us/azure/azure-monitor/app/opencensus-python#introducing-opencensus-python-sdk
[3]: https://pypi.org/project/applicationinsights/
[4]: https://github.com/census-instrumentation/opencensus-python/issues/1009
