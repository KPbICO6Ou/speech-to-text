## speech-to-text: 自托管的 Whisper 转录服务器

[![CI](https://github.com/wachawo/speech-to-text/actions/workflows/ci.yml/badge.svg)](https://github.com/wachawo/speech-to-text/actions/workflows/ci.yml)
[![License](https://img.shields.io/badge/license-MIT-blue.svg)](https://github.com/wachawo/speech-to-text/blob/main/LICENSE)
[![Python](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org/)

[English](https://github.com/wachawo/speech-to-text/blob/main/README.md) | [Español](https://github.com/wachawo/speech-to-text/blob/main/docs/README_ES.md) | [Português](https://github.com/wachawo/speech-to-text/blob/main/docs/README_PT.md) | [Français](https://github.com/wachawo/speech-to-text/blob/main/docs/README_FR.md) | [Deutsch](https://github.com/wachawo/speech-to-text/blob/main/docs/README_DE.md) | [Italiano](https://github.com/wachawo/speech-to-text/blob/main/docs/README_IT.md) | [Русский](https://github.com/wachawo/speech-to-text/blob/main/docs/README_RU.md) | **[中文](https://github.com/wachawo/speech-to-text/blob/main/docs/README_ZH.md)** | [日本語](https://github.com/wachawo/speech-to-text/blob/main/docs/README_JA.md) | [हिन्दी](https://github.com/wachawo/speech-to-text/blob/main/docs/README_HI.md) | [한국어](https://github.com/wachawo/speech-to-text/blob/main/docs/README_KR.md)

`speech-to-text` 使用 [openai-whisper](https://github.com/openai/whisper) 将音频转换为文本，并封装在一个由你自己运行的小型 HTTP 服务中。你发送一个音频文件，就能得到转录结果。没有外部 API，没有按分钟计费，你的音频也绝不会离开你的机器。

本项目适用于本地使用、批量转录，以及在网络上运行你自己的 STT 服务器。

* **开箱即用的 HTTP 服务器。** 由 uvicorn 提供服务的 Flask 在启动时加载 Whisper，并响应本地网络中其他机器的请求。
* **并发安全。** 服务器维护一个预加载的 Whisper 实例池，因此可以并行转录多个请求而无需重新加载模型。
* **CPU 或 GPU，代码相同。** 后端由环境以及你构建的 Docker 镜像决定。CUDA 显卡能加速推理，但一切也都能在 CPU 上运行。
* **附带命令行客户端。** `stt_client.py` 将本地文件提交到服务器并打印结果。

### 模型

Whisper 提供多种模型尺寸。更大的模型更准确但更慢；更小的模型快速且轻量。

| 模型       | 参数量     | 显存    | 语言            | 适用场景                                      |
| ---------- | ---------- | ------- | --------------- | --------------------------------------------- |
| `tiny`     | 39M        | ~1 GB   | 多语言          | 弱硬件上的快速草稿                            |
| `base`     | 74M        | ~1 GB   | 多语言          | 轻量的通用默认选项                            |
| `small`    | 244M       | ~2 GB   | 多语言          | 准确度与速度的良好平衡                        |
| `medium`   | 769M       | ~5 GB   | 多语言          | 在内存允许时获得更高准确度                    |
| `turbo`    | 809M       | ~6 GB   | 多语言          | 接近 `large` 的准确度，速度快得多             |
| `large`    | 1550M      | ~10 GB  | 多语言          | 最佳质量，需要 GPU                            |

仅英语的变体（`tiny.en`、`base.en`、`small.en`、`medium.en`）在英语音频上略微更准确。默认值是 `turbo`，它是 GPU 上英语转录的最佳综合选择。

### 快速开始（Docker）

运行服务器最简单的方式是使用 Docker。模型文件缓存在主机的 `./models` 中，因此在容器重建后仍会保留。

```bash
git clone https://github.com/wachawo/speech-to-text.git
cd speech-to-text

docker compose up --build                              # GPU (CUDA 13.0)
docker compose -f docker-compose-cpu.yml up --build    # CPU only
```

GPU 构建需要主机上安装 `nvidia-container-toolkit`。首次运行会将 Whisper 模型下载到 `./models`。

### HTTP API

服务器启动后，检查其状态并发送音频文件进行转录。

```bash
curl localhost:5099/api/health

curl -X POST localhost:5099/api/stt \
  -F file=@speech.mp3

curl -X POST 'localhost:5099/api/stt?language=ru' \
  -H 'Content-Type: audio/wav' \
  --data-binary @speech.wav
```

`GET /api/health` 返回池状态。`available` 降为 0 意味着每个模型当前都在使用中：

```json
{ "status": "ok", "pool_size": 4, "available": 3, "diarize": false }
```

`POST /api/stt` 接受名为 `file` 的 `multipart/form-data` 字段，或一个原始的 `audio/*` 请求体。可选的 `language`（查询字符串或表单字段）会针对该请求覆盖服务器默认值；`auto` 表示自动检测。成功时返回文本和耗费的秒数：

```json
{ "text": "transcribed text", "elapsed": 1.23 }
```

语言可以用代码（`ru`）或其英文名称（`russian`）给出；模型不认识的值会以 `400` 拒绝，而不是在转写中途失败。`GET /api/models` 会列出它认识的语言。

`GET /api/models` 会报告本服务器所具备的能力，因此客户端无需猜测。每个后端都带有自己的语言列表，因为这些集合确实存在差异，而一个合并后的列表对任何单独的后端来说都是错误的。

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

当有实例在池中等待时，`status` 为 `loaded`；当权重已在磁盘上但尚未加载任何实例时为 `installed`；其余情况为 `absent`。已配置但未安装的后端只会返回 `absent`，不作其他说明；原因记录在日志中。`accepts_language` 说明 `?language=` 对该后端是否有任何意义。说话人分离器报告的 `languages` 为 `null` 而非空列表，因为它不产生任何语言的文本。

命令行客户端读取的是同一个接口：

```bash
python3 stt_client.py --list
```

`POST /api/diarize` 回答的是**谁在什么时候说话**，仅此而已：它返回带说话人编号的时间区间，而绝不返回文本。除非在以 `DIARIZE=true` 构建的镜像上设置了 `DIARIZE_ENABLED`，否则该接口处于关闭状态，并返回 `503`。

```bash
curl -X POST localhost:5099/api/diarize -F file=@meeting.wav
```

```json
{ "segments": [ { "speaker": 0, "start": 0.51, "end": 12.62 },
                { "speaker": 1, "start": 12.20, "end": 19.04 } ], "speakers": 2, "elapsed": 1.23 }
```

关于这些数字有两点说明。时间区间可能重叠，因为每个说话人通道都是单独评分的，所以两个人同时说话会产生覆盖相同秒数的两个区间。而这些编号只是这一次录音中的位置，按谁先开口排序：它们不是身份标识，同一个人在下一次请求中会得到不同的编号。要给说话人命名，需要一个本服务所不具备的声纹注册步骤。最多可区分八个说话人。

`POST /api/transcript` 回答的是**谁说了什么**：它对同一段音频同时运行说话人分离和转录，并按时间将二者连接起来。它需要启用说话人分离，否则返回 `503`。

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

`turns` 是说话人分离器的原始输出，`segments` 是二者连接后的结果，它们被分开保留，以便不信任这种归属的调用方仍能看到说话人分离器给出的结论。`text` 是纯转录文本，与 `/api/stt` 对同一文件返回的内容完全相同。没有任何一个 turn 覆盖到的语句会保持 `"speaker": null`，而不会被交给最接近的那一个。

`overlap` 标记的是在该语句期间还有其他人同时在说话。NVIDIA 明确指出，将传统的单说话人模型与说话人分离配合使用，并不等同于一个为重叠语音而构建的模型：被截取出来的时间区间里仍然包含所有与之重叠的声音，因此这些语句可能会混在一起，或者选中错误说话人的话语。把标记了 `overlap` 的片段视为转录结果最不可信的地方。

上传大小上限为 `MAX_CONTENT_LENGTH_MB`（默认 10 MB）；更大的请求体返回 `413`。

错误格式统一：`error` 携带一个通用类别，`request_id` 将响应与服务器日志关联起来，完整的异常信息记录在日志中。

```json
{ "error": "Invalid audio data", "request_id": "a1b2c3d4e5f6" }
```

当设置了 `STT_TOKENS` 时，除 `GET /api/health` 之外的每个路由都必须携带 `Authorization: Bearer <token>`；该接口保持开放，以便健康检查能正常工作。

### 命令行客户端

`stt_client.py` 是一个用于操作和测试服务器的小型客户端。它从 `STT_URL` 和 `STT_TOKEN` 读取服务器地址和令牌。

```bash
python3 stt_client.py speech.mp3
python3 stt_client.py file1.wav file2.mp3 file3.ogg
```

### 环境变量

`.env` 由服务器和客户端通过 `python-dotenv` 共同加载。

| 变量                    | 默认值                  | 用途                                               |
| ----------------------- | ----------------------- | -------------------------------------------------- |
| `STT_HOST`              | `0.0.0.0`               | 服务器绑定地址                                     |
| `STT_PORT`              | `5099`                  | 服务器端口                                         |
| `STT_POOL_SIZE`         | `8`                     | 预加载的 Whisper 实例数量                          |
| `STT_TOKENS`            | （空）                  | 逗号分隔的有效令牌；为空则禁用鉴权                 |
| `STT_DEBUG`             | `false`                 | Flask 调试模式                                     |
| `MAX_CONTENT_LENGTH_MB` | `10`                    | 最大上传大小（MB）；更大的请求体返回 `413`         |
| `CORS_ORIGINS`          | `*`                     | 允许的 CORS 来源：`*` 或逗号分隔的列表             |
| `GUNICORN_WORKERS`      | `4`                     | 工作进程数量（仅 gunicorn）                        |
| `LOG_LEVEL`             | `INFO`                  | 日志级别                                           |
| `LOG_ACCESS`            | `false`                 | 记录 uvicorn 访问日志行                            |
| `WHISPER_MODEL`         | `turbo`                 | Whisper 模型名称（例如 `small.en`、`turbo`）       |
| `WHISPER_LANGUAGE`      | `en`                    | 默认转录语言                                       |
| `WHISPER_DOWNLOAD_ROOT` | `models`                | 模型缓存目录（Docker 中为 `/opt/models`）          |
| `COMPUTE_TYPE`          | `auto`                  | `cpu`、`cuda` 或 `auto`                            |
| `DIARIZE_ENABLED`       | `false`                 | 启用 `POST /api/diarize`（需 `DIARIZE=true` 镜像） |
| `DIARIZE_MODEL`         | `nvidia/Nemotron-3-Diarization` | 说话人分离模型 id                                  |
| `DIARIZE_POOL_SIZE`     | `1`                     | 预加载的说话人分离实例数量                         |
| `DIARIZE_DOWNLOAD_ROOT` | `models`                | 说话人分离模型缓存目录                             |
| `DIARIZE_THRESHOLD`     | `0.5`                   | 判定为语音的说话人活动概率                         |
| `STT_URL`               | `http://localhost:5099` | 客户端：服务器基础 URL                             |
| `STT_TOKEN`             | （空）                  | 客户端：发送给服务器的 bearer 令牌                 |

### 项目结构

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
│   └── diarize.py       # speaker diarization (who spoke when, no text)
├── Dockerfile           # GPU build (CUDA 13.0)
├── Dockerfile-cpu       # CPU build
├── docs/                # README translations
└── tests/               # pytest tests, no model downloads and no GPU
```

### 开发

系统软件包 `ffmpeg` 和 `libsndfile1` 必须存在。安装运行时和开发依赖：

```bash
pip install -e ".[dev]"
pre-commit install
```

Makefile 封装了常见任务：

```bash
make run            # foreground: python3 stt_server.py
make start          # background: PID -> .stt_server.pid, logs -> logs/stt_server.log
make stop           # stop the background server
make gunicorn       # run via gunicorn
make test           # pytest
make lint           # pre-commit (black + ruff)
make typecheck      # mypy
```

测试套件对 Whisper 后端进行了打桩，因此它覆盖了 HTTP 层（request_id、错误类别、模型池语义），并能在数秒内运行完成，无需下载模型或使用 GPU。

### 许可证

[MIT](../LICENSE)
