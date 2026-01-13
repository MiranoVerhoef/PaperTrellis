# Configuration

All paths are **inside the container**. Use bind mounts or volumes to persist them.

## Environment variables

- `ODM_INGEST_DIR` (default `/data/ingest`)
- `ODM_LIBRARY_DIR` (default `/data/library`)
- `ODM_CONFIG_DIR` (default `/data/config`)
- `ODM_FAILED_DIR` (default `/data/failed`)
- `ODM_TMP_DIR` (default `/data/tmp`)

- `ODM_SCAN_ENABLED` (`true|false`, default `true`)
- `ODM_SCAN_INTERVAL_SECONDS` (default `15`)
- `ODM_TESSERACT_LANG` (default `eng`)

## Authentication (single-user)

- `ODM_AUTH_ENABLED` (`true|false`, default `true`)
- `ODM_ADMIN_PASSWORD` (**required** if auth enabled)
- `ODM_SESSION_SECRET` (**required** if auth enabled; use a long random string)
