# -*- coding: utf-8 -*-
"""Local text-to-image on CPU — no GPU, no account, no credits.

    generate(prompt, out, width, height)  ->  path

Quality knobs (env):
    SD_MODEL      default "stabilityai/sdxl-base-1.0" (high quality)
                  "stabilityai/sd-turbo" is the fast/weak variant
    SD_STEPS      default 30 for full models, 4 for turbo
    SD_GUIDANCE   default 7.0 for full models, 0.0 for turbo
    SD_MAX_SIDE   default 1024 (render box; the result is rescaled to the
                  requested thumbnail size afterwards)
    SD_THREADS    default = cpu count
"""

import os
import time

MODEL = os.environ.get("SD_MODEL", "stabilityai/sdxl-base-1.0")
NEGATIVE = os.environ.get(
    "SD_NEGATIVE",
    "blurry, low quality, deformed, extra fingers, extra limbs, bad anatomy, "
    "watermark, text, logo, signature, jpeg artifacts, cropped, worst quality, "
    "duplicate, ugly, out of frame")
STATE = {"pipe": None}


def _is_turbo():
    return "turbo" in MODEL.lower()


def _pipe():
    if STATE["pipe"] is None:
        import torch
        from diffusers import AutoPipelineForText2Image
        n = int(os.environ.get("SD_THREADS", "0") or 0) or (os.cpu_count() or 4)
        torch.set_num_threads(n)
        print("[sd] loading %s on CPU (%d threads)..." % (MODEL, n), flush=True)
        t0 = time.time()
        # prefer the fp16 variant files: half the download on a 14 GB runner,
        # then upcast to float32 for CPU inference.
        kwargs = dict(safety_checker=None, requires_safety_checker=False)
        pipe, err = None, None
        for extra in ({"variant": "fp16"}, {}):
            try:
                pipe = AutoPipelineForText2Image.from_pretrained(
                    MODEL, torch_dtype=torch.float32, **kwargs, **extra)
                break
            except Exception as e:  # noqa: BLE001
                err = e
                print("[sd] load failed (%s) -> retry" % type(e).__name__, flush=True)
        if pipe is None:
            raise err
        pipe.set_progress_bar_config(disable=True)
        STATE["pipe"] = pipe
        print("[sd] ready in %.0fs" % (time.time() - t0), flush=True)
    return STATE["pipe"]


def _render_size(w, h):
    cap = float(os.environ.get("SD_MAX_SIDE", "1024"))
    s = min(1.0, cap / max(w, h))
    nw = max(64, int(w * s) // 8 * 8)
    nh = max(64, int(h * s) // 8 * 8)
    return nw, nh


def generate(prompt, out, width=1280, height=720, steps=None, log=print):
    from PIL import Image

    pipe = _pipe()
    w, h = _render_size(width, height)
    turbo = _is_turbo()
    if steps is None:
        steps = int(os.environ.get("SD_STEPS", "4" if turbo else "30"))
    steps = max(1, min(50, steps))
    guidance = float(os.environ.get("SD_GUIDANCE", "0.0" if turbo else "7.0"))
    full_prompt = prompt if turbo else "%s, ultra detailed, sharp focus, 8k, photorealistic" % prompt
    t0 = time.time()
    log("[sd] render %dx%d steps=%d guidance=%.1f ..." % (w, h, steps, guidance))
    kw = dict(num_inference_steps=steps, width=w, height=h)
    if guidance > 0:
        kw["guidance_scale"] = guidance
        kw["negative_prompt"] = NEGATIVE
    img = pipe(full_prompt, **kw).images[0]
    if img.size != (width, height):
        img = img.resize((width, height), Image.LANCZOS)
    os.makedirs(os.path.dirname(out) or ".", exist_ok=True)
    img.convert("RGB").save(out, "JPEG", quality=94)
    log("[sd] saved %s (%.0fs)" % (out, time.time() - t0))
    return out


if __name__ == "__main__":
    import sys
    generate(sys.argv[1], sys.argv[2],
             int(sys.argv[3]) if len(sys.argv) > 3 else 1280,
             int(sys.argv[4]) if len(sys.argv) > 4 else 720)
