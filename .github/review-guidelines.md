# GFYMS AI code-review guidelines

## Review posture

Treat this repository as systems and reverse-engineering infrastructure. Findings
must be grounded in the actual code and repository context. Do not invent APIs,
binary formats, Windows semantics, or test results.

Prefer concrete correctness defects over style commentary. A suggested
improvement is only useful when it materially reduces a correctness, security,
reproducibility, or maintenance risk.

## ABI-map v2

Audit PE/COFF handling for malformed inputs, architecture detection, import and
delay-import parsing, ordinal imports, export handling, CLR/runtime detection,
deterministic serialization, and graph node/edge identity.

Treat host-provided Windows modules as explicit ABI dependencies. Do not
silently convert a missing corpus file into an external dependency when the
difference affects compatibility conclusions.

Heuristic detections must retain evidence and confidence. Do not present
heuristics as authoritative facts.

## INF

Check section structure, continuation lines, [Strings] expansion, decorated
install sections, AddService/ServiceBinary relationships, Include/Needs
relationships, and hardware-ID normalization. Preserve enough provenance to
trace a result back to the source section and line/value.

## MSI

Check Directory -> Component -> File joins, short/long FileName semantics,
case-insensitive path behavior, missing-table behavior, duplicate filenames,
payload-to-PE confidence levels, and CustomAction type/flag decoding.

Never treat a basename-only MSI -> PE match as exact.

## WDF/KMDF

Treat WDF/KMDF detection as heuristic until corroborated by authoritative
binary evidence. Verify pointer width, structure offsets, version fields,
function counts, and string/RVA relationships before assigning high confidence.

## .NET

Distinguish legacy .NET Framework configuration from modern .NET runtimeconfig
and deps files. Apphost sidecar detection must remain evidence-based. Do not
claim a precise runtime version unless the source provides that version.

## PowerShell tooling

Reject basename collisions, path traversal, accidental live-host collection,
and Git-LFS pointer false positives. Live PnP/service inventory must remain
explicitly opt-in.

## Tests

Tests should be deterministic and isolated. Prefer fixtures covering malformed
inputs, missing MSI tables, basename collisions, ordinal imports, LFS pointers,
fallback confidence paths, and real parser behavior rather than only mocked
helper behavior.

## Distribution boundary

Research-corpus analysis and distributable GFYMS implementation are separate.
Do not recommend shipping Microsoft vendor binaries merely because the corpus
contains them. Do not infer hardware support from package presence alone.
