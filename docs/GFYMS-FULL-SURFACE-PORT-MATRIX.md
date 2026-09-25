# GFYMS Surface Pro 7 full-port matrix

This matrix separates Microsoft-package presence from actual Linux implementation and real Surface Pro 7 qualification.

Status: Corpus = present in the extracted MSI; Native = normal Linux/GFYMS implementation; Compat = Windows compatibility runtime; Hybrid = Linux hardware boundary plus selected Windows-derived behavior; Optional = not required for the base system; HIL = hardware-in-the-loop required; Not inferred = package presence alone is insufficient evidence.

> **ABI-map v2 status:** the `abi-map status` column is populated only after the first restored-LFS corpus run. Package presence alone must not be used to assign an ABI status.

## Platform / firmware / Surface management
| Component | Corpus | GFYMS path | Status |
|---|---|---|---|
| Surface UEFI | surfaceuefi | fwupd / Surface firmware backend | HIL |
| Intel ME / HECI / TEE | managementengine, me, heci, TeeDriverW10x64.sys | Linux MEI/HECI/TEE | Hybrid/HIL |
| Surface SAM | sam/SurfaceSAM.inf | Surface Aggregator / SSAM | Native/HIL |
| ACPI notify | surfaceacpinotify | Linux ACPI/platform | Native/HIL |
| Surface integration | surfaceintegration | SSAM + GFYMS service | Native |
| Surface serial hub | surfaceserialhub | Linux platform/serial | Native/HIL |
| Surface accessory / CFU | surfaceaccessorydevice, surfacecfuoverhid | HID/USB + firmware updater | Hybrid/HIL |
| Surface button / cover click | surfacebutton, surfacecoverclick | input/ACPI/HID | Native/HIL |
| Power filter / tracker | surfacepowerfilter, surfacepowertrackercore | Linux PM + GFYMS policy | Native/HIL |
| Surface PD / UCSI client | surfacepd, surfaceucmucsihidclient | Type-C/UCSI | Native/HIL |
| Telemetry / capability licensing | devicestelemetryservicedriver, capabilitylicensingsvcclient | diagnostics/compatibility only | Optional |

## Touch / pen / Type Cover
| Component | Corpus | GFYMS path | Status |
|---|---|---|---|
| IPTS / Intel Precise Touch | itouch/iaPreciseTouch.sys | linux-surface IPTS + iptsd | HIL |
| HID PCI | hidpciminiport/HID_PCI.sys | Linux HID/PCI | HIL |
| Surface HID mini | surfacehidmini | HID + Surface protocol | HIL |
| Type Cover | surfacetypecover | HID/input | HIL |
| Type Cover V3 | surfacetypecoverv3integration | HID/Surface integration | HIL |
| Keyboard backlight | surfacekeyboardbacklight | LED/HID + Plasma | HIL |
| Surface Pen | surfacepen*integration | HID/BLE + pen protocol | HIL |
| Pen/touch firmware | surfacepen*firmwareupdate, surfacetouchfw, surfacetouchpenprocessorupdate | guarded firmware path | Optional/HIL |

## Cameras
| Component | Corpus | GFYMS path | Status |
|---|---|---|---|
| Camera framework | iacamera64.sys | IPU4/IPU4P + libcamera | HIL |
| Camera control / ISP | iactrllogic64.sys, iaisp64.sys | IPU4/libcamera | Hybrid/HIL |
| OV5693 | ov5693.sys | V4L2/libcamera sensor | HIL |
| OV8865 | ov8865.sys | V4L2/libcamera sensor | HIL |
| OV7251 IR | ov7251.sys | V4L2/libcamera + GFYMS Hello | HIL |
| Camera user-mode stack | IntelDeviceMFT64.dll and related DLLs | native port first, compatibility fallback | Compat/Hybrid |

## Audio / DSP / far-field voice
| Component | Corpus | GFYMS path | Status |
|---|---|---|---|
| Intel SST | IntcSST.sys | SOF/ASoC | HIL |
| Intel DMIC | IntcDMic.sys | SOF DMIC/ALSA | HIL |
| Audio bus | IntcAudioBus.sys | SOF/ASoC | HIL |
| SoundWire | IntcSDW.sys | SoundWire/ASoC | HIL |
| Intel OED | IntcOED.sys | SOF + protocol RE | Hybrid |
| Bluetooth audio | IntcBTAu.sys | BlueZ/PipeWire | HIL |
| Realtek HDA | RTKVHD64.sys | HDA/ASoC codec path | HIL |
| Realtek extensions | RealtekExt.inf, RealtekHSA.inf | ALSA/PipeWire policy | Hybrid |
| IntelAudioService | IntelAudioService.exe | native .NET/Mono or Windows compatibility | Compat |
| Voice/DSP models | hundreds of amp/dsp/nrm/phm/th assets | model/firmware research | HIL |

## Sensors / ISH / rotation
| Component | Corpus | GFYMS path | Status |
|---|---|---|---|
| ISH bus | ISH_BusDriver.sys | Intel ISH | HIL |
| ISH HECI | ISH.sys | Intel ISH/HECI | HIL |
| Light sensor | SurfaceLightSensor.sys | IIO + iio-sensor-proxy | HIL |
| Accelerometer / rotation | ISH/SAM relationships | IIO + Plasma | HIL |
| Gyroscope / magnetometer | not proven by package names alone | investigate on hardware | Not inferred |

## Power / thermal
| Component | Corpus | GFYMS path | Status |
|---|---|---|---|
| Surface Battery | SurfaceBattery.sys | power_supply + SSAM | HIL |
| DPTF | dptf_acpi.sys, dptf_cpu.sys | ACPI/thermal/cpufreq | HIL |
| ESIF | esif_lf.sys, esif_uf.exe, esif_cmp.dll | native thermal policy where possible | Hybrid/Compat |
| Performance profiles | DPTF + Surface power paths | KDE power profiles | HIL |
| Suspend/s2idle | multiple device stacks | device-by-device qualification | HIL |

## Networking
| Component | Corpus | GFYMS path | Status |
|---|---|---|---|
| Intel Wi-Fi | Netwtw08/10/14/16.sys | iwlwifi + linux-firmware | Native/HIL |
| Intel Bluetooth | ibtusb.sys | btusb/btintel + firmware | Native/HIL |
| Wi-Fi user-mode helpers | IntelIHVRouter*.dll | investigate only where Linux lacks equivalent | Optional |

## Intel chipset / Serial I/O / storage
| Component | Corpus | GFYMS path | Status |
|---|---|---|---|
| Ice Lake PCH/LPSS | iclchipset*, iclserialio* | Linux PCI/ACPI/serial IO | Native/HIL |
| GPIO | iaLPSS2_GPIO2.sys | Linux GPIO | Native/HIL |
| I2C | iaLPSS2_I2C.sys | Linux I2C | Native/HIL |
| SPI | iaLPSS2_SPI.sys | Linux SPI | Native/HIL |
| UART | iaLPSS2_UART2.sys | Linux serial | Native/HIL |
| microSD | RtsUer.sys | Linux Realtek reader | HIL |
| MSU53/MSU56 controllers | matching package directories | protocol investigation | HIL |

## Graphics / display
| Component | Corpus | GFYMS path | Status |
|---|---|---|---|
| Intel graphics kernel | igdkmd64.sys | i915/DRM | Native |
| Display audio | IntcDAud.sys variants | DRM/HDA/SOF | HIL |
| Intel user-mode graphics | igd*.dll, igfx*.dll | Mesa/Intel Vulkan/OpenCL/VA-API | Native |
| Intel graphics services | OneApp.IGCC*.exe, igfx*.exe | native GFYMS controls or compatibility fallback | Compat/Optional |
| OEM panel/color | SurfaceOemPanel.dll | DRM/color management | Hybrid/HIL |

## Security / identity
| Component | Corpus | GFYMS path | Status |
|---|---|---|---|
| Surface TPM | surfacetpm/SurfaceTPM.inf | Linux TPM2 | Native/HIL |
| Intel TEE | TeeDriverW10x64.sys | Linux TEE where supported | HIL/Compat |
| Fingerprint | fingerprint package + DLLs | libfprint/fprintd investigation | Optional/HIL |
| IR face authentication | OV7251 package | libcamera + GFYMS Hello + PAM | HIL |

## USB-C / docks / accessories
The corpus contains Dock 2, Thunderbolt 4 Dock, and USB4-dock firmware/update packages. Their presence in the installer does not prove that the Surface Pro 7 host itself exposes USB4 or Thunderbolt 4.

Base SP7 qualification should target USB-C data, DisplayPort Alt Mode, external-display/MST behavior where supported, UCSI/Type-C policy, Surface Connect accessories, and dock firmware/update workflows.

## Windows user-mode runtime
| Payload class | GFYMS runtime |
|---|---|
| Portable modern .NET | native .NET 10 |
| Legacy .NET Framework | Mono when API-compatible |
| Managed + Windows-only APIs | Wine + Wine Mono fallback |
| Native Win32 | Wine or native reimplementation |
| MSI database inspection | native msitools |
| MSI Windows custom actions | translate natively; Wine only when unavoidable |

The Surface corpus contains three IntelAudioService.exe.config files targeting .NET Framework 4.6.1 and an Intel graphics service configuration targeting .NET Framework 4.7.2 with WCF named pipes. Microsoft retired .NET Framework 4.6.1 in 2022, so it should be treated as a legacy compatibility target rather than a modern runtime baseline. 

## MSI translation
The MSI tables expose Feature -> Component -> File relationships and CustomAction -> ExecuteSequence behavior. One package custom action invokes PowerShell and pnputil to install drivers. GFYMS should model those operations and translate them to Arch packages, Linux firmware workflows, or the native Windows compatibility layer; pnputil is not a Linux driver manager.

## Azure Linux donor/reference
Azure Linux is useful for Microsoft's open-source kernel patch history, configuration, hardening, package/build provenance, and supply-chain practices. It is not an official Surface-driver repository. Microsoft says Azure Linux is Azure-focused and does not support bare-metal/ISO deployments as a product support scenario.

## Qualification rule
Package presence is research evidence. A feature becomes GFYMS-supported only after its native/compatibility implementation passes real Surface Pro 7 hardware-in-the-loop testing.