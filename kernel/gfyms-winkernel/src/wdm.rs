//! Typed WDM-style driver, device, and IRP compatibility objects.

use crate::status::NtStatus;
use std::sync::atomic::{AtomicU64, Ordering};
use std::sync::{Arc, Mutex};

/// Number of standard Windows IRP major function codes.
pub const MAJOR_FUNCTION_COUNT: usize = 28;

/// Common WDM IRP major function codes.
#[repr(u8)]
#[derive(Clone, Copy, Debug, Eq, Hash, PartialEq)]
pub enum MajorFunction {
    /// IRP_MJ_CREATE.
    Create = 0x00,
    /// IRP_MJ_CLOSE.
    Close = 0x02,
    /// IRP_MJ_READ.
    Read = 0x03,
    /// IRP_MJ_WRITE.
    Write = 0x04,
    /// IRP_MJ_FLUSH_BUFFERS.
    FlushBuffers = 0x09,
    /// IRP_MJ_DEVICE_CONTROL.
    DeviceControl = 0x0E,
    /// IRP_MJ_INTERNAL_DEVICE_CONTROL.
    InternalDeviceControl = 0x0F,
    /// IRP_MJ_POWER.
    Power = 0x16,
    /// IRP_MJ_SYSTEM_CONTROL.
    SystemControl = 0x17,
    /// IRP_MJ_PNP.
    Pnp = 0x1B,
}

impl TryFrom<u8> for MajorFunction {
    type Error = ();

    /// Converts a supported numeric major-function code.
    fn try_from(value: u8) -> Result<Self, Self::Error> {
        match value {
            0x00 => Ok(Self::Create),
            0x02 => Ok(Self::Close),
            0x03 => Ok(Self::Read),
            0x04 => Ok(Self::Write),
            0x09 => Ok(Self::FlushBuffers),
            0x0E => Ok(Self::DeviceControl),
            0x0F => Ok(Self::InternalDeviceControl),
            0x16 => Ok(Self::Power),
            0x17 => Ok(Self::SystemControl),
            0x1B => Ok(Self::Pnp),
            _ => Err(()),
        }
    }
}

impl MajorFunction {
    /// Returns the Windows numeric major-function code.
    pub const fn code(self) -> u8 {
        self as u8
    }
}

/// Request-specific parameters carried by an I/O stack location.
#[derive(Clone, Debug, Eq, PartialEq)]
pub enum RequestParameters {
    /// No decoded parameters.
    None,
    /// Read/write request parameters.
    ReadWrite {
        /// Number of bytes requested.
        length: u32,
        /// Byte offset within the target.
        byte_offset: u64,
    },
    /// Device-control request parameters.
    DeviceIoControl {
        /// Device-specific IOCTL code.
        io_control_code: u32,
        /// Input buffer length.
        input_length: u32,
        /// Output buffer length.
        output_length: u32,
    },
    /// Plug-and-Play request parameters.
    PlugAndPlay {
        /// PnP minor function code.
        minor_function: u8,
    },
}

/// An I/O stack location owned by one driver in an IRP chain.
#[derive(Clone, Debug, Eq, PartialEq)]
pub struct IoStackLocation {
    /// Major function for this stack location.
    pub major_function: MajorFunction,
    /// Driver-specific minor function code.
    pub minor_function: u8,
    /// Decoded request parameters.
    pub parameters: RequestParameters,
    /// WDM stack-control flags.
    pub control: u8,
}

impl IoStackLocation {
    /// Creates an empty stack location for a major function.
    pub const fn new(major_function: MajorFunction) -> Self {
        Self {
            major_function,
            minor_function: 0,
            parameters: RequestParameters::None,
            control: 0,
        }
    }
}

/// Final completion state associated with an IRP.
#[derive(Clone, Copy, Debug, Eq, PartialEq)]
pub struct IoStatusBlock {
    /// Final NTSTATUS for the request.
    pub status: NtStatus,
    /// Request-dependent information, commonly bytes transferred.
    pub information: usize,
}

impl Default for IoStatusBlock {
    fn default() -> Self {
        Self {
            status: NtStatus::SUCCESS,
            information: 0,
        }
    }
}

/// A completion callback invoked when an IRP reaches completion.
pub type CompletionRoutine = Arc<dyn Fn(&IoStatusBlock) + Send + Sync + 'static>;

/// A dispatch routine registered for a driver's major function.
pub type DispatchRoutine =
    Arc<dyn Fn(&mut Irp, &DeviceObject) -> NtStatus + Send + Sync + 'static>;

/// A typed Windows-style I/O request packet.
pub struct Irp {
    stack: Vec<IoStackLocation>,
    current_location: usize,
    io_status: IoStatusBlock,
    completed: bool,
    completion_routines: Vec<CompletionRoutine>,
}

impl Irp {
    /// Allocates an IRP model with one stack location per participating driver.
    pub fn new(stack_size: usize, major_function: MajorFunction) -> Result<Self, NtStatus> {
        if stack_size == 0 {
            return Err(NtStatus::INVALID_PARAMETER);
        }

        Ok(Self {
            stack: vec![IoStackLocation::new(major_function); stack_size],
            current_location: 0,
            io_status: IoStatusBlock::default(),
            completed: false,
            completion_routines: Vec::new(),
        })
    }

    /// Returns the number of stack locations in this IRP.
    pub fn stack_size(&self) -> usize {
        self.stack.len()
    }

    /// Returns the current stack location.
    pub fn current_stack_location(&self) -> &IoStackLocation {
        &self.stack[self.current_location]
    }

    /// Returns the current stack location mutably.
    pub fn current_stack_location_mut(&mut self) -> &mut IoStackLocation {
        &mut self.stack[self.current_location]
    }

    /// Returns the next-lower stack location without changing the current cursor.
    pub fn next_stack_location(&self) -> Option<&IoStackLocation> {
        self.stack.get(self.current_location + 1)
    }

    /// Returns the next-lower stack location mutably without changing the current cursor.
    pub fn next_stack_location_mut(&mut self) -> Option<&mut IoStackLocation> {
        self.stack.get_mut(self.current_location + 1)
    }

    /// Copies the current stack parameters to the next-lower stack location.
    pub fn copy_current_to_next(&mut self) -> NtStatus {
        let next_index = self.current_location + 1;
        if next_index >= self.stack.len() {
            return NtStatus::INVALID_PARAMETER;
        }

        let current = self.stack[self.current_location].clone();
        self.stack[next_index] = current;
        NtStatus::SUCCESS
    }

    /// Advances this IRP to the next-lower driver's stack location.
    pub fn skip_current_stack_location(&mut self) -> NtStatus {
        if self.current_location + 1 >= self.stack.len() {
            return NtStatus::INVALID_PARAMETER;
        }

        self.current_location += 1;
        NtStatus::SUCCESS
    }

    /// Returns the current stack cursor.
    pub fn current_location(&self) -> usize {
        self.current_location
    }

    /// Records completion status and information.
    pub fn set_io_status(&mut self, status: NtStatus, information: usize) {
        self.io_status = IoStatusBlock {
            status,
            information,
        };
    }

    /// Returns the current I/O status block.
    pub fn io_status(&self) -> IoStatusBlock {
        self.io_status
    }

    /// Returns whether this IRP has been completed.
    pub fn is_completed(&self) -> bool {
        self.completed
    }

    /// Registers a completion callback.
    pub fn set_completion_routine(&mut self, routine: CompletionRoutine) {
        self.completion_routines.push(routine);
    }

    /// Completes this IRP and invokes registered completion callbacks once.
    pub fn complete(&mut self) -> bool {
        if self.completed {
            return false;
        }

        self.completed = true;
        let status = self.io_status;
        for routine in &self.completion_routines {
            routine(&status);
        }
        true
    }
}

/// A Linux-side representation of a WDM DEVICE_OBJECT.
#[derive(Clone, Debug)]
pub struct DeviceObject {
    id: u64,
    name: String,
    driver_name: String,
    flags: u32,
    extension: Arc<Mutex<Vec<u8>>>,
}

static NEXT_DEVICE_ID: AtomicU64 = AtomicU64::new(1);

impl DeviceObject {
    /// Creates a device object and zeroed device-extension storage.
    pub fn new(
        driver_name: impl Into<String>,
        name: impl Into<String>,
        extension_size: usize,
    ) -> Self {
        Self {
            id: NEXT_DEVICE_ID.fetch_add(1, Ordering::Relaxed),
            name: name.into(),
            driver_name: driver_name.into(),
            flags: 0,
            extension: Arc::new(Mutex::new(vec![0; extension_size])),
        }
    }

    /// Returns the stable process-local device identifier.
    pub fn id(&self) -> u64 {
        self.id
    }

    /// Returns the Windows device name represented by this object.
    pub fn name(&self) -> &str {
        &self.name
    }

    /// Returns the owning driver name.
    pub fn driver_name(&self) -> &str {
        &self.driver_name
    }

    /// Returns the device flags.
    pub fn flags(&self) -> u32 {
        self.flags
    }

    /// Replaces the device flags.
    pub fn set_flags(&mut self, flags: u32) {
        self.flags = flags;
    }

    /// Returns a snapshot of the device-extension bytes.
    pub fn extension(&self) -> Vec<u8> {
        self.extension
            .lock()
            .expect("device extension mutex poisoned")
            .clone()
    }

    /// Writes bytes into the device-extension storage.
    pub fn write_extension(&self, offset: usize, bytes: &[u8]) -> Result<(), NtStatus> {
        let mut extension = self
            .extension
            .lock()
            .expect("device extension mutex poisoned");
        let end = offset
            .checked_add(bytes.len())
            .ok_or(NtStatus::INVALID_PARAMETER)?;
        if end > extension.len() {
            return Err(NtStatus::INVALID_PARAMETER);
        }
        extension[offset..end].copy_from_slice(bytes);
        Ok(())
    }
}

/// A Linux-side representation of a Windows DRIVER_OBJECT dispatch table.
pub struct DriverObject {
    name: String,
    major_functions: Mutex<Vec<Option<DispatchRoutine>>>,
}

impl DriverObject {
    /// Creates a driver object with an empty dispatch table.
    pub fn new(name: impl Into<String>) -> Self {
        Self {
            name: name.into(),
            major_functions: Mutex::new(vec![None; MAJOR_FUNCTION_COUNT]),
        }
    }

    /// Returns the driver name.
    pub fn name(&self) -> &str {
        &self.name
    }

    /// Registers a dispatch routine for a supported major function.
    pub fn set_major_function(
        &self,
        major_function: MajorFunction,
        routine: Option<DispatchRoutine>,
    ) -> NtStatus {
        let mut functions = self
            .major_functions
            .lock()
            .expect("driver dispatch mutex poisoned");
        functions[major_function.code() as usize] = routine;
        NtStatus::SUCCESS
    }

    /// Dispatches an IRP to the routine registered for its current major function.
    pub fn dispatch(&self, irp: &mut Irp, device: &DeviceObject) -> NtStatus {
        let major = irp.current_stack_location().major_function;
        let routine = self
            .major_functions
            .lock()
            .expect("driver dispatch mutex poisoned")
            .get(major.code() as usize)
            .and_then(Clone::clone);

        let Some(routine) = routine else {
            irp.set_io_status(NtStatus::INVALID_PARAMETER, 0);
            return NtStatus::INVALID_PARAMETER;
        };

        let status = routine(irp, device);
        if !irp.is_completed() {
            irp.set_io_status(status, 0);
        }
        status
    }
}

/// Completes an IRP and returns whether this call transitioned it to completed.
pub fn io_complete_request(irp: &mut Irp) -> bool {
    irp.complete()
}

/// Returns the current IRP stack location.
pub fn io_get_current_irp_stack_location(irp: &Irp) -> &IoStackLocation {
    irp.current_stack_location()
}

/// Returns the next-lower IRP stack location.
pub fn io_get_next_irp_stack_location(irp: &Irp) -> Option<&IoStackLocation> {
    irp.next_stack_location()
}

/// Copies the current IRP stack parameters to the next-lower stack location.
pub fn io_copy_current_irp_stack_location_to_next(irp: &mut Irp) -> NtStatus {
    irp.copy_current_to_next()
}

/// Advances to the next-lower IRP stack location without copying parameters.
pub fn io_skip_current_irp_stack_location(irp: &mut Irp) -> NtStatus {
    irp.skip_current_stack_location()
}

#[cfg(test)]
mod tests {
    use super::{
        io_complete_request, io_copy_current_irp_stack_location_to_next,
        io_get_current_irp_stack_location, io_get_next_irp_stack_location,
        io_skip_current_irp_stack_location, CompletionRoutine, DeviceObject, DriverObject, Irp,
        MajorFunction, RequestParameters,
    };
    use crate::status::NtStatus;
    use std::sync::{Arc, Mutex};

    #[test]
    fn irp_has_explicit_stack_and_io_status() {
        let mut irp = Irp::new(2, MajorFunction::DeviceControl).unwrap();
        assert_eq!(irp.stack_size(), 2);
        assert_eq!(
            io_get_current_irp_stack_location(&irp).major_function,
            MajorFunction::DeviceControl
        );
        assert_eq!(irp.io_status(), Default::default());

        irp.current_stack_location_mut().parameters = RequestParameters::DeviceIoControl {
            io_control_code: 0x1234,
            input_length: 4,
            output_length: 8,
        };
        assert!(matches!(
            io_get_current_irp_stack_location(&irp).parameters,
            RequestParameters::DeviceIoControl {
                io_control_code: 0x1234,
                input_length: 4,
                output_length: 8
            }
        ));
    }

    #[test]
    fn stack_copy_and_skip_are_distinct_operations() {
        let mut irp = Irp::new(2, MajorFunction::Read).unwrap();
        irp.current_stack_location_mut().minor_function = 7;
        assert_eq!(
            io_copy_current_irp_stack_location_to_next(&mut irp),
            NtStatus::SUCCESS
        );
        assert_eq!(irp.next_stack_location().unwrap().minor_function, 7);
        assert_eq!(irp.current_location(), 0);

        assert_eq!(
            io_skip_current_irp_stack_location(&mut irp),
            NtStatus::SUCCESS
        );
        assert_eq!(irp.current_location(), 1);
        assert_eq!(
            io_get_current_irp_stack_location(&irp).minor_function,
            7
        );
    }

    #[test]
    fn driver_dispatch_updates_status_and_device_extension_isolated() {
        let driver = DriverObject::new("SurfaceFoo");
        let device = DeviceObject::new("SurfaceFoo", "\\Device\\SurfaceFoo", 8);
        let routine: super::DispatchRoutine = Arc::new(|irp, device| {
            device.write_extension(0, &[1, 2, 3, 4]).unwrap();
            irp.set_io_status(NtStatus::SUCCESS, 4);
            io_complete_request(irp);
            NtStatus::SUCCESS
        });
        assert_eq!(
            driver.set_major_function(MajorFunction::DeviceControl, Some(routine)),
            NtStatus::SUCCESS
        );

        let mut irp = Irp::new(1, MajorFunction::DeviceControl).unwrap();
        let status = driver.dispatch(&mut irp, &device);
        assert_eq!(status, NtStatus::SUCCESS);
        assert!(irp.is_completed());
        assert_eq!(irp.io_status().information, 4);
        assert_eq!(device.extension(), vec![1, 2, 3, 4, 0, 0, 0, 0]);
    }

    #[test]
    fn missing_dispatch_is_explicit_failure() {
        let driver = DriverObject::new("SurfaceFoo");
        let device = DeviceObject::new("SurfaceFoo", "\\Device\\SurfaceFoo", 0);
        let mut irp = Irp::new(1, MajorFunction::Read).unwrap();

        assert_eq!(
            driver.dispatch(&mut irp, &device),
            NtStatus::INVALID_PARAMETER
        );
        assert_eq!(irp.io_status(), Default::default());
    }

    #[test]
    fn completion_routines_run_once_with_final_status() {
        let mut irp = Irp::new(1, MajorFunction::Close).unwrap();
        let seen = Arc::new(Mutex::new(Vec::new()));
        let seen_clone = Arc::clone(&seen);
        let routine: CompletionRoutine = Arc::new(move |status| {
            seen_clone.lock().unwrap().push(*status);
        });

        irp.set_io_status(NtStatus::TIMEOUT, 12);
        irp.set_completion_routine(routine);
        assert!(io_complete_request(&mut irp));
        assert!(!io_complete_request(&mut irp));
        assert_eq!(*seen.lock().unwrap(), vec![NtStatus::TIMEOUT]);
    }

    #[test]
    fn next_stack_is_absent_at_bottom() {
        let mut irp = Irp::new(1, MajorFunction::Read).unwrap();
        assert!(io_get_next_irp_stack_location(&irp).is_none());
        assert_eq!(
            io_skip_current_irp_stack_location(&mut irp),
            NtStatus::INVALID_PARAMETER
        );
    }

    #[test]
    fn unknown_major_function_is_rejected() {
        assert!(MajorFunction::try_from(0xFF).is_err());
    }
}
