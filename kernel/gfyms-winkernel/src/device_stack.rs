//! Device-stack management and IRP routing primitives.

use crate::status::NtStatus;
use crate::wdm::{DeviceObject, DriverObject, Irp};
use std::sync::Arc;

/// One driver/device pair participating in a WDM device stack.
#[derive(Clone)]
pub struct DeviceStackEntry {
    driver: Arc<DriverObject>,
    device: Arc<DeviceObject>,
}

impl DeviceStackEntry {
    /// Creates a stack entry from a driver and its device object.
    pub fn new(driver: Arc<DriverObject>, device: Arc<DeviceObject>) -> Self {
        Self { driver, device }
    }

    /// Returns the driver backing this stack entry.
    pub fn driver(&self) -> &Arc<DriverObject> {
        &self.driver
    }

    /// Returns the device object backing this stack entry.
    pub fn device(&self) -> &Arc<DeviceObject> {
        &self.device
    }
}

/// Ordered WDM device stack.
///
/// Entries are stored from the uppermost filter/function driver at index zero
/// to the lowest driver at the final index. The manager owns routing state but
/// does not load Windows binaries or provide a PE execution environment.
#[derive(Default)]
pub struct DeviceStack {
    entries: Vec<DeviceStackEntry>,
}

impl DeviceStack {
    /// Creates an empty device stack.
    pub const fn new() -> Self {
        Self {
            entries: Vec::new(),
        }
    }

    /// Returns the number of drivers currently attached to the stack.
    pub fn len(&self) -> usize {
        self.entries.len()
    }

    /// Returns whether the stack contains no drivers.
    pub fn is_empty(&self) -> bool {
        self.entries.is_empty()
    }

    /// Returns a stack entry by upper-to-lower index.
    pub fn get(&self, index: usize) -> Option<&DeviceStackEntry> {
        self.entries.get(index)
    }

    /// Attaches a new upper filter/function-driver entry.
    ///
    /// The newest entry becomes the first dispatch target.
    pub fn attach(&mut self, driver: Arc<DriverObject>, device: Arc<DeviceObject>) -> NtStatus {
        self.entries.insert(0, DeviceStackEntry::new(driver, device));
        NtStatus::SUCCESS
    }

    /// Detaches the uppermost entry.
    pub fn detach_top(&mut self) -> Option<DeviceStackEntry> {
        if self.entries.is_empty() {
            None
        } else {
            Some(self.entries.remove(0))
        }
    }

    /// Dispatches an IRP through each stack entry from top to bottom.
    ///
    /// The current IRP stack location is aligned with the driver being invoked.
    /// A driver that completes the IRP terminates routing. Otherwise routing
    /// continues to the next lower driver. The final uncompleted status is
    /// recorded on the IRP before returning.
    pub fn dispatch(&self, irp: &mut Irp) -> NtStatus {
        if self.entries.is_empty() {
            irp.set_io_status(NtStatus::INVALID_PARAMETER, 0);
            return NtStatus::INVALID_PARAMETER;
        }

        if irp.stack_size() < self.entries.len() {
            irp.set_io_status(NtStatus::INVALID_PARAMETER, 0);
            return NtStatus::INVALID_PARAMETER;
        }

        for (index, entry) in self.entries.iter().enumerate() {
            irp.set_current_location_for_stack(index);
            let status = entry.driver().dispatch(irp, entry.device());

            if irp.is_completed() {
                return irp.io_status().status;
            }

            if status != NtStatus::SUCCESS {
                irp.set_io_status(status, 0);
                return status;
            }
        }

        irp.io_status().status
    }
}

#[cfg(test)]
mod tests {
    use super::DeviceStack;
    use crate::status::NtStatus;
    use crate::wdm::{io_complete_request, DeviceObject, DriverObject, Irp, MajorFunction};
    use std::sync::Arc;

    fn entry(name: &str) -> (Arc<DriverObject>, Arc<DeviceObject>) {
        let driver = Arc::new(DriverObject::new(name));
        let device = Arc::new(DeviceObject::new(name, format!("\\\\Device\\{name}"), 0));
        (driver, device)
    }

    #[test]
    fn attaches_in_upper_to_lower_order() {
        let mut stack = DeviceStack::new();
        let (lower_driver, lower_device) = entry("Lower");
        let (upper_driver, upper_device) = entry("Upper");

        stack.attach(lower_driver, lower_device);
        stack.attach(upper_driver, upper_device);

        assert_eq!(stack.len(), 2);
        assert_eq!(stack.get(0).unwrap().driver().name(), "Upper");
        assert_eq!(stack.get(1).unwrap().driver().name(), "Lower");
    }

    #[test]
    fn dispatches_top_to_bottom_and_preserves_order() {
        let mut stack = DeviceStack::new();
        let (lower_driver, lower_device) = entry("Lower");
        let (upper_driver, upper_device) = entry("Upper");
        let seen = Arc::new(std::sync::Mutex::new(Vec::new()));

        let seen_upper = Arc::clone(&seen);
        upper_driver
            .set_major_function(
                MajorFunction::Read,
                Some(Arc::new(move |_, _| {
                    seen_upper.lock().unwrap().push("Upper");
                    NtStatus::SUCCESS
                })),
            )
            .unwrap();

        let seen_lower = Arc::clone(&seen);
        lower_driver
            .set_major_function(
                MajorFunction::Read,
                Some(Arc::new(move |irp, _| {
                    seen_lower.lock().unwrap().push("Lower");
                    irp.set_io_status(NtStatus::SUCCESS, 9);
                    io_complete_request(irp);
                    NtStatus::SUCCESS
                })),
            )
            .unwrap();

        stack.attach(lower_driver, lower_device);
        stack.attach(upper_driver, upper_device);

        let mut irp = Irp::new(2, MajorFunction::Read).unwrap();
        assert_eq!(stack.dispatch(&mut irp), NtStatus::SUCCESS);
        assert_eq!(*seen.lock().unwrap(), vec!["Upper", "Lower"]);
        assert!(irp.is_completed());
        assert_eq!(irp.io_status().information, 9);
        assert_eq!(irp.current_location(), 1);
    }

    #[test]
    fn completed_upper_driver_stops_routing() {
        let mut stack = DeviceStack::new();
        let (lower_driver, lower_device) = entry("Lower");
        let (upper_driver, upper_device) = entry("Upper");
        let lower_called = Arc::new(std::sync::atomic::AtomicBool::new(false));

        let lower_called_clone = Arc::clone(&lower_called);
        lower_driver
            .set_major_function(
                MajorFunction::Read,
                Some(Arc::new(move |_, _| {
                    lower_called_clone.store(true, std::sync::atomic::Ordering::SeqCst);
                    NtStatus::SUCCESS
                })),
            )
            .unwrap();

        upper_driver
            .set_major_function(
                MajorFunction::Read,
                Some(Arc::new(|irp, _| {
                    irp.set_io_status(NtStatus::SUCCESS, 3);
                    io_complete_request(irp);
                    NtStatus::SUCCESS
                })),
            )
            .unwrap();

        stack.attach(lower_driver, lower_device);
        stack.attach(upper_driver, upper_device);

        let mut irp = Irp::new(2, MajorFunction::Read).unwrap();
        assert_eq!(stack.dispatch(&mut irp), NtStatus::SUCCESS);
        assert!(!lower_called.load(std::sync::atomic::Ordering::SeqCst));
        assert_eq!(irp.io_status().information, 3);
    }

    #[test]
    fn missing_stack_capacity_fails_without_dispatch() {
        let mut stack = DeviceStack::new();
        let (driver, device) = entry("Only");
        stack.attach(driver, device);

        let mut irp = Irp::new(1, MajorFunction::Read).unwrap();
        assert_eq!(stack.dispatch(&mut irp), NtStatus::INVALID_PARAMETER);

        let mut irp = Irp::new(0, MajorFunction::Read);
        assert_eq!(irp, Err(NtStatus::INVALID_PARAMETER));
    }

    #[test]
    fn empty_stack_is_an_explicit_failure() {
        let stack = DeviceStack::new();
        let mut irp = Irp::new(1, MajorFunction::Read).unwrap();

        assert_eq!(stack.dispatch(&mut irp), NtStatus::INVALID_PARAMETER);
        assert_eq!(irp.io_status().status, NtStatus::INVALID_PARAMETER);
    }

    #[test]
    fn detach_removes_only_the_uppermost_entry() {
        let mut stack = DeviceStack::new();
        let (lower_driver, lower_device) = entry("Lower");
        let (upper_driver, upper_device) = entry("Upper");
        stack.attach(lower_driver, lower_device);
        stack.attach(upper_driver, upper_device);

        assert_eq!(stack.detach_top().unwrap().driver().name(), "Upper");
        assert_eq!(stack.len(), 1);
        assert_eq!(stack.detach_top().unwrap().driver().name(), "Lower");
        assert!(stack.detach_top().is_none());
    }
}
