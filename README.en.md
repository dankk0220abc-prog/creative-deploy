# CreativeDeploy

[中文](README.md) · [Architecture](docs/architecture.md) · [Evidence index](docs/evidence-index.md) · [Demo script](docs/demo-script.md)

> A browser-first, bilingual AI application platform for creative workflows. It pairs real product experiences with private-data boundaries, traceable retrieval, provider governance, and recoverable delivery.

CreativeDeploy contains two distinct product spaces:

- **PaintPilot** is a miniature repaint-planning workspace. Private images, ImageSet / RegionSet, structured Paint Plans, cited knowledge, and human approval replace the usual “upload an image and trust the model” flow.
- **Arcana** is a private three-card reading and reflection product. It organizes question analysis, position and orientation, deterministic cross-card relationships, repository-local knowledge, and citations instead of concatenating generic per-card prose.

## Why it is more than an AI demo

The platform is bilingual (`zh-CN` / `en-US`) and browser-first, but the important work sits behind the UI: OIDC sessions, ownership and project policy, API-only private-object delivery, encrypted BYOK, provider registry/policy, budget reservation, durable pre-egress claims, idempotency, accounting, auditability, cited RAG/provenance, migrations, and synthetic staging recovery.

Independent real-provider proof was completed for PaintPilot with GLM-5V-Turbo and for Arcana with GLM-5.2. The public Portfolio Demo remains **Live OFF with zero provider calls**: it uses local synthetic data and repeatable fixtures and never asks an evaluator for a key.

## Five-minute local demo

With Docker Desktop (Compose), `curl`, and `python3`:

```bash
git clone https://github.com/dankk0220abc-prog/creative-deploy.git
cd creative-deploy
make demo-up
```

Open <http://127.0.0.1:18173/> and choose **PaintPilot Demo Visitor** on the synthetic local sign-in page. The product chooser exposes the preloaded PaintPilot workspace; Arcana guides you to an inspectable, read-only Fixture reading with question-aware interpretation, citations, and history. The loopback-only profile uses an isolated dataset, local OIDC, and local object storage; it does not read your private `.env` or call a real provider.

```bash
make demo-status
make demo-reset  # only recreates guarded, named Demo volumes and synthetic data
make demo-down
```

For the complete story, see the [Chinese README](README.md), [architecture](docs/architecture.md), [case studies](docs/case-studies/), and [interview material](docs/portfolio/). This is public source under [Apache-2.0](LICENSE), not a public production deployment. The explicit deployment boundary is documented in [docs/deployment-decision.md](docs/deployment-decision.md).
