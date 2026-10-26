#!/usr/bin/env python3
"""TradingView WebSocket عبر raw socket (بدون مكتبات) — جلب سعر/تاريخ مؤشر
اللي مش موجود في الـscanner (زي EGX:SHARIAH). الـOrigin مطلوب من TV."""
import socket, ssl, base64, os, struct, json, time


def ws_connect(host, path, headers, timeout=25):
    raw = socket.create_connection((host, 443), timeout=timeout)
    s = ssl.create_default_context().wrap_socket(raw, server_hostname=host)
    key = base64.b64encode(os.urandom(16)).decode()
    req = f"GET {path} HTTP/1.1\r\nHost: {host}\r\nUpgrade: websocket\r\nConnection: Upgrade\r\n"
    req += f"Sec-WebSocket-Key: {key}\r\nSec-WebSocket-Version: 13\r\n"
    for k, v in headers.items():
        req += f"{k}: {v}\r\n"
    req += "\r\n"
    s.sendall(req.encode())
    buf = b""
    while b"\r\n\r\n" not in buf:
        chunk = s.recv(4096)
        if not chunk:
            break
        buf += chunk
    if b"101" not in buf.split(b"\r\n")[0]:
        raise RuntimeError("handshake failed: " + buf.split(b"\r\n")[0].decode(errors="ignore"))
    return s, buf.split(b"\r\n\r\n", 1)[1]


def ws_send(s, payload):
    data = payload.encode()
    mask = os.urandom(4)
    n = len(data)
    if n < 126:
        hdr = struct.pack("!BB", 0x81, 0x80 | n)
    elif n < 65536:
        hdr = struct.pack("!BBH", 0x81, 0x80 | 126, n)
    else:
        hdr = struct.pack("!BBQ", 0x81, 0x80 | 127, n)
    masked = bytes(b ^ mask[i % 4] for i, b in enumerate(data))
    s.sendall(hdr + mask + masked)


def ws_recv(s, buf, timeout=25):
    s.settimeout(timeout)

    def need(n, buf):
        while len(buf) < n:
            c = s.recv(65536)
            if not c:
                raise RuntimeError("closed")
            buf += c
        return buf

    hdr = need(2, buf)
    b1, b2 = hdr[0], hdr[1]
    ln = b2 & 0x7F
    off = 2
    if ln == 126:
        hdr = need(4, hdr); ln = struct.unpack("!H", hdr[2:4])[0]; off = 4
    elif ln == 127:
        hdr = need(10, hdr); ln = struct.unpack("!Q", hdr[2:10])[0]; off = 10
    if b2 & 0x80:
        mask = need(off + 4, hdr)[off:off + 4]; off += 4
    data = need(off + ln, hdr)[off:off + ln]
    if b2 & 0x80:
        data = bytes(b ^ mask[i % 4] for i, b in enumerate(data))
    return data, hdr[off + ln:]


def parse_frames(raw):
    out, i = [], 0
    while True:
        t = raw.find(b"~m~", i)
        if t < 0:
            break
        le = raw.find(b"~m~", t + 3)
        if le < 0:
            break
        ln = int(raw[t + 3:le])
        try:
            out.append(json.loads(raw[le + 3:le + 3 + ln]))
        except Exception:
            pass
        i = le + 3 + ln
    return out


def fetch(symbol, count=5):
    host = "data.tradingview.com"
    path = "/socket.io/websocket?from=chart%2F" + symbol.replace(":", "%3A").replace("/", "%2F") + "%2F&date=2026_10_26-00_00"
    s, buf = ws_connect(host, path, {
        "Origin": "https://www.tradingview.com",
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/124.0 Safari/537.36",
    })
    cs = "cs_test"
    def send(m, p):
        ws_send(s, f"~m~{len(json.dumps({'m': m, 'p': p}))}~m~" + json.dumps({"m": m, "p": p}))
    send("set_auth_token", ["unauthorized_user_token"])
    send("chart_create_session", [cs, ""])
    send("resolve_symbol", [cs, "symbol_1", "=" + json.dumps({"symbol": symbol, "adjustment": "splits"})])
    send("create_series", [cs, "s1", "s1", "symbol_1", "1D", count, ""])
    bars = []
    t0 = time.time()
    while time.time() - t0 < 20:
        data, buf = ws_recv(s, buf, timeout=8)
        for m in parse_frames(data):
            if m.get("m") == "timescale_update":
                p = m.get("p") or []
                for node in (p[1] or {}).values():
                    for b in (node.get("s") or []):
                        v = b.get("v")
                        if isinstance(v, list):
                            bars.append({"t": v[0], "o": v[1], "h": v[2], "l": v[3], "c": v[4], "v": v[5]})
    s.close()
    return bars


fetch_series = fetch  # alias واضح للباك


if __name__ == "__main__":
    import sys
    sym = sys.argv[1] if len(sys.argv) > 1 else "EGX:SHARIAH"
    bars = fetch(sym, 5)
    print(f"{sym}: {len(bars)} شمعة")
    for b in bars:
        print("  ", time.strftime('%Y-%m-%d', time.gmtime(b['t'])), b['c'])
