## speech-to-text: a self-hosted Whisper transcription server

[![CI](https://github.com/wachawo/speech-to-text/actions/workflows/ci.yml/badge.svg)](https://github.com/wachawo/speech-to-text/actions/workflows/ci.yml)
[![License](https://img.shields.io/badge/license-MIT-blue.svg)](https://github.com/wachawo/speech-to-text/blob/main/LICENSE)
[![Python](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org/)

**[English](https://github.com/wachawo/speech-to-text/blob/main/README.md)** | [Español](https://github.com/wachawo/speech-to-text/blob/main/docs/README_ES.md) | [Português](https://github.com/wachawo/speech-to-text/blob/main/docs/README_PT.md) | [Français](https://github.com/wachawo/speech-to-text/blob/main/docs/README_FR.md) | [Deutsch](https://github.com/wachawo/speech-to-text/blob/main/docs/README_DE.md) | [Italiano](https://github.com/wachawo/speech-to-text/blob/main/docs/README_IT.md) | [Русский](https://github.com/wachawo/speech-to-text/blob/main/docs/README_RU.md) | [中文](https://github.com/wachawo/speech-to-text/blob/main/docs/README_ZH.md) | [日本語](https://github.com/wachawo/speech-to-text/blob/main/docs/README_JA.md) | [हिन्दी](https://github.com/wachawo/speech-to-text/blob/main/docs/README_HI.md) | [한국어](https://github.com/wachawo/speech-to-text/blob/main/docs/README_KR.md)

`speech-to-text` turns audio into text with [openai-whisper](https://github.com/openai/whisper), wrapped in a small HTTP service you run yourself. You send an audio file, you get the transcription back. No external API, no per-minute billing, and your audio never leaves your machine.

The project fits local use, batch transcription, and running your own STT server on the network.

* **A ready-to-use HTTP server.** Flask served by uvicorn loads Whisper at startup and answers requests from other machines on your local network.
* **Safe under concurrency.** The server keeps a pool of pre-loaded Whisper instances, so several requests are transcribed in parallel without reloading the model.
* **CPU or GPU, same code.** The backend is selected by environment and which Docker image you build. A CUDA card speeds inference up, but everything also runs on CPU.
* **A CLI client is included.** `stt_client.py` posts local files to the server and prints the result.

### Models

Whisper ships several model sizes. Bigger models are more accurate and slower; smaller ones are fast and light.

| Model      | Parameters | VRAM    | Languages       | Good for                                      |
| ---------- | ---------- | ------- | --------------- | --------------------------------------------- |
| `tiny`     | 39M        | ~1 GB   | multilingual    | quick drafts on weak hardware                 |
| `base`     | 74M        | ~1 GB   | multilingual    | a light general-purpose default               |
| `small`    | 244M       | ~2 GB   | multilingual    | a good accuracy / speed balance               |
| `medium`   | 769M       | ~5 GB   | multilingual    | higher accuracy when you can spare the memory |
| `turbo`    | 809M       | ~6 GB   | multilingual    | near-`large` accuracy, much faster            |
| `large`    | 1550M      | ~10 GB  | multilingual    | best quality, needs a GPU                     |

English-only variants (`tiny.en`, `base.en`, `small.en`, `medium.en`) are a bit more accurate on English audio. The default is `turbo`, which is the best all-round pick for English on a GPU.

### Quick start (Docker)

The easiest way to run the server is with Docker. Model files are cached in `./models` on the host, so they survive container rebuilds.

```bash
git clone https://github.com/wachawo/speech-to-text.git
cd speech-to-text

docker compose up --build                              # GPU (CUDA 13.0)
docker compose -f docker-compose-cpu.yml up --build    # CPU only
```

The GPU build needs `nvidia-container-toolkit` on the host. The first run downloads the Whisper model into `./models`.

### HTTP API

Once the server is up, check its status and send an audio file for transcription.

```bash
curl localhost:5099/api/health

curl -X POST localhost:5099/api/stt \
  -F file=@speech.mp3

curl -X POST 'localhost:5099/api/stt?language=ru' \
  -H 'Content-Type: audio/wav' \
  --data-binary @speech.wav
```

`GET /api/health` returns the pool status. `available` dropping to 0 means every model is currently in flight:

```json
{ "status": "ok", "pool_size": 4, "available": 3, "diarize": false }
```

`POST /api/stt` accepts a `multipart/form-data` field named `file`, or a raw `audio/*` body. An optional `language` (query string or form field) overrides the server default for that request; `auto` autodetects. On success it returns the text and the elapsed seconds:

```json
{ "text": "transcribed text", "elapsed": 1.23 }
```

A language may be given as a code (`ru`) or as its English name (`russian`); anything the model does not know is refused with `400` instead of failing part-way through a transcription. `GET /api/models` lists what it knows.

`GET /api/models` reports what this server carries, so a client does not have to guess. Each backend brings its own language list, because the sets genuinely diverge and a merged list would be wrong for every backend on its own.

```bash
curl -H 'Authorization: Bearer <token>' localhost:5099/api/models
```

```json
{
  "default": "whisper",
  "models": [
    { "backend": "whisper", "model": "turbo", "aliases": ["large-v3-turbo"], "status": "loaded",
      "multilingual": true, "accepts_language": true, "languages_source": "derived",
      "languages": ["en", "zh", "de", "..."], "default_language": "en", "default": true },
    { "backend": "diarize", "model": "nvidia/Nemotron-3-Diarization", "status": "installed",
      "accepts_language": false, "languages": null, "max_speakers": 8, "default": false }
  ]
}
```

`status` is `loaded` when an instance is waiting in a pool, `installed` when the weights are on disk but nothing is loaded yet, and `absent` otherwise. A backend that is configured but not installed says `absent` and nothing more; the reason goes to the log. `accepts_language` says whether `?language=` means anything to that backend at all. The diarizer reports `null` languages rather than an empty list, because it produces no text in any language.

The CLI client reads the same endpoint:

```bash
python3 stt_client.py --list
```

`POST /api/diarize` answers **who spoke when**, and nothing else: it returns time ranges with a speaker number, never text. It is off unless `DIARIZE_ENABLED` is set on an image built with `DIARIZE=true`; otherwise it answers `503`.

```bash
curl -X POST localhost:5099/api/diarize -F file=@meeting.wav
```

```json
{ "segments": [ { "speaker": 0, "start": 0.51, "end": 12.62 },
                { "speaker": 1, "start": 12.20, "end": 19.04 } ], "speakers": 2, "elapsed": 1.23 }
```

Two things about those numbers. Turns may overlap, because each speaker channel is scored on its own, so two people talking at once produce two turns covering the same seconds. And the labels are positions in this one recording, ordered by who spoke first: they are not identities, and the same person gets a different number in the next request. Naming a speaker needs an enrollment step that this service does not have. At most eight speakers are distinguished.

Two transcription backends are available. **Whisper** is the default and accepts a `language`. **Parakeet** (`nvidia/parakeet-tdt-0.6b-v3`) covers 25 European languages, detects the language itself and therefore takes no `language` argument at all, which `GET /api/models` reports as `accepts_language: false`. Select it with `STT_BACKEND=parakeet` on an image built with `PARAKEET=true`; it is a deploy-time choice, not a per-request one, because a second resident model would mean a second set of weights in every worker.

Neither backend is overlap-aware. NVIDIA's overlap-aware model ships only as a NeMo checkpoint, and NeMo pins a different PyTorch than this project's CUDA build, so it is not installable here.

`POST /api/transcript` answers **who said what**: it runs diarization and transcription over the same audio and joins them by time. It needs diarization enabled, and otherwise answers `503`.

```bash
curl -X POST localhost:5099/api/transcript -F file=@meeting.wav
```

```json
{
  "segments": [ { "speaker": 0, "start": 0.5, "end": 4.2, "text": "so where are we", "overlap": false },
                { "speaker": 1, "start": 4.0, "end": 9.8, "text": "green since this morning", "overlap": true } ],
  "turns": [ { "speaker": 0, "start": 0.51, "end": 4.24 }, { "speaker": 1, "start": 4.0, "end": 9.81 } ],
  "speakers": 2,
  "text": "so where are we green since this morning",
  "elapsed": 3.41
}
```

`turns` is the diarizer's raw output and `segments` is the join, kept apart so a caller who distrusts the attribution can still see what the diarizer said. `text` is the plain transcript, identical to what `/api/stt` returns for the same file. A phrase no turn covers keeps `"speaker": null` rather than being handed to the nearest one.

`overlap` marks a phrase during which somebody else was also talking. NVIDIA is explicit that pairing a conventional single-speaker model with diarization is not equivalent to a model built for overlapping speech: an extracted time range still contains every voice that overlaps it, so those phrases may merge or select the wrong speaker's words. Treat a segment marked `overlap` as a place the transcript is least trustworthy.

Uploads are capped at `MAX_CONTENT_LENGTH_MB` (10 MB by default); a larger body returns `413`.

Errors are uniform: `error` carries a generic category and `request_id` correlates the response with the server log, where the full exception is recorded.

```json
{ "error": "Invalid audio data", "request_id": "a1b2c3d4e5f6" }
```

When `STT_TOKENS` is set, every route except `GET /api/health` must carry `Authorization: Bearer <token>`; health stays open so healthchecks keep working.

### CLI client

`stt_client.py` is a small client for working with and testing the server. It reads the server address and token from `STT_URL` and `STT_TOKEN`.

```bash
python3 stt_client.py speech.mp3
python3 stt_client.py file1.wav file2.mp3 file3.ogg
```

### Environment variables

`.env` is loaded by both the server and the client through `python-dotenv`.

| Variable                | Default                 | Purpose                                             |
| ----------------------- | ----------------------- | --------------------------------------------------- |
| `STT_HOST`              | `0.0.0.0`               | server bind address                                 |
| `STT_PORT`              | `5099`                  | server port                                         |
| `STT_POOL_SIZE`         | `8`                     | number of pre-loaded Whisper instances              |
| `STT_TOKENS`            | (empty)                 | comma-separated valid tokens; empty disables auth   |
| `STT_DEBUG`             | `false`                 | Flask debug mode                                     |
| `MAX_CONTENT_LENGTH_MB` | `10`                    | max upload size in MB; a larger body returns `413`  |
| `CORS_ORIGINS`          | `*`                     | allowed CORS origins: `*` or a comma-separated list |
| `GUNICORN_WORKERS`      | `4`                     | worker processes (gunicorn only)                    |
| `LOG_LEVEL`             | `INFO`                  | logging level                                       |
| `LOG_ACCESS`            | `false`                 | log uvicorn access lines                            |
| `WHISPER_MODEL`         | `turbo`                 | Whisper model name (e.g. `small.en`, `turbo`)       |
| `WHISPER_LANGUAGE`      | `en`                    | default transcription language                      |
| `WHISPER_DOWNLOAD_ROOT` | `models`                | model cache directory (`/opt/models` in Docker)     |
| `COMPUTE_TYPE`          | `auto`                  | `cpu`, `cuda`, or `auto`                             |
| `STT_BACKEND`           | `whisper`               | transcription backend: `whisper` or `parakeet`      |
| `PARAKEET_MODEL`        | `nvidia/parakeet-tdt-0.6b-v3` | Parakeet model id                             |
| `PARAKEET_DOWNLOAD_ROOT`| `models`                | Parakeet model cache directory                      |
| `DIARIZE_ENABLED`       | `false`                 | enable `POST /api/diarize` (needs a `DIARIZE=true` image) |
| `DIARIZE_MODEL`         | `nvidia/Nemotron-3-Diarization` | diarization model id                        |
| `DIARIZE_POOL_SIZE`     | `1`                     | pre-loaded diarizer instances                       |
| `DIARIZE_DOWNLOAD_ROOT` | `models`                | diarization model cache directory                   |
| `DIARIZE_THRESHOLD`     | `0.5`                   | speaker activity probability counted as speech      |
| `STT_URL`               | `http://localhost:5099` | client: server base URL                             |
| `STT_TOKEN`             | (empty)                 | client: bearer token sent to the server             |

### Project structure

```text
speech-to-text/
├── stt_server.py        # Flask app wiring, routes, entry point
├── stt_client.py        # CLI client that posts files to the server
├── gu.py                # Gunicorn config and hooks
├── libs/
│   ├── config.py        # every environment variable, read once
│   ├── logs.py          # logging format shared by the app, uvicorn and the CLIs
│   ├── errors.py        # uniform JSON error responses and Flask error handlers
│   ├── auth.py          # optional static-token authentication
│   ├── audio.py         # upload -> 16 kHz mono WAV conversion
│   ├── model_pool.py    # pools of pre-loaded Whisper and diarizer instances
│   ├── catalog.py       # what the server can do, for GET /api/models
│   ├── align.py         # joins transcription segments to speaker turns
│   ├── stt.py           # Whisper wrapper
│   ├── parakeet.py      # NVIDIA Parakeet wrapper, the second transcriber
│   ├── backends.py      # which module transcribes, per STT_BACKEND
│   └── diarize.py       # speaker diarization (who spoke when, no text)
├── Dockerfile           # GPU build (CUDA 13.0)
├── Dockerfile-cpu       # CPU build
├── docs/                # README translations
└── tests/               # pytest tests, no model downloads and no GPU
```

### Development

System packages `ffmpeg` and `libsndfile1` must be present. Install the runtime and dev dependencies:

```bash
pip install -e ".[dev]"
pre-commit install
```

The Makefile wraps the common tasks:

```bash
make run            # foreground: python3 stt_server.py
make start          # background: PID -> .stt_server.pid, logs -> logs/stt_server.log
make stop           # stop the background server
make gunicorn       # run via gunicorn
make test           # pytest
make lint           # pre-commit (black + ruff)
make typecheck      # mypy
```

The test suite stubs the Whisper backend, so it covers the HTTP layer (request_id, error categories, model pool semantics) and runs in seconds without downloading a model or needing a GPU.

### License

[MIT](LICENSE)
