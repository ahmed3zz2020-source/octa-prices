#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
🧪 بيئة الاختبار المعزولة — الجولة ٢٥ (R25 · المرحلة ٩)

📌 الأداة دي بتغلّف أداة الـstaging الموجودة ⭐
   (`tools/staging/run_staging.py` ⭐) وبتديها ability إضافية ⭐:
   · تشغيل / إيقاف / إعادة تشغيل ⭐ (عشان نختبر الـrecovery ⭐).
   · مجلد بيانات **مؤقّت** لكل تشغيل ⭐ (عزل كامل ⭐).
   · عميل HTTPStdlib ⭐ (مكتبة قياسية ⭐ — مافيش اعتماديات ⭐).
   · قياس زمن الاستجابة ⭐ (p50 · p95 · p99 ⭐).

⛔⛔⛔ قواعد صارمة ⬇️ ⬇️ ⬇️
  ⛔ كل السيرفرات بتقوم على `127.0.0.1` ⬇️ ⬇️ (مش أي عنوان خارجي ⭐)
  ⛔ كل الأسرار **اصطناعية** ⭐ وبتتولّد هنا ⭐
  ⛔ الشبكة مقفولة جوه العملية ⭐ (مشSkeleton ⭐)
  ⛔ مافيش أي نشر ⭐ ومافيش أي مورد مدفوع ⭐

📌 التشغيل (بلا سيرفر ⭐):
   python3 tools/staging/iso_env.py
"""
import http.client
import json
import os
import socket
import subprocess
import sys
import threading
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parent.parent
STAGING = HERE / "run_staging.py"

# ⛔ بادئة الأسرار الاصطناعية ⭐ (مش أسرار إنتاج ⭐ ولا أسرار حقيقية ⭐)
_SYNTH = "SYNTH-R25-"


def free_port():
    """بورت فاضي على الـloopback ⭐."""
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.bind(("127.0.0.1", 0))
    port = s.getsockname()[1]
    s.close()
    return port


def synth_secret(tag):
    """سر **اصطناعي** خاص بالاختبار ⭐ — بيتولّد محلياً ⭐."""
    import secrets as _secrets
    return "%s%s-%s" % (_SYNTH, tag, _secrets.token_urlsafe(18))


# ══════════════════════════════════════════════════════════════════
#  🖥️ السيرفر المعزول
# ══════════════════════════════════════════════════════════════════
class IsoServer:
    """سيرفر staging معزول ⭐ — مع إيقاف وإعادة تشغيل ⭐."""

    def __init__(self, stage_dir, port, proc, log_path, env):
        self.stage_dir = Path(stage_dir)
        self.port = int(port)
        self.proc = proc
        self.log_path = Path(log_path)
        self.env = dict(env)
        self.base_url = "http://127.0.0.1:%d" % self.port

    @property
    def proxy_secret(self):
        """⛔ سر البروبزي ⭐ — من ملف الأسرار المشترك ⭐."""
        prev = read_secrets(self.stage_dir)
        if prev.get("proxy"):
            return str(prev["proxy"])
        return str(self.env.get("STAGE_PROXY_SECRET", "") or "")

    # ── الحالة ⭐ ──
    @property
    def alive(self):
        return self.proc is not None and self.proc.poll() is None

    def log_tail(self, n=40):
        try:
            lines = self.log_path.read_text(encoding="utf-8", errors="replace").splitlines()
            return lines[-n:]
        except Exception:
            return []

    # ── الإيقاف ⭐ ──
    def stop(self, kill=False, timeout=20):
        """⛔ يوقف السيرفر ⭐ — `kill=True` ⇒ إيقاف قاسٍ ⭐ (محاكاة انهيار ⭐)."""
        if self.proc is None:
            return
        try:
            if kill:
                self.proc.kill()
            else:
                self.proc.terminate()
            self.proc.wait(timeout=timeout)
        except Exception:
            try:
                self.proc.kill()
                self.proc.wait(timeout=10)
            except Exception:
                pass
        try:
            self._close_port()
        except Exception:
            pass

    def _close_port(self):
        try:
            s = socket.create_connection(("127.0.0.1", self.port), timeout=1)
            s.close()
        except Exception:
            pass

    # ── الانتظار ⭐ ──
    def wait_ready(self, timeout=240, path="/api/health"):
        """بيرجع (ok · elapsed_seconds) ⭐."""
        t0 = time.time()
        deadline = t0 + timeout
        while time.time() < deadline:
            if self.proc is not None and self.proc.poll() is not None:
                return False, time.time() - t0
            try:
                c = Client(self.base_url, self.proxy_secret)
                st, _h, body, _ms = c.request("GET", path, auth=False, timeout=8)
                c.close()
                if st == 200:
                    return True, time.time() - t0
            except Exception:
                pass
            time.sleep(0.4)
        return False, time.time() - t0

    def wait_down(self, timeout=30):
        t0 = time.time()
        while time.time() - t0 < timeout:
            try:
                s = socket.create_connection(("127.0.0.1", self.port), timeout=1)
                s.close()
                time.sleep(0.2)
            except Exception:
                return True, time.time() - t0
        return False, time.time() - t0


def launch(stage_dir=None, port=None, extra_env=None, bg_tasks=None,
           rate_mult=None, harness=True, warmup="0", log_path=None,
           source_mode=None):
    """يشغّل أداة الـstaging المعزولة ⭐ في عملية منفصلة ⭐."""
    stage_dir = Path(stage_dir or os.environ.get("OCTA_ISO_DIR")
                     or ("/tmp/octa_r25_iso_%d" % int(time.time())))
    stage_dir.mkdir(parents=True, exist_ok=True)
    port = int(port or free_port())

    env = dict(os.environ)
    env.update({
        "STAGE_DIR": str(stage_dir),
        "STAGE_PORT": str(port),
        # ⛔ ملف الأسرار **مشترك بين الـworkers على نفس المجلد** ⭐
        # 📌 (لازم ⭐) ⇒ التوكنات والـpepper واحد ⭐
        # 📌 ⇒ من غير كده كل عامل بيعمل hashes مختلفة ⭐
        # 📌 ⇒ والدخول بيقع 401 ⭐ ⇒ ودي **مش** عيب في الإنتاج ⭐
        "STAGE_SECRETS_FILE": str(stage_dir / "secrets.json"),
        "OCTA_ISO": "1",
        # ⛔ العزل ⭐ — الشبكة مقفولة ⭐ ومافيش أي اتصال خارجي ⭐
        "STAGE_ISOLATED": "1",
        "STAGE_HARNESS": "1" if harness else "0",
        "PYTHONUNBUFFERED": "1",
    })
    # ⛔ لو فيه أسرار من تشغيل قبل ⭐ ⇒ نستخدمها ⭐ (تزامن ⭐)
    prev = read_secrets(stage_dir)
    if prev:
        env["STAGE_TOKEN_SECRET"] = prev.get("secret", "")
        env["STAGE_PROXY_SECRET"] = prev.get("proxy", "")
        env["STAGE_ADMIN_TOKEN"] = prev.get("admin", "")
    else:
        env["STAGE_TOKEN_SECRET"] = synth_secret("TOKEN")
        env["STAGE_PROXY_SECRET"] = synth_secret("PROXY")
        env["STAGE_ADMIN_TOKEN"] = synth_secret("ADMIN")
    if source_mode is not None:
        env["STAGE_SOURCE_MODE"] = str(source_mode)
    if bg_tasks is not None:
        env["OCTA_BG_TASKS"] = str(bg_tasks)
    if rate_mult is not None:
        env["OCTA_RATE_MULT"] = str(rate_mult)
    if extra_env:
        env.update({k: str(v) for k, v in dict(extra_env).items()})
    if warmup is not None:
        env["OCTA_WARMUP"] = str(warmup)

    # ⛔ لوج **لكل تشغيل** ⭐ ⇒ العدّ مايتلخبطش من تشغيلات قديمة ⭐
    log_path = Path(log_path or (stage_dir / ("server-%d.log" % port)))
    logf = open(str(log_path), "ab")
    proc = subprocess.Popen(
        [sys.executable, str(STAGING)], cwd=str(REPO), env=env,
        stdout=logf, stderr=subprocess.STDOUT)
    srv = IsoServer(stage_dir, port, proc, log_path, env)
    return srv


def restart(srv, kill=False, timeout=240):
    """⛔ يعيد تشغيل السيرفر **بنفس مجلد البيانات** ⭐ (اختبار الاسترجاع ⭐)."""
    srv.stop(kill=kill)
    new = launch(stage_dir=srv.stage_dir, port=srv.port,
                 extra_env={k: v for k, v in srv.env.items()
                            if k in ("OCTA_BG_TASKS", "OCTA_RATE_MULT",
                                     "OCTA_WARMUP", "STAGE_HARNESS",
                                     "STAGE_SOURCE_MODE")},
                 log_path=srv.log_path)
    ok, elapsed = new.wait_ready(timeout=timeout)
    return new, ok, elapsed


# ══════════════════════════════════════════════════════════════════
#  📡 العميل
# ══════════════════════════════════════════════════════════════════
class Resp:
    """رد HTTP مبسّط ⭐."""

    __slots__ = ("status", "headers", "body", "ms")

    def __init__(self, status, headers, body, ms):
        self.status = status
        self.headers = headers
        self.body = body
        self.ms = ms

    def json(self):
        try:
            return json.loads(self.body.decode("utf-8"))
        except Exception:
            return None

    @property
    def ok(self):
        return 200 <= self.status < 400


class Client:
    """عميل HTTP ⭐ — دايمًا على `127.0.0.1` ⭐ وبيرسل سر البروبسي ⭐."""

    def __init__(self, base_url, proxy_secret="", client_ip="127.0.0.1",
                 token=None):
        self.base_url = base_url.rstrip("/")
        self.host, self.port = _split(self.base_url)
        self.proxy_secret = proxy_secret or ""
        self.client_ip = client_ip
        self.token = token
        self._local = threading.local()
        self.samples = []

    # ── الاتصال ⭐ ──
    def _conn(self):
        conn = getattr(self._local, "conn", None)
        if conn is None:
            conn = http.client.HTTPConnection(self.host, self.port, timeout=120)
            self._local.conn = conn
        return conn

    def close(self):
        conn = getattr(self._local, "conn", None)
        if conn is not None:
            try:
                conn.close()
            except Exception:
                pass
            self._local.conn = None

    # ── الطلب ⭐ ──
    def request(self, method, path, body=None, headers=None, auth=True,
                timeout=120, keep=True):
        payload = None
        hdrs = {"Accept": "application/json"}
        if self.proxy_secret:
            hdrs["X-OCTA-Proxy"] = self.proxy_secret
        if self.client_ip:
            hdrs["X-OCTA-Client-IP"] = self.client_ip
        if auth and self.token:
            hdrs["Authorization"] = "Bearer %s" % self.token
        if body is not None:
            payload = json.dumps(body, ensure_ascii=False).encode("utf-8")
            hdrs["Content-Type"] = "application/json"
        if headers:
            hdrs.update({str(k): str(v) for k, v in dict(headers).items()})

        t0 = time.perf_counter()
        conn = self._conn()
        try:
            conn.request(method, path, body=payload, headers=hdrs)
            resp = conn.getresponse()
            data = resp.read()
            status = resp.status
            rh = dict(resp.getheaders())
        except Exception:
            # ⛔ الاتصال اتقفل ⭐ ⇒ نعيد فتحه ونجرب مرة واحدة ⭐
            self.close()
            conn = self._conn()
            conn.request(method, path, body=payload, headers=hdrs)
            resp = conn.getresponse()
            data = resp.read()
            status = resp.status
            rh = dict(resp.getheaders())
        ms = (time.perf_counter() - t0) * 1000.0
        if not keep:
            self.close()
        out = Resp(status, rh, data, ms)
        self.samples.append(out)
        return out.status, rh, data, ms

    def get(self, path, **kw):
        return self.request("GET", path, **kw)

    def post(self, path, body=None, **kw):
        return self.request("POST", path, body=body if body is not None else {},
                            **kw)

    # ── الدخول ⭐ ──
    def login(self, pin, device):
        st, _h, body, _ms = self.post("/api/auth/pin/login",
                                      {"pin": pin, "device": device},
                                      auth=False)
        try:
            j = json.loads(body.decode("utf-8"))
        except Exception:
            j = {}
        tok = j.get("token")
        if tok:
            self.token = tok
        return tok, st, j


def _split(base_url):
    rest = base_url.split("://", 1)[-1]
    hostport = rest.split("/", 1)[0]
    if ":" in hostport:
        host, port = hostport.rsplit(":", 1)
        return host, int(port)
    return hostport, 80


# ══════════════════════════════════════════════════════════════════
#  📊 إحصاء
# ══════════════════════════════════════════════════════════════════
def percentile(values, pct):
    """نسبة مئوية حقيقية ⭐ — الطريقة الخطّية (شبيهة بـnumpy ⭐)."""
    data = sorted(float(v) for v in values)
    if not data:
        return None
    if len(data) == 1:
        return data[0]
    k = (len(data) - 1) * (float(pct) / 100.0)
    lo = int(k)
    hi = min(lo + 1, len(data) - 1)
    frac = k - lo
    return data[lo] * (1.0 - frac) + data[hi] * frac


def summarize(values):
    """ملخّص زمن الاستجابة ⭐."""
    data = sorted(float(v) for v in values)
    if not data:
        return {"n": 0}
    return {
        "n": len(data),
        "min_ms": round(data[0], 3),
        "p50_ms": round(percentile(data, 50), 3),
        "p95_ms": round(percentile(data, 95), 3),
        "p99_ms": round(percentile(data, 99), 3),
        "max_ms": round(data[-1], 3),
        "mean_ms": round(sum(data) / len(data), 3),
    }


def read_secrets(stage_dir):
    """يقرأ أسرار الـstaging ⭐ (اصطناعية ⭐ · مشروعة للاختبار ⭐)."""
    try:
        p = Path(stage_dir) / "secrets.json"
        return json.loads(p.read_text(encoding="utf-8"))
    except Exception:
        return {}


def read_stage_cfg(stage_dir):
    """يقرأ ملف إعدادات الـstaging ⭐ (اللي السيرفر كاتبه ⭐)."""
    p = Path(stage_dir) / "staging-config.json"
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except Exception:
        return {}


if __name__ == "__main__":
    print("🧪 بيئة الاختبار المعزولة — الجولة ٢٥")
    print("   مجلد الأدوات: %s" % HERE)
    print("   أداة الـstaging: %s" % STAGING)
    print("   البورتات الحرة: %d" % free_port())
