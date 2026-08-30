"""Coordinate conversion between parser output and :class:`Region`.

PDF coordinates are in points with the origin at the **bottom-left** of the page
and y increasing upward. `Region` is normalised 0-1 with the origin at the
**top-left** and y increasing downward, so it survives re-rendering at any DPI
and matches how every viewer addresses a page.

Both axes differ. Getting this wrong does not crash anything — it silently
places every citation on the mirror image of the right spot, which is the kind
of defect that surfaces as "the highlighting is a bit off" months later.
"""

from __future__ import annotations

from agts.contracts.objects import Region

#: US Letter in points. Used only when a caller cannot supply real page sizes,
#: and callers are expected to warn rather than rely on it.
DEFAULT_PAGE_SIZE = (612.0, 792.0)


def pdf_points_to_region(
    bbox: list[float] | tuple[float, float, float, float],
    *,
    page: int,
    page_width: float,
    page_height: float,
) -> Region:
    """Convert `[left, bottom, right, top]` in PDF points to a `Region`.

    Coordinates are clamped to the page. Parsers occasionally emit boxes a
    fraction of a point outside the media box, and a clamp is preferable to a
    validation error that stops a run over a rounding artefact.
    """
    if page_width <= 0 or page_height <= 0:
        raise ValueError(f"page {page}: non-positive page size {page_width}x{page_height}")

    left, bottom, right, top = (float(v) for v in bbox)
    if right < left:
        left, right = right, left
    if top < bottom:
        bottom, top = top, bottom

    x0 = _clamp(left / page_width)
    x1 = _clamp(right / page_width)
    # Flip the vertical axis: PDF top edge is the largest y, Region top is 0.
    y0 = _clamp(1.0 - top / page_height)
    y1 = _clamp(1.0 - bottom / page_height)

    width = max(x1 - x0, _EPSILON)
    height = max(y1 - y0, _EPSILON)
    # A clamped box can be pushed past the far edge; pull the origin back.
    x0 = min(x0, 1.0 - width)
    y0 = min(y0, 1.0 - height)

    return Region(page=page, x=x0, y=y0, width=width, height=height)


def region_to_pdf_points(
    region: Region, *, page_width: float, page_height: float
) -> tuple[float, float, float, float]:
    """Inverse of :func:`pdf_points_to_region`, for cropping a figure out of the
    original PDF. Round-trips to within floating-point error."""
    left = region.x * page_width
    right = (region.x + region.width) * page_width
    top = (1.0 - region.y) * page_height
    bottom = (1.0 - region.y - region.height) * page_height
    return (left, bottom, right, top)


_EPSILON = 1e-6


def _clamp(value: float) -> float:
    return min(max(value, 0.0), 1.0)


def page_sizes_from_pdf(pdf_path: str) -> dict[int, tuple[float, float]]:
    """Read per-page media box sizes, 1-indexed.

    Page size is per page, not per document: NCERT chapters mix portrait body
    pages with landscape tables, and assuming one size mirrors those tables onto
    the wrong half of the page.

    Either pypdf or pypdfium2 will do. Both are common transitive dependencies
    of PDF tooling, so accepting either usually means installing neither.
    """
    try:
        from pypdf import PdfReader
    except ImportError:
        pass
    else:
        reader = PdfReader(pdf_path)
        return {
            index: (float(page.mediabox.width), float(page.mediabox.height))
            for index, page in enumerate(reader.pages, start=1)
        }

    try:
        import pypdfium2
    except ImportError as exc:  # pragma: no cover - depends on the environment
        raise ImportError(
            "page_sizes_from_pdf needs pypdf or pypdfium2. Install one, or pass "
            "page sizes explicitly to the adapter."
        ) from exc

    document = pypdfium2.PdfDocument(pdf_path)
    try:
        return {
            index + 1: tuple(float(v) for v in document[index].get_size())
            for index in range(len(document))
        }
    finally:
        document.close()
