# Phase 2D — Browser and Screenshot Evidence

Date: 2026-08-03

## Environment and provenance

- Actual Vite source: isolated loopback `127.0.0.1:19084`
- Task-owned in-memory API fixture: isolated loopback `127.0.0.1:18184`
- Browser: isolated in-app Chromium profile
- Data: synthetic user Mina Chen, reviewer Noah Rivera, project, vector image, two Polygons,
  immutable review, and one generated PNG upload
- Repository `.env`, database, object storage, Docker, staging, TLS, and recovery services: unused

The two task-owned listeners and temporary fixture source were removed after the run.

## Unified journey

1. Anonymous English Login rendered the governed sign-in boundary. The synthetic login redirect
   established only task-owned loopback cookies and opened Projects.
2. Projects rendered the one synthetic record without overflow. Detail rendered persisted project
   facts, three private synthetic image previews, readiness history, and the image upload surface.
3. The image-set fixture deliberately returned a safe 503 on initial load; `Retry image set`
   recovered to the complete workbench with no inferred fallback facts.
4. Reviewer management loaded one existing reviewer and one assignable synthetic user, preserving
   owner-only access controls.
5. A generated 1440 x 974 PNG was selected in the controlled primary-front replacement form.
   The first request deliberately returned `REJECTED_DIMENSIONS` / 422; retrying the unchanged
   file and declaration returned 201 and the UI exposed its success state before refreshing.
6. Region loaded an approved v2 snapshot with two hand-authored Polygons, disabled immutable
   editing controls, private image overlay, append-only history, and reviewer attribution.
7. English and Simplified Chinese content, HTML language, state-aware document title, persisted
   user-entered labels, and route identity were verified. Final titles were
   `Region Annotation — PaintPilot` and `区域标注 — PaintPilot`.
8. A keyboard-focused language option had a visible 2 px solid focus outline. The active
   `prefers-reduced-motion: reduce` stylesheet rule was present. Final console warnings/errors:
   `[]`.

The deliberate 503 and 422 responses were both followed by successful retries. There was no
unexplained network failure.

## Responsive measurements

| Width | Document overflow | Language | Logout | Region tools | Tool overlap | Polygon canvas |
| ---: | --- | ---: | ---: | ---: | --- | ---: |
| 320 px | none | 44 px | 44 px | 44 px | none | 288 px |
| 390 px | none | 44 px | 44 px | 44 px | none | 358 px |
| 768 px | none | 44 px | 44 px | 44 px | none | 720 px |
| 1440 px | none | compact desktop | compact desktop | compact desktop | none | 971.7 px |

At 320 and 390 px the Region toolbar retained two three-column groups, all controls stayed
separate, the small-screen precision guidance remained visible, and the inspector/history stayed
available below the full-width canvas.

## Public captures

- `docs/screenshots/paintpilot-region-workspace-en.png`
- `docs/screenshots/paintpilot-region-workspace-zh-cn.png`

Both are single-viewport 1440 x 974 PNG captures. They contain no stitched fixed header, repeated
page section, browser UI, private path, real account, unrelated project, or tool/runtime label.
