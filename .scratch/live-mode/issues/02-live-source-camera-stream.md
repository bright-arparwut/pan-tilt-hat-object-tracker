# 02 — Live Source: camera / stream over cv2.VideoCapture

Status: done

## Goal

Add a **`CameraSource`** — a `FrameSource` over `cv2.VideoCapture` that serves a live camera
(by index) or a stream URL — and the source-string classification that decides Live vs file.
Unbounded, derived `VideoInfo`, no on-screen output yet (that's 03); this phase is unit-tested
against a fake capture.

## Decisions (from grilling session, ADR-0010)

- **One source string, type-inferred:** all-digits → camera **index** (`int(s)`); a URL scheme
  in `{rtsp, http, https, udp, tcp}` → **stream URL**; anything else → file path. Both of the
  first two build a `CameraSource`; the third stays `FileSource` (01).
- **Process every frame, sequentially** — plain `cap.read()` in the loop, no background reader,
  no drop-to-latest. Accept that a slow loop sees driver-dropped frames or growing lag.
- **Derived `VideoInfo`:** width/height from `CAP_PROP_FRAME_WIDTH/HEIGHT`; `fps` from
  `CAP_PROP_FPS` when `> 0` else a nominal `DEFAULT_CAMERA_FPS` (feeds `ByteTrack.frame_rate`
  + annotator scaling); `total_frames = None` (open-ended `tqdm`).
- **Fail clearly** if the device/URL won't open (`cap.isOpened()` false) — a user-facing error,
  not a silent empty run.

## Tasks

- `config.py` — add `DEFAULT_CAMERA_FPS` (e.g. 30) with a comment on why a fallback is needed.
- A `classify_source(s: str) -> CameraSpec | FileSpec` helper (pure, no IO) — `CameraSpec`
  holds an `int` index **or** a stream `str`; URL-scheme detection via `urllib.parse`/regex.
- `CameraSource(spec)` — opens `cv2.VideoCapture(index_or_url)`, raises a clear error if not
  opened; `info` builds the derived `sv.VideoInfo(total_frames=None)`; `__iter__` yields frames
  until `read()` returns falsey; `release()` releases the capture.
- Tests: `classify_source` covers `"0"`, `"12"`, `"rtsp://…"`, `"http://…"`, `"clip.mp4"`,
  `"./a/b.mov"`; `CameraSource` over a **fake VideoCapture** (monkeypatched) yields the queued
  frames, builds `VideoInfo` with the fps fallback when the device reports 0, and raises on
  `isOpened() == False`. No real camera in tests.

## Acceptance

1. `classify_source` returns the right spec for digits / each URL scheme / file paths
   (table-tested).
2. `CameraSource` over a fake capture yields every queued frame, stops on the first falsey
   `read()`, and `release()`s once; `info.total_frames is None`; fps falls back when 0.
3. Opening a non-openable source raises a clear, user-facing error (asserted).
4. `uv run pytest` green; no real device or network touched.

## Depends on

01 (the `FrameSource` Protocol).

## Refs

ADR-0010 (§Source overloading, §Throughput). PRD §CLI surface, §Key decisions.
