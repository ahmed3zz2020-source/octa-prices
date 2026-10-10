"""
🐙 OCTA — طبقة التنبيهات فوق التطبيق الأساسي
==============================================
هذا الملف ما بيعدّلش update_prices.py خالص.
بيستورد التطبيق، وبيضيف عليه تنبيهات تيليجرام.

Railway لازم يشغّل:  gunicorn octa_app:app

المتغيرات (Railway → Variables):
    TELEGRAM_BOT_TOKEN = 8760752022:AAHSurRALWSyWzluuVqmruN6WDZ5Cn-E8XU
    TELEGRAM_CHAT_ID   = 2073907990
"""

import os
import json
import time
import threading
from datetime import datetime as _dt

# ══════════════════════════════════════════════════════════════
#  ① التطبيق الأصلي — فيه كل الـ API الموجودة
# ══════════════════════════════════════════════════════════════

import update_prices as U

app = U.app
print(f"[octa] app loaded, routes={len(app.url_map._rules)}", flush=True)


# ══════════════════════════════════════════════════════════════
#  ② المتغيرات
# ══════════════════════════════════════════════════════════════

def _clean(v):
    """يشيل أي قالب أقواس معقوفة مزدوجة من قيمة المتغير."""
    v = str(v or "").strip()
    if not v:
        return ""
    if v.startswith("{{"):
        return ""
    if v.count(".") > 3:          # شكل مش طبيعي لتوكن
        return ""
    return v


TOKEN = _clean(os.environ.get("TELEGRAM_BOT_TOKEN", ""))
CHAT = _clean(os.environ.get("TELEGRAM_CHAT_ID", ""))
TG_ON = bool(TOKEN and CHAT)
TG_API = f"https://api.telegram.org/bot{TOKEN}"

STATE = "alerts_state.json"
COOLDOWN = 240          # 4 ساعات بين نفس التنبيه
DIGEST_HOUR = 9

ORDER = {"بيع": 0, "غير كافٍ": 1, "احتفظ": 2, "تجميع": 3}
TG_ERR = [""]


# ══════════════════════════════════════════════════════════════
#  ③ الحالة
# ══════════════════════════════════════════════════════════════

def st_load():
    try:
        with open(STATE, "r", encoding="utf-8") as f:
            d = json.load(f)
            return d if isinstance(d, dict) else {}
    except Exception:
        return {}


def st_save(d):
    try:
        with open(STATE + ".t", "w", encoding="utf-8") as f:
            json.dump(d, f, ensure_ascii=False)
        os.replace(STATE + ".t", STATE)
    except Exception as e:
        print(f"[tg] save: {e}", flush=True)


def can(d, k):
    return (time.time() - d.get("sent", {}).get(k, 0)) >= COOLDOWN * 60


def mark(d, k):
    d.setdefault("sent", {})[k] = int(time.time())


def clr(d, k):
    d.get("sent", {}).pop(k, None)


# ══════════════════════════════════════════════════════════════
#  ④ الإرسال
# ══════════════════════════════════════════════════════════════

def send(text, silent=False):
    if not TG_ON:
        TG_ERR[0] = "bot disabled"
        return False
    try:
        import requests
        p = {"chat_id": CHAT, "text": str(text)[:3900],
             "disable_web_page_preview": "true"}
        if silent:
            p["disable_notification"] = "true"
        r = requests.post(f"{TG_API}/sendMessage", data=p, timeout=15)
        if r.status_code != 200:
            TG_ERR[0] = f"HTTP {r.status_code}: {str(r.text)[:180]}"
            print(f"[tg] {TG_ERR[0]}", flush=True)
            return False
        TG_ERR[0] = ""
        return True
    except Exception as e:
        TG_ERR[0] = f"{type(e).__name__}: {e}"
        print(f"[tg] {TG_ERR[0]}", flush=True)
        return False


def esc(v):
    return str(v if v is not None else "?").replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def pc(x):
    try:
        return f"{float(x):+.2f}%"
    except Exception:
        return "?"


# ══════════════════════════════════════════════════════════════
#  ⑤ قائمة المتابعة
# ══════════════════════════════════════════════════════════════

def w_add(d, code, hi=None, lo=None):
    c = str(code or "").upper().strip()
    if not c:
        return
    it = d.setdefault("watch", {}).setdefault(c, {})
    if hi not in (None, ""):
        it["hi"] = float(hi)
    if lo not in (None, ""):
        it["lo"] = float(lo)
    it.setdefault("at", int(time.time()))


def w_del(d, code):
    d.setdefault("watch", {}).pop(str(code or "").upper().strip(), None)


def w_list(d):
    return [{"code": c, "hi": v.get("hi"), "lo": v.get("lo"), "at": v.get("at")}
            for c, v in (d.get("watch") or {}).items()]


# ══════════════════════════════════════════════════════════════
#  ⑥ التنبيهات الأربعة
# ══════════════════════════════════════════════════════════════

def a_price(d, rows):
    out = []
    for r in rows or []:
        code, px = r.get("code"), r.get("price")
        if not code or not px:
            continue
        try:
            px = float(px)
        except Exception:
            continue
        prev = (d.get("prices") or {}).get(code)
        ch = ((px - prev["p"]) / prev["p"] * 100) if (prev and prev.get("p")) else 0.0
        d.setdefault("prices", {})[code] = {"p": px, "t": int(time.time())}

        w = (d.get("watch") or {}).get(code)
        if not w:
            continue

        if w.get("hi") and px >= float(w["hi"]):
            k = f"hi:{code}"
            if can(d, k) and send(
                f"🔺 <b>السهم عدّى الحد الأعلى</b>\n\n"
                f"<b>{esc(r.get('name') or code)}</b> ({esc(code)})\n"
                f"السعر: <b>{px:.2f} ج</b>\nحدّك: {float(w['hi']):.2f} ج\n"
                f"التغير: {pc(ch)}\n\n💡 شوف السبب في كارت القرار قبل ما تبيع."):
                mark(d, k); out.append(code)

        if w.get("lo") and px <= float(w["lo"]):
            k = f"lo:{code}"
            if can(d, k) and send(
                f"🔻 <b>السهم وصل الحد الأدنى</b>\n\n"
                f"<b>{esc(r.get('name') or code)}</b> ({esc(code)})\n"
                f"السعر: <b>{px:.2f} ج</b>\nحدّك: {float(w['lo']):.2f} ج\n"
                f"التغير: {pc(ch)}\n\n💡 إشارة شراء — اتأكد إن السبب لسه قايم."):
                mark(d, k); out.append(code)

        if abs(ch) >= 4.0:
            k = f"mv:{code}"
            if can(d, k) and send(
                f"{'📈' if ch > 0 else '📉'} <b>حركة كبيرة</b>\n\n"
                f"<b>{esc(r.get('name') or code)}</b> ({esc(code)})\n"
                f"السعر: <b>{px:.2f} ج</b>\nالتغير: <b>{pc(ch)}</b>"):
                mark(d, k); out.append(code)

        if w.get("hi") and px < float(w["hi"]) * 0.97:
            clr(d, f"hi:{code}")
        if w.get("lo") and px > float(w["lo"]) * 1.03:
            clr(d, f"lo:{code}")
        if abs(ch) < 1.5:
            clr(d, f"mv:{code}")
    return out


def a_decision(d, rows):
    out = []
    for r in rows or []:
        code, dec = r.get("code"), r.get("decision")
        if not code or not dec:
            continue
        prev = (d.get("decisions") or {}).get(code)
        d.setdefault("decisions", {})[code] = {"d": dec, "t": int(time.time())}
        if not prev or prev.get("d") == dec:
            continue
        k = f"dec:{code}"
        if not can(d, k):
            continue
        up = ORDER.get(dec, 1) > ORDER.get(prev["d"], 1)
        if send(
            f"{'⬆️' if up else '⬇️'} <b>التوصية اتغيّرت ({'تحسّن' if up else 'ضعف'})</b>\n\n"
            f"<b>{esc(r.get('name') or code)}</b> ({esc(code)})\n"
            f"السعر: {float(r.get('price') or 0):.2f} ج\n"
            f"من <b>{esc(prev['d'])}</b> ← إلى <b>{esc(dec)}</b>\n"
            + (f"النقاط: {r.get('score')}\n" if r.get("score") else "")
            + "💡 افتح كارت القرار على OCTA."):
            mark(d, k); out.append(code)
    return out


def a_dividend(d, divs):
    out = []
    today = _dt.now().date()
    for v in divs or []:
        code, ex = v.get("code"), v.get("ex_date")
        if not code or not ex:
            continue
        try:
            exd = _dt.strptime(str(ex)[:10], "%Y-%m-%d").date()
        except Exception:
            continue
        days = (exd - today).days
        if days < 0 or days > 7:
            continue
        k = f"div:{code}:{exd}"
        if not can(d, k):
            continue
        head = ("🔴 <b>استحقاق اليوم!</b>" if days == 0 else
                "🟠 <b>استحقاق بكرة</b>" if days == 1 else
                f"🟡 <b>استحقاق بعد {days} أيام</b>")
        amt = v.get("amount")
        amt_t = f"{float(amt):.4f} ج" if amt not in (None, "", "-") else "غير محدد"
        if send(f"{head}\n\n<b>{esc(v.get('name') or code)}</b> ({esc(code)})\n"
                f"📅 الاستحقاق: <b>{exd}</b>\n💰 التوزيع: {amt_t}\n\n"
                f"💡 لازم تكون ماسك السهم يوم الاستحقاق."):
            mark(d, k); out.append(code)
    return out


def a_risk(d, rows):
    out = []
    for r in rows or []:
        code = r.get("code")
        if not code:
            continue
        m = r.get("mdd1y")
        if m is None:
            continue
        try:
            mv = abs(float(m))
        except Exception:
            continue
        k = f"risk:{code}"
        if mv >= 20:
            if can(d, k) and send(
                f"⚠️ <b>تحذير مخاطرة</b>\n\n"
                f"<b>{esc(r.get('name') or code)}</b> ({esc(code)})\n"
                f"أكبر هبوط في سنة: <b>-{mv:.1f}%</b>"
                + (f"\nمن أعلى 52 أسبوع: {pc(r.get('frm52hi'))}" if r.get("frm52hi") else "")
                + "\n\n💡 مؤشر خطر — مش نصيحة بيع."):
                mark(d, k); out.append(code)
        elif mv < 12:
            clr(d, k)
    return out


def digest(d, ranked, divs=None):
    today = _dt.now().strftime("%Y-%m-%d")
    if d.get("last_digest") == today or not ranked:
        return False
    top = ranked[:5]
    lines = [f"<b>{i}.</b> {esc(r.get('name') or r.get('code'))} ({esc(r.get('code'))}) — "
             f"{esc(r.get('decision'))}" + (f" · {r.get('score')} نقطة" if r.get("score") else "")
             for i, r in enumerate(top, 1)]
    dist = {}
    for r in ranked:
        dist[r.get("decision")] = dist.get(r.get("decision"), 0) + 1
    dv = ""
    if divs:
        near = [x for x in divs if x.get("ex_date") and str(x["ex_date"])[:10] >= today]
        if near:
            dv = "\n\n📅 <b>استحقاقات قريبة</b>\n" + "\n".join(
                f"· {esc(x.get('name') or x.get('code'))} — {str(x['ex_date'])[:10]}"
                for x in near[:5])
    msg = (f"🌅 <b>ملخص OCTA اليوم</b>\n{_dt.now().strftime('%Y-%m-%d %H:%M')}\n{'━'*20}\n\n"
           f"🏆 <b>أفضل {len(top)} فرص</b>\n" + "\n".join(lines)
           + "\n\n📊 <b>توزيع القرارات</b>\n" + " · ".join(f"{esc(k)} {v}" for k, v in dist.items())
           + f"\n\n👁️ <b>المتابعة</b> {len(d.get('watch') or {})} سهم" + dv)
    if send(msg, silent=True):
        d["last_digest"] = today
        return True
    return False


def run_alerts(ranked=None, divs=None, risk_rows=None):
    if not TG_ON:
        return
    d = st_load()
    try:
        p = a_price(d, ranked)
        dc = a_decision(d, ranked)
        dv = a_dividend(d, divs)
        rk = a_risk(d, risk_rows)
        dg = digest(d, ranked, divs) if _dt.now().hour >= DIGEST_HOUR else False
        st_save(d)
        if any([p, dc, dv, rk, dg]):
            print(f"[tg] sent p={p} d={dc} v={dv} r={rk} dg={dg}", flush=True)
    except Exception as e:
        print(f"[tg] run: {e}", flush=True)


# ══════════════════════════════════════════════════════════════
#  ⑦ الجدولة
# ══════════════════════════════════════════════════════════════

def _loop():
    time.sleep(120)
    while True:
        try:
            ld = getattr(U, "LIVE_DATA", {}) or {}
            st = ld.get("egx30") or []
            if st and TG_ON:
                ranked = [{"code": x.get("code"), "name": x.get("name"),
                           "price": x.get("price"), "decision": x.get("decision"),
                           "score": x.get("final_score")}
                          for x in st if isinstance(x, dict)]
                ranked.sort(key=lambda r: -(r.get("score") or 0))
                risk = [{"code": x.get("code"), "name": x.get("name"),
                         "mdd1y": x.get("mdd1y"), "frm52hi": x.get("frm52hi")}
                        for x in st if isinstance(x, dict) and x.get("mdd1y")]
                divs = [{"code": a.get("code") or a.get("symbol"), "name": a.get("name"),
                         "ex_date": a.get("ex_date") or a.get("exDate"),
                         "amount": a.get("amount") or a.get("value"), "type": a.get("type")}
                        for a in (getattr(U, "_actions", []) or [])]
                run_alerts(ranked=ranked[:60], divs=divs, risk_rows=risk)
        except Exception as e:
            print(f"[tg] loop: {e}", flush=True)
        time.sleep(300)


print(f"[tg] enabled={TG_ON} token={TOKEN[:6] if TOKEN else '-'} chat={CHAT or '-'}",
      flush=True)
if TG_ON:
    threading.Thread(target=_loop, daemon=True).start()


# ══════════════════════════════════════════════════════════════
#  ⑧ المسارات
# ══════════════════════════════════════════════════════════════

from flask import jsonify, request


@app.route("/api/alerts/test", methods=["GET"])
def _octa_test():
    ok = send("OCTA test " + str(int(time.time())))
    return jsonify({"ok": ok, "enabled": TG_ON, "error": TG_ERR[0],
                    "bot_ok": ok})


@app.route("/api/alerts/state", methods=["GET"])
def _octa_state():
    d = st_load()
    return jsonify({"ok": True, "enabled": TG_ON,
                    "watch": len(d.get("watch") or {}),
                    "tracked": len(d.get("prices") or {}),
                    "last_digest": d.get("last_digest")})


@app.route("/api/alerts/watch", methods=["GET"])
def _octa_watch_get():
    return jsonify({"ok": True, "items": w_list(st_load())})


@app.route("/api/alerts/watch", methods=["POST"])
def _octa_watch_post():
    d = st_load()
    j = request.get_json(silent=True) or {}
    a = j.get("action")
    if a == "add":
        w_add(d, j.get("code"), j.get("hi"), j.get("lo"))
    elif a == "del":
        w_del(d, j.get("code"))
    elif a == "clear":
        d["watch"] = {}
    st_save(d)
    return jsonify({"ok": True, "items": w_list(d)})


@app.route("/api/alerts/diag", methods=["GET"])
def _octa_diag():
    out = {"code": "diag", "enabled": TG_ON,
           "token_len": len(TOKEN), "chat": CHAT, "routes": len(app.url_map._rules)}
    if TG_ON:
        try:
            import requests
            r = requests.get(f"{TG_API}/getMe", timeout=12)
            out["getMe"] = r.status_code
            try:
                out["bot"] = (r.json().get("result") or {}).get("username")
            except Exception:
                pass
        except Exception as e:
            out["getMe_err"] = str(e)[:120]
    return jsonify(out)


print("[octa] ✅ ready", flush=True)
