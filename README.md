# Manifest Platform Core Suite (MPC)

**Manifest odaklı platform geliştirmek için Python kütüphane seti.**

Uygulamanıza "kullanıcılar kural/konfigürasyon tanımlasın, biz çalıştıralım"
özelliği ekliyorsanız, sıfırdan inşa etmenize gerek yok. MPC bunu hazır verir.

---

## Problem

Her platform ekibi aynı döngüyü yeniden kuruyor:

```text
Kullanıcı YAML/JSON yazar
    → Validate et
    → Compile et
    → Runtime'da olayı değerlendir
    → Karar ver + yan etkileri üret
    → Audit kaydı tut
```

Bu döngüyü sağlıklı yazmak — determinizm, tip güvenliği, bütçe limitleri,
imzalama, audit — aylar sürer ve çoğunlukla yarım kalır.

**MPC bu döngüyü bir kere, doğru şekilde yapar. Siz domain'inize odaklanırsınız.**

---

## Mimari

```text
Sizin uygulamanız
│
├── Domain meta'nızı tanımlarsınız    (hangi kind, type, fonksiyon geçerli)
├── Kullanıcılarınız manifest yazar   (DSL / YAML / JSON)
│
│   ┌──────────────────────────────────────────────────────┐
│   │                    MPC Libraries                     │
│   │                                                      │
│   │  mpc-core-parser    →  Canonical AST                 │
│   │  mpc-core-validator →  Structural + Semantic check   │
│   │  mpc-core-compiler  →  Immutable artifact            │
│   │                                                      │
│   │  Runtime:                                            │
│   │  EventEnvelope → [policy + acl + workflow + expr]    │
│   │              →  Decision + Intent + Trace            │
│   └──────────────────────────────────────────────────────┘
│
├── Decision'a göre uygulamanız harekete geçer
└── Intent'leri kendi adapter'larınız işler
```

---

## Hızlı Başlangıç

```bash
pip install mpc-core mpc-policy mpc-acl
```

```python
from mpc.core import ManifestEngine
from mpc.presets import load_preset
from mpc.contracts import EventEnvelope, Actor, Object

# 1. Engine'i kurun
engine = ManifestEngine(
    preset=load_preset("preset-generic-full"),
    meta=my_domain_meta,        # kendi allowed kind/type tanımlarınız
)

# 2. Kullanıcının manifest'ini compile edin
artifact = engine.compile(open("rules.yaml").read())

# 3. Runtime'da olay geldiğinde değerlendirin
event = EventEnvelope(
    name="order.approve",
    kind="transition",
    timestamp="2026-02-22T10:00:00Z",
    actor=Actor(id="user-42", type="user", roles=["manager"]),
    object=Object(type="order", id="order-99", state="pending"),
)

decision = engine.evaluate(event, artifact)

if decision.allow:
    for intent in decision.intents:
        my_intent_handler(intent)   # notify, audit, maskField, vs.
else:
    raise PermissionError([r.code for r in decision.reasons])
```

---

## Kütüphane Seti

### Kernel (zorunlu)

| Paket | Ne yapar |
| --- | --- |
| `mpc-core-contracts` | EventEnvelope, Decision, Error, Intent, Trace modelleri |
| `mpc-core-canonical` | Deterministik JSON + SHA-256 stable hash |
| `mpc-core-ast` | Canonical AST modeli |
| `mpc-core-errors` | Hata kodu registry ve yardımcılar |

### Feature (ihtiyaca göre seçin)

| Paket | Ne yapar |
| --- | --- |
| `mpc-core-parser` | DSL / YAML / JSON → AST |
| `mpc-core-validator` | Structural + semantic doğrulama |
| `mpc-core-expr` | Tip güvenli expression engine (host eval yok) |
| `mpc-core-policy` | Olay bazlı kural değerlendirme, deny-wins |
| `mpc-core-acl` | RBAC + opsiyonel ABAC + field masking |
| `mpc-core-workflow` | Pure FSM + Guard / Auth port binding |
| `mpc-core-overlay` | Manifest merge / patch operasyonları |
| `mpc-core-decision-compose` | Birden fazla engine kararını birleştirme |
| `mpc-core-trace` | Structured audit trace |

### Enterprise

| Paket | Ne yapar |
| --- | --- |
| `mpc-enterprise-governance` | Signing, attestation, lifecycle |
| `mpc-enterprise-activation` | Atomic artifact deploy + audit |
| `mpc-enterprise-quotas` | Tenant bazlı kota ve bütçe yönetimi |

---

## Preset'ler

| Preset | Kullanım |
| --- | --- |
| `preset-generic-min` | Prototipleme, sıkı limitler |
| `preset-generic-full` | Genel amaçlı üretim |
| `preset-security-hardened` | Güvenlik kritik platformlar |
| `preset-ui-friendly` | UI schema yoğun uygulamalar |

---

## Belgeler

- [docs/CONSUMING_APP_MODEL.md](docs/CONSUMING_APP_MODEL.md) — MPC'yi uygulamanıza nasıl entegre edersiniz
- [docs/MASTER_SPEC.md](docs/MASTER_SPEC.md) — Normative gereksinimler
- [docs/INTENT_TAXONOMY.md](docs/INTENT_TAXONOMY.md) — Intent kind listesi
- [docs/RFC_CORE_CONTRACTS.md](docs/RFC_CORE_CONTRACTS.md) — Kontrat şemaları
- [docs/RFC_ENTERPRISE_ADDENDUM.md](docs/RFC_ENTERPRISE_ADDENDUM.md) — Enterprise özellikler
- [docs/HASH_CANONICAL_SPEC.md](docs/HASH_CANONICAL_SPEC.md) — Canonicalization kuralları
- [docs/ERROR_CODE_REGISTRY.md](docs/ERROR_CODE_REGISTRY.md) — Hata ve reason kod registryleri
- [docs/BACKLOG.md](docs/BACKLOG.md) — Epic ve story listesi
- [packages/core-conformance/](packages/core-conformance/) — Conformance fixture'ları

---

## Conformance

Tüm MPC implementasyonları `packages/core-conformance/fixtures/` altındaki
fixture'ları geçmek zorundadır. Fixture'lar davranışı tanımlar — belgeler değil.

```bash
pytest mpc_conformance/
```

---

> MPC bir son kullanıcı ürünü değildir.
> Manifest odaklı platform geliştiren ekipler için tasarlanmış **Python kütüphane setidir**.
