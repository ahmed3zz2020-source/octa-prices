"""
🐙 OCTA — نقطة الدخول مع تنبيهات تيليجرام
===========================================
مهم: هذا الملف لا يلمس update_prices.py إطلاقًا.
يستورد كل حاجة، ويضيف طبقة التنبيهات، ثم يشغّل.

Railway يشغّل:  gunicorn octa_app:app
الملف القديم    update_prices:app  (لسه شغال لوحده عادي)

التركيب في Railway:
  Settings → Variables (موجودين)
  ثم غيّر Procfile لسطر واحد:
      web: gunicorn octa_app:app --bind 0.0.0.0:$PORT --workers 1 --timeout 120
"""

# ══════════════════════════════════════════════════════════════
#  ① نستورد التطبيق الأصلي — فيه كل الـ routes الموجودة
# ══════════════════════════════════════════════════════════════

import update_prices as U

app = U.app
print("[octa_app] importing update_prices...", flush=True)



# ══════════════════════════════════════════════════════════════
#  ② طبقة التنبيهات — مستقلة تماماً
# ══════════════════════════════════════════════════════════════

import os
import json
import time
import threading
from datetime import datetime as _dt

TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN", "").strip()
CHAT = os.environ.get("TELEGRAM_CHAT_ID", "").strip()
TG_ON = bool(TOKEN and CHAT)
TG_API = f"https://api.telegram.org/bot{TOKEN}"

STATE = os.environ.get("ALERTS_STATE_PATH", "alerts_state.json")
COOLDOWN_MIN = int(os.environ.get("ALERT_INTERVAL_MIN", "240"))
DIGEST_HOUR = int(os.environ.get("ALERT_DIGEST_HOUR", "9"))

ORDER = {"بيع": 0, "غير كافٍ": 1, "احتفظ": 2, "تجميع": 3}


# ── حالة ─────────────────────────────────────────────────────

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
        print(f"[tg] save: {e}")


def can_send(d, key):
    last = d.get("sent", {}).get(key, 0)
    return (time.time() - last) >= COOLDOWN_MIN * 60


def mark(d, key):
    d.setdefault("sent", {})[key] = int(time.time())


def clear_key(d, key):
    d.get("sent", {}).pop(key, None)


# ── إرسال ────────────────────────────────────────────────────

def send(text, silent=False):
    if not TG_ON:
        return False
    try:
        import requests
        p = {"chat_id": CHAT, "text": text[:3900],
             "parse_mode": "HTML", "disable_web_page_preview": True}
        if silent:
            p["disable_notification"] = True
        r = requests.post(f"{TG_API}/sendMessage", data=p, timeout=15)
        return r.status_code == 200
    except Exception as e:
        print(f"[tg] send: {e}")
        return False


def esc(v):
    return str(v if v is not None else "?").replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def pct(x):
    try:
        return f"{float(x):+.2f}%"
    except Exception:
        return "?"


# ── متابعة ───────────────────────────────────────────────────

def watch_add(d, code, hi=None, lo=None):
    c = str(code or "").upper().strip()
    if not c:
        return
    it = d.setdefault("watch", {}).setdefault(c, {})
    if hi not in (None, ""):
        it["hi"] = float(hi)
    if lo not in (None, ""):
        it["lo"] = float(lo)
    it.setdefault("at", int(time.time()))


def watch_del(d, code):
    d.setdefault("watch", {}).pop(str(code or "").upper().strip(), None)


def watch_list(d):
    return [{"code": c, "hi": v.get("hi"), "lo": v.get("lo"), "at": v.get("at")}
            for c, v in (d.get("watch") or {}).items()]


# ══════════════════════════════════════════════════════════════
#  ③ التنبيهات الأربعة
# ══════════════════════════════════════════════════════════════

def alert_price(d, rows):
    hits = []
    for r in rows or []:
        code, px = r.get("code"), r.get("price")
        if not code or not px:
            continue
        px = float(px)
        prev = (d.get("prices") or {}).get(code)
        ch = ((px - prev["p"]) / prev["p"] * 100) if (prev and prev.get("p")) else 0.0
        d.setdefault("prices", {})[code] = {"p": px, "t": int(time.time())}

        w = (d.get("watch") or {}).get(code)
        if not w:
            continue

        if w.get("hi") and px >= float(w["hi"]):
            k = f"hi:{code}"
            if can_send(d, k) and send(
                f"🔺 <b>السهم عدّى الحد الأعلى</b>\n\n"
                f"<b>{esc(r.get('name') or code)}</b> ({esc(code)})\n"
                f"السعر: <b>{px:.2f} ج</b>\nحدّك: {float(w['hi']):.2f} ج\n"
                f"التغير: {pct(ch)}\n\n"
                f"💡 لو باعته — شوف السبب في كارت القرار قبل ما تبيع."
            ):
                mark(d, k); hits.append(code)

        if w.get("lo") and px <= float(w["lo"]):
            k = f"lo:{code}"
            if can_send(d, k) and send(
                f"🔻 <b>السهم وصل الحد الأدنى</b>\n\n"
                f"<b>{esc(r.get('name') or code)}</b> ({esc(code)})\n"
                f"السعر: <b>{px:.2f} ج</b>\nحدّك: {float(w['lo']):.2f} ج\n"
                f"التغير: {pct(ch)}\n\n"
                f"💡 ده إشارة شراء — بس اتأكد إن السبب لسه قايم."
            ):
                mark(d, k); hits.append(code)

        if abs(ch) >= 4.0:
            k = f"mv:{code}"
            if can_send(d, k) and send(
                f"{'📈' if ch > 0 else '📉'} <b>حركة كبيرة</b>\n\n"
                f"<b>{esc(r.get('name') or code)}</b> ({esc(code)})\n"
                f"السعر: <b>{px:.2f} ج</b>\nالتغير: <b>{pct(ch)}</b>"
            ):
                mark(d, k); hits.append(code)

        if w.get("hi") and px < float(w["hi"]) * 0.97:
            clear_key(d, f"hi:{code}")
        if w.get("lo") and px > float(w["lo"]) * 1.03:
            clear_key(d, f"lo:{code}")
        if abs(ch) < 1.5:
            clear_key(d, f"mv:{code}")
    return hits


def alert_decision(d, rows):
    hits = []
    for r in rows or []:
        code, dec = r.get("code"), r.get("decision")
        if not code or not dec:
            continue
        prev = (d.get("decisions") or {}).get(code)
        d.setdefault("decisions", {})[code] = {"d": dec, "t": int(time.time())}
        if not prev or prev.get("d") == dec:
            continue

        po, no = ORDER.get(prev["d"], 1), ORDER.get(dec, 1)
        k = f"dec:{code}"
        if not can_send(d, k):
            continue
        up = no > po
        if send(
            f"{'⬆️' if up else '⬇️'} <b>التوصية اتغيّرت ({'تحسّن' if up else 'ضعف'})</b>\n\n"
            f"<b>{esc(r.get('name') or code)}</b> ({esc(code)})\n"
            f"السعر: {float(r.get('price') or 0):.2f} ج\n"
            f"من <b>{esc(prev['d'])}</b> ← إلى <b>{esc(dec)}</b>\n"
            + (f"النقاط: {r.get('score')}\n" if r.get("score") else "")
            + "\n💡 افتح كارت القرار على OCTA وشوف السبب."
        ):
            mark(d, k); hits.append(code)
    return hits


def alert_dividend(d, divs):
    hits = []
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
        if not can_send(d, k):
            continue
        head = ("🔴 <b>استحقاق اليوم!</b>" if days == 0 else
                "🟠 <b>استحقاق بكرة</b>" if days == 1 else
                f"🟡 <b>استحقاق بعد {days} أيام</b>")
        amt = v.get("amount")
        amt_t = f"{float(amt):.4f} ج" if amt not in (None, "", "-") else "غير محدد"
        if send(
            f"{head}\n\n<b>{esc(v.get('name') or code)}</b> ({esc(code)})\n"
            f"📅 الاستحقاق: <b>{exd}</b>\n💰 التوزيع: {amt_t}\n\n"
            f"💡 لازم تكون ماسك السهم يوم الاستحقاق (مش يوم الصرف)."
        ):
            mark(d, k); hits.append(code)
    return hits


def alert_risk(d, rows):
    hits = []
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
            if can_send(d, k) and send(
                f"⚠️ <b>تحذير مخاطرة</b>\n\n"
                f"<b>{esc(r.get('name') or code)}</b> ({esc(code)})\n"
                f"أكبر هبوط في سنة: <b>-{mv:.1f}%</b>"
                + (f"\nمن أعلى 52 أسبوع: {pct(r.get('frm52hi'))}" if r.get("frm52hi") else "")
                + "\n\n💡 ده مؤشر خطر — مش نصيحة بيع. راجع كارت القرار."
            ):
                mark(d, k); hits.append(code)
        elif mv < 12:
            clear_key(d, k)
    return hits


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
    div_t = ""
    if divs:
        near = [x for x in divs if x.get("ex_date") and str(x["ex_date"])[:10] >= today]
        if near:
            div_t = "\n\n📅 <b>استحقاقات قريبة</b>\n" + "\n".join(
                f"· {esc(x.get('name') or x.get('code'))} — {str(x['ex_date'])[:10]}"
                for x in near[:5])
    msg = (f"🌅 <b>ملخص OCTA اليوم</b>\n{_dt.now().strftime('%Y-%m-%d %H:%M')}\n{'━'*20}\n\n"
           f"🏆 <b>أفضل {len(top)} فرص</b>\n" + "\n".join(lines)
           + f"\n\n📊 <b>توزيع القرارات</b>\n" + " · ".join(f"{esc(k)} {v}" for k, v in dist.items())
           + f"\n\n👁️ <b>المتابعة</b> {len(d.get('watch') or {})} سهم" + div_t)
    if send(msg, silent=True):
        d["last_digest"] = today
        return True
    return False


def run_alerts(ranked=None, divs=None, risk_rows=None):
    if not TG_ON:
        return
    d = st_load()
    try:
        p = alert_price(d, ranked)
        dc = alert_decision(d, ranked)
        dv = alert_dividend(d, divs)
        rk = alert_risk(d, risk_rows)
        dg = digest(d, ranked, divs) if _dt.now().hour >= DIGEST_HOUR else False
        st_save(d)
        if any([p, dc, dv, rk, dg]):
            print(f"[tg] sent price={p} dec={dc} div={dv} risk={rk} digest={dg}")
    except Exception as e:
        print(f"[tg] run: {e}")


# ══════════════════════════════════════════════════════════════
#  ④ جدولة — مستقلة تماماً عن update_prices
# ══════════════════════════════════════════════════════════════

def _alert_loop():
    """thread منفصل — بيقرأ LIVE_DATA ويبعت تنبيهات."""
    time.sleep(90)                                   # استنى التطبيق warms up
    every = 300                                      # كل 5 دقايق
    while True:
        try:
            ld = getattr(U, "LIVE_DATA", {}) or {}
            st = ld.get("egx30") or ld.get("stocks") or []
            if st and TG_ON:
                ranked = []
                for x in st:
                    if not isinstance(x, dict):
                        continue
                    ranked.append({
                        "code": x.get("code"),
                        "name": x.get("name"),
                        "price": x.get("price"),
                        "decision": x.get("decision"),
                        "score": x.get("final_score"),
                    })
                ranked.sort(key=lambda r: -(r.get("score") or 0))
                risk = [{"code": x.get("code"), "name": x.get("name"),
                         "mdd1y": x.get("mdd1y"), "frm52hi": x.get("frm52hi")}
                        for x in st if isinstance(x, dict) and x.get("mdd1y")]
                divs = [{"code": a.get("code") or a.get("symbol"),
                         "name": a.get("name"),
                         "ex_date": a.get("ex_date") or a.get("exDate"),
                         "amount": a.get("amount") or a.get("value"),
                         "type": a.get("type")}
                        for a in (getattr(U, "_actions", []) or [])]
                run_alerts(ranked=ranked[:60], divs=divs, risk_rows=risk)
        except Exception as e:
            print(f"[tg] loop: {e}")
        time.sleep(every)


if TG_ON:
    print("[octa_app] ✅ Telegram alerts ON")
    threading.Thread(target=_alert_loop, daemon=True).start()
else:
    print("[octa_app] ⚠️ Telegram alerts OFF — env vars missing")


# ══════════════════════════════════════════════════════════════
#  ⑤ المسارات — تُضاف للتطبيق الأصلي
# ══════════════════════════════════════════════════════════════

from flask import jsonify, request


@app.route("/api/alerts/test", methods=["GET"])
def _octa_alerts_test():
    ok = send("✅ <b>تنبيهات OCTA شغّالة</b>\n\n"
              "🔺🔻 السعر يوصل للحد اللي حددته\n"
              "⬆️⬇️ التوصية تتغيّر\n"
              "📅 قبل أي استحقاق\n"
              "⚠️ هبوط حاد\n🌅 ملخص كل يوم")
    return jsonify({"ok": ok, "enabled": TG_ON})


@app.route("/api/alerts/watch", methods=["GET"])
def _octa_watch_get():
    return jsonify({"ok": True, "items": watch_list(st_load())})


@app.route("/api/alerts/watch", methods=["POST"])
def _octa_watch_post():
    d = st_load()
    j = request.get_json(silent=True) or {}
    a = j.get("action")
    if a == "add":
        watch_add(d, j.get("code"), j.get("hi"), j.get("lo"))
    elif a == "del":
        watch_del(d, j.get("code"))
    elif a == "clear":
        d["watch"] = {}
    st_save(d)
    return jsonify({"ok": True, "items": watch_list(d)})


@app.route("/api/alerts/state", methods=["GET"])
def _octa_alerts_state():
    d = st_load()
    return jsonify({"ok": True, "enabled": TG_ON,
                    "watch": len(d.get("watch") or {}),
                    "tracked": len(d.get("prices") or {}),
                    "last_digest": d.get("last_digest")})


print("[octa_app] ✅ ready")