from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path
from typing import Sequence

from .core import (
    ProcessResult,
    require_absolute_file,
    require_existing_file,
    require_windows,
    run_argv,
    system_executable,
)
from .errors import ManifestError

_HWID_PREFIXES = (
    "PCI\\", "ACPI\\", "USB\\", "HID\\", "I2C\\", "SPI\\",
    "UART\\", "GPIO\\", "SWD\\",
)


@dataclass(frozen=True)
class DriverPackage:
    inf: Path
    catalog: Path


def validate_driver_package(
    inf: str | Path, catalog: str | Path
) -> DriverPackage:
    inf_path = require_existing_file(inf)
    catalog_path = require_existing_file(catalog)
    if inf_path.suffix.casefold() != ".inf":
        raise ManifestError("driver package INF must end in .inf")
    if catalog_path.suffix.casefold() != ".cat":
        raise ManifestError("driver catalog must end in .cat")
    return DriverPackage(inf_path, catalog_path)


def extract_inf_hardware_ids(inf: str | Path) -> tuple[str, ...]:
    path = require_existing_file(inf)
    ids: set[str] = set()
    for raw_line in path.read_text(
        encoding="utf-8-sig", errors="replace"
    ).splitlines():
        for token in raw_line.split(","):
            value = token.strip().strip('"')
            upper = value.upper()
            if upper.startswith(_HWID_PREFIXES) or re.search(
                r"(?:^|[\\&])(?:VEN|DEV|VID|PID|SUBSYS|REV)_[0-9A-F]{2,8}(?:$|[&\\])",
                upper,
            ):
                ids.add(upper)
    return tuple(sorted(ids))


def validate_manifest_hardware_ids(
    inf: str | Path, declared: Sequence[str]
) -> tuple[str, ...]:
    actual = set(extract_inf_hardware_ids(inf))
    if not actual:
        raise ManifestError("INF contains no recognizable hardware IDs")
    if not declared or not all(isinstance(x, str) and x for x in declared):
        raise ManifestError("manifest requires one or more non-empty hardware IDs")
    missing = sorted({x.upper() for x in declared} - actual)
    if missing:
        raise ManifestError(
            "manifest hardware ID evidence is not present in INF: " + ", ".join(missing)
        )
    return tuple(sorted(actual))


def pnputil_add_driver(
    inf: str | Path, *, install: bool = False, reboot: bool = False
) -> ProcessResult:
    """Stage an INF and optionally install it on matching devices."""
    require_windows()
    inf_path = require_existing_file(inf)
    argv: list[str | Path] = [
        system_executable("pnputil.exe"),
        "/add-driver",
        inf_path,
    ]
    if install:
        argv.append("/install")
    if reboot:
        argv.append("/reboot")
    return run_argv(argv)


def pnputil_enum_drivers() -> ProcessResult:
    require_windows()
    return run_argv([system_executable("pnputil.exe"), "/enum-drivers"])


def verify_driver_catalog(
    signtool: str | Path, package: DriverPackage
) -> tuple[ProcessResult, ProcessResult]:
    """Verify the catalog and INF coverage. Never signs or modifies the package."""
    require_windows()
    sign = require_absolute_file(signtool, "SignTool")
    catalog_result = run_argv([sign, "verify", "/kp", package.catalog])
    inf_result = run_argv(
        [sign, "verify", "/kp", "/c", package.catalog, package.inf]
    )
    return catalog_result, inf_result


def build_wdk_solution(
    msbuild: str | Path,
    solution: str | Path,
    *,
    configuration: str,
    platform: str,
    extra_properties: Sequence[str] = (),
) -> ProcessResult:
    """Build supplied WDK source in an already configured VS/WDK/EWDK environment."""
    require_windows()
    build = require_absolute_file(msbuild, "MSBuild")
    solution_path = require_existing_file(solution)
    if configuration not in {"Debug", "Release"}:
        raise ManifestError("configuration must be Debug or Release")
    if platform not in {"x64", "ARM64", "Win32"}:
        raise ManifestError("platform must be x64, ARM64, or Win32")
    argv: list[str | Path] = [
        build,
        solution_path,
        "/m",
        f"/p:Configuration={configuration}",
        f"/p:Platform={platform}",
    ]
    for prop in extra_properties:
        if not isinstance(prop, str) or not prop.startswith("/p:"):
            raise ManifestError("extra MSBuild properties must start with /p:")
        argv.append(prop)
    return run_argv(argv)
