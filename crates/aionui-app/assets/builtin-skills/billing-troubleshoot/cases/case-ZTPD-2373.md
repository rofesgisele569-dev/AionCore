# Case ZTPD-2373 — 多次挂起/复机 ASYN_CALL 漏发 + RecurrRate previousState 限制

## 元信息

| | |
|---|---|
| JIRA | [ZTPD-2373](https://ytlcomms.jira.com/browse/ZTPD-2373) |
| 客户 | 0183045564 |
| SUBS_ID | 67652714 |
| ACCT_ID | 67652712 |
| BILLING_CYCLE_TYPE_ID | 310 |
| 账期 BCID | 2911 (5/10~6/10, 31d) |
| 状态 | 🔴 已确诊根因，待修复 |
| 排查日期 | 2026-06-18 |

## 1. 问题描述

**业务背景** (JIRA 描述):
- 5/23 17:51 挂起 → 22:13 复机 → 22:17 又挂起 → 6/7 复机 → 6/8 又挂起
- 5/15 开户 (5/15 ~ 5/23 17:51 期间活跃)
- 客户说"5 月账单的发票只看到 2 笔退费 (-31.81 × 2), 没有 5/23 22:13 复机那笔补收"

## 2. 排查链路

```
CC.SUBS (ACC_NBR='0183045564')
  → SUBS_ID=67652714, ACCT_ID=67652712
  → CC.ACCT: BILLING_CYCLE_TYPE_ID=310
  → CC.BILLING_CYCLE: BCID=2911 (5/10~6/10, 31d)
  → CC.PROD_HIS: 5 个状态变更 (5/23 17:51 ~ 6/7 00:50)
  → CRM.ORDER_ITEM: 6 个订单 (5/23 一天)
  → CC.ASYN_CALL_TO_BILLING: 4 条 (按 ACCT_ID=67652712 查)
  → RB.EVENT_RECURRING_2911: 4 行 MRC 话单
  → RB.ACCT_ITEM_BILLING_2911: 5 行 (含 0 元的下期占位)
```

## 3. 实际数据

### 3.1 完整状态链 (CC.PROD_HIS)

| 时间 | PROD_STATE | 含义 |
|---|---|---|
| 5/23 17:51:23 | **E** | TWB 双向锁定 (挂起) |
| 5/23 22:13:47 | **D** | 单向停机 (复机后状态) |
| 5/23 22:15:18 | A | 活跃 (One-way Reactivation 65) |
| 5/23 22:17:55 | **E** | TWB 双向锁定 (又挂起) |
| 6/7 00:50:12 | A | 活跃 (复机) |

### 3.2 订单链 (CRM.ORDER_ITEM)

| ORDER_ID | 时间 | SUBS_EVENT_ID | 事件 |
|---|---|---|---|
| 66261270 | 5/23 17:51:23 | 28 | Suspension Under Request |
| 66299887 | 5/23 20:09:11 | 42 | Change Password (无关) |
| **66334233** | **5/23 22:13:47** | **29** | **Reactivation Under Request** ⚠️ |
| 66334402 | 5/23 22:15:18 | 65 | One-way Reactivation |
| 66334469 | 5/23 22:16:09 | 42 | Change Password (无关) |
| 66334698 | 5/23 22:17:55 | 28 | Suspension Under Request |

### 3.3 ASYN_CALL_TO_BILLING (4 条)

| ID | CREATED | 1329 | 969 | 对应 ORDER |
|---|---|---|---|---|
| 1419282 | 5/23 17:51:23 | 14 | D | 66261270 (挂起) |
| **缺** | — | — | — | **66334233 (复机 22:13) ⚠️** |
| 1419452 | 5/23 22:17:55 | 14 | A | 66334698 (挂起) |
| 1435261 | 6/7 00:50:13 | 2 | E | (复机) |
| 1436336 | 6/8 06:21:00 | 14 | A | (挂起) |

**ASYN_CALL 缺一条**：5/23 22:13:47 复机 (ORDER 66334233) 没触发 ASYN_CALL

### 3.4 RB.EVENT_RECURRING_2911 (4 行)

| # | 金额(RM) | BEGIN_TIME | 1329 | SELF |
|---|---:|---|---|---|
| 1 | -31.8065 | 5/24 17:51 | 14 | None |
| 2 | -31.8065 | 5/24 22:17 | 14 | None |
| 3 | +5.6129 | 6/7 00:50 | 2 | None |
| 4 | -1.871 | 6/9 06:20 | 14 | None |

### 3.5 RB.ACCT_ITEM_BILLING_2911 (5 行, 跟截图对应)

| ACCT_ITEM_ID | 金额 | BEGIN_DATE | 解读 |
|---|---:|---|---|
| 264487124 | -31.8065 | 5/24 22:17 | 5/23 17:51 挂起退费 (17d) |
| 264487125 | -31.8065 | 5/24 17:51 | 5/23 22:17 又挂起退费 (17d) |
| 264487123 | +5.6129 | 6/7 00:50 | 6/7 复机补收 (3d) |
| 264487122 | -1.871 | 6/9 06:20 | 6/8 挂起退费 (1d) |
| 264487121 | 0 | 6/10 00:00 | 下期预收占位 |

**客户截图的 2 笔退费 = ACCT_ITEM 264487124 + 264487125 ✓**

## 4. 根因

**两层根因**：

### 4.1 表面: ASYN_CALL 漏发

- ORDER 66334233 (5/23 22:13 复机) 没有触发 CC.ASYN_CALL_TO_BILLING
- 导致 RecurrRate 脚本 dealMode=1 路径 (processServiceType=2 复机) 没被调用
- 5/23 22:13 ~ 6/10 期间的复机补收缺失

### 4.2 底层: RecurrRate 脚本限制 (脚本第 286-287 行)

```python
# ~/Desktop/billing-kb/scripts/MRC_Charge_By_Subs_Plan_Attr.py
elif processServiceType in(14,2):
    # 挂起/复机处理
    ...
    if processServiceType == 2 and previousState != 'E':
        mrcCharge = 0    # ← 限制: 复机时 previousState 不是 E (TWB) 就不补收
```

**业务逻辑**: 复机时如果之前不是 TWB 双向锁定状态 (previousState != 'E'), 就不算真正的复机, mrcCharge=0。

**本 case 不命中这个限制**: 5/23 22:13 复机时 previousState='E' (TWB, 17:51 挂起) → 满足 !=E 不成立, 不会清零 → **脚本逻辑没问题, 只是没触发到**

### 4.3 漏发金额 (按公式计算)

如果 22:13 ASYN_CALL 不漏发, 应该产生的补收:

```python
# 公式 (脚本 261-264 行):
chargeDays = diffdays(cycleEndTime, adjustTime)
# cycleEndTime = 6/10 00:00, adjustTime = AddDay(22:13, 0) = 22:13
# chargeDays = 17 天
# mrcCharge = 1.0 * 58 (Infinite Basic 58 月租) * 17 / 31 = 31.81 RM
```

**月租确认 (4 个独立证据交叉验证)**:

**直接证据 1: SUBS_PLAN_OFFER_ATTR (默认月租)**
- 客户 `CC.PROD.OFFER_ID` = **1310** ("Postpaid Mobile Plan Mass" 产品)
- 套餐 `CC.OFFER_VER` OFFER_ID=12003 → **OFFER_VER_ID = 3846** ("Infinite Basic 58" 套餐)
- `CC.SUBS_PLAN_OFFER_ATTR`:
  - `OFFER_ID=1310, OFFER_VER_ID=3846, ATTR_ID=292 (EXP_HNCNC_RENTAL_FEE)` → **DEFAULT_VALUE='58'**
  - 多版本都=58 (3918/3846/32102)

**直接证据 2: SUBS_UPP_INST_VALUE (覆盖价, 实际生效)**
- 客户 `CC.SUBS_UPP_INST` 4 行, 其中 `SUBS_UPP_INST_ID=655494, PRICE_PLAN_ID=1324`
- `CC.SUBS_UPP_INST_VALUE[INST=655494, ATTR_ID=907487 (EXP_OVERWRITTEN_MRC)]` → **VALUE='58'**
- EFF_DATE=2023-11-07 18:33:23 (开户时), EXP_DATE=NULL (永久)
- 脚本优先用覆盖价 (脚本 46-49 行): `if overWrittenMRC != -1: mrcCharge = overWrittenMRC`
- 覆盖价 = 默认价 (都是 58) → 双重确认

**反推证据 3-5 (3 个 EVENT_RECURRING 行)**:
- 5/23 22:17 挂起退 -31.8065 → 31.8065 × 31 / 17 = **58.0** ✓
- 6/7 00:50 复机补 +5.6129 → 5.6129 × 31 / 3 = **58.0** ✓
- 6/8 06:20 挂起退 -1.871 → 1.871 × 31 / 1 = **58.0** ✓

**套餐名佐证**: OFFER 12003 名称 "Infinite Basic 58"

**漏发金额**: **~31.81 RM** (5/23 22:13 复机本应补收到 6/10, 按月租 58 算)

## 5. 修复方向

### 5.1 数据修复 (在 ytlc-test 验证后到生产)

```sql
-- 补一条 ASYN_CALL (模拟 22:13 复机消息)
-- INPUT 字段格式参考 1419452 (5/23 22:17 挂起), 改 1329=2 (复机) + 969=E (previousState)
INSERT INTO CC.ASYN_CALL_TO_BILLING (ID, EVENT, CREATED_DATE, ACCT_ID, SUBS_ID, INPUT, STATE, STATE_DATE)
VALUES (1499999, 58007, DATE'2026-05-23 22:13:47', 67652712, 67652714,
        '201=67652714,3=20260523221347,969=E,975=67652714,1000=1,1329=2,972=,987=,897=,254=N,973=310,1102=,1109=,881=,104=,206=,211=67652712,1841=,1842=,1214=101',
        'C', DATE'2026-05-23 22:13:47');

-- 重跑 RecurrRate 处理该 ASYN_CALL (在 ytlc-test 验证)
-- 会产生一条 +31.81 RM 的 EVENT_RECURRING + ACCT_ITEM_BILLING

-- 验证: 重跑后查 ACCT_ITEM_BILLING_2911
SELECT ACCT_ITEM_ID, CHARGE/10000 as charge_rm, BEGIN_DATE, END_DATE, OFFER_ID
FROM RB.ACCT_ITEM_BILLING_2911@LINK2RB
WHERE ACCT_ID = 67652712 AND ACCT_ITEM_TYPE_ID = 12
  AND BEGIN_DATE = DATE'2026-05-23' AND CHARGE/10000 > 0;
-- 应出现 1 条 +31.81 RM, OFFER_ID=12003
```

### 5.2 代码修复 (开发组)

**调查方向**:
- 查为什么 ORDER 66334233 (EVENT 29 复机) 没触发 ASYN_CALL
- 候选原因:
  1. **竞态**: 22:13 复机 + 22:15 One-way Reactivation (65) + 22:17 又挂起 (28) — 4 分钟内 3 个状态变更, 触发器可能只处理第一个或最后一个
  2. **触发器条件**: 22:15 的 65 订单可能标记状态 D→A, 让 22:13 的 29 复机"作废" (因为已经变了)
  3. **去重逻辑**: 同账号短时间内多事件可能被去重
- 建议查触发器日志 / queue 日志 (5/23 22:13-22:17 期间的事件分发)
- 复现: 制造一个 4 分钟内 3 个状态变更的测试账号, 看 ASYN_CALL 是否漏发

## 6. 速查表

### 6.1 状态码 (CC.PROD.PROD_STATE)

| 状态 | 含义 |
|---|---|
| A | 活跃 |
| D | 单向停机 |
| E | TWB 双向锁定 |

### 6.2 事件码 (CC.SUBS_EVENT.SUBS_EVENT_ID)

| EVENT_ID | 名称 | 触发 MRC |
|---|---|---|
| 28 | Suspension Under Request | 退费 (1329=14) |
| 29 | Reactivation Under Request | 补收 (1329=2) |
| 42 | Change Password | 不触发 |
| 65 | One-way Reactivation | 不触发 (跟 29 不同) |

### 6.3 ASYN_CALL 1329 速查

| 1329 | 事件 | MRC 动作 |
|---|---|---|
| 2 | 复机 | 补收 (按复机时间 prorate) |
| 14 | 挂起 | 退费 (按挂起到 cycleEnd prorate) |

## 7. 复现路径

**输入**: "5/15 开户的客户在同账期内多次挂起/复机"

**复现条件**:
1. ASYN_CALL 触发的 5/23 22:13 复机消息漏发 (根因 1)
2. 即使不漏发, 22:15 又有 One-way Reactivation (65) 订单可能竞争触发器 (根因 2 推测)
3. 4 分钟后又挂起 (22:17), 状态变化太快可能漏中间环节

## 8. 备注

- 跟 RUNBOOK Case 1 (0183045564 同客户) 是**不同事件**: Case 1 是挂起复机, 这次也是同一客户的另一次挂起复机
- RUNBOOK Case 1 描述"5/23 22:13 复机补收缺失" — 跟本 case 的 ASYN_CALL 漏发 66334233 是**同一事件** (JIRA 报告可能是同一个 bug 持续发酵)
- 5/23 22:13 复机 4 分钟后又挂起 (22:17), 时间太短可能是 ASYN_CALL 漏发的诱因
- 排查思路已写入 memory: "不遍历 BCID" + "ASYN_CALL 按 ACCT_ID 查"

## 9. JIRA 倒查

已知 JIRA key 拉详情:
```bash
python3 ~/.hermes/scripts/jira_ticket_get.py get ZTPD-2373
```

已知 SUBS_ID 反查 JIRA (先 grep 本地 INDEX, 再 JQL):
```bash
grep "67652714" ~/Desktop/billing-kb/cases/INDEX.md  # 优先
# 或 jira search: project = ZTPD AND description ~ "0183045564"
```

JIRA 同步: 把本 case 贴到 ZTPD-2373 (用户授权后):
```bash
python3 ~/.hermes/scripts/jira_ticket_get.py comment ZTPD-2373 \
  --text-file ~/Desktop/billing-kb/cases/case-ZTPD-2373.md
```
