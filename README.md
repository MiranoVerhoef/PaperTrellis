# PaperTrellis (Docker)

**Version:** v0.1


A self-hosted document organizer that:
- Accepts **manual uploads** in a Web UI
- Watches an **ingest folder** and auto-processes new files
- Uses **OCR** (Tesseract) and/or embedded PDF text
- Applies **configurable templates** to:
  - classify documents (e.g. Invoices)
  - extract fields (company, invoice number, date)
  - move files into a folder structure
  - rename files based on those extracted fields

## Quick start (Docker Compose)

PaperTrellis comes with **two Compose variants**:

- **Bind mounts** (recommended): uses your host folders (easy to inspect/backup)
- **Named volumes**: Docker-managed volumes (portable, no local folder clutter)

### Option A — Bind mounts (recommended)

1) Create folders:

```bash
mkdir -p data/ingest data/library data/config data/failed
```

2) Start:

```bash
docker compose -f docker-compose.bind.yml up -d
```

### Option B — Named volumes

Start:

```bash
docker compose -f docker-compose.volumes.yml up -d
```

### Open the Web UI

- `http://localhost:8000`

Drop documents into the ingest location:
- Bind mounts: `./data/ingest`
- Volumes: use the Web UI uploader, or `docker cp` into the container’s `/data/ingest`

## Volumes

Mount these paths:

- `/data/ingest`  → where you drop incoming files
- `/data/library` → organized output
- `/data/config`  → SQLite database (templates + history)
- `/data/failed`  → ingest files that could not be processed

## Template logic

Each template has:
- **Match patterns**: regex lines used to detect a document type (all/any)
- **Extraction regexes**: company, invoice number, date (first capture group)
- **Output path template** and **Filename template**

Available variables:

- `{doc_folder}` / `{doc_type}` – your document folder (e.g. `Invoices`)
- `{company}`
- `{invoice_number}`
- `{date}` (Python datetime formatting supported: `{date:%Y-%m-%d}`)
- `{original_name}`

Example:
- Output path: `{doc_folder}/{company}/{date:%Y}`
- Filename: `{company}_{invoice_number}_{date:%Y-%m-%d}`

## OCR

- PDFs: if the PDF already contains text, it will be used. If not, the app renders pages and OCRs them.
- Images: OCR via Tesseract.

Set OCR language(s) with:

- `ODM_TESSERACT_LANG=eng` (or `eng+nld` etc)

> Note: For additional Tesseract languages, install language packs in your Docker image (or extend the image).

## Publishing to GHCR

This repo includes a GitHub Actions workflow that builds and pushes to:

- `ghcr.io/MiranoVerhoef/papertrellis`

On:
- pushes to `main` → tags `latest` + `sha`
- tags like `v1.2.3` → tag `v1.2.3`

## Roadmap ideas

- Per-template “destination root” overrides
- PDF preview + extracted text viewer
- More field types + multiple capture groups
- Rules/conditions (numeric comparisons, date ranges)
- Queue & concurrency controls
- Authentication (basic auth / OAuth)


## Non-destructive by design

PaperTrellis **does not reorganize or touch your existing library**. It only processes:
- files you **upload** via the Web UI
- files you **drop into the ingest folder**

Existing folders under `/data/library` are only **scanned read-only** so you can select them in the template UI.
Files are never overwritten: if a name already exists, PaperTrellis appends `_1`, `_2`, etc.

## Upload to GitHub

This repository is ready to upload as-is:

1) Create the repo: `MiranoVerhoef/papertrellis`
2) Upload the contents of this zip (or push via git)
3) GitHub Actions will build & publish to GHCR:
   - `ghcr.io/MiranoVerhoef/papertrellis:latest` on pushes to `main`
   - version tags like `v0.1.0` will publish the same tag

> Note: the included `.gitignore` excludes `data/` so you don’t accidentally commit your documents.
