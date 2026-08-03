# Phase 2E synthetic dataset

`compose.demo.yaml` creates this dataset only through the formal PaintProject,
ImageAsset, ImageSet readiness, and RegionSet application services. It contains
one synthetic OIDC identity, one PaintProject, four program-generated PNG files,
a human READY review, and an approved human-authored RegionSet.

The PNGs are generated at seed time from repository code using simple geometric
forms. They are original project-created synthetic material, with no third-party,
customer, personal, AI-generated, or model-derived content. Their reserved
`.invalid` email address is not a real mailbox.

`make demo-reset` removes only the named Compose project volumes after its exact
configuration guard succeeds, then creates this dataset again. IDs and timestamps
are server-generated; titles, image bytes, rights declaration, review facts, and
polygon geometry are deterministic.
