## speech-to-text: ein selbst gehosteter Whisper-Transkriptionsserver

[![CI](https://github.com/wachawo/speech-to-text/actions/workflows/ci.yml/badge.svg)](https://github.com/wachawo/speech-to-text/actions/workflows/ci.yml)
[![License](https://img.shields.io/badge/license-MIT-blue.svg)](https://github.com/wachawo/speech-to-text/blob/main/LICENSE)
[![Python](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org/)

[English](https://github.com/wachawo/speech-to-text/blob/main/README.md) | [Español](https://github.com/wachawo/speech-to-text/blob/main/docs/README_ES.md) | [Português](https://github.com/wachawo/speech-to-text/blob/main/docs/README_PT.md) | [Français](https://github.com/wachawo/speech-to-text/blob/main/docs/README_FR.md) | **[Deutsch](https://github.com/wachawo/speech-to-text/blob/main/docs/README_DE.md)** | [Italiano](https://github.com/wachawo/speech-to-text/blob/main/docs/README_IT.md) | [Русский](https://github.com/wachawo/speech-to-text/blob/main/docs/README_RU.md) | [中文](https://github.com/wachawo/speech-to-text/blob/main/docs/README_ZH.md) | [日本語](https://github.com/wachawo/speech-to-text/blob/main/docs/README_JA.md) | [हिन्दी](https://github.com/wachawo/speech-to-text/blob/main/docs/README_HI.md) | [한국어](https://github.com/wachawo/speech-to-text/blob/main/docs/README_KR.md)

`speech-to-text` wandelt Audio mit [openai-whisper](https://github.com/openai/whisper) in Text um, eingebettet in einen kleinen HTTP-Dienst, den Sie selbst betreiben. Sie senden eine Audiodatei und erhalten die Transkription zurück. Keine externe API, keine Abrechnung pro Minute, und Ihre Audiodaten verlassen niemals Ihre Maschine.

Das Projekt eignet sich für die lokale Nutzung, für die Stapeltranskription und für den Betrieb eines eigenen STT-Servers im Netzwerk.

* **Ein einsatzbereiter HTTP-Server.** Flask, ausgeliefert über uvicorn, lädt Whisper beim Start und beantwortet Anfragen von anderen Maschinen in Ihrem lokalen Netzwerk.
* **Sicher bei Nebenläufigkeit.** Der Server hält einen Pool vorab geladener Whisper-Instanzen bereit, sodass mehrere Anfragen parallel transkribiert werden, ohne das Modell neu zu laden.
* **CPU oder GPU, derselbe Code.** Das Backend wird über die Umgebung und über das gebaute Docker-Image ausgewählt. Eine CUDA-Karte beschleunigt die Inferenz, aber alles läuft auch auf der CPU.
* **Ein CLI-Client ist enthalten.** `stt_client.py` sendet lokale Dateien an den Server und gibt das Ergebnis aus.

### Modelle

Whisper liefert mehrere Modellgrößen. Größere Modelle sind genauer und langsamer; kleinere sind schnell und leichtgewichtig.

| Model      | Parameters | VRAM    | Languages       | Good for                                      |
| ---------- | ---------- | ------- | --------------- | --------------------------------------------- |
| `tiny`     | 39M        | ~1 GB   | mehrsprachig    | schnelle Entwürfe auf schwacher Hardware      |
| `base`     | 74M        | ~1 GB   | mehrsprachig    | ein leichter Allzweck-Standard                |
| `small`    | 244M       | ~2 GB   | mehrsprachig    | eine gute Balance aus Genauigkeit und Tempo   |
| `medium`   | 769M       | ~5 GB   | mehrsprachig    | höhere Genauigkeit, wenn Speicher verfügbar ist |
| `turbo`    | 809M       | ~6 GB   | mehrsprachig    | nahezu `large`-Genauigkeit, deutlich schneller |
| `large`    | 1550M      | ~10 GB  | mehrsprachig    | beste Qualität, benötigt eine GPU             |

Die rein englischen Varianten (`tiny.en`, `base.en`, `small.en`, `medium.en`) sind bei englischem Audio etwas genauer. Der Standard ist `turbo`, die beste Allround-Wahl für Englisch auf einer GPU.

### Schnellstart (Docker)

Am einfachsten lässt sich der Server mit Docker betreiben. Modelldateien werden auf dem Host in `./models` zwischengespeichert, sodass sie Neuaufbauten der Container überstehen.

```bash
git clone https://github.com/wachawo/speech-to-text.git
cd speech-to-text

docker compose up --build                              # GPU (CUDA 13.0)
docker compose -f docker-compose-cpu.yml up --build    # CPU only
```

Der GPU-Build benötigt `nvidia-container-toolkit` auf dem Host. Beim ersten Lauf wird das Whisper-Modell nach `./models` heruntergeladen.

### HTTP-API

Sobald der Server läuft, prüfen Sie seinen Status und senden eine Audiodatei zur Transkription.

```bash
curl localhost:5099/api/health

curl -X POST localhost:5099/api/stt \
  -F file=@speech.mp3

curl -X POST 'localhost:5099/api/stt?language=ru' \
  -H 'Content-Type: audio/wav' \
  --data-binary @speech.wav
```

`GET /api/health` gibt den Status des Pools zurück. Wenn `available` auf 0 fällt, sind gerade alle Modelle in Verwendung:

```json
{ "status": "ok", "pool_size": 4, "available": 3, "diarize": false }
```

`POST /api/stt` akzeptiert ein `multipart/form-data`-Feld namens `file` oder einen rohen `audio/*`-Body. Ein optionales `language` (Query-String oder Formularfeld) überschreibt für diese Anfrage den Server-Standard; `auto` erkennt die Sprache automatisch. Bei Erfolg werden der Text und die verstrichenen Sekunden zurückgegeben:

```json
{ "text": "transcribed text", "elapsed": 1.23 }
```

Die Sprache kann als Code (`ru`) oder mit ihrem englischen Namen (`russian`) angegeben werden; was das Modell nicht kennt, wird mit `400` abgelehnt, statt mitten in einer Transkription zu scheitern. `GET /api/models` listet auf, was es kennt. Das gilt für Backends, die eine Sprache annehmen (`accepts_language: true`). Parakeet erkennt die Sprache selbst und ignoriert den Wert, und es kann Sprache, bei der es unsicher ist, ohne Hinweis auslassen: In einer mehrsprachigen Aufnahme liefert es für die Minderheitensprache unter Umständen gar nichts.

`GET /api/models` gibt an, was dieser Server mitbringt, sodass ein Client nicht raten muss. Jedes Backend bringt seine eigene Sprachliste mit, denn die Mengen weichen tatsächlich voneinander ab, und eine zusammengeführte Liste wäre für jedes Backend einzeln falsch.

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

`status` ist `loaded`, wenn eine Instanz in einem Pool wartet, `installed`, wenn die Gewichte auf der Platte liegen, aber noch nichts geladen ist, und andernfalls `absent`. Ein Backend, das konfiguriert, aber nicht installiert ist, meldet `absent` und nichts weiter; der Grund geht ins Log. `accepts_language` sagt, ob `?language=` für dieses Backend überhaupt eine Bedeutung hat. Der Diarisierer meldet `null` als Sprachen statt einer leeren Liste, denn er erzeugt in keiner Sprache Text.

Der CLI-Client liest denselben Endpunkt:

```bash
python3 stt_client.py --list
```

`POST /api/diarize` beantwortet **wer wann gesprochen hat**, und sonst nichts: Der Endpunkt gibt Zeitbereiche mit einer Sprechernummer zurück, niemals Text. Er ist deaktiviert, sofern nicht `DIARIZE_ENABLED` auf einem mit `DIARIZE=true` gebauten Image gesetzt ist; andernfalls antwortet er mit `503`.

```bash
curl -X POST localhost:5099/api/diarize -F file=@meeting.wav
```

```json
{ "segments": [ { "speaker": 0, "start": 0.51, "end": 12.62 },
                { "speaker": 1, "start": 12.20, "end": 19.04 } ], "speakers": 2, "elapsed": 1.23 }
```

Zwei Hinweise zu diesen Zahlen. Die Sprechbeiträge dürfen sich überlappen, denn jeder Sprecherkanal wird für sich bewertet, sodass zwei gleichzeitig sprechende Personen zwei Beiträge über dieselben Sekunden erzeugen. Und die Nummern sind Positionen innerhalb dieser einen Aufnahme, geordnet danach, wer zuerst gesprochen hat: Sie sind keine Identitäten, und dieselbe Person erhält bei der nächsten Anfrage eine andere Nummer. Einen Sprecher zu benennen erfordert einen Enrollment-Schritt, den dieser Dienst nicht hat. Es werden höchstens acht Sprecher unterschieden.

Es stehen zwei Transkriptions-Backends zur Verfügung. **Whisper** ist der Standard und akzeptiert ein `language`. **Parakeet** (`nvidia/parakeet-tdt-0.6b-v3`) deckt 25 europäische Sprachen ab, erkennt die Sprache selbst und nimmt daher überhaupt kein `language`-Argument entgegen, was `GET /api/models` als `accepts_language: false` meldet. Wählen Sie es mit `STT_BACKEND=parakeet` auf einem mit `PARAKEET=true` gebauten Image; das ist eine Entscheidung zur Deployment-Zeit und keine pro Anfrage, denn ein zweites dauerhaft geladenes Modell würde einen zweiten Satz Gewichte in jedem Worker bedeuten.

Keines der beiden Backends ist auf überlappende Sprache ausgelegt. NVIDIAs Modell für überlappende Sprache wird ausschließlich als NeMo-Checkpoint ausgeliefert, und NeMo legt eine andere PyTorch-Version fest als der CUDA-Build dieses Projekts, sodass es sich hier nicht installieren lässt.

`POST /api/transcript` beantwortet **wer was gesagt hat**: Der Endpunkt führt Diarisierung und Transkription über demselben Audio aus und verbindet beides über die Zeit. Er benötigt eine aktivierte Diarisierung und antwortet andernfalls mit `503`.

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

`turns` ist die Rohausgabe des Diarisierers und `segments` ist die Verknüpfung; beides bleibt getrennt, damit ein Client, der der Zuordnung misstraut, weiterhin sehen kann, was der Diarisierer gemeldet hat. `text` ist die schlichte Transkription, identisch mit dem, was `/api/stt` für dieselbe Datei zurückgibt. Eine Phrase, die von keinem Sprechbeitrag abgedeckt wird, behält `"speaker": null`, statt dem nächstgelegenen zugeschlagen zu werden.

`overlap` markiert eine Phrase, während der auch jemand anderes gesprochen hat. NVIDIA sagt ausdrücklich, dass die Kombination eines herkömmlichen Einzelsprecher-Modells mit Diarisierung nicht einem Modell entspricht, das für überlappende Sprache gebaut wurde: Ein herausgeschnittener Zeitbereich enthält weiterhin jede Stimme, die ihn überlappt, sodass diese Phrasen verschmelzen oder die Worte des falschen Sprechers auswählen können. Behandeln Sie ein mit `overlap` markiertes Segment als die Stelle, an der die Transkription am wenigsten vertrauenswürdig ist.

Uploads sind auf `MAX_CONTENT_LENGTH_MB` begrenzt (standardmäßig 10 MB); ein größerer Body gibt `413` zurück.

Fehler sind einheitlich: `error` trägt eine generische Kategorie, und `request_id` verknüpft die Antwort mit dem Server-Log, in dem die vollständige Ausnahme festgehalten wird.

```json
{ "error": "Invalid audio data", "request_id": "a1b2c3d4e5f6" }
```

Wenn `STT_TOKENS` gesetzt ist, muss jede Route außer `GET /api/health` `Authorization: Bearer <token>` mitführen; dieser Endpunkt bleibt offen, damit Healthchecks weiterhin funktionieren.

### CLI-Client

`stt_client.py` ist ein kleiner Client zum Arbeiten mit dem Server und zum Testen. Er liest die Server-Adresse und das Token aus `STT_URL` und `STT_TOKEN`.

```bash
python3 stt_client.py speech.mp3
python3 stt_client.py file1.wav file2.mp3 file3.ogg
```

### Umgebungsvariablen

`.env` wird sowohl vom Server als auch vom Client über `python-dotenv` geladen.

| Variable                | Default                 | Zweck                                               |
| ----------------------- | ----------------------- | --------------------------------------------------- |
| `STT_HOST`              | `0.0.0.0`               | Bind-Adresse des Servers                            |
| `STT_PORT`              | `5099`                  | Server-Port                                         |
| `STT_POOL_SIZE`         | `8`                     | Anzahl vorab geladener Whisper-Instanzen            |
| `STT_TOKENS`            | (empty)                 | kommagetrennte gültige Tokens; leer deaktiviert Auth |
| `STT_DEBUG`             | `false`                 | Flask-Debug-Modus                                   |
| `MAX_CONTENT_LENGTH_MB` | `10`                    | maximale Upload-Größe in MB; ein größerer Body gibt `413` zurück |
| `CORS_ORIGINS`          | `*`                     | erlaubte CORS-Ursprünge: `*` oder eine kommagetrennte Liste |
| `GUNICORN_WORKERS`      | `4`                     | Worker-Prozesse (nur gunicorn)                      |
| `LOG_LEVEL`             | `INFO`                  | Logging-Level                                       |
| `LOG_ACCESS`            | `false`                 | uvicorn-Access-Zeilen protokollieren                |
| `WHISPER_MODEL`         | `small.en`              | Whisper-Modellname (z. B. `small.en`, `turbo`)      |
| `WHISPER_LANGUAGE`      | `en`                    | Standardsprache der Transkription                   |
| `WHISPER_DOWNLOAD_ROOT` | `models`                | Verzeichnis des Modell-Caches (`/opt/models` in Docker) |
| `COMPUTE_TYPE`          | `auto`                  | `cpu`, `cuda` oder `auto`                            |
| `STT_BACKEND`           | `whisper`               | Transkriptions-Backend: `whisper` oder `parakeet`   |
| `PARAKEET_MODEL`        | `nvidia/parakeet-tdt-0.6b-v3` | ID des Parakeet-Modells                             |
| `PARAKEET_DOWNLOAD_ROOT`| `models`                | Verzeichnis des Parakeet-Modell-Caches              |
| `DIARIZE_ENABLED`       | `false`                 | `POST /api/diarize` aktivieren (erfordert ein `DIARIZE=true`-Image) |
| `DIARIZE_MODEL`         | `nvidia/Nemotron-3-Diarization` | ID des Diarisierungsmodells                         |
| `DIARIZE_POOL_SIZE`     | `1`                     | Anzahl vorab geladener Diarisierungs-Instanzen      |
| `DIARIZE_DOWNLOAD_ROOT` | `models`                | Verzeichnis des Diarisierungsmodell-Caches          |
| `DIARIZE_THRESHOLD`     | `0.5`                   | Sprecheraktivitäts-Wahrscheinlichkeit, die als Sprache zählt |
| `STT_URL`               | `http://localhost:5099` | Client: Basis-URL des Servers                       |
| `STT_TOKEN`             | (empty)                 | Client: an den Server gesendetes Bearer-Token       |

### Projektstruktur

```text
speech-to-text/
├── stt_server.py        # Flask-App-Verdrahtung, Routen, Einstiegspunkt
├── stt_client.py        # CLI-Client, der Dateien an den Server sendet
├── gu.py                # Gunicorn-Konfiguration und Hooks
├── libs/
│   ├── config.py        # alle Umgebungsvariablen, einmalig gelesen
│   ├── logs.py          # Logging-Format für App, uvicorn und die CLIs
│   ├── errors.py        # einheitliche JSON-Fehlerantworten und Flask-Error-Handler
│   ├── auth.py          # optionale Authentifizierung per statischem Token
│   ├── audio.py         # Upload -> Konvertierung nach 16 kHz Mono-WAV
│   ├── model_pool.py    # Pools vorgeladener Whisper- und Diarisierungs-Instanzen
│   ├── catalog.py       # was dieser Server kann, für GET /api/models
│   ├── align.py         # verbindet Transkriptionssegmente mit Sprechbeiträgen
│   ├── stt.py           # Whisper-Wrapper
│   ├── parakeet.py      # NVIDIA-Parakeet-Wrapper, der zweite Transkribierer
│   ├── backends.py      # welches Modul transkribiert, je nach STT_BACKEND
│   └── diarize.py       # Sprecherdiarisierung (wer wann gesprochen hat, kein Text)
├── Dockerfile           # GPU-Build (CUDA 13.0)
├── Dockerfile-cpu       # CPU-Build
├── docs/                # README-Übersetzungen
└── tests/               # pytest-Tests, keine Modell-Downloads und keine GPU
```

### Entwicklung

Die Systempakete `ffmpeg` und `libsndfile1` müssen vorhanden sein. Installieren Sie die Laufzeit- und Entwicklungsabhängigkeiten:

```bash
pip install -e ".[dev]"
pre-commit install
```

Das Makefile fasst die gängigen Aufgaben zusammen:

```bash
make run            # foreground: python3 stt_server.py
make start          # background: PID -> .stt_server.pid, logs -> logs/stt_server.log
make stop           # stop the background server
make gunicorn       # run via gunicorn
make test           # pytest
make lint           # pre-commit (black + ruff)
make typecheck      # mypy
```

Die Testsuite ersetzt das Whisper-Backend durch einen Stub, deckt also die HTTP-Schicht ab (request_id, Fehlerkategorien, Semantik des Modell-Pools) und läuft in Sekunden, ohne ein Modell herunterzuladen oder eine GPU zu benötigen.

### Lizenz

[MIT](../LICENSE)
