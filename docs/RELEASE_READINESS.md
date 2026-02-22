# MPC Release-Readiness Matrisi

**Tarih:** 2026-02-22  
**Temel:** 126 dosya (39 md + 87 json, invalid=0), 26 fixture case / 10 kategori

---

## Epic A — Contracts + Canonicalization

| Kriter | Durum | Notlar |
|---|---|---|
| 5 kontrat şeması var ve geçerli JSON | PASS | event, decision, error, intent, trace |
| Her şema `additionalProperties: false` | PASS | tümü kapalı |
| `timestamp` format doğrulaması | FAIL | `"type":"string"` yeterli değil; `format: date-time` yok |
| Enterprise meta (`artifactHash`, `engine`) şema-level zorunlu | FAIL | açıklama olarak var, `if/then` conditional yok |
| `Intent.kind` enum ile kısıtlı | FAIL | serbest string; taxonomy sadece dokümanda |
| Canonical spec normative ve idempotence kuralı yazılı | PASS | HASH_CANONICAL_SPEC.md |
| Definition ordering kuralı fixture ile test ediliyor | PASS | canonical/01 |
| Key sorting fixture ile test ediliyor | PASS | canonical/02 |

**Olgunluk: 5/8 — %62**

---

## Epic B — AST + Meta + Parser + Validator + Registry

| Kriter | Durum | Notlar |
|---|---|---|
| Canonical AST root alanları tanımlı | PASS | MASTER_SPEC §6 |
| Node `kind` + `id` zorunluluğu belgelenmiş | PASS | |
| Meta-metadata schema tanımlı | PARTIAL | dokümanda var, JSON şeması yok |
| Parser eşdeğerlik kuralı yazılı | PASS | §8: DSL/YAML/JSON → aynı AST |
| Parser eşdeğerlik fixture ile test ediliyor | FAIL | fixture yok |
| Validator cycle/duplicate/ref kuralları yazılı | PASS | §9 |
| Validator fixture kategorisi | FAIL | fixture yok |
| Registry cache key (astHash+metaHash+engine) tanımlı | PASS | §10 |

**Olgunluk: 5/8 — %62**

---

## Epic C — Expression Engine

| Kriter | Durum | Notlar |
|---|---|---|
| Host eval yasağı açık | PASS | MASTER_SPEC §11 |
| Budget limitleri (steps, depth, time, regex) tanımlı | PASS | |
| `E_BUDGET_EXCEEDED` registry'de | PASS | |
| Type mismatch fixture | PASS | expr/01 |
| Steps budget aşım fixture | PASS | expr/02 |
| Depth budget aşım fixture | PASS | expr/03 |
| Unknown function fixture | PASS | expr/04 |
| Time/regex limit fixture | FAIL | test yok |
| Clock injection kuralı | PASS | meta.json clock alanı |

**Olgunluk: 7/9 — %78**

---

## Epic D — Engines + Composition

| Kriter | Durum | Notlar |
|---|---|---|
| FSM pure tanımlı, GuardPort/AuthPort belgelenmiş | PASS | §12 + CONSUMING_APP_MODEL.md |
| Valid transition fixture | PASS | workflow/02 |
| Unknown transition fixture | PASS | workflow/01 |
| No initial state fixture | PASS | workflow/03 |
| Policy deny-wins fixture | PASS | policy/01 |
| Policy allow-all (positive path) fixture | FAIL | fixture yok |
| ACL RBAC deny fixture | PASS | acl/01 |
| ACL maskField intent fixture | PASS | acl/02 |
| ACL ABAC fixture | FAIL | fixture yok |
| Compose deny-wins fixture | PASS | compose/01 |
| Compose all-allow fixture | PASS | compose/02 |
| Intent dedup kuralı yazılı | PASS | INTENT_TAXONOMY.md |
| Intent dedup fixture | FAIL | test yok |

**Olgunluk: 9/13 — %69**

---

## Epic E — Overlay / Imports / Namespaces

| Kriter | Durum | Notlar |
|---|---|---|
| Replace op fixture | PASS | overlay/01 |
| Merge op fixture | PASS | overlay/02 |
| Conflict hard-error fixture | PASS | overlay/03 |
| Append/remove/patch op fixture | FAIL | 3 op hiç test edilmemiş |
| Stable selector (kind, namespace, id) kuralı | PASS | notes.md'de açık |
| Import/alias/semver kuralı | FAIL | BACKLOG E2'de var, fixture yok |
| Namespace collision fixture | FAIL | test yok |

**Olgunluk: 4/7 — %57**

---

## Epic F — Enterprise Governance

| Kriter | Durum | Notlar |
|---|---|---|
| Lifecycle 7 aşaması tanımlı | PASS | RFC_ENTERPRISE_ADDENDUM.md §1 |
| Artifact bundle bileşenleri tanımlı | PASS | §2 |
| Activation protokolü tanımlı | PASS | §3 |
| Signature zorunlu fixture | PASS | governance/01 |
| Signature invalid fixture | PASS | governance/02 |
| Attestation missing fixture | FAIL | test yok |
| Quota/budget fixture | FAIL | test yok |
| Rollback / canary / kill-switch fixture | FAIL | test yok |
| Idempotency key kontrolü fixture | FAIL | test yok |
| Audit record fixture | FAIL | test yok |

**Olgunluk: 5/10 — %50**

---

## Epic G — Security Hardening

| Kriter | Durum | Notlar |
|---|---|---|
| Trace PII redaction fixture | PASS | security/01 |
| Error PII redaction fixture | PASS | security/02 |
| `denyByDefaultACL` preset'te tanımlı | PASS | preset-security-hardened |
| `allowNowFunction=false` preset'te tanımlı | PASS | |
| Safe regex budget fixture | FAIL | test yok |
| Plugin governance belgesi | FAIL | sadece BACKLOG G3'te var |
| Redaction kayıp-key senaryosu fixture | FAIL | test yok |

**Olgunluk: 4/7 — %57**

---

## Epic H — Conformance Suite & CI Gates

| Kriter | Durum | Notlar |
|---|---|---|
| Runner spec normative ve kategori eşlemesi tam | PASS | CONFORMANCE_RUNNER_SPEC.md |
| Tüm JSON geçerli (machine-checked) | PASS | 87/87 valid |
| Her fixture 4 dosya yapısına uyuyor | PASS | meta/input/expected/notes |
| Gerçek runner kodu workspace'de var | FAIL | sadece spec var |
| CI gate (`pytest mpc_conformance/`) çalışıyor | FAIL | doğrulanamadı |
| Compatibility matrix belgesi | FAIL | yok |
| Semver ve breaking change kuralı belgesi | FAIL | sadece BACKLOG H3'te var |
| Kategori başına ≥ 3 case | PARTIAL | policy = 1 case |

**Olgunluk: 4/8 — %50**

---

## Özet Tablo

| Epic | Alan | PASS/Toplam | Olgunluk |
|---|---|---:|---:|
| A | Contracts + Canonicalization | 5/8 | %62 |
| B | AST + Meta + Parser + Validator | 5/8 | %62 |
| C | Expression Engine | 7/9 | **%78** |
| D | Engines + Composition | 9/13 | %69 |
| E | Overlay / Imports | 4/7 | %57 |
| F | Enterprise Governance | 5/10 | %50 |
| G | Security Hardening | 4/7 | %57 |
| H | Conformance + CI Gates | 4/8 | %50 |
| **Toplam** | | **43/70** | **%61** |

---

## Release Gate Kararı

### Alfa (spec hazır) ✓
Epics A, B, C, D spec kalitesi alfa çıkışına yeterli.

### Beta için blocker ✗
- **E:** append / remove / patch fixture eksik
- **F:** quota / rollback / attestation fixture eksik
- **H:** runner kodu yok; policy kategorisinde ≥ 3 case zorunluluğu karşılanmıyor

### Production için blocker ✗
Tüm FAIL maddeleri kapatılmalı; özellikle:
1. Runner referans implementasyonu + `pytest mpc_conformance/` CI entegrasyonu
2. `Intent.kind` enum şema kısıtı
3. `timestamp` `format: date-time` kısıtı
4. Enterprise meta `if/then` şema zorunluluğu
5. Parser eşdeğerlik + validator + namespace collision fixture'ları
