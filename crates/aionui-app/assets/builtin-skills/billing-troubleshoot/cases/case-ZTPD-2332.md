# Case ZTPD-2332 — BS停用+切套餐 dealMode=0 取旧套餐月租致多收多退

## 元信息

| | |
|---|---|
| JIRA | [ZTPD-2332](https://ytlcomms.jira.com/browse/ZTPD-2332) |
| 客户 | 0187005168 (BA: 839934298) |
| SUBS_ID | 61892269 |
| 个人 BA ACCT_ID | 61892242 |
| 公司 BA ACCT_ID | 86915845 |
| 账期 BCID | 2909 (CYCLE_TYPE=303, 5/3~6/3) |
| 状态 | 🔴 已确诊根因，待数据修复 |
| 排查日期 | 2026-06-18 |

## 1. 问题描述

**业务背景**：
- 用户有 BS (公司→个人)
- 2026-05-18 14:19:16 换套餐 (旧 Infinite Ultra 88 hotspot → 新 Yes 35 150GB)
- 2026-05-29 09:52:55 公司 BA 停用 BS
- 2026-06-03 发票生成

**错误现象**：
- 个人 BA (61892242) 多收 +14.19 RM
- 公司 BA (86915845) 多退 -14.19 RM
- 时间段: 5/29 ~ 6/3 (5 天 prorate)

## 2. 排查链路

```
CC.SUBS (ACC_NBR='0187005168')
  → SUBS_ID=61892269, ACCT_ID=61892242
  → CC.ACCT: BA=839934298, POSTPAID=Y, BILLING_CYCLE_TYPE_ID=303
  → CC.PROD: OFFER_ID=1310, SUBS_PLAN_ID=12061, PROD_STATE=A
  → CC.BILLING_CYCLE: BCID=2909 (5/3~6/3)
  → CC.BAL_SHARE_DETAIL: BS_ID=3317, EFF=2025-06-07, EXP=2026-05-29 09:52:55 ✓
  → CC.SUBS_UPP_INST: 5/18 14:19 切套餐 (PRICE_PLAN 1324→23664)
  → CC.ASYN_CALL_TO_BILLING (按 ACCT_ID 查!):
       ID 1414034  EVENT 58007  5/18 14:19:17  1329=13 (Change Plan)
       ID 1425316  EVENT 58007  5/29 09:52:55  1329=7  (Account Change / BS停用)
  → RB.EVENT_RECURRING_2909: 11 行 (按时间排序)
  → RB.ACCT_ITEM_BILLING_2909: 验证截图 (ACCT_ITEM_ID 主键, 不是 _BILLING_ID)
```

## 3. 实际数据

### 3.1 RB.EVENT_RECURRING_2909 (11 行)

| # | 金额(RM) | ACCT_ID1 | PAID | SELF | 时段 | 解读 |
|---|---:|---|---|---|---|---|
| 1 | -45.42 | CO | U | Y | 5/18~6/3 16d | 退旧 dealMode=1 防重行 |
| 2 | -45.42 | CO | CO | N | 5/18~6/3 16d | 退旧 dealMode=0 公司合账 |
| 3 | +18.06 | CO | U | Y | 5/18~6/3 16d | 补新 dealMode=1 防重行 |
| 4 | +18.06 | CO | CO | N | 5/18~6/3 16d | 补新 dealMode=0 公司合账 |
| 5 | -14.19 | CO | U | Y | 5/29~6/3 5d | 退旧 dealMode=1 防重行 (旧88) |
| 6 | +5.65 | U | U | None | 5/29~6/3 5d | 补新 (35) 个人 |
| **7** | **-14.19** | **CO** | **CO** | **N** | **5/29~6/3 5d** | **退旧 dealMode=0 公司 ❌** |
| 8 | -5.65 | CO | U | Y | 5/29~6/3 5d | 退新 dealMode=1 防重行 |
| 9 | -5.65 | CO | CO | N | 5/29~6/3 5d | 退新 dealMode=0 公司 (正确) |
| **10** | **+14.19** | **U** | **U** | **None** | **5/29~6/3 5d** | **补旧 dealMode=0 个人 ❌** |
| 11 | +35.00 | U | U | None | 6/3~7/3 30d | 预收下月 (正确) |

SELF_FLAG: Y=防重不参与合账 / N=公司合账 / None=当前BA合账
**行 #7 (公司) 和 #10 (个人) 错误**

### 3.2 CC.ASYN_CALL_TO_BILLING (2 条)

| ID | EVENT | 时间 | 1329 | 含义 |
|---|---|---|---|---|
| 1414034 | 58007 | 5/18 14:19:17 | 13 | Change Plan |
| 1425316 | 58007 | 5/29 09:52:55 | 7 | Account Change (BS停用) |

**关键**: ASYN_CALL 按 ACCT_ID 查 (不是 SUBS_ID)

### 3.3 RB.ACCT_ITEM_BILLING_2909 (合账硬证据)

```
ACCT_ITEM_ID  ACCT_ID    MRC(ACCT_ITEM_TYPE_ID=12)  OFFER_ID  BEGIN_DATE   END_DATE
264283575     61892242   5.6452                      12061     5/29 09:52   6/3
264283576     61892242   14.1935  ← 错误             12061     5/29 09:52   6/3
264283574     61892242   35                         12061     6/3          7/3
264245926     86915845   -14.1935 ← 错误            12148     5/29 12:04   6/3
```

**个人 BA 5/29-6/3 期间**: +5.6452 (35×5/31 正确) + **+14.1935 (88×5/31 错误)**
**公司 BA 5/29-6/3 期间**: **-14.1935 (88×5/31 错误)**

## 4. 根因

**5/29 BS 停用时 dealMode=0 取了已废弃的旧套餐 (OFFER 12199) 月租 88，错误应用了 5 天 prorate**

### 4.1 OFFER 关系 (CC.OFFER + CC.OFFER_VER 验证)

| 套餐 | OFFER_ID | OFFER_VER_ID | 名称 | EFF_DATE | 月租 |
|---|---|---|---|---|---|
| 旧 | **12199** | **42104** | Infinite Ultra 88 hotspot 110GB | 2026-04-28 | 88 |
| 新 | 12061 | 3904 | Yes 35 150GB | 2000-01-01 | 35 |

### 4.2 Bug 位置 (推断)

`RecurrRate 脚本` 在 dealMode=0 路径 (公司/当前BA合账) 计算 prorate 时：
- 正确: 用 SUBS_UPP_INST 当前生效的 PRICE_PLAN_ID 对应月租 (新套餐 35)
- 实际: 用了过期套餐的月租 (旧套餐 88)

### 4.3 证据链

| 证据 | 数据 | 结论 |
|---|---|---|
| 错误行 OFFER_ID | 12061 (新套餐) | OFFER 维度正确 |
| 错误行金额 | 14.1935 = 88×5/31 | 月租数值用了 88 (旧) |
| BS 停用时间 | 5/29 09:52:55 | 跟 1329=7 事件吻合 |
| 5/18 已切套餐 | OFFER 12199 → 12061 | 切套餐动作已生效 |
| ASYN_CALL 存在 | 2 条 (1329=13, 7) | 消息没漏发 |

**结论**: OFFER_ID 取对了 (12061)，但月租数值**误用**了旧套餐 12199 的 88。

## 5. 修复方向

### 5.1 数据修复 (在 ytlc-test 验证后到生产执行)

```sql
-- 删个人 BA 错误行
DELETE FROM RB.ACCT_ITEM_BILLING_2909@LINK2RB
WHERE ACCT_ITEM_ID = 264283576;  -- +14.19 个人

-- 删公司 BA 错误行
DELETE FROM RB.ACCT_ITEM_BILLING_2909@LINK2RB
WHERE ACCT_ITEM_ID = 264245926;  -- -14.19 公司

-- 重新跑合账 (生产不执行)
-- LedgerCollect -c 2909 -N rb1 -t recurring
```

### 5.2 代码修复 (开发组)

`RecurrRate 脚本` dealMode=0 路径取月租时：
- 改用 SUBS_UPP_INST 当前生效 PRICE_PLAN_ID 关联的 OFFER
- 而非从全局 OFFER 多版本中按 EFF_DATE 最早取

## 6. 速查表

### 6.1 SELF_FLAG 含义 (RB.EVENT_RECURRING)

| SELF | dealMode | 含义 | 合账 |
|---|---|---|---|
| Y | 1 | 防重行 | 不参与任何人合账 |
| N | 0 | 归属公司 BA | 公司合账 |
| None | — | 正常归属行 | 当前 BA 合账 |

### 6.2 ASYN_CALL 1329 关键值

| 1329 | 事件 | MRC 计算 |
|---|---|---|
| 13 | 切套餐 | 退旧(-MRC×天/cycle) + 补新(+MRC×天/cycle) |
| 7 | 账户变更 (BS 停用) | 同切套餐 |

### 6.3 涉及表

| 表 | 用途 | 字段注意 |
|---|---|---|
| CC.SUBS | 订户 | 无 STATE 列 |
| CC.ACCT | 账号 | POSTPAID, BILLING_CYCLE_TYPE_ID |
| CC.PROD | 产品 | PROD_STATE, OFFER_ID, SUBS_PLAN_ID |
| CC.SUBS_UPP_INST | 套餐实例 | EFF_DATE, EXP_DATE |
| CC.BAL_SHARE_DETAIL | BS 关系 | EFF_DATE, EXP_DATE, BAL_SHARE_ID |
| CC.ASYN_CALL_TO_BILLING | 计费触发 | **按 ACCT_ID 查** (非 SUBS_ID) |
| RB.EVENT_RECURRING_${BCID}@LINK2RB | MRC 话单 | CHARGE1/10000, ATTR_LIST 1329/959 |
| RB.ACCT_ITEM_BILLING_${BCID}@LINK2RB | 合账结果 | **主键 ACCT_ITEM_ID** (非 _BILLING_ID) |
| CC.OFFER_VER | 套餐版本 | OFFER_VER_ID, EFF_DATE |
| CC.OFFER | 套餐主表 | OFFER_ID, OFFER_NAME |

## 7. 复现路径

**输入**: "BS有效期内切换套餐 + BS停用在同账期 + 新旧套餐月租不同"

**自动调用链**:
```
CRM Order (329 Change Plan) → ASYN_CALL (1329=13)
  → RecurrRate (dealMode=0 + dealMode=1) → EVENT_RECURRING
CRM Order (20011 Member Quit) → ASYN_CALL (1329=7)
  → RecurrRate (dealMode=0 + dealMode=1) → EVENT_RECURRING
dealMode=0 取了旧套餐 OFFER 12199 的月租 88 → 多产退/补错行
```

## 8. 备注

- 别的 agent 6/17 写过一份 HTML 报告 (~/Desktop/ytlc-skills/MRC_BALANCESHARE_0187005168.html)
  - 大部分结论正确
  - OFFER_VER=42104 数据真实 (属于 OFFER 12199, 不是当前 1310/12061)
- 现场 SQL 验证 (本次) 补完了 ACCT_ITEM_BILLING 硬证据
- 修复需要 ytlc-test 验证 + 用户授权才能在生产执行
- JIRA 同步：用 `python3 ~/.hermes/scripts/jira_ticket_get.py comment ZTPD-2332 --text-file case-ZTPD-2332.md` 可把本报告贴到工单

## 9. JIRA 倒查

已知 JIRA key 拉详情：
```bash
python3 ~/.hermes/scripts/jira_ticket_get.py get ZTPD-2332
```

已知 SUBS_ID 反查 JIRA（先 grep 本地 INDEX，再视情况查 ZTPD 项目）：
```bash
grep "61892269" ~/Desktop/billing-kb/cases/INDEX.md  # 优先
# 或 JQL: project = ZTPD AND description ~ "0187005168"  # 通过 jira search
```
