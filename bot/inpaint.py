# -*- coding: utf-8 -*-
"""AI out-painting on CPU  -  no GPU, no account, no credits.

The photo is already pasted onto the canvas at its final place; everything
around it (the strip ABOVE the head, the side gaps) is masked and generated
again, so the new area continues the photo's own background instead of being
a fabricated empty space.

Reads the job list from the JOBS env var:

  [{"file":"prep_long.jpg","rect":[0,170,1280,550],
    "out":"out_long.jpg","prompt":"..."}]

rect = the region that must be KEPT untouched (the photo).  Everything else
is regenerated.  STEPS (optional) = inference steps, default 28.
"""
import os
import json
import time

from PIL import Image, ImageFilter

MODEL = os.environ.get(
    "SD_INPAINT_MODEL",
    "stabilityai/stable-diffusion-xl-1.0-inpainting-0.1")
NEGATIVE = os.environ.get(
    "SD_NEGATIVE",
    "text, watermark, logo, signature, letters, writing, people, person, "
    "face, hands, extra person, blurry, low quality, deformed, jpeg "
    "artifacts, visible seam, hard edge, abrupt cut, mismatched colours, "
    "clutter, busy")


def mask_from_rect(size, rect, feather=24):
    """255 = regenerate, 0 = keep the photo exactly as it is."""
    w, h = size
    m = Image.new("L", size, 255)
    x, y, rw, rh = [int(v) for v in rect]
    x = max(0, min(x, w - 1))
    y = max(0, min(y, h - 1))
    rw = max(1, min(rw, w - x))
    rh = max(1, min(rh, h - y))
    m.paste(0, (x, y, x + rw, y + rh))
    return m.filter(ImageFilter.GaussianBlur(feather))


def load_pipe():
    import torch
    from diffusers import AutoPipelineForInpainting
    n = int(os.environ.get("SD_THREADS", "0") or 0) or (os.cpu_count() or 4)
    torch.set_num_threads(n)
    print("[inpaint] loading %s on CPU (%d threads)..." % (MODEL, n), flush=True)
    pipe, err = None, None
    for extra in ({"variant": "fp16"}, {}):
        try:
            pipe = AutoPipelineForInpainting.from_pretrained(
                MODEL, torch_dtype=torch.float32,
                safety_checker=None, requires_safety_checker=False, **extra)
            break
        except Exception as e:  # noqa: BLE001
            err = e
            print("[inpaint] load failed (%s) -> retry" % type(e).__name__,
                  flush=True)
    if pipe is None:
        raise SystemExit("[inpaint] cannot load %s: %s" % (MODEL, err))
    pipe.set_progress_bar_config(disable=True)
    return pipe


def main():
    jobs = json.loads(os.environ.get("JOBS", "[]"))
    steps = int(os.environ.get("STEPS", "28") or 28)
    guidance = float(os.environ.get("GUIDANCE", "6.5") or 6.5)
    os.makedirs("out", exist_ok=True)
    if not jobs:
        raise SystemExit("[inpaint] no jobs")
    pipe = load_pipe()
    import torch
    for j, job in enumerate(jobs):
        path = job["file"]
        if not os.path.exists(path):
            print("[inpaint] missing %s - skipped" % path, flush=True)
            continue
        img = Image.open(path).convert("RGB")
        mask = mask_from_rect(img.size, job["rect"])
        out = job.get("out") or ("out_%d.jpg" % (j + 1))
        if not out.startswith("out/"):
            out = "out/" + os.path.basename(out)
        print("[inpaint] %s -> %s  (%dx%d, %d steps)"
              % (path, out, img.width, img.height, steps), flush=True)
        t0 = time.time()
        g = torch.Generator().manual_seed(int(job.get("seed", 7)))
        res = pipe(
            prompt=job["prompt"],
            negative_prompt=NEGATIVE,
            image=img,
            mask_image=mask,
            width=img.width,
            height=img.height,
            num_inference_steps=steps,
            guidance_scale=guidance,
            strength=1.0,
            generator=g,
        ).images[0]
        res.save(out, "JPEG", quality=96)
        print("[inpaint] done in %.0fs" % (time.time() - t0), flush=True)
    print("[inpaint] ALL DONE", flush=True)


if __name__ == "__main__":
    main()
