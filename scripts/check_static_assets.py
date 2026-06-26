#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Static frontend sanity check for the desktop / server packaging pipeline.

Validates that ``index.html`` and the referenced frontend bundle only point
to asset files that actually exist on disk. A mismatch here is the most
common cause of the "Preparing backend..." / blank-page bug reported in
GitHub issues #1064, #1065, #1050: vite re-builds with a new content hash,
but the packaging step picks up a stale ``static/`` directory or copies the
files out of sync, so the browser receives a 404 (often as JSON) for the
main bundle or a lazy-loaded route chunk and refuses to execute it.

Usage:
    python scripts/check_static_assets.py [<static_dir>]

Exits 0 when consistent, non-zero with a human-readable message otherwise.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path
from typing import List, Optional, Tuple

# Match Vite asset references in HTML plus lazy-loaded chunks/preloads in
# emitted JS/CSS. Vite usually emits absolute /assets/* references from
# index.html and relative ./chunk.js or assets/chunk.css references inside
# the JS bundle.
_ASSET_PATTERN = re.compile(
    r"""["']((?:/assets/|assets/|\./)[^"']+\.(?:js|css|mjs|json|wasm|svg|png|jpg|jpeg|gif|webp|avif|ico|woff2?|ttf)(?:[?#][^"']*)?)["']""",
    re.IGNORECASE,
)
_SCANNABLE_ASSET_SUFFIXES = {".html", ".js", ".mjs", ".css"}


def _parse_referenced_assets(index_html: str) -> List[str]:
    """Return the unique list of asset paths referenced by bundle text."""
    seen: List[str] = []
    for match in _ASSET_PATTERN.finditer(index_html):
        ref = match.group(1)
        if ref not in seen:
            seen.append(ref)
    return seen


def _strip_asset_suffix(ref: str) -> str:
    return ref.split("?", 1)[0].split("#", 1)[0]


def _resolve_asset_ref(static_dir: Path, source_path: Path, ref: str) -> Optional[Path]:
    clean_ref = _strip_asset_suffix(ref)
    if clean_ref.startswith("/assets/"):
        return static_dir / clean_ref.lstrip("/")
    if clean_ref.startswith("assets/"):
        return static_dir / clean_ref
    if clean_ref.startswith("./"):
        return source_path.parent / clean_ref[2:]
    return None


def _display_asset_ref(static_dir: Path, candidate: Path) -> str:
    try:
        return "/" + candidate.relative_to(static_dir).as_posix()
    except ValueError:
        return candidate.as_posix()


def check_static_dir(static_dir: Path) -> Tuple[List[str], List[str]]:
    """
    Inspect ``static_dir`` and return ``(referenced, missing)``.

    ``referenced`` is the list of ``/assets/...`` paths declared in
    ``index.html``. ``missing`` is the subset that does not exist on disk.
    Raises ``FileNotFoundError`` if ``index.html`` itself is missing.
    """
    index_html_path = static_dir / "index.html"
    if not index_html_path.is_file():
        raise FileNotFoundError(f"index.html not found under {static_dir}")

    referenced: List[str] = []
    missing: List[str] = []
    scan_queue: List[Path] = [index_html_path]
    scanned: set[Path] = set()

    while scan_queue:
        source_path = scan_queue.pop(0)
        try:
            resolved_source = source_path.resolve()
        except OSError:
            resolved_source = source_path
        if resolved_source in scanned:
            continue
        scanned.add(resolved_source)

        try:
            content = source_path.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue

        for ref in _parse_referenced_assets(content):
            candidate = _resolve_asset_ref(static_dir, source_path, ref)
            if candidate is None:
                continue
            display_ref = _display_asset_ref(static_dir, candidate)
            if display_ref not in referenced:
                referenced.append(display_ref)
            if not candidate.is_file():
                if display_ref not in missing:
                    missing.append(display_ref)
                continue
            if candidate.suffix.lower() in _SCANNABLE_ASSET_SUFFIXES:
                scan_queue.append(candidate)
    return referenced, missing


def main(argv: List[str]) -> int:
    if len(argv) > 1:
        static_dir = Path(argv[1]).resolve()
    else:
        static_dir = (Path(__file__).resolve().parent.parent / "static").resolve()

    print(f"[check_static_assets] inspecting {static_dir}")

    try:
        referenced, missing = check_static_dir(static_dir)
    except FileNotFoundError as exc:
        print(f"[check_static_assets] ERROR: {exc}", file=sys.stderr)
        print(
            "[check_static_assets] Hint: build the frontend first via "
            "`cd apps/dsa-web && npm install && npm run build`.",
            file=sys.stderr,
        )
        return 2

    if not referenced:
        print(
            "[check_static_assets] WARNING: index.html does not reference any "
            "/assets/* files; this is unusual for a vite build.",
            file=sys.stderr,
        )
        return 0

    if missing:
        print(
            "[check_static_assets] ERROR: frontend bundle references assets that "
            "are not present on disk:",
            file=sys.stderr,
        )
        for ref in missing:
            print(f"  - {ref}", file=sys.stderr)
        print(
            "[check_static_assets] This produces a blank page when the missing "
            "entry or lazy-loaded chunk is requested (see GitHub #1064 / #1065). "
            "Re-run the frontend build and make sure the packaging step copies "
            "the freshly generated static/ directory.",
            file=sys.stderr,
        )
        return 1

    print(
        f"[check_static_assets] OK: {len(referenced)} asset reference(s) "
        f"resolved successfully."
    )
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
