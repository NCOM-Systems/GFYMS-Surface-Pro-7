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
