---
name: billing-troubleshoot
description: Diagnose SM81 billing issues — wrong charges, missing refunds, BS errors, rebate problems, MRC miscalculations. Use when user reports a billing anomaly.
---

# 账务异常排查

5 步标准流程。详见 [RUNBOOK.md](RUNBOOK.md)、[docs/BILLING_MASTER.md](docs/BILLING_MASTER.md)。

## 快速流程

**Step 0 分诊** → 月租?退费?BS?挂起复机?

**Step 1 定位** → CC.SUBS → CC.ACCT → CC.BILLING_CYCLE, 拿 (SUBS_ID, ACCT_ID, CYCLE_ID)

**Step 2 拉话单** → RB.EVENT_RECURRING_${CYCLE}, 逐行看金额/SELF_FLAG/ATTR_LIST[1329]

**Step 3 时间对齐** → CRM.ORDER_ITEM → CC.ASYN_CALL_TO_BILLING → EVENT_RECURRING

**Step 4 根因** → 少行=漏消息 | 多行=dealMode交叉 | PAID错=BS到期 | 金额错=OFFER_VER/proration

**Step 5 报告** → 6 节: 账号+链路+话单逐行表+时间对齐表+根因+修复方向

## 经典案例

详见 [cases/](cases/) 目录。
