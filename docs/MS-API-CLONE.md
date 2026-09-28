# MS API Clone — Verified MSI, EXE, and .NET Runtime Orchestration Specification

**Status:** research/design baseline — not an implementation of undocumented Microsoft internals
**Prepared:** 2026-09-25 (America/New_York)
**Scope authorization:** installer artifacts are owned by, or may be analyzed by, the requestor.
**Evidence rule:** every asserted platform contract below is linked to a primary Microsoft or official .NET/WiX source. “Observed” behavior must be recorded separately with the artifact SHA-256, Windows build, command line, log, and test result; it must never be promoted to a general rule merely because it worked once.

---

## 1. Executive decision: what can and cannot be cloned one-to-one

There is **no universal “Microsoft EXE installer API.”** `.exe` names a Windows executable format, not an installer protocol. Each vendor EXE can choose its own engine, command line, exit codes, prerequisite rules, UI, download behavior, and uninstall registration. A one-to-one clone of *every* EXE would require reproducing each vendor’s private implementation and is neither a stable nor a supportable compatibility target.

There **is** a supported public Windows Installer boundary for `.msi`/`.msp`: `msi.dll` / `msiexec.exe`, plus the `WindowsInstaller.Installer` COM automation object. The clone should **delegate MSI execution to the installed Windows Installer engine**, rather than attempting to reimplement MSI semantics. Microsoft documents the MSI function surface in the [Installer Function Reference][msi-functions].

There is also a documented .NET deployment/runtime boundary. A framework-dependent .NET app requires an appropriate preinstalled runtime; self-contained and Native AOT deployments do not require a preinstalled runtime ([.NET publishing overview][dotnet-publish]). The runtime installer for Windows is a Microsoft EXE with documented silent-install switches, but its behavior must be treated as a runtime-package adapter, not as a generic EXE protocol ([Install .NET on Windows][dotnet-windows]).

### Meaning of “one-to-one” in this specification

| Area | Compatibility target | Explicit limit |
|---|---|---|
| MSI execution | Execute the original, authored MSI via `msiexec.exe` or documented `msi.dll` APIs, preserving the MSI engine’s own action sequencing, rollback, repair, and logging behavior. | This does not recreate a different MSI package or undocumented Windows Installer implementation details. |
| MSI inspection | Read-only inspection of the actual MSI database with documented APIs; results refer to the package’s authored tables and conditions. | Custom actions can have arbitrary code and external effects; table inspection cannot prove all runtime behavior. |
| .NET prerequisite handling | Determine a declared/observed runtime requirement, install a verified Microsoft runtime through the documented runtime-installer adapter, then verify the required runtime family/version/architecture. | Do not infer a runtime solely from a filename, and do not hard-code “latest” versions. |
| Known EXE installers | Run only through an approved engine/vendor profile whose switches, success codes, and detection rule are documented or evidenced in a controlled test. | Unknown EXEs are **inspect-only / interactive approval**, never silently guessed. |
| Orchestration | Provide one deterministic workflow, audit record, restart semantics, logs, and a manifest-driven plan. | It cannot bypass signatures, UAC, policy, licensing, vendor entitlement checks, or package custom actions. |

---

## 2. Non-negotiable design rules

1. **Use public contracts first.** The supported MSI execution surface is `msiexec.exe` and the documented APIs in `msi.dll`; the documented COM ProgID is `WindowsInstaller.Installer` ([Installer object][installer-object]). Do not depend on private registry state, undocumented MSI caches, or reverse-engineered service RPC.
2. **Do not implement an MSI engine.** It is materially different from making a compatible launcher. Send an MSI to Windows Installer; let it execute its authored `InstallUISequence`/`InstallExecuteSequence`. MSI sequence tables define standard/custom actions, conditions, and order ([Using a Sequence Table][sequence-table]).
3. **No nested/concurrent MSI installs.** The Windows Installer guidance says not to ship concurrent/nested installations and recommends a setup application that installs several MSI packages sequentially ([MSI best practices][msi-best-practices]). Windows Installer returns `1618` when another execute sequence is running ([MSIExecute mutex][msi-mutex]).
4. **“EXE” is never a silent-install capability signal.** File extension, publisher name, and `/S` folklore are insufficient. A silent command can be used only if an approved profile or the vendor’s current documentation/test evidence says exactly what it is.
5. **Trust before execution.** Verify the candidate file’s Authenticode trust with `WinVerifyTrust`, capture signer and chain outcome, and compare a strong content hash to an approved manifest before starting it. `WinVerifyTrust` is the documented trust-verification function; `WINTRUST_DATA` supports installation UI context and explicit revocation behavior ([Wintrust API][wintrust-api], [WINTRUST_DATA][wintrust-data]).
6. **Use an absolute executable path.** For native EXE execution, pass the fully-qualified executable in `CreateProcessW`’s `lpApplicationName`, not a search-path-dependent command. Microsoft documents a `Program.exe` search-order hazard when applications rely on an ambiguous command line ([CreateProcessW security remarks][createprocess]).
7. **Never equate a download with a trusted package.** Resolve a version from a source-of-truth manifest, download over TLS, verify the listed hash and signer, then execute only the verified staged copy.
8. **No undocumented .NET registry detection.** Use the runtime requirement declared in the app’s output, the `dotnet` host’s documented reporting command, and a post-install launch/compatibility check. Do not synthesize a registry key just to make a detector pass.
9. **Always record reboot as an outcome, not an error.** For MSI, `0`, `1641`, and `3010` are success outcomes; `3010` means success with a reboot required. See Microsoft’s [MSI error-code reference][msi-errors] and [system reboot behavior][msi-reboots].
10. **Keep inspect mode side-effect free.** It may hash, verify, parse, enumerate, and open MSI databases read-only. It must never invoke custom actions, write transforms, install, repair, or remove anything.

---

## 3. Current platform baseline and freshness policy

### 3.1 Time-sensitive facts verified on 2026-09-25

Microsoft’s current .NET support page identifies .NET **10** as LTS through November 2028, and .NET **9** (STS) and .NET **8** (LTS) as supported through November 2026 at the time this document was prepared ([.NET releases and support][dotnet-support]). This is context only—not a rule to upgrade an application’s runtime major version. .NET roll-forward does not generally cross major-version boundaries by default ([.NET tool troubleshooting][dotnet-rollforward]).

The current Windows installation guidance lists Microsoft Windows installers, WinGet, and `dotnet-install.ps1` paths. The Microsoft runtime/SDK EXE supports `/install /quiet /norestart`; its `/ ?` help remains the authoritative check for a particular downloaded installer ([Install .NET on Windows][dotnet-windows]).

### 3.2 Freshness algorithm — required at each release build and deployment

Do **not** embed a version such as `10.0.x` or a permanent download URL in the clone’s source code. Instead:

1. Fetch the official .NET release metadata index: `https://builds.dotnet.microsoft.com/dotnet/release-metadata/releases-index.json`.
2. Select only an allowed channel declared by the application/package manifest—e.g., `10.0`, not “highest version available.”
3. Follow that channel’s `releases.json` URL. The official schema states that the index includes channel, support phase, latest patch, security status, and detailed release-metadata links; `releases.json` contains per-release download endpoints and hashes ([official release-metadata schema][release-metadata]).
4. Select an asset that exactly matches:
   - product family: `dotnet`, `windowsdesktop`, `aspnetcore`, or SDK/hosting bundle as required;
   - Windows architecture: `x86`, `x64`, or `arm64`;
   - approved major/minor channel and package type;
   - a version satisfying the app’s declared roll-forward policy.
5. Persist the metadata URL, retrieval timestamp, channel, asset URL, version, listed SHA-512, local SHA-512, local SHA-256, signer result, and certificate identity in the run journal.
6. Fail closed if the metadata schema/asset fields are unexpected, the hash mismatches, the signature cannot be trusted under the selected trust policy, or a package falls outside the manifest’s allowed channel.

This is how runtime acquisition stays current without silently changing the application’s compatibility contract.

---

## 4. Public contract map — the API surface to use

### 4.1 MSI: native Windows Installer contract

| Need | Supported interface | Required behavior in the clone | Primary source |
|---|---|---|---|
| Identify whether a file is an MSI package | `MsiVerifyPackage` | Use it as a package-validation signal; then open only in read-only mode for inspection. | [Function reference][msi-functions] |
| Open/inspect a package database | `MsiOpenDatabase` → `MsiDatabaseOpenView` → `MsiViewExecute` / `MsiViewFetch` → `MsiViewClose` | Read authoring data with Windows Installer SQL; release all handles. | [Obtaining a database handle][msi-db-handle], [Working with queries][msi-queries] |
| Inventory installed MSI products | `MsiEnumProductsEx`, `MsiGetProductInfoEx`, `MsiQueryProductState` | Enumerate all desired per-machine/per-user contexts explicitly; retain context and user SID in the record. | [Inventory products and patches][msi-inventory] |
| Find a product family/update relation | `MsiEnumRelatedProducts`, product/upgrade data from the package | Use this for the MSI product relationship only; do not mistake display-name equality for identity. | [Function reference][msi-functions] |
| Install/configure a package | `MsiInstallProduct`, `MsiConfigureProductEx`, or `msiexec.exe` | Choose exactly one execution backend per run. Pass only manifest-allowed public properties. | [Function reference][msi-functions], [MSI install flow][msi-install] |
| Repair | `MsiReinstallProduct` / `MsiReinstallFeature`, or documented `msiexec /f…` | Permit only when the manifest identifies the installed product and repair mode. | [Function reference][msi-functions], [MSI command-line options][msiexec-options] |
| Remove | `MsiConfigureProductEx` with absent state or `msiexec /uninstall <MSI|ProductCode>` | Target ProductCode/context exactly; do not derive an uninstaller from Add/Remove Programs registry display text. | [ConfigureProduct][configure-product], [standard msiexec options][msiexec-standard] |
| UI/progress/logs | `MsiSetInternalUI`, `MsiSetExternalUIRecord`, `MsiEnableLog`; or `msiexec` logging switches | Record UI choice and log location. Prefer record-based external UI where detailed file-in-use data matters. | [Function reference][msi-functions], [external UI progress][msi-external-ui], [MSI logging][msi-logging] |
| MSI signing-related inspection | `MsiGetFileSignatureInformation`, `MsiGetFileHash`; MSI signature tables | Treat MSI file/signature and any external payload/CAB verification as separate evidence. | [File/signature functions][msi-file-signature], [fully verified MSI signing][msi-signing] |
| COM scripting/automation | `WindowsInstaller.Installer` | Optional automation adapter; do not require it when native P/Invoke is available. | [Installer object][installer-object] |

**Important MSI database rule.** The MSI package is a relational database, but its SQL dialect is Windows Installer SQL—not a general SQL database. The documented inspection flow is open database → open view → execute → fetch → close ([Working with queries][msi-queries]). Inspection must use `MSIDBOPEN_READONLY`; authoring/transforms are a separate, explicit workflow and are out of scope for a runtime clone.

**Important product-inventory rule.** MSI may be per-machine or per-user. `MsiEnumProductsEx` is the supported way to enumerate products across contexts, and `MsiGetProductInfoEx` reads a particular context; therefore every stored identity must include at minimum `{ ProductCode, Context, UserSid }`, not only ProductCode ([Inventory products and patches][msi-inventory]).

### 4.2 EXE: controlled adapter contract

The clone exposes a single native process launcher, not an imaginary EXE-installer API:

```text
LaunchVerifiedProcess(
  absoluteApplicationPath,
  exactArgumentVector,
  workingDirectory,
  elevationPolicy,
  timeoutPolicy,
  cancellationPolicy,
  signerAndHashEvidence
) -> ProcessResult
```

Implementation boundary:

- Launch with `CreateProcessW` (or an elevation-aware Shell/UAC wrapper when the approved profile requires elevation); capture PID, start/end timestamps, and raw process exit code. `CreateProcessW` creates the child process in the caller’s security context ([CreateProcessW][createprocess]).
- An **EXE profile** supplies the only allowed install, uninstall, repair, layout/extract, detection, reboot, and success-code rules. A profile is approved only when based on vendor documentation or a named, repeatable controlled-lab observation.
- The clone must preserve the raw exit code. It may additionally emit a normalized status only when the profile defines a mapping.
- Unknown EXE → `classification=unknown`, `decision=manual-review`; no silent arguments are added.

For a known WiX Burn bundle, WiX documents that a bundle chain can contain `BundlePackage`, `ExePackage`, `MsiPackage`, `MspPackage`, and `MsuPackage`; WiX also documents `wix burn extract` for extraction. This can support **authorized inspection** of a recognized Burn bundle, but it does not make its internal chain a general EXE standard ([WiX Burn bundles][wix-burn], [wix burn extract][wix-extract]).

### 4.3 .NET runtime and deployment contract

| App/deployment evidence | Required clone behavior | Do not assume |
|---|---|---|
| `<app>.runtimeconfig.json` alongside a framework-dependent app | Parse `runtimeOptions` and retain the requested framework(s), version(s), roll-forward/configuration settings, source path, and file hash. A runtimeconfig file is generated with app output and can be app-specific. | Do not substitute a different major version merely because it is newer. |
| `.deps.json` / managed app metadata | Treat as supporting evidence for application/framework content; use it to cross-check the runtimeconfig requirement. | Do not use a filename or `TargetFrameworkAttribute` as the sole operational runtime contract. |
| Self-contained publish | Mark runtime prerequisite as `none` for the application payload, then still inspect native prerequisites separately. | Do not install shared .NET solely because a self-contained app uses .NET. |
| Native AOT publish | Mark shared .NET runtime prerequisite as `none`, subject to normal native dependency checks. | Do not treat any `.exe` as Native AOT without build/metadata evidence. |
| Desktop UI framework-dependent app | Require the matching Windows Desktop runtime family, architecture, and compatible version according to the application’s declared policy. | Do not install only a generic runtime if the app requires Windows Desktop. |
| ASP.NET Core app / IIS hosting requirement | Distinguish normal ASP.NET Core runtime from a Hosting Bundle/IIS requirement; retain this in the manifest/profile. | Do not claim the ordinary runtime is sufficient for IIS hosting. |

The .NET publishing documentation says framework-dependent deployment is the default and requires a preinstalled matching runtime; self-contained deployment includes the runtime; Native AOT has no runtime dependency ([.NET publishing overview][dotnet-publish]). The .NET runtime configuration guidance documents generated `runtimeconfig.json` files and app-specific configuration ([.NET runtime configuration][dotnet-runtimeconfig]).

#### Runtime verification

1. Invoke the target-architecture `dotnet` host and capture `dotnet --list-runtimes` output. Microsoft documents it as the installed-runtime listing command. An x86 host reports x86 runtimes and x64 reports x64; .NET 10+ also supports `--arch` ([dotnet command][dotnet-command]).
2. Preserve the raw output as primary evidence. Parse it conservatively into `{family, version, installPath, hostArchitecture}` only after validating the expected fields; if parsing fails, report `runtime-inventory-unparsed` rather than inventing state.
3. Evaluate installed versions against the manifest/runtimeconfig policy. A later patch in the same supported line may be valid only if the app’s roll-forward policy allows it. A higher major is not assumed valid; .NET’s documented default behavior does not roll forward across a major boundary ([dotnet-rollforward][dotnet-rollforward]).
4. Perform an explicitly designated read-only health check, or a normal app-launch smoke check only in a disposable lab, when the artifact is available. This validates the effective host policy rather than only an inventory listing.

#### Runtime installation

For a verified Microsoft Windows runtime installer, use only the documented silent path:

```text
<verified-dotnet-installer>.exe /install /quiet /norestart
```

Microsoft documents `/install`, `/quiet`, and `/norestart` for .NET Windows installers and directs callers to `/ ?` for an installer’s options ([Install .NET on Windows][dotnet-windows]). Capture that installer’s help text in profile-validation evidence before an unattended production rollout. `dotnet-install.ps1` is an alternative intended for CI/non-admin installation scenarios; it is not this clone’s default machine-wide prerequisite mechanism ([dotnet install script][dotnet-install-script]).

#### .NET Framework is distinct from modern .NET

The legacy **.NET Framework** and modern **.NET / .NET Core** must never share a detector or package identity. If WiX authoring is used, the documented `WixToolset.Netfx.wixext` extension provides .NET Framework detection properties and `DotNetCompatibilityCheck` support for modern .NET ([WiX .NET detection][wix-dotnet]). For an execution clone, a `.NET Framework` prerequisite must have its own approved profile and evidence; do not apply modern `dotnet --list-runtimes` logic to it.

---

## 5. Package manifest: the clone’s source of truth

A manifest turns a package workflow into an auditable contract. It must be version-controlled and signed/approved with the package release. It contains **no secrets** and must not provide a free-form arbitrary command execution field.

```yaml
schemaVersion: 1
id: com.example.product
release: 4.2.0
scope: machine                         # machine | user, as authored/approved
architecture: x64                      # x86 | x64 | arm64
policy:
  requireAuthenticodeTrust: true
  allowedPublisherSubjects:
    - "CN=Example Corporation, O=Example Corporation, C=US"
  requirePinnedSha256: true
  unknownExeMode: manual-review
  rebootMode: defer-and-report         # never force an unapproved reboot
  msiMutexRetry:
    maxAttempts: 6
    initialDelaySeconds: 10
    maxDelaySeconds: 60
packages:
  - id: dotnet-desktop
    kind: dotnet-runtime-exe
    family: windowsdesktop
    channel: "10.0"
    minimumVersion: "10.0.0"
    arch: x64
    source: official-release-metadata
    operation: install
    verify:
      command: ["dotnet", "--list-runtimes"]
      requirement: "Microsoft.WindowsDesktop.App >= 10.0.0; same architecture"

  - id: product-msi
    kind: msi
    path: payload/Product.msi
    sha256: "<release-pinned SHA-256>"
    msi:
      productCode: "{AAAAAAAA-BBBB-CCCC-DDDD-EEEEEEEEEEEE}"
      upgradeCode: "{FFFFFFFF-1111-2222-3333-444444444444}"
      publicProperties:
        INSTALLFOLDER: "[approved-at-deploy-time]"
      ui: quiet
      log: logs/product-msi.log
    verify:
      installedProduct: "{AAAAAAAA-BBBB-CCCC-DDDD-EEEEEEEEEEEE}"
      context: machine

  - id: optional-vendor-tool
    kind: exe-profile
    profile: example-vendor-setup-v4
    path: payload/ToolSetup.exe
    sha256: "<release-pinned SHA-256>"
    verify:
      detection: profile-defined
```

Manifest validation rejects:

- an MSI whose inspected `ProductCode`, `UpgradeCode`, platform/summary information, or hash differs from the approved manifest;
- an EXE without both hash and approved profile;
- any shell-string command field, URL not resolved through the approved source, or property not on the MSI public-property allowlist;
- a runtime family/architecture mismatch;
- a request to remove or repair a product not established by its exact MSI identity/context or profile-defined verified detection.

---

## 6. Deterministic workflow state machine

### 6.1 States

```text
DISCOVERED
  -> INSPECTED
  -> TRUSTED
  -> PLANNED
  -> PREFLIGHT_OK
  -> EXECUTING(package-id)
  -> VERIFYING(package-id)
  -> [next package | REBOOT_PENDING | SUCCEEDED | FAILED | CANCELLED]
```

Every transition appends an immutable journal event. A failed package ends required-chain execution; optional-package continuation must be an explicit manifest decision and is recorded as a degraded outcome.

### 6.2 Stage 0 — discovery and read-only inspection

For each supplied artifact:

1. Canonicalize the path; reject a path that resolves outside the approved staging root.
2. Record file size, SHA-256, SHA-512, PE/MSI classification, Authenticode result, signer/chain evidence, and acquisition provenance.
3. Call `MsiVerifyPackage` for prospective MSI artifacts. If valid, open with `MsiOpenDatabase(..., MSIDBOPEN_READONLY, ...)`.
4. Query, at minimum, the MSI `Property`, `SummaryInformation`, `Feature`, `Component`, `File`, `Media`, `Upgrade`, `LaunchCondition`, `CustomAction`, `InstallUISequence`, `InstallExecuteSequence`, `MsiDigitalCertificate`, and `MsiDigitalSignature` tables **when present**. Save raw table exports and a normalized digest; do not execute a custom action.
5. Mark custom actions as review findings. The table can show that an action was authored and sequenced, but the action’s program/script must be separately analyzed in a sandbox to describe effects.
6. For application payloads, locate and hash `.runtimeconfig.json`, `.deps.json`, executable/apphost, and managed assemblies; classify deployment as framework-dependent, self-contained, Native AOT, or unknown only when evidence is sufficient.
7. For EXEs, identify only a **known** engine/profile when the evidence matches a profile. Otherwise retain `unknown-exe`.

The MSI sequences are authoring data: a condition may cause an action to be skipped. The sequence-table documentation confirms that each row specifies action, condition, and order ([Using a Sequence Table][sequence-table]). Therefore a static report must present both the raw condition and a plan-time evaluation result, not claim unconditional execution.

### 6.3 Stage 1 — plan and resolve dependencies

1. Start with required packages in manifest order.
2. Parse the app runtime requirement before deciding whether to add a .NET prerequisite.
3. Query installed MSI products with `MsiEnumProductsEx` / `MsiGetProductInfoEx`; query the .NET host with `dotnet --list-runtimes`; save raw evidence.
4. Resolve a .NET asset only via the freshness algorithm in §3.2. Pin the resolved exact asset in the run plan so a retry cannot silently acquire a newer patch.
5. Build an execution plan in this order:
   - required runtime/external prerequisites;
   - one MSI or EXE package at a time;
   - post-package verification;
   - optional packages only when their prerequisites and policy allow.
6. If a runtime install requires a deferred reboot, do not run a dependent package until its profile/verification says it is safe. Default: end the run as `REBOOT_PENDING` and resume with the exact pinned plan after reboot.

### 6.4 Stage 2 — preflight

- Confirm all payload hashes/signatures and approved publisher policy again after staging.
- Confirm OS/architecture, free-space requirements, required elevation, and manifest scope.
- Check whether another MSI execute sequence is in progress. Do not attempt a parallel MSI install. Retry a bounded number of times on `1618`, then return a retryable failure. The documented `_MSIExecute` mutex guidance explains that execute sequences cannot run concurrently and notes `QueryServiceStatusEx` as a status check where needed ([MSIExecute mutex][msi-mutex]).
- Create unique log paths and a parent correlation ID.
- Obtain explicit approval for an interactive EXE/unknown profile; unattended mode refuses it.

### 6.5 Stage 3 — execute

#### MSI backend A: `msiexec.exe`

Use an explicit absolute executable (`%SystemRoot%\System32\msiexec.exe`) and package path. Prefer Microsoft’s standard forms:

```text
msiexec /package "C:\staging\Product.msi" /quiet /norestart /log "C:\logs\Product.msi.log" PUBLICPROPERTY="value"
msiexec /uninstall "{PRODUCT-CODE}" /quiet /norestart /log "C:\logs\Product.uninstall.log"
```

`/package`, `/uninstall`, `/quiet`, and `/norestart` are documented standard Installer options; `/quiet` is the standard equivalent of `/qn` ([standard msiexec options][msiexec-standard]). Only **public** MSI properties may be set on a command line, and their names are interpreted in uppercase ([MSI command-line options][msiexec-options]).

#### MSI backend B: `msi.dll`

For a native host with controlled progress/UI, use `MsiSetInternalUI` or `MsiSetExternalUIRecord`, `MsiEnableLog`, then `MsiInstallProduct` / `MsiConfigureProductEx`. Callers must collect return status and extended MSI message records. The clone must not combine an in-process `MsiInstallProduct` execution with an `msiexec` execution for the same operation.

External UI is not merely cosmetic: Microsoft states that a string external UI handler does not receive full FilesInUse details and that `MsiSetExternalUIRecord` should be used when that information is needed ([external UI progress][msi-external-ui]).

#### EXE profile backend

1. Reconfirm staged-file hash/signature against the manifest/profile.
2. Construct the exact approved argument vector—never concatenate user-provided fragments into a command shell.
3. Launch with absolute `CreateProcessW` application path, wait/cancel only according to profile policy, and collect stdout/stderr only if the profile defines it.
4. Persist raw exit code; map it to `Succeeded`, `SucceededRebootRequired`, `Retryable`, `Cancelled`, or `Failed` only by profile rule.
5. Verify installed state with the profile’s approved detection method; an exit code alone does not prove a successful install.

#### .NET runtime EXE adapter

1. Use the resolved exact runtime asset and verify its metadata hash/signature.
2. Run the documented command: `/install /quiet /norestart`.
3. Interpret its raw exit code by the Microsoft runtime-installer profile (validate `/ ?` per version before rollout); record a reboot requirement.
4. Re-run `dotnet --list-runtimes` in the needed architecture and evaluate the exact family/version policy.
5. If available, execute the dependent app’s non-mutating host smoke check.

### 6.6 Stage 4 — normalize outcomes

For **MSI only**, these standard outcomes are normalized as follows:

| Raw code | Normalized status | Meaning / behavior |
|---:|---|---|
| `0` (`ERROR_SUCCESS`) | `Succeeded` | Continue to post-verification. |
| `3010` (`ERROR_SUCCESS_REBOOT_REQUIRED`) | `SucceededRebootRequired` | MSI completed successfully; mark reboot pending and follow manifest restart policy. |
| `1641` (`ERROR_SUCCESS_REBOOT_INITIATED`) | `SucceededRebootInitiated` | Installation initiated a reboot; treat continuation as interrupted and resume only after reboot. |
| `1618` (`ERROR_INSTALL_ALREADY_RUNNING`) | `RetryableBusy` | Bounded retry, then return a clear busy outcome. |
| Any other code | `Failed` unless an MSI operation-specific documented mapping says otherwise | Preserve raw code and MSI log. |

Microsoft identifies `ERROR_SUCCESS`, `ERROR_SUCCESS_REBOOT_INITIATED`, and `ERROR_SUCCESS_REBOOT_REQUIRED` as successful outcomes; `3010` specifically means successful installation with reboot required ([MSI error codes][msi-errors]). Windows Installer also documents that it can use Restart Manager on supported versions to reduce restarts ([MSI system reboots][msi-reboots]).

For **EXE**, never apply this MSI table unless its profile explicitly and evidentially maps the EXE’s code to the same semantics.

### 6.7 Stage 5 — post-verification and journal close

**MSI verification**

- Re-enumerate with `MsiEnumProductsEx` and query `MsiGetProductInfoEx` / `MsiQueryProductState` for the expected `{ProductCode, Context, UserSid}`.
- Confirm intended install location/version only if those properties are applicable and reported by the package/product.
- Attach the MSI log path and parsed final status.

**Runtime verification**

- Record `dotnet --list-runtimes` raw and parsed output for the target architecture.
- Re-evaluate family, version, architecture, and declared roll-forward requirement.
- Record the app host smoke-check result when supplied.

**Product/exe verification**

- Execute only a profile-approved detection rule: exact MSI identity, signed installed file hash/version, documented product CLI query, or application health check.
- Never treat an uninstall-registry display name by itself as proof of the requested product/version.

End with one signed/immutable JSON result record containing final status, reboot status, plan digest, artifact digests, trust evidence, raw/normalized exit codes, and all logs.

---

## 7. MSI semantics that the clone must preserve—not imitate

### 7.1 Install, remove, repair, patch, upgrade

- **Install/configure:** `MsiInstallProduct` runs the package’s installation/removal sequence; `MsiConfigureProduct` configures product state. Microsoft’s installation guidance names these APIs ([MSI install flow][msi-install]).
- **Remove:** use an exact ProductCode (and correct context) or a package identified by the manifest. Do not invoke a guessed EXE uninstaller.
- **Repair:** use the product’s documented repair mode through `MsiReinstallProduct`/feature APIs or the approved `msiexec /f` form. Repair can reconfigure the system—record it as a mutating operation.
- **Patch:** `.msp` handling is a separate package kind. Inventory applied patches through `MsiEnumPatchesEx` where needed; do not mistake an MSP as a full product MSI ([MSI inventory][msi-inventory]).
- **Upgrade:** ProductCode/UpgradeCode/versioning and authored `Upgrade` table conditions decide the MSI relationship. The wrapper should expose what was authored and let Windows Installer execute it; it must not delete the old product solely because its name looks similar.

### 7.2 Multiple packages

Default: chain prerequisites and MSIs **sequentially** from the outer orchestrator. This follows the documented warning against nested/concurrent installations ([MSI best practices][msi-best-practices]).

Windows Installer has a documented multiple-package transaction feature beginning with Windows Installer 4.5, using `MsiBeginTransaction`, `MsiJoinTransaction`, `MsiEndTransaction`, and related tables; use it only if the packages are intentionally authored and tested for that feature ([multiple-package MSI installs][msi-multiple]). Do not claim every multi-package setup is atomic. Reboots in a package can prevent that package from joining/finishing the transaction as documented ([multiple-package MSI installs][msi-multiple]).

### 7.3 Custom actions and rollback

Custom actions are package code, not a generic MSI operation the clone can safely reproduce. Static inspection reports:

- type/source/target;
- sequence, condition, immediate/deferred/rollback/commit scheduling indicators;
- embedded vs external payload;
- signature/hash and sandbox observation references.

The clone delegates execution to Windows Installer only after the artifact passes trust/policy checks. It must never “replay” a custom action independently. Microsoft’s best practices recommend restricting custom actions and explain elevated/custom-action requirements ([MSI best practices][msi-best-practices]).

### 7.4 Logging and diagnostics

- Always create a package-specific log; avoid enabling global verbose logging permanently.
- Microsoft documents command-line, programmatic, package-property, and policy mechanisms for MSI logging, and cautions that verbose logging should be used for troubleshooting due to performance/disk impact ([MSI logging][msi-logging], [MSI best practices][msi-best-practices]).
- Keep raw logs immutable; generate summaries separately so diagnostic evidence is not modified.

---

## 8. Compatibility profiles for EXE installers

A profile makes a known EXE deterministic without pretending that arbitrary EXEs are standardized.

```yaml
profileId: example-vendor-setup-v4
classification:
  engine: vendor-documented | wix-burn | dotnet-runtime | msiexec-wrapper
  evidence:
    - kind: vendor-doc-url
      value: https://vendor.example/docs/setup-v4
    - kind: lab-run
      artifactSha256: "..."
      windowsBuild: "..."
      observedAt: "2026-09-25T...Z"
trust:
  publisherSubjects: ["CN=Example Corporation, O=Example Corporation, C=US"]
  requirePinnedSha256: true
operations:
  install:
    arguments: ["/quiet", "/norestart"]
    successExitCodes: [0]
    rebootRequiredExitCodes: [3010]
  uninstall:
    enabled: false
verification:
  kind: msi-product | signed-file | documented-cli | service | app-health
  # concrete fields are profile-specific
```

A profile is rejected unless it defines:

1. exact artifact identification (hash + signer policy);
2. command arguments for each enabled operation;
3. exit-code policy;
4. a verified installed-state detector;
5. rollback/removal behavior or a deliberate `not supported` declaration;
6. documentation or controlled-lab evidence with enough detail to reproduce.

**Prohibited profile behavior:** bypass UAC, patch the vendor EXE, disable endpoint protection, suppress signature failures, scrape a web page for an unpinned arbitrary download, or use a command interpreter to launch an installer.

---

## 9. Required data models and audit record

### 9.1 Normalized package record

```json
{
  "id": "product-msi",
  "kind": "msi",
  "classificationConfidence": "verified",
  "path": "C:\\staging\\Product.msi",
  "sha256": "…",
  "sha512": "…",
  "signature": {
    "winVerifyTrust": "success",
    "publisher": "CN=Example Corporation, O=Example Corporation, C=US",
    "revocationMode": "online-chain"
  },
  "identity": {
    "productCode": "{…}",
    "upgradeCode": "{…}",
    "packageCode": "{…}",
    "context": "machine"
  },
  "requirements": {
    "architecture": "x64",
    "dotnet": [{"family": "Microsoft.WindowsDesktop.App", "minimum": "10.0.0"}]
  },
  "evidence": ["inspection-report.json", "msi-table-export/"],
  "policyDecision": "approved"
}
```

### 9.2 Per-operation journal event

```json
{
  "correlationId": "uuid",
  "planDigest": "sha256:…",
  "packageId": "product-msi",
  "operation": "install",
  "backend": "msiexec",
  "commandRedacted": ["/package", "<payload>", "/quiet", "/norestart", "/log", "<log>"],
  "startedUtc": "…",
  "endedUtc": "…",
  "rawExitCode": 3010,
  "normalizedStatus": "SucceededRebootRequired",
  "verification": {"status": "passed", "evidence": ["…"]},
  "reboot": "required-deferred",
  "logs": ["…"],
  "artifactSha256": "…"
}
```

Secrets, license keys, bearer tokens, personal paths, and property values classified as confidential must be redacted in UI and journal summaries. The original secure deployment system—not the log—must hold them.

---

## 10. Differential validation plan (the proof of one-to-one behavior)

“Works on my machine” is not proof. The clone should be accepted per artifact/version only after this test matrix on disposable Windows VMs:

| Test | Original supported path | Clone path | Required equivalence evidence |
|---|---|---|---|
| Clean install | Vendor/MSI documented install | Clone plan install | Product identity/state, expected files, services/shortcuts/registry only where package authoring specifies, app launch, log success. |
| Already installed | Original upgrade/maintenance behavior | Clone re-run | Same resulting product state; no duplicate products. |
| Upgrade | Original supported newer package path | Clone upgrade plan | Expected old/new ProductCode/UpgradeCode state and application version. |
| Repair | Vendor/MSI documented repair | Clone repair | Expected restoration and MSI state. |
| Uninstall | Vendor/MSI documented removal | Clone removal | Product absent in correct context; expected remaining user data described separately. |
| Missing runtime | Original prerequisite flow | Clone prerequisite + product plan | Exact runtime family/version/architecture installed; app starts afterward. |
| Runtime already valid | Original prerequisite flow | Clone plan | Runtime installer is skipped; app starts. |
| Wrong architecture | Original behavior | Clone preflight | Clear, no-mutation failure. |
| MSI busy | Existing MSI activity | Clone run | Bounded wait/retry or `RetryableBusy`; no parallel install attempt. |
| Reboot required | Package/runtime that reports it | Clone run | `SucceededRebootRequired`, no false failure, no unapproved restart, resume proof. |
| Trust failure | Modified/signer-mismatched staged artifact | Clone run | Fails before execution with evidence. |
| Unknown EXE | Unsigned/unsupported profile | Clone unattended run | Refusal/manual-review state; it is not launched silently. |

For every comparison, capture:

- VM image and Windows build;
- artifact cryptographic hashes and signer chains;
- exact public command/API input;
- MSI/installer logs, raw exit codes, reboot marker;
- before/after inventory and file-system snapshots limited to test areas;
- raw `dotnet --list-runtimes` output with host architecture;
- application health/launch test;
- a human-reviewed difference report.

Do **not** claim package behavior from a single VM or substitute registry scraping for Windows Installer inventory.

---

## 11. Implementation roadmap

### Milestone A — read-only analyzer

Deliverables:

- MSI inspector built on `MsiVerifyPackage`, `MsiOpenDatabase`, views/records, and table export;
- PE/Authenticode verifier based on `WinVerifyTrust`;
- SHA-256/SHA-512 provenance capture;
- `.runtimeconfig.json` / `.deps.json` parser;
- `dotnet --list-runtimes` collector;
- evidence report matching §§4 and 6.2.

Acceptance criterion: no package installation APIs/processes are called; every fact in the report has raw evidence and an evidence-source label.

### Milestone B — MSI executor

Deliverables:

- plan/manifest validator;
- MSI inventory adapter (`MsiEnumProductsEx`, `MsiGetProductInfoEx`);
- one `msiexec` execution backend plus log/return/reboot normalization;
- bounded MSI-busy handling;
- post-install verification and journal.

Acceptance criterion: complete clean-install/repair/uninstall/reboot tests for one signed sample MSI, including correct context handling.

### Milestone C — .NET runtime adapter

Deliverables:

- release-metadata resolver with schema validation, hash pinning, and provenance;
- Microsoft .NET runtime EXE adapter using the documented silent switches;
- runtime family/architecture/roll-forward verifier;
- framework-dependent, self-contained, and Native AOT decision tests.

Acceptance criterion: a missing runtime is installed only when required; a valid runtime is not needlessly reinstalled; mismatch cases fail before the application MSI begins.

### Milestone D — profile-driven EXE adapter

Deliverables:

- `CreateProcessW`-based execution host;
- strict profile schema/approval gate;
- known Burn inspection adapter, if needed;
- vendor-profile test harness and evidence capture.

Acceptance criterion: no unknown EXE can silently run; each enabled operation in a profile has an approved detector and reproducible lab result.

### Milestone E — end-to-end differential test suite

Deliverables:

- isolated VM/Hyper-V/Windows Sandbox test fixtures;
- golden evidence bundles;
- automated comparison report;
- regression gate requiring source freshness/revalidation whenever an upstream runtime channel, installer profile, or Windows build changes.

---

## 12. Explicit non-goals and safety boundaries

This project does **not**:

- break, remove, decrypt, or bypass code signing, DRM, UAC, Windows policy, endpoint protection, licensing, or vendor authentication;
- reconstruct or call undocumented Microsoft installer service interfaces;
- treat arbitrary EXEs as MSI/Burn/.NET installers based on names or extension;
- modify an MSI’s tables, custom actions, or embedded payloads during execution;
- use nested MSI installations as a generic prerequisite mechanism;
- use a private MSI cache path or undocumented registry value as a supported identity source;
- force reboot by default;
- claim support for a vendor installer until a version-specific profile has documented or controlled-lab evidence.

---

## 13. Source ledger

All links below were consulted for this specification on **2026-09-25**. Links are primary vendor documentation unless explicitly marked official WiX/.NET GitHub documentation.

[msi-functions]: https://learn.microsoft.com/en-us/windows/win32/msi/installer-function-reference
[installer-object]: https://learn.microsoft.com/en-us/windows/win32/msi/installer-object
[msi-db-handle]: https://learn.microsoft.com/en-us/windows/win32/msi/obtaining-a-database-handle
[msi-queries]: https://learn.microsoft.com/en-us/windows/win32/msi/working-with-queries
[msi-inventory]: https://learn.microsoft.com/en-us/windows/win32/msi/inventory-products-and-patches-
[msi-install]: https://learn.microsoft.com/en-us/windows/win32/msi/installing-an-application
[configure-product]: https://learn.microsoft.com/en-us/windows/win32/msi/installer-configureproduct
[msiexec-options]: https://learn.microsoft.com/en-us/windows/win32/msi/command-line-options
[msiexec-standard]: https://learn.microsoft.com/en-us/windows/win32/msi/standard-installer-command-line-options
[msi-external-ui]: https://learn.microsoft.com/en-us/windows/win32/msi/handling-progress-messages-using-msisetexternalui
[msi-logging]: https://learn.microsoft.com/en-us/windows/win32/msi/normal-logging
[msi-file-signature]: https://learn.microsoft.com/en-us/windows/win32/msi/installer-function-reference
[msi-signing]: https://learn.microsoft.com/en-us/windows/win32/msi/authoring-a-fully-verified-signed-installation
[msi-errors]: https://learn.microsoft.com/en-us/windows/win32/msi/error-codes
[msi-reboots]: https://learn.microsoft.com/en-us/windows/win32/msi/system-reboots
[msi-mutex]: https://learn.microsoft.com/en-us/windows/win32/msi/-msiexecute-mutex
[msi-best-practices]: https://learn.microsoft.com/en-us/windows/win32/msi/windows-installer-best-practices
[msi-multiple]: https://learn.microsoft.com/en-us/windows/win32/msi/multiple-package-installations
[sequence-table]: https://learn.microsoft.com/en-us/windows/win32/msi/using-a-sequence-table
[dotnet-windows]: https://learn.microsoft.com/en-us/dotnet/core/install/windows
[dotnet-support]: https://learn.microsoft.com/en-us/dotnet/core/releases-and-support
[dotnet-publish]: https://learn.microsoft.com/en-us/dotnet/core/deploying/
[dotnet-runtimeconfig]: https://learn.microsoft.com/en-us/dotnet/core/runtime-config/
[dotnet-command]: https://learn.microsoft.com/en-us/dotnet/core/tools/dotnet
[dotnet-rollforward]: https://learn.microsoft.com/en-us/dotnet/core/tools/troubleshoot-usage-issues
[dotnet-install-script]: https://learn.microsoft.com/en-us/dotnet/core/tools/dotnet-install-script
[release-metadata]: https://github.com/dotnet/core/blob/main/release-notes/schemas/README.md
[wix-dotnet]: https://wixtoolset.org/docs/tools/wixext/dotnet/
[wix-burn]: https://wixtoolset.org/docs/tools/burn/
[wix-extract]: https://wixtoolset.org/docs/tools/wixexe/
[wintrust-api]: https://learn.microsoft.com/en-us/windows/win32/api/wintrust/
[wintrust-data]: https://learn.microsoft.com/en-us/windows/win32/api/wintrust/ns-wintrust-wintrust_data
[createprocess]: https://learn.microsoft.com/en-us/windows/win32/api/processthreadsapi/nf-processthreadsapi-createprocessw
