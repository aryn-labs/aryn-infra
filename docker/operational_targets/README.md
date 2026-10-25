# Isolated operational targets

This local test infrastructure runs a real disposable business subprocess and a
separate lifecycle controller. A fresh observer contacts both internal HTTP
endpoints. Relay receives actual health, process instance, generation, request
count, timestamps and measured probe latency; changing ARYN database state cannot
start the business process or manufacture a successful response.

The controller listens only inside a container with network `none`. There are no
published ports, Docker socket, host mounts, provider credentials or external
network access. The fixed profile uses UID/GID 65532, read-only root, all Linux
capabilities dropped, no new privileges, 128 MiB memory/swap, 0.5 CPU and 64 PIDs.
Its parent lifetime is bounded to 30–28800 seconds. Resource ceilings are limits,
not measured CPU/memory consumption. This is disposable infrastructure, not an
administration interface for customer or production services.

## Create, observe and destroy

Run from the sibling `aryn` checkout. Docker must already have a reviewed Python
base image. Use its exact local `sha256:` image ID; creation never pulls an image.
The example placeholders contain no credentials.

```powershell
New-Item -ItemType Directory -Force .local/operational-intelligence | Out-Null
$baseImage = 'sha256:<reviewed-local-python-image-id>'
.venv/Scripts/python.exe ../aryn-infra/scripts/operational_environment.py create --manifest .local/operational-intelligence/service-environment.json --base-image $baseImage --ttl 3600
.venv/Scripts/python.exe ../aryn-infra/scripts/operational_environment.py observe --manifest .local/operational-intelligence/service-environment.json
```

The new manifest binds the exact container/image, environment, organization,
project and fixed resource profile. The companion `service-environment-build.json`
records the reviewed base image, unique owned image tag and SHA-256 of Dockerfile,
build exclusions and service source. Creation refuses existing manifest files.
The local classic Docker builder consumes the verified image ID with pull disabled
and build network disabled; this is a per-process setting, not a daemon change.

To demonstrate a real stopped process or a latched business-health failure:

```powershell
.venv/Scripts/python.exe ../aryn-infra/scripts/operational_environment.py fault --manifest .local/operational-intelligence/service-environment.json --fault stop_worker
.venv/Scripts/python.exe ../aryn-infra/scripts/operational_environment.py observe --manifest .local/operational-intelligence/service-environment.json
```

Fault injection is an explicit local test-operator command, never a browser or
agent tool. `latch_unhealthy` terminates the child and makes a subsequent recovered
child return HTTP 503. Recreate a fresh environment for each full demonstration.

Always clean up, including after cancellation/failure:

```powershell
.venv/Scripts/python.exe ../aryn-infra/scripts/operational_environment.py destroy --manifest .local/operational-intelligence/service-environment.json
```

Cleanup first verifies exact labels, identities and isolation. It removes only
the owned disposable container and its unique image tag; it preserves shared base
images, other image references, manifests/evidence and user data. A mismatched
manifest/tag is refused. Historical manifests without build metadata remove only
the owned container. Expired service containers may be stopped but remain eligible
for identity-checked cleanup. No Docker prune is used.

## Core integration and reproducible proofs

ARYN starts with `python -m services.api --operational-bindings <manifest>`.
Only the trusted operator configures this path. Web registration selects an opaque
binding ID and name in the exact tenant/project, then uses existing Core RBAC,
human approval, signer, execution ownership and durable idempotency claims.
The manifest never goes to the model or browser. A fixed signed admission contains
the exact target instance/generation, action, approval, grant identity and deadline.
The constrained adapter executes only the fixed controller protocol through stdin.
The controller rechecks its instance/generation/deadline before starting one child.
No arbitrary command, host path, destination or credential is accepted.

The effect and application checkpoint cannot be physically atomic. Transport loss
means outcome unknown; Core never retries the effect. Independent observation can
reconcile the causal child execution ID and generation. A successful controller
return alone cannot establish recovery. Cancellation fences a pending dispatch;
an already dispatched process is never falsely reported undone.

```powershell
$env:PYTHONPATH='.'
.venv/Scripts/python.exe tests/operational_intelligence_check.py --manifest .local/operational-intelligence/service-environment.json --output .local/operational-intelligence/service-recovery.json
.venv/Scripts/python.exe -m unittest discover -s ../aryn-infra/tests -v
```

The product proof creates a disposable ARYN database, real Git/file sources and
actual service telemetry. It covers healthy/fault/recovery, unapproved and revoked
denial, health failure, deliberately lost verification, immutable unknown/failed
capsules, reconciliation, zero-live-write replay and human-reviewed regression
authoring. It makes no model request. JSON evidence is sanitized and identifies
the actual immutable target image/environment; it is local verification, not a
commit-bound CI artifact or production certification.

For browser verification, create a **fresh** environment with `--organization
org_studio_local --project proj_studio_research`, set the absolute manifest path
in `ARYN_TEST_OPERATIONAL_MANIFEST`, build `aryn/apps/web`, and run its existing
`playwright.intelligence.config.ts`. The browser fixture uses real API/Core state,
physical temporary runbooks and read-only Git blobs. With that explicit manifest,
the operational Web recovery uses the actual Docker service. Without it, the
offline browser contract tests label their transport `OperationalProtocolDouble`.
Neither mode uses a paid provider or global Hermes/gateway configuration.

Existing native worker and PostgreSQL provisioning remain in their established
ARYN verification flows. Do not provision public or paid infrastructure from these
commands. Hosted operational deployment, persistent secret management, general
infrastructure adapters and unmediated Hermes capabilities require separate
review and evidence.
