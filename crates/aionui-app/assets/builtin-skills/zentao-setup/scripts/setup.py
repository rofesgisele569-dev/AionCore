#!/usr/bin/env python3
"""禅道环境初始化 — 配置存储在技能目录下。"""

import json, os, subprocess, sys, time
from pathlib import Path

D = Path.cwd() / ".zentao"
CFG = D / "config.json"
BUG = D / "bug-config.yaml"
TK  = D / "token.json"


def ld(p): return json.loads(p.read_text()) if p.exists() else {}
def sv(p, d): p.parent.mkdir(parents=True, exist_ok=True); p.write_text(json.dumps(d))


def curl(method, url, headers=None, data=None):
    args = ["curl", "-s", "-w", "\n%{http_code}", "-X", method, url]
    if headers:
        for k, v in headers.items(): args.extend(["-H", f"{k}: {v}"])
    if data: args.extend(["-H", "Content-Type: application/json", "-d", json.dumps(data)])
    r = subprocess.run(args, capture_output=True, text=True, timeout=30)
    body, _, _ = r.stdout.rpartition("\n")
    if not body: raise Exception(f"HTTP {r.stdout.strip()}")
    d = json.loads(body)
    if "error" in d: raise Exception(d["error"])
    return d


def get_token(cfg):
    if TK.exists():
        d = json.loads(TK.read_text())
        if d.get("expires", 0) > time.time(): return d["token"]
    r = curl("POST", f"{cfg['url']}/api.php/v1/tokens",
              data={"account": cfg["account"], "password": cfg["password"]})
    t = r.get("token", "")
    D.mkdir(parents=True, exist_ok=True)
    TK.write_text(json.dumps({"token": t, "expires": time.time()+3600}))
    return t


def ask(prompt, default=""):
    try: v = input(f"{prompt}: ").strip(); return v or default
    except EOFError: return default


def main():
    print("=" * 50)
    print("禅道环境初始化")
    print("=" * 50)
    cfg = ld(CFG)
    url = cfg.get("url") or os.environ.get("ZENTAO_URL", "")
    acct = cfg.get("account") or os.environ.get("ZENTAO_ACCOUNT", "")
    pw = cfg.get("password") or os.environ.get("ZENTAO_PASSWORD", "")
    chg = False
    if not url: url = ask("禅道地址"); cfg["url"] = url; chg = True
    else: print(f"✅ 地址: {url}")
    if not acct: acct = ask("账号"); cfg["account"] = acct; chg = True
    else: print(f"✅ 账号: {acct}")
    if not pw: pw = ask("密码"); cfg["password"] = pw; chg = True
    else: print("✅ 密码: ***")
    if chg: sv(CFG, cfg)

    print("\n验证连接...")
    try:
        t = get_token(cfg)
        print(f"✅ Token: {t[:8]}...")
    except Exception as e:
        print(f"❌ {e}"); return

    if not BUG.exists():
        BUG.write_text(
            "product: 1\nproject: 24\nmodule_mapping:\n"
            "  登录: [101, \"你的账号\"]\n  计费: [201, \"你的账号\"]\n"
            "  MRC:  [202, \"你的账号\"]\ndefault_assignee: \"你的账号\"\nseverity_default: 2\n"
        )
        print(f"✅ Bug 配置模板: {BUG}")

    try:
        print("\n可用项目:")
        for p in curl("GET", f"{cfg['url']}/api.php/v1/projects", headers={"Token": t}).get("projects", []):
            print(f"  ID={p['id']:4s} {p['name']}")
    except: pass
    print("\n✅ 环境就绪！")


if __name__ == "__main__":
    main()
