from __future__ import annotations

import hashlib
import os
import re
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Sequence

from .errors import ManifestError, PlatformNotSupportedError

_SHA256 = re.compile(r"^[0-9a-fA-F]{64}$")


@dataclass(frozen=True)
class ProcessResult:
    argv: tuple[str, ...]
    exit_code: int
    stdout: str
    stderr: str


def require_windows() -> None:
    if sys.platform != "win32":
        raise PlatformNotSupportedError(
            "This operation requires Windows. WinKIT does not emulate Windows APIs on another OS."
        )


def sha256_file(path: str | Path, *, chunk_size: int = 1024 * 1024) -> str:
    digest = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for chunk in iter(lambda: stream.read(chunk_size), b""):
            digest.update(chunk)
    return digest.hexdigest()


def assert_sha256(path: str | Path, expected_hex: str) -> None:
    if not isinstance(expected_hex, str) or not _SHA256.fullmatch(expected_hex):
        raise ManifestError("expected SHA-256 must be exactly 64 hexadecimal characters")
    actual = sha256_file(path)
    if actual.casefold() != expected_hex.casefold():
        raise ManifestError(
            f"SHA-256 mismatch for {path}: expected {expected_hex}, received {actual}"
        )


def require_existing_file(path: str | Path) -> Path:
    result = Path(path).expanduser().resolve()
    if not result.is_file():
        raise ManifestError(f"required file does not exist: {result}")
    return result


def resolve_under_root(root: str | Path, relative: str | Path) -> Path:
    root_path = Path(root).expanduser().resolve()
    candidate = (root_path / relative).resolve()
    if candidate == root_path or root_path not in candidate.parents:
        raise ManifestError(f"path escapes manifest root: {relative}")
    return candidate


def require_absolute_file(path: str | Path, label: str) -> Path:
    candidate = Path(path).expanduser()
    if not candidate.is_absolute():
        raise ManifestError(f"{label} must be an absolute path")
    return require_existing_file(candidate)


def run_argv(argv: Sequence[str | Path], *, timeout: int | None = None) -> ProcessResult:
    """Run an explicit argv vector. Never invokes a shell or cmd.exe."""
    normalized = tuple(str(part) for part in argv)
    if not normalized:
        raise ManifestError("argv must not be empty")
    executable = Path(normalized[0])
    if not executable.is_absolute():
        raise ManifestError("the executable path must be absolute")
    if not executable.is_file():
        raise ManifestError(f"executable does not exist: {executable}")
    completed = subprocess.run(
        normalized,
        shell=False,
        check=False,
        timeout=timeout,
        text=True,
        encoding="utf-8",
        errors="replace",
        capture_output=True,
    )
    return ProcessResult(normalized, completed.returncode, completed.stdout, completed.stderr)


def system_executable(name: str) -> Path:
    require_windows()
    system_root = Path(os.environ.get("SystemRoot", r"C:\Windows"))
    candidate = (system_root / "System32" / name).resolve()
    if not candidate.is_file():
        raise ManifestError(f"Windows system executable not found: {candidate}")
    return candidate
