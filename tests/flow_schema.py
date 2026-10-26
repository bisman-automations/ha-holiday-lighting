"""Serialize a flow form's schema exactly the way Home Assistant sends it.

The frontend never sees a voluptuous schema: Home Assistant's flow HTTP and
websocket views turn it into a JSON field list first. Which library does that
depends on the Home Assistant release:

- up to 2026.9, ``voluptuous_serialize.convert``;
- from 2026.10, ``probatio.to_field_list`` (voluptuous-serialize is no longer
  installed).

Both are called with ``config_validation.custom_serializer``, which knows
selectors and sections. That serializer returns "not handled" as a sentinel
that only its own library understands, so mixing them (voluptuous-serialize
with the 2026.10 serializer) fails on every field. That is what broke these
tests on 2026.10; the forms themselves were fine.

Tests use :func:`serialize_schema` so they check the same JSON the frontend
gets on whichever Home Assistant they run against.
"""

from __future__ import annotations

from typing import Any

from homeassistant.helpers import (
    config_validation as cv,
    data_entry_flow as flow_helpers,
)

# Follow Home Assistant's own choice rather than what happens to be importable:
# voluptuous-serialize can still be installed next to a release that no longer
# uses it.
if hasattr(flow_helpers, "probatio"):
    from probatio import to_field_list as _convert  # HA 2026.10 and newer
else:
    from voluptuous_serialize import convert as _convert  # HA 2026.9 and older


def serialize_schema(schema: Any) -> list[dict[str, Any]]:
    """Return the field list the frontend receives for ``schema``."""
    return _convert(schema, custom_serializer=cv.custom_serializer)
