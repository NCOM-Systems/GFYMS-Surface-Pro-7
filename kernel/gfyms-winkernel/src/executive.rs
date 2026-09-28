//! NT executive object and handle services for the WinRunner model.
//!
//! Handles are process-local capabilities. The executive owns the handle table,
//! while typed object references keep an object alive after handle duplication.
//! This is intentionally a safe Rust model; it does not expose kernel pointers.
use crate::status::NtStatus;
use crate::sync::{EventType, KernelEvent};
use std::any::Any;
use std::collections::BTreeMap;
use std::sync::{Arc, Mutex};
use std::time::Duration;

/// Process-local executive handle.
#[derive(Clone, Copy, Debug, Eq, Hash, Ord, PartialEq, PartialOrd)]
#[repr(transparent)]
pub struct Handle(u64);

impl Handle {
    /// Returns the numeric handle value for diagnostics and ABI shims.
    pub const fn value(self) -> u64 {
        self.0
    }
}

/// Object classes recognized by the first executive implementation.
#[derive(Clone, Copy, Debug, Eq, PartialEq)]
pub enum ObjectType {
    /// Dispatcher event object.
    Event,
    /// Generic section/object used by loader-facing code.
    Section,
    /// WDM driver object.
    Driver,
    /// WDM device object.
    Device,
}

struct HandleEntry {
    object_type: ObjectType,
    object: Arc<dyn Any + Send + Sync>,
}

/// The NT-style object manager and handle table.
#[derive(Default)]
pub struct ObjectManager {
    next_handle: u64,
    handles: BTreeMap<Handle, HandleEntry>,
    names: BTreeMap<String, Handle>,
}

impl ObjectManager {
    /// Creates an empty object manager.
    pub fn new() -> Self {
        Self {
            next_handle: 0x100,
            handles: BTreeMap::new(),
            names: BTreeMap::new(),
        }
    }

    /// Inserts a typed object and returns its process-local handle.
    pub fn insert<T>(
        &mut self,
        object_type: ObjectType,
        object: Arc<T>,
    ) -> Result<Handle, NtStatus>
    where
        T: Any + Send + Sync,
    {
        self.insert_raw(object_type, object)
    }

    /// Inserts a named object, rejecting duplicate names in this namespace.
    pub fn insert_named<T>(
        &mut self,
        name: impl Into<String>,
        object_type: ObjectType,
        object: Arc<T>,
    ) -> Result<Handle, NtStatus>
    where
        T: Any + Send + Sync,
    {
        let name = name.into();
        if name.is_empty() || self.names.contains_key(&name) {
            return Err(NtStatus::OBJECT_NAME_COLLISION);
        }
        let handle = self.insert(object_type, object)?;
        self.names.insert(name, handle);
        Ok(handle)
    }

    fn insert_raw(
        &mut self,
        object_type: ObjectType,
        object: Arc<dyn Any + Send + Sync>,
    ) -> Result<Handle, NtStatus> {
        let handle = Handle(self.next_handle);
        self.next_handle = self
            .next_handle
            .checked_add(4)
            .ok_or(NtStatus::INSUFFICIENT_RESOURCES)?;
        self.handles.insert(
            handle,
            HandleEntry {
                object_type,
                object,
            },
        );
        Ok(handle)
    }

    /// Returns a typed object reference for a valid handle.
    pub fn reference<T>(&self, handle: Handle, expected: ObjectType) -> Result<Arc<T>, NtStatus>
    where
        T: Any + Send + Sync,
    {
        let entry = self
            .handles
            .get(&handle)
            .ok_or(NtStatus::INVALID_HANDLE)?;
        if entry.object_type != expected {
            return Err(NtStatus::OBJECT_TYPE_MISMATCH);
        }
        Arc::clone(&entry.object)
            .downcast::<T>()
            .map_err(|_| NtStatus::OBJECT_TYPE_MISMATCH)
    }

    /// Implements an ObReferenceObjectByHandle-style typed reference.
    pub fn reference_object_by_handle<T>(
        &self,
        handle: Handle,
        expected: ObjectType,
    ) -> Result<Arc<T>, NtStatus>
    where
        T: Any + Send + Sync,
    {
        self.reference(handle, expected)
    }

    /// Resolves a named object and returns a new handle to the same object.
    pub fn open_named(&mut self, name: &str, expected: ObjectType) -> Result<Handle, NtStatus> {
        let handle = *self.names.get(name).ok_or(NtStatus::OBJECT_NAME_NOT_FOUND)?;
        if self.object_type(handle)? != expected {
            return Err(NtStatus::OBJECT_TYPE_MISMATCH);
        }
        self.duplicate(handle)
    }

    /// Duplicates a live handle to the same object.
    pub fn duplicate(&mut self, handle: Handle) -> Result<Handle, NtStatus> {
        let entry = self
            .handles
            .get(&handle)
            .ok_or(NtStatus::INVALID_HANDLE)?;
        let object_type = entry.object_type;
        let object = Arc::clone(&entry.object);
        self.insert_raw(object_type, object)
    }

    /// Closes a handle. Existing typed references keep the object alive.
    pub fn close(&mut self, handle: Handle) -> Result<(), NtStatus> {
        self.handles
            .remove(&handle)
            .map(|_| ())
            .ok_or(NtStatus::INVALID_HANDLE)?;
        self.names.retain(|_, named| *named != handle);
        Ok(())
    }

    /// Describes the object currently referenced by a handle.
    pub fn object_type(&self, handle: Handle) -> Result<ObjectType, NtStatus> {
        self.handles
            .get(&handle)
            .map(|entry| entry.object_type)
            .ok_or(NtStatus::INVALID_HANDLE)
    }
}

/// NT executive services exposed to a WinRunner instance.
#[derive(Default)]
pub struct Executive {
    objects: Mutex<ObjectManager>,
}

impl Executive {
    /// Creates a new executive instance with an empty handle table.
    pub fn new() -> Self {
        Self {
            objects: Mutex::new(ObjectManager::new()),
        }
    }

    /// Implements an NtCreateEvent/KeInitializeEvent-style service.
    pub fn nt_create_event(
        &self,
        event_type: EventType,
        initial_state: bool,
    ) -> Result<Handle, NtStatus> {
        let event = Arc::new(KernelEvent::new(event_type, initial_state));
        self.objects
            .lock()
            .map_err(|_| NtStatus::EXECUTIVE_FAILURE)?
            .insert(ObjectType::Event, event)
    }

    /// Implements NtSetEvent and returns the previous signaled state.
    pub fn nt_set_event(&self, handle: Handle) -> Result<bool, NtStatus> {
        let event = self.reference_event(handle)?;
        Ok(event.set())
    }

    /// Implements NtResetEvent and returns the previous signaled state.
    pub fn nt_reset_event(&self, handle: Handle) -> Result<bool, NtStatus> {
        let event = self.reference_event(handle)?;
        Ok(event.reset())
    }

    /// Implements NtWaitForSingleObject for dispatcher events.
    pub fn nt_wait_for_single_object(
        &self,
        handle: Handle,
        timeout: Option<Duration>,
    ) -> Result<NtStatus, NtStatus> {
        Ok(self.reference_event(handle)?.wait(timeout))
    }

    /// Implements NtDuplicateObject for this process-local table.
    pub fn nt_duplicate_object(&self, handle: Handle) -> Result<Handle, NtStatus> {
        self.objects
            .lock()
            .map_err(|_| NtStatus::EXECUTIVE_FAILURE)?
            .duplicate(handle)
    }

    /// Implements NtClose.
    pub fn nt_close(&self, handle: Handle) -> Result<(), NtStatus> {
        self.objects
            .lock()
            .map_err(|_| NtStatus::EXECUTIVE_FAILURE)?
            .close(handle)
    }

    /// Returns the object type for diagnostics and dispatch validation.
    pub fn object_type(&self, handle: Handle) -> Result<ObjectType, NtStatus> {
        self.objects
            .lock()
            .map_err(|_| NtStatus::EXECUTIVE_FAILURE)?
            .object_type(handle)
    }

    fn reference_event(&self, handle: Handle) -> Result<Arc<KernelEvent>, NtStatus> {
        self.objects
            .lock()
            .map_err(|_| NtStatus::EXECUTIVE_FAILURE)?
            .reference(handle, ObjectType::Event)
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn event_handles_support_signal_wait_duplicate_and_close() {
        let executive = Executive::new();
        let handle = executive
            .nt_create_event(EventType::Notification, false)
            .unwrap();
        assert_eq!(executive.nt_wait_for_single_object(handle, Some(Duration::ZERO)), Ok(NtStatus::TIMEOUT));
        assert!(!executive.nt_set_event(handle).unwrap());
        let duplicate = executive.nt_duplicate_object(handle).unwrap();
        assert_eq!(executive.nt_wait_for_single_object(duplicate, Some(Duration::ZERO)), Ok(NtStatus::SUCCESS));
        executive.nt_close(handle).unwrap();
        assert_eq!(executive.nt_close(handle), Err(NtStatus::INVALID_HANDLE));
        assert_eq!(executive.object_type(duplicate), Ok(ObjectType::Event));
    }

    #[test]
    fn typed_reference_rejects_wrong_object_type() {
        let mut manager = ObjectManager::new();
        let event = Arc::new(KernelEvent::new(EventType::Notification, false));
        let handle = manager.insert(ObjectType::Event, event).unwrap();
        assert_eq!(manager.reference::<KernelEvent>(handle, ObjectType::Section).unwrap_err(), NtStatus::OBJECT_TYPE_MISMATCH);
    }

    #[test]
    fn named_objects_are_openable_and_names_are_unique() {
        let mut manager = ObjectManager::new();
        let event = Arc::new(KernelEvent::new(EventType::Notification, false));
        let handle = manager
            .insert_named("\\Device\\GfymsTest", ObjectType::Device, event)
            .unwrap();
        assert_eq!(
            manager.insert_named(
                "\\Device\\GfymsTest",
                ObjectType::Device,
                Arc::new(KernelEvent::new(EventType::Notification, false))
            ),
            Err(NtStatus::OBJECT_NAME_COLLISION)
        );
        let opened = manager.open_named("\\Device\\GfymsTest", ObjectType::Device).unwrap();
        assert_ne!(opened, handle);
        manager.close(handle).unwrap();
        assert_eq!(manager.open_named("\\Device\\GfymsTest", ObjectType::Device), Err(NtStatus::OBJECT_NAME_NOT_FOUND));
    }
}
