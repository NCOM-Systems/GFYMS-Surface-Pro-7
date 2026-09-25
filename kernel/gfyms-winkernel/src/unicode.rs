//! Windows counted Unicode string compatibility primitives.

use crate::status::NtStatus;

/// Windows WCHAR width in bytes.
pub const WCHAR_SIZE: usize = 2;

/// Windows UNICODE_STRING-compatible layout.
///
/// Length and MaximumLength are byte counts, not UTF-16 code-unit counts.
/// Buffer may point at storage that is not otherwise NUL-terminated.
#[repr(C)]
#[derive(Clone, Copy, Debug)]
pub struct UnicodeString {
    /// Number of bytes currently occupied by the string.
    pub length: u16,
    /// Total byte capacity of the backing buffer.
    pub maximum_length: u16,
    /// Pointer to UTF-16 code units.
    pub buffer: *mut u16,
}

impl Default for UnicodeString {
    fn default() -> Self {
        Self {
            length: 0,
            maximum_length: 0,
            buffer: core::ptr::null_mut(),
        }
    }
}

impl UnicodeString {
    /// Creates an empty counted string.
    pub const fn empty() -> Self {
        Self {
            length: 0,
            maximum_length: 0,
            buffer: core::ptr::null_mut(),
        }
    }

    /// Returns the number of UTF-16 code units represented by Length.
    pub const fn len_units(&self) -> usize {
        self.length as usize / WCHAR_SIZE
    }

    /// Returns the number of UTF-16 code units represented by MaximumLength.
    pub const fn capacity_units(&self) -> usize {
        self.maximum_length as usize / WCHAR_SIZE
    }

    /// Returns true when the descriptor is internally well-formed.
    pub fn is_well_formed(&self) -> bool {
        self.length <= self.maximum_length
            && self.length % WCHAR_SIZE as u16 == 0
            && self.maximum_length % WCHAR_SIZE as u16 == 0
            && (self.maximum_length == 0 || !self.buffer.is_null())
    }

    /// Views the counted string as UTF-16 code units.
    ///
    /// # Safety
    ///
    /// The descriptor must contain a valid buffer for at least len_units UTF-16
    /// elements for the duration of the returned borrow.
    pub unsafe fn as_units<'a>(&'a self) -> &'a [u16] {
        unsafe { core::slice::from_raw_parts(self.buffer, self.len_units()) }
    }
}

/// Initializes a counted UTF-16 string descriptor from caller-owned NUL-terminated storage.
///
/// The source slice must contain a NUL terminator. The descriptor points at the
/// caller's storage and does not copy it.
pub fn rtl_init_unicode_string(target: &mut UnicodeString, source: Option<&[u16]>) -> NtStatus {
    let Some(source) = source else {
        *target = UnicodeString::empty();
        return NtStatus::SUCCESS;
    };

    let Some(nul_index) = source.iter().position(|unit| *unit == 0) else {
        *target = UnicodeString::empty();
        return NtStatus::INVALID_PARAMETER;
    };

    let Some(length_bytes) = nul_index.checked_mul(WCHAR_SIZE) else {
        *target = UnicodeString::empty();
        return NtStatus::INVALID_PARAMETER;
    };
    let Some(maximum_bytes) = length_bytes.checked_add(WCHAR_SIZE) else {
        *target = UnicodeString::empty();
        return NtStatus::INVALID_PARAMETER;
    };

    if maximum_bytes > u16::MAX as usize {
        *target = UnicodeString::empty();
        return NtStatus::BUFFER_TOO_SMALL;
    }

    target.length = length_bytes as u16;
    target.maximum_length = maximum_bytes as u16;
    target.buffer = source.as_ptr() as *mut u16;
    NtStatus::SUCCESS
}

/// Copies a counted Unicode string to the destination.
///
/// This mirrors the documented RtlCopyUnicodeString behavior: a NULL source
/// clears only Length, while a non-NULL source copies the smaller of Source
/// Length and Destination MaximumLength. The destination Buffer and
/// MaximumLength fields are preserved by the operation.
///
/// # Safety
///
/// The destination buffer must be valid for at least MaximumLength bytes and
/// the source buffer must be valid for Length bytes. The regions must not
/// overlap unless the underlying platform explicitly permits overlapping
/// copies for the chosen implementation.
pub unsafe fn rtl_copy_unicode_string(
    destination: &mut UnicodeString,
    source: Option<&UnicodeString>,
) {
    match source {
        None => {
            destination.length = 0;
        }
        Some(source) => {
            let copy_bytes = (source.length as usize).min(destination.maximum_length as usize);
            if copy_bytes > 0 {
                unsafe {
                    core::ptr::copy_nonoverlapping(
                        source.buffer.cast_const(),
                        destination.buffer,
                        copy_bytes / WCHAR_SIZE,
                    );
                }
            }
            destination.length = copy_bytes as u16;
        }
    }
}

/// Compares two counted UTF-16 strings lexicographically by code unit.
///
/// This first implementation models the case-sensitive form. Windows also
/// exposes a CaseInSensitive parameter; that Unicode case-folding behavior is
/// intentionally left as a separate contract until its reference semantics
/// are covered by differential tests.
pub unsafe fn rtl_compare_unicode_string(
    left: &UnicodeString,
    right: &UnicodeString,
) -> Result<i32, NtStatus> {
    if !left.is_well_formed() || !right.is_well_formed() {
        return Err(NtStatus::INVALID_PARAMETER);
    }

    let left_units = unsafe { left.as_units() };
    let right_units = unsafe { right.as_units() };
    for (a, b) in left_units.iter().zip(right_units.iter()) {
        match a.cmp(b) {
            core::cmp::Ordering::Less => return Ok(-1),
            core::cmp::Ordering::Greater => return Ok(1),
            core::cmp::Ordering::Equal => {}
        }
    }
    Ok(left_units.len().cmp(&right_units.len()) as i32)
}

#[cfg(test)]
mod tests {
    use super::{
        rtl_compare_unicode_string, rtl_copy_unicode_string, rtl_init_unicode_string, UnicodeString,
    };
    use crate::status::NtStatus;

    fn units(value: &str) -> Vec<u16> {
        let mut result: Vec<u16> = value.encode_utf16().collect();
        result.push(0);
        result
    }

    #[test]
    fn init_preserves_counted_string_layout() {
        let source = units("Surface");
        let mut string = UnicodeString::default();

        assert_eq!(
            rtl_init_unicode_string(&mut string, Some(&source)),
            NtStatus::SUCCESS
        );
        assert_eq!(string.length, 14);
        assert_eq!(string.maximum_length, 16);
        assert_eq!(string.len_units(), 7);
        assert_eq!(unsafe { string.as_units() }, &source[..7]);
    }

    #[test]
    fn init_rejects_non_terminated_source() {
        let source: Vec<u16> = "Surface".encode_utf16().collect();
        let mut string = UnicodeString::default();

        assert_eq!(
            rtl_init_unicode_string(&mut string, Some(&source)),
            NtStatus::INVALID_PARAMETER
        );
        assert_eq!(string, UnicodeString::empty());
    }

    #[test]
    fn null_source_creates_empty_descriptor() {
        let mut string = UnicodeString::default();
        assert_eq!(rtl_init_unicode_string(&mut string, None), NtStatus::SUCCESS);
        assert_eq!(string.length, 0);
        assert_eq!(string.maximum_length, 0);
        assert!(string.buffer.is_null());
    }

    #[test]
    fn copy_uses_source_length_or_destination_capacity() {
        let source_units = units("Surface");
        let mut source = UnicodeString::default();
        rtl_init_unicode_string(&mut source, Some(&source_units));

        let mut destination_storage = [0u16; 8];
        let mut destination = UnicodeString {
            length: 0,
            maximum_length: 16,
            buffer: destination_storage.as_mut_ptr(),
        };

        unsafe { rtl_copy_unicode_string(&mut destination, Some(&source)) };
        assert_eq!(destination.length, source.length);
        assert_eq!(&destination_storage[..7], &source_units[..7]);
        assert_eq!(destination_storage[7], 0);
    }

    #[test]
    fn copy_truncates_at_destination_maximum_length_without_inventing_status() {
        let source_units = units("Surface Pro 7");
        let mut source = UnicodeString::default();
        rtl_init_unicode_string(&mut source, Some(&source_units));

        let mut destination_storage = [0xAAAAu16; 8];
        let destination_buffer = destination_storage.as_mut_ptr();
        let mut destination = UnicodeString {
            length: 0,
            maximum_length: 8,
            buffer: destination_buffer,
        };

        unsafe { rtl_copy_unicode_string(&mut destination, Some(&source)) };
        assert_eq!(destination.length, 8);
        assert_eq!(&destination_storage, &source_units[..8]);
    }

    #[test]
    fn null_copy_preserves_destination_buffer_and_capacity() {
        let mut destination_storage = [0xAAAAu16; 4];
        let buffer = destination_storage.as_mut_ptr();
        let mut destination = UnicodeString {
            length: 6,
            maximum_length: 8,
            buffer,
        };

        unsafe { rtl_copy_unicode_string(&mut destination, None) };
        assert_eq!(destination.length, 0);
        assert_eq!(destination.maximum_length, 8);
        assert_eq!(destination.buffer, buffer);
        assert_eq!(destination_storage, [0xAAAA; 4]);
    }

    #[test]
    fn compare_is_counted_not_terminator_based() {
        let left_storage = units("abc");
        let right_storage = units("abd");
        let mut left = UnicodeString::default();
        let mut right = UnicodeString::default();
        rtl_init_unicode_string(&mut left, Some(&left_storage));
        rtl_init_unicode_string(&mut right, Some(&right_storage));

        assert_eq!(
            unsafe { rtl_compare_unicode_string(&left, &right) }.unwrap(),
            -1
        );
        assert_eq!(
            unsafe { rtl_compare_unicode_string(&left, &left) }.unwrap(),
            0
        );
    }
}
