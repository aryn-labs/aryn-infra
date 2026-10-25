# ARYN Infrastructure

Private infrastructure and operations repository for ARYN. No real credentials, live production infrastructure, or automatic deployment is included in this scaffold.

Directories:
- `docker/`: reproducible local services and sandbox resources.
- `deployment/cloud/`: cloud provisioning/deployment templates after approval.
- `deployment/local/`: Windows installer packaging and local lifecycle guides.
- `environments/example/`: non-secret illustrative configuration only.
- `monitoring/`: metrics, logs and alerts without secret leakage.
- `provisioning/`: infrastructure as code candidates, subject to cost review.
- `.github/workflows/`: CI/CD pipelines when real checks exist.

Principles: separate dev/test/prod, cost ceilings, least-privilege CI permissions, signed releases when available, rollback plans, and explicit approval before provisioning paid resources.

[Isolated operational targets](docker/operational_targets/README.md) provides a
real disposable service, independent endpoint observations, constrained fault
injection, bounded resources and identity-checked cleanup. Product Core admission,
approval and evidence remain in `aryn`; this repository owns only the service and
trusted local provisioning/lifecycle mechanism. No public deployment is performed.

The [cloud proxy review example](deployment/cloud/README.md) was copied from
application source with verified provenance. It remains an undeployed example;
owner-approved publication to `main` precedes application-source relocation.
