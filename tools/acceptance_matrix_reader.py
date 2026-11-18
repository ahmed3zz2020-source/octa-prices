#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
acceptance_matrix_reader.py — قارئ مصفوفة القبول (OCTA)

الهدف: قراءة مصفوفة القبول الأصلية للمالك لما توصل — سواء Excel أو نص —
واستخراج: معرّف النطاق · عنوان النطاق · بنود القبول (رقم + نص) ·
الدليل · البصمة (sha) · الحالة · الملاحظات.

⛔ الأداة دي **قارئة فقط**: مش بتكتب في المصفوفة، ومش بتخترع أي صف.
⛔ مفيش أرقام ولا عناصر مخترعة: كل اللي بيظهر جاي من الملف نفسه.
⛔ لو النطاق مافيهوش بنود ⇒ ده **معلومة** (مش خطأ) — بيتبلّغ في التقرير.

صيغ الملفات المدعومة:
   · .xlsx  → عبر openpyxl (أول شيت فيها بيانات)
   · .txt / .md / .csv / .tsv  → جدول (pipe/tab/;) أو نص مقسّم لنطاقات وبنود

 autodetect: الصيغة بتتحدّد من الامتداد، والأعمدة بتتحدّد من **نص الهيدر**
 (مش من ترتيب الأعمدة) — يعني لو المالك غيّر أسماء الأعمدة أو ترتيبها
 أو كتبها بالعربي أو بالإنجليزي، الأداة لسه هتشتغل.

استعمال:
   python3 acceptance_matrix_reader.py <file> [--json out.json] [--quiet]
"""
from __future__ import annotations

import argparse
import csv
import json
import os
import re
import sys

# ══════════════════════════════════════════════════════════════════════
# 1) تطبيع النص + كلمات مفتاحية لاكتشاف الأعمدة (عربي + إنجليزي)
# ══════════════════════════════════════════════════════════════════════

_TATWEEL = "\u0640"
_DIACRITICS = re.compile(r"[\u0610-\u061A\u064B-\u065F\u0670\u06D6-\u06ED]")
_NON_WORD = re.compile(r"[^0-9a-z\u0600-\u06FF]+")


def normalize(text) -> str:
    """يوحّد شكل النص عشان المطابقة تبقى متسامحة مع الإملاء والتنسيق."""
    s = "" if text is None else str(text)
    s = s.replace(_TATWEEL, "")
    s = _DIACRITICS.sub("", s)
    s = s.lower()
    for a, b in (("\u0623", "\u0627"), ("\u0625", "\u0627"), ("\u0622", "\u0627"),
                 ("\u0624", "\u0648"), ("\u0626", "\u064a"), ("\u0649", "\u064a"),
                 ("\u0629", "\u0647"), ("\u06a9", "\u0643")):
        s = s.replace(a, b)
    s = s.replace("|", " ").replace(":", " ").replace("/", " ")
    s = _NON_WORD.sub(" ", s)
    return re.sub(r"\s+", " ", s).strip()


# كل دور (role) و الكلمات اللي بتدل عليه — الأطول/الأدق بوزن أعلى
ROLE_KEYWORDS = {
    "scope_id": [
        "معرف النطاق", "رقم النطاق", "كود النطاق", "معرّف النطاق",
        "scope id", "scope code", "scope key", "scope no", "scope",
        "النطاق", "نطاق", "معرف", "رقم", "id", "code", "كود", "ref",
    ],
    "scope_title": [
        "عنوان النطاق", "اسم النطاق", "نطاق العمل",
        "scope title", "scope name", "scope description", "title",
        "الاسم", "عنوان", "وصف", "name", "desc",
    ],
    "item_id": [
        "رقم البند", "معرف البند", "كود البند", "رقم المتطلب", "معرف المتطلب",
        "item id", "item code", "acceptance id", "requirement id",
        "معرف", "رقم", "كود", "id", "code", "ref", "req",
    ],
    "item_text": [
        "بند القبول", "نص البند", "بند", "شرط", "معيار", "المعيار", "الشروط",
        "المتطلبات", "نص", "الوصف",
        "acceptance item", "acceptance criteria", "acceptance", "criterion",
        "criteria", "requirement", "statement", "description", "item", "text",
    ],
    "evidence": [
        "دليل", "الدليل", "اثبات", "إثبات", "مصدر", "مرجع", "اختبار",
        "evidence", "proof", "reference", "source", "test", "link", "url", "file",
    ],
    "sha": [
        "بصمة", "البصمة", "بصمة الدليل", "هاش", "توقيع",
        "sha", "sha256", "sha1", "hash", "checksum", "signature", "digest",
    ],
    "status": [
        "الحالة", "حالة", "وضع", "انجاز", "منجز", "مكتمل",
        "status", "state", "done", "progress",
    ],
    "notes": [
        "ملاحظات", "ملاحظة", "تعليق", "تنبيه",
        "notes", "note", "remarks", "comment", "comments",
    ],
}

# ترتيب الأعمدة المتوقعة لو الملف مالوش هيدر خالص (position fallback)
POSITIONAL_ORDER = ["scope_id", "scope_title", "item_id", "item_text",
                    "evidence", "sha", "status", "notes"]
POSITIONAL_BY_COUNT = {
    1: ["item_text"],
    2: ["scope_id", "item_text"],
    3: ["scope_id", "item_id", "item_text"],
    4: ["scope_id", "scope_title", "item_id", "item_text"],
    5: ["scope_id", "scope_title", "item_id", "item_text", "evidence"],
    6: ["scope_id", "scope_title", "item_id", "item_text", "evidence", "sha"],
    7: ["scope_id", "scope_title", "item_id", "item_text", "evidence", "sha", "status"],
    8: POSITIONAL_ORDER,
}


def score_header(header_text):
    """ بيرجّع {role: score} — أعلى score = تسمية أدق."""
    h = normalize(header_text)
    if not h:
        return {}
    out = {}
    for role, kws in ROLE_KEYWORDS.items():
        best = 0
        for kw in kws:
            nk = normalize(kw)
            if not nk:
                continue
            if h == nk:
                s = 100 + len(nk)
            elif nk in h:
                # أدق = أطول = أعلى
                s = 10 * len(nk.split()) + len(nk)
            else:
                continue
            if s > best:
                best = s
        if best:
            out[role] = best
    return out


def pick_roles(headers):
    """ يوزّع الأعمدة على الأدوار بأعلى score، كل عمود لدور واحد بس."""
    scores = [score_header(h) for h in headers]
    pairs = []
    for idx, sc in enumerate(scores):
        for role, val in sc.items():
            pairs.append((val, idx, role))
    pairs.sort(key=lambda p: (-p[0], p[1], p[2]))
    roles, used = {}, set()
    for val, idx, role in pairs:
        if idx in used or role in roles:
            continue
        roles[role] = idx
        used.add(idx)
    return roles, scores


# ══════════════════════════════════════════════════════════════════════
# 2) أدوات عامة
# ══════════════════════════════════════════════════════════════════════

def cell_text(v):
    if v is None:
        return ""
    if isinstance(v, float) and v.is_integer():
        return str(int(v))
    return str(v).strip()


def is_separator_row(cells):
    """ صف فاصل في الجداول (------ أو :---:) """
    filled = [cell_text(c) for c in cells]
    if not filled:
        return False
    return all(re.fullmatch(r"[:\-\s]+", cell_text(c) or " ") for c in filled)


def is_blank_row(cells):
    return not any(cell_text(c) for c in cells)


def pick_text_column(rows, headers):
    """ لو مفيش عمود نص بند، اختار أعمى عمود فيه نص أطول."""
    best, best_len = None, 0
    for idx, _h in enumerate(headers):
        longest = 0
        for r in rows:
            if idx < len(r):
                longest = max(longest, len(cell_text(r[idx])))
        if longest > best_len:
            best, best_len = idx, longest
    return best


# ══════════════════════════════════════════════════════════════════════
# 3) قراءة XLSX
# ══════════════════════════════════════════════════════════════════════

def read_xlsx(path):
    try:
        import openpyxl
    except ImportError:
        raise SystemExit("ERROR: openpyxl is required to read .xlsx files "
                         "(pip install openpyxl) — or provide the .txt fallback")

    wb = openpyxl.load_workbook(path, data_only=True, read_only=True)
    try:
        sheet_name, grid = None, []
        for ws in wb.worksheets:
            rows = [[cell_text(c) for c in row] for row in ws.iter_rows(values_only=True)]
            rows = [r for r in rows if not is_blank_row(r)]
            if rows:
                sheet_name = ws.title
                grid = rows
                break
        if not grid:
            return [], None, [], "empty workbook (no non-empty sheet)"
    finally:
        wb.close()

    header_idx, headers, scores = find_header_row(grid)
    if header_idx is None:
        return grid, sheet_name, [], ("no recognisable header row found in the "
                                      "first 40 rows (need at least 2 columns "
                                      "matching id/title/item keywords)")
    preamble = grid[:header_idx]
    body = grid[header_idx + 1:]
    body = [r for r in body if not is_blank_row(r) and not is_separator_row(r)]
    return body, sheet_name, headers, preamble


def find_header_row(grid):
    """ يختار صف الهيدر: اللي فيه أكتر كلمات مفتاحية معروفة."""
    best_idx, best_headers, best_scores, best_total = None, [], [], 0
    for i, row in enumerate(grid[:40]):
        cells = [cell_text(c) for c in row]
        if is_separator_row(cells) or is_blank_row(cells):
            continue
        headers = list(cells)
        scores = [score_header(h) for h in headers]
        total = sum(max(s.values()) for s in scores if s)
        n_roles = len({r for s in scores for r in s})
        if n_roles >= 2 and total > best_total:
            best_idx, best_headers, best_scores, best_total = i, headers, scores, total
    return best_idx, best_headers, best_scores


# ══════════════════════════════════════════════════════════════════════
# 4) قراءة النصوص
# ══════════════════════════════════════════════════════════════════════

def split_pipe_line(line):
    return [p.strip() for p in line.strip().strip("|").split("|")]


def looks_like_table(lines):
    pipe = [i for i, l in enumerate(lines) if l.count("|") >= 2]
    if len(pipe) >= 2:
        return "pipe", pipe
    for delim in ("\t", ";", ","):
        hits = [i for i, l in enumerate(lines) if l.count(delim) >= 2]
        if len(hits) >= 2:
            return delim, hits
    return None, []


def read_csv(path):
    with open(path, "r", encoding="utf-8-sig", newline="") as fh:
        rows = [[cell_text(c) for c in r] for r in csv.reader(fh)]
    return [r for r in rows if not is_blank_row(r)]


BULLET_RE = re.compile(r"^\s*[-*\u2022\u2023\u25AA+\u2013]\s+(?P<body>.+?)\s*$")
NUM_ITEM_RE = re.compile(r"^\s*(?P<id>\d{1,3}[.)])\s*(?P<body>.+?)\s*$")
ID_ITEM_RE = re.compile(r"^\s*(?P<id>[A-Za-z]{1,8}[-_ ]?\d{1,5})\s*[:.\u2013-]\s*(?P<body>.+?)\s*$")
ID_ONLY_RE = re.compile(r"^[A-Za-z]{1,8}[-_]?\d{1,5}$")
IDISH_RE = re.compile(r"^[A-Za-z0-9\u0600-\u06FF]{0,10}[-._]?\d{1,5}([.]\d{1,3})?$")
SCOPE_FALLBACK_RE = re.compile(
    r"^\s*(?P<id>[A-Za-z0-9\u0600-\u06FF]{0,10}[-._]?\d{1,5})\s*[-–—:]\s+(?P<title>.+?)\s*$")
SCOPE_WORDS = ("scope", "section", "chapter", "gate", "area", "domain",
               "النطاق", "نطاق", "مجال", "محور", "قسم", "بوابة")
SEPS = " \t-\u2013\u2014:|\u2500-\u257F"


def extract_table(lines):
    """ أكبر كتلة أسطر جدولية متتالية (pipe / tab / ؛ / ,) — أو None."""
    kind, _hits = looks_like_table(lines)
    if not kind:
        return None
    token = "|" if kind == "pipe" else kind
    block, cur = [], []
    for l in lines:
        if l.count(token) >= 2:
            cur.append(l)
        else:
            if len(cur) > len(block):
                block = cur
            cur = []
    if len(cur) > len(block):
        block = cur
    rows = []
    for l in block:
        if kind == "pipe":
            rows.append(split_pipe_line(l))
        else:
            rows.append([cell_text(x) for x in l.split(kind)])
    rows = [r for r in rows if not is_blank_row(r) and not is_separator_row(r)]
    return rows or None


def row_is_header_like(row):
    """ هل السطر ده هيدر فعلاً؟ (مش سطر بيانات فيه كلمات مفتاحية بالصدفة)"""
    scores = [score_header(c) for c in row]
    distinct = {r for s in scores for r in s}
    structural = distinct & {"scope_id", "scope_title", "item_id", "item_text"}
    if len(distinct) < 3:
        return False
    max_words = max((len(normalize(c).split()) for c in row), default=0)
    # هيدر حقيقي: أعمدة بنيوية (نطاق/بند) — أو أعمدة قصيرة بتسمية واضحة
    if len(structural) >= 3:
        return True
    return len(structural) >= 2 and max_words <= 3


def parse_scope_line(line):
    """ سطر نطاق ⇒ (scope_id, scope_title) أو None"""
    for w in SCOPE_WORDS:
        m = re.search(re.escape(w), line, re.IGNORECASE)
        if not m:
            continue
        rest = line[m.end():].strip(SEPS)
        mid = re.match(r"([A-Za-z\u0600-\u06FF]{0,8}[-_]?\d{1,4})\b", rest)
        if not mid:
            continue
        sid = re.sub(r"\s+", "", mid.group(1))
        title = rest[mid.end():].strip(SEPS)
        if not title:
            continue
        return sid, title
    # fallback: سطر "<معرّف> - عنوان" من غير كلمة نطاق (بس من غير أنابيب)
    if "|" not in line:
        m = SCOPE_FALLBACK_RE.match(line)
        if m:
            return re.sub(r"\s+", "", m.group("id")), m.group("title").strip()
    return None


def parse_item_line(line):
    """ سطر بند ⇒ (item_id, text, extra_fields) أو None"""
    if "|" in line:
        parts = [p.strip() for p in line.split("|")]
        if len(parts) >= 2 and IDISH_RE.match(parts[0]):
            return parts[0], parts[1], parts[2:]
    mb = BULLET_RE.match(line)
    if mb:
        body = mb.group("body")
    else:
        mi = NUM_ITEM_RE.match(line)
        mid = ID_ITEM_RE.match(line)
        if mi:
            body = mi.group("body")
        elif mid:
            return (re.sub(r"\s+", "", mid.group("id")),
                    mid.group("body").strip(), [])
        else:
            return None
    if "|" in body:
        parts = [p.strip() for p in body.split("|")]
        if IDISH_RE.match(parts[0]) and len(parts) > 1:
            return parts[0], parts[1], parts[2:]
        return "", parts[0], parts[1:]
    return "", body, []


def extract_sections(lines):
    """ نص مقسّم: سطر نطاق + بنود تحته — (rows, scopes_raw, preamble) أو None"""
    scopes, cur, preamble, rows = [], None, [], []
    started = False
    for raw in lines:
        line = raw.rstrip()
        if not line.strip():
            continue
        sc = parse_scope_line(line)
        if not started:
            if sc:
                started = True
                cur = {"scope_id": sc[0], "scope_title": sc[1], "lines": []}
                scopes.append(cur)
            else:
                preamble.append(line)
            continue
        if sc and not BULLET_RE.match(line):
            cur = {"scope_id": sc[0], "scope_title": sc[1], "lines": []}
            scopes.append(cur)
            continue
        parsed_item = parse_item_line(line)
        if parsed_item is None:
            continue
        item_id, text, extra = parsed_item
        if not text:
            continue
        rows.append({
            "_row": len(rows) + 1,
            "scope_id": cur["scope_id"], "scope_title": cur["scope_title"],
            "item_id": item_id, "item_text": text,
            "evidence": extra[0] if len(extra) > 0 else "",
            "sha": extra[1] if len(extra) > 1 else "",
            "status": extra[2] if len(extra) > 2 else "",
            "notes": extra[3] if len(extra) > 3 else "",
        })
    if not started:
        return None
    return rows, scopes, preamble


def read_text(path):
    """ جدول (pipe/tab/;) أو نص مقسّم لنطاقات وبنود."""
    with open(path, "r", encoding="utf-8-sig") as fh:
        raw = fh.read()
    lines = raw.splitlines()

    table = extract_table(lines)
    if table:
        hidx, headers, _scores = find_header_row(table)
        if hidx is not None and row_is_header_like(table[hidx]):
            return {"mode": "header-row", "headers": headers,
                    "body": table[hidx + 1:], "preamble": table[:hidx],
                    "rows": None, "scopes_raw": None}

    sections = extract_sections(lines)
    if sections:
        rows, scopes_raw, preamble = sections
        return {"mode": "sections", "headers": [], "body": [],
                "preamble": preamble, "rows": rows, "scopes_raw": scopes_raw}

    if table:
        return {"mode": "inferred-positional", "headers": table[0],
                "body": table[1:], "preamble": [], "rows": None,
                "scopes_raw": None}

    return {"mode": "empty", "headers": [], "body": [], "preamble": lines,
            "rows": [], "scopes_raw": []}


# ══════════════════════════════════════════════════════════════════════
# 5) التوحيد: صفوف موحّدة + تجميع النطاقات
# ══════════════════════════════════════════════════════════════════════

def build_rows(body, headers, roles, positional=False):
    rows = []

    def val(r, role):
        idx = roles.get(role)
        if idx is None or idx >= len(r):
            return ""
        return cell_text(r[idx])

    if not roles:
        order = POSITIONAL_BY_COUNT.get(min(len(headers), 8), POSITIONAL_ORDER)
        roles = {role: i for i, role in enumerate(order)}
        positional = True

    if roles.get("item_text") is None:
        text_col = pick_text_column(body, headers)
        if text_col is not None:
            roles["item_text"] = text_col

    for i, r in enumerate(body, start=1):
        item_text = val(r, "item_text")
        if not item_text:
            continue
        rows.append({
            "_row": i,
            "scope_id": val(r, "scope_id"),
            "scope_title": val(r, "scope_title"),
            "item_id": val(r, "item_id"),
            "item_text": item_text,
            "evidence": val(r, "evidence"),
            "sha": val(r, "sha"),
            "status": val(r, "status"),
            "notes": val(r, "notes"),
        })
    return rows, positional


def group_scopes(rows, scopes_raw=None):
    """ يجمّع البنود في نطاقات — بنفس المعرّف أو العنوان."""
    order, buckets = [], {}
    for r in rows:
        key = (r.get("scope_id") or "", r.get("scope_title") or "")
        if key not in buckets:
            buckets[key] = {"scope_id": r.get("scope_id") or "",
                            "scope_title": r.get("scope_title") or "",
                            "items": []}
            order.append(key)
        buckets[key]["items"].append(r)

    scopes = [buckets[k] for k in order]

    # نطاقات مُعلَنة بس بدون بنود (من صيغة النطاقات) — تُبلّغ، مش خطأ
    if scopes_raw:
        seen = {(s["scope_id"], s["scope_title"]) for s in scopes}
        for raw in scopes_raw:
            key = (raw.get("scope_id") or "", raw.get("scope_title") or "")
            if key in seen:
                continue
            seen.add(key)
            scopes.append({"scope_id": raw.get("scope_id") or "",
                           "scope_title": raw.get("scope_title") or "",
                           "items": []})

    for n, s in enumerate(scopes, start=1):
        if not s["scope_id"]:
            s["scope_id"] = "SCOPE-%02d" % n
            s["scope_id_generated"] = True
        if not s["scope_title"]:
            s["scope_title"] = s["scope_id"]
    return scopes


def build_report(source, rows, scopes, columns, warnings, fmt, sheet=None):
    return {
        "source": source,
        "scopes": len(scopes),
        "items": len(rows),
        "rows": rows,
        "scope_details": [
            {
                "scope_id": s["scope_id"],
                "scope_title": s["scope_title"],
                "items": len(s["items"]),
                "item_ids": [i.get("item_id") or "" for i in s["items"]],
                "has_items": bool(s["items"]),
                "scope_id_generated": bool(s.get("scope_id_generated")),
            } for s in scopes
        ],
        "scopes_without_items": [s["scope_id"] for s in scopes if not s["items"]],
        "columns": columns,
        "format": fmt,
        "sheet": sheet,
        "warnings": warnings,
        "generator": "acceptance_matrix_reader.py",
    }


# ══════════════════════════════════════════════════════════════════════
# 6) الجدول المختصر في الـstdout
# ══════════════════════════════════════════════════════════════════════

def print_summary(report):
    out = sys.stdout
    out.write("=" * 78 + "\n")
    out.write("  ACCEPTANCE MATRIX READER — SUMMARY\n")
    out.write("=" * 78 + "\n")
    out.write("  source : %s\n" % report["source"])
    out.write("  format : %s%s\n" % (report["format"],
                                    (" (sheet: %s)" % report["sheet"]) if report.get("sheet") else ""))
    out.write("  scopes : %d\n" % report["scopes"])
    out.write("  items  : %d\n" % report["items"])
    cols_meta = report.get("columns", {})
    roles = cols_meta.get("roles", {})
    if roles:
        cols = cols_meta.get("headers", [])
        out.write("  columns detected:\n")
        for role, idx in sorted(roles.items(), key=lambda kv: kv[1]):
            head = cols[idx] if idx < len(cols) else "?"
            out.write("      %-12s <- col %d : %s\n" % (role, idx, head))
    if cols_meta.get("positional"):
        out.write("  (header row not recognised — columns mapped by position)\n")
    out.write("-" * 78 + "\n")
    hdr = "%-14s %-6s %s" % ("SCOPE ID", "ITEMS", "SCOPE TITLE")
    out.write("  " + hdr + "\n")
    out.write("  " + "-" * (len(hdr) + 6) + "\n")
    for s in report["scope_details"]:
        flag = "" if s["has_items"] else "   <-- NO ITEMS (reported, not an error)"
        out.write("  %-14s %-6s %s%s\n" % (s["scope_id"], s["items"], s["scope_title"], flag))
    out.write("-" * 78 + "\n")
    for s in report["scope_details"]:
        if not s["items"]:
            continue
        out.write("  [%s] %s\n" % (s["scope_id"], s["scope_title"]))
        for r in report["rows"]:
            if (r.get("scope_id") or "") != s["scope_id"]:
                continue
            bits = []
            if r.get("item_id"):
                bits.append("id=%s" % r["item_id"])
            if r.get("evidence"):
                bits.append("evidence=%s" % r["evidence"])
            if r.get("sha"):
                bits.append("sha=%s" % r["sha"])
            if r.get("status"):
                bits.append("status=%s" % r["status"])
            if r.get("notes"):
                bits.append("notes=%s" % r["notes"])
            out.write("      - %s%s\n" % (r.get("item_text", ""),
                                          ("   [" + " | ".join(bits) + "]") if bits else ""))
    if report.get("warnings"):
        out.write("-" * 78 + "\n")
        for w in report["warnings"]:
            out.write("  WARNING: %s\n" % w)
    out.write("=" * 78 + "\n")
    out.write("  RESULT: scopes=%d items=%d\n" % (report["scopes"], report["items"]))
    out.write("=" * 78 + "\n")


# ══════════════════════════════════════════════════════════════════════
# 7) main
# ══════════════════════════════════════════════════════════════════════

def parse_file(path):
    ext = os.path.splitext(path)[1].lower()
    warnings = []
    roles, scores, headers, body, rows, scopes_raw = {}, [], [], [], None, None
    sheet = None

    if ext == ".xlsx":
        body, sheet, headers, extra = read_xlsx(path)
        fmt = "xlsx"
        if isinstance(extra, str):
            raise SystemExit("ERROR: %s" % extra)
        roles, scores = pick_roles(headers) if headers else ({}, [])
    elif ext == ".csv":
        grid = read_csv(path)
        hidx, headers, _ = find_header_row(grid)
        if hidx is None:
            headers = grid[0] if grid else []
            body = grid[1:]
            warnings.append("no recognisable header row — columns mapped by position")
        else:
            headers = grid[hidx]
            body = grid[hidx + 1:]
        fmt = "csv"
        roles, scores = pick_roles(headers) if headers else ({}, [])
    elif ext in (".txt", ".md", ".markdown", ".tsv", ""):
        parsed = read_text(path)
        fmt = "text"
        headers = parsed["headers"]
        body = parsed["body"]
        rows = parsed["rows"]
        scopes_raw = parsed["scopes_raw"]
        if parsed["mode"] == "inferred-positional":
            warnings.append("no recognisable header row — columns mapped by position")
        elif parsed["mode"] == "empty":
            warnings.append("no table and no scope sections found in the file")
        roles, scores = pick_roles(headers) if headers else ({}, [])
    else:
        raise SystemExit("ERROR: unsupported extension '%s' for %s — "
                         "expected .xlsx, .txt, .md or .csv" % (ext, path))

    positional = False
    parse_mode = "table"
    if rows is None:
        rows, positional = build_rows(body, headers, roles)
        if not positional and roles.get("item_id") is None:
            counters = {}
            for r in rows:
                key = r.get("scope_id") or ""
                counters[key] = counters.get(key, 0) + 1
                r["item_id"] = "%s-%02d" % (key or "ITEM", counters[key])
            warnings.append("no item-id column found — item ids generated sequentially")
    else:
        # صيغة النطاقات: الحقول جاية من البنية نفسها (مش من أعمدة)
        parse_mode = "sections"
        roles, scores = {}, []

    scopes = group_scopes(rows, scopes_raw)
    empty = [s["scope_id"] for s in scopes if not s["items"]]
    if empty:
        warnings.append("scope(s) with no acceptance items: %s" % ", ".join(empty))

    columns = {
        "headers": headers,
        "roles": roles,
        "role_scores": {str(i): s for i, s in enumerate(scores)},
        "positional": positional,
    }
    report = build_report(os.path.abspath(path), rows, scopes, columns,
                          warnings, fmt, sheet)
    report["parse_mode"] = parse_mode
    return report


def main(argv=None):
    ap = argparse.ArgumentParser(description="Read an acceptance matrix (.xlsx/.txt/.csv)")
    ap.add_argument("path", help="path to the matrix file")
    ap.add_argument("--json", dest="json_path", default=None,
                    help="also write the JSON report to this path")
    ap.add_argument("--quiet", action="store_true", help="suppress the summary table")
    args = ap.parse_args(argv)

    path = args.path
    if not os.path.exists(path):
        sys.stderr.write("ERROR: file not found: %s\n" % path)
        return 2
    if os.path.isdir(path):
        sys.stderr.write("ERROR: expected a file, got a directory: %s\n" % path)
        return 2
    if not os.access(path, os.R_OK):
        sys.stderr.write("ERROR: file is not readable: %s\n" % path)
        return 2

    try:
        report = parse_file(path)
    except SystemExit:
        raise
    except Exception as exc:  # noqa: BLE001
        sys.stderr.write("ERROR: failed to parse %s: %s: %s\n"
                         % (path, type(exc).__name__, exc))
        return 3

    if not args.quiet:
        print_summary(report)
    payload = json.dumps(report, ensure_ascii=False, indent=2)
    if args.json_path:
        with open(args.json_path, "w", encoding="utf-8") as fh:
            fh.write(payload + "\n")
        sys.stderr.write("JSON report written to %s\n" % args.json_path)
    else:
        sys.stdout.write(payload + "\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
