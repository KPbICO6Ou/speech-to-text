# AGENTS.md

Conventions and context for anyone working in this repository, human or tooling.

## What this is

A single-process Flask + uvicorn HTTP service wrapping `openai-whisper` for speech-to-text. No database, no background worker, no frontend - just `stt_server.py` (app wiring, routes, entry point), `stt_client.py` (a CLI that POSTs files to it), `gu.py` (Gunicorn config and hooks) and the `libs/` package holding everything else: `config.py`, `logs.py`, `errors.py`, `auth.py`, `audio.py`, `model_pool.py`, `stt.py`.

## Architecture

- **One module, one job.** `libs/config.py` is the only place `os.getenv` is called and the only place `load_dotenv` runs - enforced, nothing else in the repo calls either. Import it as `from libs import config` and read `config.X` at call time, never `from libs.config import X`: the tests monkeypatch `config` attributes and a copied name would not see the patch.
- **Model pool, not a model singleton.** `libs/model_pool.py::init_model_pool()` pre-loads `STT_POOL_SIZE` Whisper instances into a `queue.Queue`. Each `/api/stt` request calls `acquire_model()`, runs `stt.get_stt_bio()`, and `release_model()`s it in `finally`. Pool exhaustion returns 503. This is what makes the server safe under concurrency, because Whisper itself is not thread-safe.
- **Two run modes, two pool semantics:**
  - **Direct (`python3 stt_server.py`)** - one process; the pool lives in it and `STT_POOL_SIZE` is the real concurrency limit.
  - **Gunicorn (`gunicorn --config gu.py stt_server:app`)** - `worker_class = "sync"`, `GUNICORN_WORKERS` processes; each worker calls `init_model_pool` from `post_fork` under an `flock` on `/tmp/.stt_model_init.lock` so only one downloads the model. With sync workers `STT_POOL_SIZE=1` per worker is intentional - concurrency comes from worker count. **Do not switch to `gthread`**: PyTorch's MKL/OpenBLAS thread pools deadlock with Gunicorn threads.
- **Torch must never load before `fork()`.** `libs/stt.py`, and therefore `libs/model_pool.py`, pulls in torch and whisper. `gu.py` imports `init_model_pool` inside `post_fork`, not at module scope. The tests rely on the same boundary - `tests/conftest.py` replaces `sys.modules["libs.stt"]` with a stub before importing `stt_server`, so the suite needs neither torch nor whisper.
- **Audio path.** `libs/audio.py::convert_to_wav()` decodes the upload through pydub and exports 16 kHz mono 16-bit WAV to a `BytesIO` before `stt.get_stt_bio()` sees it. The server does the resampling so `libs/stt.py` skips its torchaudio resample branch on the hot path. Changing one side means keeping this contract intact.
- **Determinism is deliberate.** `get_stt_bio` seeds torch + numpy and decodes with `temperature=0.0, beam_size=1, best_of=1, condition_on_previous_text=False`. Don't relax these without a reason - the goal is stable output for repeated identical inputs.
- **CPU vs GPU is environment-only.** The same Python code runs both; `COMPUTE_TYPE` (`cpu` / `cuda` / `auto`) plus the chosen Dockerfile/compose file select the backend. `Dockerfile` + `docker-compose.yml` (CUDA 13.0, `torch+cu130`) and `Dockerfile-cpu` + `docker-compose-cpu.yml` are the two parallel images.
- **Containers start as root, then drop.** `entrypoint.sh` runs as root, chowns the bind-mounted `/opt/models`, `/opt/logs`, `/opt/recs` (host-owned mounts the build-time chown cannot reach) and `exec`s the command as `stt` via `setpriv`. Without it the first `whisper.load_model` dies with `PermissionError`.
- **The GPU is requested through CDI** (`devices: [nvidia.com/gpu=all]`), not `deploy.resources.reservations.devices`: with the latter a `systemctl daemon-reload` silently revokes device access on cgroup v2, and the failure surfaces as misleading cuDNN/cuBLAS errors. CDI needs `sudo nvidia-ctk cdi generate --output=/etc/cdi/nvidia.yaml` on the host, regenerated after driver updates.

## Commands

```bash
make run           # foreground: python3 stt_server.py
make start         # background via nohup; PID -> .stt_server.pid, logs -> logs/stt_server.log
make stop          # kills the PID from .stt_server.pid (SIGTERM, then SIGKILL after 1s)
make gunicorn      # gunicorn --config gu.py stt_server:app

make test          # pytest (stubs Whisper; no model download, no GPU)
make lint          # pre-commit: black + ruff over the whole repo

docker compose up --build                            # GPU build (default)
docker compose -f docker-compose-cpu.yml up --build   # CPU build

python3 stt_client.py file.mp3 [file2 ...]   # respects STT_URL (default http://localhost:5099)
python3 -m libs.stt file.wav                 # transcribe one file without the server
```

CI runs exactly two jobs: `pre-commit run --all-files` and `pytest`. Both must pass before a PR is mergeable. Docker images are **not** built in CI - changing a `COPY` line or `entrypoint.sh` needs a local `docker compose ... up --build`.

## Environment

`.env` is loaded once, by `libs/config.py`. Variables actually consumed by the code:

- Server: `STT_HOST`, `STT_PORT`, `STT_POOL_SIZE`, `STT_DEBUG`, `LOG_LEVEL`, `LOG_ACCESS`
- Auth / limits / CORS: `STT_TOKENS` (comma-separated; empty disables auth), `MAX_CONTENT_LENGTH_MB`, `CORS_ORIGINS`
- Whisper: `WHISPER_MODEL`, `WHISPER_LANGUAGE`, `WHISPER_DOWNLOAD_ROOT` (host `models`, container `/opt/models`), `COMPUTE_TYPE`
- Gunicorn: `GUNICORN_WORKERS`
- Client: `STT_URL`, `STT_TOKEN`

Model `.pt` files live in `./models/` and are mounted at `/opt/models`, so the cache survives rebuilds.

## Endpoints

- `GET /api/health` - `{status, pool_size, available}`; `available` at 0 means every model is in flight. Open, no token required, so healthchecks keep working.
- `POST /api/stt` - multipart field `file` or a raw `audio/*` body, optional `language` (ISO code or `auto`). Returns `{text, elapsed}`. 400 on missing/bad audio or bad language, 401 without a valid token when `STT_TOKENS` is set, 413 over the size limit, 503 when the pool stays exhausted for 120s, 500 on Whisper errors.
- Every error body is exactly `{"error": <category>, "request_id": <12 hex>}` (413 adds `limit_mb`). Details never reach the client - the full exception goes to the log under the same `request_id`. Build them with `libs/errors.py::build_error_response`, never by hand.

## Code conventions

Beyond PEP 8 and Python 3.12 defaults:

- **File header:** `#!/usr/bin/env python3`, `# -*- coding: utf-8 -*-`, then a one-line module docstring. Every file.
- **Every function has a docstring** - nested functions, Flask handlers, Gunicorn hooks and test helpers included.
- **No name starts with `_`.** Not for "private", not for callbacks, not for unused arguments (write `exception`, not `_exception`). Dunder methods are the only exception.
- **Function names are verb + noun** (`get_pool_status`, `build_error_response`, `convert_to_wav`).
- **Imports:** stdlib, then third-party, then a `# Local imports` block, then UPPER_CASE constants. No imports buried inside functions, except the deliberate torch-after-fork ones described above.
- **Every message goes through `logging`** - never `print`. Module-level `logger = logging.getLogger(__name__)`; `libs/logs.py::setup_logging()` configures the root logger, and only entry points call it. Log calls use lazy `%`-style formatting, not f-strings.
- **Exceptions log `type(exc).__name__`, `str(exc)` and `traceback.format_exc()`**, then return a generic body.
- **Every runnable file ends with `main()` + `if __name__ == "__main__": main()`**; module-only files get an empty `main()`.
- **No decorative comment banners** (`# ----`, `# ====`).
- **Functional style over classes.** Classes only for ORM models and framework subclasses; there are none here.
- **Do not add tests unless asked.** When behaviour changes, update the existing suite so it keeps passing.
- `black` and `ruff` cover the whole repo (line length 100, target py312, rules `E,F,I,UP,B`, ignoring `E501,UP009`). Nothing is excluded except `models/`.

## Repo etiquette

- **English only** in everything that lands in the repo: code, comments, docstrings, log messages, commit messages, PR titles and bodies, README, CHANGELOG. The sole exception is `docs/README_<LANG>.md`, which are translations.
- **No em dash and no middle dot.** Use a spaced hyphen (` - `) as a separator, in prose, in UI strings and in log messages alike.
- **Branch per change**, PR into `main`. Never force-push to `main`.
- **`CHANGELOG.md` follows Keep a Changelog**; user-visible changes get an entry under `## [Unreleased]`. Release tags are a manual step, never automatic.
- **The ten `docs/README_<LANG>.md` translations mirror `README.md`.** A change to its Project structure or environment table belongs in all of them. Only three carry a translated file tree today (DE, FR, RU); the rest keep the English one.
- `.gitignore` applies a default-deny to root `*.md`: only `README.md`, `CHANGELOG.md`, `AGENTS.md` and `docs/*.md` are tracked.

## Local overlay

`CLAUDE.local.md` sits beside this file, is gitignored, and holds whatever is specific to one machine or one operator: deployment targets, host addresses, personal workflow rules. It is optional - a clone without it works fine, and the import below is simply skipped.

@CLAUDE.local.md
