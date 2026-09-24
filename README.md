# GFYMS Surface Pro 7

Utilities for inspecting and extracting the Microsoft Surface Pro 7 Windows 11 driver MSI.

## pymsi integration

This repository uses [nightlark/pymsi](https://github.com/nightlark/pymsi) for MSI parsing and extraction.

The current pymsi CLI supports:
- listing MSI tables
- dumping parsed MSI contents
- validation
- summary information
- custom-action analysis
- installer behavior analysis
- extracting files from the MSI

The pymsi viewer exposes Files, Tables, Summary, Streams, and Capabilities. It can export tables and extract streams.

## Comprehensive Dropbox export

Run the GitHub Actions workflow named:

**Download and comprehensively export Surface Pro 7 MSI**

When starting the workflow, paste the Dropbox shared URL for the MSI into the \`dropbox_url\` field. You can paste the normal \`dl=0\` URL; the workflow converts it to a direct download.

The generated ZIP contains:

\`\`\`text
source/
  original MSI

files/
  files extracted from the Windows Installer package by pymsi

tables/
  every parsed MSI table as JSON and CSV

streams/
  every OLE stream exposed by the MSI

metadata/
  summary.json
  manifest.json
  ole-tree.txt

reports/
  pymsi tables
  pymsi dump
  pymsi summary
  pymsi test
  pymsi analyze JSON
  pymsi custom-actions JSON
  pymsi extraction log
\`\`\`

This is deliberately broader than a normal driver extraction: the archive keeps the original MSI bytes, parsed database tables, raw OLE streams, and pymsi-extracted installer files together.

The workflow does not execute the MSI.

### External CAB files

If the MSI references an external cabinet instead of embedding the cabinet inside the MSI, that cabinet must also be supplied. pymsi supports MSI packages with external CAB inputs in its viewer, but a missing external CAB cannot be reconstructed from the MSI alone.

### Local MSI Preview

https://pymsi.readthedocs.io/en/latest/msi_viewer.html
