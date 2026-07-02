# Billing 计费排查权威手册

> **术语基准见 [CONTEXT.md](../../CONTEXT.md)** — 领域语言、体系、编号体系以它为准。本文档聚焦排查步骤、脚本逻辑、场景速查。
> 唯一更新入口。旧的分散文件（MRC_VERIFY.md / MRC_SUSPEND_ISSUE.md / troubleshoot-mrc/SKILL.md）以此为准。

> 唯一更新入口。覆盖 MRC、PAP、Rebate、Balance Share、挂起复机、新开户、切换套餐。
> 旧的分散文件（MRC_VERIFY.md / MRC_SUSPEND_ISSUE.md / troubleshoot-mrc/SKILL.md）以此为准。

---

## 1. 全链路数据流

```
CRM Order → ASYN_CALL_TO_BILLING → RecurrRate 脚本 → EVENT_RECURRING
  ↓                                                      ↓ LedgerCollect
EVENT_CHARGE ← SUBS_AGREEMENT_INST_FEE              ACCT_ITEM_BILLING
  ↓                                                      ↓ YTL_BILL_RUN
EVENT_CHARGE_EXT / EVENT_CHARGE_DISCOUNT             BILL_DATA → Invoice
```

**时间对齐规则：** 三步间隔通常 < 30s，排查时必须输出时间对照表。

```
CRM ORDER.CREATED_DATE  ~  ASYN_CALL.CREATED_DATE  ~  EVENT_RECURRING.CREATED_DATE
```

---

## 2. 排查步骤（9 步）

### 2.1 账号→账期定位

```sql
-- ① SUBS + ACCT
SELECT s.SUBS_ID, s.ACCT_ID, s.ACC_NBR FROM CC.SUBS s WHERE s.ACC_NBR = '${PHONE_NBR}';

-- ② 账期（ACCT.BILLING_CYCLE_TYPE → BILLING_CYCLE）
SELECT a.ACCT_ID, a.BILLING_CYCLE_TYPE_ID, bc.BILLING_CYCLE_ID, bc.CYCLE_BEGIN_DATE, bc.CYCLE_END_DATE
FROM CC.ACCT a
JOIN CC.BILLING_CYCLE bc ON a.BILLING_CYCLE_TYPE_ID = bc.BILLING_CYCLE_TYPE_ID
WHERE a.ACCT_ID = ${ACCT_ID} AND bc.CYCLE_BEGIN_DATE <= DATE'${TARGET_DATE}' AND bc.CYCLE_END_DATE >= DATE'${TARGET_DATE}';
```

### 2.2 PROD → 月租

```sql
-- ③ PROD（SUBS_ID = PROD_ID）
SELECT p.PROD_STATE, p.OFFER_ID, p.SUBS_PLAN_ID, p.AGREEMENT_EFF_DATE, p.AGREEMENT_EXP_DATE
FROM CC.PROD p WHERE p.PROD_ID = ${SUBS_ID};

-- ④ 月租：OFFER_ATTR[292] = EXP_HNCNC_RENTAL_FEE（多版本取 EFF_DATE 覆盖的）
SELECT soa.DEFAULT_VALUE, soa.OFFER_VER_ID FROM CC.SUBS_PLAN_OFFER_ATTR soa
WHERE soa.OFFER_ID = ${OFFER_ID} AND soa.ATTR_ID = 292 ORDER BY OFFER_VER_ID;

-- ⑤ 覆盖价 ATTR[907487] = EXP_OVERWRITTEN_MRC
SELECT soa.DEFAULT_VALUE FROM CC.SUBS_PLAN_OFFER_ATTR soa
WHERE soa.OFFER_ID = ${OFFER_ID} AND soa.ATTR_ID = 907487;

-- ⑥ SUBS_UPP_INST（套餐变更、覆盖价来源）
SELECT PRICE_PLAN_ID, EFF_DATE, EXP_DATE FROM CC.SUBS_UPP_INST WHERE SUBS_ID = ${SUBS_ID};
```

**SUBS → PROD → OFFER_ATTR 链：**
```
SUBS_ID = PROD_ID → PROD(OFFER_ID) → SUBS_PLAN_OFFER_ATTR(OFFER_ID, ATTR_ID=292/907487)
```

### 2.3 EVENT_RECURRING 验证

```sql
-- ⑦ MRC 明细
SELECT CHARGE1/10000, ACCT_ID1, PAID_ACCT_ID, SELF_FLAG,
       EVENT_BEGIN_TIME, EVENT_END_TIME, CREATED_DATE, ATTR_LIST
FROM RB.EVENT_RECURRING_${CYCLE}@LINK2RB WHERE SUBS_ID = ${SUBS_ID}
ORDER BY CREATED_DATE;
```

**ATTR_LIST 关键字段：**

| attr | 含义 | 取值 |
|---|---|---|
| 1329 | processServiceType | 14=挂起, 2=复机, 3=新开, 11/12=拆机, 13=切换套餐, 7=账户变更 |
| 969 | previousState | E=TWB, D=单向停机, A=活跃 |
| 2002/2003 | 合约有效期 | agreementEff/Exp |
| 862/863 | 收费时段 | chargeBegin/End |
| 959 | dealMode | 0=Offline, 1=Prorate, 2=Mock |
| 1821 | subsPlanChangeState | 1=旧套餐, 2=新套餐 |

**SELF_FLAG 含义：**

| SELF_FLAG | 含义 | 合账 |
|---|---|---|
| Y | dealMode=1 生成，防重行 | 不参与合账 |
| N | dealMode=0 生成 | 公司/当前 BA 合账 |
| None | 正常归属行 | 当前 BA 合账 |

**验证公式：** `MRC = 月租 × (EVENT_END - EVENT_BEGIN) / cycleDays`

### 2.4 计费触发消息

```sql
-- ⑧ ASYN_CALL_TO_BILLING：CRM 订单→计费触发
SELECT ID, EVENT, STATE, CREATED_DATE, SUBS_ID
FROM CC.ASYN_CALL_TO_BILLING
WHERE ACCT_ID = ${ACCT_ID} AND CREATED_DATE >= DATE'${RANGE_START}'
ORDER BY CREATED_DATE;
```

**每笔 MRC 变动的 CRM 订单必定对应一条 ASYN_CALL。缺失 = 消息漏发。**

### 2.5 订单溯源

```sql
-- ⑨ CRM 订单
SELECT ORDER_ITEM_ID, SUBS_EVENT_ID, ORDER_TYPE, CREATED_DATE
FROM CRM.ORDER_ITEM WHERE ACC_NBR = '${PHONE_NBR}' AND CREATED_DATE >= DATE'${RANGE_START}'
ORDER BY CREATED_DATE;

-- 事件名
SELECT SUBS_EVENT_ID, EVENT_NAME FROM CC.SUBS_EVENT WHERE SUBS_EVENT_ID IN (${EVENT_IDS});
```

### 2.6 状态变更

```sql
-- ⑩ PROD_HIS
SELECT PROD_STATE, PROD_STATE_DATE FROM CC.PROD_HIS
WHERE PROD_ID = ${SUBS_ID} AND PROD_STATE_DATE >= DATE'${RANGE_START}' ORDER BY PROD_STATE_DATE;
```

### 2.7 Balance Share

```sql
-- ⑪ BS 关系
SELECT bsd.SUBS_ID, bs.ACCT_ID COMPANY_BA, bsd.EFF_DATE, bsd.EXP_DATE
FROM CC.BAL_SHARE_DETAIL bsd JOIN CC.BAL_SHARE bs ON bsd.BAL_SHARE_ID = bs.BAL_SHARE_ID
WHERE bsd.SUBS_ID = ${SUBS_ID};

-- ⑫ 公司/个人账期是否一致
SELECT acct_id, BILLING_CYCLE_TYPE_ID FROM CC.ACCT WHERE ACCT_ID IN (${USER_BA}, ${COMPANY_BA});

-- ⑬ 公司 BA 的 MRC
SELECT CHARGE1/10000, EVENT_BEGIN_TIME, EVENT_END_TIME, ATTR_LIST
FROM RB.EVENT_RECURRING_${CYCLE}@LINK2RB
WHERE ACCT_ID1 = ${COMPANY_BA} AND SUBS_ID = ${SUBS_ID} ORDER BY EVENT_BEGIN_TIME;
```

### 2.8 合账验证

```sql
-- ⑭ 合账前后对比
SELECT SUM(CHARGE1)/10000 FROM RB.EVENT_RECURRING_${CYCLE}@LINK2RB WHERE ACCT_ID1 = ${ACCT_ID};
SELECT SUM(CHARGE)/10000 FROM RB.ACCT_ITEM_BILLING_${CYCLE}@LINK2RB WHERE ACCT_ID = ${ACCT_ID} AND ACCT_ITEM_TYPE_ID = 12;
```

### 2.9 Rebate 检查

```sql
-- ⑮ SUBS_AGREEMENT_INST_FEE
SELECT f.FEE_VALUE/10000, f.ACCT_ITEM_TYPE_ID, f.OFFER_REBATE_ID, f.INSTALMENT_TYPE_ID, f.CREATE_DATE
FROM CC.SUBS_AGREEMENT_INST_FEE f WHERE f.SUBS_ID = ${SUBS_ID};

-- ⑯ OFFER_REBATE
SELECT o.OFFER_REBATE_ID, o.REBATE_NAME, o.REBATE_COUNT, o.VALUE/10000, o.ACCT_ITEM_TYPE_ID
FROM CC.OFFER_REBATE o WHERE o.OFFER_REBATE_ID = ${REBATE_ID};

-- ⑰ EVENT_CHARGE + EVENT_CHARGE_EXT
SELECT e.CHARGE/10000, e.PRICE_ID, e.BILLING_CYCLE_ID, e.STATE, e.CREATE_DATE
FROM CC.EVENT_CHARGE e WHERE e.SUBS_ID = ${SUBS_ID} ORDER BY e.CREATE_DATE;

SELECT ext.PRICE_ID, ext.DEDUCT_SEQ, ext.OFFER_REBATE_ID, ext.SUBS_AGREEMENT_INST_ID, COUNT(*)
FROM CC.EVENT_CHARGE_EXT ext WHERE ext.EVENT_INST_ID = ${EVENT_INST_ID}
GROUP BY ext.PRICE_ID, ext.DEDUCT_SEQ, ext.OFFER_REBATE_ID, ext.SUBS_AGREEMENT_INST_ID;

-- ⑱ EVENT_CHARGE_DISCOUNT（优惠券/折扣）
SELECT ecd.DISCOUNT_CHARGE/10000, ecd.VOUCHER_CODE, ecd.DEDUCT_SEQ
FROM CC.EVENT_CHARGE_DISCOUNT ecd WHERE ecd.EVENT_INST_ID = ${EVENT_INST_ID};
```

---

## 3. MRC 脚本完整逻辑

脚本：`/web/cvbs/r13/script/template/MRC_Charge_By_Subs_Plan_Attr.py`

### 入口：取月租 → 查覆盖价 → 判断阶梯/首免 → 三条分支

| 参数 | 来源 | 说明 |
|---|---|---|
| subsPlanMRC | OFFER_ATTR[292] | 套餐月租 EXP_HNCNC_RENTAL_FEE |
| overWrittenMRC | SUBS_UPP_INST / OFFER_ATTR[907487] | 覆盖价 |
| dealMode | attr[959] | 0/1/2 |

### dealMode=0 (Offline)

| 条件 | 产物 |
|---|---|
| 合约有效期内 | 整月 MRC |
| 合约在 cycle 内到期 | prorate: MRC × (EXP - cycleBegin) / cycleDays |
| 无有效合约 | MRC=0 |

### dealMode=1 (Online Prorate)

| processServiceType | 场景 | 公式 |
|---|---|---|
| 3 | 新开户 DPP | MRC × (cycleEnd - completeDate) / cycleDays |
| 11,12 | 拆机 | -MRC × (cycleEnd - terminationDate) / cycleDays |
| 13 | 切换套餐 | subsPlanChangeState=1(退旧,-MRC); =2(补新,+MRC) |
| 7 | 账户变更 | 同切换套餐 |
| 14 | 挂起 | -MRC × (cycleEnd - (currentTime+1)) / cycleDays |
| 2 | 复机 | +MRC × (cycleEnd - currentTime) / cycleDays。脚本最后一行：`if PStype==2 and prevState!='E': mrcCharge=0` |

### dealMode=2 (Mock)

`immBillingCycleId ≠ dealBillingCycleId` → 补收 currentTime → cycleEnd。一次只产一条。

### 切换套餐关键逻辑

```python
subsPlanChangeState = attr[1821]  # 1=旧套餐, 2=新套餐
chargeDays = cycleEnd - currentTime
mrcCharge = {-1, +1}[subsPlanChangeState] × MRC × chargeDays / cycleDays
```

---

## 4. 场景速查

### 4.1 挂起/复机 — ASYN_CALL 漏发

**现象：** EVENT_RECURRING 缺复机补收行，CRM 订单存在但 ASYN_CALL 无。

**排查：** CRM → ASYN_CALL → EVENT_RECURRING 三步时间对齐。

**案例：** 0183045564，5/23 22:13 复机 (ORDER=66334233) 无 ASYN_CALL → MRC 补收缺失。

### 4.2 Balance Share — dealMode 取错费率

**现象：** 切换套餐后 BS 停用，dealMode=0 取了旧 OFFER_VER 费率。

**排查：** SUBS_PLAN_OFFER_ATTR 多版本，dealMode=0 vs dealMode=1 各自取到不同版本。

**案例：** 0187005168，5/29 BS 停用时 dealMode=0 取了 88 旧费率，产出错误 +14.19/-14.19。

### 4.3 新开户 MRC prorate

**公式：** MRC = 月租 × (cycleEnd - ACTIVE_DATE) / cycleDays

### 4.4 合约到期 prorate

**公式：** MRC = 月租 × (EXP - cycleBegin) / cycleDays

### 4.5 覆盖价未生效

**排查：** OFFER_ATTR[907487] 或 SUBS_UPP_INST.EXP_OVERWRITTEN_MRC

---

## 5. SUBS_EVENT → MRC 映射

| EVENT_ID | 事件 | MRC | 条件 |
|---|---|---|---|
| 1 | New Connection | 补收（prorate） | — |
| 28 | Suspension | 退费 (-) | — |
| 29 | Reactivation | 补收 (+) | ASYN_CALL 存在 + previousState='E' |
| 64 | Two-Way Block | 退费 (-) | — |
| 27 | Two-Way Reactivation | 补收 (+) | — |
| 46 | Termination | 退费 (-) | — |
| 329 | Change Plan | 退旧+补新 | subsPlanChangeState |
| 20011 | Member Quit (BS Stop) | 归属迁移 | ACCT_ID 从公司→个人 |

---

## 6. ACCT_ITEM_TYPE 速查

| TYPE | 名称 | 说明 |
|---|---|---|
| 12 | MRC | 月租 |
| 307 | PAP | 预付款 |
| 19 | PAP Refund | 预付款退 |
| 903 | Monthly Device Cost | 设备月付 |
| 909 | Advance Device Cost | 设备首付 |
| 306 | Advance Device Cost Refund | 设备首付退 |
| 2703 | Rounding | 零头 |
| 304 | SST | 税 (6%) |
| 5002 | MRC Discount | 租费折扣 |

---

## 7. EVENT_CHARGE STATE 状态码

| STATE | 含义 |
|---|---|
| 1 | 待出账（未挂 CYCLE） |
| 3 | 合账完成 |
| 4 | 现金已付（即时支付，已挂 CYCLE 但未走 LedgerCollect） |
| 7 | 作废 |

---

## 8. DB Link

| 环境 | LINK | 用途 |
|---|---|---|
| 生产 RB/INV | LINK2RB | RB.EVENT_RECURRING, RB.ACCT_ITEM_BILLING, ACCT_ITEM_TYPE |
| 测试 RB/INV | LINK_RB | 同上 |
| 生产 CRM | 直连 CRM.ORDER_ITEM | Sufficient for query, no link needed |

> ⚠️ 生产环境 `@LINK2RB` vs 测试 `@LINK_RB`，名称不同。CONTEXT.md 写的是 `@LINK_RB` 指测试环境。

---

## 9. 排查模板

排查报告使用 `ytlc-skills/troubleshoot-template.html` 格式，7 个章节：

1. 问题描述
2. 排查链路
3. 实际数据（含 SQL + 表）
4. 根因
5. 修复方向
6. 排查工具链
7. 速查表 / 复现
