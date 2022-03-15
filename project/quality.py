#!/usr/bin/env python3

import argparse
import subprocess
import sys
from typing import Sequence

from utils import get_pyproject_toml, get_src_dir

parser = argparse.ArgumentParser()
parser.add_argument(
    "-g",
    "--github",
    help="signals execution within Github Actions",
    action="store_true",
)
parser.add_argument(
    "-a",
    "--fail-asap",
    help="fail immediately when error occurs",
    action="store_true",
)
args = parser.parse_args()

output_fmt = "text" if args.github else "colorized"
src_dir = get_src_dir()
cfg_file = get_pyproject_toml()


def run(cmd: Sequence[str], label: str, fail_asap: bool) -> int:
    print(f"\n>>> {label}")
    print(" ".join(cmd))
    code = subprocess.call(cmd)
    if code > 0 and fail_asap:
        print(f"[ERROR] {label}: {code}")
        sys.exit(code)
    return code


flake8_code = run(["pflake8", "--statistics"], "flake8", args.fail_asap)

color = "--no-color-output" if args.github else "--pretty"
mypy_code = run(
    [
        "mypy",
        "--config-file",
        cfg_file,
        "--no-incremental",
        "--no-error-summary",
        color,
        src_dir,
    ],
    "mypy",
    args.fail_asap,
)

bandit_code = run(
    ["bandit", "-r", src_dir, "-c", cfg_file, "--quiet"],
    "bandit",
    args.fail_asap,
)

exit_code = max(flake8_code, mypy_code, bandit_code)
if exit_code != 0:
    print(
        f"\n[ERROR] flake8: {flake8_code}, "
        + f"mypy: {mypy_code}, bandit: {bandit_code}"
    )
    sys.exit(exit_code)
else:
    print("\n[SUCCESS]")
