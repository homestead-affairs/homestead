"""I-17 — no network egress by default, and the preview is the payload.

`keep/egress.send` is the one place the self-contained face could reach out, so
it is the one place the refusal lives. Two properties carry the invariant:

* nothing leaves without an explicit per-call act — no `confirm`, no send; and
* what the operator approves is what leaves, because the confirmation and the
  transport are handed the *same* `Wire`. BUG-5 was possible only because the
  shown thing and the sent thing were computed separately; here they cannot be.

Import-purity (no network at load, I-26/I-30) is held for the whole package by
`test_i30_i26_nothing_imports_the_network`; a targeted check is here too.
"""
from __future__ import annotations

import ast
import json
from pathlib import Path

import pytest

from homestead.keep.egress import EgressRefused, Wire, send

URL = "https://example.invalid/intake"
PAYLOAD = {"matter": "custody", "note_ref": "custody/atom/ATM-001"}


class _Transport:
    """A transport that records what it was asked to send and never touches a
    network — the injection point that keeps these tests offline."""

    def __init__(self) -> None:
        self.sent: list[Wire] = []

    def __call__(self, wire: Wire):
        self.sent.append(wire)
        return "delivered"


# ── promoted from test_invariants_pending.py ─────────────────────────────────

def test_i17_no_egress_without_an_explicit_per_call_act():
    """The default is refusal. With no confirmation there is no send, and the
    refusal is a PermissionError so a caller cannot mistake it for a network
    hiccup and retry past it."""
    with pytest.raises(PermissionError):
        send(URL, payload={"x": 1})


# ── the act is explicit, per call, and not remembered ────────────────────────

def test_a_declined_preview_sends_nothing():
    """Shown exactly what would go and saying no leaves nothing sent — the
    transport is never reached."""
    transport = _Transport()
    with pytest.raises(EgressRefused):
        send(URL, PAYLOAD, confirm=lambda wire: False, transport=transport)
    assert transport.sent == []


def test_the_permission_is_per_call_not_an_ambient_flag():
    """A confirmed send does not unlock a second one. There is no flag set once
    and forgotten; each call brings its own act or is refused."""
    transport = _Transport()
    send(URL, PAYLOAD, confirm=lambda wire: True, transport=transport)
    assert len(transport.sent) == 1
    # the next call, with no confirmation, is refused all the same
    with pytest.raises(EgressRefused):
        send(URL, PAYLOAD, transport=transport)
    assert len(transport.sent) == 1


# ── the preview IS the payload (BUG-5's answer at the wire) ───────────────────

def test_what_is_previewed_is_exactly_what_is_sent():
    """The object the confirmation is shown and the object the transport sends
    are one and the same, so the bytes approved are the bytes that leave. Not
    'equal' — identical: there is no second serialization to diverge."""
    shown: dict[str, Wire] = {}

    def confirm(wire: Wire) -> bool:
        shown["wire"] = wire
        return True

    transport = _Transport()
    send(URL, PAYLOAD, confirm=confirm, transport=transport)

    assert transport.sent, "a confirmed send must reach the transport"
    assert shown["wire"] is transport.sent[0]


def test_the_preview_carries_the_real_url_and_the_exact_payload():
    """The confirmation is shown the true destination and the exact body — not a
    gloss. The operator approves what is actually there."""
    seen: dict[str, Wire] = {}
    send(URL, PAYLOAD, confirm=lambda wire: seen.setdefault("w", wire) and True,
         transport=_Transport())
    wire = seen["w"]
    assert wire.url == URL
    assert wire.method == "POST"
    assert json.loads(wire.body) == PAYLOAD
    assert wire.url in wire.preview() and wire.body in wire.preview()


def test_a_confirmed_send_reaches_the_transport_and_returns_its_result():
    transport = _Transport()
    result = send(URL, PAYLOAD, confirm=lambda wire: True, transport=transport)
    assert result == "delivered"
    assert len(transport.sent) == 1


def test_confirm_runs_before_the_transport():
    """The preview is shown *before* sending, so a confirmation that refuses (or
    raises) stops the wire. Ordering is structural, not hopeful."""
    transport = _Transport()

    def confirm(wire: Wire) -> bool:
        raise RuntimeError("operator closed the dialog")

    with pytest.raises(RuntimeError):
        send(URL, PAYLOAD, confirm=confirm, transport=transport)
    assert transport.sent == []


# ── import-pure (I-26/I-30), targeted ────────────────────────────────────────

def test_egress_imports_no_network_at_module_load():
    """The default transport lazy-imports urllib inside itself; the module load
    pulls in no network. Held package-wide elsewhere; pinned here because this is
    the module most tempted to reach for it."""
    src = (Path(__file__).resolve().parent.parent
           / "homestead" / "keep" / "egress.py").read_text(encoding="utf-8")
    tree = ast.parse(src)
    top_level: set[str] = set()
    for node in tree.body:
        if isinstance(node, ast.Import):
            top_level |= {a.name.split(".")[0] for a in node.names}
        elif isinstance(node, ast.ImportFrom) and node.module:
            top_level.add(node.module.split(".")[0])
    net = {"socket", "ssl", "urllib", "http", "requests", "httpx", "aiohttp",
           "websockets", "urllib3", "socketserver", "ftplib", "smtplib"}
    assert not (net & top_level), f"egress imports a network module at load: {net & top_level}"
