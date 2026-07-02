#!/usr/bin/env python3
"""禅道一键提 Bug — 配置存储在技能目录下。"""

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


def load_bug_config():
    if not BUG.exists(): return {}
    cfg = {"module_mapping": {}}
    for line in BUG.read_text().split("\n"):
        s = line.strip()
        if not s or s.startswith("#") or ":" not in s: continue
        k, _, v = s.partition(":"); k, v = k.strip(), v.strip()
        if k == "default_assignee": cfg["default_assignee"] = v.strip('"')
        elif k == "product": cfg["product"] = int(v) if v.isdigit() else v
        elif k == "project": cfg["project"] = int(v) if v.isdigit() else v
        elif k == "severity_default": cfg["severity_default"] = int(v) if v.isdigit() else v
        elif "[" in v and "]" in v:
            parts = v.strip("[]").split(",")
            if len(parts) >= 2:
                try: cfg["module_mapping"][k] = (int(parts[0].strip()), parts[1].strip().strip('"'))
                except: pass
    return cfg


def infer(title, bug):
    for kw, (mid, a) in bug.get("module_mapping", {}).items():
        if kw in title: return mid, a
    return None, bug.get("default_assignee", "")


def cmd_setup(_=None):
    if BUG.exists(): print(f"已存在: {BUG}"); return
    BUG.write_text(
        "product: 1\nproject: 24\nmodule_mapping:\n"
        "  登录: [101, \"你的账号\"]\n  计费: [201, \"你的账号\"]\n"
        "  MRC:  [202, \"你的账号\"]\ndefault_assignee: \"你的账号\"\nseverity_default: 2\n"
    )
    print(f"✅ {BUG}")


def cmd_preview(args):
    cfg = ld(CFG)
    if not cfg: print("请先 zentao setup"); return
    title = " ".join(args) if args else "请输入标题"
    bug = load_bug_config()
    mid, who = infer(title, bug)
    print(f"标题: {title}\n严重: {bug.get('severity_default',2)}\n模块: {mid or '-'}\n指派: {who or '-'}")


def cmd_submit(args):
    cfg = ld(CFG)
    if not cfg: print("请先 zentao setup"); return
    title = " ".join(args) if args else "请输入标题"
    bug = load_bug_config()
    mid, who = infer(title, bug)
    data = {
        "title": title, "product": bug.get("product",1), "project": bug.get("project",1),
        "severity": bug.get("severity_default",2), "type": "codeerror",
        "assignedTo": who or "", "steps": title,
    }
    if mid: data["module"] = mid
    try:
        token = get_token(cfg)
        r = curl("POST", f"{cfg['url']}/api.php/v1/bugs",
                 headers={"Token": token}, data=data)
        print(f"✅ Bug #{r['id']}")
    except Exception as e: print(f"❌ {e}")


COMMANDS = {"setup": cmd_setup, "preview": cmd_preview, "submit": cmd_submit}
if __name__ == "__main__":
    if len(sys.argv) < 2 or sys.argv[1] not in COMMANDS:
        print("用法: zentao-bug <setup|preview|submit> [标题]"); sys.exit(1)
    COMMANDS[sys.argv[1]](sys.argv[2:])
