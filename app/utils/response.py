from __future__ import annotations

from flask import jsonify


def ok(**payload):
    data = {"ok": True}
    data.update(payload)
    return jsonify(data)


def err(message: str, status_code: int = 400, **extra):
    data = {"ok": False, "error": message}
    data.update(extra)
    return jsonify(data), status_code
