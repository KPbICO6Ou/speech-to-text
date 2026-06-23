## Changelog

### [Unreleased]

#### Added
- **Per-request language for `/api/stt`.** An optional `language` (query string
  `?language=ru` or a multipart form field) overrides the server
  `WHISPER_LANGUAGE` default for a single request; `auto` autodetects. Invalid
  values return `400 {"error": "Invalid language"}`.
- **Static token auth.** `STT_TOKENS` holds a comma-separated list of valid
  tokens. When set, every `POST /api/stt` must carry `Authorization: Bearer
  <token>`; missing or invalid tokens return `401`. `GET /api/health` stays open
  so docker-compose healthchecks keep working. The client sends `STT_TOKEN`.
- **Configurable `STT_PORT`.** Both docker-compose files honor `STT_PORT`, so the
  published port follows the server port without editing the compose files.
- **Multilingual README.** Translations live in `docs/README_<LANG>.md` and are
  linked from the language switcher at the top of each README.

#### Changed
- **Uniform error responses.** Every error carries a generic `error` category and
  a `request_id` that correlates the response with the full exception in the
  server log.
- **Simplified request log.** Request lines log elapsed seconds with a plain
  separator instead of milliseconds and a duplicated status code.
