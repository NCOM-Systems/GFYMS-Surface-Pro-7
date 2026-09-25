class WinKitError(RuntimeError):
    """Base error for a refused or failed WinKIT operation."""


class PlatformNotSupportedError(WinKitError):
    """Raised when a Windows-only function is called on another platform."""


class TrustVerificationError(WinKitError):
    """Raised when Authenticode verification does not return success."""


class ManifestError(WinKitError):
    """Raised when required package identity or evidence is absent or inconsistent."""


class NativeCallError(WinKitError):
    """Raised when a documented Win32 or MSI API returns an unexpected status."""
