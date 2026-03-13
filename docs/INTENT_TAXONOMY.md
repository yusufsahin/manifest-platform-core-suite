# Intent Taxonomy v1.0 (Normative)

An `Intent` represents a side-effect that an engine recommends but does not execute.
Adapters consume intents and perform the actual work.

Each intent MUST have a `kind`. All valid kinds are defined below.
Implementations producing an unknown `kind` MUST fail conformance.

## Field Masking

### `maskField`

Instructs the adapter to redact a field before returning data to the caller.

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `target` | string | yes | Dot-path of the field to mask (e.g. `user.ssn`) |
| `params.mask` | string | no | Replacement value; defaults to `***` |
| `idempotencyKey` | string | no | Dedupe key |

## Notification

### `notify`

Instructs the adapter to send a notification.

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `target` | string | yes | Recipient identifier (user ID, channel, topic) |
| `params.template` | string | yes | Notification template key |
| `params.data` | object | no | Template variables |
| `idempotencyKey` | string | yes | Required to prevent duplicate sends |

## Access Control

### `revoke`

Instructs the adapter to revoke a token, session, or permission grant.

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `target` | string | yes | Token or session identifier |
| `params.reason` | string | no | Human-readable revocation reason |
| `idempotencyKey` | string | yes | Required |

### `grantRole`

Instructs the adapter to assign a role to an actor.

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `target` | string | yes | Actor identifier |
| `params.role` | string | yes | Role name to grant |
| `idempotencyKey` | string | yes | Required |

## Audit

### `audit`

Instructs the adapter to append an immutable audit record.

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `target` | string | yes | Resource identifier being audited |
| `params.action` | string | yes | Action that was taken |
| `params.actor` | string | yes | Actor who performed the action |
| `params.artifactHash` | string | no | Hash of the artifact involved |
| `idempotencyKey` | string | yes | Required for WORM compliance |

## Data Transformation

### `transform`

Instructs the adapter to apply a named transformation to an object.

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `target` | string | yes | Object identifier |
| `params.operation` | string | yes | Transformation key |
| `params.input` | object | no | Input data for the transformation |
| `idempotencyKey` | string | no | |

### `tag`

Instructs the adapter to attach metadata tags to an object.

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `target` | string | yes | Object identifier |
| `params.tags` | object | yes | Key-value pairs to attach |
| `idempotencyKey` | string | no | |

## Traffic / Rate Control

### `rateLimit`

Instructs the adapter to apply rate limiting to an actor or resource.

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `target` | string | yes | Actor or resource identifier |
| `params.limitKey` | string | yes | Limit bucket identifier |
| `params.windowMs` | integer | yes | Window size in milliseconds |
| `params.maxRequests` | integer | yes | Max requests per window |
| `idempotencyKey` | string | no | |

### `redirect`

Instructs the adapter to route a request to a different resource.

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `target` | string | yes | Destination resource identifier or URL path |
| `params.permanent` | boolean | no | True = 301, false = 302; defaults to false |
| `idempotencyKey` | string | no | |

## Artifact Lifecycle

### `publish`

Instructs the adapter to promote an artifact to the published state.

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `target` | string | yes | Artifact identifier |
| `params.artifactHash` | string | yes | Hash of the artifact to publish |
| `idempotencyKey` | string | yes | Required |

### `rollback`

Instructs the adapter to restore a previous artifact version.

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `target` | string | yes | Namespace or resource identifier |
| `params.artifactHash` | string | yes | Hash of the artifact version to restore |
| `idempotencyKey` | string | yes | Required |

## Deduplication Rules

Intent deduplication MUST be applied by `(kind, target, idempotencyKey)` tuple.
If `idempotencyKey` is absent, deduplication is by `(kind, target)` only.
Duplicate intents within the same Decision MUST be collapsed to one (see `mpc.features.compose`).
