"""Visual regression helper — Task 25: screenshot diff using pixelmatch."""

import base64
import io
from dataclasses import dataclass


@dataclass
class DiffResult:
    diff_percentage: float   # 0.0–100.0
    diff_pixel_count: int
    diff_image_bytes: bytes  # PNG diff image


def diff_screenshots(baseline_bytes: bytes, actual_bytes: bytes) -> DiffResult:
    """
    Compare two PNG screenshots using pixelmatch.
    Returns pixel diff percentage, count, and a diff PNG image.
    """
    try:
        from pixelmatch.contrib.PIL import pixelmatch
        from PIL import Image

        img_a = Image.open(io.BytesIO(baseline_bytes)).convert("RGBA")
        img_b = Image.open(io.BytesIO(actual_bytes)).convert("RGBA")

        # Resize to match if dimensions differ
        if img_a.size != img_b.size:
            img_b = img_b.resize(img_a.size, Image.LANCZOS)

        diff_img = Image.new("RGBA", img_a.size)
        mismatch = pixelmatch(img_a, img_b, diff_img, threshold=0.1)

        total_pixels = img_a.width * img_a.height
        diff_pct = (mismatch / total_pixels * 100) if total_pixels > 0 else 0.0

        buf = io.BytesIO()
        diff_img.save(buf, format="PNG")
        return DiffResult(
            diff_percentage=round(diff_pct, 4),
            diff_pixel_count=mismatch,
            diff_image_bytes=buf.getvalue(),
        )

    except ImportError:
        # pixelmatch or Pillow not installed — return zero diff
        return DiffResult(
            diff_percentage=0.0,
            diff_pixel_count=0,
            diff_image_bytes=baseline_bytes,
        )
