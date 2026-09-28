//! NTSTATUS values used by the compatibility contract.

/// A Windows NTSTATUS value.
#[repr(transparent)]
#[derive(Clone, Copy, Debug, Eq, Hash, Ord, PartialEq, PartialOrd)]
pub struct NtStatus(pub i32);

impl NtStatus {
    /// Successful operation.
    pub const SUCCESS: Self = Self(0);

    /// The requested wait interval expired.
    pub const TIMEOUT: Self = Self(0x0000_0102);

    /// A supplied buffer was too small for the requested operation.
    pub const BUFFER_TOO_SMALL: Self = Self(0xC000_0023u32 as i32);

    /// A caller supplied an invalid parameter.
    pub const INVALID_PARAMETER: Self = Self(0xC000_000Du32 as i32);

    /// The requested memory or object operation is not permitted.
    pub const ACCESS_DENIED: Self = Self(0xC000_0022u32 as i32);

    /// The operation is not implemented by this compatibility layer.
    pub const NOT_SUPPORTED: Self = Self(0xC000_00BBu32 as i32);

    /// A requested allocation or executive resource was unavailable.
    pub const INSUFFICIENT_RESOURCES: Self = Self(0xC000_009Au32 as i32);

    /// The supplied handle is not valid in this object table.
    pub const INVALID_HANDLE: Self = Self(0xC000_0008u32 as i32);

    /// The object handle has the wrong object type for the requested service.
    pub const OBJECT_TYPE_MISMATCH: Self = Self(0xC000_0024u32 as i32);

    /// An object with the requested name already exists.
    pub const OBJECT_NAME_COLLISION: Self = Self(0xC000_0035u32 as i32);

    /// An object with the requested name was not found.
    pub const OBJECT_NAME_NOT_FOUND: Self = Self(0xC000_0034u32 as i32);

    /// An executive mutex or table could not be acquired safely.
    pub const EXECUTIVE_FAILURE: Self = Self(0xC000_00E5u32 as i32);

    /// A mapped address does not belong to a live allocation.
    pub const MEMORY_NOT_ALLOCATED: Self = Self(0xC000_00A0u32 as i32);

    /// The image is not a valid supported PE image.
    pub const INVALID_IMAGE_FORMAT: Self = Self(0xC000_007Bu32 as i32);

    /// The image targets a machine architecture not supported by this loader.
    pub const IMAGE_MACHINE_TYPE_MISMATCH: Self = Self(0xC000_012Fu32 as i32);

    /// A required imported symbol could not be resolved.
    pub const PROCEDURE_NOT_FOUND: Self = Self(0xC000_007Au32 as i32);

    /// The allocation tag does not match the tag supplied at allocation time.
    pub const POOL_TAG_MISMATCH: Self = Self(0xC000_02C9u32 as i32);

    /// Returns true when the status represents success or a non-error informational result.
    pub const fn is_non_error(self) -> bool {
        self.0 >= 0
    }
}

impl From<NtStatus> for i32 {
    fn from(value: NtStatus) -> Self {
        value.0
    }
}

#[cfg(test)]
mod tests {
    use super::NtStatus;

    #[test]
    fn status_values_are_stable() {
        assert_eq!(NtStatus::SUCCESS.0, 0);
        assert_eq!(NtStatus::TIMEOUT.0, 0x0102);
        assert_eq!(NtStatus::BUFFER_TOO_SMALL.0, -1_073_741_789);
        assert_eq!(NtStatus::INVALID_PARAMETER.0, -1_073_741_811);
    }

    #[test]
    fn success_classification_uses_sign_bit() {
        assert!(NtStatus::SUCCESS.is_non_error());
        assert!(NtStatus::TIMEOUT.is_non_error());
        assert!(!NtStatus::BUFFER_TOO_SMALL.is_non_error());
    }
}
