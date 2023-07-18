"""
This module contains serialization classes required
to construct JSON body of HTTP request to Application Insights.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
from enum import Enum
import gzip
import hashlib
import os
import re
import time
import traceback
from typing import Any, Dict, List, Optional, Sequence, Union

import orjson
import requests


# https://github.com/microsoft/ApplicationInsights-dotnet/tree/master/BASE
# /Schema/PublicSchema

MAX_KEY_LENGTH = 128
MAX_VALUE_LENGTH = 8192
SAFE_STR_REGEX = re.compile(f"^[a-zA-Z]\\w{{0,{MAX_KEY_LENGTH - 1}}}$")

GZIP_COMPRESS_LEVEL = 6
GZIP_THRESHOLD_BYTES = 1000
MAX_ATTEMPTS = 3
DELAY_BETWEEN_ATTEMPTS_SECS = 0.5

UNSPECIFIED_ERROR = -1
CONNECTION_ERROR = 0
SUCCESS_HTTP_STATUSES = [200]
RETRYABLE_HTTP_STATUSES = [CONNECTION_ERROR, 500, 502]


def is_safe_key(s: str) -> bool:
    """Determine if the key can be used as metric or logger name."""
    return True if SAFE_STR_REGEX.match(s) else False


def sanitize_value(s: str) -> str:
    """Make sure the string cannot exceed allowed length."""
    return s[:MAX_VALUE_LENGTH] if s and len(s) > MAX_VALUE_LENGTH else s


def serialize(data: Union[Sequence[Envelope], Envelope]) -> bytes:
    def convert(obj: Any) -> str:
        if isinstance(obj, timedelta):
            return str(obj)
        type_name = obj.__class__.__name__
        raise TypeError(f"Type '{type_name}' is not serializable.")

    jsopts = orjson.OPT_NAIVE_UTC | orjson.OPT_UTC_Z
    return orjson.dumps(data, default=convert, option=jsopts)


def deserialize(data: bytes) -> Union[ApiResponseBody, str, None]:
    def errors(node: Any) -> List[ApiResponseError]:
        result = []
        if "errors" in node:
            for e in node["errors"]:
                err = ApiResponseError(
                    index=e["index"],
                    statusCode=e["statusCode"],
                    message=e["message"],
                )
                result.append(err)
        return result

    if not data or len(data) == 0:
        return None
    try:
        obj = orjson.loads(data)
        return ApiResponseBody(
            itemsReceived=obj["itemsReceived"],
            itemsAccepted=obj["itemsAccepted"],
            errors=errors(obj),
        )
    except RuntimeError:
        return data.decode("utf-8")


def http_send(url: str, body: bytes, headers: Dict[str, str], attempt: int) -> PublishResult:
    try:
        resp = requests.post(url, headers=headers, data=body)

        if resp.status_code in SUCCESS_HTTP_STATUSES:
            return PublishResult(True, resp.status_code, attempt)

        resp_body = deserialize(resp.content)
        return PublishResult(False, resp.status_code, attempt, resp_body)

    except requests.exceptions.ConnectionError as ce:
        return PublishResult(False, CONNECTION_ERROR, attempt, exception=ce)

    except Exception as e:
        return PublishResult(False, UNSPECIFIED_ERROR, attempt, exception=e)


def send_batch(
    batch: Sequence[Envelope],
    endpoint: str,
    max_attempts: int = MAX_ATTEMPTS,
    delay_between_attempts_secs: float = DELAY_BETWEEN_ATTEMPTS_SECS,
    gzip_threshold: int = GZIP_THRESHOLD_BYTES,
) -> PublishResult:
    """
    Serialize and send the batch to ingestion endpoint.

    :param batch: sequence of envelopes to publish
    :param endpoint: endpoint URL for publishing
    :param max_attempts: maximum number of publish attempts.
        Use 0 to turn retries off.
    :param delay_between_attempts_secs: wait between publish attempts
        this number of seconds. Use 0 to turn retries off.
    :param gzip_threshold: if serialized payload is larger than this threshold,
        than it will be gzipped. Use -1 for no compression regardless
        of the payload size. The value represents number of bytes.
    :return: object describing publish result
    """
    body = serialize(batch)
    if 0 < gzip_threshold < len(body):
        body = gzip.compress(body, compresslevel=GZIP_COMPRESS_LEVEL)
        headers = {
            "Content-Encoding": "gzip",
            "Content-Type": "application/json",
            "User-Agent": "easytelemetry",
        }
    else:
        headers = {
            "Content-Type": "application/json",
            "User-Agent": "easytelemetry",
        }

    if max_attempts > 1 and delay_between_attempts_secs > 0:
        for attempt in range(1, MAX_ATTEMPTS + 1):
            result = http_send(endpoint, body, headers, attempt)
            end = result.success or attempt == MAX_ATTEMPTS or result.status_code not in RETRYABLE_HTTP_STATUSES
            if end:
                return result
            time.sleep(delay_between_attempts_secs)

        assert False, "code should not reach here ('attempt == MAX_ATTEMPTS')"
    else:
        return http_send(endpoint, body, headers, 1)


@dataclass
class PublishResult:
    """Describes the result of batch publish attempt."""

    success: bool
    status_code: int
    attempt: int = 1
    response_body: Union[ApiResponseBody, str, None] = None
    exception: Optional[Exception] = None


class SeverityLevel(Enum):
    VERBOSE = 0
    INFORMATION = 1
    WARNING = 2
    ERROR = 3
    CRITICAL = 4


class DataPointKind(Enum):
    MEASUREMENT = 0
    AGGREGATION = 1


@dataclass(frozen=True)
class DataPoint:
    """Metric data single measurement."""

    # Name of the metric.
    name: str

    # Single value for measurement.
    # Sum of individual measurements for the aggregation.
    value: float

    # Namespace of the metric.
    ns: str = ""

    # Metric type. Single measurement or the aggregated value.
    # Measurement | Aggregation
    kind: DataPointKind = DataPointKind.MEASUREMENT

    # Metric weight of the aggregated metric.
    # Should not be set for a measurement.
    count: Optional[int] = None

    # Minimum value of the aggregated metric.
    # Should not be set for a measurement.
    min: Optional[float] = None

    # Maximum value of the aggregated metric.
    # Should not be set for a measurement.
    max: Optional[float] = None

    # Standard deviation of the aggregated metric.
    # Should not be set for a measurement.
    stdDev: Optional[float] = None  # noqa: N815


@dataclass(frozen=True)
class EventData:
    """
    Instances of Event represent structured event records
    that can be grouped and searched by their properties.
    Event data item also creates a metric of event count by name.
    """

    # Event name.
    # Keep it low cardinality to allow proper grouping and useful metrics.
    name: str

    # Schema version
    ver: int = 2

    # Collection of custom properties.
    properties: Optional[Dict[str, str]] = None

    # Collection of custom measurements.
    measurements: Optional[Dict[str, float]] = None

    def to_envelope(self, tags: Optional[Dict[str, str]] = None) -> Envelope:
        return Envelope(
            name=Envelope.EVENT_NAME,
            time=datetime.utcnow(),
            data=Data(self, Envelope.EVENT_BASE_TYPE),
            tags=tags,
        )


@dataclass(frozen=True)
class StackFrame:
    """Stack frame information."""

    # Level in the call stack.
    # For the long stacks SDK may not report every function in a call stack.
    level: int

    # Method name.
    method: str

    # Name of the assembly (dll, jar, etc.) containing this function.
    assembly: Optional[str] = None

    # File name or URL of the method implementation.
    fileName: Optional[str] = None  # noqa: N815

    # Line number of the code implementation.
    line: Optional[int] = None


@dataclass(frozen=True)
class ExceptionDetails:
    """Exception details of the exception in a chain."""

    # Exception type name.
    typeName: str  # noqa: N815

    # Exception message.
    message: str

    # List of stack frames. Either stack or parsedStack should have a value.
    parsedStack: Optional[List[StackFrame]] = None  # noqa: N815

    # Text describing the stack.
    # Either stack or parsedStack should have a value.
    stack: Optional[str] = None

    # Indicates if full exception stack is provided in the exception.
    # The stack may be trimmed, such as in the case
    # of a StackOverflow exception.
    hasFullStack: bool = True  # noqa: N815

    # In case exception is nested (outer exception contains inner one),
    # the id and outerId properties are used to represent the nesting.
    id: int = 1

    # The value of outerId is a reference to an element in ExceptionDetails
    # that represents the outer exception.
    outerId: int = 0  # noqa: N815


@dataclass(frozen=True)
class ExceptionData:
    """
    An instance of Exception represents a handled or unhandled exception
    that occurred during execution of the monitored application.
    """

    # Exception chain - list of inner exceptions.
    exceptions: List[ExceptionDetails]

    # Schema version
    ver: int = 2

    # Severity level. Mostly used to indicate exception severity level
    # when it is reported by logging library.
    # Verbose, Information, Warning, Error, Critical,
    severityLevel: SeverityLevel = SeverityLevel.INFORMATION  # noqa: N815

    # Identifier of where the exception was thrown in code.
    # Used for exceptions grouping. Typically, a combination of exception type
    # and a function from the call stack.
    problemId: Optional[str] = None  # noqa: N815

    # Collection of custom properties.
    properties: Optional[Dict[str, str]] = None

    # Collection of custom measurements.
    measurements: Optional[Dict[str, float]] = None

    def to_envelope(self, tags: Optional[Dict[str, str]] = None) -> Envelope:
        return Envelope(
            name=Envelope.EXCEPTION_NAME,
            time=datetime.utcnow(),
            data=Data(self, Envelope.EXCEPTION_BASE_TYPE),
            tags=tags,
        )

    @staticmethod
    def create(
        ex: BaseException,
        level: SeverityLevel = SeverityLevel.ERROR,
        properties: Optional[Dict[str, str]] = None,
        measurements: Optional[Dict[str, float]] = None,
    ) -> ExceptionData:
        mdl = ex.__class__.__module__
        clsname = ex.__class__.__name__
        ex_name = f"{mdl}.{clsname}" if mdl and mdl != "builtins" else clsname
        stack = ExceptionData._parsed_stack(ex)
        details = ExceptionDetails(ex_name, str(ex), stack)
        problem_id = ExceptionData._problem_id(
            ex_name,
            stack[0].fileName,
            stack[0].line,
        )
        return ExceptionData(
            [details],
            severityLevel=level,
            problemId=problem_id,
            properties=properties,
            measurements=measurements,
        )

    @staticmethod
    def _parsed_stack(ex: BaseException) -> List[StackFrame]:
        parsed_stack: List[StackFrame] = []
        frames = traceback.extract_tb(ex.__traceback__)
        level = 1
        prev_path = ""
        prev_file = ""
        frm: traceback.FrameSummary
        for frm in reversed(frames):  # inner to outer
            if level == 1:
                filename = frm.filename
                prev_path = frm.filename
                prev_file = os.path.basename(frm.filename)
            else:
                if prev_path == frm.filename:
                    filename = prev_file
                else:
                    filename = frm.filename
                    prev_path = frm.filename
                    prev_file = os.path.basename(frm.filename)
            method = frm.line if frm.line else ""
            stack_frame = StackFrame(
                level=level,
                method=method,
                fileName=filename,
                line=frm.lineno,
            )
            parsed_stack.append(stack_frame)
            level += 1
        return parsed_stack

    @staticmethod
    def _problem_id(
        exception_name: str,
        file_path: Optional[str],
        line: Optional[int],
    ) -> str:
        alg = hashlib.md5()  # nosec
        bts = f"{file_path}:{line}".encode("utf-8")
        alg.update(bts)
        md5 = alg.hexdigest()
        return f"{exception_name}/{md5}"


@dataclass(frozen=True)
class MessageData:
    """
    Instances of Message represent printf-like trace statements
    that are text-searched. Log4Net, NLog and other text-based log file entries
    are translated into intances of this type.
    The message does not have measurements.
    """

    # Trace message
    message: str

    # Schema version
    ver: int = 2

    # Trace severity level.
    # Verbose, Information, Warning, Error, Critical,
    severityLevel: SeverityLevel = SeverityLevel.INFORMATION  # noqa: N815

    # Collection of custom properties.
    properties: Optional[Dict[str, str]] = None

    # Collection of custom measurements.
    measurements: Optional[Dict[str, float]] = None

    def to_envelope(self, tags: Optional[Dict[str, str]] = None) -> Envelope:
        return Envelope(
            name=Envelope.TRACE_NAME,
            time=datetime.utcnow(),
            data=Data(self, Envelope.TRACE_BASE_TYPE),
            tags=tags,
        )


@dataclass
class MetricData:
    """
    An instance of the Metric item is a list of measurements
    (single data points) and/or aggregations.
    """

    # List of metrics. Only one metric in the list is currently supported
    # by Application Insights storage.
    # If multiple data points were sent only the first one will be used.
    metrics: List[DataPoint]

    # Schema version
    ver: int = 2

    # Collection of custom properties.
    properties: Optional[Dict[str, str]] = None

    def to_envelope(self, tags: Optional[Dict[str, str]] = None) -> Envelope:
        return Envelope(
            name=Envelope.METRIC_NAME,
            time=datetime.utcnow(),
            data=Data(self, Envelope.METRIC_BASE_TYPE),
            tags=tags,
        )

    @staticmethod
    def create(
        name: str,
        value: float,
        properties: Optional[Dict[str, str]] = None,
    ) -> MetricData:
        point = DataPoint(name, value)
        return MetricData([point], properties=properties)


@dataclass
class RemoteDependencyData:
    """
    An instance of Remote Dependency represents an interaction
    of the monitored component with a remote component/service
    like SQL or an HTTP endpoint.
    """

    # Name of the command initiated with this dependency call.
    # Low cardinality value.
    # Examples are stored procedure name and URL path template.
    name: str

    # Request duration in format: DD.HH:MM:SS.MMMMMM.
    # Must be less than 1000 days.
    duration: timedelta

    # Indication of successful or unsuccessful call.
    success: bool = True

    # Schema version
    ver: int = 2

    # Identifier of a dependency call instance.
    # Used for correlation with the request telemetry item corresponding
    # to this dependency call.
    id: Optional[str] = None

    # Result code of a dependency call.
    # Examples are SQL error code and HTTP status code.
    resultCode: Optional[str] = None  # noqa: N815

    # Command initiated by this dependency call.
    # Examples are SQL statement and HTTP URL's with all query parameters.
    data: Optional[str] = None

    # Dependency type name.
    # Very low cardinality value for logical grouping of dependencies
    # and interpretation of other fields like commandName and resultCode.
    # Examples are SQL, Azure table, and HTTP.
    type: Optional[str] = None

    # Target site of a dependency call. Examples are server name, host address.
    target: Optional[str] = None

    # Collection of custom properties.
    properties: Optional[Dict[str, str]] = None

    # Collection of custom measurements.
    measurements: Optional[Dict[str, float]] = None

    def to_envelope(self, tags: Optional[Dict[str, str]] = None) -> Envelope:
        return Envelope(
            name=Envelope.DEPENDENCY_NAME,
            time=datetime.utcnow(),
            data=Data(self, Envelope.DEPENDENCY_BASE_TYPE),
            tags=tags,
        )


@dataclass
class RequestData:
    """
    An instance of Request represents completion of an external request
    to the application to do work and contains a summary
    of that request execution and the results.
    """

    # Identifier of a request call instance.
    # Used for correlation between request and other telemetry items.
    id: str

    # Request duration in format: DD.HH:MM:SS.MMMMMM.
    # Must be less than 1000 days.
    duration: timedelta

    # Result of a request execution. HTTP status code for HTTP requests.
    responseCode: str  # noqa: N815

    # Indication of successful or unsuccessful call.
    success: bool = True

    # Schema version
    ver: int = 2

    # Source of the request.
    # Examples are the instrumentation key of the caller
    # or the ip address of the caller.
    source: Optional[str] = None

    # Name of the request. Represents code path taken to process request.
    # Low cardinality value to allow better grouping of requests.
    # For HTTP requests it represents the HTTP method
    # and URL path template like 'GET /values/{id}'.
    name: Optional[str] = None

    # Request URL with all query string parameters.
    url: Optional[str] = None

    # Collection of custom properties.
    properties: Optional[Dict[str, str]] = None

    # Collection of custom measurements.
    measurements: Optional[Dict[str, float]] = None

    def to_envelope(self, tags: Optional[Dict[str, str]] = None) -> Envelope:
        return Envelope(
            name=Envelope.REQUEST_NAME,
            time=datetime.utcnow(),
            data=Data(self, Envelope.REQUEST_BASE_TYPE),
            tags=tags,
        )


@dataclass(frozen=True)
class Data:
    """Data container."""

    # Discriminated union of data item.
    baseData: Union[  # noqa: N815
        MessageData,
        ExceptionData,
        MetricData,
        EventData,
        RemoteDependencyData,
        RequestData,
    ]

    # ExceptionData|MessageData|EventData|MetricData|RemoteDependencyData|
    # RequestData
    baseType: str  # noqa: N815


class TagKey:
    """Common envelope tag keys."""

    # Application version.
    # Information in the application context fields is always
    # about the application that is sending the telemetry.
    APP_VER = "ai.application.ver"

    # Unique client device id. Computer name in most cases.
    DEVICE_ID = "ai.device.id"

    # Device locale using <language>-<REGION> pattern,
    # following RFC 5646. Example 'en-US'.
    DEVICE_LOCALE = "ai.device.locale"

    # Model of the device the end user of the application is using.
    # Used for client scenarios.
    # If this field is empty then it is derived from the user agent.
    DEVICE_MODEL = "ai.device.model"

    # Client device OEM name taken from the browser.
    DEVICE_OEM_NAME = "ai.device.oemName"

    # Operating system name and version of the device the end user
    # of the application is using.
    # If this field is empty then it is derived from the user agent.
    # Example 'Windows 10 Pro 10.0.10586.0'
    DEVICE_OS_VER = "ai.device.osVersion"

    # The type of the device the end user of the application is using.
    # Used primarily to distinguish JavaScript telemetry
    # from server side telemetry.
    # Examples: 'PC', 'Phone', 'Browser'. 'PC' is the default value.
    DEVICE_TYPE = "ai.device.type"

    # The IP address of the client device. IPv4 and IPv6 are supported.
    # Information in the location context fields is always about the end user.
    # When telemetry is sent from a service,
    # the location context is about the user that initiated the operation
    # in the service.
    LOCATION_IP = "ai.location.ip"

    # The country of the client device.
    # If any of Country, Province, or City is specified,
    # those values will be preferred over geolocation of the IP address field.
    # Information in the location context fields is always about the end user.
    # When telemetry is sent from a service,
    # the location context is about the user that initiated the operation
    # in the service.
    LOCATION_COUNTRY = "ai.location.country"

    # The province/state of the client device.
    # If any of Country, Province, or City is specified,
    # those values will be preferred over geolocation of the IP address field.
    # Information in the location context fields is always about the end user.
    # When telemetry is sent from a service, the location context
    # is about the user that initiated the operation in the service.
    LOCATION_PROVINCE = "ai.location.province"

    # The city of the client device.
    # If any of Country, Province, or City is specified,
    # those values will be preferred over geolocation of the IP address field.
    # Information in the location context fields is always about the end user.
    # When telemetry is sent from a service, the location context
    # is about the user that initiated the operation in the service.
    LOCATION_CITY = "ai.location.city"

    # A unique identifier for the operation instance.
    # The operation.id is created by either a request or a page view.
    # All other telemetry sets this to the value for the containing request
    # or page view.
    # Operation.id is used for finding all the telemetry items
    # for a specific operation instance.
    OPERATION_ID = "ai.operation.id"

    # The name (group) of the operation.
    # The operation.name is created by either a request or a page view.
    # All other telemetry items set this to the value
    # for the containing request or page view.
    # Operation.name is used for finding all the telemetry items
    # for a group of operations (i.e. 'GET Home/Index').
    OPERATION_NAME = "ai.operation.name"

    # The unique identifier of the telemetry item's immediate parent.
    OPERATION_PARENT_ID = "ai.operation.parentId"

    # Name of synthetic source.
    # Some telemetry from the application may represent synthetic traffic.
    # It may be web crawler indexing the website, site availability tests
    # or traces from diagnostic libraries like Application Insights SDK itself.
    OPERATION_SOURCE = "ai.operation.syntheticSource"

    # The correlation vector is a lightweight vector clock
    # which can be used to identify and order related events
    # across clients and services.
    OPERATION_CORRELATION_VECTOR = "ai.operation.correlationVector"

    # Session ID - the instance of the user's interaction with the app.
    # Information in the session context fields is always about the end user.
    # When telemetry is sent from a service,
    # the session context is about the user that initiated the operation
    # in the service.
    SESSION_ID = "ai.session.id"

    # Boolean value indicating whether the session identified
    # by ai.session.id is first for the user or not.
    SESSION_IS_FIRST = "ai.session.isFirst"

    # In multi-tenant applications this is the account ID or name
    # which the user is acting with.
    # Examples may be subscription ID for Azure portal
    # or blog name blogging platform.
    USER_ACCOUNT_ID = "ai.user.accountId"

    # Anonymous user id. Represents the end user of the application.
    # When telemetry is sent from a service, the user context is about the user
    # that initiated the operation in the service.
    USER_ID = "ai.user.id"

    # Authenticated user id. The opposite of ai.user.id,
    # this represents the user with a friendly name.
    # Since it's PII information it is not collected by default by most SDKs.
    USER_AUTH_ID = "ai.user.authUserId"

    # Name of the role the application is a part of.
    # Maps directly to the role name in azure.
    CLOUD_ROLE = "ai.cloud.role"

    # Name of the instance where the application is running.
    # Computer name for on-premises, instance name for Azure.
    CLOUD_ROLE_INSTANCE = "ai.cloud.roleInstance"

    # SDK version.
    # See https://github.com/Microsoft/ApplicationInsights-Home/blob/master
    # /SDK-AUTHORING.md#sdk-version-specification
    # for information.
    # SDK_VER = "ai.internal.sdkVersion"

    # Agent version. Used to indicate the version of StatusMonitor
    # installed on the computer if it is used for data collection.
    # AGENT_VER = "ai.internal.agentVersion"

    # This is the node name used for billing purposes.
    # Use it to override the standard detection of nodes.
    # NODE_NAME = "ai.internal.nodeName"


@dataclass
class Envelope:
    """System variables for a telemetry item."""

    METRIC_NAME = "Microsoft.ApplicationInsights.Metric"
    METRIC_BASE_TYPE = "MetricData"
    TRACE_NAME = "Microsoft.ApplicationInsights.Message"
    TRACE_BASE_TYPE = "MessageData"
    EVENT_NAME = "Microsoft.ApplicationInsights.Event"
    EVENT_BASE_TYPE = "EventData"
    EXCEPTION_NAME = "Microsoft.ApplicationInsights.Exception"
    EXCEPTION_BASE_TYPE = "ExceptionData"
    DEPENDENCY_NAME = "Microsoft.ApplicationInsights.RemoteDependency"
    DEPENDENCY_BASE_TYPE = "RemoteDependencyData"
    REQUEST_NAME = "Microsoft.ApplicationInsights.Request"
    REQUEST_BASE_TYPE = "RequestData"
    JSON_OPTIONS = orjson.OPT_NAIVE_UTC | orjson.OPT_UTC_Z

    # Type name of telemetry data item.
    # Microsoft.ApplicationInsights.(
    # Exception|Message|Event|Metric|RemoteDependency|Request)
    name: str

    # Event date time when telemetry item was created.
    # This is the wall clock time on the client when the event was generated.
    # There is no guarantee that the client's time is accurate.
    # This field must be formatted in UTC ISO 8601 format,
    # with a trailing 'Z' character,
    # as described publicly on https://en.wikipedia.org/wiki/ISO_8601#UTC.
    # Example: 2009-06-15T13:45:30.0000000Z.
    time: datetime

    # Telemetry data item.
    data: Data

    # The application's instrumentation key.
    # The key is typically represented as a GUID, but there are cases
    # when it is not a guid. No code should rely on iKey being a GUID.
    # Instrumentation key is case-insensitive.
    iKey: str = ""  # noqa: N815

    # Envelope version. For internal use only. By assigning this the default,
    # it will not be serialized within the payload
    # unless changed to a value other than #1.
    ver: int = 1

    # Sampling rate used in application.
    sampleRate: float = 100.0  # noqa: N815

    # Sequence field used to track absolute order of uploaded events.
    seq: Optional[str] = None

    # A collection of values bit-packed to represent
    # how the event was processed.
    # Currently, represents whether IP address needs to be stripped out
    # from event (set 0x200000) or should be preserved.
    flags: Optional[int] = None

    # Key/value collection of context properties.
    # See TagKey for information on available properties.
    tags: Optional[Dict[str, str]] = None

    def to_json(self) -> str:
        bts = serialize(self)
        return bts.decode("utf-8")


@dataclass(frozen=True)
class ApiResponseError:
    index: int
    statusCode: int  # noqa: N815
    message: str


@dataclass(frozen=True)
class ApiResponseBody:
    itemsReceived: int  # noqa: N815
    itemsAccepted: int  # noqa: N815
    errors: List[ApiResponseError]
