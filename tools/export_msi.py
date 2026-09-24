#!/usr/bin/env python3
from __future__ import annotations
import base64, csv, datetime as dt, hashlib, json, shutil, subprocess, sys
from pathlib import Path

import pymsi
from pymsi.package import Package


def safe(s: str) -> str:
    chars = "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789._- "
    out = "".join(c if c in chars else "_" for c in s).strip(". ")
    return out or "_"


def j(v):
    if isinstance(v, (str, int, float, bool)) or v is None:
        return v
    if isinstance(v, (dt.datetime, dt.date, dt.time)):
        return v.isoformat()
    if isinstance(v, dt.timedelta):
        return v.total_seconds()
    if isinstance(v, (bytes, bytearray, memoryview)):
        b = bytes(v)
        return {
            "type": "bytes",
            "base64": base64.b64encode(b).decode(),
            "length": len(b),
        }
    if isinstance(v, dict):
        return {str(k): j(x) for k, x in v.items()}
    if isinstance(v, (list, tuple)):
        return [j(x) for x in v]
    if callable(v):
        return {
            "type": "callable",
            "name": getattr(v, "__qualname__", getattr(v, "__name__", repr(v))),
        }
    return repr(v)


def attr_value(obj, name: str, *call_args):
    """Read an attribute that may be either a value or a callable across pymsi versions."""
    value = getattr(obj, name, None)
    if callable(value):
        try:
            return value(*call_args)
        except TypeError:
            return value
    return value


def sha(path):
    h = hashlib.sha256()
    with path.open("rb") as f:
        for b in iter(lambda: f.read(1024 * 1024), b""):
            h.update(b)
    return h.hexdigest()


def run_pymsi(args, out):
    p = subprocess.run(
        [sys.executable, "-m", "pymsi", *args],
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        encoding="utf-8",
        errors="replace",
        check=False,
    )
    Path(out).write_text(p.stdout, encoding="utf-8")
    return p.returncode


def main():
    if len(sys.argv) != 3:
        raise SystemExit("usage: export_msi.py INPUT.msi OUTPUT_DIR")
    src = Path(sys.argv[1]).resolve()
    out = Path(sys.argv[2]).resolve()
    if not src.is_file():
        raise SystemExit(f"missing MSI: {src}")
    if out.exists():
        shutil.rmtree(out)
    for name in ("source", "files", "streams", "tables", "reports", "metadata"):
        (out / name).mkdir(parents=True)
    shutil.copy2(src, out / "source" / src.name)

    strict_error = None
    try:
        pkg = Package(src, strict=True)
        strict = True
    except Exception as e:
        strict = False
        strict_error = repr(e)
        pkg = Package(src, strict=False)

    manifest = {
        "tool": "nightlark/pymsi",
        "version": getattr(pymsi, "__version__", "unknown"),
        "source": {"name": src.name, "size": src.stat().st_size, "sha256": sha(src)},
        "strict_validation": strict,
    }
    if strict_error:
        manifest["strict_error"] = strict_error

    with pkg:
        s = pkg.summary
        manifest["summary"] = {
            k: getattr(s, m)()
            for k, m in {
                "title": "title",
                "subject": "subject",
                "author": "author",
                "uuid": "uuid",
                "architecture": "arch",
                "languages": "languages",
                "creating_application": "creating_application",
                "creation_time": "creation_time",
                "comments": "comments",
                "word_count": "word_count",
            }.items()
        }

        table_manifest = []
        for name, table in sorted(pkg.tables.items()):
            table = pkg.get(name)
            rows = list(table.iter())
            stem = safe(name)
            (out / "tables" / f"{stem}.json").write_text(
                json.dumps(
                    {
                        "name": name,
                        "columns": [
                            {
                                "name": j(attr_value(c, "name")),
                                "type": j(attr_value(c, "type")),
                                "width": j(
                                    attr_value(
                                        c,
                                        "width",
                                        pkg.string_pool.long_string_refs,
                                    )
                                ),
                                "primary_key": j(attr_value(c, "primary_key",)),
                                "nullable": j(attr_value(c, "nullable")),
                                "localizable": j(attr_value(c, "localizable")),
                            }
                            for c in table.columns
                        ],
                        "rows": j(rows),
                    },
                    indent=2,
                    ensure_ascii=False,
                ),
                encoding="utf-8",
            )
            with (out / "tables" / f"{stem}.csv").open(
                "w", newline="", encoding="utf-8-sig"
            ) as f:
                w = csv.DictWriter(f, fieldnames=[c.name for c in table.columns])
                w.writeheader()
                for r in rows:
                    w.writerow(
                        {
                            c.name: (
                                json.dumps(j(r.get(c.name)), ensure_ascii=False)
                                if isinstance(
                                    r.get(c.name),
                                    (bytes, bytearray, memoryview, dict, list, tuple),
                                )
                                else r.get(c.name)
                            )
                            for c in table.columns
                        }
                    )
            table_manifest.append(
                {"name": name, "rows": len(rows), "columns": len(table.columns)}
            )

        streams = []
        try:
            stream_paths = pkg.ole.listdir(streams=True, storages=False)
        except Exception:
            stream_paths = []
        tree = []
        try:
            storages = pkg.ole.listdir(streams=False, storages=True)
            tree.extend("STORAGE: " + " / ".join(p) for p in storages)
        except Exception as e:
            tree.append("ERROR listing storages: " + repr(e))
        for i, path in enumerate(sorted(stream_paths, key=lambda p: tuple(p)), 1):
            raw = path[-1]
            try:
                logical, is_table = pymsi.streamname.decode_unicode(raw)
            except Exception:
                logical, is_table = raw, False
            with pkg.ole.openstream(path) as stream:
                data = stream.read()
            name = f"{i:04d}__{safe(logical)}.bin"
            (out / "streams" / name).write_bytes(data)
            streams.append(
                {
                    "index": i,
                    "ole_path": list(path),
                    "raw_name": raw,
                    "logical_name": logical,
                    "is_table_stream": is_table,
                    "size": len(data),
                    "sha256": hashlib.sha256(data).hexdigest(),
                    "file": f"streams/{name}",
                }
            )
            tree.append(
                ("TABLE: " if is_table else "STREAM: ")
                + "/".join(path)
                + f" -> {logical!r} ({len(data)} bytes)"
            )
        (out / "metadata" / "ole-tree.txt").write_text(
            "\n".join(tree) + "\n", encoding="utf-8"
        )
        manifest["tables"] = table_manifest
        manifest["streams"] = streams

    jobs = {
        "tables.txt": ["tables", str(src)],
        "dump.txt": ["dump", "--no-strict", str(src)],
        "suminfo.txt": ["suminfo", str(src)],
        "analysis.json": ["analyze", "--no-strict", "--json", str(src)],
        "customactions.json": ["customactions", "--no-strict", "--json", str(src)],
        "test.txt": ["test", "--no-strict", str(src)],
    }
    cli = {}
    for file, args in jobs.items():
        rc = run_pymsi(args, out / "reports" / f"pymsi-{file}")
        cli[file] = rc
    manifest["cli"] = cli

    files_rc = run_pymsi(
        ["extract", "--no-strict", str(src), "--output", str(out / "files")],
        out / "reports" / "pymsi-extract.txt",
    )
    manifest["file_extraction_returncode"] = files_rc
    manifest["extracted_file_count"] = sum(
        1 for p in (out / "files").rglob("*") if p.is_file()
    )

    # Normalize all pymsi-native values (including datetime instances) before JSON output.
    normalized_manifest = j(manifest)
    (out / "metadata" / "summary.json").write_text(
        json.dumps(normalized_manifest["summary"], indent=2, ensure_ascii=False),
        encoding="utf-8",
    )
    (out / "metadata" / "manifest.json").write_text(
        json.dumps(normalized_manifest, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )
    print(
        json.dumps(
            {
                "status": "ok",
                "pymsi_version": normalized_manifest["version"],
                "tables": len(table_manifest),
                "streams": len(streams),
                "files": normalized_manifest["extracted_file_count"],
                "strict_validation": strict,
                "file_extraction_returncode": files_rc,
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
