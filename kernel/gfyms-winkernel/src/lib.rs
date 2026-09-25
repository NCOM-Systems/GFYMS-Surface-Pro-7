#![forbid(unsafe_op_in_unsafe_fn)]
#![deny(missing_docs)]

//! Linux-side primitives for the GFYMS Windows-kernel compatibility boundary.
//!
//! This crate does not load or execute Microsoft Windows kernel binaries.
//! It provides explicit, testable representations of Windows-facing ABI
//! semantics that higher layers can translate onto native Linux mechanisms.

pub mod status;
pub mod sync;
pub mod unicode;
