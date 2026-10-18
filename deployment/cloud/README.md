# Reverse proxy review example

`nginx.conf` is the original example extracted and verified byte-for-byte from
ARYN application source. It has not been deployed or validated against a real
identity provider, TLS installation or production host. Certificates/keys remain
external, example.org is illustrative, and private API/runtime/gateway ports must
not be published. Application authentication/authorization is defined by ARYN Core;
proxy headers never establish user or administrative identity.

See [source provenance](source-history.json) for the source commit, Git blob,
section and verified content hash. No infrastructure was provisioned. The owner
authorized publication to `main` on 18 October 2026, before application-source
delivery. `development` remains a historical reference.

The raw extraction hash is retained alongside a CRLF-to-LF normalized content
hash, allowing verification after Git checkout on another operating system.
