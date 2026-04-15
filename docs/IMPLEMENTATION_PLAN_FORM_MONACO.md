# MPC — Cursor Implementation Plan

> **Bu plan Cursor tarafından uygulanacaktır.**
> Her adım bağımsız bir görevdir. Sırayla uygula. Adımlar arası bağımlılıklar belirtilmiştir.

---

## PROJE KÖKLERİ

```
Python paketi  : manifest-platform-core-suite/
Studio (React) : manifest-platform-core-suite/tooling/mpc-studio/
```

---

## UYGULAMA SIRASI (ÖNERİLEN) (YENİ)

Bu planı minimum sürtünmeyle uygulamak için önerilen sıra:

- **A (Bug fixes)**: Parser/AST/UISchema/workflow determinism gibi temel düzeltmeler.
- **B (Form Engine)**: FormDef/FieldDef + FormEngine + field state + (opsiyonel) tek çağrı package helper.
- **C (Monaco DSL)**: Editor language/theme/snippet’ler (Form işiyle bağımsız; paralel yürütülebilir).
- **D (Studio FormPreview)**: Worker message + engine API + panel + App wiring.
- **E (Worker runtime bundle)**: `requiredFiles` ve/veya dinamik loader; Form/Expr/ACL import’ları garanti altına alınır.
- **F (Enterprise ready)**:
  - **F-1/F-2** remote parity + artifact lifecycle
  - **F-3** security posture + limits + fail-open/closed policy
  - **F-4** conformance fixtures + CI gates
  - **F-5** observability + diagnostics yüzeyi

Önerilen paralelleştirme:
- C bölümü, A/B/D/E ile paralel yapılabilir.
- F-4 (fixtures) ile F-5 (observability) paralel yapılabilir; ama F-1/F-2 bitmeden remote parity testi anlamlı olmaz.

## HEDEFLER (GÜNCELLENDİ)

Bu planın hedefi yalnızca “FormPreview demo” değil, **üretim-kalitesine yakın** bir form hattı kurmaktır:

- **Tek kaynak gerçeklik**: Form kuralları (required/validation/visibility/readonly/ACL) mümkünse **Python engine** tarafında hesaplanır; UI sadece render eder.
- **Stabil sözleşme**: UI’ya dönen çıktı, **JSON Schema + UI Schema + FieldState** şeklinde açık bir kontrat olur (sadece dağınık `x-*` alanları değil).
- **Güvenli worker entegrasyonu**: DSL string’i Python’a aktarırken injection riski yok (Pyodide globals).
- **Ölçeklenebilir React UI**: Basit input map’inin ötesinde, alan tipleri/array/object/layout gibi konulara hazır.

---

## ENTERPRISE READY HEDEFLERİ (YENİ)

Bu plan “enterprise ready” sayılabilmesi için aşağıdaki ek hedefleri de kapsar:

- **Runtime parity**: Studio (local Pyodide) ile remote runtime aynı `FormPackage` kontratını üretir.
- **Multi-tenant**: `tenant_id` ve “active artifact” modeliyle form paketi üretimi desteklenir (remote).
- **Governance**: manifest/artefact lifecycle (draft/active), imza doğrulama (varsa), audit izleri ve deterministik çıktılar.
- **Güvenlik posture**: fail-open/closed davranışları açıkça tanımlı ve konfigüre edilebilir; input limits ve timeouts mevcut.
- **Conformance + CI gate**: FormDef/FormEngine için fixture + runner + Studio contract gate eklenir.
- **Gözlemlenebilirlik**: FormPackage üretimi envelope diagnostics + duration metrikleri ile raporlanır (local + remote).

## TASARIM KARARLARI (GÜNCELLENDİ)

- **Form sözleşmesi**: Worker → UI arasında tek bir payload modeli taşınır: `FormPackage`.
  - `jsonSchema`: JSON Schema
  - `uiSchema`: UI Schema (renderer ipuçları)
  - `fieldState`: `visible/readonly` gibi runtime durumlar
  - `validation`: submit doğrulama sonucu (field error listesi)
- **Değerlendirme yeri**:
  - `visibilityExpr/readonlyExpr/validationExpr` değerlendirmesi **Python (Pyodide)** tarafında yapılır.
  - React sadece bu çıktıyı uygular (tek kaynak gerçeklik, tutarlı davranış).
- **Güvenlik**: DSL ve kullanıcı girdileri Python’a **globals** ile aktarılır (string interpolation yok).

---

## ÖN KOŞULLAR / DEPENDENCY’LER (YENİ)

### Studio (React) bağımlılıkları

`FormPreview.tsx` (RJSF tabanlı) için aşağıdaki paketler gereklidir:

- `@rjsf/core`
- `@rjsf/validator-ajv8`

Kurulum:

```bash
cd tooling/mpc-studio
npm install @rjsf/core @rjsf/validator-ajv8
```

> Not: Eğer RJSF kullanmak istemezsen, `FormPreview.tsx` RJSF import’ları içermemeli (elle renderer yaklaşımı).

### Remote runtime (MVP) (YENİ)

Bu repo içinde Studio’nun remote mode’u için minimal bir FastAPI runtime bulunur:

- Kod: `tooling/mpc_runtime/app.py`
- Doküman: `tooling/mpc-runtime/README.md`

Çalıştırma (PowerShell):

```bash
python -m pip install -r tooling/mpc-runtime/requirements.txt
$env:PYTHONPATH='src'
python -m uvicorn tooling.mpc_runtime.app:app --reload --port 8787
```

Studio’yu remote’a bağlamak:

```bash
$env:VITE_MPC_RUNTIME_MODE='remote'
$env:VITE_MPC_RUNTIME_BASE_URL='http://localhost:8787/api/v1/rule-artifacts'
cd tooling/mpc-studio
npm run dev
```

# BÖLÜM A — Python Engine Bug Fixes
> Bağımlılık yok. Hepsi bağımsız uygulanabilir.

---

## A-1 · UISchema generator — child node yanlış kind_def alıyor

**Dosya:** `src/mpc/tooling/uischema/generator.py`

**Sorun:** `_build_node_schema` içinde child node'lara parent'ın `kind_def`'i geçiriliyor.  
`kind_def` child'ın kendi kind tanımına bakmalı.

**Değişiklik:**

`generate_ui_schema` fonksiyonunu şu şekilde değiştir:

```python
# ÖNCE
def generate_ui_schema(
    ast: ManifestAST,
    meta: DomainMeta,
) -> UISchemaResult:
    schemas: dict[str, Any] = {}
    warnings: list[str] = []

    kind_defs = {k.name: k for k in meta.kinds}
    defs_sorted = sorted(ast.defs, key=lambda d: (d.kind, d.id))

    for node in defs_sorted:
        schema_key = f"{node.kind}:{node.id}"
        kind_def = kind_defs.get(node.kind)
        schema = _build_node_schema(node, kind_def, warnings)
        schemas[schema_key] = schema

    return UISchemaResult(schemas=schemas, warnings=warnings)
```

```python
# SONRA
def generate_ui_schema(
    ast: ManifestAST,
    meta: DomainMeta,
) -> UISchemaResult:
    schemas: dict[str, Any] = {}
    warnings: list[str] = []

    kind_defs = {k.name: k for k in meta.kinds}
    defs_sorted = sorted(ast.defs, key=lambda d: (d.kind, d.id))

    for node in defs_sorted:
        schema_key = f"{node.kind}:{node.id}"
        kind_def = kind_defs.get(node.kind)
        schema = _build_node_schema(node, kind_def, warnings, kind_defs)  # kind_defs eklendi
        schemas[schema_key] = schema

    return UISchemaResult(schemas=schemas, warnings=warnings)
```

`_build_node_schema` fonksiyon imzasını ve child çağrısını değiştir:

```python
# ÖNCE
def _build_node_schema(
    node: ASTNode,
    kind_def: KindDef | None,
    warnings: list[str],
) -> dict[str, Any]:
    ...
    if node.children:
        children_schemas = []
        for child in sorted(node.children, key=lambda c: (c.kind, c.id)):
            children_schemas.append(_build_node_schema(child, kind_def, warnings))
        schema["x-children"] = children_schemas
```

```python
# SONRA
def _build_node_schema(
    node: ASTNode,
    kind_def: KindDef | None,
    warnings: list[str],
    kind_defs: dict[str, KindDef] | None = None,  # yeni parametre
) -> dict[str, Any]:
    ...
    if node.children:
        children_schemas = []
        _kd = kind_defs or {}
        for child in sorted(node.children, key=lambda c: (c.kind, c.id)):
            child_kind_def = _kd.get(child.kind)  # child'ın kendi kind_def'i
            children_schemas.append(_build_node_schema(child, child_kind_def, warnings, _kd))
        schema["x-children"] = children_schemas
```

---

## A-2 · WorkflowSpec.to_json() — deterministic serialization

**Dosya:** `src/mpc/features/workflow/fsm.py`

**Sorun:** `WorkflowSpec.to_json()` `__dict__` kullanıyor; `set` JSON serialize edilemez, deterministik değil.

**Değişiklik — `WorkflowSpec.to_json` metodunu tamamen değiştir:**

```python
# ÖNCE
def to_json(self) -> str:
    """Serialize spec to JSON for designer tools."""
    return json.dumps(self.__dict__, default=lambda o: o.__dict__ if hasattr(o, '__dict__') else str(o))
```

```python
# SONRA
def to_json(self) -> str:
    """Serialize spec to canonical JSON for designer tools."""
    from mpc.kernel.canonical.serializer import canonicalize

    def _to_serializable(obj: Any) -> Any:
        if hasattr(obj, '__dataclass_fields__'):
            return {k: _to_serializable(v) for k, v in vars(obj).items()}
        if isinstance(obj, (set, frozenset)):
            return sorted(_to_serializable(i) for i in obj)
        if isinstance(obj, (list, tuple)):
            return [_to_serializable(i) for i in obj]
        return obj

    return canonicalize(_to_serializable(self))
```

---

## A-3 · FSM factory — snake_case/camelCase alignment

**Dosya:** `src/mpc/features/workflow/fsm.py`

**Sorun:** `from_fixture_input` hem `on_enter` hem `onEnter` kabul eder; `from_ast_node` sadece `on_enter`.
Ortak helper ekleyerek her ikisini normalize et.

**Adım 1:** `WorkflowEngine` class tanımının hemen üstüne bu helper fonksiyonu ekle:

```python
def _normalize_transition_dict(tr: dict[str, Any]) -> dict[str, Any]:
    """camelCase ve snake_case transition anahtarlarını normalize eder."""
    on_enter = tr.get("on_enter") or tr.get("onEnter") or []
    on_leave = tr.get("on_leave") or tr.get("onLeave") or []
    if isinstance(on_enter, str):
        on_enter = [on_enter]
    if isinstance(on_leave, str):
        on_leave = [on_leave]
    return {
        "from":        str(tr.get("from", "")),
        "to":          str(tr.get("to", "")),
        "on":          str(tr.get("on", tr.get("to", ""))),
        "guard":       tr.get("guard"),
        "auth_roles":  tr.get("auth_roles") or tr.get("authRoles") or [],
        "on_enter":    list(on_enter),
        "on_leave":    list(on_leave),
        "rule_type":   tr.get("rule_type", "fixed"),
        "timeout_ms":  tr.get("timeout_ms") or tr.get("timeout"),
    }
```

**Adım 2:** `from_fixture_input` içindeki transitions döngüsünü değiştir:

```python
# ÖNCE (from_fixture_input içinde)
for tr in data.get("transitions") or []:
    if isinstance(tr, dict):
        on_enter = tr.get("on_enter") or tr.get("onEnter") or []
        on_leave = tr.get("on_leave") or tr.get("onLeave") or []
        if isinstance(on_enter, str): on_enter = [on_enter]
        if isinstance(on_leave, str): on_leave = [on_leave]
        transitions.append(Transition(
            from_state=str(tr.get("from", "")),
            to_state=str(tr.get("to", "")),
            on=str(tr.get("on", tr.get("to", ""))),
            guard=tr.get("guard"),
            auth_roles=tr.get("authRoles", tr.get("auth_roles", [])),
            on_enter=list(on_enter),
            on_leave=list(on_leave),
            rule_type=tr.get("rule_type", "fixed"),
            timeout_ms=tr.get("timeout_ms", tr.get("timeout")),
        ))
```

```python
# SONRA (from_fixture_input içinde)
for tr in data.get("transitions") or []:
    if isinstance(tr, dict):
        n = _normalize_transition_dict(tr)
        transitions.append(Transition(
            from_state=n["from"],
            to_state=n["to"],
            on=n["on"],
            guard=n["guard"],
            auth_roles=n["auth_roles"],
            on_enter=n["on_enter"],
            on_leave=n["on_leave"],
            rule_type=n["rule_type"],
            timeout_ms=n["timeout_ms"],
        ))
```

**Adım 3:** `from_ast_node` içindeki transitions döngüsünü de aynı helper'a geçir:

```python
# ÖNCE (from_ast_node içinde)
for tr in node.properties.get("transitions", []):
    if isinstance(tr, dict):
        on_enter = tr.get("on_enter") or tr.get("onEnter") or []
        on_leave = tr.get("on_leave") or tr.get("onLeave") or []
        transitions.append(Transition(
            from_state=str(tr.get("from", "")),
            to_state=str(tr.get("to", "")),
            on=str(tr.get("on", tr.get("to", ""))),
            guard=tr.get("guard"),
            auth_roles=tr.get("auth_roles", tr.get("authRoles", [])),
            on_enter=list(on_enter),
            on_leave=list(on_leave),
            rule_type=tr.get("rule_type", "fixed"),
        ))
```

```python
# SONRA (from_ast_node içinde)
for tr in node.properties.get("transitions", []):
    if isinstance(tr, dict):
        n = _normalize_transition_dict(tr)
        transitions.append(Transition(
            from_state=n["from"],
            to_state=n["to"],
            on=n["on"],
            guard=n["guard"],
            auth_roles=n["auth_roles"],
            on_enter=n["on_enter"],
            on_leave=n["on_leave"],
            rule_type=n["rule_type"],
            timeout_ms=n["timeout_ms"],
        ))
```

---

## A-4 · Normalizer — boş kind/id guard

**Dosya:** `src/mpc/kernel/ast/normalizer.py`

**Sorun:** `kind` veya `id` boş string olduğunda normalizer sessizce geçiyor. Validator sonra anlamsız hata üretiyor.

**Adım 1:** `src/mpc/kernel/errors/registry.py` içindeki `ERROR_CODES` frozenset'e bu kodu ekle:

```python
# Mevcut ERROR_CODES frozenset içine şunu ekle:
"E_PARSE_MISSING_REQUIRED",
```

**Adım 2:** `normalizer.py`'deki `_normalize_node` fonksiyonuna guard ekle:

```python
# ÖNCE
def _normalize_node(raw: dict[str, Any]) -> ASTNode:
    props = {k: v for k, v in raw.items() if k not in _RESERVED_KEYS}
    ...
    return ASTNode(
        kind=raw.get("kind", ""),
        id=raw.get("id", ""),
        ...
    )
```

```python
# SONRA
def _normalize_node(raw: dict[str, Any]) -> ASTNode:
    kind = raw.get("kind", "")
    node_id = raw.get("id", "")
    if not kind:
        raise MPCError("E_PARSE_MISSING_REQUIRED", "Node must have a non-empty 'kind' field")
    if not node_id:
        raise MPCError("E_PARSE_MISSING_REQUIRED", f"Node of kind '{kind}' must have a non-empty 'id' field")

    props = {k: v for k, v in raw.items() if k not in _RESERVED_KEYS}
    ...
    return ASTNode(
        kind=kind,
        id=node_id,
        ...
    )
```

`MPCError`'ı import et — dosyanın başına ekle:

```python
from mpc.kernel.errors import MPCError
```

---

## A-5 · ASTNode.properties — mutation guard

**Dosya:** `src/mpc/kernel/ast/models.py`

**Sorun:** `frozen=True` dataclass ama `properties: dict` mutable. `node.properties["k"] = "v"` çalışır, engel yok.

**Değişiklik:**

```python
# ÖNCE
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from mpc.kernel.contracts.models import SourceMap


@dataclass(frozen=True)
class ASTNode:
    kind: str
    id: str
    name: str | None = None
    properties: dict[str, Any] = field(default_factory=dict)
    children: list[ASTNode] = field(default_factory=list)
    source: SourceMap | None = None
```

```python
# SONRA
from __future__ import annotations

from dataclasses import dataclass, field
from types import MappingProxyType
from typing import Any

from mpc.kernel.contracts.models import SourceMap


@dataclass(frozen=True)
class ASTNode:
    kind: str
    id: str
    name: str | None = None
    properties: dict[str, Any] = field(default_factory=dict)
    children: list[ASTNode] = field(default_factory=list)
    source: SourceMap | None = None

    def __post_init__(self) -> None:
        # dict ve list'i immutable yap — frozen=True ile tutarlı
        object.__setattr__(self, "properties", MappingProxyType(dict(self.properties)))
        object.__setattr__(self, "children", tuple(self.children))
```

> **Dikkat:** Bu değişiklikten sonra `properties` artık `MappingProxyType` döner.
> Aşağıdaki dosyalarda `node.properties` üzerinde `dict` varsayımı yapan yerler var,
> bunlar `dict(node.properties)` ile güncellenmeli:
> - `src/mpc/kernel/ast/normalizer.py` — zaten dict oluşturuyor, sorun yok
> - `src/mpc/tooling/validator/structural.py` — iterate ediyor, sorun yok
> - `src/mpc/features/workflow/fsm.py` — `.get()` kullanıyor, sorun yok
> - `src/mpc/features/acl/engine.py` — `.get()` kullanıyor, sorun yok

---

---

# BÖLÜM B — Form Engine (Python)
> **Bağımlılık:** A-4 ve A-5 tamamlanmış olmalı.

---

## B-1 · Form kind tanımları

**Yeni dosya:** `src/mpc/features/form/__init__.py`

```python
"""Form engine — FormDef ve FieldDef kind desteği."""
from mpc.features.form.engine import FormEngine, FormField, FormSchema, ValidationResult

__all__ = ["FormEngine", "FormField", "FormSchema", "ValidationResult"]
```

**Yeni dosya:** `src/mpc/features/form/kinds.py`

```python
"""FormDef ve FieldDef için KindDef tanımları.

Consuming app kendi DomainMeta'sına FORM_KINDS listesini ekler:

    from mpc.features.form.kinds import FORM_KINDS
    meta = DomainMeta(kinds=[...existing..., *FORM_KINDS], ...)
"""
from __future__ import annotations

from mpc.kernel.meta.models import KindDef

FORM_KINDS: list[KindDef] = [
    KindDef(
        name="FormDef",
        required_props=["fields"],
        optional_props=["title", "workflowState", "workflowTrigger"],
    ),
    KindDef(
        name="FieldDef",
        required_props=["type"],
        optional_props=[
            "label", "required", "default", "min", "max",
            "options", "placeholder",
            "validationExpr", "visibilityExpr", "readonlyExpr",
        ],
    ),
]

FORM_FIELD_TYPES: list[str] = [
    "string", "number", "boolean",
    "select", "multiselect",
    "date", "textarea", "hidden",
]
```

---

## B-2 · FormEngine (GÜNCELLENDİ: kontrat + field state)

**Yeni dosya:** `src/mpc/features/form/engine.py`

> **Kontrat hedefi (UI için):**
>
> - `jsonSchema`: JSON Schema uyumlu form şeması (validation’ın *statik* kısmı: type/required/min/max/enum…)
> - `uiSchema`: UI render ipuçları (placeholder, widget, order, layout, help…)
> - `fieldState`: runtime field durumları (visible/readonly + computed errors gibi)
>
> Bu üçlü, worker’dan React’e taşınacak “tek stabil sözleşme” olacak.

### B-2.1 · Expr evaluation sözleşmesi (NETLEŞTİR) (YENİ)

Worker’daki `EVALUATE_EXPR` akışı `ExprEngine.evaluate(EXPR, context=ctx, ...)` şeklinde **string expression** değerlendiriyor.
FormEngine’deki `validationExpr/visibilityExpr/readonlyExpr` alanları da MVP’de **string** olarak değerlendirilmelidir.

- Expression bir `str` ise: doğrudan `ExprEngine.evaluate(expr, context=...)`
- (Opsiyonel) Expression bir `dict` IR ise: ayrı bir “IR mode” kararıyla desteklenir; MVP’de zorunlu değil.

```python
"""Form engine — FormDef ASTNode'larından FormSchema üretir ve submission validate eder.

Entegrasyonlar:
- ExprEngine  : validationExpr / visibilityExpr / readonlyExpr evaluate
- ACLEngine   : Intent(maskField) → field readonly=True
- WorkflowEngine: workflowState ile aktif form eşleştirme
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from mpc.kernel.ast.models import ASTNode, ManifestAST
from mpc.kernel.contracts.models import Error
from mpc.kernel.meta.models import DomainMeta


# ---------------------------------------------------------------------------
# Data models
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class FormField:
    id: str
    type: str
    label: str | None = None
    required: bool = False
    default: Any = None
    min: Any = None
    max: Any = None
    options: list[str] = field(default_factory=list)
    placeholder: str | None = None
    validation_expr: str | None = None
    visibility_expr: str | None = None
    readonly_expr: str | None = None


@dataclass(frozen=True)
class FormSchema:
    id: str
    title: str | None
    workflow_state: str | None
    workflow_trigger: str | None
    fields: list[FormField]

    def to_json_schema(self) -> dict[str, Any]:
        """JSON Schema uyumlu çıktı üretir (form renderer için)."""
        properties: dict[str, Any] = {}
        required: list[str] = []

        for f in self.fields:
            prop: dict[str, Any] = {"type": _field_type_to_json(f.type), "x-field-id": f.id}
            if f.label:
                prop["title"] = f.label
            if f.default is not None:
                prop["default"] = f.default
            if f.min is not None:
                prop["minimum" if f.type == "number" else "minLength"] = f.min
            if f.max is not None:
                prop["maximum" if f.type == "number" else "maxLength"] = f.max
            if f.options:
                prop["enum"] = f.options
            if f.placeholder:
                prop["x-placeholder"] = f.placeholder
            if f.validation_expr:
                prop["x-validation-expr"] = f.validation_expr
            if f.visibility_expr:
                prop["x-visibility-expr"] = f.visibility_expr
            if f.readonly_expr:
                prop["x-readonly-expr"] = f.readonly_expr

            properties[f.id] = prop
            if f.required:
                required.append(f.id)

        schema: dict[str, Any] = {
            "type": "object",
            "title": self.title or self.id,
            "x-form-id": self.id,
            "properties": properties,
        }
        if required:
            schema["required"] = sorted(required)
        if self.workflow_state:
            schema["x-workflow-state"] = self.workflow_state
        if self.workflow_trigger:
            schema["x-workflow-trigger"] = self.workflow_trigger
        return schema

    def to_ui_schema(self) -> dict[str, Any]:
        """UI renderer için UI schema üretir (widget/layout/placeholder/order).

        Not: Basit bir başlangıç sözleşmesi; consuming app isterse genişletir.
        """
        ui: dict[str, Any] = {
            "ui:order": [f.id for f in self.fields],
        }
        for f in self.fields:
            ui[f.id] = {}
            if f.placeholder:
                ui[f.id]["ui:placeholder"] = f.placeholder
            # Basit widget önerileri
            if f.type in ("textarea",):
                ui[f.id]["ui:widget"] = "textarea"
            if f.type in ("hidden",):
                ui[f.id]["ui:widget"] = "hidden"
            if f.type in ("date",):
                ui[f.id]["ui:widget"] = "date"
        return ui


@dataclass(frozen=True)
class FieldValidationError:
    field_id: str
    message: str
    expr: str | None = None


@dataclass(frozen=True)
class ValidationResult:
    valid: bool
    errors: list[FieldValidationError] = field(default_factory=list)


@dataclass(frozen=True)
class FieldState:
    field_id: str
    visible: bool = True
    readonly: bool = False


# ---------------------------------------------------------------------------
# Engine
# ---------------------------------------------------------------------------

@dataclass
class FormEngine:
    """FormDef ASTNode'larından FormSchema üretir ve submission validate eder."""

    ast: ManifestAST
    meta: DomainMeta | None = None

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def get_forms(self) -> list[FormSchema]:
        """Manifest'teki tüm FormDef'leri döndürür."""
        return [
            self._node_to_form(node)
            for node in self.ast.defs
            if node.kind == "FormDef"
        ]

    def get_form(self, form_id: str) -> FormSchema | None:
        """Belirli bir FormDef'i döndürür; bulunamazsa None."""
        for node in self.ast.defs:
            if node.kind == "FormDef" and node.id == form_id:
                return self._node_to_form(node)
        return None

    def get_forms_for_state(self, workflow_state: str) -> list[FormSchema]:
        """Belirli bir workflow state'ine bağlı formları döndürür."""
        return [f for f in self.get_forms() if f.workflow_state == workflow_state]

    def validate_submission(
        self,
        form_id: str,
        data: dict[str, Any],
        *,
        actor_roles: list[str] | None = None,
        actor_attrs: dict[str, Any] | None = None,
    ) -> ValidationResult:
        """
        Her field'ın validationExpr'ını ExprEngine ile evaluate eder.
        meta yoksa sadece required kontrolü yapılır.
        """
        form = self.get_form(form_id)
        if form is None:
            return ValidationResult(
                valid=False,
                errors=[FieldValidationError(field_id="__form__", message=f"FormDef '{form_id}' not found")],
            )

        errors: list[FieldValidationError] = []

        for f in form.fields:
            value = data.get(f.id)

            # required kontrolü
            if f.required and (value is None or value == ""):
                errors.append(FieldValidationError(
                    field_id=f.id,
                    message=f"'{f.label or f.id}' alanı zorunludur",
                ))
                continue

            # validationExpr (ExprEngine gerektirir)
            if f.validation_expr and self.meta:
                expr_result = self._eval_expr(
                    f.validation_expr,
                    context={**data, "role": (actor_roles or [""])[0]},
                )
                if expr_result is False:
                    errors.append(FieldValidationError(
                        field_id=f.id,
                        message=f"'{f.label or f.id}' doğrulama koşulunu sağlamıyor",
                        expr=f.validation_expr,
                    ))

        return ValidationResult(valid=len(errors) == 0, errors=errors)

    def compute_field_state(
        self,
        form_id: str,
        data: dict[str, Any],
        *,
        actor_roles: list[str] | None = None,
        actor_attrs: dict[str, Any] | None = None,
    ) -> list[FieldState]:
        """
        visibilityExpr / readonlyExpr + ACL ile field state hesaplar.
        UI tarafı bu çıktıyı uygular (tek kaynak gerçeklik).
        """
        form = self.get_form(form_id)
        if form is None:
            return []

        readonly_map = self.apply_acl(form_id, actor_roles=actor_roles, actor_attrs=actor_attrs)
        states: list[FieldState] = []

        for f in form.fields:
            visible = True
            readonly = bool(readonly_map.get(f.id, False))

            if f.visibility_expr and self.meta:
                v = self._eval_expr(f.visibility_expr, context={**data, "role": (actor_roles or [""])[0]})
                if v is False:
                    visible = False

            if f.readonly_expr and self.meta:
                r = self._eval_expr(f.readonly_expr, context={**data, "role": (actor_roles or [""])[0]})
                if r is True:
                    readonly = True

            states.append(FieldState(field_id=f.id, visible=visible, readonly=readonly))

        return states
    def apply_acl(
        self,
        form_id: str,
        *,
        actor_roles: list[str] | None = None,
        actor_attrs: dict[str, Any] | None = None,
    ) -> dict[str, bool]:
        """
        ACLEngine'den maskField intent'lerini okur.
        Döndürülen dict: {field_id: is_readonly}
        """
        if self.meta is None:
            return {}

        readonly_map: dict[str, bool] = {}
        form = self.get_form(form_id)
        if form is None:
            return {}

        try:
            from mpc.features.acl.engine import ACLEngine
            acl = ACLEngine(ast=self.ast, meta=self.meta)
            for f in form.fields:
                result = acl.check(
                    "read", f.id,
                    actor_roles=actor_roles,
                    actor_attrs=actor_attrs,
                )
                has_mask = any(i.kind == "maskField" for i in result.intents)
                readonly_map[f.id] = has_mask
        except Exception:
            pass

        return readonly_map

    # ------------------------------------------------------------------
    # Internals
    # ------------------------------------------------------------------

    def _node_to_form(self, node: ASTNode) -> FormSchema:
        props = dict(node.properties)
        fields: list[FormField] = []

        for child in node.children:
            if child.kind == "FieldDef":
                fields.append(self._node_to_field(child))

        # eski stil: fields property'si list of dict
        for f_raw in props.get("fields", []):
            if isinstance(f_raw, dict):
                fields.append(FormField(
                    id=f_raw.get("id", ""),
                    type=f_raw.get("type", "string"),
                    label=f_raw.get("label"),
                    required=bool(f_raw.get("required", False)),
                    default=f_raw.get("default"),
                    min=f_raw.get("min"),
                    max=f_raw.get("max"),
                    options=list(f_raw.get("options", [])),
                    placeholder=f_raw.get("placeholder"),
                    validation_expr=f_raw.get("validationExpr"),
                    visibility_expr=f_raw.get("visibilityExpr"),
                    readonly_expr=f_raw.get("readonlyExpr"),
                ))

        return FormSchema(
            id=node.id,
            title=node.name or props.get("title"),
            workflow_state=props.get("workflowState"),
            workflow_trigger=props.get("workflowTrigger"),
            fields=fields,
        )

    def _node_to_field(self, node: ASTNode) -> FormField:
        props = dict(node.properties)
        return FormField(
            id=node.id,
            type=props.get("type", "string"),
            label=node.name or props.get("label"),
            required=bool(props.get("required", False)),
            default=props.get("default"),
            min=props.get("min"),
            max=props.get("max"),
            options=list(props.get("options", [])),
            placeholder=props.get("placeholder"),
            validation_expr=props.get("validationExpr"),
            visibility_expr=props.get("visibilityExpr"),
            readonly_expr=props.get("readonlyExpr"),
        )

    def _eval_expr(self, expr: str, context: dict[str, Any]) -> Any:
        """ExprEngine üzerinden expression evaluate eder; hata durumunda True döner (fail-open)."""
        if self.meta is None:
            return True
        try:
            from mpc.features.expr.engine import ExprEngine
            engine = ExprEngine(meta=self.meta)
            result = engine.evaluate({"lit": expr} if not isinstance(expr, dict) else expr, context=context)
            return result.value
        except Exception:
            return True


def _field_type_to_json(field_type: str) -> str:
    mapping = {
        "string": "string", "textarea": "string", "hidden": "string",
        "number": "number",
        "boolean": "boolean",
        "select": "string", "multiselect": "array",
        "date": "string",
    }
    return mapping.get(field_type, "string")
```

---

## B-3 · CLI'ya form komutu ekle (opsiyonel)

**Dosya:** `src/mpc/tooling/cli.py`

Mevcut CLI komutlarının sonuna `list-forms` komutunu ekle:

```python
# cli.py içindeki argparse/click/typer sistemine uyan şekilde ekle
# Diğer komutlarla aynı pattern'ı kullan

def _run_list_forms(args):
    """mpc list-forms <file> — manifest'teki form tanımlarını listeler."""
    import json
    from mpc.kernel.parser import parse
    from mpc.features.form.engine import FormEngine
    from mpc.features.form.kinds import FORM_KINDS
    from mpc.kernel.meta.models import DomainMeta

    with open(args.file, "r", encoding="utf-8") as f:
        ast = parse(f.read())

    meta = DomainMeta(kinds=FORM_KINDS)
    engine = FormEngine(ast=ast, meta=meta)
    forms = engine.get_forms()

    output = [
        {
            "id": form.id,
            "title": form.title,
            "workflowState": form.workflow_state,
            "workflowTrigger": form.workflow_trigger,
            "fieldCount": len(form.fields),
            "fields": [{"id": f.id, "type": f.type, "required": f.required} for f in form.fields],
            "jsonSchema": form.to_json_schema(),
        }
        for form in forms
    ]
    print(json.dumps(output, indent=2, ensure_ascii=False))
```

---

## B-4 · (ÖNERİLEN) Tek çağrıda form paketleme helper'ı

> UI tarafı için “3 ayrı çağrı” yerine tek çağrı idealdir.

**Yeni yardımcı fonksiyon/çıktı sözleşmesi önerisi:**

- `get_form_package(form_id, data, actor_roles, actor_attrs)` → `{ jsonSchema, uiSchema, fieldState, validation }`

Bu sayede React paneli “tek response” ile render + state + error’ları çizer.

---

---

# BÖLÜM C — Monaco DSL Dili
> **Bağımlılık:** Yok. Bağımsız uygulanabilir.

---

## C-1 · MPC DSL language definition

**Yeni dosya:** `tooling/mpc-studio/src/engine/mpc-dsl-language.ts`

```typescript
/**
 * Monaco Editor için MPC DSL dil kaydı.
 * grammar.lark'tan türetilen tokenizer + snippet autocomplete.
 */

export function registerMpcDslLanguage(monaco: any): void {
  // Dil zaten kayıtlıysa tekrar kaydetme
  const existing = monaco.languages.getLanguages().find((l: any) => l.id === 'mpc-dsl');
  if (existing) return;

  monaco.languages.register({ id: 'mpc-dsl', extensions: ['.manifest', '.mpc'] });

  // -------------------------------------------------------------------------
  // Tokenizer (grammar.lark kurallarından türetildi)
  // -------------------------------------------------------------------------
  monaco.languages.setMonarchTokensProvider('mpc-dsl', {
    defaultToken: '',
    tokenPostfix: '.mpc',

    keywords: ['def', 'true', 'false', 'null'],
    directives: ['schema', 'namespace', 'name', 'version'],

    tokenizer: {
      root: [
        // Satır yorumları
        [/\/\/.*$/, 'comment'],

        // @direktifler
        [/@(schema|namespace|name|version)\b/, 'keyword.directive'],

        // def anahtar kelimesi
        [/\bdef\b/, 'keyword.def'],

        // Boolean ve null literaller
        [/\b(true|false|null)\b/, 'constant.language'],

        // String
        [/"([^"\\]|\\.)*"/, 'string'],

        // Sayı (integer ve float)
        [/-?\d+\.\d+/, 'number.float'],
        [/-?\d+/, 'number'],

        // Yapı karakterleri
        [/[{}]/, 'delimiter.curly'],
        [/[\[\]]/, 'delimiter.bracket'],
        [/:/, 'delimiter.colon'],
        [/,/, 'delimiter.comma'],

        // İdentifier (kind adları, id'ler, property key'ler)
        [/[a-zA-Z_][a-zA-Z0-9_.\-]*/, {
          cases: {
            '@keywords': 'keyword',
            '@default': 'identifier',
          },
        }],

        // Boşluk
        [/\s+/, 'white'],
      ],
    },
  });

  // -------------------------------------------------------------------------
  // Tema renklendirmesi (mpc-dark theme tanımını genişlet)
  // -------------------------------------------------------------------------
  monaco.editor.defineTheme('mpc-dark', {
    base: 'vs-dark',
    inherit: true,
    rules: [
      { token: 'keyword.directive',  foreground: 'C792EA', fontStyle: 'bold' }, // @schema vb. — mor
      { token: 'keyword.def',        foreground: '82AAFF', fontStyle: 'bold' }, // def — mavi
      { token: 'constant.language',  foreground: 'F78C6C' },                   // true/false/null — turuncu
      { token: 'string',             foreground: 'C3E88D' },                   // string — yeşil
      { token: 'number',             foreground: 'F78C6C' },                   // sayı — turuncu
      { token: 'number.float',       foreground: 'F78C6C' },
      { token: 'comment',            foreground: '546E7A', fontStyle: 'italic' },
      { token: 'delimiter.colon',    foreground: '89DDFF' },
      { token: 'identifier',         foreground: 'EEFFFF' },
    ],
    colors: {
      'editor.background': '#12141c00',
    },
  });

  // -------------------------------------------------------------------------
  // Autocomplete provider
  // -------------------------------------------------------------------------
  monaco.languages.registerCompletionItemProvider('mpc-dsl', {
    triggerCharacters: ['@', ' ', '\n'],

    provideCompletionItems(model: any, position: any) {
      const word = model.getWordUntilPosition(position);
      const lineContent = model.getLineContent(position.lineNumber);
      const range = {
        startLineNumber: position.lineNumber,
        endLineNumber:   position.lineNumber,
        startColumn:     word.startColumn,
        endColumn:       word.endColumn,
      };

      const suggestions: any[] = [];

      // @direktif önerileri
      const directives = [
        { label: '@schema',    detail: 'Schema versiyonu (integer)',      insert: '@schema 1' },
        { label: '@namespace', detail: 'Manifest namespace\'i',           insert: '@namespace "${1:acme}"' },
        { label: '@name',      detail: 'Manifest adı',                    insert: '@name "${1:my-rules}"' },
        { label: '@version',   detail: 'Semantic versiyon',               insert: '@version "${1:1.0.0}"' },
      ];

      for (const d of directives) {
        suggestions.push({
          label: d.label,
          kind: monaco.languages.CompletionItemKind.Keyword,
          detail: d.detail,
          insertText: d.insert,
          insertTextRules: monaco.languages.CompletionItemInsertTextRule.InsertAsSnippet,
          range,
        });
      }

      // def <Kind> snippet'leri
      const kinds = [
        {
          kind: 'Policy',
          snippet: 'def Policy ${1:id} "${2:Name}" {\n\teffect: "${3:allow}"\n\tpriority: ${4:10}\n\t$0\n}',
        },
        {
          kind: 'Workflow',
          snippet: 'def Workflow ${1:id} "${2:Name}" {\n\tinitial: "${3:draft}"\n\tstates: ["${3:draft}", "${4:published}"]\n\ttransitions: []\n\t$0\n}',
        },
        {
          kind: 'ACL',
          snippet: 'def ACL ${1:id} "${2:Name}" {\n\taction: "${3:read}"\n\tresource: "${4:*}"\n\troles: ["${5:admin}"]\n\teffect: "${6:allow}"\n\t$0\n}',
        },
        {
          kind: 'Entity',
          snippet: 'def Entity ${1:id} "${2:Name}" {\n\t$0\n}',
        },
        {
          kind: 'FormDef',
          snippet: 'def FormDef ${1:form_id} "${2:Form Adı}" {\n\tworkflowState: "${3:draft}"\n\tworkflowTrigger: "${4:submit}"\n\tdef FieldDef ${5:field_id} {\n\t\ttype: "${6:string}"\n\t\tlabel: "${7:Alan Adı}"\n\t\trequired: ${8:true}\n\t}\n\t$0\n}',
        },
        {
          kind: 'FieldDef',
          snippet: 'def FieldDef ${1:field_id} "${2:Alan Adı}" {\n\ttype: "${3|string,number,boolean,select,textarea,date|}"\n\trequired: ${4:false}\n\t$0\n}',
        },
      ];

      for (const k of kinds) {
        suggestions.push({
          label: `def ${k.kind}`,
          kind: monaco.languages.CompletionItemKind.Snippet,
          detail: `${k.kind} tanımı`,
          insertText: k.snippet,
          insertTextRules: monaco.languages.CompletionItemInsertTextRule.InsertAsSnippet,
          documentation: { value: `\`\`\`mpc-dsl\n${k.snippet.replace(/\$\{[^}]*\}/g, '...')}\n\`\`\`` },
          range,
        });
      }

      // field type değerleri — "type": yazıldığında
      if (lineContent.includes('type:')) {
        for (const t of ['string', 'number', 'boolean', 'select', 'multiselect', 'date', 'textarea', 'hidden']) {
          suggestions.push({
            label: `"${t}"`,
            kind: monaco.languages.CompletionItemKind.EnumMember,
            insertText: `"${t}"`,
            range,
          });
        }
      }

      return { suggestions };
    },
  });

  // -------------------------------------------------------------------------
  // Hover provider — kind adları için kısa açıklama
  // -------------------------------------------------------------------------
  const kindDocs: Record<string, string> = {
    Policy:   '**Policy** — Kural tanımı. `effect: allow|deny`, `priority`, koşullar.',
    Workflow: '**Workflow** — FSM tanımı. `initial`, `states[]`, `transitions[]`.',
    ACL:      '**ACL** — Erişim kontrolü. RBAC + ABAC destekler.',
    Entity:   '**Entity** — Domain varlık tanımı.',
    FormDef:  '**FormDef** — Form tanımı. `workflowState`, `workflowTrigger`, `FieldDef` children.',
    FieldDef: '**FieldDef** — Form alanı. `type`, `required`, `validationExpr`, `visibilityExpr`.',
  };

  monaco.languages.registerHoverProvider('mpc-dsl', {
    provideHover(model: any, position: any) {
      const word = model.getWordAtPosition(position);
      if (!word) return null;
      const doc = kindDocs[word.word];
      if (!doc) return null;
      return {
        range: new monaco.Range(position.lineNumber, word.startColumn, position.lineNumber, word.endColumn),
        contents: [{ value: doc }],
      };
    },
  });
}
```

---

## C-2 · ManifestEditor — Python → mpc-dsl

**Dosya:** `tooling/mpc-studio/src/components/ManifestEditor.tsx`

```typescript
// ÖNCE
import Editor, { type OnMount } from '@monaco-editor/react';
```

```typescript
// SONRA
import Editor, { type OnMount } from '@monaco-editor/react';
import { registerMpcDslLanguage } from '../engine/mpc-dsl-language';
```

```typescript
// ÖNCE
        <Editor
          height="100%"
          defaultLanguage="python"
          theme="vs-dark"
          ...
          beforeMount={(monaco) => {
            monaco.editor.defineTheme('mpc-theme', {
              base: 'vs-dark',
              inherit: true,
              rules: [],
              colors: {
                'editor.background': '#12141c00',
              }
            });
          }}
        />
```

```typescript
// SONRA
        <Editor
          height="100%"
          defaultLanguage="mpc-dsl"
          theme="mpc-dark"
          ...
          beforeMount={(monaco) => {
            registerMpcDslLanguage(monaco);  // DSL dilini ve mpc-dark theme'ini kaydet
          }}
        />
```

---

---

# BÖLÜM D — mpc-studio FormPreview Komponenti
> **Bağımlılık:** B-1, B-2 (ve önerilen B-4) + worker mesajı tamamlanmış olmalı.

---

## D-1 · Worker — FORM_PACKAGE mesajı (GÜNCELLENDİ)

**Dosya:** `tooling/mpc-studio/src/engine/worker.ts`

Mevcut `GENERATE_UISCHEMA` case'in hemen altına ekle.

> **Uyumluluk notu (mpc-studio mevcut worker kontratı):**
> `mpc-engine.ts` hem envelope’lu hem envelope’suz payload’ları destekliyor (`unwrapEnvelopePayload`).
> Ancak Studio’da metrik/diagnostics görünürlüğü için **Form paketini `postEnvelope(...)` ile dönmek** önerilir (LIST_DEFINITIONS/PREVIEW_DEFINITION gibi).

```typescript
// Not: Bu “unsafe interpolation” örneğini kullanma; aşağıdaki globals tabanlı versiyonu uygula.
```

> **Not:** Worker içindeki Python string interpolasyonu için dsl değişkenini güvenli şekilde geçirmek üzere
> Pyodide'ın `globals` mekanizmasını kullan:

### D-1.1 · Enterprise-ready davranışlar (mevcut gerçek) (YENİ)

Bu repo’da `GENERATE_FORM_PACKAGE` implementasyonu aşağıdaki davranışları zaten içerir; eklerken dokümandaki snippet’i birebir kopyalamak yerine mevcut worker yapısına uyumlu şekilde ilerle:

- **Limits**: `VITE_MPC_FORM_MAX_DSL_BYTES`, `VITE_MPC_FORM_MAX_DATA_BYTES`, `VITE_MPC_FORM_MAX_ACTOR_BYTES`
- **Timeout**: `VITE_MPC_FORM_PACKAGE_TIMEOUT_MS`
- **Fail-open/closed**: `VITE_MPC_FORM_FAIL_OPEN` (default `true`)
- **Envelope diagnostics**: limit/timeout/expr failure için `diagnostics[]`

```typescript
// Güvenli versiyon (injection riski yok):
case 'GENERATE_FORM_PACKAGE': {
  const { dsl, formId, data, actorRoles, actorAttrs } = payload;
  pyodide.globals.set('_form_dsl_input', dsl);
  pyodide.globals.set('_form_id', formId);
  pyodide.globals.set('_form_data', data || {});
  pyodide.globals.set('_actor_roles', actorRoles || []);
  pyodide.globals.set('_actor_attrs', actorAttrs || {});
  const result = await pyodide.runPythonAsync(`
import json
from mpc.kernel.parser import parse
from mpc.features.form.engine import FormEngine
from mpc.features.form.kinds import FORM_KINDS
from mpc.kernel.meta.models import DomainMeta

try:
    ast = parse(_form_dsl_input)
    meta = DomainMeta(kinds=FORM_KINDS)
    engine = FormEngine(ast=ast, meta=meta)
    form = engine.get_form(_form_id)
    if form is None:
        json.dumps({"ok": False, "error": f"FormDef '{_form_id}' not found"})
    else:
        json_schema = form.to_json_schema()
        ui_schema = form.to_ui_schema()
        field_state = [s.__dict__ for s in engine.compute_field_state(_form_id, _form_data, actor_roles=_actor_roles, actor_attrs=_actor_attrs)]
        validation = engine.validate_submission(_form_id, _form_data, actor_roles=_actor_roles, actor_attrs=_actor_attrs)
        json.dumps({
            "ok": True,
            "package": {
                "jsonSchema": json_schema,
                "uiSchema": ui_schema,
                "fieldState": field_state,
                "validation": {
                    "valid": validation.valid,
                    "errors": [e.__dict__ for e in validation.errors],
                },
            },
        })
except Exception as e:
    json.dumps({"ok": False, "error": str(e)})
`);
  const parsed = JSON.parse(result as string);
  postEnvelope(id, 'FORM_PACKAGE', requestId, parsed.ok ? parsed.package : {}, startedAt);
  break;
}
```

---

## D-2 · MPCEngine — generateFormPackage metodu (GÜNCELLENDİ)

**Dosya:** `tooling/mpc-studio/src/engine/mpc-engine.ts`

`generateUISchema` metodunun hemen altına ekle:

```typescript
async generateFormPackage(input: {
  dsl: string;
  formId: string;
  data?: Record<string, unknown>;
  actorRoles?: string[];
  actorAttrs?: Record<string, unknown>;
}): Promise<any> {
  const response = await this.postMessage<unknown>({
    type: 'GENERATE_FORM_PACKAGE',
    payload: input,
  });
  return this.unwrapEnvelopePayload<any>(response);
}
```

---

## D-3 · FormPreview komponenti (GÜNCELLENDİ: package tüket)

**Yeni dosya:** `tooling/mpc-studio/src/components/FormPreview.tsx`

> Bu komponent iki aşamalı ilerler:
> 1) “Hangi form?” seçimi: `selectedDefinition` (kind=`FormDef`) veya bir select ile definition list.
> 2) `generateFormPackage({ dsl, formId, data, actorRoles, actorAttrs })` ile `FormPackage` alıp render eder.

**Refactor notu:** Bu dosyadaki örnekte `onGenerate(): Promise<JsonSchema[]>` gibi “schema listesi” dönen API var. Yeni tasarımda
`FormPackage` döndüğümüz için prop’u `onGeneratePackage(input)` şeklinde değiştir.

### D-3.1 · (ÖNERİLEN) React form renderer stratejisi

Bu dokümandaki `FieldInput` bazlı “elle input render” yaklaşımı MVP için iyi; üretimde hızla karmaşıklaşır.

Önerilen iki yol:

- **Yol A (hızlı ve standart)**: JSON Schema renderer kullan (`@rjsf/core`).
  - `jsonSchema` → formun iskeleti + validation kuralları
  - `uiSchema` → widget/placeholder/order/layout
  - `validation.errors` → submit sonrası error göstermek için
  - `fieldState` → `uiSchema` üzerinde `ui:disabled/ui:readonly/ui:widget` gibi alanlarla uygulanır

- **Yol B (tam kontrol)**: `react-hook-form` + kendi “field registry”n.
  - Bu yol, fieldState/ACL/workflow gibi kuralları daha ince kontrolle uygular ama daha çok kod ister.

### D-3.2 · Form seçimi (FormDef → formId) (YENİ)

Studio zaten `LIST_DEFINITIONS` ile definition listesi ve `selectedDefinitionId` state’ini tutuyor (`App.tsx`).
FormPreview panelinde form seçimi için iki pratik seçenek var:

- **Seçenek A (önerilen)**: `selectedDefinition` kind=`FormDef` ise direkt onu kullan.
- **Seçenek B (fallback)**: Panel içinde bir `<select>` ile tüm `FormDef`’leri listele.

Örnek wiring (App.tsx içinden `FormPreview`’a gereken prop’lar):

```typescript
// App.tsx içinde
const selectedFormId = selectedDefinition?.kind === 'FormDef' ? selectedDefinition.id : '';

if (sidebarTab === 'form-preview') {
  return (
    <FormPreview
      formId={selectedFormId || 'signup'} // fallback form id (demo)
      onGeneratePackage={async ({ formId, data }) =>
        mpcEngine.generateFormPackage({ dsl, formId, data })
      }
    />
  );
}
```

> Not: Daha iyi UX için `selectedFormId` boşsa, `definitionItems.filter(d => d.kind === 'FormDef')` ile bir select gösterip kullanıcıya seçtir.

```typescript
import { useEffect, useMemo, useState } from 'react';
import { Layout, RefreshCw, AlertTriangle } from 'lucide-react';
import Form from '@rjsf/core';

type FormPackage = {
  jsonSchema: Record<string, unknown>;
  uiSchema: Record<string, unknown>;
  fieldState: Array<{ field_id: string; visible: boolean; readonly: boolean }>;
  validation: { valid: boolean; errors: Array<{ field_id: string; message: string; expr?: string | null }> };
};

interface FormPreviewProps {
  formId: string;
  onGeneratePackage: (input: {
    formId: string;
    data: Record<string, unknown>;
    actorRoles?: string[];
    actorAttrs?: Record<string, unknown>;
  }) => Promise<FormPackage>;
}

function applyFieldStateToUiSchema(uiSchema: Record<string, any>, fieldState: FormPackage['fieldState']) {
  const next = { ...uiSchema };
  for (const state of fieldState) {
    const existing = (next[state.field_id] ?? {}) as Record<string, unknown>;
    next[state.field_id] = {
      ...existing,
      // RJSF uyumlu ipuçları:
      'ui:disabled': state.readonly,
      'ui:readonly': state.readonly,
      'ui:widget': state.visible ? existing['ui:widget'] : 'hidden',
    };
  }
  return next;
}

export default function FormPreview({ formId, onGeneratePackage }: FormPreviewProps) {
  const [loading, setLoading] = useState(false);
  const [engineError, setEngineError] = useState<string | null>(null);
  const [pkg, setPkg] = useState<FormPackage | null>(null);
  const [formData, setFormData] = useState<Record<string, unknown>>({});

  const uiSchema = useMemo(() => {
    if (!pkg) return {};
    return applyFieldStateToUiSchema((pkg.uiSchema ?? {}) as Record<string, any>, pkg.fieldState ?? []);
  }, [pkg]);

  const handleGenerate = async () => {
    setLoading(true);
    setEngineError(null);
    try {
      const next = await onGeneratePackage({ formId, data: formData });
      setPkg(next);
    } catch (err) {
      setEngineError(err instanceof Error ? err.message : String(err));
      setPkg(null);
    } finally {
      setLoading(false);
    }
  };

  // İlk render’da otomatik üret (istersen kaldır)
  useEffect(() => {
    void handleGenerate();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [formId]);

  return (
    <div className="h-full flex flex-col bg-white/[0.01]">
      <div className="p-4 border-b border-white/5 flex items-center justify-between">
        <div className="flex items-center gap-2">
          <Layout className="w-4 h-4 text-violet-400" />
          <h2 className="text-xs font-bold uppercase tracking-widest text-white">Form Preview</h2>
          <span className="text-[10px] text-gray-600 font-mono">{formId}</span>
        </div>
        <button
          onClick={handleGenerate}
          disabled={loading}
          className="p-1.5 rounded-lg hover:bg-white/5 text-gray-500 hover:text-white transition-all disabled:opacity-50"
          title="Regenerate"
        >
          <RefreshCw className={`w-3.5 h-3.5 ${loading ? 'animate-spin' : ''}`} />
        </button>
      </div>

      {engineError ? (
        <div className="p-4 text-[11px] text-red-300 flex items-start gap-2">
          <AlertTriangle className="w-4 h-4 mt-0.5" />
          <div className="font-mono whitespace-pre-wrap">{engineError}</div>
        </div>
      ) : null}

      <div className="flex-1 overflow-auto p-4">
        {pkg ? (
          <Form
            schema={pkg.jsonSchema as any}
            uiSchema={uiSchema as any}
            formData={formData}
            onChange={(e) => setFormData((e.formData ?? {}) as Record<string, unknown>)}
            onSubmit={async (e) => {
              // submit sonrası “tek kaynak gerçeklik” için tekrar generate çağır:
              // validation ve fieldState güncellensin
              setFormData((e.formData ?? {}) as Record<string, unknown>);
              await handleGenerate();
            }}
          />
        ) : (
          <div className="h-full flex items-center justify-center text-gray-600 opacity-60 text-[11px]">
            Generate a form package to preview.
          </div>
        )}

        {pkg && !pkg.validation.valid ? (
          <div className="mt-4 rounded-xl border border-red-500/20 bg-red-500/5 p-3">
            <p className="text-[10px] font-bold uppercase tracking-widest text-red-200">Validation</p>
            <ul className="mt-2 space-y-1 text-[11px] text-red-200 font-mono">
              {pkg.validation.errors.map((err, idx) => (
                <li key={idx}>
                  [{err.field_id}] {err.message}
                </li>
              ))}
            </ul>
          </div>
        ) : null}
      </div>
    </div>
  );
}
```

---

## D-4 · panelRegistry — FormPreview panel kaydı

**Dosyalar:** `tooling/mpc-studio/src/config/panelRegistry.ts` + `tooling/mpc-studio/src/App.tsx` (+ gerekirse sidebar menü/router dosyaları)

> **Önemli uyumluluk notu:** Bu repo’daki `panelRegistry.ts` sadece “sidebar tab metadata” tutuyor (id/label/group/icon/capabilities).
> React component mapping’i burada değil, `App.tsx` içindeki `renderSidebarPanel()` switch’inde yapılıyor.

**Adım 1:** `panelRegistry.ts` içine yeni tab kaydı ekle:

- `id`: `form-preview`
- `label`: `Form Preview`
- `group`: `Runtime`
- `icon`: mevcut ikon union’ından birini seç (örn. `Layers` veya `Workflow`)
- `matchCapabilities`: en az `preview_json` (veya yeni bir capability tanımlanacaksa onu)  
- `matchKinds`: `['FormDef']` (veya FormDef’ler definition listesinde nasıl görünüyorsa)

**Adım 2:** `App.tsx` içinde `renderSidebarPanel()` içine yeni branch ekle:

- `if (sidebarTab === 'form-preview') return <FormPreview ... />;`

**Adım 3 (opsiyonel ama önerilir):** `worker.ts` içindeki `LIST_DEFINITIONS` capability router’ına `FormDef` için uygun capability set’i ekle, böylece metadata-driven router ile panel otomatik önerilebilir.

Örnek (worker.ts içindeki `capabilities` seçimi):

- `if (item.kind === 'FormDef') return ['preview_json', 'diagnostics'];`

---

## D-5 · App.tsx — FormPreview onGenerate bağlantısı

**Dosya:** `tooling/mpc-studio/src/App.tsx`

`UISchemaView`'ın `onGenerate` prop'unun nasıl bağlandığını bul ve aynı pattern'ı `FormPreview` için uygula:

```typescript
// Mevcut UISchemaView bağlantısına benzer şekilde:
onGeneratePackage={async ({ formId, data }) => mpcEngine.generateFormPackage({ dsl, formId, data })}
```

---

---

# BÖLÜM E — public/ mirror güncelleme

**Dosya:** `tooling/mpc-studio/src/engine/worker.ts` (ve bilgi amaçlı: `tooling/mpc-studio/scripts/sync-mpc.js`)

> **Önemli uyumluluk notu:** `sync-mpc.js` zaten `src/mpc` klasörünü **tamamını** `public/mpc/` altına recursive kopyalıyor; bu yüzden “dosya listesine ekle” gerekmiyor.
> Asıl kritik kısım, `worker.ts` içindeki `requiredFiles` listesi: Pyodide runtime’a hangi Python dosyalarının yükleneceğini burada belirliyor.

**Yapılacaklar:**

- `requiredFiles` listesine en az şunları ekle (FormEngine ve bağımlılıkları için):
  - `features/form/__init__.py`
  - `features/form/engine.py`
  - `features/form/kinds.py`
  - `features/expr/__init__.py`
  - `features/expr/engine.py`
  - `features/expr/ir.py`
  - `features/expr/compiler.py`
  - `features/acl/__init__.py`
  - `features/acl/engine.py`

> Not: `acl/engine.py` içinden `from mpc.features.expr import ExprEngine` import edildiği için expr dosyaları şart.

> Alternatif (daha iyi): `public/mpc/manifest.json` (sync-mpc’nin ürettiği) üzerinden **dinamik required file loader** yazıp “hardcoded requiredFiles” yaklaşımını kaldır.
> Bu, yeni feature ekledikçe worker’a manuel dosya ekleme ihtiyacını bitirir.

### E-1 · (ÖNERİLEN) Dinamik loader taslağı

Mevcut `requiredFiles` listesi “minimum runtime bundle” yaklaşımı. Bu listeyi büyütmek yerine:

- `GET /mpc/manifest.json` ile dosya listesini al
- Sadece gereken alt-kümeyi yükle (ör. `kernel/**`, `tooling/validator/**`, `features/workflow/**`, `features/form/**`, `features/expr/**`, `features/acl/**`)
- Kalan her şeyi yok say (Studio runtime hafif kalır)

Bu yaklaşımın avantajı: MPC’ye yeni feature eklendiğinde worker kodu değişmeden Studio çalışmaya devam eder.

---

---

# BÖLÜM F — Enterprise Ready Ekleri (YENİ)
> **Bağımlılık:** B (FormEngine) + D (Studio entegrasyonu) tamamlanmış olmalı.
> Bu bölüm, “preview”i enterprise-grade hale getiren runtime parity + governance + conformance + güvenlik + gözlemlenebilirlik işlerini kapsar.

---

## F-1 · Remote runtime parity — FormPackage endpoint

**Hedef:** `MPCEngine` remote moddayken (aktif artefact / tenant) FormPackage üretimi **remote endpoint** üzerinden çalışsın; remote kapalıysa local worker’a düşsün.

**Yapılacaklar:**

- Remote runtime’a yeni endpoint tasarla:
  - `POST /runtime/forms/package`
  - Request (mpc-studio remote stiline uyumlu):
    - `tenant_id: string`
    - `source: { manifest_text?: string; artifact_id?: string }`
      - Not: Studio `mpc-engine.ts` `buildRuntimeSource(...)` ile bu shape’i zaten üretiyor.
    - `form_id: string`
    - `data: object`
    - `actor_roles?: string[]`
    - `actor_attrs?: object`
  - Response (remote stiline uyumlu, snake_case):
    - `json_schema: object`
    - `ui_schema: object`
    - `field_state: Array<{ field_id: string; visible: boolean; readonly: boolean }>`
    - `validation: { valid: boolean; errors: Array<{ field_id: string; message: string; expr?: string | null }> }`
- `tooling/mpc-studio/src/engine/mpc-engine.ts` içine:
  - `generateFormPackage(...)` için policy/workflow ile aynı remote-first akışı:
    - `if (runtimeMode() === 'remote' && !isCircuitOpen()) try postRemote(...) catch → local worker fallback`
  - Remote hata formatı:
    - `postRemote` başarısız olduğunda body’den `code/message/detail.code/detail.message/retryable` okunuyor (RemoteRuntimeError).
    - Enterprise endpoint bu alanları mümkünse döndürmeli.
  - Header/Idempotency/CSRF:
    - `postRemote` otomatik `Idempotency-Key` ekliyor
    - `tenant_id` varsa `X-Tenant-Id` header set ediliyor
    - CSRF cookie/header isimleri env’den okunuyor
- Parite testi:
  - Aynı DSL + input ile local ve remote çıktıları “shape” olarak aynı olmalı (en azından keys ve deterministik ordering).

---

## F-2 · Governance/Artifact lifecycle ile uyum

**Hedef:** Studio’da “tenant active manifest” kullanımında form paket üretimi **manifest_text yerine artefact** üzerinden çalışsın.

**Yapılacaklar:**

- `tooling/mpc-studio/src/engine/mpc-engine.ts` içinde `generateFormPackage` için policy/workflow ile aynı opsiyon modelini kullan:
  - options: `{ tenantId?: string; artifactId?: string; useTenantActiveManifest?: boolean }`
  - remote request içinde:
    - `tenant_id`: `options.tenantId` veya URL param’dan gelen tenant
    - `source`: `buildRuntimeSource({ dsl, artifactId, useTenantActiveManifest })`
  - `buildRuntimeSource` davranışı:
    - `artifactId` verildiyse: `{ artifact_id }`
    - `useTenantActiveManifest === true` ise: `{}` (server “active artifact”ı seçer)
    - aksi halde: `{ manifest_text: dsl }`
- Remote endpoint tarafında `source` çözümlemesi ve yetkiler:
  - `{}` (active manifest) → tenant için “active artefact required” kuralı (yoksa `ACTIVE_ARTIFACT_REQUIRED`)
  - `{ artifact_id }` → tenant mismatch kontrolü (`TENANT_MISMATCH`) + bulunamadı (`ARTIFACT_NOT_FOUND`)
  - `{ manifest_text }` → sadece Studio/draft preview için; prod modda kapatılabilir
- (Opsiyonel) Eğer enterprise imzalama/güven zinciri varsa:
  - Studio yalnızca “signed+verified” artefact’lar için form paket üretimine izin verir (ya da en azından warning diagnostics üretir).

---

## F-3 · Güvenlik posture — fail-open/closed ve input limits

**Hedef:** Expression/ACL/visibility/readonly/validation davranışları açıkça tanımlı ve konfigüre edilebilir olsun.

**Yapılacaklar:**

- **Fail-open/closed politikası**:
  - Tek parametre: `fail_open: bool` (default: **true** Studio/dev).
  - Expression hata verirse uygulanacak davranış (NET):
    - `visibilityExpr` hata → `visible=True` (fail-open) / `visible=False` (fail-closed)
    - `readonlyExpr` hata → `readonly=False` (fail-open) / `readonly=True` (fail-closed)
    - `validationExpr` hata → “valid say” (fail-open) / “invalid say” (fail-closed)
  - Worker tarafında bu değer env ile set edilir: `VITE_MPC_FORM_FAIL_OPEN=true|false`.
- **Input limits** (worker + remote):
  - `dsl` boyutu için limit (örn. 256KB) + `E_FORM_DSL_TOO_LARGE`
  - `data` payload byte limiti + `E_FORM_DATA_TOO_LARGE`
  - `actor_attrs` için limit (örn. 8KB) + `E_FORM_ACTOR_TOO_LARGE`
- **Time budget / timeout**:
  - FormPackage üretimi için üst limit (örn. 100ms) ve aşılırsa:
    - local worker: `postEnvelope(..., diagnostics=[{code:'E_FORM_TIMEOUT',...}])` + `ERROR` yerine kontrollü payload
    - remote: `{ code: 'E_FORM_TIMEOUT', message: '...', retryable: true|false }`
- **Diagnostics kod standardı** (remote `code/message/retryable` ile uyumlu):
  - `E_FORM_EXPR_FAILED` (retryable=false)
  - `E_FORM_DATA_TOO_LARGE` (retryable=false)
  - `E_FORM_DSL_TOO_LARGE` (retryable=false)
  - `E_FORM_TIMEOUT` (retryable=true, opsiyonel)
  - `FORBIDDEN` / `TENANT_MISMATCH` / `ACTIVE_ARTIFACT_REQUIRED` (mevcut engine code set’iyle uyumlu)

---

## F-4 · Conformance — fixtures + CI gate

**Hedef:** FormDef/FormEngine davranışı fixture ile tanımlansın; regresyonlar CI’da yakalansın.

**Yapılacaklar:**

- **Yeni kategori**: `packages/core-conformance/fixtures/form/*`
  - Her fixture klasörü standard MPC fixture yapısını izler:
    - `meta.json` (category/description + opsiyonel preset/clock/limits)
    - `input.json`
    - `expected.json` (canonical; byte-compare)
    - (opsiyonel) `notes.md`

- **Fixture input sözleşmesi (öneri)**:
  - `dsl: string` (manifest text)
  - `form_id: string`
  - `data: object`
  - `actor_roles?: string[]`
  - `actor_attrs?: object`
  - `fail_open?: boolean` (enterprise posture testi için)

- **Fixture expected sözleşmesi (öneri, engine-native snake_case)**:
  - `json_schema: object`
  - `ui_schema: object`
  - `field_state: Array<{ field_id: string; visible: boolean; readonly: boolean }>`
  - `validation: { valid: boolean; errors: Array<{ field_id: string; message: string; expr?: string | null }> }`

- **Örnek fixture seti (minimum)**:
  - `fixtures/form/01_basic_required/`
  - `fixtures/form/02_visibility_readonly_expr/`
  - `fixtures/form/03_acl_mask_readonly/`
  - `fixtures/form/04_fail_closed_unknown_function/` (enterprise fail-closed posture; unknown function)
  - `fixtures/form/05_budget_steps_fail_closed/` (expr budget/limit posture; fail-closed)

- **Runner entegrasyonu (Python)**:
  - `src/mpc/tooling/conformance/runner.py` içine yeni handler ekle:
    - `_handlers["form"] = ConformanceRunner._handle_form`
    - `_handle_form` içinde:
      - `parse(dsl)` → `FormEngine(ast, meta=DomainMeta(kinds=FORM_KINDS))`
      - `form = engine.get_form(form_id)` (yoksa MPCError)
      - `package = { json_schema, ui_schema, field_state, validation }`
      - `canonicalize(package)` ve `expected.json` ile compare
  - Not: Worker/UI kontratı camelCase (`jsonSchema/uiSchema/...`) olabilir; conformance ise engine-native snake_case tutabilir. Studio’da mapping testini ayrıca gate et.

- **Studio contracts gate**:
  - `tooling/mpc-studio/scripts/run-contract-gate.mjs` benzeri bir gate ekle:
    - Worker’dan gelen `FORM_PACKAGE` payload’ının shape’ini doğrula (jsonSchema/uiSchema/fieldState/validation)
    - (opsiyonel) `fieldState` uygulanınca gizli alanların gerçekten gizlendiğini e2e ile kontrol et (Playwright).

---

## F-5 · Observability — envelope metrics + diag yüzeyi

**Hedef:** FormPackage üretimi her zaman `postEnvelope` ile dönsün ve `durationMs/diagnostics` izlenebilir olsun (local + remote).

**Yapılacaklar:**

- Worker `GENERATE_FORM_PACKAGE`:
  - envelope diagnostics’ı doldur (warnings/errors)
    - `diagnostics[]` shape’i worker’daki `EnvelopeDiagnostic` ile aynı: `{ code, message, severity: 'info'|'warning'|'error' }`
  - `durationMs` zaten zarf içinde; UI’da debug panelde göster (App footer’da worker metrics zaten var)
  - (Öneri) `payload` içine ayrıca `meta` alanı ekleme: payload’a değil envelope’a metrics koy (contract stable kalsın)
- Remote runtime:
  - requestId propagation ve diag count
    - Remote response body’sinde mümkünse `request_id` ve `duration_ms` döndür
    - Studio `postRemote` ile bu alanları otomatik kaydetmiyor; ama `RemoteRuntimeError` code/message ile korelasyon yapılabilir
  - rate limit / forbidden gibi durumlar için kod standardı (Studio’nun `KNOWN_RUNTIME_ERROR_CODES` set’i ile uyumlu)
    - `FORBIDDEN` (403)
    - `TENANT_MISMATCH` (403/404 policy)
    - `ACTIVE_ARTIFACT_REQUIRED` (409 veya 400; retryable=false)
    - `ARTIFACT_NOT_FOUND` (404)
    - `MANIFEST_PARSE_ERROR` / `MANIFEST_INVALID_SHAPE` (400)
    - `REMOTE_RUNTIME_5XX` (retryable=true)

### F-5.1 · UI yüzeyi (nerede gösterilecek?)

- `mpcEngine.getLastWorkerMetrics()` zaten `App.tsx` footer’da gösteriliyor.
- FormPreview paneli için ek öneri:
  - Son `FORM_PACKAGE` çağrısının `diagnostics` listesini panel içinde (collapse) göster.
  - `validation.errors` ile `diagnostics`’i karıştırma: validation = kullanıcı hatası; diagnostics = runtime/engine uyarısı.

### F-5.2 · Log/telemetry (opsiyonel)

Remote runtime enterprise ortamında:
- FormPackage endpoint’inde structured log: `{tenant_id, artifact_id?, form_id, duration_ms, diag_count, error_code?}`
- Rate limiting için `retryable` + `Retry-After` header (varsa) önerilir.

# DOĞRULAMA

## Python testleri

```bash
cd manifest-platform-core-suite

# Mevcut testler hâlâ geçmeli
python -m pytest tests/ -v --tb=short

# UISchema child fix kontrolü
python -c "
from mpc.kernel.parser import parse
from mpc.tooling.uischema.generator import generate_ui_schema
from mpc.kernel.meta.models import DomainMeta, KindDef

dsl = '''
@schema 1 @namespace \"t\" @name \"t\" @version \"1.0.0\"
def Policy p1 {
    def Condition c1 { expr: \"x > 0\" }
}
'''
meta = DomainMeta(kinds=[KindDef('Policy'), KindDef('Condition')])
res = generate_ui_schema(parse(dsl), meta)
child = res.schemas['Policy:p1']['x-children'][0]
assert child['x-kind'] == 'Condition', f'FAIL: {child}'
print('A-1 OK: child kind_def fix çalışıyor')
"

# Form engine smoke test
python -c "
from mpc.kernel.parser import parse
from mpc.features.form.engine import FormEngine
from mpc.features.form.kinds import FORM_KINDS
from mpc.kernel.meta.models import DomainMeta

dsl = '''
@schema 1 @namespace \"t\" @name \"t\" @version \"1.0.0\"
def FormDef signup \"Kayıt\" {
    workflowState: \"draft\"
    def FieldDef email { type: \"string\" required: true }
    def FieldDef age { type: \"number\" min: 18 }
}
'''
ast = parse(dsl)
engine = FormEngine(ast=ast, meta=DomainMeta(kinds=FORM_KINDS))
forms = engine.get_forms()
assert len(forms) == 1
assert forms[0].id == 'signup'
assert len(forms[0].fields) == 2
schema = forms[0].to_json_schema()
assert 'email' in schema['properties']
assert schema['required'] == ['email']
print('B OK: FormEngine çalışıyor')
print(schema)
"
```

## Studio

```bash
cd tooling/mpc-studio
npm run dev

# Manuel kontrol listesi:
# 1. Editor'da def yazınca "def Policy", "def FormDef" vb. autocomplete geliyor mu?
# 2. @schema, @namespace mor renkte mi?
# 3. def keyword'ü mavi renkte mi?
# 4. FormDef içeren manifest yazınca "Form Preview" panelinde form render oluyor mu?
# 5. required: true alan boşsa validation error UI’da görünüyor mu?
# 6. visibilityExpr/readonlyExpr/ACL kaynaklı field state UI’da uygulanıyor mu?
```

---

## Enterprise ekleri doğrulama (YENİ)

### 1) Conformance (Form fixtures)

```bash
cd manifest-platform-core-suite
mpc-conformance run packages/core-conformance/fixtures/form
```

Beklenti:
- `form/*` fixture’ları **byte-compare** ile geçer.
- Runner unknown `E_* / R_* / Intent-kind` kodları reject etmeye devam eder.

### 2) Studio contracts gate

```bash
cd tooling/mpc-studio
npm run test:contracts
```

Beklenti:
- Worker’dan gelen `FORM_PACKAGE` payload shape’i doğrulanır.

### 3) Remote runtime parity (varsa)

Ön koşul:
- `VITE_MPC_RUNTIME_MODE=remote`
- `VITE_MPC_RUNTIME_BASE_URL` remote runtime’a işaret eder
- URL query’de `tenant_id=...` veya seçenekler ile tenant set edilir

Kontrol listesi:
- Aynı `formId` + aynı input ile:
  - remote `POST /runtime/forms/package` sonucu
  - local worker `GENERATE_FORM_PACKAGE` sonucu
  “shape” olarak uyumlu olmalı.
- Remote error formatı:
  - hata body’sinde `code/message` ve gerekiyorsa `retryable` geliyor mu?
  - `postRemote` retry/circuit-breaker davranışı bekleneni yapıyor mu?

### 4) Security posture

Kontrol listesi:
- `fail_open=false` modunda expr error olduğunda:
  - visibility/readonly/validation için belirlenen policy uygulanıyor mu?
- `data`/`dsl` size limit aşımında:
  - `E_FORM_INPUT_TOO_LARGE` / `E_FORM_DSL_TOO_LARGE` diagnostics/remote error kodu doğru mu?
- Time budget aşımlarında:
  - local envelope diagnostics ve/veya remote `E_FORM_TIMEOUT` doğru mu?


# DOSYA ÖZETİ

| Dosya | İşlem |
|---|---|
| `src/mpc/tooling/uischema/generator.py` | Değiştir — A-1 |
| `src/mpc/features/workflow/fsm.py` | Değiştir — A-2, A-3 |
| `src/mpc/kernel/ast/normalizer.py` | Değiştir — A-4 |
| `src/mpc/kernel/errors/registry.py` | Değiştir — A-4 |
| `src/mpc/kernel/ast/models.py` | Değiştir — A-5 |
| `src/mpc/features/form/__init__.py` | **Yeni** — B-1 |
| `src/mpc/features/form/kinds.py` | **Yeni** — B-1 |
| `src/mpc/features/form/engine.py` | **Yeni** — B-2 |
| `src/mpc/tooling/cli.py` | Değiştir — B-3 |
| `tooling/mpc-studio/src/engine/mpc-dsl-language.ts` | **Yeni** — C-1 |
| `tooling/mpc-studio/src/components/ManifestEditor.tsx` | Değiştir — C-2 |
| `tooling/mpc-studio/src/engine/worker.ts` | Değiştir — D-1 |
| `tooling/mpc-studio/src/engine/mpc-engine.ts` | Değiştir — D-2 |
| `tooling/mpc-studio/src/components/FormPreview.tsx` | **Yeni** — D-3 |
| `tooling/mpc-studio/src/config/panelRegistry.ts` | Değiştir — D-4 |
| `tooling/mpc-studio/src/App.tsx` | Değiştir — D-5 |
| `tooling/mpc-studio/scripts/sync-mpc.js` | (Değişiklik yok) — zaten recursive kopyalıyor |
