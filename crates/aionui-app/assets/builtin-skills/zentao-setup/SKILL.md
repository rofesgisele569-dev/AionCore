---
name: zentao-setup
description: Initialize Zendao connection — configure URL, account, token, project, and bug module mapping. Use when user wants to set up Zendao for the first time or reconfigure.
---

# 禅道环境初始化

首次使用，引导用户配置禅道连接：

```bash
python3 scripts/setup.py
```

自动检测已有配置，缺什么补什么（地址/账号/Token/项目）。
