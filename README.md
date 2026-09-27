# sd-gen

Image generation that runs entirely on GitHub Actions. No GPU, no API key, no
GPU bill - you start a workflow by hand and pick the pictures out of the run's
artifacts.

## The four workflows

All four are `workflow_dispatch`, started from the **Actions** tab.

| Workflow | What it does |
| --- | --- |
| `image-gen` | Stable Diffusion XL (`stabilityai/stable-diffusion-xl-base-1.0`) on CPU with diffusers. Frees about 14 GB of runner disk first, adds 6 GB of swap for the model's peak memory, and caches the weights so later runs skip the 3.5 GB download. |
| `txt2img` | Keyless text to image through `image.pollinations.ai`. Takes a JSON list, so one run produces a whole batch. |
| `inpaint` | Out-painting: the photo is placed at its final position and the masked area around it is generated as a continuation of the photo's own background. |
| `probe` | Latency benchmark - one unique prompt per model, so no response can be served from cache. |

## Running it

**Actions - pick a workflow - Run workflow.**

`image-gen` takes a `prompt`, plus optional `width`, `height` and any
diffusers model id.

`txt2img` takes a JSON list of jobs, so a single run can produce many images:

```json
[{"file": "boat.jpg", "prompt": "a red rowing boat docked at a wooden pier",
  "model": "flux", "width": 1024, "height": 576, "seed": 101}]
```

`inpaint` jobs are `{"file", "rect", "out", "prompt"}` with a `steps` input
(28 by default).

Everything comes back as workflow **artifacts**.

## Model notes

`txt2img` needs no key and falls through `flux` - `nanobanana-2-lite` -
`nanobanana-2` - `seedream5` - `qwen-image` when one of them is throttled.
Every result is decoded before it is saved: anything under 64 x 64 or under
3 KB is thrown away instead of uploaded, so a throttled run never hands you a
broken file.

## Requirements

A **public** repository - public workflow runs are free, and nothing is
installed on your own machine.

---

**[dazo](https://fyosamu.github.io/)** - AI, automation and web work.

[AI and automation](https://fyosamu.github.io/ai-automation/) -
[Pricing](https://fyosamu.github.io/pricing/) -
[hkay7645@gmail.com](mailto:hkay7645@gmail.com)
