"""Form engine — generate form schemas and validate submissions.

This is intentionally lightweight and deterministic so consuming apps (and Studio)
can treat the Python engine as the single source of truth.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from mpc.kernel.ast.models import ASTNode, ManifestAST
from mpc.kernel.meta.models import DomainMeta
from mpc.kernel.errors.exceptions import MPCBudgetError, MPCError


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
        ui: dict[str, Any] = {"ui:order": [f.id for f in self.fields]}
        for f in self.fields:
            field_ui: dict[str, Any] = {}
            if f.placeholder:
                field_ui["ui:placeholder"] = f.placeholder
            if f.type == "textarea":
                field_ui["ui:widget"] = "textarea"
            elif f.type == "hidden":
                field_ui["ui:widget"] = "hidden"
            elif f.type == "date":
                field_ui["ui:widget"] = "date"
            ui[f.id] = field_ui
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


@dataclass(frozen=True)
class FormPackage:
    jsonSchema: dict[str, Any]
    uiSchema: dict[str, Any]
    fieldState: list[dict[str, Any]]
    validation: dict[str, Any]


@dataclass
class FormEngine:
    ast: ManifestAST
    meta: DomainMeta | None = None
    max_expr_steps: int = 5000
    max_expr_depth: int = 50
    max_eval_time_ms: float = 50.0
    max_regex_ops: int = 5000

    def get_forms(self) -> list[FormSchema]:
        return [self._node_to_form(node) for node in self.ast.defs if node.kind == "FormDef"]

    def get_form(self, form_id: str) -> FormSchema | None:
        for node in self.ast.defs:
            if node.kind == "FormDef" and node.id == form_id:
                return self._node_to_form(node)
        return None

    def get_forms_for_state(self, workflow_state: str) -> list[FormSchema]:
        return [f for f in self.get_forms() if f.workflow_state == workflow_state]

    def validate_submission(
        self,
        form_id: str,
        data: dict[str, Any],
        *,
        actor_roles: list[str] | None = None,
        actor_attrs: dict[str, Any] | None = None,
        fail_open: bool = True,
        clock: Any | None = None,
    ) -> ValidationResult:
        form = self.get_form(form_id)
        if form is None:
            return ValidationResult(
                valid=False,
                errors=[FieldValidationError(field_id="__form__", message=f"FormDef '{form_id}' not found")],
            )

        errors: list[FieldValidationError] = []

        for f in form.fields:
            value = data.get(f.id)
            if f.required and (value is None or value == ""):
                errors.append(FieldValidationError(field_id=f.id, message=f"'{f.label or f.id}' alanı zorunludur"))
                continue

            if f.validation_expr and self.meta:
                expr_result = self._eval_expr(
                    f.validation_expr,
                    context={**data, "role": (actor_roles or [""])[0]},
                    fail_open=fail_open,
                    default=True,
                    clock=clock,
                )
                if expr_result is False:
                    errors.append(
                        FieldValidationError(
                            field_id=f.id,
                            message=f"'{f.label or f.id}' doğrulama koşulunu sağlamıyor",
                            expr=f.validation_expr,
                        )
                    )

        return ValidationResult(valid=len(errors) == 0, errors=errors)

    def apply_acl(
        self,
        form_id: str,
        *,
        actor_roles: list[str] | None = None,
        actor_attrs: dict[str, Any] | None = None,
        fail_open: bool = True,
        clock: Any | None = None,
    ) -> dict[str, bool]:
        if self.meta is None:
            return {}
        form = self.get_form(form_id)
        if form is None:
            return {}

        readonly_map: dict[str, bool] = {}
        try:
            from mpc.features.acl.engine import ACLEngine
            from mpc.features.expr.engine import ExprEngine

            acl = ACLEngine(ast=self.ast, meta=self.meta)
            expr_engine = ExprEngine(
                meta=self.meta,
                max_steps=self.max_expr_steps,
                max_depth=self.max_expr_depth,
                max_time_ms=self.max_eval_time_ms,
                max_regex_ops=self.max_regex_ops,
                clock=clock,
            )
            for f in form.fields:
                result = acl.check(
                    "read",
                    f.id,
                    actor_roles=actor_roles,
                    actor_attrs=actor_attrs,
                    expr_engine=expr_engine,
                )
                readonly_map[f.id] = any(i.kind == "maskField" for i in result.intents)
        except Exception:
            return {} if fail_open else {f.id: True for f in form.fields}
        return readonly_map

    def compute_field_state(
        self,
        form_id: str,
        data: dict[str, Any],
        *,
        actor_roles: list[str] | None = None,
        actor_attrs: dict[str, Any] | None = None,
        fail_open: bool = True,
        clock: Any | None = None,
    ) -> list[FieldState]:
        form = self.get_form(form_id)
        if form is None:
            return []

        readonly_map = self.apply_acl(
            form_id,
            actor_roles=actor_roles,
            actor_attrs=actor_attrs,
            fail_open=fail_open,
            clock=clock,
        )
        states: list[FieldState] = []

        for f in form.fields:
            visible = True
            readonly = bool(readonly_map.get(f.id, False))

            if f.visibility_expr and self.meta:
                v = self._eval_expr(
                    f.visibility_expr,
                    context={**data, "role": (actor_roles or [""])[0]},
                    fail_open=fail_open,
                    default=True,
                    clock=clock,
                )
                if v is False:
                    visible = False

            if f.readonly_expr and self.meta:
                r = self._eval_expr(
                    f.readonly_expr,
                    context={**data, "role": (actor_roles or [""])[0]},
                    fail_open=fail_open,
                    default=False,
                    clock=clock,
                )
                if r is True:
                    readonly = True

            states.append(FieldState(field_id=f.id, visible=visible, readonly=readonly))

        return states

    def get_form_package(
        self,
        form_id: str,
        data: dict[str, Any],
        *,
        actor_roles: list[str] | None = None,
        actor_attrs: dict[str, Any] | None = None,
        fail_open: bool = True,
        clock: Any | None = None,
    ) -> FormPackage:
        form = self.get_form(form_id)
        if form is None:
            return FormPackage(
                jsonSchema={},
                uiSchema={},
                fieldState=[],
                validation={"valid": False, "errors": [{"field_id": "__form__", "message": f"FormDef '{form_id}' not found"}]},
            )

        json_schema = form.to_json_schema()
        ui_schema = form.to_ui_schema()
        field_state = [
            {"field_id": s.field_id, "visible": s.visible, "readonly": s.readonly}
            for s in self.compute_field_state(
                form_id,
                data,
                actor_roles=actor_roles,
                actor_attrs=actor_attrs,
                fail_open=fail_open,
                clock=clock,
            )
        ]
        validation = self.validate_submission(
            form_id,
            data,
            actor_roles=actor_roles,
            actor_attrs=actor_attrs,
            fail_open=fail_open,
            clock=clock,
        )
        return FormPackage(
            jsonSchema=json_schema,
            uiSchema=ui_schema,
            fieldState=field_state,
            validation={
                "valid": validation.valid,
                "errors": [
                    {"field_id": e.field_id, "message": e.message, "expr": e.expr}
                    for e in validation.errors
                ],
            },
        )

    def _node_to_form(self, node: ASTNode) -> FormSchema:
        props = dict(node.properties)
        fields: list[FormField] = []

        for child in node.children:
            if child.kind == "FieldDef":
                fields.append(self._node_to_field(child))

        for f_raw in props.get("fields", []):
            if isinstance(f_raw, dict):
                fields.append(
                    FormField(
                        id=str(f_raw.get("id", "")),
                        type=str(f_raw.get("type", "string")),
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
                    )
                )

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
            type=str(props.get("type", "string")),
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

    def _eval_expr(
        self,
        expr: str,
        *,
        context: dict[str, Any],
        fail_open: bool,
        default: bool,
        clock: Any | None = None,
    ) -> Any:
        if self.meta is None:
            return default
        try:
            from mpc.features.expr.engine import ExprEngine

            engine = ExprEngine(
                meta=self.meta,
                max_steps=self.max_expr_steps,
                max_depth=self.max_expr_depth,
                max_time_ms=self.max_eval_time_ms,
                max_regex_ops=self.max_regex_ops,
                clock=clock,
            )
            result = engine.evaluate(expr, context=context)
            return result.value
        except (MPCError, MPCBudgetError):
            return default if fail_open else (not default)
        except Exception:
            return default if fail_open else (not default)


def _field_type_to_json(field_type: str) -> str:
    mapping = {
        "string": "string",
        "textarea": "string",
        "hidden": "string",
        "number": "number",
        "boolean": "boolean",
        "select": "string",
        "multiselect": "array",
        "date": "string",
    }
    return mapping.get(field_type, "string")

