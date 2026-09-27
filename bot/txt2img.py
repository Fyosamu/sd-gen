# -*- coding: utf-8 -*-
"""Free text->image for the bot - no API key, no credits, no local bandwidth.

The runner calls gen.pollinations.ai keyless (verified from a GitHub runner:
200 + image/jpeg for `flux` and `nanobanana-2-lite`).  Prompting, download and
validation all happen on the runner, so the machine that runs the bot never
touches a byte of it - same rule as everything else in this project.

Reads the job list from the JOBS env var:

  [{"file": "chess_scene.jpg", "prompt": "...", "model": "flux",
    "width": 1280, "height": 720, "seed": 11}]
"""
import io
import json
import os
import time
import urllib.parse
import urllib.request

from PIL import Image

# gen.pollinations.ai now answers 401 (wants an sk_ key); the classic host
# image.pollinations.ai still serves images keyless - verified from a runner.
BASE = "https://image.pollinations.ai/prompt/"
# tried in order when the first choice fails / is throttled
FALLBACK_MODELS = ["flux", "nanobanana-2-lite", "nanobanana-2", "seedream5",
                   "qwen-image"]


def _get(url, timeout=100):
    req = urllib.request.Request(url, headers={"User-Agent": "sd-gen/1.0"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        data = r.read()
        ctype = (r.headers.get("Content-Type") or "").lower()
        if "json" in ctype or "text" in ctype or "html" in ctype:
            raise ValueError("server said: %s"
                             % data[:240].decode("utf-8", "replace"))
        return data


def generate(prompt, out, model="flux", width=1280, height=720, seed=0,
             tries=5):
    p = urllib.parse.quote(prompt, safe="")
    pool = [model] + [m for m in FALLBACK_MODELS if m != model]
    last = None
    for attempt in range(tries):
        m = pool[min(attempt, len(pool) - 1)]
        url = ("%s%s?model=%s&width=%d&height=%d&nologo=true&seed=%d"
               % (BASE, p, m, int(width), int(height), int(seed) + attempt))
        try:
            data = _get(url)
            img = Image.open(io.BytesIO(data))
            img.load()                     # fails on an HTML/JSON error body
            if img.width < 64 or img.height < 64 or len(data) < 3000:
                raise ValueError("degenerate image (%dB)" % len(data))
            os.makedirs(os.path.dirname(out) or ".", exist_ok=True)
            img.convert("RGB").save(out, "JPEG", quality=95)
            print("[txt2img] %s  %dx%d  %dB  model=%s"
                  % (out, img.width, img.height, len(data), m), flush=True)
            return out
        except Exception as e:              # noqa: BLE001
            last = e
            print("[txt2img] attempt %d/%d model=%s failed: %s"
                  % (attempt + 1, tries, m, e), flush=True)
            time.sleep(3 + 3 * attempt)
    raise SystemExit("[txt2img] giving up on %s: %s" % (out, last))


def main():
    jobs = json.loads(os.environ.get("JOBS", "[]") or "[]")
    if not jobs:
        raise SystemExit("[txt2img] no jobs")
    os.makedirs("out", exist_ok=True)
    for j in jobs:
        name = j.get("file") or ("img_%d.jpg" % (abs(hash(j["prompt"])) % 99999))
        if not name.startswith("out/"):
            name = "out/" + os.path.basename(name)
        generate(j["prompt"], name,
                 model=j.get("model", "flux"),
                 width=int(j.get("width", 1280)),
                 height=int(j.get("height", 720)),
                 seed=int(j.get("seed", 7)))
    print("[txt2img] ALL DONE", flush=True)


if __name__ == "__main__":
    main()
