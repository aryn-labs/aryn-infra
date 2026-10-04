# ARYN Infrastructure agent rules

- Never deploy, create billable services, alter DNS, or open public ports without explicit owner approval.
- Never store credentials or signed license private keys in git or CI logs.
- Keep infrastructure separate for dev/test/prod and document destroy/rollback procedures.
- Require confirmed project/tenant isolation and safe sandbox defaults before exposing endpoints.
- Work on development/feature branches; do not push main without owner approval.
