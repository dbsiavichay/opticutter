# Cutting diagram rendering

`src/modules/optimizations/visualization.py` (`VisualizationService`) draws
the per-board cutting diagram: boards, placed pieces, remainders (waste) and
edge-banded sides, with dimensions and an efficiency percentage. It is built
on Pillow (PIL) and used as an **internal building block**, not a
standalone endpoint — there is no `/optimize/visualize/{hash}` route. The
diagram is embedded directly into the PDF documents rendered by
`proforma.py`:

- the commercial document (`GET /preorders/{id}/proforma`,
  `GET /orders/{id}/document`),
- the order's production sheet (`GET /orders/{id}/production-sheet`),
- the dispatch sheet (`GET /orders/{id}/dispatch-sheet`).

If you need a diagram outside of those documents (e.g. for a new export or a
debugging script), call `VisualizationService` directly rather than adding a
new public image endpoint — see `proforma.py` for the call pattern.

## Themes

Two color themes share the same drawing code:

| Theme | Used in | Notes |
|-------|---------|-------|
| `brand` | Proforma / order document | Branded palette (coral pieces, dark outlines), matches the MADERABLE letterhead. |
| `mono` | Production sheet | Black & white, optimized for workshop printing. |

In both themes, a banded edge is drawn as a colored strip along that side of
the piece: solid fill for soft (`Suave`) banding, diagonal hatching for hard
(`Duro`) banding — so the distinction survives in the monochrome sheet, where
color alone can't carry it.

## Visual elements

- **Boards** — rectangles with a dark outline.
- **Pieces** — filled rectangles with a colored outline; a thicker band along
  any edge-banded side highlights the canto (see Themes above for soft vs.
  hard rendering).
- **Remainders (waste)** — neutral gray rectangles.
- **Annotations** — per-board title, dimensions, and a yield/efficiency
  percentage.

## Layout

- Boards are laid out automatically in rows.
- Scale and minimum dimensions are computed automatically to keep small
  pieces legible.
- Font lookup tries a list of system paths in order (macOS first, then
  Linux/Docker) — see `_FONT_CANDIDATES` — and falls back to PIL's default
  bitmap font if none are found.

## Possible improvements

- Cache rendered diagrams (currently regenerated on every document request).
- Support additional output formats (SVG) for non-PDF consumers.
- Surface cost/kerf annotations directly on the diagram.
