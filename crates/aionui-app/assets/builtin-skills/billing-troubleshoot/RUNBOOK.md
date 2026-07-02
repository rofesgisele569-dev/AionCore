# 排查路线图

> 无论什么问题，从这里开始。不要跳步骤。

## Step 0: 判断问题类型

| 用户说 | 可能问题 | 切入文档 |
|---|---|---|
| "月租不对/多收/少收" | MRC proration / 挂起复机 / BS | [BILLING_MASTER §2](docs/BILLING_MASTER.md) |
| "发票上金额/列不对" | BILL_SRC / jrxml 模板 | [JASPER.md](../JASPER.md) |
| "多了一行/少了一行费用" | dealMode 重复 / ASYN_CALL 漏发 | [BILLING_MASTER §4](docs/BILLING_MASTER.md) |
| "退费不对" | Rebate COUNT/INST / PAP Refund | [BILLING_MASTER §2.9](docs/BILLING_MASTER.md) |
| "公司/个人付错了" | Balance Share | [BILLING_MASTER §2.7](docs/BILLING_MASTER.md) |

## Step 1: 账号定位（必做）

```sql
-- 从客户给的手机号/BA号 → SUBS_ID + ACCT_ID
SELECT s.SUBS_ID, s.ACCT_ID, s.ACC_NBR FROM CC.SUBS s WHERE s.ACC_NBR = '${NBR}';

-- 拿到 BILLING_CYCLE_TYPE → 账期
SELECT a.BILLING_CYCLE_TYPE_ID FROM CC.ACCT a WHERE a.ACCT_ID = ${ACCT_ID};

-- 账期定位（不要猜 CYCLE ID！）
SELECT bc.BILLING_CYCLE_ID, bc.CYCLE_BEGIN_DATE, bc.CYCLE_END_DATE
FROM CC.BILLING_CYCLE bc
WHERE bc.BILLING_CYCLE_TYPE_ID = ${TYPE} AND bc.CYCLE_BEGIN_DATE <= DATE'${TARGET}' AND bc.CYCLE_END_DATE >= DATE'${TARGET}';
```

## Step 2: 看话单 (EVENT_RECURRING)

```sql
-- 拿到所有 MRC 行，按时间排序
SELECT CHARGE1/10000, ACCT_ID1, PAID_ACCT_ID, SELF_FLAG,
       EVENT_BEGIN_TIME, EVENT_END_TIME, CREATED_DATE, ATTR_LIST
FROM RB.EVENT_RECURRING_${CYCLE}@LINK2RB WHERE SUBS_ID = ${SUBS_ID}
ORDER BY CREATED_DATE;
```

**看三件事：**
1. 行数对不对 → 预期几行？实际几行？
2. 金额对不对 → 验证 `月租 × 天数 / cycleDays`
3. ATTR_LIST[1329] → 哪些行是 dealMode=1 触发、哪些是 dealMode=0

## Step 3: 三步时间对齐

```
CRM ORDER  →  ASYN_CALL_TO_BILLING  →  EVENT_RECURRING
  时间差 < 30s      时间差 < 30s
```

**缺 ASYN_CALL = 计费消息漏发**（Case 1 场景）  
**一条 ASYN_CALL 产多行 = dealMode 交叉**（Case 2 场景）

## Step 4: 查根因

| 行数异常 | 查 |
|---|---|
| 少行 | ASYN_CALL_TO_BILLING 是否缺失 |
| 多行（翻倍） | SELF_FLAG 区分 dealMode=0(Y/N) vs dealMode=1(None)；OFFER_VER 是否取错版本 |
| PAID 归属错 | BAL_SHARE_DETAIL.EXP_DATE 是否到期 |
| 金额不对 | OFFER_ATTR[292] 月租 + PRICE_PLAN 覆盖价 + proration 天数 |

## Step 5: 输出报告

用 `templates/troubleshoot-template.html`，7 章节。必含三步时间对齐表 + EVENT_RECURRING 逐行分析表。

---

## 实操案例

### Case 1: 挂起复机补收缺失 (0183045564)

**客户描述：** 挂了、恢复了、又挂了，退了两笔没补一笔。

**排查路径：**
1. Step 1 → SUBS=67652714, CYCLE=2911
2. Step 2 → EVENT_RECURRING: 2条退费 -31.81, 无补收
3. Step 3 → ASYN_CALL: 缺 5/23 22:13 那一条 → 消息漏发
4. 根因：ORDER=66334233 (Reactivation) 的计费触发消息没生成

### Case 2: Balance Share 停用 + 套餐切换 费率取错 (0187005168)

**客户描述：** 个人多收、公司多退。

**排查路径：**
1. Step 1 → SUBS=61892269, CYCLE=2909
2. Step 2 → EVENT_RECURRING: 11 行 (应 4~5 行)
3. Step 3 → 两条 ASYN_CALL 各产 4~6 行
4. SELF_FLAG 分组分析 → dealMode=1 和 dealMode=0 各产一份
5. OFFER_ATTR 多版本 → dealMode=0 取了旧费率 88
6. 根因：dealMode=0 在 BS 停用时取了已废弃的旧 OFFER_VER
