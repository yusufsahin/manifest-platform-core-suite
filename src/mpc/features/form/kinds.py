"""Kind definitions for FormDef and FieldDef."""

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
            "label",
            "required",
            "default",
            "min",
            "max",
            "options",
            "placeholder",
            "validationExpr",
            "visibilityExpr",
            "readonlyExpr",
        ],
    ),
]

FORM_FIELD_TYPES: list[str] = [
    "string",
    "number",
    "boolean",
    "select",
    "multiselect",
    "date",
    "textarea",
    "hidden",
]

