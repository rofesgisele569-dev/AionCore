#!/usr/bin/env python3
"""禅道 API 工具 — 配置存储在技能目录下。"""

import json, os, subprocess, sys, time
from pathlib import Path

D = Path.cwd() / ".zentao"
CFG = D / "config.json"
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


def api_get(cfg, path):
    return curl("GET", f"{cfg['url']}/api.php/v1{path}", headers={"Token": get_token(cfg)})


def api_post(cfg, path, data):
    return curl("POST", f"{cfg['url']}/api.php/v1{path}", headers={"Token": get_token(cfg)}, data=data)


def cmd_setup(_=None):
    cfg = ld(CFG)
    if not cfg.get("url"): cfg["url"] = input("禅道地址: ").strip() or ""
    if not cfg.get("account"): cfg["account"] = input("账号: ").strip() or ""
    if not cfg.get("password"): cfg["password"] = input("密码: ") or ""
    if cfg.get("url") and cfg.get("account"):
        sv(CFG, cfg)
        t = get_token(cfg)
        print(f"✅ 配置成功, Token: {t[:8]}...")
    else: print("❌ 配置不完整")


def cmd_task(args):
    cfg = ld(CFG)
    if not cfg: return print("请先 setup")
    if not args or args[0] == "list":
        data = api_get(cfg, "/tasks")
        for t in data.get("tasks", []):
            print(f"#{t['id']} [{t.get('status','?')}] {t['name']} | {t.get('assignedTo','?')}")
        if not data.get("tasks"): print("(无)")
        return
    tid = args[0]
    t = api_get(cfg, f"/tasks/{tid}")
    print(f"#{t['id']}: {t['name']}")
    print(f"  状态:{t.get('status','?')} 指派:{t.get('assignedTo','?')} 预估:{t.get('estimate','?')}h")


def cmd_projects(_):
    cfg = ld(CFG)
    if not cfg: return print("请先 setup")
    for p in api_get(cfg, "/projects").get("projects", []):
        print(f"  #{p['id']:4s} [{p.get('status','?')}] {p['name']}")


COMMANDS = {"setup": cmd_setup, "task": cmd_task, "projects": cmd_projects}
if __name__ == "__main__":
    if len(sys.argv) < 2 or sys.argv[1] not in COMMANDS:
        print("用法: zentao <setup|task|projects> [...]"); sys.exit(1)
    COMMANDS[sys.argv[1]](sys.argv[2:])
