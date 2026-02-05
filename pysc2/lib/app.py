import sys

from pysc2.lib import flags
from pysc2.lib import logging


class UsageError(Exception):
    pass


def run(main, argv=None):
    if argv is None:
        argv = sys.argv
    if not logging.getLogger().handlers:
        logging.basicConfig(level=logging.INFO)
    remaining = flags.FLAGS.parse(argv)
    return main(remaining)
