#!/usr/bin/env python

import logging

from shared import ensure_env

from easytelemetry.appinsights import Options, build


ensure_env()


def with_named_logger() -> None:
    lgr = logging.getLogger("mylgr")
    lgr.info("message through standard logging 2")
    lgr.warning("warning through standard logging 2")


def with_exception() -> None:
    try:
        _ = 1 / 0
    except ZeroDivisionError:
        logging.exception("not a great idea to divide by 0")


def configure(opts: Options) -> None:
    opts.setup_std_logging = True
    opts.clear_std_logging_handlers = True


def main():
    with build("example", configure=configure):
        logging.info("message through standard logging 1")
        logging.warning("warning through standard logging 1")
        with_named_logger()
        with_exception()


if __name__ == "__main__":
    main()
