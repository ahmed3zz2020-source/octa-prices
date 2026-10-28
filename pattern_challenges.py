# -*- coding: utf-8 -*-
"""🎯 تحدي اليوم — تحدٍ يومي بلوحة متصدرين (٢٨ أكتوبر ٢٠٢٦)

📌 الفكرة: كل يوم تحدٍ واحد مبني على **شموع يومية حقيقية** من محرك
   الأنماط: levels (دخول/وقف/هدف) + سؤال «صعود ولا هبوط؟» + تصويت
   + لوحة متصدرين بالنقاط.

⛔ القواعد الحمرا (مفيش استثناء):
   · **مفيش look-ahead**: مستويات التحدي بتتبني من شموع **يوم D بس**
     (نقصّ السلسلة عند D ونشغّل الكاشف على الناقص) ⇒ والقرار بيتحسب
     من شموع **بعد D بس**.
   · **مفيش اختراع**: لو الشموع ناقصة ⇒ `pending` + سبب مكتوب.
   · **مفيش است regia**: نقطة واحدة = إجابة صحيحة. غلط = 0. متعادل = 0.
   · **الخصوصية**: لوحة المتصدرين بتعرض اسم مستعار مقنّع بس
     (أول حرفين) — ممنوع إيميل كامل أو uid.
   · **لوحة فاضية = لوح فاشل**: تحت ٣ مصوّتين ⇒ المتصدرين مقفولين.

📌 التخزين: ملفان في `DATA_DIR` (نفس نمط pattern_studio):
   · `challenges.json`      ⇒ {"challenges": {id: {...}}, "meta": {...}}
   · `challenge_votes.json` ⇒ {"votes": {id: {uid: {vote, at}}}}

⛔ مافيش print جوّه دوال المكتبة (الـlogging في الطبقة الأعلى).
"""
import json
import os
import threading
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
DATA_DIR = Path(os.environ.get("OCTA_DATA_DIR", "/data"))
try:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    (DATA_DIR / ".probe_challenges").write_text("1", encoding="utf-8")
except Exception:
    DATA_DIR = HERE
CHALLENGES_FILE = DATA_DIR / "challenges.json"
VOTES_FILE = DATA_DIR / "challenge_votes.json"

HORIZON = 10          # جلسات بعد يوم التوليد
STOP_ATR = 1.0        # الوقف = حافة المنطقة ± ١ ATR (نفس قاعدة الإنتاج)
TARGET_ATR = 4.0      # الهدف = الدخول ± ٤ ATR
BACKFILL_DAYS = 7     # كام يوم محفوظ مسبقاً (عشان اللعبة تبدأ فيها نقط)
MIN_LEADERBOARD = 3   # أقل من ٣ مصوّتين ⇒ المتصدرين مقفولين
POINT_CORRECT = 1
POINT_WRONG = 0
POINT_NEUTRAL = 0
MAX_VOTES_PER_USER = 400

QUESTION_AR = ("خلال ١٠ جلسات: هل يوصل السعر للهدف قبل ما يلمس الوقف؟")
QUESTION_AR_ALT = ("هدف ولا وقف — أيهم ييجي الأول خلال ١٠ جلسات؟")


# ══════════════════════════════════════════════════════════════
# تخزين
# ══════════════════════════════════════════════════════════════
def _read_json(path, default):
    try:
        if not path.exists():
            return default
        data = json.loads(path.read_text(encoding="utf-8"))
        return data if isinstance(data, type(default)) else default
    except Exception:
        return default


def _write_json(path, data):
    try:
        tmp = path.with_suffix(".tmp")
        tmp.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
        tmp.replace(path)
        return True
    except Exception:
        return False


def _challenges():
    return _read_json(CHALLENGES_FILE, {"challenges": {}, "meta": {}})


def _votes():
    return _read_json(VOTES_FILE, {"votes": {}})


def _save_challenges(data):
    return _write_json(CHALLENGES_FILE, data)


def _save_votes(data):
    return _write_json(VOTES_FILE, data)


# ══════════════════════════════════════════════════════════════
# أدوات
# ══════════════════════════════════════════════════════════════
def _alias(user):
    """👤 اسم مستعار مقنّع — مافيش إيميل ولا uid.

    📌 أول حرفين من الاسم، أو من بداية الإيميل لو الاسم فاضي.
    ⛔ ممنوع أي معرّف كامل.
    """
    try:
        u = user or {}
        name = str(u.get("name") or "").strip()
        src = name
        if not src:
            email = str(u.get("email") or "").strip()
            src = email.split("@")[0] if email else ""
        src = src.strip()
        if not src:
            return "مستخدم"
        return src[:2] + "…"
    except Exception:
        return "مستخدم"


def _last_index_le(bars, date_str):
    """آخر فهرس بشمعة تاريخها <= date_str (-1 لو مفيش)."""
    try:
        idx = -1
        for i, b in enumerate(bars):
            if str(b.get("d") or "") <= str(date_str or ""):
                idx = i
            else:
                break
        return idx
    except Exception:
        return -1


def _opp(direction):
    return "down" if direction == "up" else "up"


def _outcome_ar(outcome):
    if outcome == "up":
        return "صعود"
    if outcome == "down":
        return "هبوط"
    return "متعادل"


# ══════════════════════════════════════════════════════════════
# ⭐ التوليد — بلا look-ahead
# ══════════════════════════════════════════════════════════════
def generate_for_date(date_str, codes=None, max_codes=None, universe=None,
                      bars_by_code=None):
    """يبني تحدي واحد لتاريخ بيانات معيّن.

    ⭐ الفكرة: التحدي = **أقرب مستوى مهم قدام السعر** (مقاومة أو دعم)
       من محرك المناطق — مش كسر قديم. السؤال: «خلال ١٠ جلسات، هل يوصل
       الهدف قبل ما يلمس الوقف؟»

    ⛔ مفيش look-ahead: السلسلة بتتقصّ عند `date_str` ⇒ المنطقة والـATR
       بيتحسبوا من البيانات المتاحة وقت D بس.
    ⛔ مافيش كسر لازم يتأكد ⇒ مافيش مشكلة «آخر شمعة» (الكسر في آخر
       شمعة مش بيتأكد أصلاً).
    """
    try:
        import pattern_daily as pday
        import pattern_zones as pz
    except Exception:
        return None, "محرك المناطق مش متاح"
    try:
        import radar_api
    except Exception:
        radar_api = None

    try:
        uni = universe if universe is not None else pday._load_universe()
        if not uni:
            return None, "قائمة الأسهم غير متاحة"
        codes = list(codes) if codes else sorted(uni.keys())
        if max_codes:
            codes = codes[:int(max_codes)]
        # ⛔ seam للاختبارات: نقدر ن inject شموع وهمية (مفيش شبكة)
        if bars_by_code is not None:
            got = bars_by_code
            failed = []
        elif radar_api is not None:
            got, failed = radar_api.history_for(codes, n=320)
        else:
            got, failed = {}, []
        if not got:
            return None, "مفيش شموع (%d فشل)" % len(failed or [])
    except Exception as e:
        return None, "تعذّر جلب الشموع: %s" % str(e)[:120]

    best = None
    for code in sorted(got.keys()):
        try:
            raw = got.get(code)
            if bars_by_code is not None:
                bars = list(raw) if isinstance(raw, list) else []
            else:
                bars = pday._cols_to_bars(raw)
            idx = _last_index_le(bars, date_str)
            if idx < 60:
                continue
            # ⛔ القصّ = نقطة الأمان: المنطقة والـATR من لحد D بس
            trunc = bars[:idx + 1]
            zres = pz.detect_zones(trunc, code=code)
            if not zres or zres.get("status") != "ok":
                continue
            atr = zres.get("atr")
            entry = zres.get("price")
            if not atr or not entry or atr <= 0:
                continue
            entry = float(entry)
            atr = float(atr)
            meta = uni.get(code) or {}
            # ⭐Levels = أقرب مقاومة (فوق) + أقرب دعم (تحت)
            #   السؤال: مين يُلمس الأول خلال ١٠ جلسات؟
            #   · الهدف = المستوى الأقرب (المقاومة لو فوق، الدعم لو تحت)
            #   · الوقف = المستوى المقابل (تحت أو فوق)
            #   ⛔ الوقف لازم يكون على عكس الهدف عن الدخول — عشان
            #      معنى «لمس الوقف» يبقى صحيح من أول شمعة.
            # ⭐ أقرب مقاومة فوق + أقرب دعم تحت (محرك المناطق بيحسبهم)
            res_z = zres.get("nearest_resistance")
            sup_z = zres.get("nearest_support")
            if not res_z or not sup_z:
                continue
            try:
                res_z = dict(res_z); sup_z = dict(sup_z)
                res_z["level"] = float(res_z.get("level"))
                sup_z["level"] = float(sup_z.get("level"))
            except Exception:
                continue
            if not res_z["level"] or not sup_z["level"]:
                continue
            d_res = abs(res_z["level"] - entry)
            d_sup = abs(sup_z["level"] - entry)
            if d_res <= d_sup:
                direction = "up"
                target = res_z["level"]
                stop = sup_z["level"]
                zone = res_z
                other = sup_z
            else:
                direction = "down"
                target = sup_z["level"]
                stop = res_z["level"]
                zone = sup_z
                other = res_z
            if target == entry or stop == entry:
                continue
            # ⛔ الوقف لازم عكس الهدف عن الدخول
            if (direction == "up" and not (stop < entry < target)) or \
               (direction == "down" and not (target < entry < stop)):
                continue
            risk = abs(entry - stop)
            if risk <= 0.3 * atr:
                continue
            rr = abs(target - entry) / risk
            dist_atr = abs(target - entry) / atr
            # ⛔ لازم السؤال يكون **متوازن**: المسافة ≤ ٣ ATR والعائد
            #    بين ٠٫٧ و ١٫٦ (لو الهدف أبعد بكتير ⇒ السؤال بيلفّ favor)
            if dist_atr > 3.0 or rr < 0.7 or rr > 1.6:
                continue
            cand = {
                "code": code,
                "name": meta.get("name") or code,
                "sector": meta.get("sector"),
                "date": str(date_str),
                "direction": direction,
                "entry": round(entry, 4),
                "level": round(target, 4),
                "stop": round(stop, 4),
                "target": round(target, 4),
                "rr": round(rr, 2),
                "atr": round(atr, 4),
                "atr_pct": round(atr / entry * 100.0, 2) if entry else None,
                "zone_low": zone.get("zone_low"),
                "zone_high": zone.get("zone_high"),
                "zone_kind": zone.get("kind"),
                "zone_label": zone.get("label"),
                "other_kind": other.get("kind"),
                "other_level": round(other["level"], 4),
                "distance_pct": zone.get("distance_pct"),
                "distance_atr": zone.get("distance_atr"),
                "touches": zone.get("touches"),
                "zone_score": zone.get("score"),
                "last_test": zone.get("last_test"),
                "source": "startamarkets",
            }
            # ⭐ الاختيار: الأقرب فATR (السؤال الأهم) ⇒ والباقي بالرمز
            key = (-round(dist_atr, 4), round(rr, 4))
            if best is None or key > best[0]:
                best = (key, cand)
        except Exception:
            continue

    if not best:
        return None, "مفيش مستوى صالح في تاريخ %s" % date_str
    cand = best[1]
    cid = "CH-%s-%s" % (cand["date"], cand["code"])
    cand["id"] = cid
    cand["question_ar"] = QUESTION_AR
    cand["status"] = "open"
    cand["resolved"] = None
    cand["created_at"] = int(time.time())
    cand["votes_count"] = 0
    return cand, None


def _bars_after(cand, bars, limit=HORIZON):
    """الشموع **بعد** يوم D (يعني بيانات الحل فقط)."""
    try:
        idx = _last_index_le(bars, cand.get("date"))
        if idx < 0:
            return []
        return bars[idx + 1: idx + 1 + int(limit)]
    except Exception:
        return []


def resolve_challenge(cand, bars):
    """يحسب نتيجة التحدي من الشموع **بعد** يوم التوليد.

    ⛔ مافيش نتيجة من غير شموع ⇒ `pending` + سبب.
    """
    try:
        if not cand:
            return None, "مفيش تحدي"
        if cand.get("resolved"):
            return cand["resolved"], None
        after = _bars_after(cand, bars)
        if len(after) < HORIZON:
            return None, "لسه مفيش %d جلسات بعد يوم التوليد (%d بس)" % (HORIZON, len(after))
        direction = cand.get("direction") or "up"
        entry = float(cand.get("entry") or 0)
        target = float(cand.get("target") or 0)
        stop = float(cand.get("stop") or 0)
        if not entry or not target or not stop:
            return None, "المستويات ناقصة"
        for b in after:
            hi = float(b.get("h") or 0)
            lo = float(b.get("l") or 0)
            if direction == "up":
                hit_target = hi >= target
                hit_stop = lo <= stop
            else:
                hit_target = lo <= target
                hit_stop = hi >= stop
            if hit_target and hit_stop:
                return ({"outcome": "neutral", "reason": "الشمعة لمست المستويين مع بعض",
                         "resolved_at": int(time.time()), "hit_at": b.get("d")}), None
            if hit_target:
                return ({"outcome": direction, "reason": "الهدف اتلمس قبل الوقف",
                         "resolved_at": int(time.time()), "hit_at": b.get("d")}), None
            if hit_stop:
                return ({"outcome": _opp(direction), "reason": "الوقف اتلمس قبل الهدف",
                         "resolved_at": int(time.time()), "hit_at": b.get("d")}), None
        return ({"outcome": "neutral", "reason": "مفيش لمس خلال %d جلسات" % HORIZON,
                 "resolved_at": int(time.time()), "hit_at": None}), None
    except Exception as e:
        return None, "تعذّر حساب النتيجة: %s" % str(e)[:100]


def refresh(resolve=True, backfill=BACKFILL_DAYS, max_codes=None):
    """بيعيد بناء التحديات (الحالي + كم يوم سابق) وبيحلّ اللي اتحل.

    ⛔ آمن للاستدعاء المتكرر: التحدي المحفوظ بنفس التاريخ ما بيتغيرش.
    """
    try:
        import pattern_daily as pday
        import radar_api
    except Exception as e:
        return {"ok": False, "error": str(e)[:120]}
    try:
        uni = pday._load_universe()
        codes = sorted(uni.keys())
        got, failed = radar_api.history_for(codes, n=320)
        if not got:
            return {"ok": False, "error": "مفيش شموع"}
        # ⭐ آخر جلسة متاحة في البيانات (مش تاريخ النظام)
        last_dates = []
        for code in got:
            bars = pday._cols_to_bars(got.get(code))
            if bars:
                last_dates.append(str(bars[-1]["d"]))
        if not last_dates:
            return {"ok": False, "error": "مفيش تواريخ"}
        last_d = max(last_dates)
        # ⭐ التواريخ المتاحة (تنازلي)
        all_dates = set()
        for code in got:
            for b in pday._cols_to_bars(got.get(code)):
                all_dates.add(str(b.get("d")))
        past = sorted([d for d in all_dates if d <= last_d], reverse=True)
        target_dates = past[:max(1, int(backfill))]

        data = _challenges()
        store = data.get("challenges") or {}
        created = 0
        for d in target_dates:
            cid_exists = any(k.startswith("CH-%s-" % d) for k in store.keys())
            if cid_exists:
                continue
            cand, err = generate_for_date(d, codes=codes, universe=uni)
            if not cand:
                continue
            store[cand["id"]] = cand
            created += 1
        # ⭐ حلّ اللي culminated
        resolved = 0
        if resolve:
            for cid, ch in list(store.items()):
                if ch.get("resolved"):
                    continue
                bars = pday._cols_to_bars(got.get(ch.get("code")))
                if not bars:
                    continue
                res, err = resolve_challenge(ch, bars)
                if res:
                    ch["resolved"] = res
                    ch["status"] = "resolved"
                    resolved += 1
        data["challenges"] = store
        data["meta"] = {"updated_at": int(time.time()), "last_data_date": last_d}
        _save_challenges(data)
        # ⭐ عدّ المصوّتين
        votes = _votes().get("votes") or {}
        for cid, ch in store.items():
            ch["votes_count"] = len(votes.get(cid) or {})
        _save_challenges(data)
        return {"ok": True, "created": created, "resolved": resolved,
                "total": len(store), "last_data_date": last_d}
    except Exception as e:
        return {"ok": False, "error": str(e)[:160]}


# ══════════════════════════════════════════════════════════════
# ⭐ الحسابات (نقاط/دقة/رتبة)
# ══════════════════════════════════════════════════════════════
def _is_correct(ch, vote):
    try:
        res = ch.get("resolved") or {}
        outcome = res.get("outcome")
        if not outcome or outcome == "neutral":
            return None
        return (vote == outcome)
    except Exception:
        return None


def user_stats(uid, store, votes):
    """إحصاءات مستخدم واحد: نقاط · صح · غلط · متعادل · دقة · سلسلة."""
    mine = {}
    for cid, per_user in (votes or {}).items():
        rec = per_user.get(uid) if isinstance(per_user, dict) else None
        if rec and rec.get("vote"):
            mine[cid] = rec
    correct = wrong = neutral = 0
    for cid, rec in mine.items():
        ch = (store or {}).get(cid) or {}
        ok = _is_correct(ch, rec.get("vote"))
        if ok is None:
            neutral += 1
        elif ok:
            correct += 1
        else:
            wrong += 1
    # ⭐ السلسلة:_correct متتالية من الأحدث
    seq_sorted = sorted(mine.keys(), key=lambda c: str((store or {}).get(c, {}).get("date") or ""))
    streak = 0
    for cid in reversed(seq_sorted):
        ok = _is_correct((store or {}).get(cid) or {}, mine[cid].get("vote"))
        if ok:
            streak += 1
        else:
            break
    decided = correct + wrong
    accuracy = (round(correct / float(decided), 4) if decided else None)
    return {
        "points": correct * POINT_CORRECT + wrong * POINT_WRONG + neutral * POINT_NEUTRAL,
        "correct": correct,
        "wrong": wrong,
        "neutral": neutral,
        "votes": len(mine),
        "accuracy": accuracy,
        "streak": streak,
        "rank": None,
        "days_played": len([c for c in mine if (store or {}).get(c)]),
    }


def leaderboard(store, votes, user_getter=None, limit=50, me_uid=None):
    """لوحة المتصدرين — أسماء مقنّعة بس.

    ⛔ ممنوع إيميل كامل أو uid في النتيجة.
    ⛔ أقل من ٣ مصوّنين ⇒ `hidden` (لوح فاشل أفضل منه لوح فاضي).
    """
    totals = {}
    voters = set()
    for cid, per_user in (votes or {}).items():
        for uid, rec in (per_user or {}).items():
            if not isinstance(rec, dict) or not rec.get("vote"):
                continue
            voters.add(uid)
            ch = (store or {}).get(cid) or {}
            ok = _is_correct(ch, rec.get("vote"))
            if ok is None:
                continue
            t = totals.setdefault(uid, {"points": 0, "correct": 0, "wrong": 0, "neutral": 0})
            if ok:
                t["points"] += POINT_CORRECT
                t["correct"] += 1
            else:
                t["points"] += POINT_WRONG
                t["wrong"] += 1
    if len(voters) < MIN_LEADERBOARD:
        return {"status": "hidden", "reason": "اللوحة بتتفتح بعد %d مصوّتين" % MIN_LEADERBOARD,
                "rows": [], "voters": len(voters)}
    rows = []
    for uid, t in totals.items():
        u = None
        if user_getter:
            try:
                u = user_getter(uid)
            except Exception:
                u = None
        decided = t["correct"] + t["wrong"]
        rows.append({
            "uid_key": uid,           # ⛔ بيتشال قبل الإرسال
            "alias": _alias(u),
            "points": t["points"],
            "correct": t["correct"],
            "wrong": t["wrong"],
            "accuracy": (round(t["correct"] / float(decided), 4) if decided else None),
        })
    rows.sort(key=lambda r: (-r["points"], -(r["accuracy"] or 0), -r["correct"], r["alias"]))
    my_rank = None
    for i, r in enumerate(rows, 1):
        if me_uid and r.get("uid_key") == me_uid:
            my_rank = i
    out = []
    for i, r in enumerate(rows[:int(limit)], 1):
        r = dict(r)
        r.pop("uid_key", None)
        r["rank"] = i
        out.append(r)
    return {"status": "ok", "rows": out, "voters": len(voters), "my_rank": my_rank}


# ══════════════════════════════════════════════════════════════
# ⭐ التسجيل والمسارات
# ══════════════════════════════════════════════════════════════
_BUILD = {"on": False, "last": 0.0}
_LOCK = threading.Lock()


def _bg_refresh():
    with _LOCK:
        if _BUILD["on"]:
            return False
        _BUILD["on"] = True

    def _run():
        try:
            refresh()
        except Exception:
            pass
        finally:
            _BUILD["on"] = False

    try:
        threading.Thread(target=_run, daemon=True).start()
        return True
    except Exception:
        _BUILD["on"] = False
        return False


def _open_challenges(store):
    """التحديات المفتوحة (لسه ما اتحلّتش) — الأحدث الأول."""
    out = []
    for cid, ch in (store or {}).items():
        if ch.get("resolved"):
            continue
        out.append(ch)
    out.sort(key=lambda c: (str(c.get("date") or ""), str(c.get("code") or "")), reverse=True)
    return out


def register(app, require_user=None, plan_checker=None, user_getter=None,
             universe=None):
    """🎯 مسارات تحدي اليوم + لوحة المتصدرين (محمية بالباقة)."""
    from flask import jsonify, request

    def _plan_of(user):
        try:
            if plan_checker:
                p = plan_checker(user)
                if p:
                    return str(p)
        except Exception:
            pass
        return str((user or {}).get("plan") or "free")

    def _locked(user=None):
        return jsonify({"ok": False, "locked": True, "plan": _plan_of(user),
                        "error": "باقة «نماذجي» مدفوعة — محتاجة تفعيل"}), 403

    def _current(store):
        """التحدي الحالي = الأحدث مفتوح."""
        opens = _open_challenges(store)
        return opens[0] if opens else None

    @app.route("/api/challenges/today", methods=["GET"])
    def challenges_today():
        """🎯 تحدي اليوم + إحصاءاتك."""
        u = require_user() if require_user else None
        if require_user is not None and not u:
            return jsonify({"ok": False, "error": "لازم تسجّل دخول"}), 401
        if _plan_of(u) != "pro":
            return _locked(u)
        data = _challenges()
        store = data.get("challenges") or {}
        votes = _votes().get("votes") or {}
        ch = _current(store)
        # ⛔ مفيش تحدي ⇒ نعيد بناء في الخلفية (مرة واحدة كل ٥ دقايق)
        if not ch:
            if time.time() - _BUILD["last"] > 300:
                _BUILD["last"] = time.time()
                _bg_refresh()
            return jsonify({"ok": True, "challenge": None, "open": [],
                            "status": "no_challenge",
                            "reason": "مفيش تحدي دلوقتي — بنجهّز واحد من شموع اليوم",
                            "me": user_stats((u or {}).get("uid") or "", store, votes)})
        mine = (votes.get(ch.get("id")) or {}).get((u or {}).get("uid") or "") or {}
        out = dict(ch)
        out["my_vote"] = mine.get("vote")
        out["outcome_ar"] = _outcome_ar((ch.get("resolved") or {}).get("outcome"))
        return jsonify({"ok": True, "challenge": out,
                        "open": [{"id": c.get("id"), "date": c.get("date"),
                                   "code": c.get("code"), "name": c.get("name"),
                                   "direction": c.get("direction"),
                                   "resolved": bool(c.get("resolved"))}
                                  for c in _open_challenges(store)][:8],
                        "status": "ok",
                        "me": user_stats((u or {}).get("uid") or "", store, votes)})

    @app.route("/api/challenges/vote", methods=["POST"])
    def challenges_vote():
        """🗳️ تصويت على تحدي (صعود/هبوط)."""
        u = require_user() if require_user else None
        if require_user is not None and not u:
            return jsonify({"ok": False, "error": "لازم تسجّل دخول"}), 401
        if _plan_of(u) != "pro":
            return _locked(u)
        try:
            body = request.get_json(silent=True) or {}
        except Exception:
            body = {}
        if not isinstance(body, dict):
            body = {}
        vote = str(body.get("vote") or "").strip().lower()
        key = str(body.get("code") or body.get("challenge_id") or "").strip()
        if vote not in ("up", "down"):
            return jsonify({"ok": False, "error": " vote لازم يكون up أو down"}), 400
        if not key:
            return jsonify({"ok": False, "error": "محتاج كود التحدي"}), 400
        uid = str((u or {}).get("uid") or "")
        if not uid:
            return jsonify({"ok": False, "error": "مفيش مستخدم"}), 401
        data = _challenges()
        store = data.get("challenges") or {}
        cid = None
        for k, c in (store or {}).items():
            if k == key or str(c.get("code") or "") == key:
                cid = k
                break
        if not cid:
            return jsonify({"ok": False, "error": "مفيش تحدي بالكود ده"}), 404
        ch = store.get(cid) or {}
        if ch.get("resolved"):
            return jsonify({"ok": False, "error": "التحدي ده اتحل خلاص"}), 409
        votes_data = _votes()
        votes = votes_data.get("votes") or {}
        per = votes.setdefault(cid, {})
        if uid not in per and len(per) > MAX_VOTES_PER_USER:
            return jsonify({"ok": False, "error": "الحد الأقصى للتصويت اتملا"}), 400
        per[uid] = {"vote": vote, "at": int(time.time()),
                    "alias": _alias(u)}
        votes_data["votes"] = votes
        if not _save_votes(votes_data):
            return jsonify({"ok": False, "error": "تعذّر حفظ التصويت"}), 500
        ch["votes_count"] = len(per)
        store[cid] = ch
        data["challenges"] = store
        _save_challenges(data)
        return jsonify({"ok": True, "challenge_id": cid, "my_vote": vote})

    @app.route("/api/challenges/leaderboard", methods=["GET"])
    def challenges_leaderboard():
        """🏆 لوحة المتصدرين (أسماء مقنّعة بس)."""
        u = require_user() if require_user else None
        if require_user is not None and not u:
            return jsonify({"ok": False, "error": "لازم تسجّل دخول"}), 401
        if _plan_of(u) != "pro":
            return _locked(u)
        data = _challenges()
        store = data.get("challenges") or {}
        votes = _votes().get("votes") or {}
        uid = str((u or {}).get("uid") or "")
        lb = leaderboard(store, votes, user_getter=user_getter, me_uid=uid)
        me = user_stats(uid, store, votes)
        rows = lb.get("rows") or []
        rank = lb.get("my_rank")
        return jsonify({"ok": True, "status": lb.get("status"),
                        "reason": lb.get("reason"),
                        "rows": rows,
                        "voters": lb.get("voters"),
                        "me": {"rank": rank, "points": me.get("points"),
                               "accuracy": me.get("accuracy"),
                               "correct": me.get("correct"),
                               "wrong": me.get("wrong"),
                               "streak": me.get("streak"),
                               "votes": me.get("votes")}})

    return True
