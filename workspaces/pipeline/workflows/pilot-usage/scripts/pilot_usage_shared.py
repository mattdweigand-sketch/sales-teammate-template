"""Policy loading, local-only JSON storage, and font verification shared by the pilot-usage scripts."""

from __future__ import annotations

import hashlib
import json
import shutil
import urllib.request
from pathlib import Path
from typing import Any

import yaml

PROJECT_FILES_ROOT = Path(__file__).resolve().parents[5]  # workspaces/pipeline/workflows/pilot-usage/scripts/x.py -> files root
DEFAULT_POLICY = PROJECT_FILES_ROOT / "_core" / "policy.yaml"
LFS_POINTER_SIGNATURE = b"version https://git-lfs.github.com/spec/v1"
# Network timeout for the one-time CDN font fetch, unrelated to policy `chromium_timeout_seconds`.
FONT_DOWNLOAD_TIMEOUT_SECONDS = 60
# Render writes fonts here, relative to the HTML file; print verifies them at the same place.
FONT_OUTPUT_DIRECTORY = Path("assets") / "fonts"


def load_pilot_usage_policy(policy_path: Path = DEFAULT_POLICY) -> dict[str, Any]:
    """Return `pilot_usage.pdf` flat, plus `top_users` and lowercased `tooling.internal_domains`. Keys keep their YAML names."""
    document = yaml.safe_load(policy_path.read_text(encoding="utf-8"))
    try:
        pilot_usage = document["pilot_usage"]
        pdf = dict(pilot_usage["pdf"])
        internal_domains = document["tooling"]["internal_domains"]
    except (KeyError, TypeError) as exc:
        raise ValueError("policy.yaml has no pilot_usage.pdf block or tooling.internal_domains") from exc
    return {
        **pdf,
        "top_users": int(pilot_usage["top_users"]),
        "internal_domains": [str(domain).lower() for domain in internal_domains],
    }


def require_local_only_output_path(output_path: Path) -> Path:
    """Return a resolved output path or reject a path inside Project Files."""
    resolved_output = output_path.expanduser().resolve()
    if resolved_output == PROJECT_FILES_ROOT or PROJECT_FILES_ROOT in resolved_output.parents:
        raise ValueError("real pilot run artifacts must remain outside the Project Files repository")
    return resolved_output


def read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def write_local_json(output_path: Path, payload: Any) -> Path:
    """Write indented JSON to a path outside Project Files, creating parents."""
    resolved_output = require_local_only_output_path(output_path)
    resolved_output.parent.mkdir(parents=True, exist_ok=True)
    resolved_output.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    return resolved_output


def verify_font_bytes(font_path: Path, expected_sha256: str, role: str) -> None:
    if not font_path.is_file():
        raise RuntimeError(f"required {role} font is unavailable: {font_path}")
    font_bytes = font_path.read_bytes()
    if font_bytes.startswith(LFS_POINTER_SIGNATURE):
        raise RuntimeError(f"required {role} font at {font_path} is an unhydrated Git LFS pointer, not font bytes")
    if hashlib.sha256(font_bytes).hexdigest() != expected_sha256:
        raise RuntimeError(f"required {role} font failed integrity verification: {font_path}")


def _download_font(url: str, target: Path) -> None:
    with urllib.request.urlopen(url, timeout=FONT_DOWNLOAD_TIMEOUT_SECONDS) as response:
        target.write_bytes(response.read())


def ensure_font_assets(policy: dict[str, Any], font_directory: Path, download: bool = True) -> Path:
    """sha256-verify every `policy["fonts"]` entry in `font_directory`.

    With `download=True` (render) a missing font is fetched, and a font that fails verification
    is deleted and fetched once more before the final check. With `download=False` (print) the
    fonts must already be present and valid.
    """
    font_directory.mkdir(parents=True, exist_ok=True)
    for role, font in policy["fonts"].items():
        target = font_directory / font["file_name"]
        if not download:
            verify_font_bytes(target, font["sha256"], role)
            continue
        if not target.is_file():
            if "source_path" in font:
                source = (PROJECT_FILES_ROOT / font["source_path"]).resolve()
                if PROJECT_FILES_ROOT not in source.parents:
                    raise RuntimeError("font source must remain inside the bundled assets")
                verify_font_bytes(source, font["sha256"], role)
                shutil.copyfile(source, target)
            else:
                _download_font(font["url"], target)
        try:
            verify_font_bytes(target, font["sha256"], role)
        except RuntimeError:
            target.unlink(missing_ok=True)
            if "source_path" in font:
                source = (PROJECT_FILES_ROOT / font["source_path"]).resolve()
                verify_font_bytes(source, font["sha256"], role)
                shutil.copyfile(source, target)
            else:
                _download_font(font["url"], target)
            verify_font_bytes(target, font["sha256"], role)
    return font_directory
