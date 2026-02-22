# Consuming App Model — MPC Entegrasyon Kılavuzu

Bu belge, MPC kütüphanelerini kullanan bir uygulamanın nasıl inşa edileceğini açıklar.

---

## MPC Ne Verir, Siz Ne Yaparsınız

```text
MPC'nin sorumluluğu          Sizin sorumluluğunuz
────────────────────         ──────────────────────────────
AST modeli                   Domain meta tanımı
Parser (DSL/YAML/JSON)       Preset seçimi veya özel preset
Validator (structural)       Semantic kurallar (meta ile)
Expression engine            Port implementasyonları
Policy engine                Intent adapter'ları
ACL engine                   Manifest storage / versioning
Workflow (FSM)               UI / API katmanı
Canonical hash               Kullanıcıya sunulan DSL/YAML
Error registry
Audit trace
Enterprise signing (opt.)
```

---

## Entegrasyon Adımları

### Adım 1 — Domain Meta'yı Tanımla

Meta, MPC'ye "bu uygulamada hangi manifest yapıları geçerli?" diyorsunuzdur.

```python
from mpc.core.meta import DomainMeta, KindDef, TypeDef, FunctionDef

my_domain_meta = DomainMeta(
    schema_version=1,
    kinds=[
        KindDef(
            name="ApprovalPolicy",
            required_props=["effect", "conditions"],
            allowed_types=["string", "bool", "int"],
        ),
        KindDef(
            name="WorkflowDef",
            required_props=["initial_state", "transitions"],
        ),
    ],
    allowed_functions=[
        FunctionDef(name="len",   args=["string|array"], returns="int",  cost=2),
        FunctionDef(name="regex", args=["string","string"], returns="bool", cost=20),
    ],
)
```

### Adım 2 — Engine'i Kur

```python
from mpc.core import ManifestEngine
from mpc.presets import load_preset

engine = ManifestEngine(
    preset=load_preset("preset-generic-full"),
    meta=my_domain_meta,
)
```

### Adım 3 — Manifest'i Compile Et

Kullanıcı bir manifest kaydedince compile edin ve artifact'ı saklayın.
Artifact immutable'dır — her değişiklik yeni bir compile üretir.

```python
# YAML, JSON veya DSL — parser otomatik algılar
with open("user_rules.yaml") as f:
    raw = f.read()

try:
    artifact = engine.compile(raw)
    # artifact.hash  → stable SHA-256, cache key olarak kullanın
    # artifact.data  → compiled payload
    store.save(artifact.hash, artifact)
except MPCValidationError as e:
    # e.errors → list[Error], her biri code + message + source_map içerir
    return {"errors": [err.to_dict() for err in e.errors]}
```

### Adım 4 — Runtime'da Olay Değerlendir

Sisteminizde bir olay olduğunda (HTTP isteği, mesaj, zamanlayıcı vs.)
EventEnvelope oluşturun ve engine'e verin.

```python
from mpc.contracts import EventEnvelope, Actor, Object

def handle_order_approve(request):
    event = EventEnvelope(
        name="order.approve",
        kind="transition",
        timestamp=utcnow(),
        actor=Actor(
            id=request.user_id,
            type="user",
            roles=request.user_roles,
            claims=request.claims,
        ),
        object=Object(
            type="order",
            id=request.order_id,
            state=request.current_state,
            attributes=request.order_attrs,
        ),
        context={"tenant_id": request.tenant_id},
    )

    artifact = store.load(active_artifact_hash)
    decision  = engine.evaluate(event, artifact)
    return decision
```

### Adım 5 — Decision'a Göre Hareket Et

```python
decision = engine.evaluate(event, artifact)

if not decision.allow:
    reasons = [r.code for r in decision.reasons]
    raise PermissionDenied(reasons)

# Intent'leri kendi adapter'larınızla işleyin
for intent in decision.intents:
    match intent.kind:
        case "notify":
            notification_service.send(
                target=intent.target,
                template=intent.params["template"],
                idempotency_key=intent.idempotency_key,
            )
        case "audit":
            audit_log.append(intent)
        case "maskField":
            response.redact(intent.target, mask=intent.params.get("mask", "***"))
        case "rateLimit":
            rate_limiter.apply(intent)
```

---

## Port Implementasyonları

MPC bazı davranışları sizden bekler. Bunlar **port** arayüzleridir.

### GuardPort — Workflow Geçiş Koşulları

Bir FSM geçişinin önüne ek iş mantığı koymak için implement edin.

```python
from mpc.workflow.ports import GuardPort

class MyGuardPort(GuardPort):
    def check(self, transition: str, context: dict) -> bool:
        # örnek: "publish" geçişi için manager onayı zorunlu
        if transition == "publish":
            return context.get("manager_approved") is True
        return True

engine = ManifestEngine(
    preset=load_preset("preset-generic-full"),
    meta=my_domain_meta,
    guard=MyGuardPort(),
)
```

### AuthPort — Workflow Kimlik Doğrulama

Geçiş yapan aktörün yetkisini dış sistemde doğrulamak için implement edin.

```python
from mpc.workflow.ports import AuthPort

class MyAuthPort(AuthPort):
    def authorize(self, actor_id: str, transition: str) -> bool:
        return permission_service.check(actor_id, f"workflow:{transition}")

engine = ManifestEngine(..., auth=MyAuthPort())
```

---

## Preset Özelleştirme

Hazır preset'ler yetmiyorsa kendi preset'inizi tanımlayabilirsiniz:

```python
from mpc.presets import Preset, Limits, PolicyStrategy, FeatureFlags

my_preset = Preset(
    name="my-app-preset",
    preset_version="1.0.0",
    meta_schema_version=1,
    limits=Limits(
        max_manifest_nodes=2000,
        max_expr_steps=1000,
        max_expr_depth=20,
        max_eval_time_ms=30,
        max_regex_ops=500,
    ),
    feature_flags=FeatureFlags(
        allow_now_function=False,
        allow_regex=True,
        deny_by_default_acl=True,
    ),
    default_policy_strategy=PolicyStrategy(compose="deny-wins"),
)

engine = ManifestEngine(preset=my_preset, meta=my_domain_meta)
```

---

## Multi-Tenant Kullanım

Her tenant'ın kendi artifact'ı olabilir. Engine thread-safe ve stateless'tır;
artifact'ı evaluate çağrısında geçin.

```python
def evaluate_for_tenant(tenant_id: str, event: EventEnvelope) -> Decision:
    artifact_hash = tenant_store.get_active_hash(tenant_id)
    artifact      = artifact_store.load(artifact_hash)
    return engine.evaluate(event, artifact)
```

Tenant bazlı kota yönetimi için `mpc-enterprise-quotas` paketini ekleyin:

```python
from mpc.enterprise.quotas import QuotaEnforcer

enforcer = QuotaEnforcer(backend=redis_backend)

@enforcer.guard(tenant_id=lambda e: e.context["tenant_id"])
def evaluate_for_tenant(tenant_id, event):
    ...
```

---

## Hata Yönetimi

MPC her hatayı `Error` nesnesiyle döner. Kod her zaman
`ERROR_CODE_REGISTRY.md`'deki listeden gelir.

```python
from mpc.core.errors import MPCError, MPCValidationError, MPCBudgetError

try:
    artifact = engine.compile(raw)
except MPCValidationError as e:
    for err in e.errors:
        print(f"[{err.severity}] {err.code}: {err.message}")
        if err.source:
            print(f"  → {err.source.file}:{err.source.line}")

except MPCBudgetError as e:
    # E_BUDGET_EXCEEDED veya E_EXPR_LIMIT_*
    print(f"Bütçe aşıldı: {e.code}")
```

---

## Hangi Paketi Ne Zaman Eklersiniz

```text
İhtiyacınız                          Eklenecek paket
─────────────────────────────────    ────────────────────────────
Temel kontratlar ve hash             mpc-core-contracts
                                     mpc-core-canonical

YAML/JSON manifest parse             mpc-core-parser
                                     mpc-core-validator

Koşul ifadeleri (expr)               mpc-core-expr

"Kim ne yapabilir" (ACL)             mpc-core-acl

Olay bazlı kurallar (policy)         mpc-core-policy

Durum makinesi (workflow)            mpc-core-workflow

Birden fazla engine birleştirme      mpc-core-decision-compose

Manifest varyantları (overlay)       mpc-core-overlay

Audit/debug trace                    mpc-core-trace

Artifact imzalama + lifecycle        mpc-enterprise-governance
Atomic deploy + audit log            mpc-enterprise-activation
Tenant kota yönetimi                 mpc-enterprise-quotas
```

---

## Conformance Testleri

Kütüphanelerin doğru çalıştığını doğrulamak için conformance runner'ı çalıştırın:

```bash
pip install mpc-conformance
mpc-conformance run packages/core-conformance/fixtures/
```

Tüm fixture'lar geçmelidir. Geçemeyen fixture implementation hatasına işaret eder.

---

Daha fazla bilgi için: [MASTER_SPEC.md](MASTER_SPEC.md) ve [INTENT_TAXONOMY.md](INTENT_TAXONOMY.md)
