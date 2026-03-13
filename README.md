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
pip install mpc
```

```python
from mpc.kernel.parser import parse
from mpc.kernel.meta.models import DomainMeta, KindDef
from mpc.tooling.validator.structural import validate_structural
from mpc.tooling.validator.semantic import validate_semantic

manifest_text = open("rules.manifest", encoding="utf-8").read()
ast = parse(manifest_text)

# Domain meta'nızı uygulamanıza göre doldurun.
meta = DomainMeta(
    kinds=[
        KindDef(name="Workflow", required_props=["states", "transitions", "initial"]),
    ]
)

struct_errors = validate_structural(ast, meta)
sem_errors = validate_semantic(ast)
all_errors = struct_errors + sem_errors

if all_errors:
    for err in all_errors:
        print(f"[{err.code}] {err.message}")
else:
    print("Manifest doğrulaması başarılı.")
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
mpc-conformance run packages/core-conformance/fixtures
```

---

> MPC bir son kullanıcı ürünü değildir.
> Manifest odaklı platform geliştiren ekipler için tasarlanmış **Python kütüphane setidir**.
