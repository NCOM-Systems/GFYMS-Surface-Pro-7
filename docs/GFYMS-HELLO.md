# GFYMS Hello — Surface Pro 7 biometric stack

## Goal

Give the Surface Pro 7 a first-class Linux authentication experience using the hardware Microsoft exposes for Windows Hello, without embedding the Windows Hello implementation itself.

Microsoft identifies the Surface Pro 7 as having a dedicated Windows Hello facial-recognition camera. The extracted Surface package also identifies the SP7 IR camera as an OV7251 path behind the Intel IPU4/IPU4P camera stack.

## Architecture

```text
Surface Pro 7 OV7251 IR camera
          |
          v
   Linux IPU4/IPU4P stack
          |
          v
       libcamera
          |
          v
 GFYMS Hello capture service
          |
          +--> IR face detection
          +--> liveness / presentation-attack checks
          +--> local face embedding
          +--> encrypted local credential store
          |
          v
     PAM authentication
          |
          +--> KDE / display manager
          +--> sudo / polkit
          +--> tty/login
          |
          +--> password / PIN fallback
```

## Security boundary

GFYMS Hello must never become the only recovery path. The system must retain a normal password-based recovery path and must fail closed when the camera, model, or biometric store is unavailable.

Biometric templates should remain local to the machine. Do not upload face images or embeddings. Do not make telemetry a prerequisite for authentication.

A future hardened profile can use TPM 2.0-backed sealing for the local biometric store. That should be an explicit security feature rather than an assumption.

## SP7-specific camera work

Current community reverse engineering identifies the SP7 as:

- Intel IPU4P: PCI 8086:8A19
- Front RGB: OV5693
- Rear RGB: OV8865
- IR: OV7251
- Surface camera package firmware includes `cpd_component_signed.bin`

GFYMS should treat the Windows package as provenance/reference material. The Linux camera implementation should be native and use the existing kernel/libcamera path.

## Authentication backends

The project should expose a stable GFYMS Hello interface and keep the recognition engine replaceable. Candidate Linux backends can be evaluated independently for:

- IR-only capture
- liveness / anti-spoofing
- offline inference
- PAM integration
- TPM-backed key protection
- KDE Plasma lock-screen integration
- measurable CPU/RAM cost

Do not advertise a backend as security-equivalent to Windows Hello until it has been independently evaluated for its threat model.

## Fingerprint

The Surface driver corpus contains a SurfaceFingerprintSensor.inf, but the exact fingerprint hardware/protocol still needs to be identified on the target SP7. Fingerprint support should therefore be a separate capability from face unlock and should use the standard Linux fingerprint stack where hardware support exists.

## User-visible commands

```bash
gfyms hello status
gfyms hello camera
gfyms hello enroll
gfyms hello test
gfyms hello remove
gfyms hello diagnostics
```

## Build packages

Planned Arch packages:

- `gfyms-hello-core` — policy, enrollment format, diagnostics
- `gfyms-hello-pam` — PAM module/integration
- `gfyms-hello-ir` — Surface IPU4/IPU4P IR capture adapter
- `gfyms-hello-ui` — KDE/desktop enrollment and status UI
- `gfyms-hello-tpm` — optional TPM2 protection
- `gfyms-hello-bench` — local benchmark and anti-spoof test harness

The package family should not contain Microsoft Windows Hello binaries.

## Recovery requirement

During installation or configuration, GFYMS should verify that a working password/PIN path remains available before enabling face authentication in PAM. A bad biometric configuration must never leave the administrator locked out.