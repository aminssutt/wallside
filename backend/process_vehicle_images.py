"""
Remove image backgrounds for vehicle assets using rembg.

Input directory:
    backend/data/vehicle_images

Output:
    Transparent PNG files with the same basename.
    Original non-PNG files are removed by default after successful conversion.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Dict, List

from PIL import Image
from rembg import remove


BACKEND_DIR = Path(__file__).parent
IMAGES_DIR = BACKEND_DIR / "data" / "vehicle_images"
SUPPORTED_EXT = {".png", ".jpg", ".jpeg", ".webp"}


def parse_args():
    parser = argparse.ArgumentParser(description="Remove vehicle image backgrounds with rembg.")
    parser.add_argument("--force", action="store_true", help="Reprocess even if already transparent PNG.")
    parser.add_argument("--keep-originals", action="store_true", help="Keep source files after PNG output.")
    parser.add_argument("--summary-json", help="Optional path to write processing summary as JSON.")
    return parser.parse_args()


def _is_alpha_png(path: Path) -> bool:
    if path.suffix.lower() != ".png":
        return False
    try:
        with Image.open(path) as img:
            return "A" in img.getbands()
    except Exception:
        return False


def _process_file(path: Path, force: bool, keep_originals: bool) -> Dict[str, str]:
    suffix = path.suffix.lower()
    if suffix not in SUPPORTED_EXT:
        return {"status": "skipped", "file": path.name, "reason": "unsupported_ext"}

    if path.name.lower() == "sources.json":
        return {"status": "skipped", "file": path.name, "reason": "metadata_file"}

    output_path = path.with_suffix(".png")

    if not force and path.suffix.lower() == ".png" and _is_alpha_png(path):
        return {"status": "skipped", "file": path.name, "reason": "already_transparent_png"}

    if (
        not force
        and path.suffix.lower() != ".png"
        and output_path.exists()
        and output_path.stat().st_mtime >= path.stat().st_mtime
        and _is_alpha_png(output_path)
    ):
        if not keep_originals:
            path.unlink(missing_ok=True)
        return {"status": "skipped", "file": path.name, "reason": "already_processed_png"}

    try:
        input_bytes = path.read_bytes()
        output_bytes = remove(input_bytes)
        output_path.write_bytes(output_bytes)
    except Exception as exc:
        return {"status": "failed", "file": path.name, "reason": f"remove_bg_error:{exc}"}

    if path != output_path and not keep_originals:
        path.unlink(missing_ok=True)

    return {
        "status": "processed",
        "file": path.name,
        "output": output_path.name,
    }


def main():
    args = parse_args()

    if not IMAGES_DIR.exists():
        print(f"No image directory found: {IMAGES_DIR}")
        return 0

    image_files = sorted(
        [
            p for p in IMAGES_DIR.iterdir()
            if p.is_file() and p.suffix.lower() in SUPPORTED_EXT
        ],
        key=lambda p: p.name.lower(),
    )

    summary: Dict[str, List[dict]] = {
        "processed": [],
        "skipped": [],
        "failed": [],
    }

    for image_path in image_files:
        result = _process_file(
            path=image_path,
            force=args.force,
            keep_originals=args.keep_originals,
        )
        status = result.get("status", "failed")
        summary.setdefault(status, []).append(result)

    print("\nVehicle image background cleanup")
    print(f"Directory: {IMAGES_DIR}")
    print(f"Processed: {len(summary['processed'])}")
    print(f"Skipped: {len(summary['skipped'])}")
    print(f"Failed: {len(summary['failed'])}")

    if summary["failed"]:
        print("\nFailed files:")
        for item in summary["failed"]:
            print(f"  - {item['file']} -> {item.get('reason', 'unknown_error')}")

    if args.summary_json:
        summary_path = Path(args.summary_json)
        summary_path.parent.mkdir(parents=True, exist_ok=True)
        summary_path.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"Summary JSON: {summary_path}")

    # Non-zero if at least one file failed.
    return 1 if summary["failed"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
