import os
import sys
from datetime import datetime


def wire_up_src_dir() -> None:
    root = os.path.abspath(os.path.dirname(__file__))
    src = os.path.normpath(os.path.join(root, "../src"))
    if os.path.isdir(src) and src not in sys.path:
        sys.path.append(src)


def stdout(msg: str) -> None:
    t = datetime.now().strftime("%T")
    print(f"[{t}] {msg}")
