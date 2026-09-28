#![forbid(unsafe_op_in_unsafe_fn)]
#![deny(missing_docs)]

//! Safe first milestone of the GFYMS WinRunner runtime.
//!
//! This crate parses/maps PE images and models NT executive, WDM/IRP, and
//! memory semantics, but deliberately does not invoke arbitrary vendor code
//! yet. The execution boundary remains explicit and test-only until hardware
//! qualification exists.

pub mod executive;
pub mod loader;
pub mod memory;
pub mod status;
pub mod sync;
pub mod unicode;
pub mod wdm;
