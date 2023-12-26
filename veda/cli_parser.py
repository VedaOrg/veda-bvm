import argparse
import json
import logging
from pathlib import Path
from typing import (
    Any,
)

from eth_utils import (
    DEBUG2_LEVEL_NUM,
    ValidationError,
)

from veda.constants import (
    VEDA_NETWORK_ID,
)

from veda import __version__


LOG_LEVEL_CHOICES = {
    # numeric versions
    '8': DEBUG2_LEVEL_NUM,
    '10': logging.DEBUG,
    '20': logging.INFO,
    '30': logging.WARNING,
    '40': logging.ERROR,
    '50': logging.CRITICAL,
    # string versions
    'DEBUG2': DEBUG2_LEVEL_NUM,
    'DEBUG': logging.DEBUG,
    'INFO': logging.INFO,
    'WARN': logging.WARNING,
    'WARNING': logging.WARNING,
    'ERROR': logging.ERROR,
    'CRITICAL': logging.CRITICAL,
}


def log_level_formatted_string() -> str:
    numeric_levels = [k for k in LOG_LEVEL_CHOICES.keys() if k.isdigit()]
    literal_levels = [k for k in LOG_LEVEL_CHOICES.keys() if not k.isdigit()]

    return (
        "LEVEL must be one of: "
        f"\n  {'/'.join(numeric_levels)} (numeric); "
        f"\n  {'/'.join(literal_levels).lower()} (lowercase); "
        f"\n  {'/'.join(literal_levels).upper()} (uppercase)."
    )


class ValidateAndStoreLogLevel(argparse.Action):
    def __call__(self,
                 parser: argparse.ArgumentParser,
                 namespace: argparse.Namespace,
                 value: Any,
                 option_string: str = None) -> None:
        if value is None:
            return

        raw_value = value.upper()

        # this is a global log level.
        if raw_value in LOG_LEVEL_CHOICES:
            path = None
            log_level = LOG_LEVEL_CHOICES[raw_value]
        else:
            path, _, raw_log_level = value.partition('=')

            if not path or not raw_log_level:
                raise argparse.ArgumentError(
                    self,
                    f"Invalid logging config: '{value}'.  Log level may be specified "
                    "as a global logging level using the syntax `--log-level "
                    "<LEVEL>`; or, to specify the logging level for an "
                    "individual logger, '--log-level "
                    "<LOGGER-NAME>=<LEVEL>'" + '\n' +
                    log_level_formatted_string()
                )

            try:
                log_level = LOG_LEVEL_CHOICES[raw_log_level.upper()]
            except KeyError:
                raise argparse.ArgumentError(self, (
                    f"Invalid logging level.  Got '{raw_log_level}'.",
                    log_level_formatted_string())
                )

        if getattr(namespace, self.dest) is None:
            setattr(namespace, self.dest, {})
        log_levels = getattr(namespace, self.dest)
        if path in log_levels:
            if path is None:
                raise argparse.ArgumentError(
                    self,
                    f"Global logging has already been configured to '{log_level}'.  The "
                    "global logging level may only be specified once."
                )
            else:
                raise argparse.ArgumentError(
                    self,
                    f"The logging level for '{path}' was provided more than once. "
                    "Please ensure the each name is provided only once"
                )
        log_levels[path] = log_level


parser = argparse.ArgumentParser(description='Veda')

#
# subparser for sub commands
#
# Components may add subcommands with a `func` attribute
# to gain control over the main Veda process
subparser = parser.add_subparsers(dest='subcommand')

#
# Argument Groups
#
veda_parser = parser.add_argument_group('core')
logging_parser = parser.add_argument_group('logging')
network_parser = parser.add_argument_group('network')
chain_parser = parser.add_argument_group('chain')
debug_parser = parser.add_argument_group('debug')


#
# Veda Globals
#
veda_parser.add_argument('--version', action='version', version=__version__)
veda_parser.add_argument(
    '--veda-root-dir',
    help=(
        "The filesystem path to the base directory that veda will store it's "
        "information.  Default: $XDG_DATA_HOME/.local/share/veda"
    ),
)
veda_parser.add_argument(
    '--port',
    type=int,
    required=False,
    default=30303,
    help=(
        "Port on which veda should listen for incoming p2p/discovery connections. Default: 30303"
    ),
)
veda_parser.add_argument(
    '--veda-tmp-root-dir',
    action="store_true",
    required=False,
    default=False,
    help=(
        "If this flag is set, veda will launch with a temporary root"
        " directory as provided by the ``tempfile`` library."
    ),
)


#
# Logging configuration
#
logging_parser.add_argument(
    '-l',
    '--log-level',
    action=ValidateAndStoreLogLevel,
    dest="log_levels",
    metavar="LEVEL",
    help=(
        "Configure the logging level. " + log_level_formatted_string()
    ),
)
logging_parser.add_argument(
    '--stderr-log-level',
    dest="stderr_log_level",
    help=(
        "Configure the logging level for the stderr logging."
    ),
)
logging_parser.add_argument(
    '--file-log-level',
    dest="file_log_level",
    help=(
        "Configure the logging level for file-based logging."
    ),
)

#
# Chain configuration
#

chain_parser.add_argument(
    '--data-dir',
    help=(
        "The directory where chain data is stored"
    ),
)

#
# Debug configuration
#
debug_parser.add_argument(
    '--profile',
    action='store_true',
    help=(
        "Enables profiling via cProfile."
    ),
)
