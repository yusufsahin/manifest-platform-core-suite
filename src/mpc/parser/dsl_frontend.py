"""DSL -> ManifestAST frontend using Lark.

The grammar lives in grammar.lark next to this file.
Lark builds a parse tree; a Transformer converts it to ManifestAST.
propagate_positions=True gives line/col info for SourceMap.
"""
from __future__ import annotations

from pathlib import Path
from typing import Any

from lark import Lark, Transformer, v_args, Token, Tree
from lark.exceptions import UnexpectedInput

from mpc.ast.models import ASTNode, ManifestAST
from mpc.contracts.models import SourceMap
from mpc.errors import MPCError

_GRAMMAR_PATH = Path(__file__).parent / "grammar.lark"

_parser = Lark(
    _GRAMMAR_PATH.read_text(encoding="utf-8"),
    parser="earley",
    propagate_positions=True,
)


def parse_dsl(text: str) -> ManifestAST:
    """Parse an MPC DSL string into a ManifestAST."""
    try:
        tree = _parser.parse(text)
    except UnexpectedInput as exc:
        raise MPCError(
            "E_PARSE_SYNTAX",
            f"DSL parse error at line {exc.line}, col {exc.column}: {exc}",
        ) from exc

    return _ASTBuilder().transform(tree)


@v_args(tree=True)
class _ASTBuilder(Transformer):
    """Walk the Lark parse tree and produce a ManifestAST."""

    def start(self, tree: Tree) -> ManifestAST:
        schema_version = 1
        namespace = ""
        name = ""
        version = "0.0.0"
        defs: list[ASTNode] = []

        for child in tree.children:
            if isinstance(child, dict):
                key = child.get("_directive")
                if key == "schema":
                    schema_version = child["value"]
                elif key == "namespace":
                    namespace = child["value"]
                elif key == "name":
                    name = child["value"]
                elif key == "version":
                    version = child["value"]
            elif isinstance(child, ASTNode):
                defs.append(child)

        return ManifestAST(
            schema_version=schema_version,
            namespace=namespace,
            name=name,
            manifest_version=version,
            defs=defs,
        )

    # -- directives ---------------------------------------------------------

    def schema_dir(self, tree: Tree) -> dict[str, Any]:
        return {"_directive": "schema", "value": int(tree.children[0])}

    def namespace_dir(self, tree: Tree) -> dict[str, Any]:
        return {"_directive": "namespace", "value": _unquote(tree.children[0])}

    def name_dir(self, tree: Tree) -> dict[str, Any]:
        return {"_directive": "name", "value": _unquote(tree.children[0])}

    def version_dir(self, tree: Tree) -> dict[str, Any]:
        return {"_directive": "version", "value": _unquote(tree.children[0])}

    # -- definitions --------------------------------------------------------

    def definition(self, tree: Tree) -> ASTNode:
        tokens = [c for c in tree.children if isinstance(c, Token)]
        pairs = [c for c in tree.children if isinstance(c, tuple)]

        kind = str(tokens[0])
        node_id = str(tokens[1])
        node_name = _unquote(tokens[2]) if len(tokens) >= 3 else None

        props: dict[str, Any] = {}
        for key, val in pairs:
            props[key] = val

        source = SourceMap(
            line=tree.meta.line if tree.meta else None,
            col=tree.meta.column if tree.meta else None,
        )

        return ASTNode(
            kind=kind, id=node_id, name=node_name, properties=props, source=source
        )

    # -- properties ---------------------------------------------------------

    def property(self, tree: Tree) -> tuple[str, Any]:
        key = str(tree.children[0])
        val = tree.children[1]
        return (key, val)

    # -- values -------------------------------------------------------------

    def string_val(self, tree: Tree) -> str:
        return _unquote(tree.children[0])

    def number_val(self, tree: Tree) -> int | float:
        raw = str(tree.children[0])
        return float(raw) if "." in raw else int(raw)

    def true_val(self, tree: Tree) -> bool:
        return True

    def false_val(self, tree: Tree) -> bool:
        return False

    def null_val(self, tree: Tree) -> None:
        return None

    def array(self, tree: Tree) -> list[Any]:
        return list(tree.children)

    def object(self, tree: Tree) -> dict[str, Any]:
        return {k: v for k, v in tree.children}


def _unquote(token: Token) -> str:
    s = str(token)
    if s.startswith('"') and s.endswith('"'):
        return s[1:-1].replace('\\"', '"').replace("\\\\", "\\")
    return s
