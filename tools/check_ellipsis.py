#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""🔍 فحص عامل Ellipsis ( السطر المقطوع ) في كود الإنتاج.

📌 ليه الفحص ده موجود: أي `...` في الكود (مش في الكومنت ولا النصوص)
   almost-permanent علامة إن سطر اتلصق ناقص — والـCI القديم كان بيفشل
   على ٣ سطور كومنت/دوكسترنج في main (الفلتر '^\\s*#' ماكانش بيشتغل).

✅ الفحص دقيق: tokenize بيفصل الكود عن الكومنت والنصوص ⇒ نعدّ
   السطر المقطوع بس.
"""
import ast
import io
import sys
import tokenize

TARGETS = ["update_prices.py"]


def check(path):
    src = open(path, encoding="utf-8").read()
    bad = []
    for tok in tokenize.generate_tokens(io.StringIO(src).readline):
        if tok.type == tokenize.OP and tok.string == "...":
            bad.append(tok.start[0])
    for node in ast.walk(ast.parse(src)):
        if isinstance(node, ast.Constant) and node.value is Ellipsis:
            bad.append(node.lineno)
    return sorted(set(bad))


def main(argv=None):
    args = list(argv if argv is not None else sys.argv[1:])
    targets = args or TARGETS
    failed = False
    for path in targets:
        try:
            bad = check(path)
        except Exception as e:
            print("⚠️ %s: %s" % (path, e))
            continue
        if bad:
            print("❌ %s: لقيت ... في سطور %s" % (path, bad))
            failed = True
        else:
            print("✅ %s: مفيش أنماط غلط" % path)
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
