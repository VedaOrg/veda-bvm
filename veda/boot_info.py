from argparse import Namespace
from typing import Dict, NamedTuple

from veda.config import VedaConfig


class BootInfo(NamedTuple):
    args: Namespace
    veda_config: VedaConfig
    profile: bool
    min_log_level: int
    logger_levels: Dict[str, int]
