# Mira Review Setup

Mira is the primary AI reviewer for GFYMS. The checked-in `.mira.yaml` contains
the repository-specific review policy; secrets and deployment credentials must
never be committed here.

## Deployment

Run the official Mira Docker image or use one of its documented PaaS targets.
The current official image is:

    ghcr.io/miracodeai/mira:latest

Mira exposes HTTP on port 8000. Put it behind HTTPS before registering the
GitHub webhook.

For a production deployment, use persistent storage for Mira's index directory
and Postgres if the service will scale beyond a single instance.

## GitHub App

Create a GitHub App owned by the account or organization that owns GFYMS.

Repository permissions:
- Pull requests: Read and write
- Contents: Read and write
- Issues: Read and write
- Metadata: Read
- Checks: Read and write (optional)

Subscribe the app to:
- Pull request
- Pull request review comment
- Issue comment
- Push

Set the webhook to:

    https://YOUR-MIRA-HOST/github/webhook

Generate a private key and keep it outside Git. Configure:

    MIRA_GITHUB_APP_ID=YOUR_APP_ID
    MIRA_GITHUB_PRIVATE_KEY=@/etc/mira/private-key.pem
    MIRA_WEBHOOK_SECRET=YOUR_RANDOM_SECRET
    ADMIN_PASSWORD=YOUR_ADMIN_PASSWORD

## LLM backend

Mira is model-agnostic. For a high-quality first review, use a capable reasoning
model. For private/local operation, point Mira at an OpenAI-compatible local
endpoint such as Ollama or vLLM.

Do not put API keys in `.mira.yaml`. Keep credentials in the deployment
environment.

## GFYMS review policy

The repository configuration asks Mira to inspect:
- PE/COFF and delay-import parsing
- INF section/string/HWID/service relationships
- MSI Directory/Component/File joins and CustomAction semantics
- WDF/KMDF evidence and confidence
- .NET Framework, runtimeconfig, deps, and apphost detection
- dependency-graph identity and ambiguity handling
- Git LFS pointer handling
- PowerShell path/error handling
- reproducibility and deterministic output
- research-corpus versus distributable-code boundaries

Heuristic matches are expected to retain explicit evidence and confidence.
Basename-only matches are not treated as exact relationships.

## Review command

After Mira is connected to the repository, use:

    @Mira review

The repo policy is designed for a thorough review rather than a cosmetic pass.
