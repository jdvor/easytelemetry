#!/usr/bin/env python3

import glob
import os
import shutil

from utils import get_root_dir

root_dir = get_root_dir()
os.chdir(root_dir)

dist_dir = os.path.join(root_dir, "dist")
shutil.rmtree(dist_dir, ignore_errors=True)

build_dir = os.path.join(root_dir, "build")
shutil.rmtree(build_dir, ignore_errors=True)

docs_dir = os.path.join(root_dir, "docs")
shutil.rmtree(docs_dir, ignore_errors=True)

patterns = [
    "**/.eggs",
    "**/.mypy_cache",
    "**/__pycache__",
    "**/.pytest_cache",
    "**/*.egg-info",
]
for pattern in patterns:
    for path in glob.glob(pattern, recursive=True):
        shutil.rmtree(path, ignore_errors=True)
