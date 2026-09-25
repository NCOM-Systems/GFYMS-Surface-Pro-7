//! Windows counted Unicode string compatibility primitives.

use crate::status::NtStatus;

/// Windows WCHAR width in bytes.
pub const WCHAR_SIZE: usize = 2;

/// Windows UNICODE_STRING-compatible layout.
///
/// Length and MaximumLength are byte counts, not UTF-16 code-unit counts.
/// Buffer is not required to be NUL-terminated.
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

    /// Returns the number of UTF-16 code units represented by length.
    pub const fn len_units(&self) -> usize {
        self.length as usize / WCHAR_SIZE
    }

    /// Returns the number of UTF-16 code units available in the backing buffer.
    pub const fn capacity_units(&self) -> usize {
        self.maximum_length as usize / WCHAR_SIZE
    }

    /// Returns true when the descriptor is internally well-formed.
    pub fn is_well_formed(&self) -> bool {
        self.length <= self.maximum_length
            && self.length % WCHAR_SIZE as u16 == 0
            && self.maximum_length % WCHAR_SIZE as u16 == 0
            && (self.length == 0 || !self.buffer.is_null())
    }

    /// Views the counted string as UTF-16 code units.
    ///
    /// # Safety
    ///
    /// The caller must ensure the buffer pointer remains valid for len_units
    /// UTF-16 elements for the duration of the returned borrow.
    pub unsafe fn as_units<'a>(&'a self) -> &'a [u16] {
        unsafe { core::slice::from_raw_parts(self.buffer, self.len_units()) }
    }
}

/// Initializes a counted UTF-16 string descriptor from caller-owned storage.
///
/// The source slice is not copied and must outlive the returned descriptor use.
pub fn rtl_init_unicode_string(target: &mut UnicodeString, source: Option<&[u16]>) -> NtStatus {
    let Some(source) = source else {
        *target = UnicodeString::empty();
        return NtStatus::SUCCESS;
    };

    let Some(length_bytes) = source.len().checked_mul(WCHAR_SIZE) else {
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

/// Copies a counted Unicode string into an existing destination buffer.
///
/// The destination length is updated to the number of code units copied.
/// When the destination has room for a terminator, it is written immediately
/// after the copied string.
pub fn rtl_copy_unicode_string(destination: &mut UnicodeString, source: &UnicodeString) -> NtStatus {
    if !destination.is_well_formed() || !source.is_well_formed() {
        return NtStatus::INVALID_PARAMETER;
    }
    if source.length > 0 && source.buffer.is_null() {
        return NtStatus::INVALID_PARAMETER;
    }
    if destination.maximum_length > 0 && destination.buffer.is_null() {
        return NtStatus::INVALID_PARAMETER;
    }

    let destination_capacity = destination.maximum_length as usize;
    let source_length = source.length as usize;
    let copy_bytes = source_length.min(destination_capacity.saturating_sub(WCHAR_SIZE));

    if destination.maximum_length == 0 {
        destination.length = 0;
        return if source_length == 0 {
            NtStatus::SUCCESS
        } else {
            NtStatus::BUFFER_TOO_SMALL
        };
    }

    if copy_bytes > 0 {
        unsafe {
            core::ptr::copy_nonoverlapping(
                source.buffer.cast_const(),
                destination.buffer,
                copy_bytes / WCHAR_SIZE,
            );
            *destination.buffer.add(copy_bytes / WCHAR_SIZE) = 0;
        }
    } else {
        unsafe {
            *destination.buffer = 0;
        }
    }

    destination.length = copy_bytes as u16;

    if copy_bytes < source_length {
        NtStatus::BUFFER_TOO_SMALL
    } else {
        NtStatus::SUCCESS
    }
}

/// Compares two counted UTF-16 strings lexicographically by code unit.
pub fn rtl_compare_unicode_string(left: &UnicodeString, right: &UnicodeString) -> Result<i32, NtStatus> {
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
        value.encode_utf16().collect()
    }

    #[test]
    fn init_preserves_counted_string_layout() {
        let source = units("Surface");
        let mut string = UnicodeString::default();

        assert_eq!(rtl_init_unicode_string(&mut string, Some(&source)), NtStatus::SUCCESS);
        assert_eq!(string.length, 14);
        assert_eq!(string.maximum_length, 16);
        assert_eq!(string.len_units(), 7);
        assert_eq!(unsafe { string.as_units() }, source.as_slice());
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
    fn copy_uses_counted_lengths_and_terminates_when_possible() {
        let source_units = units("Surface");
        let mut source = UnicodeString::default();
        assert_eq!(
            rtl_init_unicode_string(&mut source, Some(&source_units)),
            NtStatus::SUCCESS
        );

        let mut destination_storage = [0u16; 8];
        let mut destination = UnicodeString {
            length: 0,
            maximum_length: 16,
            buffer: destination_storage.as_mut_ptr(),
        };

        assert_eq!(
            rtl_copy_unicode_string(&mut destination, &source),
            NtStatus::SUCCESS
        );
        assert_eq!(destination_storage[7], 0);
        assert_eq!(
            unsafe { core::slice::from_raw_parts(destination.buffer, destination.len_units()) },
            source_units.as_slice()
        );
    }

    #[test]
    fn copy_reports_truncation() {
        let source_units = units("Surface Pro 7");
        let mut source = UnicodeString::default();
        assert_eq!(
            rtl_init_unicode_string(&mut source, Some(&source_units)),
            NtStatus::SUCCESS
        );

        let mut destination_storage = [0u16; 8];
        let mut destination = UnicodeString {
            length: 0,
            maximum_length: 8,
            buffer: destination_storage.as_mut_ptr(),
        };

        assert_eq!(
            rtl_copy_unicode_string(&mut destination, &source),
            NtStatus::BUFFER_TOO_SMALL
        );
        assert_eq!(destination.len_units(), 3);
        assert_eq!(&destination_storage[..4], &[83, 117, 114, 0]);
    }

    #[test]
    fn compare_is_counted_not_terminator_based() {
        let left_storage = units("abc");
        let right_storage = units("abd");
        let mut left = UnicodeString::default();
        let mut right = UnicodeString::default();
        rtl_init_unicode_string(&mut left, Some(&left_storage));
        rtl_init_unicode_string(&mut right, Some(&right_storage));

        assert_eq!(rtl_compare_unicode_string(&left, &right).unwrap(), -1);
        assert_eq!(rtl_compare_unicode_string(&left, &left).unwrap(), 0);
    }
}
