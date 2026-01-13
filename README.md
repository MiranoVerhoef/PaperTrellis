# PaperTrellis (v0.2)

PaperTrellis is a self-hosted document organizer that **plays nice with your existing folder structure**.

It can:
- Watch an **ingest** folder (or accept manual uploads)
- Extract text via **PDF text extraction + OCR** (Tesseract)
- Match **templates** (regex patterns)
- Extract fields (company / invoice # / date)
- Apply **tags** (from templates)
- Route/rename documents into `/data/library` **without rearranging what you already have**
- If ingest fails or no template matches, move the file to `/data/failed`

The Web UI is inspired by modern “document inbox” apps:
- Single-user login
- Documents list with search + tag filters
- Tag overview
- Template editor
- Document detail view (preview + OCR text)

## Quick start (bind mounts)

```bash
mkdir -p data/{ingest,library,config,failed,tmp}
docker compose -f docker-compose.bind.yml up -d
```

Open: `http://localhost:8000`

> Set a real password & secret in the compose file:
> - `ODM_ADMIN_PASSWORD`
> - `ODM_SESSION_SECRET` (long random string)

## Volume-based compose

```bash
docker compose -f docker-compose.volumes.yml up -d
```

## How routing works

1. File arrives via ingest watcher or upload
2. PaperTrellis extracts text
3. It picks the best matching template (enabled templates only)
4. It extracts fields (optional)
5. It builds the output folder + filename from your template
6. It moves the file into `/data/library/...`

If there is **no matching template** (or an error occurs), the file is moved to `/data/failed`.

## Folder philosophy

- `/data/library` is your “truth”. PaperTrellis **inherits existing folders** and indexes them.
- Templates only affect **new** files coming in (or files you upload).
- Existing documents stay put unless you manually move them yourself.

## Configuration

See `docs/CONFIG.md`.

## GHCR publishing

This repo includes a GitHub Actions workflow that builds/pushes:

- `ghcr.io/<owner>/papertrellis:latest`
- `ghcr.io/<owner>/papertrellis:<tag>`
