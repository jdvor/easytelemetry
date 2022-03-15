"""Utilities for other project scripts."""

import functools
import os
import subprocess


@functools.lru_cache(maxsize=1)
def get_root_dir() -> str:
    root = os.path.abspath(os.path.dirname(__file__))
    return os.path.normpath(os.path.join(root, "../"))


def get_src_dir() -> str:
    return os.path.join(get_root_dir(), "src")


def get_tests_dir() -> str:
    return os.path.join(get_root_dir(), "tests")


def get_unit_tests_dir() -> str:
    return os.path.join(get_root_dir(), "tests", "unit")


def get_integration_tests_dir() -> str:
    return os.path.join(get_root_dir(), "tests", "integration")


def get_examples_dir() -> str:
    return os.path.join(get_root_dir(), "examples")


def get_benchmarks_dir() -> str:
    return os.path.join(get_root_dir(), "benchmarks")


def get_dist_dir() -> str:
    return os.path.join(get_root_dir(), "dist")


def get_pyproject_toml() -> str:
    return os.path.join(get_root_dir(), "pyproject.toml")


def get_git_commit() -> str:
    process = subprocess.run(
        ["git", "rev-parse", "HEAD"],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        universal_newlines=True,
    )
    return process.stdout.strip()


def get_git_branch() -> str:
    process = subprocess.run(
        ["git", "rev-parse", "--abbrev-ref", "HEAD"],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        universal_newlines=True,
    )
    return process.stdout.strip()
