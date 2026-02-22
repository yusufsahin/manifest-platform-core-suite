# Notes

Minimal valid Intent requires only `kind`. All other fields (target, params,
idempotencyKey) are optional. The kind value MUST appear in INTENT_TAXONOMY.md.
Runner validates against intent.schema.json.
