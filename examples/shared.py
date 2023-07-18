from datetime import datetime
import os.path

from dotenv import load_dotenv

from easytelemetry.appinsights import Options


def ensure_env() -> None:
    csname = Options.CONNECTION_STRING_ENV_VAR
    if os.environ.get(csname):
        return
    wd = os.path.dirname(os.path.abspath(__file__))
    loc1 = os.path.join(wd, ".env")
    loc2 = os.path.normpath(os.path.join(wd, "../.env"))
    for loc in [loc1, loc2]:
        if os.path.isfile(loc):
            load_dotenv(dotenv_path=loc)
    if not os.environ.get(csname):
        err = f"environment variable '{csname}' not set"
        raise EnvironmentError(err)


def stdout(msg: str) -> None:
    t = datetime.now().strftime("%T")
    print(f"[{t}] {msg}")
