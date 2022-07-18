"""
This module contains types & functions dealing with publishing
collected telemetry data.
"""

from __future__ import annotations

import concurrent.futures as cf
import gzip
import logging
import os
import queue
import time
from dataclasses import dataclass
from typing import Dict, Generator, List, Optional, Protocol, Sequence, Union

import atomics
import requests

import easytelemetry.appinsights.protocol as p
from easytelemetry.appinsights.impl import Options

GZIP_COMPRESS_LEVEL = 6
GZIP_TRESHOLD_BYTES = 1000
MAX_ATTEMPTS = 3
DELAY_BETWEEN_ATTEMPTS_SECS = 0.5

# 0 represents network errors when HTTP status could not be determined
RETRYABLE_HTTP_STATUSES = [0, 500, 502]


@dataclass
class PublishResult:
    """Describes the result of batch publish attempt."""

    success: bool
    attempt: int = 0
    status_code: int = 200
    response_body: Union[p.ApiResponseBody, str, None] = None


class Publisher(Protocol):
    """
    Responsible for consuming queue and gracefully terminating when requested.
    """

    def consume(self, source: queue.Queue[p.Envelope]) -> None:
        pass

    def close(self) -> None:
        pass


class ErrorHandler(Protocol):
    """Deals with publishing errors."""

    def on_failure(
        self, batch: Sequence[p.Envelope], result: PublishResult,
    ) -> None:
        pass


class LoggingErrorHandler:
    """
    Logs publisher failure, but otherwise makes no attempts
    to re-publish failed batch/es.
    """

    def __init__(self, options: Options):
        self._options = options

    # noinspection PyMethodMayBeStatic
    def on_failure(
        self, batch: Sequence[p.Envelope], result: PublishResult,
    ) -> None:
        attempts = (
            "" if result.attempt < 1 else f" after {result.attempt} attempts"
        )
        msg = (
            f"Failed to publish {len(batch)} "
            + f"envelopes{attempts}; result: {result}"
        )
        logging.log(logging.ERROR, msg)


class DefaultPublisher:
    """
    Publishes envelopes from the source (queue) and thus consuming them.
    Envelopes are packed in batches and published to ingestion endpoint.
    It can work using internal ThreadPoolExecutor or one passed from outside
    as means of dispatching HTTP requests to ingestion endpoint.
    """

    def __init__(
        self,
        options: Options,
        executor: Optional[cf.ThreadPoolExecutor] = None,
        error_handler: Optional[ErrorHandler] = None,
    ):
        self._options = options
        if executor:
            self._executor = executor
            self._owns_executor = False
        else:
            workers = min(8, (os.cpu_count() or 1) + 1)
            self._executor = cf.ThreadPoolExecutor(max_workers=workers)
            self._owns_executor = True
        self._error_handler: ErrorHandler = (
            error_handler if error_handler else LoggingErrorHandler(options)
        )
        self._in_flight = atomics.atomic(4, atomics.INT)

    def consume(self, source: queue.Queue[p.Envelope]) -> None:
        batches = _to_batches(source, self._options.batch_maxsize)
        for batch in batches:
            self._executor.submit(self.publish_batch, batch)

    def publish_batch(self, batch: Sequence[p.Envelope]) -> None:
        try:
            self._in_flight.inc()
            result = send_batch(batch, self._options.ingestion_url)
            if not result.success:
                self._error_handler.on_failure(batch, result)
        finally:
            self._in_flight.dec()

    def close(self) -> None:
        if self._owns_executor:
            self._executor.shutdown(wait=True)


def _to_batches(
    source: queue.Queue[p.Envelope],
    maxsize: int,
) -> Generator[Sequence[p.Envelope], None, None]:
    """Consume the source (queue) and create batches to be published."""
    batch: List[p.Envelope] = []
    n = 0
    while True:
        try:
            envelope = source.get_nowait()
            batch.append(envelope)
            n += 1
            if n == maxsize:
                yield batch
                batch.clear()
                n = 0
        except queue.Empty:
            if n > 0:
                yield batch
            else:
                return


def send_batch(
    batch: Sequence[p.Envelope],
    ingestion_url: str,
    max_attempts: int = MAX_ATTEMPTS,
    delay_between_attempts_secs: float = DELAY_BETWEEN_ATTEMPTS_SECS,
    gzip_treshold: int = GZIP_TRESHOLD_BYTES,
) -> PublishResult:
    """
    Serialize and send the batch to ingestion endpoint.

    :param batch: sequence of envelopes to publish
    :param ingestion_url: endpoint URL for publishing
    :param max_attempts: maximum number of publish attempts.
        Use 0 to turn retries off.
    :param delay_between_attempts_secs: wait between publish attempts
        this number of seconds. Use 0 to turn retries off.
    :param gzip_treshold: if serialized payload is larger than this treshold,
        than it will be gziped. Use -1 for no compression regardless
        of the payload size. The value represents number of bytes.
    :return: object describing publish result
    """
    body = p.serialize(batch)
    if 0 < gzip_treshold < len(body):
        body = gzip.compress(body, compresslevel=GZIP_COMPRESS_LEVEL)
        headers = {
            "Content-Encoding": "gzip",
            "Content-Type": "application/json",
            "User-Agent": "easytelemetry/2.0.2 (Windows)",
        }
    else:
        headers = {
            "Content-Type": "application/json",
            "User-Agent": "easytelemetry/2.0.2 (Windows)",
        }

    retry_allowed = max_attempts > 1 and delay_between_attempts_secs > 0
    if retry_allowed:
        attempt = 1
        while max_attempts >= attempt:
            result = _raw_send(ingestion_url, body, headers)
            is_last = max_attempts - 1 == attempt
            if _can_retry(result) or is_last:
                result.attempt = attempt
                return result
            attempt += 1
            time.sleep(delay_between_attempts_secs)
    else:
        return _raw_send(ingestion_url, body, headers)


def _raw_send(url: str, body: bytes, headers: Dict[str, str]) -> PublishResult:
    resp = requests.post(url, headers=headers, data=body)
    if resp.status_code == 200:
        return PublishResult(success=True)
    else:
        resp_body = p.deserialize(resp.content)
        return PublishResult(
            success=False,
            status_code=resp.status_code,
            response_body=resp_body,
        )


def _can_retry(result: PublishResult) -> bool:
    return (
        not result.success
    ) and result.status_code in RETRYABLE_HTTP_STATUSES
