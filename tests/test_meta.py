from mpc.meta import DomainMeta, KindDef, FunctionDef, diff_meta


class TestDomainMeta:
    def test_get_kind(self):
        meta = DomainMeta(kinds=[KindDef(name="Policy")])
        assert meta.get_kind("Policy") is not None
        assert meta.get_kind("Nonexistent") is None

    def test_get_function(self):
        meta = DomainMeta(
            allowed_functions=[FunctionDef(name="len", args=["string"], returns="int")]
        )
        assert meta.get_function("len") is not None
        assert meta.get_function("missing") is None

    def test_kind_names(self):
        meta = DomainMeta(kinds=[KindDef(name="A"), KindDef(name="B")])
        assert meta.kind_names == frozenset({"A", "B"})


class TestMetaDiff:
    def test_no_changes(self):
        meta = DomainMeta(kinds=[KindDef(name="Policy")])
        result = diff_meta(meta, meta)
        assert not result.has_breaking
        assert result.breaking == []
        assert result.non_breaking == []

    def test_kind_removed_is_breaking(self):
        old = DomainMeta(kinds=[KindDef(name="Policy"), KindDef(name="Workflow")])
        new = DomainMeta(kinds=[KindDef(name="Policy")])
        result = diff_meta(old, new)
        assert result.has_breaking
        assert any("Workflow" in b and "removed" in b for b in result.breaking)

    def test_kind_added_is_non_breaking(self):
        old = DomainMeta(kinds=[KindDef(name="Policy")])
        new = DomainMeta(kinds=[KindDef(name="Policy"), KindDef(name="Workflow")])
        result = diff_meta(old, new)
        assert not result.has_breaking
        assert any("Workflow" in nb and "added" in nb for nb in result.non_breaking)

    def test_required_prop_added_is_breaking(self):
        old = DomainMeta(kinds=[KindDef(name="Policy", required_props=["effect"])])
        new = DomainMeta(
            kinds=[KindDef(name="Policy", required_props=["effect", "priority"])]
        )
        result = diff_meta(old, new)
        assert result.has_breaking
        assert any("priority" in b for b in result.breaking)

    def test_function_removed_is_breaking(self):
        old = DomainMeta(
            allowed_functions=[
                FunctionDef(name="len", args=["string"], returns="int"),
                FunctionDef(name="regex", args=["string", "string"], returns="bool"),
            ]
        )
        new = DomainMeta(
            allowed_functions=[FunctionDef(name="len", args=["string"], returns="int")]
        )
        result = diff_meta(old, new)
        assert result.has_breaking
        assert any("regex" in b for b in result.breaking)

    def test_function_added_is_non_breaking(self):
        old = DomainMeta(allowed_functions=[])
        new = DomainMeta(
            allowed_functions=[FunctionDef(name="len", args=["string"], returns="int")]
        )
        result = diff_meta(old, new)
        assert not result.has_breaking
        assert any("len" in nb for nb in result.non_breaking)

    def test_event_removed_is_breaking(self):
        old = DomainMeta(allowed_events=["user.created", "user.deleted"])
        new = DomainMeta(allowed_events=["user.created"])
        result = diff_meta(old, new)
        assert result.has_breaking
        assert any("user.deleted" in b for b in result.breaking)

    def test_event_added_is_non_breaking(self):
        old = DomainMeta(allowed_events=["user.created"])
        new = DomainMeta(allowed_events=["user.created", "user.deleted"])
        result = diff_meta(old, new)
        assert not result.has_breaking
        assert any("user.deleted" in nb for nb in result.non_breaking)
