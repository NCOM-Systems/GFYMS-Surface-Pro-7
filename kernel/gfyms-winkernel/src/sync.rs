//! Windows dispatcher-event semantics implemented with native Rust synchronization.

use std::sync::{Condvar, Mutex};
use std::time::{Duration, Instant};

use crate::status::NtStatus;

/// Windows event type.
#[derive(Clone, Copy, Debug, Eq, PartialEq)]
pub enum EventType {
    /// A notification event wakes all eligible waiters and stays signaled.
    Notification,
    /// A synchronization event releases one waiter and then becomes unsignaled.
    Synchronization,
}

#[derive(Debug)]
struct EventState {
    event_type: EventType,
    signaled: bool,
}

/// Linux-side representation of a Windows event dispatcher object.
#[derive(Debug)]
pub struct KernelEvent {
    state: Mutex<EventState>,
    wake: Condvar,
}

impl KernelEvent {
    /// Creates an event with the requested type and initial state.
    pub fn new(event_type: EventType, initial_state: bool) -> Self {
        Self {
            state: Mutex::new(EventState {
                event_type,
                signaled: initial_state,
            }),
            wake: Condvar::new(),
        }
    }

    /// Reinitializes the event to the requested type and state.
    pub fn initialize(&self, event_type: EventType, initial_state: bool) {
        let mut state = self.state.lock().expect("event mutex poisoned");
        state.event_type = event_type;
        state.signaled = initial_state;
        self.wake.notify_all();
    }

    /// Returns whether the event is currently signaled.
    pub fn read_state(&self) -> bool {
        self.state.lock().expect("event mutex poisoned").signaled
    }

    /// Sets the event and returns its previous state.
    pub fn set(&self) -> bool {
        let mut state = self.state.lock().expect("event mutex poisoned");
        let previous = state.signaled;
        state.signaled = true;
        match state.event_type {
            EventType::Notification => self.wake.notify_all(),
            EventType::Synchronization => self.wake.notify_one(),
        }
        previous
    }

    /// Resets the event and returns its previous state.
    pub fn reset(&self) -> bool {
        let mut state = self.state.lock().expect("event mutex poisoned");
        let previous = state.signaled;
        state.signaled = false;
        previous
    }

    /// Waits until the event can satisfy a waiter or the optional timeout expires.
    pub fn wait(&self, timeout: Option<Duration>) -> NtStatus {
        let mut state = self.state.lock().expect("event mutex poisoned");

        match timeout {
            None => {
                while !state.signaled {
                    state = self.wake.wait(state).expect("event mutex poisoned");
                }
            }
            Some(timeout) => {
                let deadline = Instant::now() + timeout;
                while !state.signaled {
                    let remaining = deadline.saturating_duration_since(Instant::now());
                    if remaining.is_zero() {
                        return NtStatus::TIMEOUT;
                    }
                    let (next, result) = self
                        .wake
                        .wait_timeout(state, remaining)
                        .expect("event mutex poisoned");
                    state = next;
                    if result.timed_out() && !state.signaled {
                        return NtStatus::TIMEOUT;
                    }
                }
            }
        }

        if state.event_type == EventType::Synchronization {
            state.signaled = false;
        }

        NtStatus::SUCCESS
    }
}

/// Compatibility wrapper for KeInitializeEvent.
pub fn ke_initialize_event(event: &KernelEvent, event_type: EventType, initial_state: bool) {
    event.initialize(event_type, initial_state);
}

/// Compatibility wrapper for KeSetEvent.
pub fn ke_set_event(event: &KernelEvent) -> bool {
    event.set()
}

/// Compatibility wrapper for KeResetEvent.
pub fn ke_reset_event(event: &KernelEvent) -> bool {
    event.reset()
}

/// Compatibility wrapper for KeReadStateEvent.
pub fn ke_read_state_event(event: &KernelEvent) -> bool {
    event.read_state()
}

/// Compatibility wrapper for KeWaitForSingleObject(event, timeout).
pub fn ke_wait_for_single_object(event: &KernelEvent, timeout: Option<Duration>) -> NtStatus {
    event.wait(timeout)
}

#[cfg(test)]
mod tests {
    use super::{
        ke_read_state_event, ke_reset_event, ke_set_event, ke_wait_for_single_object, EventType,
        KernelEvent,
    };
    use crate::status::NtStatus;
    use std::time::Duration;

    #[test]
    fn notification_event_stays_signaled_until_reset() {
        let event = KernelEvent::new(EventType::Notification, false);

        assert!(!ke_read_state_event(&event));
        assert!(!ke_set_event(&event));
        assert!(ke_read_state_event(&event));
        assert_eq!(
            ke_wait_for_single_object(&event, Some(Duration::ZERO)),
            NtStatus::SUCCESS
        );
        assert_eq!(
            ke_wait_for_single_object(&event, Some(Duration::ZERO)),
            NtStatus::SUCCESS
        );
        assert!(ke_reset_event(&event));
        assert!(!ke_read_state_event(&event));
        assert_eq!(
            ke_wait_for_single_object(&event, Some(Duration::ZERO)),
            NtStatus::TIMEOUT
        );
    }

    #[test]
    fn synchronization_event_consumes_signal() {
        let event = KernelEvent::new(EventType::Synchronization, false);

        assert!(!ke_set_event(&event));
        assert_eq!(ke_wait_for_single_object(&event, Some(Duration::ZERO)), NtStatus::SUCCESS);
        assert!(!ke_read_state_event(&event));
        assert_eq!(ke_wait_for_single_object(&event, Some(Duration::ZERO)), NtStatus::TIMEOUT);
    }

    #[test]
    fn reset_reports_previous_state() {
        let event = KernelEvent::new(EventType::Notification, true);
        assert!(ke_reset_event(&event));
        assert!(!ke_reset_event(&event));
    }

    #[test]
    fn timeout_does_not_change_unsignaled_state() {
        let event = KernelEvent::new(EventType::Notification, false);
        assert_eq!(
            ke_wait_for_single_object(&event, Some(Duration::from_millis(1))),
            NtStatus::TIMEOUT
        );
        assert!(!ke_read_state_event(&event));
    }
}
