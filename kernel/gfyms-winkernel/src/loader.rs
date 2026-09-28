//! Safe first-stage PE/COFF loader for WinRunner.
//!
//! The loader validates and maps x86_64 PE images, applies base relocations,
//! resolves imports through an explicit resolver, and seals the mapped image.
//! It intentionally stops before `DriverEntry`: no arbitrary vendor code is
//! executed by this crate yet.
use crate::memory::{MemoryAllocation, MemoryKind, MemoryManager, MemoryProtection, VirtualAddress, PAGE_SIZE};
use crate::status::NtStatus;

const DOS_MAGIC: u16 = 0x5A4D;
const PE_SIGNATURE: u32 = 0x0000_4550;
const AMD64_MACHINE: u16 = 0x8664;
const OPTIONAL_MAGIC_PE32_PLUS: u16 = 0x020B;
const IMAGE_REL_BASED_DIR64: u16 = 10;
const IMAGE_DIRECTORY_IMPORT: usize = 1;
const IMAGE_DIRECTORY_BASERELOC: usize = 5;
const SECTION_HEADER_SIZE: usize = 40;
const DATA_DIRECTORY_SIZE: usize = 8;

/// A PE data-directory location.
#[derive(Clone, Copy, Debug, Default, Eq, PartialEq)]
pub struct DataDirectory {
    /// Relative virtual address of the directory.
    pub rva: u32,
    /// Directory size in bytes.
    pub size: u32,
}

/// A validated PE section header.
#[derive(Clone, Debug, Eq, PartialEq)]
pub struct Section {
    /// Section name, without trailing NUL bytes.
    pub name: String,
    /// Virtual address relative to the image base.
    pub virtual_address: u32,
    /// Size occupied in memory.
    pub virtual_size: u32,
    /// File offset of raw section data.
    pub raw_offset: u32,
    /// Size of raw section data.
    pub raw_size: u32,
    /// PE section characteristics.
    pub characteristics: u32,
}

/// A parsed and bounds-checked PE32+ image.
#[derive(Clone, Debug)]
pub struct PeImage {
    bytes: Vec<u8>,
    /// Preferred image base from the optional header.
    pub image_base: u64,
    /// Entry-point RVA. The first loader never invokes it.
    pub entry_rva: u32,
    /// Size of the complete mapped image.
    pub size_of_image: u32,
    /// Size of headers copied into the mapped image.
    pub size_of_headers: u32,
    /// Section alignment requested by the image.
    pub section_alignment: u32,
    /// Validated image sections.
    pub sections: Vec<Section>,
    directories: [DataDirectory; 16],
}

/// Import symbol requested by a PE image.
#[derive(Clone, Debug, Eq, PartialEq)]
pub enum ImportSymbol {
    /// Named import.
    Name(String),
    /// Ordinal import.
    Ordinal(u16),
}

/// A resolved import recorded in the loaded image.
#[derive(Clone, Debug, Eq, PartialEq)]
pub struct ResolvedImport {
    /// Imported module name.
    pub module: String,
    /// Imported symbol.
    pub symbol: ImportSymbol,
    /// Address supplied by the resolver.
    pub address: u64,
    /// IAT slot address in the mapped image.
    pub slot: VirtualAddress,
}

/// Result of mapping and sealing a PE image.
#[derive(Clone, Debug)]
pub struct LoadedImage {
    /// Backing allocation for the mapped image.
    pub allocation: MemoryAllocation,
    /// Resolved entry point address. It is metadata, not a callable pointer.
    pub entry_point: VirtualAddress,
    /// Imports bound during loading.
    pub imports: Vec<ResolvedImport>,
}

/// Explicit import resolver supplied by a future NT/WDM host.
pub trait ImportResolver {
    /// Resolve a module/symbol pair to a host address.
    fn resolve(&self, module: &str, symbol: &ImportSymbol) -> Option<u64>;
}

impl<F> ImportResolver for F
where
    F: Fn(&str, &ImportSymbol) -> Option<u64>,
{
    fn resolve(&self, module: &str, symbol: &ImportSymbol) -> Option<u64> {
        self(module, symbol)
    }
}

impl PeImage {
    /// Parses and validates an AMD64 PE32+ image without mapping or executing it.
    pub fn parse(bytes: &[u8]) -> Result<Self, NtStatus> {
        if read_u16(bytes, 0)? != DOS_MAGIC {
            return Err(NtStatus::INVALID_IMAGE_FORMAT);
        }
        let nt_offset = usize::try_from(read_u32(bytes, 0x3c)?).map_err(|_| NtStatus::INVALID_IMAGE_FORMAT)?;
        if read_u32(bytes, nt_offset)? != PE_SIGNATURE {
            return Err(NtStatus::INVALID_IMAGE_FORMAT);
        }
        let coff = nt_offset.checked_add(4).ok_or(NtStatus::INVALID_IMAGE_FORMAT)?;
        let machine = read_u16(bytes, coff)?;
        if machine != AMD64_MACHINE {
            return Err(NtStatus::IMAGE_MACHINE_TYPE_MISMATCH);
        }
        let section_count = usize::from(read_u16(bytes, coff + 2)?);
        let optional_size = usize::from(read_u16(bytes, coff + 16)?);
        let optional = coff.checked_add(20).ok_or(NtStatus::INVALID_IMAGE_FORMAT)?;
        if optional_size < 112 || optional.checked_add(optional_size).ok_or(NtStatus::INVALID_IMAGE_FORMAT)? > bytes.len() {
            return Err(NtStatus::INVALID_IMAGE_FORMAT);
        }
        if read_u16(bytes, optional)? != OPTIONAL_MAGIC_PE32_PLUS {
            return Err(NtStatus::INVALID_IMAGE_FORMAT);
        }
        let entry_rva = read_u32(bytes, optional + 16)?;
        let image_base = read_u64(bytes, optional + 24)?;
        let section_alignment = read_u32(bytes, optional + 32)?;
        let size_of_image = read_u32(bytes, optional + 56)?;
        let size_of_headers = read_u32(bytes, optional + 60)?;
        let directory_count = usize::try_from(read_u32(bytes, optional + 108)?).unwrap_or(0).min(16);
        if section_alignment == 0 || size_of_image == 0 || size_of_headers == 0 {
            return Err(NtStatus::INVALID_IMAGE_FORMAT);
        }
        let mut directories = [DataDirectory::default(); 16];
        let directory_start = optional.checked_add(112).ok_or(NtStatus::INVALID_IMAGE_FORMAT)?;
        for (index, directory) in directories.iter_mut().enumerate().take(directory_count) {
            let offset = directory_start.checked_add(index * DATA_DIRECTORY_SIZE).ok_or(NtStatus::INVALID_IMAGE_FORMAT)?;
            directory.rva = read_u32(bytes, offset)?;
            directory.size = read_u32(bytes, offset + 4)?;
        }
        if usize::try_from(size_of_headers).map_err(|_| NtStatus::INVALID_IMAGE_FORMAT)? > bytes.len() {
            return Err(NtStatus::INVALID_IMAGE_FORMAT);
        }
        let sections_start = optional.checked_add(optional_size).ok_or(NtStatus::INVALID_IMAGE_FORMAT)?;
        let sections_end = sections_start.checked_add(section_count.checked_mul(SECTION_HEADER_SIZE).ok_or(NtStatus::INVALID_IMAGE_FORMAT)?).ok_or(NtStatus::INVALID_IMAGE_FORMAT)?;
        if sections_end > bytes.len() {
            return Err(NtStatus::INVALID_IMAGE_FORMAT);
        }
        let mut sections = Vec::with_capacity(section_count);
        for index in 0..section_count {
            let offset = sections_start + index * SECTION_HEADER_SIZE;
            let name_bytes = &bytes[offset..offset + 8];
            let name_end = name_bytes.iter().position(|byte| *byte == 0).unwrap_or(name_bytes.len());
            let name = String::from_utf8_lossy(&name_bytes[..name_end]).into_owned();
            let virtual_size = read_u32(bytes, offset + 8)?;
            let virtual_address = read_u32(bytes, offset + 12)?;
            let raw_size = read_u32(bytes, offset + 16)?;
            let raw_offset = read_u32(bytes, offset + 20)?;
            let characteristics = read_u32(bytes, offset + 36)?;
            let raw_end = u64::from(raw_offset).checked_add(u64::from(raw_size)).ok_or(NtStatus::INVALID_IMAGE_FORMAT)?;
            if raw_size != 0 && raw_end > bytes.len() as u64 {
                return Err(NtStatus::INVALID_IMAGE_FORMAT);
            }
            if u64::from(virtual_address).checked_add(u64::from(virtual_size.max(raw_size))).ok_or(NtStatus::INVALID_IMAGE_FORMAT)? > u64::from(size_of_image) {
                return Err(NtStatus::INVALID_IMAGE_FORMAT);
            }
            sections.push(Section { name, virtual_address, virtual_size, raw_offset, raw_size, characteristics });
        }
        Ok(Self { bytes: bytes.to_vec(), image_base, entry_rva, size_of_image, size_of_headers, section_alignment, sections, directories })
    }

    /// Maps, relocates, binds imports, and seals an image as read-only metadata.
    ///
    /// The method intentionally returns a `LoadedImage` without a callable entry
    /// point. A future execution host must add an explicit, separately audited
    /// `DriverEntry` boundary.
    pub fn load<R: ImportResolver>(&self, manager: &mut MemoryManager, resolver: &R) -> Result<LoadedImage, NtStatus> {
        let size = usize::try_from(self.size_of_image).map_err(|_| NtStatus::INVALID_IMAGE_FORMAT)?;
        let allocation = manager.allocate(size, u64::from(self.section_alignment.max(PAGE_SIZE as u32)), MemoryProtection::ReadWrite, MemoryKind::Image)?;
        let result = self.load_inner(manager, allocation, resolver);
        if result.is_err() {
            let _ = manager.free(allocation);
        }
        result
    }

    fn load_inner<R: ImportResolver>(&self, manager: &mut MemoryManager, allocation: MemoryAllocation, resolver: &R) -> Result<LoadedImage, NtStatus> {
        let header_size = usize::try_from(self.size_of_headers).map_err(|_| NtStatus::INVALID_IMAGE_FORMAT)?;
        manager.write(allocation.base, &self.bytes[..header_size])?;
        for section in &self.sections {
            if section.raw_size == 0 { continue; }
            let destination = allocation.base.checked_add(u64::from(section.virtual_address)).ok_or(NtStatus::INVALID_IMAGE_FORMAT)?;
            let start = usize::try_from(section.raw_offset).map_err(|_| NtStatus::INVALID_IMAGE_FORMAT)?;
            let end = start.checked_add(usize::try_from(section.raw_size).map_err(|_| NtStatus::INVALID_IMAGE_FORMAT)?).ok_or(NtStatus::INVALID_IMAGE_FORMAT)?;
            manager.write(destination, &self.bytes[start..end])?;
        }
        let delta = allocation.base as i128 - self.image_base as i128;
        if delta != 0 { self.apply_relocations(manager, allocation, delta)?; }
        let imports = self.bind_imports(manager, allocation.base, resolver)?;
        manager.protect(allocation, MemoryProtection::ReadOnly)?;
        let entry_point = allocation.base.checked_add(u64::from(self.entry_rva)).ok_or(NtStatus::INVALID_IMAGE_FORMAT)?;
        Ok(LoadedImage { allocation, entry_point, imports })
    }

    fn apply_relocations(&self, manager: &mut MemoryManager, allocation: MemoryAllocation, delta: i128) -> Result<(), NtStatus> {
        let base = allocation.base;
        let directory = self.directories[IMAGE_DIRECTORY_BASERELOC];
        if directory.rva == 0 || directory.size == 0 { return Err(NtStatus::INVALID_IMAGE_FORMAT); }
        let mut cursor = usize::try_from(directory.rva).map_err(|_| NtStatus::INVALID_IMAGE_FORMAT)?;
        let end = cursor.checked_add(usize::try_from(directory.size).map_err(|_| NtStatus::INVALID_IMAGE_FORMAT)?).ok_or(NtStatus::INVALID_IMAGE_FORMAT)?;
        while cursor + 8 <= end {
            let page = read_u32(&self.bytes, cursor)?;
            let block_size = usize::try_from(read_u32(&self.bytes, cursor + 4)?).map_err(|_| NtStatus::INVALID_IMAGE_FORMAT)?;
            if block_size < 8 || cursor.checked_add(block_size).ok_or(NtStatus::INVALID_IMAGE_FORMAT)? > end { return Err(NtStatus::INVALID_IMAGE_FORMAT); }
            let count = (block_size - 8) / 2;
            for index in 0..count {
                let entry = read_u16(&self.bytes, cursor + 8 + index * 2)?;
                let kind = entry >> 12;
                let offset = u32::from(entry & 0x0fff);
                if kind == 0 { continue; }
                if kind != IMAGE_REL_BASED_DIR64 { return Err(NtStatus::INVALID_IMAGE_FORMAT); }
                let target = base.checked_add(u64::from(page + offset)).ok_or(NtStatus::INVALID_IMAGE_FORMAT)?;
                let mut value_bytes = [0u8; 8];
                manager.read(target, &mut value_bytes)?;
                let value = u64::from_le_bytes(value_bytes);
                let relocated = (value as i128).checked_add(delta).ok_or(NtStatus::INVALID_IMAGE_FORMAT)?;
                let relocated = u64::try_from(relocated).map_err(|_| NtStatus::INVALID_IMAGE_FORMAT)?;
                manager.protect(allocation, MemoryProtection::ReadWrite)?;
                manager.write(target, &relocated.to_le_bytes())?;
            }
            cursor += block_size;
        }
        Ok(())
    }

    fn bind_imports<R: ImportResolver>(&self, manager: &mut MemoryManager, base: VirtualAddress, resolver: &R) -> Result<Vec<ResolvedImport>, NtStatus> {
        let directory = self.directories[IMAGE_DIRECTORY_IMPORT];
        if directory.rva == 0 || directory.size == 0 { return Ok(Vec::new()); }
        let mut descriptor = usize::try_from(directory.rva).map_err(|_| NtStatus::INVALID_IMAGE_FORMAT)?;
        let end = descriptor.checked_add(usize::try_from(directory.size).map_err(|_| NtStatus::INVALID_IMAGE_FORMAT)?).ok_or(NtStatus::INVALID_IMAGE_FORMAT)?;
        let mut resolved = Vec::new();
        loop {
            if descriptor + 20 > end { return Err(NtStatus::INVALID_IMAGE_FORMAT); }
            let original_first_thunk = read_u32(&self.bytes, descriptor)?;
            let name_rva = read_u32(&self.bytes, descriptor + 12)?;
            let first_thunk = read_u32(&self.bytes, descriptor + 16)?;
            if original_first_thunk == 0 && name_rva == 0 && first_thunk == 0 { break; }
            let module = read_c_string(&self.bytes, usize::try_from(name_rva).map_err(|_| NtStatus::INVALID_IMAGE_FORMAT)?)?;
            let lookup_rva = if original_first_thunk != 0 { original_first_thunk } else { first_thunk };
            let mut index = 0u32;
            loop {
                let lookup = base.checked_add(u64::from(lookup_rva) + u64::from(index) * 8).ok_or(NtStatus::INVALID_IMAGE_FORMAT)?;
                let mut bytes = [0u8; 8]; manager.read(lookup, &mut bytes)?;
                let value = u64::from_le_bytes(bytes);
                if value == 0 { break; }
                let symbol = if (value & (1 << 63)) != 0 { ImportSymbol::Ordinal((value & 0xffff) as u16) } else {
                    let hint_name = base.checked_add(value).ok_or(NtStatus::INVALID_IMAGE_FORMAT)?;
                    let mut name = Vec::new();
                    let mut offset = hint_name.checked_add(2).ok_or(NtStatus::INVALID_IMAGE_FORMAT)?;
                    loop {
                        let mut byte = [0u8; 1]; manager.read(offset, &mut byte)?;
                        if byte[0] == 0 { break; }
                        name.push(byte[0]); offset += 1;
                    }
                    ImportSymbol::Name(String::from_utf8(name).map_err(|_| NtStatus::INVALID_IMAGE_FORMAT)?)
                };
                let address = resolver.resolve(&module, &symbol).ok_or(NtStatus::PROCEDURE_NOT_FOUND)?;
                let slot = base.checked_add(u64::from(first_thunk) + u64::from(index) * 8).ok_or(NtStatus::INVALID_IMAGE_FORMAT)?;
                manager.write(slot, &address.to_le_bytes())?;
                resolved.push(ResolvedImport { module: module.clone(), symbol, address, slot });
                index = index.checked_add(1).ok_or(NtStatus::INVALID_IMAGE_FORMAT)?;
            }
            descriptor += 20;
        }
        Ok(resolved)
    }

}

fn read_u16(bytes: &[u8], offset: usize) -> Result<u16, NtStatus> {
    let slice = bytes.get(offset..offset + 2).ok_or(NtStatus::INVALID_IMAGE_FORMAT)?;
    Ok(u16::from_le_bytes([slice[0], slice[1]]))
}
fn read_u32(bytes: &[u8], offset: usize) -> Result<u32, NtStatus> {
    let slice = bytes.get(offset..offset + 4).ok_or(NtStatus::INVALID_IMAGE_FORMAT)?;
    Ok(u32::from_le_bytes([slice[0], slice[1], slice[2], slice[3]]))
}
fn read_u64(bytes: &[u8], offset: usize) -> Result<u64, NtStatus> {
    let slice = bytes.get(offset..offset + 8).ok_or(NtStatus::INVALID_IMAGE_FORMAT)?;
    Ok(u64::from_le_bytes(slice.try_into().map_err(|_| NtStatus::INVALID_IMAGE_FORMAT)?))
}
fn read_c_string(bytes: &[u8], offset: usize) -> Result<String, NtStatus> {
    let tail = bytes.get(offset..).ok_or(NtStatus::INVALID_IMAGE_FORMAT)?;
    let end = tail.iter().position(|byte| *byte == 0).ok_or(NtStatus::INVALID_IMAGE_FORMAT)?;
    String::from_utf8(tail[..end].to_vec()).map_err(|_| NtStatus::INVALID_IMAGE_FORMAT)
}

#[cfg(test)]
mod tests {
    use super::*;

    fn minimal_pe(machine: u16) -> Vec<u8> {
        let mut image = vec![0u8; 0x400];
        image[0..2].copy_from_slice(&DOS_MAGIC.to_le_bytes());
        image[0x3c..0x40].copy_from_slice(&0x80u32.to_le_bytes());
        image[0x80..0x84].copy_from_slice(&PE_SIGNATURE.to_le_bytes());
        image[0x84..0x86].copy_from_slice(&machine.to_le_bytes());
        image[0x86..0x88].copy_from_slice(&1u16.to_le_bytes());
        image[0x94..0x96].copy_from_slice(&240u16.to_le_bytes());
        let optional = 0x98;
        image[optional..optional + 2].copy_from_slice(&OPTIONAL_MAGIC_PE32_PLUS.to_le_bytes());
        image[optional + 16..optional + 20].copy_from_slice(&0x1000u32.to_le_bytes());
        image[optional + 24..optional + 32].copy_from_slice(&0x100000000u64.to_le_bytes());
        image[optional + 32..optional + 36].copy_from_slice(&0x1000u32.to_le_bytes());
        image[optional + 36..optional + 40].copy_from_slice(&0x200u32.to_le_bytes());
        image[optional + 56..optional + 60].copy_from_slice(&0x2000u32.to_le_bytes());
        image[optional + 60..optional + 64].copy_from_slice(&0x200u32.to_le_bytes());
        image[optional + 108..optional + 112].copy_from_slice(&16u32.to_le_bytes());
        image[0x188..0x190].copy_from_slice(b".text\0\0\0");
        image[0x190..0x194].copy_from_slice(&4u32.to_le_bytes());
        image[0x194..0x198].copy_from_slice(&0x1000u32.to_le_bytes());
        image[0x198..0x19c].copy_from_slice(&4u32.to_le_bytes());
        image[0x19c..0x1a0].copy_from_slice(&0x200u32.to_le_bytes());
        image[0x1a4..0x1a8].copy_from_slice(&0x60000020u32.to_le_bytes());
        image[0x200..0x204].copy_from_slice(&[0xC3, 0, 0, 0]);
        image
    }

    #[test]
    fn parser_accepts_amd64_pe32_plus_and_rejects_other_machine() {
        let image = minimal_pe(AMD64_MACHINE);
        let parsed = PeImage::parse(&image).unwrap();
        assert_eq!(parsed.entry_rva, 0x1000);
        assert_eq!(parsed.sections[0].name, ".text");
        assert!(matches!(
            PeImage::parse(&minimal_pe(0x014c)),
            Err(NtStatus::IMAGE_MACHINE_TYPE_MISMATCH)
        ));
    }

    #[test]
    fn loader_maps_and_seals_image_without_execution() {
        let image = PeImage::parse(&minimal_pe(AMD64_MACHINE)).unwrap();
        let mut manager = MemoryManager::new();
        let resolver = |_module: &str, _symbol: &ImportSymbol| -> Option<u64> { None };
        let loaded = image.load(&mut manager, &resolver).unwrap();
        assert_eq!(loaded.entry_point, loaded.allocation.base + 0x1000);
        assert_eq!(manager.protection(loaded.allocation).unwrap(), MemoryProtection::ReadOnly);
        let mut code = [0u8; 4];
        manager.read(loaded.allocation.base + 0x1000, &mut code).unwrap();
        assert_eq!(code, [0xC3, 0, 0, 0]);
    }
}
