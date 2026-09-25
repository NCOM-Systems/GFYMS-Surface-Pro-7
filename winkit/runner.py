from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .core import assert_sha256, require_existing_file, resolve_under_root
from .dotnet import install_dotnet_runtime
from .drivers import (
    pnputil_add_driver,
    validate_driver_package,
    validate_manifest_hardware_ids,
    verify_driver_catalog,
)
from .errors import ManifestError
from .msi import MsiNative, run_msiexec
from .wintrust import require_trusted


@dataclass(frozen=True)
class PlanItem:
    package_id: str
    kind: str
    path: Path
    sha256: str
    detail: str


def load_manifest(path: str | Path) -> dict[str, Any]:
    manifest_path = require_existing_file(path)
    try:
        data = json.loads(manifest_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise ManifestError(f"invalid WinKIT manifest JSON: {exc}") from exc
    if (
        not isinstance(data, dict)
        or data.get("schema") != 1
        or not isinstance(data.get("packages"), list)
    ):
        raise ManifestError("unsupported or incomplete WinKIT manifest")
    ids = []
    for entry in data["packages"]:
        if not isinstance(entry, dict) or not isinstance(entry.get("id"), str):
            raise ManifestError("every package requires a string id")
        ids.append(entry["id"])
    if len(ids) != len(set(ids)):
        raise ManifestError("package ids must be unique")
    return data


def _required_string(entry: dict[str, Any], name: str) -> str:
    value = entry.get(name)
    if not isinstance(value, str) or not value:
        raise ManifestError(
            f"package {entry.get('id', '<unknown>')!r} lacks string {name!r}"
        )
    return value


def inspect_manifest(
    manifest: dict[str, Any], *, root: str | Path
) -> list[PlanItem]:
    root_path = Path(root).expanduser().resolve()
    policy = manifest.get("policy", {})
    if not isinstance(policy, dict):
        raise ManifestError("policy must be an object")
    require_authenticode = bool(policy.get("requireAuthenticode", True))

    plan: list[PlanItem] = []
    for entry in manifest["packages"]:
        if not isinstance(entry, dict):
            raise ManifestError("each package entry must be an object")
        package_id = _required_string(entry, "id")
        kind = _required_string(entry, "kind")

        if kind == "driver-inf":
            relative = _required_string(entry, "inf")
        else:
            relative = _required_string(entry, "path")
        local = resolve_under_root(root_path, relative)
        require_existing_file(local)
        assert_sha256(local, _required_string(entry, "sha256"))

        if require_authenticode and kind != "driver-inf":
            require_trusted(local)

        if kind == "msi":
            MsiNative().verify_package(local)
            operation = entry.get("operation", "install")
            if operation not in {"install", "uninstall"}:
                raise ManifestError(
                    f"package {package_id!r} has unsupported MSI operation"
                )
            detail = f"MSI verified: {local.name}"

        elif kind == "dotnet-runtime-exe":
            _required_string(entry, "family")
            _required_string(entry, "architecture")
            if local.suffix.casefold() != ".exe":
                raise ManifestError("dotnet-runtime-exe package must point to .exe")
            detail = f".NET runtime installer staged: {local.name}"

        elif kind == "driver-inf":
            catalog = resolve_under_root(root_path, _required_string(entry, "catalog"))
            catalog_hash = _required_string(entry, "catalogSha256")
            assert_sha256(catalog, catalog_hash)
            signtool = require_absolute_file(
                _required_string(entry, "signtool"), "SignTool"
            )
            package = validate_driver_package(local, catalog)
            declared_ids = entry.get("hardwareIds")
            actual_ids = validate_manifest_hardware_ids(local, declared_ids)
            catalog_result, inf_result = verify_driver_catalog(signtool, package)
            if catalog_result.exit_code != 0 or inf_result.exit_code != 0:
                raise ManifestError(
                    "driver catalog verification failed; inspect SignTool output"
                )
            for package_file in entry.get("packageFiles", []):
                if not isinstance(package_file, dict):
                    raise ManifestError("packageFiles entries must be objects")
                file_path = resolve_under_root(
                    root_path, _required_string(package_file, "path")
                )
                assert_sha256(
                    file_path, _required_string(package_file, "sha256")
                )
            detail = (
                f"driver package verified: {local.name}; "
                f"hardware IDs in INF={len(actual_ids)}"
            )

        else:
            raise ManifestError(f"unrecognized or unsupported package kind: {kind!r}")

        plan.append(
            PlanItem(
                package_id,
                kind,
                local,
                entry["sha256"],
                detail,
            )
        )
    return plan


def apply_manifest(
    manifest: dict[str, Any], *, root: str | Path, apply: bool
) -> list[str]:
    """Inspect first; mutate only when apply=True and policy permits it."""
    plan = inspect_manifest(manifest, root=root)
    if not apply:
        return [f"PLAN {item.package_id}: {item.detail}" for item in plan]

    policy = manifest.get("policy", {})
    root_path = Path(root).expanduser().resolve()
    results: list[str] = []
    entries = {entry["id"]: entry for entry in manifest["packages"]}

    for item in plan:
        entry = entries[item.package_id]
        if item.kind == "msi":
            log = resolve_under_root(root_path, _required_string(entry, "log"))
            result = run_msiexec(
                operation=entry.get("operation", "install"),
                target=item.path,
                log_path=log,
                properties=entry.get("msiProperties", {}),
            )
            results.append(
                f"{item.package_id}: {result.normalized_status} ({result.process.exit_code})"
            )
            if result.normalized_status in {"Failed", "RetryableBusy"}:
                break

        elif item.kind == "dotnet-runtime-exe":
            if not policy.get("allowRuntimeInstall", False):
                raise ManifestError(
                    "policy.allowRuntimeInstall must be true for .NET runtime mutation"
                )
            result = install_dotnet_runtime(item.path)
            results.append(f"{item.package_id}: raw exit code {result.exit_code}")
            if result.exit_code not in {0, 3010, 1641}:
                break

        elif item.kind == "driver-inf":
            if not policy.get("allowDriverInstall", False):
                raise ManifestError(
                    "policy.allowDriverInstall must be true for driver installation"
                )
            result = pnputil_add_driver(item.path, install=True, reboot=False)
            results.append(f"{item.package_id}: PnPUtil exit code {result.exit_code}")
            if result.exit_code != 0:
                break

    return results
