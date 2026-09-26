from __future__ import annotations

import ctypes
from ctypes import POINTER, Structure, byref
from ctypes import c_int32, c_uint16, c_uint32, c_ubyte, c_void_p, c_wchar_p
from dataclasses import dataclass
from pathlib import Path

from .core import require_existing_file, require_windows
from .errors import TrustVerificationError

WTD_UI_NONE = 2
WTD_REVOKE_WHOLECHAIN = 1
WTD_CHOICE_FILE = 1
WTD_STATEACTION_VERIFY = 1
WTD_STATEACTION_CLOSE = 2
WTD_REVOCATION_CHECK_CHAIN_EXCLUDE_ROOT = 0x00000080
WTD_UICONTEXT_INSTALL = 1
ERROR_SUCCESS = 0


class GUID(Structure):
    _fields_ = [
        ("Data1", c_uint32),
        ("Data2", c_uint16),
        ("Data3", c_uint16),
        ("Data4", c_ubyte * 8),
    ]

    @classmethod
    def from_text(cls, value: str) -> "GUID":
        parts = value.strip().strip("{}").split("-")
        if len(parts) != 5:
            raise ValueError(f"invalid GUID: {value!r}")
        tail = bytes.fromhex(parts[3] + parts[4])
        if len(tail) != 8:
            raise ValueError(f"invalid GUID: {value!r}")
        return cls(
            int(parts[0], 16),
            int(parts[1], 16),
            int(parts[2], 16),
            (c_ubyte * 8)(*tail),
        )


class WINTRUST_FILE_INFO(Structure):
    _fields_ = [
        ("cbStruct", c_uint32),
        ("pcwszFilePath", c_wchar_p),
        ("hFile", c_void_p),
        ("pgKnownSubject", POINTER(GUID)),
    ]


class WINTRUST_DATA(Structure):
    # Match the documented WinSDK field order. The installed wintrust.h is canonical.
    _fields_ = [
        ("cbStruct", c_uint32),
        ("pPolicyCallbackData", c_void_p),
        ("pSIPClientData", c_void_p),
        ("dwUIChoice", c_uint32),
        ("fdwRevocationChecks", c_uint32),
        ("dwUnionChoice", c_uint32),
        ("pFile", POINTER(WINTRUST_FILE_INFO)),
        ("dwStateAction", c_uint32),
        ("hWVTStateData", c_void_p),
        ("pwszURLReference", c_wchar_p),
        ("dwProvFlags", c_uint32),
        ("dwUIContext", c_uint32),
        ("pSignatureSettings", c_void_p),
    ]


@dataclass(frozen=True)
class TrustResult:
    path: Path
    status: int

    @property
    def trusted(self) -> bool:
        return self.status == ERROR_SUCCESS


_GENERIC_VERIFY_V2 = GUID.from_text("00AAC56B-CD44-11D0-8CC2-00C04FC295EE")


def verify_authenticode(path: str | Path) -> TrustResult:
    """Return the WinTrust outcome and raw status for one local file."""
    require_windows()
    file_path = require_existing_file(path)

    wintrust = ctypes.WinDLL("wintrust.dll", use_last_error=True)
    function = wintrust.WinVerifyTrust
    function.argtypes = [c_void_p, POINTER(GUID), c_void_p]
    function.restype = c_int32

    file_info = WINTRUST_FILE_INFO(
        cbStruct=ctypes.sizeof(WINTRUST_FILE_INFO),
        pcwszFilePath=str(file_path),
        hFile=None,
        pgKnownSubject=None,
    )
    trust_data = WINTRUST_DATA(
        cbStruct=ctypes.sizeof(WINTRUST_DATA),
        pPolicyCallbackData=None,
        pSIPClientData=None,
        dwUIChoice=WTD_UI_NONE,
        fdwRevocationChecks=WTD_REVOKE_WHOLECHAIN,
        dwUnionChoice=WTD_CHOICE_FILE,
        pFile=ctypes.pointer(file_info),
        dwStateAction=WTD_STATEACTION_VERIFY,
        hWVTStateData=None,
        pwszURLReference=None,
        dwProvFlags=WTD_REVOCATION_CHECK_CHAIN_EXCLUDE_ROOT,
        dwUIContext=WTD_UICONTEXT_INSTALL,
        pSignatureSettings=None,
    )

    status = ERROR_SUCCESS
    try:
        status = int(function(None, byref(_GENERIC_VERIFY_V2), byref(trust_data)))
    finally:
        # WinVerifyTrust may allocate provider state; always pair VERIFY with CLOSE.
        trust_data.dwStateAction = WTD_STATEACTION_CLOSE
        function(None, byref(_GENERIC_VERIFY_V2), byref(trust_data))
    return TrustResult(file_path, status)


def require_trusted(path: str | Path) -> TrustResult:
    result = verify_authenticode(path)
    if not result.trusted:
        raise TrustVerificationError(
            f"WinVerifyTrust rejected {result.path}; raw status={result.status}"
        )
    return result
