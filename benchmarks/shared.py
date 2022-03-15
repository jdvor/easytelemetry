import atomics
import cProfile
import os
import pstats
import random
import sys
import uuid
from datetime import timedelta
from functools import partial, wraps
from pstats import SortKey
from typing import Optional

_seq = atomics.atomic(8, atomics.INT)


def wire_up_src_dir() -> None:
    root = os.path.abspath(os.path.dirname(__file__))
    src = os.path.normpath(os.path.join(root, '../src'))
    if os.path.isdir(src) and src not in sys.path:
        sys.path.append(src)


wire_up_src_dir()


import easytelemetry.appinsights.protocol as p


def _cpu_profile(
    fn,
    sort_by: SortKey = SortKey.CUMULATIVE,
    filepath: Optional[str] = None,
):
    """
    Decorate a function to print CPU time costs
    to either stdout or a file.
    """
    filename = f'.prof/{fn.__name__}' if filepath == 'auto' else filepath

    @wraps
    def inner(*args, **kwargs):
        profiler = cProfile.Profile()
        profiler.enable()
        result = fn(*args, **kwargs)
        profiler.disable()
        ps = pstats.Stats(profiler)
        ps.sort_stats(sort_by)
        if filename:
            ps.dump_stats(filename)
        else:
            ps.print_stats()
        return result

    return inner


print_cpu = partial(_cpu_profile)
save_cpu = partial(_cpu_profile, filepath='auto')


def sample_envelope() -> p.Envelope:
    ms = random.randint(800, 3500)
    user_id = random.randint(100, 110)
    alpha = str(random.randint(1, 5))
    envelope = p.RemoteDependencyData(
        name='user_posts',
        duration=timedelta(milliseconds=ms),
        success=True,
        id=f'posts/user/{user_id}',
        data=r'SELECT * FROM posts WHERE user = @user_id',
        target='datalake1.example.com',
        type='SQL',
        properties={'alpha': alpha},
    ).to_envelope()
    envelope.iKey = '0d96cb1c-38d2-41ed-9ffd-801c0862049c'
    envelope.seq = str(_seq.fetch_inc())
    envelope.tags = {
        p.TagKey.OPERATION_ID: str(uuid.uuid4()),
        p.TagKey.OPERATION_PARENT_ID: str(uuid.uuid4()),
        p.TagKey.CLOUD_ROLE_INSTANCE: 'LIEN-02',
        p.TagKey.LOCATION_IP: '94.230.174.81',
    }
    return envelope
