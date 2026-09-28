//! Safe, testable memory-management primitives used by the WinRunner loader.
//!
//! This module models a driver address space with simulated virtual addresses. It
//! deliberately does not expose raw executable pointers or turn vendor bytes into
//! callable code. That separation lets PE parsing and relocation be tested before
//! any kernel integration or hardware access is attempted.
use crate::status::NtStatus;
use std::collections::BTreeMap;

/// Simulated virtual address.
pub type VirtualAddress = u64;

/// Page size used by the first loader model.
pub const PAGE_SIZE: u64 = 4096;

/// Memory protection applied to a mapped region.
#[derive(Clone, Copy, Debug, Eq, PartialEq)]
pub enum MemoryProtection {
    /// No access is permitted.
    NoAccess,
    /// Read-only data or immutable image content.
    ReadOnly,
    /// Read/write data.
    ReadWrite,
    /// Read/execute code. The model never executes it.
    ReadExecute,
}

impl MemoryProtection {
    fn readable(self) -> bool {
        matches!(self, Self::ReadOnly | Self::ReadWrite | Self::ReadExecute)
    }

    fn writable(self) -> bool {
        matches!(self, Self::ReadWrite)
    }
}

/// Reason a region exists in the simulated address space.
#[derive(Clone, Copy, Debug, Eq, PartialEq)]
pub enum MemoryKind {
    /// Loader-owned PE image mapping.
    Image,
    /// Non-image pool allocation.
    Pool,
    /// Memory backing an MDL.
    Mdl,
}

/// NT pool class used for an allocation request.
#[derive(Clone, Copy, Debug, Eq, PartialEq)]
pub enum PoolType {
    /// Pageable pool; callers must not use it at elevated IRQL.
    Paged,
    /// Non-pageable pool suitable for interrupt-facing state.
    NonPaged,
    /// Executable pool is intentionally not provided by WinRunner.
    NonPagedNx,
}

/// Four-character allocation tag represented in native-endian byte order.
#[derive(Clone, Copy, Debug, Eq, Hash, PartialEq)]
pub struct PoolTag(pub u32);

impl PoolTag {
    /// Creates a tag from four ASCII bytes in display order.
    pub const fn from_bytes(bytes: [u8; 4]) -> Self {
        Self(u32::from_le_bytes(bytes))
    }

    /// Returns the tag in display order.
    pub const fn bytes(self) -> [u8; 4] {
        self.0.to_le_bytes()
    }
}

/// Metadata returned by an NT pool allocation.
#[derive(Clone, Copy, Debug, Eq, PartialEq)]
pub struct PoolAllocation {
    /// Backing memory allocation.
    pub allocation: MemoryAllocation,
    /// Requested pool class.
    pub pool_type: PoolType,
    /// Diagnostic allocation tag.
    pub tag: PoolTag,
    /// Requested byte count.
    pub size: usize,
}

/// A stable allocation descriptor returned by the manager.
#[derive(Clone, Copy, Debug, Eq, PartialEq)]
pub struct MemoryAllocation {
    /// Allocation base address.
    pub base: VirtualAddress,
    /// Allocation size in bytes.
    pub size: usize,
    /// Allocation kind.
    pub kind: MemoryKind,
}

#[derive(Debug)]
struct MemoryRegion {
    allocation: MemoryAllocation,
    protection: MemoryProtection,
    bytes: Vec<u8>,
}

/// A bounded, non-overlapping virtual address-space model.
#[derive(Debug)]
pub struct MemoryManager {
    next_base: VirtualAddress,
    next_id: u64,
    regions: BTreeMap<VirtualAddress, MemoryRegion>,
}

impl Default for MemoryManager {
    fn default() -> Self {
        Self::new()
    }
}

impl MemoryManager {
    /// Creates an empty manager with a high, non-null simulated address base.
    pub fn new() -> Self {
        Self {
            next_base: 0x1_0000_0000,
            next_id: 1,
            regions: BTreeMap::new(),
        }
    }

    /// Allocates zeroed memory aligned to at least `alignment` bytes.
    pub fn allocate(
        &mut self,
        size: usize,
        alignment: u64,
        protection: MemoryProtection,
        kind: MemoryKind,
    ) -> Result<MemoryAllocation, NtStatus> {
        if size == 0 || !alignment.is_power_of_two() {
            return Err(NtStatus::INVALID_PARAMETER);
        }
        let alignment = alignment.max(PAGE_SIZE);
        let size_u64 = u64::try_from(size).map_err(|_| NtStatus::INVALID_PARAMETER)?;
        let base = align_up(self.next_base, alignment).ok_or(NtStatus::INSUFFICIENT_RESOURCES)?;
        let next = base
            .checked_add(size_u64)
            .and_then(|value| value.checked_add(PAGE_SIZE))
            .ok_or(NtStatus::INSUFFICIENT_RESOURCES)?;
        let allocation = MemoryAllocation {
            base,
            size,
            kind,
        };
        let region = MemoryRegion {
            allocation,
            protection,
            bytes: vec![0; size],
        };
        self.regions.insert(base, region);
        self.next_base = next;
        self.next_id = self.next_id.saturating_add(1);
        Ok(allocation)
    }

    /// Implements an ExAllocatePool2-style request using bounded simulated memory.
    pub fn allocate_pool(
        &mut self,
        pool_type: PoolType,
        size: usize,
        tag: PoolTag,
    ) -> Result<PoolAllocation, NtStatus> {
        let protection = match pool_type {
            PoolType::Paged | PoolType::NonPaged | PoolType::NonPagedNx => {
                MemoryProtection::ReadWrite
            }
        };
        let allocation = self.allocate(size, PAGE_SIZE, protection, MemoryKind::Pool)?;
        Ok(PoolAllocation {
            allocation,
            pool_type,
            tag,
            size,
        })
    }

    /// Implements ExFreePoolWithTag-style release with tag validation.
    pub fn free_pool(
        &mut self,
        pool: PoolAllocation,
        expected_tag: PoolTag,
    ) -> Result<(), NtStatus> {
        if pool.tag != expected_tag {
            return Err(NtStatus::POOL_TAG_MISMATCH);
        }
        self.free(pool.allocation)
    }

    /// Changes protection for a complete allocation.
    pub fn protect(
        &mut self,
        allocation: MemoryAllocation,
        protection: MemoryProtection,
    ) -> Result<(), NtStatus> {
        let region = self
            .regions
            .get_mut(&allocation.base)
            .ok_or(NtStatus::MEMORY_NOT_ALLOCATED)?;
        if region.allocation != allocation {
            return Err(NtStatus::INVALID_PARAMETER);
        }
        region.protection = protection;
        Ok(())
    }

    /// Releases an allocation.
    pub fn free(&mut self, allocation: MemoryAllocation) -> Result<(), NtStatus> {
        let Some(region) = self.regions.get(&allocation.base) else {
            return Err(NtStatus::MEMORY_NOT_ALLOCATED);
        };
        if region.allocation != allocation {
            return Err(NtStatus::INVALID_PARAMETER);
        }
        self.regions.remove(&allocation.base);
        Ok(())
    }

    /// Reads bytes from a mapped region after checking protection and bounds.
    pub fn read(&self, address: VirtualAddress, output: &mut [u8]) -> Result<(), NtStatus> {
        let region = self.find(address, output.len())?;
        if !region.protection.readable() {
            return Err(NtStatus::ACCESS_DENIED);
        }
        let offset = usize::try_from(address - region.allocation.base)
            .map_err(|_| NtStatus::INVALID_PARAMETER)?;
        output.copy_from_slice(&region.bytes[offset..offset + output.len()]);
        Ok(())
    }

    /// Writes bytes to a mapped region after checking write protection and bounds.
    pub fn write(&mut self, address: VirtualAddress, input: &[u8]) -> Result<(), NtStatus> {
        let region = self.find_mut(address, input.len())?;
        if !region.protection.writable() {
            return Err(NtStatus::ACCESS_DENIED);
        }
        let offset = usize::try_from(address - region.allocation.base)
            .map_err(|_| NtStatus::INVALID_PARAMETER)?;
        region.bytes[offset..offset + input.len()].copy_from_slice(input);
        Ok(())
    }

    /// Returns the protection of an allocation.
    pub fn protection(&self, allocation: MemoryAllocation) -> Result<MemoryProtection, NtStatus> {
        let region = self
            .regions
            .get(&allocation.base)
            .ok_or(NtStatus::MEMORY_NOT_ALLOCATED)?;
        if region.allocation != allocation {
            return Err(NtStatus::INVALID_PARAMETER);
        }
        Ok(region.protection)
    }

    fn find(&self, address: VirtualAddress, length: usize) -> Result<&MemoryRegion, NtStatus> {
        let (_, region) = self
            .regions
            .range(..=address)
            .next_back()
            .ok_or(NtStatus::MEMORY_NOT_ALLOCATED)?;
        range_inside(region.allocation, address, length)?;
        Ok(region)
    }

    fn find_mut(
        &mut self,
        address: VirtualAddress,
        length: usize,
    ) -> Result<&mut MemoryRegion, NtStatus> {
        let base = self
            .regions
            .range(..=address)
            .next_back()
            .map(|(base, _)| *base)
            .ok_or(NtStatus::MEMORY_NOT_ALLOCATED)?;
        let region = self
            .regions
            .get_mut(&base)
            .ok_or(NtStatus::MEMORY_NOT_ALLOCATED)?;
        range_inside(region.allocation, address, length)?;
        Ok(region)
    }
}

/// A locked-memory descriptor used by DMA/MDL-facing APIs.
#[derive(Clone, Copy, Debug, Eq, PartialEq)]
pub struct MemoryDescriptorList {
    /// Base address covered by this descriptor.
    pub base: VirtualAddress,
    /// Number of bytes covered by this descriptor.
    pub byte_count: usize,
    locked: bool,
}

impl MemoryDescriptorList {
    /// Creates a descriptor for a validated range.
    pub fn new(
        manager: &MemoryManager,
        base: VirtualAddress,
        byte_count: usize,
    ) -> Result<Self, NtStatus> {
        manager.find(base, byte_count)?;
        Ok(Self {
            base,
            byte_count,
            locked: false,
        })
    }

    /// Marks the descriptor as locked for an I/O operation.
    pub fn lock(&mut self) -> Result<(), NtStatus> {
        if self.locked {
            return Err(NtStatus::INVALID_PARAMETER);
        }
        self.locked = true;
        Ok(())
    }

    /// Releases the lock.
    pub fn unlock(&mut self) {
        self.locked = false;
    }

    /// Returns whether the descriptor is currently locked.
    pub fn is_locked(&self) -> bool {
        self.locked
    }
}

fn range_inside(
    allocation: MemoryAllocation,
    address: VirtualAddress,
    length: usize,
) -> Result<(), NtStatus> {
    let end = address
        .checked_add(u64::try_from(length).map_err(|_| NtStatus::INVALID_PARAMETER)?)
        .ok_or(NtStatus::INVALID_PARAMETER)?;
    let allocation_end = allocation
        .base
        .checked_add(u64::try_from(allocation.size).map_err(|_| NtStatus::INVALID_PARAMETER)?)
        .ok_or(NtStatus::INVALID_PARAMETER)?;
    if address < allocation.base || end > allocation_end {
        return Err(NtStatus::INVALID_PARAMETER);
    }
    Ok(())
}

fn align_up(value: u64, alignment: u64) -> Option<u64> {
    let mask = alignment - 1;
    value.checked_add(mask).map(|aligned| aligned & !mask)
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn allocations_are_aligned_and_zeroed() {
        let mut manager = MemoryManager::new();
        let allocation = manager
            .allocate(32, 0x1000, MemoryProtection::ReadWrite, MemoryKind::Pool)
            .unwrap();
        assert_eq!(allocation.base % PAGE_SIZE, 0);
        let mut bytes = [0xff; 4];
        manager.read(allocation.base, &mut bytes).unwrap();
        assert_eq!(bytes, [0; 4]);
    }

    #[test]
    fn protection_blocks_writes_after_image_seal() {
        let mut manager = MemoryManager::new();
        let allocation = manager
            .allocate(8, PAGE_SIZE, MemoryProtection::ReadWrite, MemoryKind::Image)
            .unwrap();
        manager.write(allocation.base, &[1, 2]).unwrap();
        manager
            .protect(allocation, MemoryProtection::ReadOnly)
            .unwrap();
        assert_eq!(
            manager.write(allocation.base, &[3]),
            Err(NtStatus::ACCESS_DENIED)
        );
    }

    #[test]
    fn mdl_validates_and_tracks_lock_state() {
        let mut manager = MemoryManager::new();
        let allocation = manager
            .allocate(16, PAGE_SIZE, MemoryProtection::ReadWrite, MemoryKind::Mdl)
            .unwrap();
        let mut mdl = MemoryDescriptorList::new(&manager, allocation.base + 4, 8).unwrap();
        assert!(!mdl.is_locked());
        mdl.lock().unwrap();
        assert!(mdl.is_locked());
        assert_eq!(mdl.lock(), Err(NtStatus::INVALID_PARAMETER));
        mdl.unlock();
        assert!(!mdl.is_locked());
    }

    #[test]
    fn pool_allocations_require_the_original_tag() {
        let mut manager = MemoryManager::new();
        let tag = PoolTag::from_bytes(*b"GFYM");
        let pool = manager.allocate_pool(PoolType::NonPagedNx, 64, tag).unwrap();
        assert_eq!(pool.tag.bytes(), *b"GFYM");
        assert_eq!(
            manager.free_pool(pool, PoolTag::from_bytes(*b"FAIL")),
            Err(NtStatus::POOL_TAG_MISMATCH)
        );
        manager.free_pool(pool, tag).unwrap();
    }
}
