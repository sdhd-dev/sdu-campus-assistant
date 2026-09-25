# Campus experience: brand assets and the photographic background

This document records where every visual asset came from and how the background
behind the account screens works. It covers the frontend only. No backend code,
API contract, or authentication flow was changed.

## Official SDU assets

Both files were downloaded from the university's own site, `sdu.edu.kz`, and are
stored unmodified except where stated.

| File | Source URL | Retrieved | Notes |
| --- | --- | --- | --- |
| `frontend/public/brand/sdu-university-logo.svg` | `https://sdu.edu.kz/wp-content/uploads/2025/09/logo_sdu_general_02-1.svg` | 2026-09-20 | **Byte-for-byte copy of the official file.** The general SDU University lockup: the winged shanyrak emblem, the `SDU` wordmark, `1996`, and `UNIVERSITY`. Colours are the file's own — `#f5a467` for the emblem and rules, `#fff` for the letterforms. |
| `frontend/public/brand/favicon.svg` | derived from the file above | 2026-09-20 | The emblem path from the official SVG, copied programmatically with its geometry and colour untouched, centred on a solid `#0f2f42` tile. Only a background and a uniform scale were added, because the official lockup is light-on-dark and would be invisible on a light browser tab. |
| `frontend/public/campus/sdu-campus-*.{webp,jpg}` | `https://sdu.edu.kz/wp-content/uploads/2025/09/campus-osennyi.webp` | 2026-09-20 | The university's own photograph of the main entrance, titled *campus-osennyi* in the site's media library. Original is 2560×1440. Resized and re-encoded only; nothing in the image was altered, retouched, or composited. |

The logo is used at its native proportions and never recoloured. Because the
official lockup is a light-on-dark variant, the header places it on a small dark
surface of its own instead of darkening the photograph behind the whole page.

### Licensing

These are the university's own published assets, used here for a university team
project about that university. **No explicit reuse licence is published on
`sdu.edu.kz`.** Before this project is shown outside the course, the team should
confirm permission with the SDU marketing office. That check has not been done.

## Why a photograph rather than a 3D model

An earlier iteration built a simplified 3D massing model of the main block from
CSS 3D transforms. It was genuine geometry, but at this level of detail it read
as a game scene rather than as SDU. The real photograph is more recognisable,
more honest, and much cheaper to render, so the model was removed.

## How the background moves

`frontend/src/campus/CampusPhoto.jsx` mounts **one** `<img>` for the whole
session. Navigation never swaps, reloads, or re-decodes it — the end-to-end check
asserts that the image is requested only once across registration, login, the
profile, a page reload, and rapid switching between views.

Each view is a different **crop** of that single picture, defined in
`frontend/src/campus/viewpoints.js` as a scale and an offset:

| View | Framing | Reads as |
| --- | --- | --- |
| `login` | widest, slightly right of centre | The main entrance with the avenue and the Alatau behind it. |
| `register` | pushed in, raised | The entrance bay: the emblem, the `SDU` lettering, the canopy. |
| `profile` | panned east | The central avenue looking across the rest of campus. |

These are **photographic moves — a push and a pan across one still image.** They
are not 3D camera rotations. No view shows a face of a building that the
photographer did not capture, and the photograph is never cut into fake depth
layers or parallax cut-outs.

A caption in the corner names the current framing, so the three views read as one
place seen three ways rather than as three unrelated pictures.

### Motion details

- The crop transition is a single CSS `transform` on `.campus-frame`, GPU
  composited, 1500 ms, one shared easing curve. CSS transitions retarget from
  their current value, so rapid navigation never queues or stacks moves.
- Pointer parallax is a separate outer element, so a slow crop transition never
  swallows the pointer response. It is desktop-only (skipped for
  `pointer: coarse`), writes at most once per animation frame, and stops while
  the tab is hidden. There is no animation loop when nothing is moving.
- `prefers-reduced-motion: reduce` holds **one composed framing** for the whole
  session and disables parallax and the fade-in. The background does not move
  at all, rather than cutting between positions.
- The frame element is intentionally larger than the viewport, which gives the
  crop room to travel without ever exposing an edge.

### Loading and failure

- The image is `decoding="async"` with `fetchPriority="low"`, so it never blocks
  the forms. It fades in when it has decoded.
- The stage carries a gradient of tones sampled from the photograph. If the
  image is slow, that is what shows; if it fails, `data-state="failed"` hides the
  broken image and the gradient stays. The end-to-end check blocks the image and
  then completes a full sign-in to prove the forms still work without it.
- Delivered as WebP at 1200/1800/2560 px with a JPEG fallback, chosen by
  `srcset`. The largest file is 317 kB; the whole `dist/` output is 1.3 MB.

## Accessibility notes

- Each view has exactly one `<h1>`, which is the panel title.
- The background is `aria-hidden` and `pointer-events: none`; it is decoration
  only and never receives focus or intercepts clicks.
- Password requirements are collapsed by default to keep the registration card
  short, but the list stays in the DOM and in the accessibility tree at all
  times. It is still referenced by the password field's `aria-describedby`, and
  it opens automatically when that field is focused.
- Validation messages keep their live regions mounted and collapse to zero
  height when empty, rather than being removed.
