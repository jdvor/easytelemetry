#!/usr/bin/env python3

import subprocess

from utils import get_pyproject_toml

cfg_file = get_pyproject_toml()

print(">>> isort")
subprocess.call(["isort", ".", "--settings-file", cfg_file])

print(">>> black")
subprocess.call(["black", ".", "--config", cfg_file])
