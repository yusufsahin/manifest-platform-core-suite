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

## Kütüphane Yapısı (Hierarchical)

MPC artık daha organize bir hiyerarşik yapıya sahiptir:

### 1. Kernel (`mpc.kernel`)
Çekirdek yapı taşları ve parser temelleri.
- `mpc.kernel.contracts`: EventEnvelope, Decision, Error modelleri.
- `mpc.kernel.canonical`: Deterministik JSON + Stable Hash.
- `mpc.kernel.ast`: Canonical AST modelleri.
- `mpc.kernel.parser`: DSL / YAML / JSON → AST dönüştürücü.
- `mpc.kernel.errors`: Hata kodu registry.

### 2. Features (`mpc.features`)
Domain spesifik engine'ler ve özellikler.
- `mpc.features.workflow`: Pure FSM motoru (Native).
- `mpc.features.expr`: Tip güvenli expression engine.
- `mpc.features.policy`: Olay bazlı kural değerlendirme.
- `mpc.features.acl`: RBAC / ABAC ve field masking.
- `mpc.features.overlay`: Manifest merge / patch operasyonları.
- `mpc.features.redaction`: PII ve hassas veri gizleme.

### 3. Tooling (`mpc.tooling`)
Geliştirme ve doğrulama araçları.
- `mpc.tooling.validator`: Structural + Semantic denetleyiciler.
- `mpc.tooling.registry`: Hashed, immutable runtime artifact yönetimi.
- `mpc.tooling.uischema`: UI generation için şema araçları.
- `mpc.tooling.conformance`: Uyumluluk test setleri.
- **MPC Studio**: Tarayıcı tabanlı görsel manifest editörü (`tooling/mpc-studio`).

### 4. Enterprise (`mpc.enterprise`)
Kurumsal seviye yönetim ve imzalama.
- `mpc.enterprise.governance`: Signing, attestation ve lifecycle.

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

- [docs/SCOPE.md](docs/SCOPE.md) — Kapsam: PII dışında; redaction yalnızca yapılandırılabilir denyKeys
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
