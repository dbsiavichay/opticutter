import hashlib
import json
from typing import Any, Dict


def to_primitive(data: Any) -> Any:
    if hasattr(data, "model_dump"):
        return data.model_dump()
    if isinstance(data, dict):
        return {k: to_primitive(v) for k, v in data.items()}
    if isinstance(data, list):
        return [to_primitive(v) for v in data]
    return data


def canonical_json_dumps(data: Any) -> str:
    """Serialize data to a canonical JSON string with sorted keys and no whitespace."""
    data = to_primitive(data)
    return json.dumps(data, sort_keys=True, separators=(",", ":"))


def request_hash(payload: Any) -> str:
    canonical = canonical_json_dumps(payload)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def canonicalize_optimize_payload(payload: Any) -> Dict[str, Any]:
    """Return a canonical dict representation of an OptimizeRequest payload.
    - Sorts materials by code
    - Sorts cuts by (material, width, height, quantity, label, force_grain)
    This makes the hash idempotent regardless of list ordering in the request.
    """
    data = to_primitive(payload)
    materials = data.get("materials", [])
    cuts = data.get("cuts", [])
    cutting_parameters = data.get("cutting_parameters", {})

    def norm_grain(v: Any) -> str:
        if v is None:
            return "none"
        if isinstance(v, str):
            return v
        # pydantic Enum -> .value
        return getattr(v, "value", str(v))

    materials_sorted = sorted(
        [
            {
                "code": m["code"],
                "width": int(m["width"]),
                "height": int(m["height"]),
                "price": float(m.get("price", 0.0)),
                "grain_direction": norm_grain(m.get("grain_direction")),
            }
            for m in materials
        ],
        key=lambda m: (
            m["code"],
            m["width"],
            m["height"],
            m["price"],
            m["grain_direction"],
        ),
    )

    cuts_sorted = sorted(
        [
            {
                "material": c["material"],
                "width": int(c["width"]),
                "height": int(c["height"]),
                "quantity": int(c.get("quantity", 1)),
                "label": c.get("label") or "",
                "force_grain": norm_grain(c.get("force_grain")),
            }
            for c in cuts
        ],
        key=lambda c: (
            c["material"],
            c["width"],
            c["height"],
            c["quantity"],
            c["label"],
            c["force_grain"],
        ),
    )

    cp = {
        "kerf": int(cutting_parameters.get("kerf", 0)),
        "top_trim": int(cutting_parameters.get("top_trim", 0)),
        "bottom_trim": int(cutting_parameters.get("bottom_trim", 0)),
        "left_trim": int(cutting_parameters.get("left_trim", 0)),
        "right_trim": int(cutting_parameters.get("right_trim", 0)),
    }

    return {
        "materials": materials_sorted,
        "cuts": cuts_sorted,
        "cutting_parameters": cp,
    }


def hash_optimize_request(payload: Any) -> str:
    canonical = canonicalize_optimize_payload(payload)
    return request_hash(canonical)
