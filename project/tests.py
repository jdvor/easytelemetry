#!/usr/bin/env python3

import argparse
import sys

import pytest
from utils import get_src_dir, get_tests_dir, get_unit_tests_dir

FAIL_UNDER_COVERAGE = 60

parser = argparse.ArgumentParser()
parser.add_argument(
    "--github",
    help="execute within Github Actions",
    action="store_true",
)
parser.add_argument(
    "--integration",
    help="include integration tests",
    action="store_true",
)
args = parser.parse_args()

src_dir = get_src_dir()
if src_dir not in sys.path:
    sys.path.append(src_dir)

tests_dir = get_tests_dir() if args.integration else get_unit_tests_dir()
cmd_args = [
    "--rootdir=" + tests_dir,
    "--disable-warnings",
    "--no-header",
    "--cov=" + src_dir,
    "--no-cov-on-fail",
]

if args.github:
    cmd_args.append([f"--cov-fail-under={FAIL_UNDER_COVERAGE}", "--color=no"])
else:
    cmd_args.append(["--color=yes", "--verbose"])

result = pytest.main(cmd_args)
sys.exit(result)
