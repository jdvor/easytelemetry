#!/usr/bin/env python3

import argparse
import glob
import os
import re
from subprocess import call

from utils import get_dist_dir, get_git_branch, get_git_commit, get_src_dir


def patch_init_file(file_path: str, new_version: str, new_commit: str):
    rgx_version = r"__version__ = '\S*'"
    rgx_commit = r"__commit__ = '\S*'"
    version_line = f"__version__ = '{new_version}'"
    commit_line = f"__commit__ = '{new_commit}'"
    with open(file_path, "r") as f:
        new_content = f.read()
        has_version = re.search(r"__version__ = '\S*'", new_content) is not None
        has_commit = re.search(r"__commit__ = '\S*'", new_content) is not None
        if has_version:
            new_content = re.sub(
                rgx_version,
                version_line,
                new_content,
                flags=re.M,
            )
        else:
            new_content = f"{new_content}\n\n{version_line}\n"
        if has_commit:
            new_content = re.sub(
                rgx_commit,
                commit_line,
                new_content,
                flags=re.M,
            )
        else:
            new_content = f"{new_content}\n\n{commit_line}\n"
    with open(file_path, "w") as f:
        f.write(new_content)


def semantic_version(ver: str, branch: str) -> str:
    ver = ver if ver and re.match(r"^\d+(\.\d+){2,3}$", ver) else "1.0.0"
    if branch and re.match(r"^[a-z][a-z0-9_\-]+$", branch, re.I):
        if branch == "master" or branch == "main":
            branch = None
        else:
            branch = branch if len(branch) <= 30 else branch[:29]
            branch = branch.lower().replace("-", "_")
    else:
        branch = None
    return ver if not branch else f"{ver}-{branch}"


parser = argparse.ArgumentParser()
parser.add_argument("version", help="semantic version")
args = parser.parse_args()


branch_name = get_git_branch()
version = semantic_version(args.version, branch_name)
commit = get_git_commit()

for init_path in glob.glob(args.pkg_dir + "/**/__init__.py", recursive=True):
    patch_init_file(init_path, version, commit)

print(">>> build sdist")
print(f"semver: {version}")
print(f"commit: {commit}")
print(f"branch: {branch_name}")
src_dir = get_src_dir()
dist_dir = get_dist_dir()
os.chdir(src_dir)
call(["python", "setup.py", "sdist", "-d", dist_dir])
