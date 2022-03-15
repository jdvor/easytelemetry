#!/usr/bin/env python3

import argparse
import os
import sys

import twine.commands.upload as twine
from twine.settings import Settings
from utils import get_root_dir

parser = argparse.ArgumentParser()
parser.add_argument(
    "-t",
    "--test",
    nargs="?",
    default=False,
    action="store_true",
    help="Use test version of pypi.",
)
parser.add_argument(
    "-a",
    "--access_token",
    nargs="?",
    default=None,
    help="PyPI API access token; if not provided it will fallback to "
    + 'environment variable "PYPI_EASYTELEMETRY_ACCESS_TOKEN".',
)
args = parser.parse_args()

if args.test:
    url = "https://test.pypi.org/legacy/"
    access_token = (
        args.access_token
        if args.access_token
        else os.environ.get("PYPI_TEST_ACCESS_TOKEN")
    )
else:
    url = "https://upload.pypi.org/legacy/"
    access_token = (
        args.access_token
        if args.access_token
        else os.environ.get("PYPI_EASYTELEMETRY_ACCESS_TOKEN")
    )

if not access_token:
    sys.exit("ERROR: no access token provided.")

builds_path = os.path.join(get_root_dir(), "dist/*")
settings = Settings(
    repository_url=url,
    username="__token__",
    password=access_token,
    skip_existing=True,
    non_interactive=True,
)
twine.upload(settings, [builds_path])
