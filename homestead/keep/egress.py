"""No network egress by default (I-17).

Nothing on this face dials on its own. `send()` **refuses** unless the caller
performs an explicit per-call act: it is shown *exactly* what will go, and it
says yes. Two properties carry the invariant, and each is a test:

* **Refused by default.** With no confirmation, `send()` raises `EgressRefused`
  (a `PermissionError`). There is no ambient "allow egress" flag to set once and
  forget — the permission is per call, spent on the call, and not remembered.
  A default that could be flipped globally is the F-3 shape: an outbound path
  that fires without a human in the loop for *this* datum.

* **The preview is the payload.** "Shows the user exactly what will be sent" is
  not a summary rendered beside a separate request — it *is* the request. `send`
  serializes the payload **once** into a `Wire`, hands that same `Wire` to the
  confirmation, and hands the same object to the transport. The bytes the
  operator approves are the bytes that leave, because they are one object. That
  is BUG-5's answer pointed at the wire: the screen said "Excluded from drafting"
  while the packet carried the atom, and it was possible only because the shown
  thing and the sent thing were computed separately. Here they cannot diverge.

**Import-pure (I-26), and nothing listens (I-30).** No network module is imported
at module load; the default transport imports `urllib` *inside itself*, reached
only after a confirmed act. An outbound dial is not a bound port — this file
never listens — but it is still the one place the self-contained face could reach
out, so it is the one place the refusal lives.

**The rung is the caller's to clear first.** `send` is transport, not the gate:
what may cross S4 at all is `serve(item, Surface.S4_EGRESS, purpose=…)`'s
decision, made upstream, and the caller sends the *served* value. `send` does not
re-score a rung; it makes the act itself refusable and honest. An `L5` datum
never reaches here because `serve` returned it as nothing.
"""
from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any, Callable

__all__ = ["Wire", "EgressRefused", "send"]


class EgressRefused(PermissionError):
    """An outbound call that did not happen.

    A `PermissionError` because the act was not permitted — the caller must be
    able to tell that apart from a transport failure. Raised for the two reasons
    egress must not proceed: no confirmation was supplied (there is no egress
    without an explicit per-call act), or the confirmation declined after seeing
    exactly what would go.
    """


@dataclass(frozen=True)
class Wire:
    """Exactly what would be sent — the preview and the payload as one object.

    The confirmation is handed this, and the transport is handed *this same
    object*, so the bytes approved are the bytes that leave. `body` is the
    serialized request, computed once; nothing downstream re-serializes, so
    nothing can carry a different payload than the one that was shown.
    """

    method: str
    url: str
    body: str
    content_type: str = "application/json"

    def preview(self) -> str:
        """A plain rendering of the whole request, for showing the operator.
        It is the request — url, method, and the exact body — not a gloss of it."""
        return f"{self.method} {self.url}\ncontent-type: {self.content_type}\n\n{self.body}"


#: A confirmation is shown the `Wire` and returns whether it may go. `None` is not
#: a confirmation — it is the absence of one, and absence refuses.
Confirm = Callable[[Wire], bool]
#: A transport is handed the *same* `Wire` the confirmation saw and performs the
#: send. Injected so the core stays import-pure; the default lazy-imports urllib.
Transport = Callable[[Wire], Any]


def _default_transport(wire: Wire) -> Any:
    """The real send, reached only after a confirmed act. Imports `urllib`
    **here**, not at module load, so the core imports no network (I-26) and the
    package-wide scan (`test_i30_i26_nothing_imports_the_network`) stays green."""
    import urllib.request

    request = urllib.request.Request(
        wire.url,
        data=wire.body.encode("utf-8"),
        method=wire.method,
        headers={"content-type": wire.content_type},
    )
    with urllib.request.urlopen(request) as response:   # noqa: S310 — url is the confirmed one
        return response.read()


def send(
    url: str,
    payload: Any,
    *,
    confirm: Confirm | None = None,
    transport: Transport | None = None,
    method: str = "POST",
) -> Any:
    """Make an outbound call — but only after an explicit, informed per-call act.

    Serializes `payload` once into a `Wire`, then:

    * with no `confirm`, raises `EgressRefused` — there is no egress by default;
    * calls `confirm(wire)`, showing *exactly* what will be sent; if it returns
      falsy, raises `EgressRefused` and sends nothing;
    * only then hands that **same** `Wire` to the transport (the injected one, or
      the lazy-`urllib` default) and returns its result.

    The confirmation and the transport receive one object, so what was approved
    is what leaves. `payload` is the already-served value the caller means to
    send; `send` is transport, and the rung was cleared upstream by `serve`.
    """
    body = json.dumps(payload, sort_keys=True, ensure_ascii=False)
    wire = Wire(method=method, url=url, body=body)

    if confirm is None:
        raise EgressRefused(
            "no egress without an explicit per-call act (I-17). Nothing on this "
            "face dials by default; pass confirm=, which is shown exactly what "
            "will be sent and returns whether it may go. There is no ambient "
            "flag to set once — the permission is per call and spent on it."
        )
    if not confirm(wire):
        raise EgressRefused(
            f"egress declined at the preview: {wire.method} {wire.url} was shown "
            "and not approved, so nothing was sent."
        )

    return (transport or _default_transport)(wire)
