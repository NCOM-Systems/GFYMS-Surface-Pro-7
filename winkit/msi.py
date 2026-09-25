from __future__ import annotations

import ctypes
import re
from ctypes import POINTER, byref, c_uint32, c_wchar_p
from dataclasses import dataclass
from pathlib import Path
from typing import Iterator, Mapping

from .core import ProcessResult, require_existing_file, require_windows, run_argv, system_executable
from .errors import ManifestError, NativeCallError

UINT = c_uint32
DWORD = c_uint32
MSIHANDLE = c_uint32
LPCWSTR = c_wchar_p
LPWSTR = c_wchar_p

ERROR_SUCCESS = 0
ERROR_MORE_DATA = 234
ERROR_NO_MORE_ITEMS = 259
ERROR_INSTALL_ALREADY_RUNNING = 1618
ERROR_SUCCESS_REBOOT_INITIATED = 1641
ERROR_SUCCESS_REBOOT_REQUIRED = 3010
MSIINSTALLCONTEXT_ALL = 7

_CONTEXT_NAMES = {1: "user-managed", 2: "user-unmanaged", 4: "machine"}
_PUBLIC_PROPERTY = re.compile(r"^[A-Z][A-Z0-9_]*$")


@dataclass(frozen=True)
class MsiProduct:
    product_code: str
    context: int
    user_sid: str

    @property
    def context_name(self) -> str:
        return _CONTEXT_NAMES.get(self.context, f"unknown({self.context})")


@dataclass(frozen=True)
class MsiExecutionResult:
    process: ProcessResult

    @property
    def normalized_status(self) -> str:
        return {
            ERROR_SUCCESS: "Succeeded",
            ERROR_SUCCESS_REBOOT_REQUIRED: "SucceededRebootRequired",
            ERROR_SUCCESS_REBOOT_INITIATED: "SucceededRebootInitiated",
            ERROR_INSTALL_ALREADY_RUNNING: "RetryableBusy",
        }.get(self.process.exit_code, "Failed")


def _validate_readonly_select(sql: str) -> str:
    normalized = sql.strip()
    if not normalized:
        raise ManifestError("MSI inspection SQL must not be empty")
    if not re.match(r"(?is)^SELECT\b", normalized):
        raise ManifestError("MSI inspection SQL must start with SELECT")
    if ";" in normalized or "--" in normalized or "/*" in normalized or "*/" in normalized:
        raise ManifestError("MSI inspection SQL must be one non-commented SELECT statement")
    return normalized


class MsiNative:
    """Unicode ctypes bindings for documented msi.dll entry points."""

    def __init__(self) -> None:
        require_windows()
        self.dll = ctypes.WinDLL("msi.dll", use_last_error=True)
        self._bind()

    def _bind(self) -> None:
        self.MsiVerifyPackageW = self.dll.MsiVerifyPackageW
        self.MsiVerifyPackageW.argtypes = [LPCWSTR]
        self.MsiVerifyPackageW.restype = UINT

        self.MsiOpenDatabaseW = self.dll.MsiOpenDatabaseW
        self.MsiOpenDatabaseW.argtypes = [LPCWSTR, LPCWSTR, POINTER(MSIHANDLE)]
        self.MsiOpenDatabaseW.restype = UINT

        self.MsiDatabaseOpenViewW = self.dll.MsiDatabaseOpenViewW
        self.MsiDatabaseOpenViewW.argtypes = [MSIHANDLE, LPCWSTR, POINTER(MSIHANDLE)]
        self.MsiDatabaseOpenViewW.restype = UINT

        self.MsiViewExecute = self.dll.MsiViewExecute
        self.MsiViewExecute.argtypes = [MSIHANDLE, MSIHANDLE]
        self.MsiViewExecute.restype = UINT

        self.MsiViewFetch = self.dll.MsiViewFetch
        self.MsiViewFetch.argtypes = [MSIHANDLE, POINTER(MSIHANDLE)]
        self.MsiViewFetch.restype = UINT

        self.MsiViewClose = self.dll.MsiViewClose
        self.MsiViewClose.argtypes = [MSIHANDLE]
        self.MsiViewClose.restype = UINT

        self.MsiRecordGetFieldCount = self.dll.MsiRecordGetFieldCount
        self.MsiRecordGetFieldCount.argtypes = [MSIHANDLE]
        self.MsiRecordGetFieldCount.restype = UINT

        self.MsiRecordGetStringW = self.dll.MsiRecordGetStringW
        self.MsiRecordGetStringW.argtypes = [MSIHANDLE, UINT, LPWSTR, POINTER(DWORD)]
        self.MsiRecordGetStringW.restype = UINT

        self.MsiCloseHandle = self.dll.MsiCloseHandle
        self.MsiCloseHandle.argtypes = [MSIHANDLE]
        self.MsiCloseHandle.restype = UINT

        self.MsiEnumProductsExW = self.dll.MsiEnumProductsExW
        self.MsiEnumProductsExW.argtypes = [
            LPCWSTR, LPCWSTR, DWORD, DWORD,
            LPWSTR, POINTER(DWORD), LPWSTR, POINTER(DWORD),
        ]
        self.MsiEnumProductsExW.restype = UINT

        self.MsiGetProductInfoExW = self.dll.MsiGetProductInfoExW
        self.MsiGetProductInfoExW.argtypes = [
            LPCWSTR, LPCWSTR, DWORD, LPCWSTR, LPWSTR, POINTER(DWORD),
        ]
        self.MsiGetProductInfoExW.restype = UINT

    @staticmethod
    def _check(code: int, operation: str, *allowed: int) -> None:
        if code not in (ERROR_SUCCESS, *allowed):
            raise NativeCallError(f"{operation} failed: Win32/MSI code {code}")

    def verify_package(self, package: str | Path) -> None:
        package_path = require_existing_file(package)
        self._check(int(self.MsiVerifyPackageW(str(package_path))), "MsiVerifyPackageW")

    def open_database_readonly(self, package: str | Path) -> "MsiDatabase":
        package_path = require_existing_file(package)
        database = MSIHANDLE()
        # MSIDBOPEN_READONLY is represented by a null persistence-mode pointer.
        code = int(self.MsiOpenDatabaseW(str(package_path), None, byref(database)))
        self._check(code, "MsiOpenDatabaseW")
        return MsiDatabase(self, database)

    def iter_products(self, *, all_users: bool = False) -> Iterator[MsiProduct]:
        requested_sid = "s-1-1-0" if all_users else None
        index = 0
        while True:
            product = ctypes.create_unicode_buffer(39)
            context = DWORD()
            sid_capacity = 256
            while True:
                sid = ctypes.create_unicode_buffer(sid_capacity)
                sid_length = DWORD(sid_capacity)
                code = int(self.MsiEnumProductsExW(
                    None, requested_sid, MSIINSTALLCONTEXT_ALL, index,
                    product, byref(context), sid, byref(sid_length),
                ))
                if code == ERROR_MORE_DATA:
                    sid_capacity = max(sid_capacity * 2, int(sid_length.value) + 1)
                    continue
                break
            if code == ERROR_NO_MORE_ITEMS:
                return
            self._check(code, "MsiEnumProductsExW")
            yield MsiProduct(product.value, int(context.value), sid.value)
            index += 1

    def product_property(self, product: MsiProduct, property_name: str) -> str:
        needed = DWORD(0)
        user_sid = None if product.context == 4 else (product.user_sid or None)
        first = int(self.MsiGetProductInfoExW(
            product.product_code, user_sid, product.context,
            property_name, None, byref(needed),
        ))
        if first == ERROR_SUCCESS and needed.value == 0:
            return ""
        self._check(first, "MsiGetProductInfoExW", ERROR_MORE_DATA)
        buffer = ctypes.create_unicode_buffer(int(needed.value) + 1)
        capacity = DWORD(len(buffer))
        second = int(self.MsiGetProductInfoExW(
            product.product_code, user_sid, product.context,
            property_name, buffer, byref(capacity),
        ))
        self._check(second, "MsiGetProductInfoExW")
        return buffer.value


class MsiDatabase:
    def __init__(self, native: MsiNative, handle: MSIHANDLE) -> None:
        self.native = native
        self.handle = handle

    def close(self) -> None:
        if self.handle.value:
            self.native.MsiCloseHandle(self.handle)
            self.handle = MSIHANDLE()

    def __enter__(self) -> "MsiDatabase":
        return self

    def __exit__(self, *_: object) -> None:
        self.close()

    def query(self, sql: str) -> list[tuple[str, ...]]:
        sql = _validate_readonly_select(sql)
        view = MSIHANDLE()
        self.native._check(
            int(self.native.MsiDatabaseOpenViewW(self.handle, sql, byref(view))),
            "MsiDatabaseOpenViewW",
        )
        try:
            self.native._check(
                int(self.native.MsiViewExecute(view, MSIHANDLE(0))),
                "MsiViewExecute",
            )
            rows: list[tuple[str, ...]] = []
            while True:
                record = MSIHANDLE()
                code = int(self.native.MsiViewFetch(view, byref(record)))
                if code == ERROR_NO_MORE_ITEMS:
                    break
                self.native._check(code, "MsiViewFetch")
                try:
                    fields = [
                        self._record_string(record, field_number)
                        for field_number in range(
                            1, int(self.native.MsiRecordGetFieldCount(record)) + 1
                        )
                    ]
                    rows.append(tuple(fields))
                finally:
                    self.native.MsiCloseHandle(record)
            return rows
        finally:
            self.native.MsiViewClose(view)
            self.native.MsiCloseHandle(view)

    def _record_string(self, record: MSIHANDLE, field_number: int) -> str:
        needed = DWORD(0)
        first = int(self.native.MsiRecordGetStringW(
            record, field_number, None, byref(needed)
        ))
        if first == ERROR_SUCCESS and needed.value == 0:
            return ""
        self.native._check(first, "MsiRecordGetStringW", ERROR_MORE_DATA)
        buffer = ctypes.create_unicode_buffer(int(needed.value) + 1)
        capacity = DWORD(len(buffer))
        second = int(self.native.MsiRecordGetStringW(
            record, field_number, buffer, byref(capacity)
        ))
        self.native._check(second, "MsiRecordGetStringW")
        return buffer.value


def validate_public_properties(properties: Mapping[str, str]) -> None:
    for name, value in properties.items():
        if not isinstance(name, str) or not _PUBLIC_PROPERTY.fullmatch(name):
            raise ManifestError(
                f"property name must be uppercase public-property syntax: {name!r}"
            )
        if not isinstance(value, str) or "\x00" in value:
            raise ManifestError(f"property value must be a NUL-free string: {name!r}")


def run_msiexec(
    *,
    operation: str,
    target: str | Path,
    log_path: str | Path,
    properties: Mapping[str, str] | None = None,
    timeout: int | None = None,
) -> MsiExecutionResult:
    require_windows()
    if operation not in {"install", "uninstall"}:
        raise ManifestError("WinKIT only enables MSI install or uninstall")
    properties = properties or {}
    validate_public_properties(properties)
    if operation == "install":
        target_path = require_existing_file(target)
        target_text = str(target_path)
        action = "/package"
    else:
        target_text = str(target)
        if not target_text:
            raise ManifestError("MSI uninstall target must not be empty")
        action = "/uninstall"

    log = Path(log_path).expanduser().resolve()
    log.parent.mkdir(parents=True, exist_ok=True)
    argv = [
        system_executable("msiexec.exe"),
        action,
        target_text,
        "/quiet",
        "/norestart",
        "/log",
        log,
    ]
    argv.extend(f"{name}={value}" for name, value in properties.items())
    return MsiExecutionResult(run_argv(argv, timeout=timeout))
