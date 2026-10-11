"""Shared setup for the tests."""
import math

from so.config import load

CFG = load()
# how far the winch lowers the sled per motor step
MMPS = math.pi * CFG["rig"]["spool_mm"] / CFG["rig"]["steps_per_rev"]
