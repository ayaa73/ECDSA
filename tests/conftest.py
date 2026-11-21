"""Shared pytest setup: run Qt without a display so GUI tests work everywhere."""
import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")  # must be set before Qt starts
