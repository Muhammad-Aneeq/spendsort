# demo/

The LinkedIn demo video, and the script that records it.

| file | what it is |
|---|---|
| `output/spendsort-demo.mp4` | **the upload-ready video** — 1:34, 1280×720, H.264 + silent AAC |
| `output/spendsort-demo.webm` | the raw Playwright capture (VP8) |
| `../frontend/demo/record-demo.mjs` | the recorder |

## Re-recording it

```bash
# 1. a clean two-run baseline, so the bend has something to show
rm -f backend/spendsort.db*
uv run uvicorn app.main:app --app-dir backend --port 8123      # serves the built SPA too
curl -F "file=@examples/month_01_realistic_seed42.csv" localhost:8123/api/ingest/csv && curl -XPOST localhost:8123/api/runs
curl -F "file=@examples/month_02_realistic_seed43.csv" localhost:8123/api/ingest/csv && curl -XPOST localhost:8123/api/runs

# 2. build the SPA so the API serves the current UI
cd frontend && npm run build

# 3. record
node demo/record-demo.mjs          # → demo/output/spendsort-demo.webm
```

Then convert to MP4 (LinkedIn's safest format):

```bash
node -e "console.log(require('ffmpeg-static'))"   # path to a full ffmpeg
"$FFMPEG" -i demo/output/spendsort-demo.webm \
  -f lavfi -i anullsrc=channel_layout=stereo:sample_rate=44100 \
  -c:v libx264 -profile:v high -pix_fmt yuv420p -crf 20 -preset medium -r 25 \
  -c:a aac -b:a 96k -shortest -movflags +faststart \
  demo/output/spendsort-demo.mp4
```

The silent audio track is deliberate — some platforms mishandle video-only files. `+faststart`
moves the index to the front so it streams rather than downloading first.

> Playwright's own bundled ffmpeg can only write VP8/WebM. The `ffmpeg-static` dev dependency
> is what provides H.264.

## What the recording does

It runs the real product against the **live** model — the third month is uploaded and
categorized during filming, not pre-baked. The database is expected to already hold two
completed runs so the memory bend has three points.

Three things exist only for the camera, injected as an overlay:

- **Burnt-in captions.** LinkedIn autoplays muted, so no beat may depend on narration.
- **A synthetic cursor.** Playwright renders no pointer, so clicks would otherwise look like
  things that happen on their own.
- **Spotlight rings** on the element being discussed, because the video plays small in a feed.

## Timing

~95 seconds. The beats:

| ~time | beat |
|---|---|
| 0:00 | title card |
| 0:06 | the chart of accounts |
| 0:20 | upload a month of transactions |
| 0:28 | categorize — a live model call per unseen vendor |
| 0:45 | the confidence histogram, and the gate |
| 0:55 | the review queue: what it thought, and why |
| 1:05 | override one → *learned* |
| 1:15 | vendor memory |
| 1:22 | **the memory bend** |
| 1:30 | export, then the close card |

## Note on the numbers shown

They are whatever the live model actually produced on the day, so they move between takes.
Dollar amounts use the fallback token price (BLOCKERS.md B4) — the ratios are real, the
absolute dollars are placeholders.
