## speech-to-text: un servidor de transcripción Whisper autoalojado

[![CI](https://github.com/wachawo/speech-to-text/actions/workflows/ci.yml/badge.svg)](https://github.com/wachawo/speech-to-text/actions/workflows/ci.yml)
[![License](https://img.shields.io/badge/license-MIT-blue.svg)](https://github.com/wachawo/speech-to-text/blob/main/LICENSE)
[![Python](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org/)

[English](https://github.com/wachawo/speech-to-text/blob/main/README.md) | **[Español](https://github.com/wachawo/speech-to-text/blob/main/docs/README_ES.md)** | [Português](https://github.com/wachawo/speech-to-text/blob/main/docs/README_PT.md) | [Français](https://github.com/wachawo/speech-to-text/blob/main/docs/README_FR.md) | [Deutsch](https://github.com/wachawo/speech-to-text/blob/main/docs/README_DE.md) | [Italiano](https://github.com/wachawo/speech-to-text/blob/main/docs/README_IT.md) | [Русский](https://github.com/wachawo/speech-to-text/blob/main/docs/README_RU.md) | [中文](https://github.com/wachawo/speech-to-text/blob/main/docs/README_ZH.md) | [日本語](https://github.com/wachawo/speech-to-text/blob/main/docs/README_JA.md) | [हिन्दी](https://github.com/wachawo/speech-to-text/blob/main/docs/README_HI.md) | [한국어](https://github.com/wachawo/speech-to-text/blob/main/docs/README_KR.md)

`speech-to-text` convierte audio en texto con [openai-whisper](https://github.com/openai/whisper), envuelto en un pequeño servicio HTTP que tú mismo ejecutas. Envías un archivo de audio y recibes la transcripción de vuelta. Sin API externa, sin facturación por minuto, y tu audio nunca sale de tu máquina.

El proyecto encaja para uso local, transcripción por lotes y para ejecutar tu propio servidor STT en la red.

* **Un servidor HTTP listo para usar.** Flask servido por uvicorn carga Whisper al arrancar y responde a las solicitudes de otras máquinas en tu red local.
* **Seguro bajo concurrencia.** El servidor mantiene un grupo de instancias de Whisper precargadas, de modo que varias solicitudes se transcriben en paralelo sin recargar el modelo.
* **CPU o GPU, el mismo código.** El backend se selecciona según el entorno y según qué imagen de Docker compiles. Una tarjeta CUDA acelera la inferencia, pero todo funciona también en CPU.
* **Se incluye un cliente CLI.** `stt_client.py` envía archivos locales al servidor e imprime el resultado.

### Modelos

Whisper ofrece varios tamaños de modelo. Los modelos más grandes son más precisos y lentos; los más pequeños son rápidos y ligeros.

| Modelo     | Parámetros | VRAM    | Idiomas         | Recomendado para                              |
| ---------- | ---------- | ------- | --------------- | --------------------------------------------- |
| `tiny`     | 39M        | ~1 GB   | multilingüe     | borradores rápidos en hardware modesto        |
| `base`     | 74M        | ~1 GB   | multilingüe     | un valor por defecto ligero y general         |
| `small`    | 244M       | ~2 GB   | multilingüe     | un buen equilibrio entre precisión y velocidad|
| `medium`   | 769M       | ~5 GB   | multilingüe     | mayor precisión cuando puedes ceder memoria   |
| `turbo`    | 809M       | ~6 GB   | multilingüe     | precisión cercana a `large`, mucho más rápido |
| `large`    | 1550M      | ~10 GB  | multilingüe     | mejor calidad, necesita una GPU               |

Las variantes solo para inglés (`tiny.en`, `base.en`, `small.en`, `medium.en`) son algo más precisas con audio en inglés. El valor por defecto es `turbo`, que es la mejor opción global para inglés en una GPU.

### Inicio rápido (Docker)

La forma más fácil de ejecutar el servidor es con Docker. Los archivos del modelo se almacenan en caché en `./models` en el host, de modo que sobreviven a las recompilaciones del contenedor.

```bash
git clone https://github.com/wachawo/speech-to-text.git
cd speech-to-text

docker compose up --build                              # GPU (CUDA 13.0)
docker compose -f docker-compose-cpu.yml up --build    # CPU only
```

La compilación para GPU necesita `nvidia-container-toolkit` en el host. La primera ejecución descarga el modelo Whisper en `./models`.

### API HTTP

Una vez que el servidor esté en marcha, comprueba su estado y envía un archivo de audio para transcribir.

```bash
curl localhost:5099/api/health

curl -X POST localhost:5099/api/stt \
  -F file=@speech.mp3

curl -X POST 'localhost:5099/api/stt?language=ru' \
  -H 'Content-Type: audio/wav' \
  --data-binary @speech.wav
```

`GET /api/health` devuelve el estado del grupo. Que `available` baje a 0 significa que todos los modelos están actualmente en uso:

```json
{ "status": "ok", "pool_size": 4, "available": 3, "diarize": false }
```

`POST /api/stt` acepta un campo `multipart/form-data` llamado `file`, o un cuerpo en bruto `audio/*`. Un parámetro opcional `language` (en la cadena de consulta o como campo del formulario) anula el valor por defecto del servidor para esa solicitud; `auto` detecta automáticamente. En caso de éxito devuelve el texto y los segundos transcurridos:

```json
{ "text": "transcribed text", "elapsed": 1.23 }
```

El idioma puede indicarse como código (`ru`) o con su nombre en inglés (`russian`); cualquier valor que el modelo desconozca se rechaza con `400` en lugar de fallar a mitad de una transcripción. `GET /api/models` enumera los que conoce.

`GET /api/models` informa de lo que lleva este servidor, para que un cliente no tenga que adivinarlo. Cada backend aporta su propia lista de idiomas, porque los conjuntos divergen de verdad y una lista fusionada sería incorrecta para cada backend por separado.

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

`status` es `loaded` cuando hay una instancia esperando en un grupo, `installed` cuando los pesos están en disco pero todavía no se ha cargado nada, y `absent` en el resto de los casos. Un backend configurado pero no instalado responde `absent` y nada más; el motivo va al registro. `accepts_language` indica si `?language=` significa algo en absoluto para ese backend. El diarizador informa de idiomas `null` en lugar de una lista vacía, porque no produce texto en ningún idioma.

El cliente CLI lee el mismo endpoint:

```bash
python3 stt_client.py --list
```

`POST /api/diarize` responde **quién habló y cuándo**, y nada más: devuelve intervalos de tiempo con un número de hablante, nunca texto. Está desactivado salvo que `DIARIZE_ENABLED` esté configurado en una imagen compilada con `DIARIZE=true`; en caso contrario responde `503`.

```bash
curl -X POST localhost:5099/api/diarize -F file=@meeting.wav
```

```json
{ "segments": [ { "speaker": 0, "start": 0.51, "end": 12.62 },
                { "speaker": 1, "start": 12.20, "end": 19.04 } ], "speakers": 2, "elapsed": 1.23 }
```

Dos cosas sobre esos números. Los turnos pueden solaparse, porque cada canal de hablante se evalúa por separado, de modo que dos personas hablando a la vez producen dos turnos que cubren los mismos segundos. Y las etiquetas son posiciones dentro de esta única grabación, ordenadas según quién habló primero: no son identidades, y la misma persona recibe un número distinto en la siguiente solicitud. Poner nombre a un hablante requiere un paso de registro previo que este servicio no tiene. Se distinguen como máximo ocho hablantes.

Hay dos backends de transcripción disponibles. **Whisper** es el que viene por defecto y acepta un `language`. **Parakeet** (`nvidia/parakeet-tdt-0.6b-v3`) cubre 25 idiomas europeos, detecta el idioma por sí mismo y por tanto no admite ningún argumento `language`, lo que `GET /api/models` informa como `accepts_language: false`. Se selecciona con `STT_BACKEND=parakeet` en una imagen compilada con `PARAKEET=true`; es una elección de despliegue, no de cada solicitud, porque un segundo modelo residente significaría un segundo juego de pesos en cada proceso de trabajo.

Ninguno de los dos backends maneja el habla solapada. El modelo de NVIDIA que sí la maneja se distribuye únicamente como un checkpoint de NeMo, y NeMo fija una versión de PyTorch distinta de la que usa la compilación CUDA de este proyecto, así que aquí no se puede instalar.

`POST /api/transcript` responde **quién dijo qué**: ejecuta la diarización y la transcripción sobre el mismo audio y las une por tiempo. Necesita que la diarización esté activada; en caso contrario responde `503`.

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

`turns` es la salida en bruto del diarizador y `segments` es la unión, mantenidos aparte para que quien desconfíe de la atribución pueda ver igualmente lo que dijo el diarizador. `text` es la transcripción simple, idéntica a la que devuelve `/api/stt` para el mismo archivo. Una frase que ningún turno cubre conserva `"speaker": null` en lugar de entregarse al turno más cercano.

`overlap` marca una frase durante la cual alguien más estaba hablando también. NVIDIA es explícita en que combinar un modelo convencional de un solo hablante con la diarización no equivale a un modelo construido para habla solapada: un intervalo de tiempo extraído sigue conteniendo todas las voces que se solapan con él, de modo que esas frases pueden fusionarse o seleccionar las palabras del hablante equivocado. Trata un segmento marcado con `overlap` como el lugar donde la transcripción es menos fiable.

Las subidas están limitadas a `MAX_CONTENT_LENGTH_MB` (10 MB por defecto); un cuerpo mayor devuelve `413`.

Los errores son uniformes: `error` lleva una categoría genérica y `request_id` correlaciona la respuesta con el registro del servidor, donde se anota la excepción completa.

```json
{ "error": "Invalid audio data", "request_id": "a1b2c3d4e5f6" }
```

Cuando `STT_TOKENS` está configurado, cada ruta debe llevar `Authorization: Bearer <token>`, excepto `GET /api/health`, que permanece abierto para que los healthchecks sigan funcionando.

### Cliente CLI

`stt_client.py` es un pequeño cliente para trabajar con el servidor y probarlo. Lee la dirección del servidor y el token de `STT_URL` y `STT_TOKEN`.

```bash
python3 stt_client.py speech.mp3
python3 stt_client.py file1.wav file2.mp3 file3.ogg
```

### Variables de entorno

`.env` es cargado tanto por el servidor como por el cliente mediante `python-dotenv`.

| Variable                | Por defecto             | Propósito                                          |
| ----------------------- | ----------------------- | -------------------------------------------------- |
| `STT_HOST`              | `0.0.0.0`               | dirección de escucha del servidor                  |
| `STT_PORT`              | `5099`                  | puerto del servidor                                |
| `STT_POOL_SIZE`         | `8`                     | número de instancias de Whisper precargadas        |
| `STT_TOKENS`            | (vacío)                 | tokens válidos separados por comas; vacío desactiva la autenticación |
| `STT_DEBUG`             | `false`                 | modo de depuración de Flask                        |
| `MAX_CONTENT_LENGTH_MB` | `10`                    | tamaño máximo de subida en MB; un cuerpo mayor devuelve `413` |
| `CORS_ORIGINS`          | `*`                     | orígenes CORS permitidos: `*` o una lista separada por comas |
| `GUNICORN_WORKERS`      | `4`                     | procesos de trabajo (solo gunicorn)                |
| `LOG_LEVEL`             | `INFO`                  | nivel de registro                                  |
| `LOG_ACCESS`            | `false`                 | registrar las líneas de acceso de uvicorn          |
| `WHISPER_MODEL`         | `turbo`                 | nombre del modelo Whisper (p. ej. `small.en`, `turbo`) |
| `WHISPER_LANGUAGE`      | `en`                    | idioma de transcripción por defecto                |
| `WHISPER_DOWNLOAD_ROOT` | `models`                | directorio de caché del modelo (`/opt/models` en Docker) |
| `COMPUTE_TYPE`          | `auto`                  | `cpu`, `cuda` o `auto`                             |
| `STT_BACKEND`           | `whisper`               | backend de transcripción: `whisper` o `parakeet`   |
| `PARAKEET_MODEL`        | `nvidia/parakeet-tdt-0.6b-v3` | identificador del modelo Parakeet                  |
| `PARAKEET_DOWNLOAD_ROOT` | `models`                | directorio de caché del modelo Parakeet            |
| `DIARIZE_ENABLED`       | `false`                 | activar `POST /api/diarize` (requiere una imagen `DIARIZE=true`) |
| `DIARIZE_MODEL`         | `nvidia/Nemotron-3-Diarization` | identificador del modelo de diarización            |
| `DIARIZE_POOL_SIZE`     | `1`                     | instancias de diarizador precargadas               |
| `DIARIZE_DOWNLOAD_ROOT` | `models`                | directorio de caché del modelo de diarización      |
| `DIARIZE_THRESHOLD`     | `0.5`                   | probabilidad de actividad del hablante contada como habla |
| `STT_URL`               | `http://localhost:5099` | cliente: URL base del servidor                     |
| `STT_TOKEN`             | (vacío)                 | cliente: token bearer enviado al servidor          |

### Estructura del proyecto

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

### Desarrollo

Los paquetes del sistema `ffmpeg` y `libsndfile1` deben estar presentes. Instala las dependencias de ejecución y de desarrollo:

```bash
pip install -e ".[dev]"
pre-commit install
```

El Makefile envuelve las tareas comunes:

```bash
make run            # foreground: python3 stt_server.py
make start          # background: PID -> .stt_server.pid, logs -> logs/stt_server.log
make stop           # stop the background server
make gunicorn       # run via gunicorn
make test           # pytest
make lint           # pre-commit (black + ruff)
make typecheck      # mypy
```

La suite de pruebas sustituye el backend de Whisper, de modo que cubre la capa HTTP (request_id, categorías de error, semántica del grupo de modelos) y se ejecuta en segundos sin descargar un modelo ni necesitar una GPU.

### Licencia

[MIT](../LICENSE)
