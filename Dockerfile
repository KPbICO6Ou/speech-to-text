# GPU image based on CUDA 13.0 + cuDNN.
FROM nvidia/cuda:13.0.3-cudnn-runtime-ubuntu24.04

# ffmpeg is required by pydub; libsndfile1 is required by soundfile.
# libcublas-13-0 provides cuBLAS / cuBLASLt runtime that torch 2.10+cu130
# calls into (cublasLtMatmul*). The `-runtime` base image does not include
# it by default - without this package the first matmul on CUDA fails with
# `CUBLAS_STATUS_NOT_INITIALIZED`.
RUN apt-get update && apt-get install -y --no-install-recommends \
        python3 \
        python3-venv \
        ffmpeg \
        build-essential \
        libsndfile1 \
        libcublas-13-0 \
    && rm -rf /var/lib/apt/lists/*

# uv: fast Python package installer (https://github.com/astral-sh/uv).
COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /usr/local/bin/

WORKDIR /opt

ENV PATH="/opt/venv/bin:${PATH}"
ENV UV_LINK_MODE=copy

RUN uv venv /opt/venv --python python3

COPY requirements.txt /opt/requirements.txt
# Install GPU-accelerated PyTorch and other dependencies via uv.
RUN uv pip install --no-cache \
        --extra-index-url https://download.pytorch.org/whl/cu130 \
        torch==2.10.0+cu130 torchaudio==2.10.0+cu130 \
 && uv pip install --no-cache -r requirements.txt

# Speaker diarization is opt-in at build time: `--build-arg DIARIZE=true`. Off, the image is
# what it was before diarization existed.
ARG DIARIZE=false
COPY requirements-diarize.txt /opt/requirements-diarize.txt
# git is here only because the transformers pin is a git+https ref: uv shells out to the git
# binary and does not vendor one, and this base image has none. It is purged in the same layer
# so it never reaches the running image, and it can go entirely once the pin is a version.
RUN if [ "$DIARIZE" = "true" ]; then \
        apt-get update \
     && apt-get install -y --no-install-recommends git \
     && uv pip install --no-cache -r requirements-diarize.txt \
     && apt-get purge -y git && apt-get autoremove -y \
     && rm -rf /var/lib/apt/lists/*; \
    fi

# Parakeet is opt-in at build time too, and needs no git: it ships in released transformers.
ARG PARAKEET=false
COPY requirements-parakeet.txt /opt/requirements-parakeet.txt
RUN if [ "$PARAKEET" = "true" ]; then uv pip install --no-cache -r requirements-parakeet.txt; fi

# The torch wheel above is a CUDA build chosen on purpose, and the resolutions that follow it
# are unconstrained: anything depending on torch can replace it, and the failure surfaces much
# later as cuBLAS and cuDNN errors that read like a driver problem. Fail the build instead.
RUN python3 -c "import torch; v = torch.__version__; assert '+cu130' in v, f'torch was replaced by {v}'"
RUN if [ "$DIARIZE" = "true" ]; then \
        python3 -c "from transformers.models.auto.configuration_auto import CONFIG_MAPPING_NAMES; \
assert 'nemotron3_diarization' in CONFIG_MAPPING_NAMES, 'this transformers build does not carry the diarization model'"; \
    fi
RUN if [ "$PARAKEET" = "true" ]; then \
        python3 -c "from transformers import AutoModelForTDT; import transformers; \
assert 'parakeet_tdt' in transformers.models.auto.configuration_auto.CONFIG_MAPPING_NAMES, \
'this transformers build does not carry the parakeet model'"; \
    fi

# The stt user is created with --no-create-home and only the bind-mounted dirs are chowned,
# so anything HuggingFace writes outside them fails. cache_dir covers the snapshot; HF_HOME
# covers the rest, including the Xet chunk cache.
ENV HF_HOME=/opt/models/hf

COPY stt_server.py stt_client.py gu.py /opt/
COPY libs /opt/libs
RUN mkdir -p /opt/models /opt/logs /opt/recs

RUN useradd --no-create-home --shell /bin/false stt
RUN chown -R stt:stt /opt

# Start as root: the entrypoint chowns the bind-mounted dirs (the build-time
# chown above cannot reach host-owned mounts) and drops privileges to stt.
COPY entrypoint.sh /opt/entrypoint.sh
RUN chmod +x /opt/entrypoint.sh
ENTRYPOINT ["/opt/entrypoint.sh"]

EXPOSE 5099
CMD ["python3", "stt_server.py"]
