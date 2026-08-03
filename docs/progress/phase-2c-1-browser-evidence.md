# Phase 2C — Unified Frontend Browser Evidence

Date: 2026-08-02

## Provenance and Environment

- `FRONTEND_SKILLS_LOADED`: `redesign-existing-projects`, `gpt-taste`, and `impeccable` v4.0.4
  were loaded before the unified audit/refinement evidence run.
- Exact isolated local stack: `RUN_ID=p2c1_taste_refine`, Web
  `http://127.0.0.1:19082/`.
- Browser: Codex in-app Chromium using the local OIDC Authorization Code + PKCE route.
- Synthetic project: `Taste-backed Figure Study`;
  `782abef5-1573-43fd-8361-d78d7a74d0cc`.
- Four task-owned synthetic PNGs only: one deliberate invalid 120 × 120 file and three distinct
  valid 900 × 1100 files. No existing private image was used.
- The earlier `p2c1_taste_audit` captures remain in the Candidate as pre-Skill reference only.
  They are not presented as final Skill-backed evidence.

## Final Journey Evidence

1. At 1440 px, anonymous Login rendered the governed CreativeDeploy / PaintPilot identity and
   real local sign-in path.
2. Owner A created the synthetic project. At 768 px, Projects retained the signed-in platform
   frame, Create project, material/facts card, workflow state, and release boundary.
3. An unassigned Reviewer C direct visit returned the expected safe unavailable/not-found
   boundary. Owner A then granted Reviewer C access; the owner surface showed the membership
   list and the reviewer role constraints.
4. A 120 × 120 PNG produced the actual upload constraint message. The valid 900 × 1100 primary,
   back, and angle retries were stored with accepted checks and rights attestation; owner then
   saved the human READY decision.
5. Owner drew a hand-authored three-vertex `Figure silhouette` Polygon at 1440 px, saved v1,
   submitted v2, and observed v1 superseded/v2 submitted history.
6. Assigned Reviewer C reopened v2, saw private image/history and read-only geometry controls,
   then approved the exact submitted snapshot. History rendered v2 approved with reviewer
   attribution.
7. At 390 px, Region retained status, tools, private canvas, inspector, history, and an explicit
   small-screen precision warning rather than hiding or pretending to support desktop-precision
   editing.
8. Keyboard navigation made `Skip to main content` active. The final browser warning/error query
   returned `[]`. The expected invalid-upload rejection was followed by a successful retry; no
   unexplained browser-visible network failure remained.

## Captures Used for Final Evidence

- `evidence/phase-2c-1/login-anonymous-1440-skill-backed.png`
- `evidence/phase-2c-1/projects-owner-768-skill-backed.png`
- `evidence/phase-2c-1/project-detail-owner-1440-skill-backed.png`
- `evidence/phase-2c-1/reviewer-management-owner-1440-skill-backed.png`
- `evidence/phase-2c-1/region-polygon-owner-1440-skill-backed.png`
- `evidence/phase-2c-1/reviewer-submitted-region-1440-skill-backed.png`

Phase 2D retired four defective historical full-page captures after visual inspection found
repeated fixed headers and stitched-page seams:
`project-detail-zh-1440-bilingual.png`, `image-readiness-1440-skill-backed.png`,
`upload-error-1440-skill-backed.png`, and `region-owner-390-skill-backed.png`. Their historical
Phase 2C hashes remain in the Phase 2C manifest as an audit record; they are not current public
evidence.

## Scope Note

These records are synthetic local smoke evidence. They demonstrate Candidate UI behavior and
role-appropriate browser state only; they do not claim independent approval, sealing, or
  production readiness. The exact `p2c1_taste_refine` stack and four task-owned fixtures
were removed after capture.

## Unified Bilingual and Impeccable Browser Evidence

The bilingual continuation did not repeat the Docker staging journey above. It ran the actual
Vite Web source at `http://127.0.0.1:19083/` against a task-owned, in-memory API fixture on
`127.0.0.1:18183`; this isolates presentation behavior and is not backend integration evidence.

1. Restored the saved locale, switched to English on Projects, then completed the English
   list/create/detail flow for `Bilingual PaintPilot proof`. User-entered English remained data.
2. Verified loading, a deliberate Projects `503`, Retry success, and the empty Projects state.
3. Assigned a reviewer, exercised a deliberate upload `422` dimension rejection, retried the
   same operation successfully, and confirmed the image workbench resumed.
4. Switched the populated detail to Chinese in place. URL remained
   `/paintpilot/projects/11111111-1111-4111-8111-111111111111`; authenticated identity,
   user-entered title/description, and raw project ID remained unchanged. Navigation to Region
   and back retained Chinese, while the persisted preference resolver is covered by unit tests.
5. Loaded Region after a deliberate invalid-response state and Retry, inspected Polygon/history,
   submitted and approved the exact synthetic snapshot, then returned to English.
6. At 1440, 768, and 390 px, document width matched viewport width. A visible-element overflow
   scan was empty; broken-image count was `0`; raw translation-key count was `0`.
7. At 390 px, the small-screen precision guidance remained visible and persisted data/history
   stayed usable. The first Tab focused `跳到主要内容`; the stylesheet contained the active
   reduced-motion media rule.
8. Final browser warning/error query: `[]`. The expected `503` and `422` paths were followed by
   successful Retry responses; no unexplained console or network failure remained.

Public-ready capture:

- `docs/screenshots/paintpilot-region-workspace-en.png` — synthetic English Region workbench,
  visually inspected; no private project asset or account.

The Vite and in-memory API processes were stopped immediately after capture and both listener
ports were confirmed closed. The temporary fixture source and one invalid stitched screenshot
were removed; neither entered the final Candidate.
