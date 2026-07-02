#!/usr/bin/env python3
"""禅道 API 工具 - 使用 curl 避免沙箱限制。"""

import json, os, subprocess, sys, time
from pathlib import Path

D = Path.home() / ".zentao"
CFG = D / "config.json"
TK  = D / "token.json"


def load_json(p): return json.loads(p.read_text()) if p.exists() else {}
def save_json(p, d): p.parent.mkdir(parents=True, exist_ok=True); p.write_text(json.dumps(d))


def curl(method, url, headers=None, data=None):
    """统一 curl 调用，返回 dict"""
    args = ["curl", "-s", "-w", "\n%{http_code}", "-X", method, url]
    if headers:
        for k, v in headers.items():
            args.extend(["-H", f"{k}: {v}"])
    if data:
        args.extend(["-H", "Content-Type: application/json", "-d", json.dumps(data)])
    r = subprocess.run(args, capture_output=True, text=True, timeout=30)
    body, _, code = r.stdout.rpartition("\n")
    code = code.strip()
    if not body:
        raise Exception(f"HTTP {code}")
    resp = json.loads(body)
    if "error" in resp:
        raise Exception(resp["error"])
    return resp


def get_token(cfg):
    if TK.exists():
        d = json.loads(TK.read_text())
        if d.get("expires", 0) > time.time():
            return d["token"]
    try:
        r = curl("POST", f"{cfg['url']}/api.php/v1/tokens",
                  data={"account": cfg["account"], "password": cfg["password"]})
        t = r.get("token", "")
        D.mkdir(parents=True, exist_ok=True)
        TK.write_text(json.dumps({"token": t, "expires": time.time()+3600}))
        return t
    except Exception as e:
        print(f"Token 失败: {e}", file=sys.stderr)
        sys.exit(1)


def api_get(cfg, path):
    return curl("GET", f"{cfg['url']}/api.php/v1{path}", headers={"Token": get_token(cfg)})


def api_post(cfg, path, data):
    return curl("POST", f"{cfg['url']}/api.php/v1{path}", headers={"Token": get_token(cfg)}, data=data)


# ── 命令 ──

def cmd_setup(_=None):
    """初始化配置"""
    cfg = load_json(CFG)
    if not cfg.get("url"): cfg["url"] = input("禅道地址: ").strip() or ""
    if not cfg.get("account"): cfg["account"] = input("账号: ").strip() or ""
    if not cfg.get("password"): cfg["password"] = input("密码: ") or ""
    if cfg.get("url") and cfg.get("account"):
        save_json(CFG, cfg)
        t = get_token(cfg)
        print(f"✅ 配置成功, Token: {t[:8]}...")
    else:
        print("❌ 配置不完整")


def cmd_task(args):
    cfg = load_json(CFG)
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
    cfg = load_json(CFG)
    if not cfg: return print("请先 setup")
    for p in api_get(cfg, "/projects").get("projects", []):
        print(f"  #{p['id']:4s} [{p.get('status','?')}] {p['name']}")


COMMANDS = {"setup": cmd_setup, "task": cmd_task, "projects": cmd_projects}
if __name__ == "__main__":
    if len(sys.argv) < 2 or sys.argv[1] not in COMMANDS:
        print("用法: zentao <setup|task|projects> [...]"); sys.exit(1)
    COMMANDS[sys.argv[1]](sys.argv[2:])
