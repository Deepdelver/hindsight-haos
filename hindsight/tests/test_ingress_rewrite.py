#!/usr/bin/env python3
"""Regression tests for the Home Assistant ingress rewrite template.

These tests read the actual nginx.conf.template and apply its sub_filter rules
to representative HTML/JS fixtures. They catch two classes of bug that have
already shipped:

1. API path suffixes getting the ingress base injected into the middle of a
   URL (-> "Client Error / HTTP 404" in the control plane).
2. The bank-selector regex losing its ingress allowance (-> cannot select a
   bank from the dropdown).

Run: python3 hindsight/tests/test_ingress_rewrite.py
"""

import os
import re
import sys
from pathlib import Path

TEMPLATE = Path(
    os.environ.get(
        "HINDSIGHT_NGINX_TEMPLATE",
        Path(__file__).resolve().parents[1] / "rootfs/etc/nginx.conf.template",
    )
)
BASE = "/api/hassio_ingress/TEST_TOKEN"

# Rules that matter for client-side behaviour. Kept in the same order as the
# template so rule interactions are reproduced.
RULES = [
    (r'href="/', 'href="' + BASE + "/"),
    (r"href='/", "href='" + BASE + "/"),
    (r'src="/', 'src="' + BASE + "/"),
    (r"src='/", "src='" + BASE + "/"),
    (r'action="/', 'action="' + BASE + "/"),
    (r"url(/", "url(" + BASE + "/"),
    (r'"/_next/', '"' + BASE + "/_next/"),
    (r"'/_next/", "'" + BASE + "/_next/"),
    (r"`/banks", "`" + BASE + "/banks"),
    (r"`/knowledge-banks", "`" + BASE + "/knowledge-banks"),
    (r"^\\/banks\\/", "^.*\\/banks\\/"),
]


def template_text():
    return TEMPLATE.read_text()


def declared_rules():
    # nginx allows both single- and double-quoted sub_filter strings, and
    # unescapes \\ inside quoted strings before matching.
    raw = re.findall(
        r"sub_filter\s+'((?:[^'\\]|\\.)*)'\s+'((?:[^'\\]|\\.)*)'|"
        r'sub_filter\s+"((?:[^"\\]|\\.)*)"\s+"((?:[^"\\]|\\.)*)"',
        template_text(),
    )
    rules = []
    for a, b, c, d in raw:
        src, dst = (a, b) if a is not None else (c, d)
        rules.append(
            (src.replace("\\\\", "\\"), dst.replace("\\\\", "\\").replace("__BASE__", BASE))
        )
    return rules


def apply_rules(text, rules):
    for src, dst in rules:
        text = text.replace(src, dst)
    return text


def check(name, condition, detail=""):
    if condition:
        print(f"PASS  {name}")
        return True
    print(f"FAIL  {name}  {detail}")
    return False


def main():
    text = template_text()
    declared = declared_rules()
    ok = True

    ok &= check("template declares sub_filter rules", len(declared) >= 12, f"got {len(declared)}")

    # Rule 1: no JS literal rewrites that inject the base into API suffixes.
    for literal in [
        r'"/api/',
        r"'/api/",
        r"`/api/",
        r"`/memories",
        r"`/observations",
        r"`/mental-models",
        r"`/directives",
        r"`/webhooks",
    ]:
        ok &= check(
            f"no rewrite of API suffix literal {literal}",
            not any(src == literal for src, _ in declared),
        )

    # Rule 2: the two genuine navigation builders must still be rewritten.
    for literal in [r"`/banks", r"`/knowledge-banks"]:
        ok &= check(
            f"navigation rewrite present: {literal}", any(src == literal for src, _ in declared)
        )

    # Rule 3: bank selector regex must tolerate the ingress prefix.
    ok &= check(
        "bank selector regex rewrite present", any(src == r"^\/banks\/" for src, _ in declared)
    )

    # Rule 4: runtime base path must be injected into the page.
    ok &= check(
        "NEXT_PUBLIC_BASE_PATH injected into <head>",
        "NEXT_PUBLIC_BASE_PATH=B" in text and "sub_filter '<head>'" in text,
    )

    # Behavioural checks with representative payloads.
    html = '<head><link href="/_next/a.css" src="/_next/a.js">'
    out = apply_rules(html, declared)
    ok &= check("HTML assets get the ingress prefix", BASE + "/_next/a.css" in out, out)

    js = (
        "async getMemoriesTimeseries(){return fetch(`/memories-timeseries?period=7d`)}"
        "async listObservations(){return fetch(`/observations?limit=1`)}"
        "function bankUrl(id){return `/banks/${id}`}"
        "var re=/^\\/banks\\/([^/?]+)/;"
    )
    out = apply_rules(js, declared)
    ok &= check(
        "API suffix /memories-timeseries stays bare",
        "`" + BASE + "/memories-timeseries" not in out,
        out,
    )
    ok &= check("API suffix /observations stays bare", "`" + BASE + "/observations" not in out, out)
    ok &= check("bank URL builder gets the prefix", "`" + BASE + "/banks/${id}`" in out, out)
    ok &= check("bank selector regex accepts ingress prefix", "^.*\\/banks\\/" in out, out)

    print("\nRESULT:", "PASS" if ok else "FAIL")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
