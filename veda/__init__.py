import pkg_resources
import sys

from veda.chains import (  # noqa: F401
    Chain,
    MainnetChain,
)

#
#  Ensure we can reach 1024 frames of recursion
#
EVM_RECURSION_LIMIT = 1024 * 12
sys.setrecursionlimit(max(EVM_RECURSION_LIMIT, sys.getrecursionlimit()))


__version__ = '0.1.0'
