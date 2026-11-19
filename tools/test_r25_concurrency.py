#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
👥 الجولة ٢٥ (R25 · المرحلة ٩) — عاملان صناعيان + تعافّي بعد إعادة التشغيل

📌 بنود القبول المستهدفة ⭐:
   · **AC-10-3** ⭐: «تحميل صناعي متزامن من عاملين ثم إعادة تشغيل
     ومقارنة الحالة المرجعية» ⭐
   · **AC-12-3** ⭐: «عاملان صناعيان، فشل مهمة ثم restart؛ تحقق من
     idempotency وأقفال البيانات» ⭐

📌 القياسات ⭐:
   ① عاملان حقيقيان ⭐ على **نفس مجلد البيانات** ⭐ (زي workers حقيقيين ⭐)
      ⇒ حمل متزامن ⭐ + قياس ⭐ + حالة مشتركة ⭐.
   ② **انتخاب القائد** ⭐ — واحد بس هو اللي يشغّل المهام الخلفية ⭐
      (قفل ملف على القرص ⭐ ⇒ idempotency ⭐).
   ③ **التعافي بعد إعادة التشغيل** ⭐ — القائد اتقتل ⭐ ⇒ القفل اتفك ⭐
      ⇒ عامل جديد بقى القائد ⭐ ⇒ المهام الخلفية رجعت ⭐.
   ④ **أقفال البيانات** ⭐ — كتابة متزامنة ⭐ ⇒ الملف مايتلخبطش ⭐
      + قياس الفقد المتبقي ⭐ (رقم حقيقي ⭐ مش مخترع ⭐).

⛔⛔⛔ العزل ⬇️ ⬇️ ⬇️
   ⛔ كل الـworkers على `127.0.0.1` ⭐ في مجلد مؤقّت ⭐
   ⛔ مافيش أي اتصال خارجي ⭐ · مافيش أي سر إنتاج ⭐ · مافيش نشر ⭐

📌 التشغيل: python3 tools/test_r25_concurrency.py
   📌 وكل ملف اختبار كمان بيشتغل تحت `pytest` ⭐.
"""
import atexit
import functools
import json
import shutil
import sys
import threading
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE / "staging"))

import iso_env as iso  # noqa: E402

# ══════════════════════════════════════════════════════════════════
#  🧰 بيئة الاختبار ⭐
# ══════════════════════════════════════════════════════════════════
_CLEANUP = []
RESULTS = []
REPORT = {}

LOAD_THREADS = 6
LOAD_EACH = 20
WRITE_THREADS = 6
WRITE_EACH = 5

LEADER_MARK = "هي القائد"
FOLLOWER_MARK = "القفل محجوز"


def _launch(tag, stage_dir=None, **kw):
    stage = Path(stage_dir or ("/tmp/octa_r25_conc_%s" % tag))
    srv = iso.launch(stage_dir=str(stage), **kw)
    ok, elapsed = srv.wait_ready(timeout=240)
    if not ok:
        tail = "\n".join(srv.log_tail(30))
        srv.stop()
        raise RuntimeError("السيرفر المعزول ماقومش:\n" + tail)
    _CLEANUP.append(srv)
    return srv


def _cleanup():
    for srv in list(_CLEANUP):
        try:
            srv.stop()
        except Exception:
            pass


atexit.register(_cleanup)


def ok(cond, label, extra=""):
    RESULTS.append((bool(cond), label))
    print(("  ✅ " if cond else "  ❌ ") + label +
          (("  — " + str(extra)) if extra else ""), flush=True)
    return bool(cond)


def _case(fn):
    """⛔ غلاف يتوافق مع `pytest` ⭐.

    📌 السبب ⭐: تحت `pytest` ⭐ لازم الاختبار **يفشل** ⭐
    📌 لو فيه أي assertion مش عدى ⭐ ⇒ عشان `pytest` يبلّغ ⭐.
    📌 والاسترجاع (standalone ⭐) بيفضل يطبع كل الإخفاقات ⭐
    📌 لأن الاستثناء بيترمي **بعد** ما الدالة تخلص ⭐.
    """
    @functools.wraps(fn)
    def wrapper(*args, **kwargs):
        before = len(RESULTS)
        completed = False
        try:
            fn(*args, **kwargs)
            completed = True
        finally:
            if completed:
                bad = [r[1] for r in RESULTS[before:] if not r[0]]
                if bad:
                    raise AssertionError(
                        "%d إخفاق ⭐: %s" % (len(bad), " · ".join(bad[:3])))
    return wrapper


def section(title):
    print("\n" + "─" * 70)
    print("  " + title)
    print("─" * 70, flush=True)


def _client(srv, ip):
    c = iso.Client(srv.base_url, srv.proxy_secret, client_ip=ip)
    cfg = iso.read_stage_cfg(srv.stage_dir)
    tok, st, j = c.login(cfg["free"]["pin"], cfg["free"]["device"])
    if not tok:
        raise RuntimeError("فشل الدخول بالحساب الوهمي (%s · %s)"
                           % (st, str(j)[:120]))
    return c


def _login_token(srv):
    """🔑 توكن واحد ⭐ — بيشاركه كل الـthreads ⭐."""
    cfg = iso.read_stage_cfg(srv.stage_dir)
    c = iso.Client(srv.base_url, srv.proxy_secret, client_ip="198.51.100.55")
    tok, st, j = c.login(cfg["free"]["pin"], cfg["free"]["device"])
    c.close()
    if not tok:
        raise RuntimeError("فشل الدخول بالحساب الوهمي (%s · %s)"
                           % (st, str(j)[:120]))
    return tok


def _leaders(srv):
    """👑 بيرجّع (عدد القادة · عدد التابعين) ⭐ من لوج السيرفر ⭐."""
    text = "\n".join(srv.log_tail(400))
    return text.count(LEADER_MARK), text.count(FOLLOWER_MARK)


def _users_file(srv):
    return Path(srv.stage_dir) / "users.json"


def _load_users(srv):
    try:
        return json.loads(_users_file(srv).read_text(encoding="utf-8"))
    except Exception:
        return None


def _stable_users(users):
    """🧷 الحقول **الثابتة** من الحسابات ⭐ (مقارنة الحالة المرجعية ⭐)."""
    out = {}
    for uid, rec in (users or {}).items():
        out[str(uid)] = {
            "email": rec.get("email"),
            "plan": rec.get("plan"),
            "id": rec.get("id"),
            "name": rec.get("name"),
        }
    return out


def _codes(srv, c, want):
    """🔎 أكواد حقيقية ⭐ (من البيانات الغنية ⭐)."""
    st, _h, b, _ms = c.get("/api/data_full")
    try:
        d = json.loads(b.decode("utf-8"))
    except Exception:
        return []
    stocks = d.get("stocks") or {}
    keys = sorted(stocks.keys()) if isinstance(stocks, dict) else []
    return keys[:want]


# ══════════════════════════════════════════════════════════════════
#  ⛔ فحص الحماية ⭐ — انLeadership ⭐
# ══════════════════════════════════════════════════════════════════
def _leader_failures(servers, label):
    """⛔ بيرجّع قائمة الإخفاقات ⭐ — نفس الفحص في كل الحالات ⭐."""
    fails = []
    total_leaders = 0
    for srv in servers:
        leaders, _followers = _leaders(srv)
        total_leaders += leaders
    if total_leaders != 1:
        fails.append("%s: عدد القادة=%s بدل 1 ⭐ (المهام الخلفية هتتكرر ⭐)"
                     % (label, total_leaders))
    return fails


# ══════════════════════════════════════════════════════════════════
#  ① عاملان + حمل متزامن ⭐
# ══════════════════════════════════════════════════════════════════
@_case
def test_concurrency_two_workers_shared_state():
    """① عاملان على نفس مجلد البيانات + حمل متزامن ⭐."""
    section("① عاملان صناعيان على نفس مجلد البيانات")
    stage = "/tmp/octa_r25_conc_shared"
    shutil.rmtree(stage, ignore_errors=True)
    a = _launch("A", stage_dir=stage, source_mode="ok")
    b = _launch("B", stage_dir=stage, source_mode="ok")
    ok(a.stage_dir == b.stage_dir,
       "①a العاملان على نفس مجلد البيانات ⭐", a.stage_dir)

    time.sleep(2.0)
    la, fa = _leaders(a)
    lb, fb = _leaders(b)
    print("   القادة: A=%d B=%d · التابعين: A=%d B=%d ⭐"
          % (la, lb, fa, fb), flush=True)
    ok(la + lb == 1,
       "①b واحد بس هو القائد ⭐ (المهام الخلفية مابتتكررش ⭐)",
       "A=%d B=%d" % (la, lb))
    ok(fa + fb >= 1,
       "①c العامل التاني اتمنع ⭐ (القفل محجوز ⭐)",
       "A=%d B=%d" % (fa, fb))

    before = _users_file(a).read_bytes()
    ok(len(before) > 0, "①d فيه حالة مرجعية ⭐", len(before))
    ref_before = _stable_users(_load_users(a))

    tokens = {"a": _login_token(a), "b": _login_token(b)}
    per_worker = {}
    lock = threading.Lock()
    errors = []

    def worker(idx):
        srv = a if idx % 2 == 0 else b
        c = iso.Client(srv.base_url, srv.proxy_secret,
                       client_ip="198.51.100.%d" % (60 + idx))
        c.token = tokens["a" if srv is a else "b"]
        n = 0
        for i in range(LOAD_EACH):
            path = "/api/data_full" if i % 3 == 0 else "/api/ranking"
            try:
                st, _h, _b, ms = c.get(path)
            except Exception as exc:
                with lock:
                    errors.append("%s: %s" % (path, type(exc).__name__))
                continue
            if st >= 500:
                with lock:
                    errors.append("%s: %s" % (path, st))
                continue
            n += 1
        with lock:
            per_worker[idx] = n

    t0 = time.perf_counter()
    threads = [threading.Thread(target=worker, args=(i,))
               for i in range(LOAD_THREADS)]
    for t in threads:
        t.start()
    for t in threads:
        t.join(timeout=300)
    wall = time.perf_counter() - t0
    total = sum(per_worker.values())
    print("   حمل: %d طلب في %.2fs ⭐ (توزيع: %s)"
          % (total, wall, per_worker), flush=True)
    ok(not errors, "①e مفيش أخطاء في الحمل المتزامن ⭐", errors[:5])
    ok(total == LOAD_THREADS * LOAD_EACH,
       "①f كل الطلبات اتجاوبت (%d/%d) ⭐" % (total, LOAD_THREADS * LOAD_EACH))
    ok(len(per_worker) == LOAD_THREADS,
       "①g كل الـthreads اشتغلت ⭐", len(per_worker))
    ok(wall > 0, "①h زمن الحمل اتقاس ⭐", round(wall, 3))

    after = _users_file(a).read_bytes()
    ok(len(after) > 0, "①i ملف الحسابات لسه موجود ⭐", len(after))
    ok(_stable_users(_load_users(a)) == ref_before,
       "①i2 الحالة المرجعية (الحسابات) سليمة تحت الحمل ⭐ (مافيش فقد ⭐)")
    users = _load_users(a)
    ok(isinstance(users, dict) and len(users) >= 3,
       "①j ملف الحسابات سليم بعد الحمل ⭐", len(users or {}))
    REPORT["load"] = {"total": total, "wall": round(wall, 3),
                       "per_worker": per_worker}
    REPORT["leaders"] = {"A": la, "B": lb}
    return {"a": a, "b": b}


# ══════════════════════════════════════════════════════════════════
#  ② التعافي بعد إعادة التشغيل ⭐
# ══════════════════════════════════════════════════════════════════
@_case
def test_concurrency_background_task_recovery_after_restart():
    """② القائد اتقتل ⇒ القفل اتفك ⇒ عامل جديد بقى القائد ⭐."""
    section("② تعافي المهام الخلفية بعد إعادة تشغيل القائد")
    stage = "/tmp/octa_r25_conc_restart"
    shutil.rmtree(stage, ignore_errors=True)
    a = _launch("RA", stage_dir=stage, source_mode="ok")
    b = _launch("RB", stage_dir=stage, source_mode="ok")
    time.sleep(2.0)
    la, _fa = _leaders(a)
    lb, _fb = _leaders(b)
    ok(la + lb == 1, "②a اتحدد القائد ⭐", "A=%d B=%d" % (la, lb))
    leader = a if la >= 1 else b

    leader.stop(kill=True)
    down, elapsed = leader.wait_down(timeout=20)
    ok(down, "②b القائد اتوقف (إيقاف قاسٍ ⭐) ⭐", round(elapsed, 2))

    c = _launch("RC", stage_dir=stage, source_mode="ok")
    time.sleep(3.0)
    lc, fc = _leaders(c)
    print("   العامل الجديد C: قادة=%d تابعين=%d ⭐" % (lc, fc), flush=True)
    ok(lc == 1,
       "②c العامل الجديد بقى القائد ⭐ (القفل اتفك بعد الموت ⭐)", lc)
    ok(fc == 0, "②d مافيش مانع مع القائد الجديد ⭐", fc)

    users = _load_users(c)
    ok(isinstance(users, dict) and len(users) >= 3,
       "②e الحالة المرجعية سليمة بعد إعادة التشغيل ⭐", len(users or {}))
    cl = _client(c, "198.51.100.71")
    st, _h, _b, _ms = cl.get("/api/health", auth=False)
    ok(st == 200, "②f العامل الجديد بيخدم ⭐", st)
    REPORT["recovery"] = {"new_leaders": lc, "new_followers": fc}
    return c


# ══════════════════════════════════════════════════════════════════
#  ③ أقفال البيانات ⭐
# ══════════════════════════════════════════════════════════════════
def _concurrent_write_burst(srv, codes, tag):
    """⛔ عبء كتابة متزامن ⭐ + قارئ متزامن ⭐ ⭐

    ⛔ بيرجّع (إخفاقات · قراءات · قراءات تالفة ⭐) ⭐
    """
    reads = {"n": 0, "bad": 0}
    stop = threading.Event()
    errors = []
    lock = threading.Lock()

    def reader():
        while not stop.is_set():
            try:
                raw = _users_file(srv).read_bytes()
            except Exception:
                raw = b""
            reads["n"] += 1
            try:
                json.loads(raw.decode("utf-8"))
            except Exception:
                reads["bad"] += 1
            time.sleep(0.001)

    def writer(idx):
        cc = iso.Client(srv.base_url, srv.proxy_secret,
                        client_ip="198.51.100.%d" % (90 + idx))
        cc.token = tokens_global["tok"]
        for j in range(WRITE_EACH):
            code = codes[idx * WRITE_EACH + j]
            try:
                st, _h, _b, _ms = cc.post("/api/portfolio", {
                    "action": "add", "code": code,
                    "shares": 1 + j, "cost": 10.0 + j, "price": 12.0 + j,
                    "sector": "اختبار"})
                if st >= 400:
                    with lock:
                        errors.append("%s: %s" % (code, st))
            except Exception as exc:
                with lock:
                    errors.append("%s: %s" % (code, type(exc).__name__))
        cc.close()

    rt = threading.Thread(target=reader)
    rt.start()
    threads = [threading.Thread(target=writer, args=(i,))
               for i in range(WRITE_THREADS)]
    for t in threads:
        t.start()
    for t in threads:
        t.join(timeout=300)
    stop.set()
    rt.join(timeout=30)

    fails = []
    if errors:
        fails.append("%s: %d كتابة فشلت ⭐ (%s)"
                     % (tag, len(errors), errors[:3]))
    if reads["bad"] > 0:
        fails.append("%s: الملف اتقري ناقص %d مرة من %d ⭐"
                     % (tag, reads["bad"], reads["n"]))
    users = _load_users(srv)
    if not isinstance(users, dict):
        fails.append("%s: ملف users.json تالف ⭐" % tag)
    return fails, reads, errors


tokens_global = {"tok": None}


@_case
def test_concurrency_data_lock_keeps_file_intact():
    """③ كتابة متزامنة ⭐ ⇒ الملف مايتلخبطش ⭐ + قياس الفقد ⭐."""
    section("③ أقفال البيانات — كتابة متزامنة")
    stage = "/tmp/octa_r25_conc_writes"
    shutil.rmtree(stage, ignore_errors=True)
    srv = _launch("W", stage_dir=stage, source_mode="ok")
    c = _client(srv, "198.51.100.80")
    tokens_global["tok"] = c.token
    codes = _codes(srv, c, WRITE_THREADS * WRITE_EACH)
    ok(len(codes) >= WRITE_THREADS * WRITE_EACH,
       "③a اتجمعت الأكواد الحقيقية ⭐", len(codes))
    if len(codes) < WRITE_THREADS * WRITE_EACH:
        return {}

    fails, reads, errors = _concurrent_write_burst(srv, codes, "مع الحماية")
    ok(not fails, "③b الملف ما اتلخبطش أثناء الكتابة المتزامنة ⭐", fails)
    ok(reads["n"] > 0, "③c القارئ المتزامن قرأ الملف ⭐", reads)
    users = _load_users(srv)
    rec = (users or {}).get("stg_free_user") or {}
    holdings = (rec.get("portfolio") or {}).get("holdings") or {}
    want = WRITE_THREADS * WRITE_EACH
    lost = max(0, want - len(holdings))
    print("   الكتابات: %d · الموجود فعلياً: %d · المفقود: %d ⭐"
          % (want, len(holdings), lost), flush=True)
    print("   قراءات متزامنة: %d · منها تالف: %d ⭐"
          % (reads["n"], reads["bad"]), flush=True)
    ok(len(users or {}) >= 3, "③d الحسابات نفسها ماتفقدتش ⭐",
       len(users or {}))
    bak = Path(srv.stage_dir) / "users.bak"
    ok(bak.exists(), "③e فيه نسخة احتياطية (.bak) ⭐", bak.name)
    REPORT["writes"] = {"written": want, "present": len(holdings),
                        "lost": lost, "reads": reads["n"],
                        "bad_reads": reads["bad"]}
    return {"lost": lost, "reads": reads}


# ══════════════════════════════════════════════════════════════════
#  🧨 البرهان السالب ⭐
# ══════════════════════════════════════════════════════════════════
@_case
def test_concurrency_negative_proof_atomic_write_removed():
    """🧨 شيل الكتابة الذرّية ⇒ الملف بيتقري ناقص ⭐."""
    section("🧨 البرهان السالب — تعطيل الكتابة الذرّية")
    stage = "/tmp/octa_r25_conc_neg"
    shutil.rmtree(stage, ignore_errors=True)
    srv = _launch("N", stage_dir=stage, source_mode="ok")
    c = _client(srv, "198.51.100.85")
    tokens_global["tok"] = c.token
    codes = _codes(srv, c, WRITE_THREADS * WRITE_EACH)
    if len(codes) < WRITE_THREADS * WRITE_EACH:
        ok(False, "🧨a مفيش أكواد كفاية ⭐", len(codes))
        return {}

    # ① مع الحماية ⭐
    fails_on, reads_on, _e = _concurrent_write_burst(srv, codes, "مع الحماية")
    ok(len(fails_on) == 0,
       "🧨a مع الحماية: الفحص بيعدّي ⭐ (0 إخفاقات ⭐)", fails_on)

    # ② شيل الحماية ⭐ (كتابة مباشرة فوق الملف ⭐)
    st, _h, _b, _ms = c.post("/__harness__/fault",
                             {"kind": "atomic_off", "value": "off"})
    ok(st == 200, "🧨b العطل اتحقن ⭐", st)
    fails_off, reads_off, _e2 = _concurrent_write_burst(srv, codes,
                                                         "بدون حماية")
    print("   مع الحماية: قراءات=%d تالفة=%d ⭐"
          % (reads_on["n"], reads_on["bad"]), flush=True)
    print("   بدونها: قراءات=%d تالفة=%d ⭐"
          % (reads_off["n"], reads_off["bad"]), flush=True)
    print("   الإخفاقات مع الحماية=%d · بدونها=%d ⭐"
          % (len(fails_on), len(fails_off)), flush=True)
    ok(len(fails_off) > 0,
       "🧨c بدون الحماية: نفس الفحص **فشل** ⭐ (الاختبار حسّاس ⭐)",
       "expected failures>0 got %d" % len(fails_off))

    # ③ رجّع الحماية ⭐
    c.post("/__harness__/fault", {"kind": "atomic_off", "value": "on"})
    fails_back, reads_back, _e3 = _concurrent_write_burst(srv, codes,
                                                          "رجوع")
    ok(len(fails_back) == 0,
       "🧨d بعد رجوع الحماية: الفحص رجع يعدّي ⭐", fails_back)
    REPORT["negative_atomic"] = {"before": len(fails_off),
                                  "after": len(fails_on)}
    return {"before": len(fails_off), "after": len(fails_on)}


@_case
def test_concurrency_negative_proof_leader_lock_removed():
    """🧨 شيل قفل القائد ⇒ العاملان الاتنين يبقوا قادة ⭐."""
    section("🧨 البرهان السالب — تعطيل قفل انتخاب القائد")
    # ① مع الحماية ⭐ ⇒ عاملان على نفس المجلد ⇒ قائد واحد ⭐
    stage = "/tmp/octa_r25_conc_lead"
    shutil.rmtree(stage, ignore_errors=True)
    a = _launch("LA", stage_dir=stage, source_mode="ok")
    b = _launch("LB", stage_dir=stage, source_mode="ok")
    time.sleep(2.0)
    fails_on = _leader_failures([a, b], "مع الحماية")
    ok(len(fails_on) == 0,
       "🧨a مع الحماية: واحد بس القائد ⭐ (0 إخفاقات ⭐)", fails_on)

    # ② شيل الحماية ⭐ ⇒ كل عامل بمجلد خاص ⭐ ⇒ قفل خاص ⭐
    shutil.rmtree("/tmp/octa_r25_conc_priv1", ignore_errors=True)
    shutil.rmtree("/tmp/octa_r25_conc_priv2", ignore_errors=True)
    p1 = _launch("P1", stage_dir="/tmp/octa_r25_conc_priv1", source_mode="ok")
    p2 = _launch("P2", stage_dir="/tmp/octa_r25_conc_priv2", source_mode="ok")
    time.sleep(2.0)
    fails_off = _leader_failures([p1, p2], "بدون حماية")
    l1, _f1 = _leaders(p1)
    l2, _f2 = _leaders(p2)
    print("   بدون الحماية: قادة=%d ⭐ (A=%d B=%d) ⭐"
          % (l1 + l2, l1, l2), flush=True)
    print("   الإخفاقات مع الحماية=%d · بدونها=%d ⭐"
          % (len(fails_on), len(fails_off)), flush=True)
    ok(len(fails_off) > 0,
       "🧨b بدون الحماية: نفس الفحص **فشل** ⭐ (الاختبار حسّاس ⭐)",
       "expected failures>0 got %d" % len(fails_off))
    ok(l1 + l2 == 2,
       "🧨c الاتنين بقوا قادة ⭐ (تكرار في المهام الخلفية ⭐)",
       "A=%d B=%d" % (l1, l2))
    REPORT["negative_leader"] = {"before": len(fails_off), "after": len(fails_on)}
    return {"before": len(fails_off), "after": len(fails_on)}


def main():
    print("=" * 70)
    print("  👥 R25 · عاملان صناعيان + تعافّي بعد إعادة التشغيل")
    print("  ⛔ بيئة معزولة · مافيش شبكة · مافيش موارد مدفوعة")
    print("=" * 70)
    test_concurrency_two_workers_shared_state()
    test_concurrency_background_task_recovery_after_restart()
    test_concurrency_data_lock_keeps_file_intact()
    test_concurrency_negative_proof_atomic_write_removed()
    test_concurrency_negative_proof_leader_lock_removed()

    passed = sum(1 for r in RESULTS if r[0])
    failed = len(RESULTS) - passed
    print("\n" + "=" * 70)
    print("  📊 نتائج التزامن (قياسات حقيقية):")
    load = REPORT.get("load")
    if load:
        print("     %-30s %d طلب في %.2fs ⭐"
              % ("الحمل المتزامن", load["total"], load["wall"]))
    lead = REPORT.get("leaders")
    if lead:
        print("     %-30s A=%d · B=%d ⭐ (واحد بس ⭐)"
              % ("انتخاب القائد", lead["A"], lead["B"]))
    rec = REPORT.get("recovery")
    if rec:
        print("     %-30s القائد الجديد=%d ⭐ (تعافّي بعد الموت ⭐)"
              % ("التعافي بعد إعادة التشغيل", rec["new_leaders"]))
    wr = REPORT.get("writes")
    if wr:
        print("     %-30s كُتب=%d · موجود=%d · مفقود=%d ⭐"
              % ("أقفال البيانات", wr["written"], wr["present"], wr["lost"]))
        print("     %-30s قراءات=%d · قراءات تالفة=%d ⭐"
              % ("سلامة الملف", wr["reads"], wr["bad_reads"]))
    neg = REPORT.get("negative_atomic")
    if neg:
        print("     %-30s الإخفاقات قبل=%d · بعد=%d ⭐"
              % ("برهان الذرّية", neg["before"], neg["after"]))
    neg2 = REPORT.get("negative_leader")
    if neg2:
        print("     %-30s الإخفاقات قبل=%d · بعد=%d ⭐"
              % ("برهان القائد", neg2["before"], neg2["after"]))
    print("=" * 70)
    print("  النتيجة: %d ناجح / %d فاشل  (الإجمالي %d)"
          % (passed, failed, len(RESULTS)))
    if failed:
        for cond, label in RESULTS:
            if not cond:
                print("   ❌ " + label)
        return 1
    print("  RESULT: CLEAN")
    return 0


if __name__ == "__main__":
    sys.exit(main())
