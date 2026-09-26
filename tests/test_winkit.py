import hashlib
import json
import os
import sys
from pathlib import Path

import pytest

from winkit.core import assert_sha256, require_absolute_file, require_windows, resolve_under_root, run_argv
from winkit.drivers import extract_inf_hardware_ids, validate_manifest_hardware_ids
from winkit.dotnet import parse_runtime_inventory
from winkit.errors import ManifestError, PlatformNotSupportedError
from winkit.msi import _validate_readonly_select
from winkit.runner import inspect_manifest, load_manifest


def test_sha256_and_absolute_process_execution(tmp_path):
    path = tmp_path / "payload.bin"
    path.write_bytes(b"gfyms")
    expected = hashlib.sha256(b"gfyms").hexdigest()
    assert_sha256(path, expected)
    with pytest.raises(ManifestError):
        assert_sha256(path, "0" * 64)
    result = run_argv([Path(sys.executable), "-c", "print('ok')"])
    assert result.exit_code == 0
    assert result.stdout.strip() == "ok"


def test_root_resolution_rejects_escape(tmp_path):
    inside = resolve_under_root(tmp_path, "a/b.txt")
    assert inside.parent == tmp_path / "a"
    with pytest.raises(ManifestError):
        resolve_under_root(tmp_path, "../outside")
    with pytest.raises(ManifestError):
        require_absolute_file("relative.exe", "tool")


def test_windows_gate_hard_stops_on_linux():
    if sys.platform != "win32":
        with pytest.raises(PlatformNotSupportedError):
            require_windows()


def test_readonly_msi_sql_gate():
    assert _validate_readonly_select("SELECT * FROM Property")[0:6] == "SELECT"
    for value in (
        "UPDATE Property SET Value='x'",
        "SELECT * FROM Property; DROP TABLE Property",
        "SELECT * FROM Property -- mutate later",
        "SELECT * FROM Property /* comment */",
    ):
        with pytest.raises(ManifestError):
            _validate_readonly_select(value)


def test_driver_hardware_ids_are_evidence_backed(tmp_path):
    inf = tmp_path / "device.inf"
    inf.write_text(
        "[Models.NTamd64]\nDevice=Install,USB\\VID_1234&PID_5678\n",
        encoding="utf-8",
    )
    actual = extract_inf_hardware_ids(inf)
    assert actual == ("USB\\VID_1234&PID_5678",)
    assert validate_manifest_hardware_ids(inf, ["usb\\vid_1234&pid_5678"]) == actual
    with pytest.raises(ManifestError):
        validate_manifest_hardware_ids(inf, ["USB\\VID_9999&PID_0000"])


def test_dotnet_inventory_parser_preserves_unknown_lines():
    output = (
        "Microsoft.NETCore.App 8.0.20 [C:\\Program Files\\dotnet\\shared\\Microsoft.NETCore.App]\n"
        "future-format-line"
    )
    parsed, unknown = parse_runtime_inventory(output)
    assert parsed[0].family == "Microsoft.NETCore.App"
    assert parsed[0].version == "8.0.20"
    assert unknown == ("future-format-line",)


def test_manifest_validation_is_deterministic(tmp_path):
    manifest = {
        "schema": 1,
        "policy": {},
        "packages": [{"id": "a", "kind": "unknown"}],
    }
    path = tmp_path / "winkit.json"
    path.write_text(json.dumps(manifest), encoding="utf-8")
    with pytest.raises(ManifestError, match="unrecognized"):
        inspect_manifest(manifest, root=tmp_path)


def test_manifest_rejects_duplicate_ids(tmp_path):
    manifest = {
        "schema": 1,
        "packages": [{"id": "a", "kind": "unknown"}, {"id": "a", "kind": "unknown"}],
    }
    path = tmp_path / "winkit.json"
    path.write_text(json.dumps(manifest), encoding="utf-8")
    with pytest.raises(ManifestError, match="unique"):
        load_manifest(path)
