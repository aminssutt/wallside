"""
Add your own vehicle manual to the guide library.
Place your PDF in the manuel/ folder, then run this script.

Usage:
    cd backend
    python -m add_manual

The script will ask you for:
  - The PDF filename (must be in the manuel/ folder)
  - The display name for the guide
  - Optionally, a car image (place it in manuel/voiture/)
"""
import sys
import json
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from index_manuals import (
    index_single_manual,
    MANUALS_DIR,
    IMAGES_DIR,
)
from src.guide_manager import GUIDES_DIR, slugify


def main():
    print("\n" + "=" * 50)
    print("  Add a New Vehicle Manual")
    print("=" * 50)

    # List available PDFs
    if not MANUALS_DIR.exists():
        print(f"\nERROR: Create a 'manuel/' folder at project root.")
        sys.exit(1)

    pdfs = [f for f in MANUALS_DIR.iterdir() if f.suffix.lower() == ".pdf"]
    if not pdfs:
        print(f"\nNo PDF files found in {MANUALS_DIR}")
        print("Place your vehicle manual PDF there and re-run.")
        sys.exit(1)

    print(f"\nPDFs found in manuel/:")
    for i, p in enumerate(pdfs, 1):
        print(f"  {i}. {p.name}")

    # Select PDF
    choice = input(f"\nSelect PDF number (1-{len(pdfs)}): ").strip()
    try:
        pdf_path = pdfs[int(choice) - 1]
    except (ValueError, IndexError):
        print("Invalid selection.")
        sys.exit(1)

    # Guide name
    default_name = pdf_path.stem.replace("manuel ", "").replace("Manuel ", "").strip().title()
    name = input(f"Guide display name [{default_name}]: ").strip() or default_name

    # Image
    image = None
    if IMAGES_DIR.exists():
        images = [f for f in IMAGES_DIR.iterdir() if f.suffix.lower() in (".png", ".jpg", ".jpeg", ".webp")]
        if images:
            print(f"\nImages found in manuel/voiture/:")
            for i, img in enumerate(images, 1):
                print(f"  {i}. {img.name}")
            img_choice = input(f"Select image number (1-{len(images)}, or Enter to skip): ").strip()
            if img_choice:
                try:
                    image = images[int(img_choice) - 1].name
                except (ValueError, IndexError):
                    print("Invalid image selection, skipping.")

    # Index
    print(f"\nIndexing '{name}' from {pdf_path.name}...")
    result = index_single_manual(pdf_path, name, image)

    if not result:
        print("\nIndexing failed.")
        sys.exit(1)

    # Update manifest
    manifest_path = GUIDES_DIR / "manifest.json"
    manifest = []
    if manifest_path.exists():
        with open(manifest_path, "r", encoding="utf-8") as f:
            manifest = json.load(f)

    # Remove existing entry with same slug
    slug = slugify(name)
    manifest = [m for m in manifest if m["slug"] != slug]
    manifest.append(result)

    with open(manifest_path, "w", encoding="utf-8") as f:
        json.dump(manifest, f, ensure_ascii=False, indent=2)

    print(f"\n{'='*50}")
    print(f"  Done! '{name}' is now available.")
    print(f"  Restart the backend to see it in the guide list.")
    print(f"{'='*50}\n")


if __name__ == "__main__":
    main()
