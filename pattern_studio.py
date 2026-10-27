# -*- coding: utf-8 -*-
"""🎨 الاستوديو — رسومات المستخدم على الشارت (٢٨ أكتوبر ٢٠٢٦)

📌 الفكرة: المستخدم يرسم مستويات (منطقة/خط) على شارت أي سهم ويحفظها
   مع ملاحظة، فيرجع لها في أي وقت. Optionally يشاركها علناً.

⛔ قواعد:
   · مافيش تخمين: كل رسمة بتتربط بسهم وتاريخ وسعر.
   · البيانات لكل مستخدم في ملف منفصل (بدون قفل على مستوى كل المستخدمين).
   · الكتابة ذرّية (ملف مؤقت + rename) — نفس أسلوب users.json.
   · مافيش أي اسم أداة ذكاء اصطناعي في النصوص.
   · ⛔ fail-soft: أي خطأ في التسجيل ما يوقعش السيرفر.
"""
import json
import os
import time
import uuid
from pathlib import Path

HERE = Path(__file__).resolve().parent
DATA_DIR = Path(os.environ.get("OCTA_DATA_DIR", "/data"))
try:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    (DATA_DIR / ".probe_studio").write_text("1", encoding="utf-8")
except Exception:
    DATA_DIR = HERE
STUDIO_DIR = DATA_DIR / "studio"

MAX_DRAWINGS = 200
MAX_NOTE = 400


def _user_file(uid):
    safe = "".join(ch for ch in str(uid) if ch.isalnum() or ch in "-_")[:40]
    return STUDIO_DIR / ("u_%s.json" % (safe or "anon"))


def _read(uid):
    try:
        p = _user_file(uid)
        if not p.exists():
            return []
        data = json.loads(p.read_text(encoding="utf-8"))
        return data if isinstance(data, list) else []
    except Exception:
        return []


def _write(uid, items):
    try:
        STUDIO_DIR.mkdir(parents=True, exist_ok=True)
        p = _user_file(uid)
        tmp = p.with_suffix(".tmp")
        tmp.write_text(json.dumps(items, ensure_ascii=False), encoding="utf-8")
        tmp.replace(p)
        return True
    except Exception:
        return False


def _clean_text(s, limit=MAX_NOTE):
    s = str(s or "").strip()
    return s[:limit]


def save_drawing(uid, payload):
    """يحفظ رسمة واحدة. يرجّع (رسمة, خطأ)."""
    if not uid:
        return None, "لازم تسجّل دخول"
    code = str((payload or {}).get("code") or "").upper().strip()
    if not code:
        return None, "لازم تختار السهم"
    try:
        price = float((payload or {}).get("price"))
    except Exception:
        return None, "السعر لازم يكون رقم"
    if price <= 0:
        return None, "السعر لازم يكون أكبر من صفر"
    kind = str((payload or {}).get("kind") or "level")
    if kind not in ("level", "zone", "note"):
        kind = "level"
    rec = {
        "id": uuid.uuid4().hex[:12],
        "code": code,
        "name": _clean_text((payload or {}).get("name"), 80),
        "kind": kind,
        "price": round(price, 4),
        "price2": None,
        "note": _clean_text((payload or {}).get("note")),
        "visibility": "public" if (payload or {}).get("visibility") == "public" else "private",
        "created_at": time.strftime("%Y-%m-%d %H:%M:%S"),
    }
    p2 = (payload or {}).get("price2")
    if p2 is not None:
        try:
            rec["price2"] = round(float(p2), 4)
        except Exception:
            rec["price2"] = None
    items = _read(uid)
    items.append(rec)
    items.sort(key=lambda x: x.get("created_at") or "", reverse=True)
    items = items[:MAX_DRAWINGS]
    if not _write(uid, items):
        return None, "مش قادر أحفظ دلوقتي"
    return rec, None


def delete_drawing(uid, did):
    items = _read(uid)
    keep = [x for x in items if x.get("id") != did]
    if len(keep) == len(items):
        return False, "مفيش رسمة بالـid ده"
    _write(uid, keep)
    return True, None


def list_drawings(uid, code=None, scope="mine", limit=100):
    """رسومات المستخدم (scope=mine) أو أحدث الرسومات العامة (scope=public)."""
    if scope == "public":
        out = []
        try:
            for f in sorted(STUDIO_DIR.glob("u_*.json")):
                try:
                    arr = json.loads(f.read_text(encoding="utf-8"))
                except Exception:
                    continue
                for it in (arr or []):
                    if isinstance(it, dict) and it.get("visibility") == "public":
                        out.append(it)
        except Exception:
            out = []
        out.sort(key=lambda x: x.get("created_at") or "", reverse=True)
    else:
        out = _read(uid)
    if code:
        code = str(code).upper().strip()
        out = [x for x in out if x.get("code") == code]
    return out[:int(limit or 100)]


def register(app, require_user=None):
    """بيسجّل مسارات الاستوديو (fail-soft)."""
    from flask import jsonify, request

    def _guard():
        if require_user is None:
            return None
        try:
            return require_user()
        except Exception:
            return None

    @app.route("/api/studio/list", methods=["GET"])
    def studio_list():
        u = _guard()
        if require_user is not None and not u:
            return jsonify({"ok": False, "error": "لازم تسجّل دخول"}), 401
        scope = str(request.args.get("scope") or "mine")
        code = request.args.get("code")
        try:
            items = list_drawings(u.get("id") if u else None, code=code,
                                  scope=scope)
        except Exception as e:
            return jsonify({"ok": False, "error": str(e)[:160]}), 503
        return jsonify({"ok": True, "items": items, "count": len(items)})

    @app.route("/api/studio/save", methods=["POST"])
    def studio_save():
        u = _guard()
        if require_user is not None and not u:
            return jsonify({"ok": False, "error": "لازم تسجّل دخول"}), 401
        body = request.get_json(silent=True) or {}
        rec, err = save_drawing(u.get("id") if u else None, body)
        if not rec:
            return jsonify({"ok": False, "error": err or "مش قادر أحفظ"}), 400
        return jsonify({"ok": True, "item": rec})

    @app.route("/api/studio/delete", methods=["POST"])
    def studio_delete():
        u = _guard()
        if require_user is not None and not u:
            return jsonify({"ok": False, "error": "لازم تسجّل دخول"}), 401
        body = request.get_json(silent=True) or {}
        ok, err = delete_drawing(u.get("id") if u else None,
                                  str(body.get("id") or ""))
        if not ok:
            return jsonify({"ok": False, "error": err or "مش قادر أحذف"}), 400
        return jsonify({"ok": True})

    return True
