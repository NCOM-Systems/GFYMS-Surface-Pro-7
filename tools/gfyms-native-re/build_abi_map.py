#!/usr/bin/env python3
"""Build a complete Surface Pro 7 Windows-driver ABI and dependency map.

Run this against the real extracted corpus with Git-LFS objects restored.
Requires: pip install pefile
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import re
from collections import Counter, defaultdict
from pathlib import Path

import pefile

LFS_PREFIX = b"version https://git-lfs.github.com/spec/v1"
PE_EXTENSIONS = {".sys", ".dll", ".exe"}


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def is_lfs_pointer(path: Path) -> bool:
    try:
        with path.open("rb") as handle:
            return handle.read(len(LFS_PREFIX)) == LFS_PREFIX
    except OSError:
        return False


def decode(value: bytes | str | None) -> str | None:
    if value is None:
        return None
    if isinstance(value, bytes):
        return value.decode("utf-8", "replace")
    return str(value)


def machine_name(machine: int) -> str:
    return {
        0x014C: "x86",
        0x8664: "x86_64",
        0xAA64: "ARM64",
        0x01C4: "ARM",
        0xA641: "ARM64EC",
    }.get(machine, f"unknown-0x{machine:04x}")


def parse_pe(path: Path) -> dict:
    record = {
        "path": path.as_posix(),
        "size": path.stat().st_size,
        "sha256": sha256(path),
        "lfs_pointer": is_lfs_pointer(path),
        "kind": path.suffix.lower().lstrip("."),
    }

    if record["lfs_pointer"]:
        record["analysis_status"] = "git-lfs-pointer"
        return record

    try:
        pe = pefile.PE(str(path), fast_load=False)
        imports = []
        for entry in getattr(pe, "DIRECTORY_ENTRY_IMPORT", []):
            module = (decode(entry.dll) or "").lower()
            functions = []
            for item in entry.imports:
                functions.append({
                    "name": decode(item.name),
                    "ordinal": int(item.ordinal) if item.ordinal else None,
                })
            imports.append({"module": module, "functions": functions})

        exports = []
        export_dir = getattr(pe, "DIRECTORY_ENTRY_EXPORT", None)
        for item in getattr(export_dir, "symbols", []):
            exports.append({
                "name": decode(item.name),
                "ordinal": int(item.ordinal),
                "address": int(item.address),
            })

        clr = pe.OPTIONAL_HEADER.DATA_DIRECTORY[14]
        record.update({
            "analysis_status": "ok",
            "architecture": machine_name(int(pe.FILE_HEADER.Machine)),
            "machine": f"0x{int(pe.FILE_HEADER.Machine):04x}",
            "entry_point_rva": int(pe.OPTIONAL_HEADER.AddressOfEntryPoint),
            "image_base": hex(int(pe.OPTIONAL_HEADER.ImageBase)),
            "subsystem": int(pe.OPTIONAL_HEADER.Subsystem),
            "clr": {
                "present": bool(clr.VirtualAddress and clr.Size),
                "directory_rva": hex(int(clr.VirtualAddress)),
                "directory_size": int(clr.Size),
            },
            "imports": imports,
            "exports": exports,
            "import_modules": sorted({x["module"] for x in imports}),
            "import_symbol_count": sum(len(x["functions"]) for x in imports),
            "export_symbol_count": len(exports),
        })
    except (pefile.PEFormatError, OSError, ValueError) as exc:
        record["analysis_status"] = "error"
        record["analysis_error"] = str(exc)

    return record


HARDWARE_PATTERNS = (
    r"PCI\\",
    r"ACPI\\",
    r"USB\\",
    r"HID\\",
    r"I2C\\",
    r"SPI\\",
    r"UART\\",
    r"GPIO\\",
    r"SWD\\",
    r"VEN_[0-9A-Fa-f]{4}",
    r"DEV_[0-9A-Fa-f]{4}",
    r"VID_[0-9A-Fa-f]{4}",
)


def parse_inf(path: Path) -> dict:
    lines = []
    for raw in path.read_text(encoding="utf-8-sig", errors="replace").splitlines():
        line = raw.split(";", 1)[0].strip()
        if line:
            lines.append(line)

    hardware_ids = set()
    services = []
    service_binaries = set()
    referenced_binaries = set()
    includes = set()

    for line in lines:
        rhs = line.split("=", 1)[1] if "=" in line else line
        for token in re.split(r"[,\s]+", rhs):
            token = token.strip().strip('"')
            if any(re.search(pattern, token, re.I) for pattern in HARDWARE_PATTERNS):
                hardware_ids.add(token)

        match = re.match(
            r"AddService\s*=\s*([^,]+)(?:,([^,]*))?(?:,([^,]+))?",
            line,
            re.I,
        )
        if match:
            services.append({
                "service": match.group(1).strip(),
                "flags": (match.group(2) or "").strip(),
                "install_section": (match.group(3) or "").strip(),
            })

        match = re.match(r"ServiceBinary\s*=\s*(.+)", line, re.I)
        if match:
            value = match.group(1).strip().strip('"')
            value = re.sub(r"%\d+%\\", "", value)
            service_binaries.add(value)

        match = re.match(r"Include\s*=\s*(.+)", line, re.I)
        if match:
            includes.add(match.group(1).strip())

        referenced_binaries.update(
            re.findall(r"(?i)\b[A-Za-z0-9_.$()%-]+\.(?:sys|dll|exe)\b", line)
        )

    referenced_binaries.update(Path(x).name for x in service_binaries)

    return {
        "path": path.as_posix(),
        "sha256": sha256(path),
        "hardware_ids": sorted(hardware_ids),
        "add_services": services,
        "service_binaries": sorted(service_binaries),
        "referenced_binaries": sorted(referenced_binaries),
        "includes": sorted(includes),
    }


def read_runtime_config(path: Path) -> dict:
    raw = path.read_text(encoding="utf-8-sig", errors="replace")
    record = {
        "path": path.as_posix(),
        "sha256": sha256(path),
        "size": path.stat().st_size,
        "kind": "runtimeconfig" if path.name.lower().endswith(".runtimeconfig.json")
        else "legacy-netfx-config",
        "runtime_requirements": [],
    }

    if path.name.lower().endswith(".exe.config"):
        versions = sorted(set(re.findall(
            r"sku\s*=\s*[\"']\.NETFramework,Version=v([^\"']+)",
            raw,
            re.I,
        )))
        record["runtime_requirements"] = [
            {"family": "netfx", "versions": versions}
        ] if versions else []
        record["wcf"] = "system.serviceModel" in raw
        return record

    try:
        data = json.loads(raw)
    except json.JSONDecodeError as exc:
        record["analysis_status"] = "invalid-json"
        record["error"] = str(exc)
        return record

    options = data.get("runtimeOptions", {})
    requirements = []
    if isinstance(options.get("framework"), dict):
        requirements.append(options["framework"])
    requirements.extend(
        item for item in options.get("frameworks", [])
        if isinstance(item, dict)
    )
    record["runtime_requirements"] = requirements
    record["self_contained"] = bool(options.get("includedFrameworks"))
    return record


def read_table(root: Path, name: str) -> list[dict[str, str]]:
    path = root / "tables" / f"{name}.csv"
    if not path.is_file():
        return []
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def parse_msi_tables(root: Path) -> dict:
    names = [
        "Feature",
        "FeatureComponents",
        "Component",
        "File",
        "CustomAction",
        "InstallExecuteSequence",
        "Property",
        "Media",
        "Binary",
    ]
    tables = {name: read_table(root, name) for name in names}

    product = {
        row.get("Property", ""): row.get("Value", "")
        for row in tables["Property"]
        if row.get("Property")
    }

    payloads = []
    for row in tables["File"]:
        raw_name = row.get("FileName", "")
        payloads.append({
            "file_id": row.get("File", ""),
            "component": row.get("Component_", ""),
            "filename": raw_name.split("|", 1)[-1],
            "raw_filename": raw_name,
            "version": row.get("Version", ""),
            "language": row.get("Language", ""),
            "size": row.get("FileSize", ""),
            "sequence": row.get("Sequence", ""),
        })

    actions = []
    for row in tables["CustomAction"]:
        source = row.get("Source", "")
        target = row.get("Target", "")
        lowered = target.lower()
        if "pnputil" in lowered or "powershell" in lowered:
            kind = "powershell-driver-install"
        elif source.lower().endswith(".dll"):
            kind = "custom-dll"
        else:
            kind = "other"
        actions.append({
            "action": row.get("Action", ""),
            "type": row.get("Type", ""),
            "source": source,
            "target": target,
            "kind": kind,
        })

    return {
        "product": product,
        "tables": tables,
        "features": tables["Feature"],
        "feature_components": [
            {
                "feature": row.get("Feature_", ""),
                "component": row.get("Component_", ""),
            }
            for row in tables["FeatureComponents"]
        ],
        "components": tables["Component"],
        "payloads": payloads,
        "custom_actions": actions,
        "execute_sequence": tables["InstallExecuteSequence"],
        "media": tables["Media"],
        "binary_table": tables["Binary"],
        "driver_install_actions": [
            action for action in actions
            if action["kind"] == "powershell-driver-install"
        ],
        "summary": {
            "feature_count": len(tables["Feature"]),
            "component_count": len(tables["Component"]),
            "file_count": len(payloads),
            "custom_action_count": len(actions),
            "driver_install_action_count": sum(
                action["kind"] == "powershell-driver-install"
                for action in actions
            ),
        },
    }


def build(root: Path) -> dict:
    files = [path for path in root.rglob("*") if path.is_file()]
    binaries = [path for path in files if path.suffix.lower() in PE_EXTENSIONS]
    infs = [path for path in files if path.suffix.lower() == ".inf"]
    configs = [
        path for path in files
        if path.name.lower().endswith(".exe.config")
        or path.name.lower().endswith(".runtimeconfig.json")
    ]
    msis = [path for path in files if path.suffix.lower() == ".msi"]

    msi = parse_msi_tables(root)

    pe_records = []
    by_basename = defaultdict(list)
    for path in binaries:
        record = parse_pe(path)
        record["path"] = path.relative_to(root).as_posix()
        if path.suffix.lower() == ".sys":
            record["runtime_class"] = "windows-kernel-driver"
        elif record.get("clr", {}).get("present"):
            record["runtime_class"] = "dotnet-managed"
        else:
            record["runtime_class"] = "native-win32"
        pe_records.append(record)
        by_basename[path.name.lower()].append(record["path"])

    inf_records = []
    for path in infs:
        record = parse_inf(path)
        record["path"] = path.relative_to(root).as_posix()
        inf_records.append(record)

    runtime_records = []
    for path in configs:
        record = read_runtime_config(path)
        record["path"] = path.relative_to(root).as_posix()
        runtime_records.append(record)

    nodes = []
    edges = []

    for record in pe_records:
        node = "pe:" + record["path"]
        nodes.append({
            "id": node,
            "type": record["runtime_class"],
            "path": record["path"],
        })
        for module in record.get("import_modules", []):
            for target in by_basename.get(module, []):
                edges.append({
                    "from": node,
                    "to": "pe:" + target,
                    "type": "imports",
                })

    for record in inf_records:
        node = "inf:" + record["path"]
        nodes.append({
            "id": node,
            "type": "windows-inf",
            "path": record["path"],
        })
        for name in record["service_binaries"]:
            for target in by_basename.get(Path(name).name.lower(), []):
                edges.append({
                    "from": node,
                    "to": "pe:" + target,
                    "type": "service-binds",
                })
        for name in record["referenced_binaries"]:
            for target in by_basename.get(Path(name).name.lower(), []):
                edges.append({
                    "from": node,
                    "to": "pe:" + target,
                    "type": "references",
                })

    configs_by_name = {Path(x["path"]).name.lower(): x for x in runtime_records}
    for record in pe_records:
        if not record.get("clr", {}).get("present"):
            continue
        config = configs_by_name.get(Path(record["path"]).name.lower() + ".config")
        if config:
            for requirement in config.get("runtime_requirements", []):
                if requirement.get("family") == "netfx":
                    runtime_id = (
                        "runtime:netfx:"
                        + ",".join(requirement.get("versions", []))
                    )
                else:
                    runtime_id = (
                        "runtime:"
                        + str(requirement.get("name"))
                        + ":"
                        + str(requirement.get("version"))
                    )
                nodes.append({
                    "id": runtime_id,
                    "type": "runtime-requirement",
                    **requirement,
                })
                edges.append({
                    "from": "pe:" + record["path"],
                    "to": runtime_id,
                    "type": "requires-runtime",
                })

    msi_features = {
        row.get("Feature", "")
        for row in msi["features"]
        if row.get("Feature")
    }
    msi_components = {
        row.get("Component", "")
        for row in msi["components"]
        if row.get("Component")
    }
    component_files = defaultdict(list)
    for payload in msi["payloads"]:
        component = payload["component"]
        file_id = payload["file_id"]
        if component and file_id:
            component_files[component].append(file_id)

    for feature in sorted(msi_features):
        nodes.append({
            "id": "msi:feature:" + feature,
            "type": "msi-feature",
            "name": feature,
        })
    for component in sorted(msi_components):
        nodes.append({
            "id": "msi:component:" + component,
            "type": "msi-component",
            "name": component,
        })

    for payload in msi["payloads"]:
        file_id = payload["file_id"]
        if not file_id:
            continue
        nodes.append({
            "id": "msi:file:" + file_id,
            "type": "msi-file",
            "name": payload["filename"],
            "component": payload["component"],
        })

    for relationship in msi["feature_components"]:
        feature = relationship["feature"]
        component = relationship["component"]
        if feature in msi_features and component in msi_components:
            edges.append({
                "from": "msi:feature:" + feature,
                "to": "msi:component:" + component,
                "type": "feature-component",
            })
        for file_id in component_files.get(component, []):
            edges.append({
                "from": "msi:component:" + component,
                "to": "msi:file:" + file_id,
                "type": "component-file",
            })

    for index, action in enumerate(msi["custom_actions"]):
        action_id = "msi:custom-action:" + str(index) + ":" + action["action"]
        nodes.append({
            "id": action_id,
            "type": "msi-custom-action",
            "name": action["action"],
            "kind": action["kind"],
            "source": action["source"],
            "target": action["target"],
        })

        source = action["source"]
        binary_names = {
            row.get("Name", "")
            for row in msi["binary_table"]
            if row.get("Name")
        }
        if source in binary_names:
            binary_id = "msi:binary:" + source
            nodes.append({
                "id": binary_id,
                "type": "msi-binary",
                "name": source,
            })
            edges.append({
                "from": action_id,
                "to": binary_id,
                "type": "custom-action-binary",
            })
        elif source:
            edges.append({
                "from": action_id,
                "to": "msi:source:" + source.lower(),
                "type": "custom-action-source",
            })

    module_counts = Counter()
    kernel_counts = Counter()
    wdf_counts = Counter()
    for record in pe_records:
        for module in record.get("import_modules", []):
            module_counts[module] += 1
        if record["kind"] == "sys":
            for imported in record.get("imports", []):
                module = imported["module"]
                if module in {"ntoskrnl.exe", "ntkrnlmp.exe", "hal.dll"}:
                    for function in imported["functions"]:
                        name = function["name"] or f"#{function['ordinal']}"
                        kernel_counts[f"{module}!{name}"] += 1
                if module in {"wdfldr.sys", "wdf01000.sys"}:
                    for function in imported["functions"]:
                        name = function["name"] or f"#{function['ordinal']}"
                        wdf_counts[f"{module}!{name}"] += 1

    duplicate_hashes = defaultdict(list)
    for record in pe_records:
        duplicate_hashes[record["sha256"]].append(record["path"])

    return {
        "schema": "gfyms.surface.abi-map.v2",
        "inventory": {
            "files": len(files),
            "pe_images": len(pe_records),
            "sys": sum(x["kind"] == "sys" for x in pe_records),
            "dll": sum(x["kind"] == "dll" for x in pe_records),
            "exe": sum(x["kind"] == "exe" for x in pe_records),
            "inf": len(inf_records),
            "runtime_config": len(runtime_records),
            "msi": len(msis),
            "lfs_pointer_pe_images": sum(
                x["lfs_pointer"] for x in pe_records
            ),
        },
        "binaries": pe_records,
        "infs": inf_records,
        "runtime_metadata": runtime_records,
        "dotnet_apps": [
            {
                "path": x["path"],
                "kind": x["kind"],
                "architecture": x.get("architecture"),
                "sha256": x["sha256"],
            }
            for x in pe_records
            if x.get("runtime_class") == "dotnet-managed"
        ],
        "msi": msi,
        "import_module_counts": module_counts.most_common(),
        "kernel_imports": kernel_counts.most_common(),
        "wdf_imports": wdf_counts.most_common(),
        "duplicate_hashes": {
            key: value for key, value in duplicate_hashes.items()
            if len(value) > 1
        },
        "dependency_graph": {
            "nodes": nodes,
            "edges": edges,
        },
        "msi_files": [
            {
                "path": path.relative_to(root).as_posix(),
                "size": path.stat().st_size,
                "sha256": sha256(path),
                "lfs_pointer": is_lfs_pointer(path),
            }
            for path in msis
        ],
    }


def render_markdown(data: dict) -> str:
    inv = data["inventory"]
    lines = [
        "# GFYMS Surface Pro 7 ABI Map",
        "",
        "Generated from the complete local extracted corpus.",
        "",
        "## Inventory",
        "",
        f"- PE images: {inv['pe_images']}",
        f"- SYS: {inv['sys']}",
        f"- DLL: {inv['dll']}",
        f"- EXE: {inv['exe']}",
        f"- INF: {inv['inf']}",
        f"- Runtime configs: {inv['runtime_config']}",
        f"- MSI: {inv['msi']}",
        f"- Unresolved Git-LFS PE pointers: {inv['lfs_pointer_pe_images']}",
        "",
        "## Managed applications",
        "",
        "| Path | Kind | Architecture |",
        "|---|---|---|",
    ]

    for row in data["dotnet_apps"]:
        lines.append(
            f"| {row['path']} | {row['kind']} | {row.get('architecture', '?')} |"
        )

    lines += [
        "",
        "## NT kernel import backlog",
        "",
        "| Symbol | References |",
        "|---|---:|",
    ]
    lines += [
        f"| {name} | {count} |"
        for name, count in data["kernel_imports"][:200]
    ]

    lines += [
        "",
        "## WDF import backlog",
        "",
        "| Symbol | References |",
        "|---|---:|",
    ]
    lines += [
        f"| {name} | {count} |"
        for name, count in data["wdf_imports"][:200]
    ]

    product = data.get("msi", {}).get("product", {})
    summary = data.get("msi", {}).get("summary", {})
    lines += [
        "",
        "## MSI installer model",
        "",
        f"- Product: {product.get('ProductName', 'unknown')}",
        f"- Version: {product.get('ProductVersion', 'unknown')}",
        f"- Manufacturer: {product.get('Manufacturer', 'unknown')}",
        f"- Features: {summary.get('feature_count', 0)}",
        f"- Components: {summary.get('component_count', 0)}",
        f"- Payload files: {summary.get('file_count', 0)}",
        f"- Custom actions: {summary.get('custom_action_count', 0)}",
        "",
        "### Custom actions",
        "",
        "| Action | Source | Target | Classification |",
        "|---|---|---|---|",
    ]

    for action in data.get("msi", {}).get("custom_actions", []):
        lines.append(
            f"| {action['action']} | {action['source']} | "
            f"{action['target']} | {action['kind']} |"
        )

    lines += [
        "",
        "The MSI graph is descriptive. GFYMS should translate Windows installer actions into native Linux package/update operations rather than executing Windows pnputil or PowerShell as Linux driver primitives.",
        "",
        "## Imported module counts",
        "",
        "| Module | Images |",
        "|---|---:|",
    ]
    lines += [
        f"| {name} | {count} |"
        for name, count in data["import_module_counts"][:100]
    ]
    return "\n".join(lines) + "\n"


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("root", type=Path)
    parser.add_argument("-o", "--output", type=Path, default=Path("abi-map.json"))
    parser.add_argument("--markdown", type=Path, default=Path("abi-map.md"))
    args = parser.parse_args()

    root = args.root.resolve()
    if not root.is_dir():
        raise SystemExit(f"Not a directory: {root}")

    data = build(root)
    args.output.write_text(
        json.dumps(data, indent=2) + "\n",
        encoding="utf-8",
    )
    args.markdown.write_text(render_markdown(data), encoding="utf-8")

    print(json.dumps(data["inventory"], indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
