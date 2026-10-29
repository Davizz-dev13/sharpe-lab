"""JSON estricto para la web: NaN/inf de float pasan a null.

json.dumps escribe NaN tal cual por defecto, y eso no es JSON valido: el
navegador (JSON.parse / fetch().json()) revienta al leer el archivo.
"""
from __future__ import annotations
import math


def clean(o):
    """Recorre dicts/listas y cambia los float NaN/inf (tambien numpy) por None."""
    if isinstance(o, dict):
        return {k: clean(v) for k, v in o.items()}
    if isinstance(o, (list, tuple)):
        return [clean(v) for v in o]
    if isinstance(o, float) and not math.isfinite(o):  # np.float64 es subclase de float
        return None
    if hasattr(o, "item") and not isinstance(o, (str, bytes)):  # escalares numpy (np.float32, np.int64...)
        try:
            v = o.item()
        except Exception:
            return o
        return None if isinstance(v, float) and not math.isfinite(v) else v
    return o
