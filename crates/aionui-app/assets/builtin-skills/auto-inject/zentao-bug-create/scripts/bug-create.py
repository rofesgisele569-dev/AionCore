#!/usr/bin/env python3
"""禅道一键提 Bug — 依赖 zentao-task 的 setup 已完成。

用法:
  zentao-bug setup    生成 bug-config.yaml 模板
  zentao-bug preview <标题>  预览模块匹配
  zentao-bug submit <标题>   提交 Bug
"""

import json
import os
import sys
from pathlib import Path
from urllib.request import Request, urlopen

CONFIG_DIR = Path.home() / ".zentao"
CONFIG_FILE = CONFIG_DIR / "config.json"
BUG_CONFIG_FILE = CONFIG_DIR / "bug-config.yaml"
TOKEN_FILE = CONFIG_DIR / "token.json"


def load_json(path):
    if path.exists(): return json.loads(path.read_text())
    return {}


def get_token(cfg):
    import time
    if TOKEN_FILE.exists():
        data = json.loads(TOKEN_FILE.read_text())
        if data.get("expires", 0) > time.time():
            return data["token"]
    req = Request(
        f"{cfg['url']}/api.php/v1/tokens",
        data=json.dumps({"account": cfg["account"], "password": cfg["password"]}).encode(),
        headers={"Content-Type": "application/json"}, method="POST",
    )
    resp = json.loads(urlopen(req, timeout=10).read())
    token = resp.get("token", "")
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    TOKEN_FILE.write_text(json.dumps({"token": token, "expires": time.time() + 3600}))
    return token


def load_bug_config():
    if not BUG_CONFIG_FILE.exists(): return {}
    content = BUG_CONFIG_FILE.read_text()
    cfg = {"module_mapping": {}}
    for line in content.split("\n"):
        s = line.strip()
        if s.startswith("#") or not s or ":" not in s: continue
        k, _, v = s.partition(":")
        k, v = k.strip(), v.strip()
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


def infer(title, bug_cfg):
    for kw, (mid, a) in bug_cfg.get("module_mapping", {}).items():
        if kw in title: return mid, a
    return None, bug_cfg.get("default_assignee", "")


# ── commands ──

def cmd_setup(_=None):
    if BUG_CONFIG_FILE.exists():
        print(f"已存在: {BUG_CONFIG_FILE}")
        return
    tpl = (
        "product: 1\nproject: 24\nmodule_mapping:\n"
        "  登录: [101, \"你的账号\"]\n  计费: [201, \"你的账号\"]\n"
        "  MRC:  [202, \"你的账号\"]\ndefault_assignee: \"你的账号\"\nseverity_default: 2\n"
    )
    BUG_CONFIG_FILE.write_text(tpl)
    print(f"✅ {BUG_CONFIG_FILE}\n请编辑填入实际模块ID")

def cmd_preview(args):
    cfg = load_json(CONFIG_FILE)
    if not cfg: print("请先运行 zentao.py setup"); return
    title = " ".join(args) if args else "请输入标题"
    bug = load_bug_config()
    mid, who = infer(title, bug)
    print(f"标题: {title}\n严重: {bug.get('severity_default',2)}\n模块: {mid or '-'}\n指派: {who or '-'}")

def cmd_submit(args):
    cfg = load_json(CONFIG_FILE)
    if not cfg: print("请先运行 zentao.py setup"); return
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
        req = Request(f"{cfg['url']}/api.php/v1/bugs", data=json.dumps(data).encode(),
            headers={"Token": token, "Content-Type": "application/json"}, method="POST")
        r = json.loads(urlopen(req, timeout=30).read())
        print(f"✅ Bug #{r['id']} 创建成功\n   {cfg['url']}/zentao/bug-view-{r['id']}.html")
    except Exception as e: print(f"❌ {e}")

COMMANDS = {"setup": cmd_setup, "preview": cmd_preview, "submit": cmd_submit}
if __name__ == "__main__":
    if len(sys.argv) < 2 or sys.argv[1] not in COMMANDS: print("用法: zentao-bug <setup|preview|submit> [标题]"); sys.exit(1)
    COMMANDS[sys.argv[1]](sys.argv[2:])
