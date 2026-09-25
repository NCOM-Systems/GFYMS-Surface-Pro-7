from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

from .core import ProcessResult, require_absolute_file, require_windows, run_argv
from .errors import ManifestError

_RUNTIME_LINE = re.compile(
    r"^(?P<family>[^\s]+)\s+(?P<version>[^\s]+)\s+\[(?P<path>.+)]\s*$"
)
_ALLOWED_ARCH = {"x86", "x64", "arm64"}
_SUCCESS_CODES = {0, 3010, 1641}


@dataclass(frozen=True)
class DotNetRuntime:
    family: str
    version: str
    install_path: str


@dataclass(frozen=True)
class DotNetRuntimeInventory:
    process: ProcessResult
    parsed: tuple[DotNetRuntime, ...]
    unparsed_lines: tuple[str, ...]


def parse_runtime_inventory(output: str) -> tuple[tuple[DotNetRuntime, ...], tuple[str, ...]]:
    parsed: list[DotNetRuntime] = []
    unparsed: list[str] = []
    for line in output.splitlines():
        if not line.strip():
            continue
        match = _RUNTIME_LINE.match(line)
        if match:
            parsed.append(DotNetRuntime(**match.groupdict()))
        else:
            unparsed.append(line)
    return tuple(parsed), tuple(unparsed)


def list_dotnet_runtimes(
    *, dotnet: str | Path, arch: str | None = None
) -> DotNetRuntimeInventory:
    """Run the documented runtime listing command using an explicit dotnet host path."""
    require_windows()
    dotnet_path = require_absolute_file(dotnet, "dotnet host")
    argv: list[str | Path] = [dotnet_path, "--list-runtimes"]
    if arch is not None:
        if arch not in _ALLOWED_ARCH:
            raise ManifestError(f"unsupported .NET architecture argument: {arch}")
        argv.extend(["--arch", arch])
    process = run_argv(argv)
    if process.exit_code != 0:
        raise ManifestError(f"dotnet runtime inventory failed: {process.stderr.strip()}")
    parsed, unparsed = parse_runtime_inventory(process.stdout)
    return DotNetRuntimeInventory(process, parsed, unparsed)


def install_dotnet_runtime(
    installer: str | Path, *, timeout: int | None = None
) -> ProcessResult:
    """Run the documented Windows runtime installer options after trust/pin checks."""
    require_windows()
    installer_path = require_absolute_file(installer, ".NET runtime installer")
    if installer_path.suffix.casefold() != ".exe":
        raise ManifestError("the .NET Windows installer adapter requires an .exe")
    return run_argv(
        [installer_path, "/install", "/quiet", "/norestart"],
        timeout=timeout,
    )
