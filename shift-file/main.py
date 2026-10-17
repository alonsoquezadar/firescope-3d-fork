#!/usr/bin/env python3
"""Hayes Cartage shift file: three slips from one ride camera."""

from __future__ import annotations

import json
import os
import re
import threading
import urllib.error
import urllib.parse
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

PORT = int(os.environ.get("PORT", "8080"))
VSS_URL = os.environ.get("VSS_URL", "").rstrip("/")
VSS_USERNAME = os.environ.get("VSS_USERNAME", "")
VSS_PASSWORD = os.environ.get("VSS_PASSWORD", "")
WANDB_API_KEY = os.environ.get("WANDB_API_KEY", "")
WANDB_TEAM = os.environ.get("WANDB_TEAM", "")
WANDB_PROJECT = os.environ.get("WANDB_PROJECT", "")
WANDB_MODEL = os.environ.get(
    "WANDB_MODEL", "nvidia/NVIDIA-Nemotron-3.5-Lightning-30B-A3B"
)
CAMERA = "nyc_bike_gopro-1"

QUERIES = (
    "a car or truck tight against the cyclist in the green bike lane",
    "cyclist in a marked bike lane with moving traffic beside the rider",
)

KEEP_WORDS = (
    "bike lane",
    "close",
    "closely",
    "alongside",
    "passing",
    "passes",
    "door",
    "cut in",
    "cuts in",
    "swerv",
    "green paint",
    "green lane",
)
SHOW_COUNTS = (
    "bicycle",
    "car",
    "truck",
    "bus",
    "person",
    "motorcycle",
)
BANNED = (
    "near-miss",
    "near miss",
    "hazard",
    "scenario",
    "analysis",
    "leverage",
    "ensure",
    "safety",
    "coaching",
    "artificial",
    "as an ai",
    "model",
)
RANK = {"keep_as_evidence": 0, "coach_rider": 1, "discard": 2}
STAMP = {
    "keep_as_evidence": "File it",
    "coach_rider": "Have a word",
    "discard": "Leave it",
}

_token = None
_token_lock = threading.Lock()
