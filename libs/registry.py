#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Which transcription models this server loads, and what a request may select among them."""

import logging
import os
from typing import Any

# Local imports
from libs import backends, config

logger = logging.getLogger(__name__)

# The value that asks the backend to detect the language rather than be told it.
AUTODETECT = "auto"

# Error categories a request's `model` or `language` can earn; each one is a 400.
INVALID_MODEL = "Invalid model"
MODEL_NOT_LOADED = "Model not loaded"
INVALID_LANGUAGE = "Invalid language"
UNSUPPORTED_LANGUAGE = "Unsupported language"


def build_model_id(model: str) -> str:
    """The public name of a model: the value itself, or for a file path its basename without `.pt`.

    A path is where the weights live on this host, which is not the client's business: the id
    reaches the open /api/health, the catalogue and every /api/stt response.
    """
    if not config.is_model_path(model):
        return model
    basename = os.path.basename(model.rstrip("/"))
    if basename.endswith(config.MODEL_PATH_SUFFIX):
        basename = basename[: -len(config.MODEL_PATH_SUFFIX)]
    return basename or model


def build_legacy_spec() -> dict[str, Any]:
    """The single spec implied by STT_BACKEND / WHISPER_MODEL / PARAKEET_MODEL / STT_POOL_SIZE.

    Computed on every call, so a changed STT_BACKEND is obeyed rather than cached.
    """
    backend = backends.transcriber_name()
    model = config.PARAKEET_MODEL if backend == "parakeet" else config.WHISPER_MODEL
    return {"id": build_model_id(model), "backend": backend, "model": model, "pool_size": config.MODEL_POOL_SIZE}


def build_model_spec(entry: dict[str, Any]) -> dict[str, Any]:
    """Turn one parsed STT_MODELS entry into a spec, filling pool_size from STT_POOL_SIZE when absent."""
    pool_size = config.MODEL_POOL_SIZE if entry["pool_size"] is None else entry["pool_size"]
    return {"id": build_model_id(entry["model"]), "backend": entry["backend"], "model": entry["model"], "pool_size": pool_size}


def get_model_specs() -> list[dict[str, Any]]:
    """Every model this deployment loads, in STT_MODELS order, or the one legacy spec."""
    if not config.STT_MODELS:
        return [build_legacy_spec()]
    return [build_model_spec(entry) for entry in config.STT_MODELS]


def get_default_spec() -> dict[str, Any]:
    """The spec a request without `model` uses: STT_DEFAULT_MODEL when set, else the first spec."""
    specs = get_model_specs()
    if config.STT_MODELS and config.STT_DEFAULT_MODEL:
        spec = find_spec(config.STT_DEFAULT_MODEL, specs)
        if spec is not None:
            return spec
    return specs[0]


def get_default_model_id() -> str:
    """The canonical id of the default model."""
    return get_default_spec()["id"]


def list_spec_names(spec: dict[str, Any]) -> list[str]:
    """Every lower-cased name that selects this spec: id, backend aliases and the backend:model form.

    The bare backend name is not among them: several specs share it, and which one it selects
    is decided by find_spec and resolve_request_model rather than counted as a clash.
    """
    backend = spec["backend"]
    names = [spec["id"]]
    if not config.is_model_path(spec["model"]):
        names.extend(backends.transcriber_for_backend(backend).list_aliases(spec["model"]))
    names.extend([f"{backend}:{name}" for name in list(names)])
    return list(dict.fromkeys(name.lower() for name in names))


def find_spec(name: str, specs: list[dict[str, Any]]) -> dict[str, Any] | None:
    """The spec a requested name selects, case-insensitively, or None.

    A bare backend name selects the first spec of that backend in STT_MODELS order; preferring
    the default model is resolve_request_model's job, which keeps STT_DEFAULT_MODEL=whisper
    from resolving through itself.
    """
    wanted = name.strip().lower()
    for spec in specs:
        if wanted in list_spec_names(spec):
            return spec
    for spec in specs:
        if spec["backend"] == wanted:
            return spec
    return None


def list_known_names() -> set[str]:
    """Every lower-cased name any backend could describe, loaded or not, in every accepted form."""
    names: set[str] = set()
    for backend, module in backends.TRANSCRIBERS.items():
        models = set(module.list_known_models())
        models.add(config.PARAKEET_MODEL if backend == "parakeet" else config.WHISPER_MODEL)
        for model in models:
            for name in [model, *module.list_aliases(model)]:
                names.update((name.lower(), f"{backend}:{name}".lower()))
        names.add(backend)
    return names


def is_known_model(name: str) -> bool:
    """Whether a name is a model some installed backend could describe, loaded or not."""
    return name.strip().lower() in list_known_names()


def resolve_request_model(requested: str | None) -> tuple[dict[str, Any] | None, str | None]:
    """Map the request's `model` onto a loaded spec; returns (spec, None) or (None, error category).

    Nothing is ever loaded lazily: a name that is real but not loaded here is refused.
    """
    default = get_default_spec()
    if requested is None or not requested.strip():
        return default, None
    wanted = requested.strip().lower()
    if wanted == default["backend"]:
        return default, None
    spec = find_spec(wanted, get_model_specs())
    if spec is not None:
        return spec, None
    return None, MODEL_NOT_LOADED if is_known_model(wanted) else INVALID_MODEL


def resolve_self_detected_language(language: str, spec: dict[str, Any], explicit: bool) -> tuple[str | None, str | None]:
    """Check a hint for a backend that detects the language itself and takes no language argument.

    A caller that did not choose a model gets today's behaviour: the value is accepted and
    ignored, whatever it is. One that did choose read the catalogue, so a code outside that
    model's list is refused; an id the table does not cover accepts anything.
    """
    if not explicit:
        return language, None
    languages = backends.transcriber_for_backend(spec["backend"]).resolve_languages(spec["model"])
    if languages is None or language in languages:
        return language, None
    return None, UNSUPPORTED_LANGUAGE


def resolve_language(language: str | None, spec: dict[str, Any], explicit: bool) -> tuple[str | None, str | None]:
    """Validate a requested language against the chosen model; returns (value to pass on, error category).

    `explicit` is whether the request named its model. A shape check cannot do this job in
    either direction: `zz` looks like a code and is not one, and `russian` is not a code but is
    a spelling Whisper accepts.
    """
    if language is None:
        return None, None
    if language == AUTODETECT:
        return AUTODETECT, None
    module = backends.transcriber_for_backend(spec["backend"])
    if not hasattr(module, "normalize_language_code"):
        return resolve_self_detected_language(language, spec, explicit)
    code = module.normalize_language_code(language)
    if code is None:
        return None, INVALID_LANGUAGE
    languages = module.resolve_languages(spec["model"])
    if code in languages:
        return code, None
    if not explicit and len(languages) == 1:
        # An English-only checkpoint has always been handed any known code and quietly decoded
        # English; a client that never chose a model keeps that, and the response says `en`.
        logger.warning("Model %s knows only %s; transcribing a %s request anyway", spec["id"], languages[0], code)
        return code, None
    return None, UNSUPPORTED_LANGUAGE


def check_duplicate_specs(specs: list[dict[str, Any]]) -> None:
    """Refuse two specs that share a selecting name, which means they name the same weights."""
    owners: dict[str, dict[str, Any]] = {}
    for spec in specs:
        for name in list_spec_names(spec):
            other = owners.get(name)
            if other is not None and other is not spec:
                raise ValueError(f"STT_MODELS lists the same model twice: '{other['id']}' and '{spec['id']}'")
            owners[name] = spec


def warn_about_implicit_pools() -> None:
    """Point out entries that silently take STT_POOL_SIZE, which is 8 outside the Docker files."""
    implicit = [entry["model"] for entry in config.STT_MODELS if entry["pool_size"] is None]
    if len(implicit) > 1:
        logger.warning(
            "STT_MODELS entries without @pool each load STT_POOL_SIZE=%d instances (%s); give each one an explicit @N",
            config.MODEL_POOL_SIZE,
            ", ".join(implicit),
        )


def validate_model_specs() -> None:
    """Refuse at startup a model list the server cannot serve unambiguously; raises ValueError."""
    if not config.STT_MODELS:
        if config.STT_DEFAULT_MODEL:
            logger.warning("STT_DEFAULT_MODEL=%s is ignored without STT_MODELS", config.STT_DEFAULT_MODEL)
        return
    logger.info("STT_MODELS is set; STT_BACKEND, WHISPER_MODEL and PARAKEET_MODEL do not choose what is loaded")
    for entry in config.STT_MODELS:
        if entry["backend"] not in backends.TRANSCRIBERS:
            raise ValueError(f"STT_MODELS names unknown backend '{entry['backend']}'")
    specs = get_model_specs()
    check_duplicate_specs(specs)
    if config.STT_DEFAULT_MODEL and find_spec(config.STT_DEFAULT_MODEL, specs) is None:
        raise ValueError(f"STT_DEFAULT_MODEL '{config.STT_DEFAULT_MODEL}' is not in STT_MODELS")
    warn_about_implicit_pools()


def describe_model_specs() -> str:
    """One log line naming every loaded model, its pool size and which one is the default."""
    specs = get_model_specs()
    default_id = get_default_model_id()
    parts = [
        f"{spec['id']} ({spec['backend']}) x{spec['pool_size']}{' default' if spec['id'] == default_id else ''}"
        for spec in specs
    ]
    total = sum(spec["pool_size"] for spec in specs)
    return f"{', '.join(parts)} - {total} instance(s) in total"


def main():
    """No-op entry point: this module is imported for its registry helpers."""
    pass


if __name__ == "__main__":
    main()
