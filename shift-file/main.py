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

PAGE = r"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Hayes Cartage · shift file</title>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=Archivo+Narrow:wght@500;700&family=Libre+Baskerville:ital,wght@0,400;0,700;1,400&display=swap" rel="stylesheet">
<style>
  :root {
    --ink: #1c1712;
    --paper: #f3ecdf;
    --rule: #1c1712;
    --mute: #5e564c;
    --red: #8e1e1e;
    --amber: #8a5a12;
    --wall: #b9b3a6;
  }
  * { box-sizing: border-box; }
  html, body { margin: 0; }
  body {
    min-height: 100vh;
    color: var(--ink);
    background-color: var(--wall);
    background-image:
      linear-gradient(rgba(28,23,18,.05) 1px, transparent 1px),
      linear-gradient(90deg, rgba(28,23,18,.05) 1px, transparent 1px);
    background-size: 28px 28px;
    font-family: "Libre Baskerville", Georgia, serif;
  }
  .sheet {
    width: min(880px, calc(100% - 28px));
    margin: 22px auto 40px;
    background: var(--paper);
    border: 1px solid var(--rule);
    border-left: 11px solid var(--red);
    box-shadow: 7px 7px 0 var(--rule);
    padding: 26px 32px 36px 28px;
  }
  header {
    display: grid;
    grid-template-columns: 1fr auto;
    gap: 12px 24px;
    align-items: end;
    border-bottom: 1px solid var(--rule);
    padding-bottom: 14px;
  }
  .mark {
    font-family: "Archivo Narrow", "Arial Narrow", Impact, sans-serif;
    font-weight: 700;
    letter-spacing: .14em;
    text-transform: uppercase;
    font-size: 28px;
    line-height: 1;
    margin: 0;
  }
  .desk {
    margin: 6px 0 0;
    font-family: "Archivo Narrow", "Arial Narrow", sans-serif;
    letter-spacing: .16em;
    text-transform: uppercase;
    font-size: 13px;
  }
  .file-no {
    text-align: right;
    font-family: "Archivo Narrow", "Arial Narrow", sans-serif;
    letter-spacing: .08em;
    text-transform: uppercase;
    font-size: 13px;
    line-height: 1.45;
  }
  .lede {
    max-width: 62ch;
    font-size: 17px;
    line-height: 1.45;
    margin: 18px 0 8px;
  }
  .lede em { font-style: italic; }
  .legend {
    display: flex;
    flex-wrap: wrap;
    gap: 8px 18px;
    margin: 0 0 18px;
    padding: 0;
    list-style: none;
    font-family: "Archivo Narrow", "Arial Narrow", sans-serif;
    letter-spacing: .04em;
    text-transform: uppercase;
    font-size: 13px;
  }
  .legend li { display: flex; gap: 8px; align-items: baseline; }
  .swatch {
    width: 9px;
    height: 9px;
    border: 1px solid var(--rule);
    display: inline-block;
    transform: translateY(1px);
  }
  .swatch.file { background: var(--red); }
  .swatch.word { background: var(--amber); }
  .swatch.leave { background: transparent; }
  .row {
    display: flex;
    justify-content: space-between;
    gap: 16px;
    align-items: center;
    border-top: 1px solid var(--rule);
    padding-top: 14px;
  }
  button {
    appearance: none;
    border: 1px solid var(--rule);
    background: var(--ink);
    color: var(--paper);
    font-family: "Archivo Narrow", "Arial Narrow", sans-serif;
    font-weight: 700;
    letter-spacing: .12em;
    text-transform: uppercase;
    font-size: 15px;
    padding: 10px 16px;
    cursor: pointer;
  }
  button:disabled { cursor: wait; background: #3a342c; }
  .status {
    font-family: "Archivo Narrow", "Arial Narrow", sans-serif;
    letter-spacing: .08em;
    text-transform: uppercase;
    font-size: 13px;
    color: var(--mute);
    min-height: 1.2em;
  }
  .ink {
    display: inline-block;
    width: 72px;
    height: 2px;
    background: var(--ink);
    vertical-align: middle;
    margin-left: 8px;
    transform-origin: left center;
    animation: tick 1.1s steps(3, end) infinite;
  }
  @keyframes tick {
    0% { transform: scaleX(.25); }
    100% { transform: scaleX(1); }
  }
  .slip {
    margin-top: 18px;
    padding-top: 14px;
    border-top: 1px solid var(--rule);
    display: grid;
    grid-template-columns: 340px 1fr;
    gap: 16px 22px;
  }
  .slip video {
    width: 100%;
    aspect-ratio: 16/10;
    object-fit: contain;
    background: #14110e;
    border: 1px solid var(--rule);
    display: block;
  }
  .stamp {
    display: inline-block;
    font-family: "Archivo Narrow", "Arial Narrow", sans-serif;
    font-weight: 700;
    letter-spacing: .14em;
    text-transform: uppercase;
    font-size: 18px;
    border: 2px solid var(--rule);
    padding: 2px 8px 1px;
    transform: rotate(-2deg);
    margin-bottom: 8px;
  }
  .stamp.file { color: var(--red); border-color: var(--red); }
  .stamp.word { color: var(--amber); border-color: var(--amber); }
  .stamp.leave { color: var(--ink); }
  .when {
    font-family: "Archivo Narrow", "Arial Narrow", sans-serif;
    letter-spacing: .06em;
    text-transform: uppercase;
    font-size: 13px;
    color: var(--mute);
    margin: 0 0 8px;
  }
  .reason { margin: 0 0 8px; font-size: 16.5px; line-height: 1.4; }
  .caption {
    margin: 0;
    color: #3c362f;
    font-size: 14px;
    line-height: 1.45;
  }
  .meta {
    margin: 10px 0 0;
    font-family: "Archivo Narrow", "Arial Narrow", sans-serif;
    font-size: 13px;
    letter-spacing: .03em;
    text-transform: uppercase;
    color: var(--mute);
  }
  .foot {
    margin: 22px 0 0;
    border-top: 1px solid var(--rule);
    padding-top: 10px;
    font-size: 12px;
    color: var(--mute);
  }
  @media (max-width: 720px) {
    .sheet { padding: 18px 16px 28px 14px; }
    header, .slip, .row { grid-template-columns: 1fr; display: grid; }
    .file-no, .status { text-align: left; }
    .mark { font-size: 24px; }
  }
</style>
</head>
<body>
  <article class="sheet">
    <header>
      <div>
        <p class="mark">Hayes Cartage</p>
        <p class="desk">Depot file · rider camera</p>
      </div>
      <p class="file-no">File HC-17<br>17 October<br>Bike cam, New York reel</p>
    </header>
    <p class="lede">Alex, the ride is in. Open the reel and the desk gives you three slips. <em>File it</em> if a vehicle is in the lane with the rider. <em>Have a word</em> if the rider moved out on their own. <em>Leave it</em> if a car is simply next door.</p>
    <ul class="legend">
      <li><i class="swatch file"></i> File it</li>
      <li><i class="swatch word"></i> Have a word</li>
      <li><i class="swatch leave"></i> Leave it</li>
    </ul>
    <div class="row">
      <button id="open" type="button">Open the ride</button>
      <p class="status" id="status"></p>
    </div>
    <div id="slips"></div>
    <p class="foot">One camera. No search box. The note uses the clip text and the object counts already on the reel. It does not measure metres.</p>
  </article>
<script>
const button = document.getElementById("open");
const status = document.getElementById("status");
const slips = document.getElementById("slips");

function prefix() {
  const path = location.pathname;
  const cut = path.indexOf("/app");
  if (cut >= 0) return path.slice(0, cut + 4).replace(/\/$/, "");
  return "";
}

function stampClass(verdict) {
  if (verdict === "keep_as_evidence") return "file";
  if (verdict === "coach_rider") return "word";
  return "leave";
}

button.addEventListener("click", async () => {
  button.disabled = true;
  slips.innerHTML = "";
  status.innerHTML = 'Reading the reel <span class="ink"></span>';
  try {
    const res = await fetch(prefix() + "/api/review", { method: "POST" });
    const data = await res.json();
    if (!res.ok || data.error) {
      status.textContent = data.error || "The camera did not answer.";
      button.disabled = false;
      return;
    }
    const items = data.slips || [];
    if (!items.length) {
      status.textContent = "Nothing on this reel worth a slip.";
      button.disabled = false;
      return;
    }
    status.textContent = items.length + (items.length === 1 ? " slip" : " slips");
    for (const slip of items) {
      const article = document.createElement("section");
      article.className = "slip";
      const video = document.createElement("video");
      video.controls = true;
      video.playsInline = true;
      video.preload = "metadata";
      video.src = prefix() + "/clip?source=" + encodeURIComponent(slip.source);
      const body = document.createElement("div");
      const stamp = document.createElement("div");
      stamp.className = "stamp " + stampClass(slip.verdict);
      stamp.textContent = slip.stamp;
      const when = document.createElement("p");
      when.className = "when";
      when.textContent = slip.when + "  ·  " + slip.reel;
      const reason = document.createElement("p");
      reason.className = "reason";
      reason.textContent = slip.reason;
      const caption = document.createElement("p");
      caption.className = "caption";
      caption.textContent = slip.caption;
      const meta = document.createElement("p");
      meta.className = "meta";
      meta.textContent = slip.counts;
      if (slip.uncertain) meta.textContent += "  ·  " + slip.uncertain;
      body.append(stamp, when, reason, caption, meta);
      article.append(video, body);
      slips.append(article);
    }
  } catch (err) {
    status.textContent = "The camera did not answer.";
  }
  button.disabled = false;
});
</script>
</body>
</html>
"""


def _request(method, url, payload=None, headers=None, timeout=90):
    data = None if payload is None else json.dumps(payload).encode()
    req = urllib.request.Request(url, data=data, headers=headers or {}, method=method)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as res:
            raw = res.read()
            return res.status, dict(res.headers), raw
    except urllib.error.HTTPError as err:
        body = err.read()
        return err.code, dict(err.headers), body


def login(force=False):
    global _token
    with _token_lock:
        if _token and not force:
            return _token
        if not (VSS_URL and VSS_USERNAME and VSS_PASSWORD):
            raise RuntimeError("missing desk credentials")
        status, _, raw = _request(
            "POST",
            VSS_URL + "/api/v1/auth/login",
            {"username": VSS_USERNAME, "password": VSS_PASSWORD},
            {"Content-Type": "application/json"},
            timeout=30,
        )
        if status != 200:
            raise RuntimeError("desk login failed")
        _token = json.loads(raw)["access_token"]
        return _token


def vss_json(method, path, payload=None, timeout=90):
    token = login()
    headers = {"Authorization": f"Bearer {token}"}
    if payload is not None:
        headers["Content-Type"] = "application/json"
    status, _, raw = _request(method, VSS_URL + path, payload, headers, timeout)
    if status == 401:
        token = login(force=True)
        headers["Authorization"] = f"Bearer {token}"
        status, _, raw = _request(method, VSS_URL + path, payload, headers, timeout)
    if status >= 400:
        raise RuntimeError(f"archive {status}")
    return json.loads(raw)


def search(query):
    data = vss_json(
        "POST",
        "/api/v1/search",
        {
            "query": query,
            "top_k": 6,
            "min_similarity": 0.2,
            "metadata_filters": {"camera_id": CAMERA},
            "include_public": True,
        },
    )
    return data.get("results") or []


def counts_of(hit):
    raw = hit.get("object_counts") or {}
    if isinstance(raw, str):
        try:
            raw = json.loads(raw)
        except json.JSONDecodeError:
            raw = {}
    if not isinstance(raw, dict):
        return {}
    return {str(k): int(v) for k, v in raw.items() if isinstance(v, (int, float))}


def count_line(counts):
    labels = {
        "person": ("person", "people"),
        "bicycle": ("bicycle", "bicycles"),
        "bus": ("bus", "buses"),
        "car": ("car", "cars"),
        "truck": ("truck", "trucks"),
        "motorcycle": ("motorcycle", "motorcycles"),
    }
    parts = []
    for key in SHOW_COUNTS:
        n = counts.get(key) or 0
        if not n:
            continue
        one, many = labels[key]
        parts.append(f"{n} {one if n == 1 else many}")
    return " · ".join(parts) if parts else "No object count"


def clock(seconds):
    try:
        total = int(float(seconds))
    except (TypeError, ValueError):
        return "—"
    return f"{total // 60}:{total % 60:02d}"


def excerpt(text):
    text = " ".join((text or "").split())
    if len(text) <= 320:
        return text
    cut = text[:320]
    stop = cut.rfind(". ")
    if stop > 140:
        return cut[: stop + 1]
    return cut.rstrip() + "…"


def interest(hit):
    text = (hit.get("reasoning_content") or "").lower()
    score = float(hit.get("similarity_score") or 0)
    for word in KEEP_WORDS:
        if word in text:
            score += 0.05
    return score


def plain_sentence(caption):
    text = " ".join((caption or "").split())
    sentence = text.split(". ")[0].strip().rstrip(".")
    if len(sentence) > 200:
        sentence = sentence[:197].rstrip() + "…"
    if not sentence:
        return "The clip notes do not say a vehicle entered the lane."
    if not sentence.endswith("."):
        sentence += "."
    return sentence


def clean_reason(reason, caption):
    reason = " ".join((reason or "").split())
    low = reason.lower()
    meta = ("caption", "does not", "doesn't", "do not", "not describe", "not show", "no vehicle")
    if (
        not reason
        or any(word in low for word in BANNED)
        or any(word in low for word in meta)
        or len(reason) > 220
    ):
        return plain_sentence(caption)
    return reason


def clean_uncertain(text):
    text = " ".join((text or "").split())
    low = text.lower()
    if low in {"", "low", "medium", "high", "none", "n/a"} or "caption" in low:
        return "Notes don't give a gap in metres"
    if len(text) > 140:
        text = text[:137].rstrip() + "…"
    return text[0].upper() + text[1:] if text else text


def verdict_for(hit):
    caption = hit.get("reasoning_content") or ""
    counts = counts_of(hit)
    fallback = {
        "verdict": "discard",
        "reason": plain_sentence(caption),
        "uncertain": "The desk note was not written",
    }
    if not WANDB_API_KEY:
        return fallback
    system = (
        "You file footage at Hayes Cartage, a London cargo-bike depot. "
        "Use only the caption and the counts. Do not invent distances or lane positions. "
        "keep_as_evidence only if the text says a vehicle is in the bike lane, "
        "tight against the rider, opening a door, or cutting in. "
        "coach_rider if the rider is in the vehicle lane or the middle of the road, "
        "or left the lane, with no vehicle forcing it. "
        "Otherwise discard. "
        "reason: one spoken sentence a dispatcher would say, using the scene itself. "
        "Do not mention captions, notes, or what is missing. "
        "uncertain: a short clause a person would write in the margin, with no word 'caption'. "
        'Reply with JSON only: {"verdict":"keep_as_evidence|coach_rider|discard","reason":"...","uncertain":"..."}'
    )
    user = (
        f"Caption:\n{caption[:1200]}\n\n"
        f"Counts: {json.dumps(counts)}\n"
        f"From {clock(hit.get('segment_start_sec'))} to {clock(hit.get('segment_end_sec'))}."
    )
    headers = {
        "Authorization": f"Bearer {WANDB_API_KEY}",
        "Content-Type": "application/json",
    }
    if WANDB_TEAM and WANDB_PROJECT:
        headers["OpenAI-Project"] = f"{WANDB_TEAM}/{WANDB_PROJECT}"
    status, _, raw = _request(
        "POST",
        "https://api.inference.wandb.ai/v1/chat/completions",
        {
            "model": WANDB_MODEL,
            "temperature": 0.1,
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
        },
        headers,
        timeout=50,
    )
    if status >= 400:
        return fallback
    try:
        content = json.loads(raw)["choices"][0]["message"]["content"]
        match = re.search(r"\{.*\}", content, re.S)
        data = json.loads(match.group(0) if match else content)
    except (KeyError, IndexError, TypeError, json.JSONDecodeError, AttributeError):
        return fallback
    verdict = data.get("verdict")
    if verdict not in RANK:
        verdict = "discard"
    return {
        "verdict": verdict,
        "reason": clean_reason(str(data.get("reason") or ""), caption),
        "uncertain": clean_uncertain(str(data.get("uncertain") or "")),
    }


def slip_from(hit, note):
    name = hit.get("filename") or "reel"
    short = name.split("_chunk_")[0].split("_")[-1] if name else "reel"
    return {
        "verdict": note["verdict"],
        "stamp": STAMP[note["verdict"]],
        "reason": note["reason"],
        "uncertain": note["uncertain"],
        "caption": excerpt(hit.get("reasoning_content") or ""),
        "counts": count_line(counts_of(hit)),
        "when": f"{clock(hit.get('segment_start_sec'))}–{clock(hit.get('segment_end_sec'))}",
        "reel": short,
        "source": hit.get("source") or "",
    }


def review():
    if not (VSS_URL and VSS_USERNAME and VSS_PASSWORD):
        return {"error": "The desk has no camera login."}
    found = []
    with ThreadPoolExecutor(max_workers=2) as pool:
        for batch in pool.map(search, QUERIES):
            found.extend(batch)
    picked = {}
    for hit in found:
        source = hit.get("source")
        if not source:
            continue
        current = picked.get(source)
        if current is None or interest(hit) > interest(current):
            picked[source] = hit
    hits = sorted(picked.values(), key=interest, reverse=True)[:4]
    with ThreadPoolExecutor(max_workers=4) as pool:
        notes = list(pool.map(verdict_for, hits))
    slips = [slip_from(hit, note) for hit, note in zip(hits, notes)]
    slips.sort(key=lambda item: RANK[item["verdict"]])
    return {
        "file": "HC-17",
        "camera": CAMERA,
        "slips": [item for item in slips if item["source"]][:3],
    }


class Handler(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"

    def log_message(self, fmt, *args):
        return

    def _send(self, status, content_type, body, extra=None):
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        for key, value in (extra or {}).items():
            self.send_header(key, value)
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        parsed = urllib.parse.urlparse(self.path)
        if parsed.path in ("/", "/index.html"):
            self._send(200, "text/html; charset=utf-8", PAGE.encode())
            return
        if parsed.path == "/health":
            self._send(200, "application/json", b'{"ok":true}')
            return
        if parsed.path == "/clip":
            self._clip(parsed)
            return
        self._send(404, "text/plain; charset=utf-8", b"Not on this file.")

    def do_POST(self):
        parsed = urllib.parse.urlparse(self.path)
        if parsed.path != "/api/review":
            self._send(404, "text/plain; charset=utf-8", b"Not on this file.")
            return
        try:
            payload = review()
            status = 400 if payload.get("error") else 200
            self._send(status, "application/json", json.dumps(payload).encode())
        except Exception:
            self._send(
                500,
                "application/json",
                json.dumps({"error": "The camera did not answer."}).encode(),
            )

    def _clip(self, parsed):
        query = urllib.parse.parse_qs(parsed.query)
        source = (query.get("source") or [""])[0]
        if not source.startswith("s3://") or not source.endswith(".mp4"):
            self._send(400, "text/plain; charset=utf-8", b"Bad reel.")
            return
        try:
            token = login()
        except Exception:
            self._send(500, "text/plain; charset=utf-8", b"The camera did not answer.")
            return
        upstream = VSS_URL + "/api/v1/videos/stream?" + urllib.parse.urlencode(
            {"source": source, "token": token}
        )
        headers = {}
        if self.headers.get("Range"):
            headers["Range"] = self.headers["Range"]
        req = urllib.request.Request(upstream, headers=headers)
        try:
            res = urllib.request.urlopen(req, timeout=120)
        except urllib.error.HTTPError as err:
            res = err
            if err.code >= 400 and err.code != 206:
                self._send(502, "text/plain; charset=utf-8", b"Reel unavailable.")
                return
        status = getattr(res, "status", None) or res.getcode()
        self.send_response(status)
        kind = res.headers.get("Content-Type") or ""
        if not kind.startswith("video/"):
            kind = "video/mp4"
        self.send_header("Content-Type", kind)
        for key in ("Content-Length", "Content-Range", "Accept-Ranges"):
            value = res.headers.get(key)
            if value:
                self.send_header(key, value)
        self.send_header("Cache-Control", "private, max-age=300")
        self.end_headers()
        while True:
            chunk = res.read(64 * 1024)
            if not chunk:
                break
            try:
                self.wfile.write(chunk)
            except (BrokenPipeError, ConnectionResetError):
                break
        res.close()


def main():
    server = ThreadingHTTPServer(("0.0.0.0", PORT), Handler)
    server.serve_forever()


if __name__ == "__main__":
    main()
