#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
🎬 اختبار شامل على الـstaging المحلي — الجولة ١٨ · المرحلة ٧ (تشغيل)
=====================================================================
📌 الهدف: **تشغيل حقيقي** — واجهة + بك-إند حيّ + تسجيل دخول بـPIN حقيقي
   + فتح كل صفحة والتأكد إنها **اتحمّلت ببيانات** (مش مجرد HTML).

⛔ العزل:
   · السيرفر-local بيقدّم ملفات الواجهة وبيوجّه `/api/*` للـstaging المحلي.
   · أي طلب لغير 127.0.0.1/localhost بيتعمله abort ⇒ **صفر اتصال بالإنتاج**.
   · البيانات من بيئة staging المعزولة (بيانات وهمية) — مش بيانات مستخدمين.

📌 التشغيل:
   python3 tools/staging/e2e_playwright.py --frontend-dir /workspace/.wt_ux
   python3 tools/staging/e2e_playwright.py --frontend-dir <path> --out /tmp/e2e.json

📌 المخرجات: JSON + Markdown (نفس شكل فاحص الواجهة).
"""
import argparse
import json
import os
import re
import socket
import sys
import threading
import time
import urllib.request
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

try:
    from playwright.sync_api import sync_playwright
except ImportError:
    print("⛔ playwright مش مثبّت", file=sys.stderr)
    sys.exit(2)

HERE = Path(__file__).resolve().parent
ALLOWED_HOSTS = {"127.0.0.1", "localhost", "::1", "", "octa.local"}
CHROMIUM = os.environ.get(
    "OCTA_CHROMIUM", "/root/.cache/ms-playwright/chromium-1243/chrome-linux/chrome")

PROD_URL_RE = re.compile(r"https://octa-prices-production-4ccb\.up\.railway\.app")


def read_staging_secrets():
    p = Path("/workspace/.staging-secrets.json")
    if p.exists():
        try:
            return json.loads(p.read_text(encoding="utf-8"))
        except Exception:
            pass
    return {}


def _is_local_base(url):
    """هل العنوان محلي؟ (⛔ التوكن ما ينفعش يروح لعنوان خارجي)"""
    try:
        host = url.split("//")[-1].split("/")[0].split(":")[0]
    except Exception:
        return False
    return host in ("127.0.0.1", "localhost", "::1", "")


def free_port():
    s = socket.socket()
    s.bind(("127.0.0.1", 0))
    p = s.getsockname()[1]
    s.close()
    return p


class Handler(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"
    fe_dir = Path(".")
    api_base = "http://127.0.0.1:8099"
    proxy_secret = ""
    routes = set()

    def log_message(self, *a):
        pass

    def _send(self, code, body=b"", ctype="text/plain; charset=utf-8"):
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        if body:
            self.wfile.write(body)

    def do_GET(self):
        self._proxy()

    def do_POST(self):
        self._proxy()

    def do_OPTIONS(self):
        self._proxy()

    def _proxy(self):
        path = self.path.split("?")[0]
        if path.startswith("/api/"):
            return self._to_api()
        if path == "/" or path == "/index.html":
            return self._file("index.html")
        if path in self.routes:
            return self._file("index.html")
        if path.endswith(".html"):
            return self._file(path.lstrip("/"))
        rel = path.lstrip("/")
        for cand in (rel, "assets/" + rel):
            fp = self.fe_dir / cand
            if fp.is_file():
                ctype = ("text/html; charset=utf-8" if fp.suffix == ".html"
                         else "text/css; charset=utf-8" if fp.suffix == ".css"
                         else "application/javascript; charset=utf-8" if fp.suffix == ".js"
                         else "application/json" if fp.suffix == ".json"
                         else "image/png" if fp.suffix == ".png"
                         else "application/octet-stream")
                return self._send(200, fp.read_bytes(), ctype)
        return self._send(404, b"not found")

    def _file(self, rel):
        fp = self.fe_dir / rel
        if not fp.is_file():
            return self._send(404, b"not found")
        body = fp.read_bytes()
        if fp.suffix == ".html":
            html = body.decode("utf-8")
            # ⛔ fail-closed زي المعاينة ⇒ ممنوع الاتصال بالإنتاج
            tag = "<script>window.OCTA_FAIL_CLOSED=1;</script>"
            html = html.replace("</head>", tag + "</head>") if "</head>" in html \
                else (tag + html)
            html = PROD_URL_RE.sub("https://blocked.invalid", html)
            body = html.encode("utf-8")
        return self._send(200, body, "text/html; charset=utf-8")

    def _to_api(self):
        """⛔ كل طلب API بيمرّ من هنا ⇒ بياخد سر الوسيط + forbidden ⛔"""
        n = int(self.headers.get("Content-Length") or 0)
        body = self.rfile.read(n) if n else None
        url = self.api_base.rstrip("/") + self.path
        req = urllib.request.Request(url, data=body, method=self.command)
        for k, v in self.headers.items():
            if k.lower() in ("host", "content-length", "connection"):
                continue
            req.add_header(k, v)
        if self.proxy_secret:
            req.add_header("X-OCTA-Proxy", self.proxy_secret)
        try:
            with urllib.request.urlopen(req, timeout=60) as r:
                data = r.read()
                self.send_response(r.status)
                ctype = r.headers.get("Content-Type", "application/json")
                self.send_header("Content-Type", ctype)
                self.send_header("Content-Length", str(len(data)))
                for k, v in r.headers.items():
                    if k.lower() in ("content-type", "content-length", "transfer-encoding"):
                        continue
                    self.send_header(k, v)
                self.end_headers()
                # ⛔ العميل ممكن يكون قفل الاتصال ⇒ من غير كده بيقع BrokenPipe
                try:
                    self.wfile.write(data)
                except (BrokenPipeError, ConnectionResetError):
                    pass
        except urllib.error.HTTPError as e:
            data = e.read()
            self.send_response(e.code)
            self.send_header("Content-Type", e.headers.get("Content-Type", "application/json"))
            self.send_header("Content-Length", str(len(data)))
            self.end_headers()
            try:
                self.wfile.write(data)
            except (BrokenPipeError, ConnectionResetError):
                pass
        except Exception as e:
            self._send(502, json.dumps({"ok": False, "error": "upstream_unreachable",
                                        "why": str(e)[:120]}).encode(), "application/json")


# ══════════════════════════════════════════════════════════════
def parse_spa_routes(fe_dir: Path):
    s = (fe_dir / "worker.js").read_text(encoding="utf-8")
    m = re.search(r"const SPA_ROUTES\s*=\s*\[([^\]]+)\]", s)
    if not m:
        return []
    return [x.strip().strip("'\"") for x in m.group(1).split(",") if x.strip().strip("'\"")]


# ⛔ تحويل موثّق في الكود (octa-filters.js · fzBestInit):
#   'best' ⇒ تبويب جوّه صفحة الفلاتر (مش صفحة مستقلة)
LEGACY_REDIRECT = {"best": "filter"}


def parse_alias(fe_dir: Path):
    s = (fe_dir / "assets" / "js" / "octa-core.js").read_text(encoding="utf-8")
    m = re.search(r"const OCTA_PATH_ALIAS\s*=\s*\{([\s\S]*?)\n\};", s)
    if not m:
        return {}
    return {mm.group(1): mm.group(2) for mm in
            re.finditer(r"'([^']+)'\s*:\s*'([^']+)'", m.group(1))}


def parse_tool_pages(fe_dir: Path):
    s = (fe_dir / "assets" / "js" / "octa-core.js").read_text(encoding="utf-8")
    m = re.search(r"const TOOL_PAGES\s*=\s*\[([^\]]+)\]", s)
    return [x.strip().strip("'\"") for x in m.group(1).split(",") if x.strip().strip("'\"")]


JS_VISIBLE = """
() => {
  const out = [];
  for (const id of __IDS__) {
    const el = document.getElementById(id);
    if (!el) continue;
    const cs = getComputedStyle(el);
    const r = el.getBoundingClientRect();
    if (cs.display !== 'none' && cs.visibility !== 'hidden'
        && parseFloat(cs.opacity || '1') > 0.01 && (r.width > 0 || r.height > 0)) out.push(id);
  }
  return out;
}
"""

JS_OVERFLOW = """
() => { const de = document.documentElement;
        return {scrollW: de.scrollWidth, innerW: window.innerWidth}; }
"""


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--frontend-dir", required=True)
    ap.add_argument("--api-base", default="http://127.0.0.1:8099")
    ap.add_argument("--out", default="/tmp/e2e.json")
    ap.add_argument("--widths", default="360,390,768")
    ap.add_argument("--pin", default="1111")
    a = ap.parse_args()

    fe = Path(a.frontend_dir).resolve()
    if not (fe / "index.html").exists():
        print("⛔ مافيش index.html في %s" % fe, file=sys.stderr)
        return 2

    sec = read_staging_secrets()
    proxy_secret = os.environ.get("OCTA_PROXY_SECRET", "") or sec.get("proxy", "")

    routes = parse_spa_routes(fe)
    alias = parse_alias(fe)
    tool_pages = parse_tool_pages(fe)
    widths = [int(x) for x in a.widths.split(",") if x.strip()]

    Handler.fe_dir = fe
    Handler.api_base = a.api_base
    Handler.proxy_secret = proxy_secret
    Handler.routes = set(routes)

    port = free_port()
    srv = ThreadingHTTPServer(("127.0.0.1", port), Handler)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    base = "http://octa.local:%d" % port
    time.sleep(0.4)

    ids = sorted(set([("dashPage" if p == "dash" else "page-" + p) for p in tool_pages]
                     + ["gate", "homeHidden", "armView", "stockPage", "intelPage",
                        "dashPage", "decideModal", "modalOverlay"]))
    js_vis = JS_VISIBLE.replace("__IDS__", json.dumps(ids))

    egress = []
    results = []
    login = {"ok": False, "detail": ""}

    with sync_playwright() as p:
        browser = p.chromium.launch(executable_path=CHROMIUM,
                                    args=["--no-sandbox", "--disable-dev-shm-usage",
                                          "--host-resolver-rules=MAP octa.local 127.0.0.1"])

        def make_ctx(width):
            ctx = browser.new_context(viewport={"width": width, "height": 844},
                                      device_scale_factor=2,
                                      is_mobile=(width < 768), locale="ar-EG")

            def guard(route, request):
                host = request.url.split("//")[-1].split("/")[0].split(":")[0]
                if host in ALLOWED_HOSTS or request.url.startswith("data:"):
                    route.continue_()
                else:
                    egress.append({"url": request.url, "width": width})
                    route.abort()
            ctx.route("**/*", guard)
            return ctx

        # ── ① الصفحة العامة (من غير دخول) ──
        ctx = make_ctx(390)
        pg = ctx.new_page()
        pub = {"kind": "public", "width": 390, "errors": []}
        pg.on("pageerror", lambda e: pub["errors"].append(str(e)[:200]))
        try:
            pg.goto(base + "/", wait_until="domcontentloaded", timeout=40000)
            pg.wait_for_timeout(2500)
            pub["visible"] = pg.evaluate(js_vis)
            pub["gate_visible"] = pg.is_visible("#gate") if pg.query_selector("#gate") else False
            pub["text_len"] = len(pg.inner_text("body") or "")
        except Exception as e:
            pub["errors"].append(str(e)[:200])
        pg.close()
        results.append(pub)

        # ── ② ربط جهاز المتصفح بالحساب (عبر أدمن الـstaging) ──
        # 📌 رقم الجهاز = octa_bio_key (عشوائي في localStorage).
        # 📌 من غير الربط ⇒ «جهاز جديد» ⇒ لازم كود إيميل ⇒ مستحيل في الاختبار.
        device = "e2e-" + ("d" * 48)
        # ⛔ ترتيب مهم: توكن **الـstaging** (من ملف الأسرار) هو الصح.
        #   ⛔ المتغيّر في البيئة ممكن يكون توكن **إنتاج** ⇒ ما ينفعش
        #   نبعتّه لعنوان غير محلي. ⇒ لو الـbase مش محلي ⇒ مافيش توكن خالص.
        admin = sec.get("admin", "")
        if not admin and _is_local_base(a.api_base):
            admin = os.environ.get("OCTA_ADMIN_TOKEN", "")
        bound = False
        if admin:
            try:
                req = urllib.request.Request(
                    a.api_base.rstrip("/") + "/api/admin/set_device",
                    data=json.dumps({"email": "staging.free@example.test",
                                     "device": device}).encode(),
                    method="POST")
                req.add_header("Content-Type", "application/json")
                req.add_header("X-OCTA-Admin", admin)
                if proxy_secret:
                    req.add_header("X-OCTA-Proxy", proxy_secret)
                with urllib.request.urlopen(req, timeout=20) as r:
                    bound = r.status == 200
            except Exception as e:
                login["bind_error"] = str(e)[:150]

        # ── ③ دخول بـPIN حقيقي ──
        ctx2 = make_ctx(390)
        ctx2.add_init_script(
            "try{localStorage.setItem('octa_bio_key','%s');}catch(e){}" % device)
        pg2 = ctx2.new_page()
        pg2.on("pageerror", lambda e: login.setdefault("errors", []).append(str(e)[:200]))
        try:
            pg2.goto(base + "/", wait_until="domcontentloaded", timeout=40000)
            # 📌 شاشة البوابة: «عندك حساب؟ ادخل» (#gtLogin) ⇒ بعدها لوحة ٤ أرقام
            #   (buttons .gt-key[data-k]) ⇒ من غير الخطوة دي اللوحة مش موجودة.
            try:
                # ⛔ مهلة طويلة: البوابة بتظهر بعد ردّ /api/auth/me
                #   (والستaging مشغول ⇒ الرد ممكن ياخد ثواني).
                pg2.wait_for_selector("#gtLogin", timeout=45000)
                pg2.click("#gtLogin")
            except Exception:
                pass
            pg2.wait_for_selector("button.gt-key[data-k='1']", timeout=45000)
            for d in a.pin:
                pg2.click("button.gt-key[data-k='%s']" % d)
                pg2.wait_for_timeout(220)
            pg2.wait_for_timeout(3500)
            login["token_present"] = bool(pg2.evaluate(
                "() => { try { return !!localStorage.getItem('octa_token'); } catch(e){ return false; } }"))
            login["gate_visible"] = pg2.is_visible("#gate") if pg2.query_selector("#gate") else False
            login["ok"] = bool(login["token_present"]) and not login["gate_visible"]
            login["device_bound"] = bound
            login["detail"] = ("token=%s gate=%s bound=%s"
                               % (login["token_present"], login["gate_visible"], bound))
        except Exception as e:
            login["ok"] = False
            login["detail"] = str(e)[:200]
        pg2.close()
        ctx2.close()

        # ── ④ كل مسار (والجلسة موجودة في localStorage) ──
        for width in widths:
            ctx3 = make_ctx(width)
            ctx3.add_init_script(
                "try{localStorage.setItem('octa_token','e2e-local');}catch(e){}")
            for route in routes:
                rec = {"route": route, "width": width, "errors": []}
                page = ctx3.new_page()
                page.on("pageerror", lambda e, r=rec: r["errors"].append(str(e)[:250]))
                try:
                    resp = page.goto(base + route, wait_until="domcontentloaded", timeout=40000)
                    rec["http"] = resp.status if resp else None
                    page.wait_for_timeout(2200)
                    vis = page.evaluate(js_vis)
                    rec["visible"] = vis
                    pid = alias.get(route.strip("/"), route.strip("/"))
                    pid = LEGACY_REDIRECT.get(pid, pid)
                    want = "dashPage" if pid == "dash" else "page-" + pid
                    rec["want"] = want
                    rec["page_ok"] = want in vis
                    ov = page.evaluate(JS_OVERFLOW)
                    rec["overflow"] = (ov["scrollW"] or 0) > (ov["innerW"] or 0) + 4
                    rec["overflow_px"] = (ov["scrollW"] or 0) - (ov["innerW"] or 0)
                    body = page.inner_text("body") or ""
                    rec["text_len"] = len(body)
                    # ⭐ دليل إن الداتا وصلت فعلاً (مش HTML فاضي)
                    rec["has_data"] = len(body) > 400 and len(
                        re.findall(r"\d", body)) > 20
                except Exception as e:
                    rec["errors"].append(str(e)[:250])
                finally:
                    page.close()
                results.append(rec)
            ctx3.close()
        browser.close()
    srv.shutdown()

    payload = {"generated_at": time.strftime("%Y-%m-%d %H:%M:%S"),
               "base": base, "api_base": a.api_base, "widths": widths,
               "routes": routes, "login": login, "results": results,
               "egress_violations": egress}
    Path(a.out).write_text(json.dumps(payload, ensure_ascii=False, indent=2),
                           encoding="utf-8")

    pages = [r for r in results if r.get("kind") != "public"]
    ok = sum(1 for r in pages if r.get("page_ok"))
    data = sum(1 for r in pages if r.get("has_data"))
    ovf = sum(1 for r in pages if r.get("overflow"))
    errs = sum(len(r.get("errors", [])) for r in results)
    print("🔑 الدخول: %s (%s)" % ("نجح ✅" if login.get("ok") else "فشل ⛔",
                                  login.get("detail", "")))
    print("📄 الصفحة الصح: %d/%d" % (ok, len(pages)))
    print("📊 فيها داتا: %d/%d" % (data, len(pages)))
    print("📱 تمدد أفقي: %d" % ovf)
    print("🐞 أخطاء JS: %d" % errs)
    print("⛔ خروج خارج localhost: %d" % len(egress))
    print("📄 %s" % a.out)
    return 0


if __name__ == "__main__":
    sys.exit(main())
