from logging import *  # noqa: F403

import logging as _logging


def set_verbosity(_level):
    return None


def set_stderrthreshold(_level):
    return None


def fatal(msg, *args, **kwargs):
    _logging.getLogger().fatal(msg, *args, **kwargs)
    raise SystemExit(1)
