# Medha models

Weights are **fetched, never committed**. `models.lock.json` is the source of truth; `tools/fetch_models.py` pins revisions, downloads, verifies and writes the license sidecars in `MODEL_LICENSES/`.

| ID | Job | Profiles | Runtime | Device | Disk | License | Gated |
|---|---|---|---|---|---|---|---|
| `qwen3-4b-instruct-2507` | lesson script + board-action JSON | `demo_gpu` | ollama | gpu | 2.5 GB | Apache-2.0 | no |
| `phi4-mini-3.8b` | VRAM-safe lesson script fallback | `safe_gpu` | ollama | gpu | 2.5 GB | MIT | no |
| `llama32-3b` | CPU-only fallback | `cpu` | ollama | cpu | 2.0 GB | Llama-3.2-Community | no |
| `bge-m3` | multilingual embeddings | `core` | onnxruntime | cpu | 2.3 GB | MIT | no |
| `bge-reranker-v2-m3` | cross-encoder reranker | `core` | torch-cpu | cpu | 2.3 GB | Apache-2.0 | no |
| `smolvlm-500m-instruct` | teaching image captions and diagram descriptions | `core` | torch-cpu | cpu | 1.0 GB | Apache-2.0 | no |
| `kokoro-82m` | English speech | `core` | torch-cpu | cpu | 0.4 GB | Apache-2.0 | no |
| `docling-layout-heron` | PDF layout analysis | `core` | torch-cpu | cpu | 0.2 GB | Apache-2.0 | no |
| `docling-models` | PDF table structure | `core` | torch-cpu | cpu | 0.4 GB | CDLA-Permissive-2.0 OR Apache-2.0 | no |
| `docling-layout-heron-onnx` | optional ONNX layout variant | `optional` | onnxruntime | cpu | 0.2 GB | Apache-2.0 | no |
| `faster-whisper-small` | optional voice input + word timestamps | `optional` | ctranslate2 | cpu | 0.5 GB | MIT | no |
| `indic-parler-tts` | Kannada / Hindi speech (pre-generated) | `indic` | torch-cpu | cpu | 3.6 GB | Apache-2.0 | **yes** |
| `flan-t5-large-tokenizer` | Indic Parler voice-description tokenizer | `indic` | torch-cpu | cpu | 0.01 GB | Apache-2.0 | no |
| `indictrans2-en-indic-dist-200M` | English to Kannada/Hindi translation | `indic` | torch-cpu | cpu | 0.9 GB | MIT | **yes** |

## Profiles

```powershell
python tools/fetch_models.py --profile demo_gpu
python tools/fetch_models.py --profile safe_gpu
python tools/fetch_models.py --profile cpu
python tools/fetch_models.py --profile indic
python tools/fetch_models.py --profile optional
python tools/fetch_models.py --verify
```

`core` entries are included in every profile. `indic` downloads are gated: accept the model terms on Hugging Face and set `HF_TOKEN` first.

## Deliberately not shipped

| ID | Reason |
|---|---|
| `qwen2.5-vl-3b` | Repo LICENSE remains Qwen Research (non-commercial) despite Apache metadata in README. |
| `piper-lessac` | Piper is GPL-3.0-or-later; en_US-lessac-medium is trained on Blizzard 2013 research-only data. |
| `meta-mms` | MMS weights are CC-BY-NC 4.0 (non-commercial). |

## Hardware notes

- Qwen3-4B-Instruct Q4_K_M + q8 KV at 3072 ctx is roughly 3.0 GB VRAM. Do not open a browser.
- All non-LLM models run CPU-only. Install `requirements/cpu.txt`, never the CUDA torch wheel.
- Prefetch Docling artifacts with `python tools/fetch_docling.py` and verify offline bundles with `python tools/fetch_docling.py --offline`.
- BGE-M3 ONNX embeddings and the BGE reranker are CPU-only and use about 4.5 GB RAM when both are warm.
- SmolVLM-500M is CPU-only and adds about 1 GB of weights. Image descriptions are cached; the first cold description can take 15-20 seconds.

Generated from `models.lock.json` on 2026-10-28T07:51:55+00:00.
