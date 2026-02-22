from mpc.contracts import (
    Actor, Object, EventEnvelope,
    SourceSpan, SourceMap, Error,
    Intent, Reason, Message, Decision,
    TraceEvent, Trace,
    to_dict, from_dict,
)


class TestActorModel:
    def test_create(self):
        actor = Actor(id="u1", type="user", roles=["admin"])
        assert actor.id == "u1"
        assert actor.type == "user"
        assert actor.roles == ["admin"]
        assert actor.claims is None

    def test_immutable(self):
        actor = Actor(id="u1", type="user")
        try:
            actor.id = "u2"  # type: ignore[misc]
            assert False, "Should be frozen"
        except AttributeError:
            pass


class TestEventEnvelopeModel:
    def test_minimal(self):
        event = EventEnvelope(
            name="entity.create",
            kind="create",
            timestamp="2026-01-01T00:00:00Z",
            actor=Actor(id="u1", type="user"),
            object=Object(type="entity", id="e1"),
        )
        assert event.name == "entity.create"
        assert event.context is None


class TestErrorModel:
    def test_with_causes(self):
        cause = Error(code="E_PARSE_SYNTAX", message="inner", severity="error")
        err = Error(
            code="E_VALID_DUPLICATE_DEF",
            message="outer",
            severity="error",
            causes=[cause],
        )
        assert len(err.causes) == 1
        assert err.causes[0].code == "E_PARSE_SYNTAX"

    def test_with_source_map(self):
        err = Error(
            code="E_PARSE_SYNTAX",
            message="bad token",
            severity="error",
            source=SourceMap(file="rules.yaml", line=3, col=10),
        )
        assert err.source.file == "rules.yaml"


class TestDecisionModel:
    def test_allow_with_intents(self):
        d = Decision(
            allow=True,
            reasons=[Reason(code="R_POLICY_ALLOW")],
            intents=[Intent(kind="audit", target="order-1")],
        )
        assert d.allow is True
        assert d.intents[0].kind == "audit"


class TestTraceModel:
    def test_minimal(self):
        t = Trace(span_id="s1", engine="core-policy")
        assert t.events == []

    def test_with_events(self):
        t = Trace(
            span_id="s1",
            engine="core-policy",
            events=[TraceEvent(t="eval", duration_ms=1.5)],
        )
        assert t.events[0].duration_ms == 1.5


class TestToDict:
    def test_actor(self):
        d = to_dict(Actor(id="u1", type="user", roles=["admin"]))
        assert d == {"id": "u1", "type": "user", "roles": ["admin"]}

    def test_none_fields_omitted(self):
        d = to_dict(Actor(id="u1", type="user"))
        assert "claims" not in d

    def test_intent_camel_case(self):
        d = to_dict(Intent(kind="audit", idempotency_key="k1"))
        assert "idempotencyKey" in d
        assert d["idempotencyKey"] == "k1"
        assert "idempotency_key" not in d

    def test_trace_camel_case(self):
        d = to_dict(Trace(span_id="s1", engine="core-policy"))
        assert d["spanId"] == "s1"
        assert "span_id" not in d

    def test_nested_dataclass(self):
        event = EventEnvelope(
            name="test",
            kind="create",
            timestamp="2026-01-01T00:00:00Z",
            actor=Actor(id="u1", type="user"),
            object=Object(type="entity", id="e1"),
        )
        d = to_dict(event)
        assert isinstance(d["actor"], dict)
        assert d["actor"]["id"] == "u1"

    def test_decision_full(self):
        dec = Decision(
            allow=True,
            reasons=[Reason(code="R_POLICY_ALLOW")],
            intents=[Intent(kind="maskField", target="user.ssn")],
        )
        d = to_dict(dec)
        assert d["allow"] is True
        assert d["reasons"] == [{"code": "R_POLICY_ALLOW"}]
        assert d["intents"] == [{"kind": "maskField", "target": "user.ssn"}]

    def test_trace_event_duration(self):
        d = to_dict(TraceEvent(t="eval", duration_ms=2.5))
        assert d["durationMs"] == 2.5


class TestFromDict:
    def test_actor(self):
        actor = from_dict(Actor, {"id": "u1", "type": "user", "roles": ["admin"]})
        assert actor.id == "u1"
        assert actor.roles == ["admin"]

    def test_intent_camel_case(self):
        intent = from_dict(Intent, {"kind": "audit", "idempotencyKey": "k1"})
        assert intent.idempotency_key == "k1"

    def test_trace_camel_case(self):
        trace = from_dict(
            Trace,
            {"spanId": "s1", "engine": "core-policy", "events": []},
        )
        assert trace.span_id == "s1"

    def test_nested_event_envelope(self):
        data = {
            "name": "test",
            "kind": "create",
            "timestamp": "2026-01-01T00:00:00Z",
            "actor": {"id": "u1", "type": "user"},
            "object": {"type": "entity", "id": "e1"},
        }
        event = from_dict(EventEnvelope, data)
        assert isinstance(event.actor, Actor)
        assert event.actor.id == "u1"
        assert isinstance(event.object, Object)

    def test_decision_with_nested_lists(self):
        data = {
            "allow": True,
            "reasons": [{"code": "R_POLICY_ALLOW"}],
            "intents": [{"kind": "audit", "target": "x"}],
        }
        dec = from_dict(Decision, data)
        assert isinstance(dec.reasons[0], Reason)
        assert isinstance(dec.intents[0], Intent)

    def test_roundtrip(self):
        original = Decision(
            allow=False,
            reasons=[Reason(code="R_ACL_DENY_ROLE", summary="denied")],
            intents=[
                Intent(kind="maskField", target="user.ssn", idempotency_key="k1")
            ],
        )
        data = to_dict(original)
        restored = from_dict(Decision, data)
        assert restored.allow == original.allow
        assert restored.reasons[0].code == "R_ACL_DENY_ROLE"
        assert restored.intents[0].idempotency_key == "k1"
