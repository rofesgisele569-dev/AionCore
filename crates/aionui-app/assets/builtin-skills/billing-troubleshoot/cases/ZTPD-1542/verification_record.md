# ZTPD-1542 修复验证记录

> 独立目录:`~/Desktop/billing-kb/cases/ZTPD-1542/`
> 跟当前 KB(`~/Desktop/billing-kb/`)区分,这是 ZTPD-1542 修复验证专用的工作区。
> 用户切到 ytlc-test profile 后,直接读这个文件跑验证。

---

## 一、问题背景

**单子**:[ZTPD-1542](https://ytlcomms.jira.com/browse/ZTPD-1542) E-invoice needed to be submitted if all classification code is zero
**Assignee**: Shenjiali
**Reporter**: sujay.ym
**Status**: Open
**Priority**: Major
**Sample**: INV202509019068993 & BA: 300351023

**问题描述**: 发票只含支付交易、分类代码全 0 时,系统判 "no need notify" → 不提交 IRBM。BRD 要求所有生成的发票都应提交 IRBM。

**R&D 修复**:

- Task: 5588
- Release Version: **v9m.2.23**
- 状态:生产版本**未升级**(用户原话"版本还没升级"),验证需在 **ytlc-test** 环境做

---

## 二、验证 SQL(用户提供的捞脏数据逻辑)

```sql
SELECT
  A.E_INVOICE_NBR,
  A.CREATE_DATE,
  A.ACCT_NBR,
  A.ACCT_ID,
  B.ATTR_VALUE AS CC,
  E.RECV_CHARGE
FROM
  CC.E_INVOICE A
  INNER JOIN CC.ACCT_ATTR_VALUE B ON A.ACCT_ID = B.ACCT_ID
  INNER JOIN CC.BILL E ON A.E_INVOICE_ID = E.E_INVOICE_ID
WHERE
  B.ATTR_ID = '907207'
  AND A.IRBM_STATE = 'N'
  AND B.ATTR_VALUE NOT IN ('TESTLINE')
  AND A.INVOICE_END_DATE >= DATE '2026-01-01'
  AND A.INVOICE_END_DATE < DATE '2026-02-01'
  AND E.RECV_CHARGE <> 0
  AND NOT EXISTS (
      SELECT 1
      FROM CC.ACCT_ITEM C
      INNER JOIN CC.BILLING_CYCLE D ON C.BILLING_CYCLE_ID = D.BILLING_CYCLE_ID
      WHERE A.ACCT_ID = C.ACCT_ID
      AND D.INVOICE_DATE >= DATE '2026-01-01'
      AND D.INVOICE_DATE < DATE '2026-02-01'
  );
```

---

## 三、修复验证 SQL(用于 ytlc-test)

### 3.1 核心思路

**修复后期望**:满足上述全部条件的脏数据 = 0 行。

> 因为修复后系统不再标 `IRBM_STATE = 'N'` 给"无费用项 + 收款"场景。

### 3.2 时间窗确认

**用户原话**:"按 6.10 以后修复的" / "调整下时间至 6.16"


| 时间窗下界 | 来源                |
| ----- | ----------------- |
| 6.10  | 用户第一次确认           |
| 6.16  | 用户第二次调整(避开部署当天边界) |


**验证用时间窗**:`INVOICE_END_DATE >= DATE '2026-06-16'`

### 3.3 COUNT 版本(只验行数)

```sql
-- 修复验证 v2 (6.16 之后,期望 0 行)
-- 用 CREATE_DATE 不是 INVOICE_END_DATE: IRBM_STATE 在 invoice 生成时确定
SELECT COUNT(*) AS dirty_count
FROM CC.E_INVOICE A
INNER JOIN CC.ACCT_ATTR_VALUE B ON A.ACCT_ID = B.ACCT_ID
INNER JOIN CC.BILL E ON A.E_INVOICE_ID = E.E_INVOICE_ID
WHERE B.ATTR_ID = '907207'
  AND A.IRBM_STATE = 'N'
  AND B.ATTR_VALUE NOT IN ('TESTLINE')
  AND A.CREATE_DATE >= DATE '2026-06-16'
  AND E.RECV_CHARGE <> 0
  AND NOT EXISTS (
      SELECT 1
      FROM CC.ACCT_ITEM C
      INNER JOIN CC.BILLING_CYCLE D ON C.BILLING_CYCLE_ID = D.BILLING_CYCLE_ID
      WHERE A.ACCT_ID = C.ACCT_ID
        AND D.INVOICE_DATE >= DATE '2026-06-16'
  );
```

**判定**:

- `dirty_count = 0` → ✅ 修复有效
- `dirty_count > 0` → ❌ 仍有脏数据

### 3.4 按月份分布版本(辅助定位)

```sql
-- 按 CREATE_DATE 月份切分 (帮助定位是哪个账期残留)
SELECT TO_CHAR(A.CREATE_DATE, 'YYYY-MM') AS ym, COUNT(*) AS cnt
FROM CC.E_INVOICE A
INNER JOIN CC.ACCT_ATTR_VALUE B ON A.ACCT_ID = B.ACCT_ID
INNER JOIN CC.BILL E ON A.E_INVOICE_ID = E.E_INVOICE_ID
WHERE B.ATTR_ID = '907207'
  AND A.IRBM_STATE = 'N'
  AND B.ATTR_VALUE NOT IN ('TESTLINE')
  AND A.CREATE_DATE >= DATE '2026-06-16'
  AND E.RECV_CHARGE <> 0
  AND NOT EXISTS (
      SELECT 1
      FROM CC.ACCT_ITEM C
      INNER JOIN CC.BILLING_CYCLE D ON C.BILLING_CYCLE_ID = D.BILLING_CYCLE_ID
      WHERE A.ACCT_ID = C.ACCT_ID
        AND D.INVOICE_DATE >= DATE '2026-06-16'
  )
GROUP BY TO_CHAR(A.CREATE_DATE, 'YYYY-MM')
ORDER BY ym;
```

---

## 四、ytlc-test 环境连接

```
Oracle: 192.168.123.1:51005/cc
User:   cc
DB Link: @LINK_RB
CRM:    @LINK_CRM
凭证: ~/.hermes/profiles/ytlc-test/.env (TEST_DB_PWD, chmod 600)
```

**注意**:测试环境 schema 简化为 `cc`(不是生产的 `bss_ms_chenjing`),DB Link 是 `@LINK_RB`(不是生产的 `@LINK2RB`)。

Python 调用样例:

```python
import oracledb, os
conn = oracledb.connect(
    user='cc',
    password=os.environ['TEST_DB_PWD'],
    dsn='192.168.123.1:51005/cc'
)
cur = conn.cursor()
cur.execute("""SELECT COUNT(*) FROM CC.E_INVOICE WHERE ...""")
```

---

## 五、生产基线(已查,作为对照)

**🔴 生产 (192.168.123.1:51008)** 用户当前 profile = ytlc(生产)


| 时间窗     | dirty_count |
| ------- | ----------- |
| 6.10 之后 | 352         |
| 6.16 之后 | 217         |


**全部在 2026-06 账期**。

**样本(6.16 之后的 217 行中 5 条)**:


| E_INVOICE_NBR      | CREATE_DATE      | ACCT_NBR  | CC               | RECV_CHARGE | INVOICE_END_DATE |
| ------------------ | ---------------- | --------- | ---------------- | ----------- | ---------------- |
| INV202606097414032 | 2026-06-11 16:17 | 843051947 | NON_VIP_CUSTOMER | -615000     | 2026-06-10       |
| INV202606098469900 | 2026-06-11 16:17 | 840632069 | NON_VIP_CUSTOMER | -118000     | 2026-06-10       |
| INV202606097419963 | 2026-06-11 16:17 | 302164050 | NON_VIP_CUSTOMER | -102500     | 2026-06-10       |
| INV202606098469908 | 2026-06-11 16:17 | 841603656 | NON_VIP_CUSTOMER | -2100000    | 2026-06-10       |
| INV202606098469909 | 2026-06-11 16:17 | 843356844 | NON_VIP_CUSTOMER | -4050000    | 2026-06-10       |


**关键观察**:

- `RECV_CHARGE` 全是**负数**(可能 = 退款/CN,不是新收款)
- 全是 `NON_VIP_CUSTOMER`
- `IRBM_STATE` 仍是 `N`

**结论**:生产 217 行 = 修复**前**残留数据(版本未升级),不能作为修复有效性证据。

---

## 六、ytlc-test 验证步骤

### Step 1 — 确认 ytlc-test 版本

```bash
# 查 ytlc-test 的部署版本
# (可能方式:查部署日志、release note、问 R&D/ops)
```

**关键问题**:ytlc-test 是不是 v9m.2.23?如果不是,验证无效。

### Step 2 — 跑修复验证 SQL

```python
# 跑第 3.3 节 COUNT 版本
# 期望 dirty_count = 0
```

**判读**:

- 0 行 → ✅ 修复有效
- > 0 行 → ❌ 检查 Step 1(确认版本)+ 切分脏数据特征(类似生产样本的切分方式)

### Step 3 — 如果 ytlc-test 没自然数据

如果测试库没产生过"无费用项 + 收款"场景,SQL 可能直接返回 0,**但这不是修复有效,是测试环境无数据**。

→ 需要在 ytlc-test 主动构造场景:

- 找一个只有 payment 没有 charge item 的 BA
- 触发发票生成
- 查 `CC.E_INVOICE` 的 `IRBM_STATE` 是否正确标为 'Y'

### Step 4 — 如果 ytlc-test 有数据,做特征切分

跟生产样本类似的切分(只读查询):

- `RECV_CHARGE` 符号分布(正/负/零)
- `ATTR_VALUE` 值分布
- `ACCT_NBR` 前缀 / 客户类型
- `IRBM_STATE` 其他取值(Y / P / E / ...)

---

## 九、🆕 正向验证(必须补做)— "零金额 invoice 生成 + 自动写 ITEMISED_FEE + 提交 IRBM"

### 9.0 修复本质(用户 2026-06-22 二次纠正后)

**关键认知更正**:

> "哎 当初这些0费用不写表的啊。客户要求了 我进行了数据补充才入了ITEMISED_FEE,但版本升级后 这些数据会入表 明白了吗"

**修复前行为**:

- 系统对"零金额发票"(只有 payment, 无费用项)**不写 `E_INVOICE_ITEMISED_FEE`**
- 系统判 `IRBM_STATE = 'N'`(无需通知) → 不提交 IRBM
- 客户监管要求后, chen.jing **手工往 ITEMISED_FEE 补行**, 让这些发票能识别 / 提交

**修复后行为(v9m.2.23)**:

- 即使发票费用为 0, 系统也**自动写 `E_INVOICE_ITEMISED_FEE` 行**(可能金额 = 0 的占位行)
- 走完整 IRBM 校验流程, `IRBM_STATE` 应该是 **A → C / F**(待校验 → 校验通过)

**⚠️ 不能再用 `ITEMISED_FEE` 是否有行作为判定修复的标志** — 历史数据已手工补齐, 6.16 之前后的 ITEMISED_FEE 都有行。

### 9.0.1 验证范围(用户 2026-06-22 最终确认)

> "正常测试思路是6.16以后,符合0费用逻辑 会生成的记录 应该是irbm state不为N的记录, 同时 ITEMISED_FEE 也产生了对应了展位记录, 同时只针对 e invoice type 为 7 的记录"

**验证范围 = 同时满足**:

1. `A.CREATE_DATE >= '2026-06-16'` (修复后生成)
2. 符合"零费用"逻辑: `E.RECV_CHARGE <> 0` AND 当月**无 ACCT_ITEM** (用户原 SQL 核心条件)
3. `A.IRBM_STATE <> 'N'` (修复后期望)
4. `CC.E_INVOICE_ITEMISED_FEE` 有对应占位记录 (修复后期望)
5. `A.E_INVOICE_TYPE = '7'` (Regular Invoice, BILL_FLOW 体系后付费)

**E_INVOICE_TYPE=7 排除什么**:

- 不查 Type 1-6, 8-9(DOC 体系 / 预付费 / 取消发票等)
- ZTPD-1542 修复只针对 Regular Invoice(type 7) 后付费常规发票

### 9.1 修复后期望的 IRBM_STATE 分布(KB 权威值域)


| 值     | 含义          | 修复后期望                             |
| ----- | ----------- | --------------------------------- |
| A     | 待校验         | 修复后新生成的可能短暂处于此状态                  |
| B     | Portal 校验失败 | 个别, 不应大量出现                        |
| C     | Portal 校验通过 | OK                                |
| D     | Portal 网络异常 | 个别, 重试后会变 C/F                     |
| E     | IRBM 校验失败   | 个别, 不应大量出现                        |
| F     | IRBM 校验通过   | 期望大部分                             |
| **N** | **无需通知**    | **❌ 修复后期望 = 0** (这是 bug 状态, 应被消除) |


### 9.2 反向验证 SQL(主)— 6.16 之后, Type=7, 零金额发票还有多少 N 状态

```sql
-- 反向验证: 6.16 之后, Type=7, "零费用 + 收款" 的发票, IRBM_STATE='N' 的数量
-- 期望: 0 行 (修复后系统不应再标 N)
SELECT COUNT(*) AS dirty_count
FROM CC.E_INVOICE A
INNER JOIN CC.ACCT_ATTR_VALUE B ON A.ACCT_ID = B.ACCT_ID
INNER JOIN CC.BILL E ON A.E_INVOICE_ID = E.E_INVOICE_ID
WHERE B.ATTR_ID = '907207'
  AND A.IRBM_STATE = 'N'
  AND A.E_INVOICE_TYPE = '7'                       -- Regular Invoice
  AND B.ATTR_VALUE NOT IN ('TESTLINE')
  AND A.CREATE_DATE >= DATE '2026-06-16'
  AND E.RECV_CHARGE <> 0
  AND NOT EXISTS (
      SELECT 1
      FROM CC.ACCT_ITEM C
      INNER JOIN CC.BILLING_CYCLE D ON C.BILLING_CYCLE_ID = D.BILLING_CYCLE_ID
      WHERE A.ACCT_ID = C.ACCT_ID
        AND D.INVOICE_DATE >= DATE '2026-06-16'
  );
```

**判定**:

- `dirty_count = 0` → ✅ 修复有效
- `dirty_count > 0` → ❌ 修复未生效 / 仅部分覆盖

### 9.3 正向验证 SQL — 6.16 之后, Type=7, 零金额发票的 IRBM_STATE 分布

```sql
-- 正向验证: 6.16 之后, Type=7, 零金额发票, IRBM_STATE 分布
SELECT A.IRBM_STATE, COUNT(*) AS cnt
FROM CC.E_INVOICE A
INNER JOIN CC.ACCT_ATTR_VALUE B ON A.ACCT_ID = B.ACCT_ID
INNER JOIN CC.BILL E ON A.E_INVOICE_ID = E.E_INVOICE_ID
WHERE B.ATTR_ID = '907207'
  AND A.E_INVOICE_TYPE = '7'                       -- Regular Invoice
  AND B.ATTR_VALUE NOT IN ('TESTLINE')
  AND A.CREATE_DATE >= DATE '2026-06-16'
  AND E.RECV_CHARGE <> 0
  AND NOT EXISTS (
      SELECT 1
      FROM CC.ACCT_ITEM C
      INNER JOIN CC.BILLING_CYCLE D ON C.BILLING_CYCLE_ID = D.BILLING_CYCLE_ID
      WHERE A.ACCT_ID = C.ACCT_ID
        AND D.INVOICE_DATE >= DATE '2026-06-16'
  )
GROUP BY A.IRBM_STATE
ORDER BY cnt DESC;
```

**修复后期望分布**:

- `N` 应该 = 0
- `A` / `C` / `F` 应占绝大多数(走完 IRBM 流程)

### 9.4 ITEMISED_FEE 写入验证(辅助)— 修复后新生成的 Type=7 零金额发票应该有 ITEMISED_FEE 行

```sql
-- ITEMISED_FEE 行验证: 6.16 之后, Type=7, 零金额发票, ITEMISED_FEE 是否被自动写入
SELECT 
  CASE WHEN f.fee_count IS NULL THEN 0 ELSE f.fee_count END AS fee_count,
  COUNT(*) AS invoice_count
FROM CC.E_INVOICE A
INNER JOIN CC.ACCT_ATTR_VALUE B ON A.ACCT_ID = B.ACCT_ID
INNER JOIN CC.BILL E ON A.E_INVOICE_ID = E.E_INVOICE_ID
LEFT JOIN (
  SELECT E_INVOICE_ID, COUNT(*) AS fee_count
  FROM CC.E_INVOICE_ITEMISED_FEE
  GROUP BY E_INVOICE_ID
) f ON f.E_INVOICE_ID = A.E_INVOICE_ID
WHERE B.ATTR_ID = '907207'
  AND A.E_INVOICE_TYPE = '7'                       -- Regular Invoice
  AND B.ATTR_VALUE NOT IN ('TESTLINE')
  AND A.CREATE_DATE >= DATE '2026-06-16'
  AND A.IRBM_STATE <> 'N'
  AND E.RECV_CHARGE <> 0
  AND NOT EXISTS (
      SELECT 1 FROM CC.ACCT_ITEM C
      INNER JOIN CC.BILLING_CYCLE D ON C.BILLING_CYCLE_ID = D.BILLING_CYCLE_ID
      WHERE A.ACCT_ID = C.ACCT_ID
        AND D.INVOICE_DATE >= DATE '2026-06-16'
  )
GROUP BY f.fee_count
ORDER BY invoice_count DESC;
```

**修复后期望**: `fee_count > 0` 的发票应该占绝大多数(系统自动补 ITEMISED_FEE 行)

### 9.5 端到端正向验证 SQL(终极)— 同时验证 IRBM_STATE 不为 N + ITEMISED_FEE 有占位行

```sql
-- 端到端: 6.16 之后, Type=7, 零金额发票, IRBM_STATE<>N 且 ITEMISED_FEE 有行
-- 期望: 全部满足(零异常)
SELECT 
  COUNT(*) AS total_invoice,
  SUM(CASE WHEN A.IRBM_STATE <> 'N' THEN 1 ELSE 0 END) AS irbm_not_n,
  SUM(CASE WHEN f.E_INVOICE_ID IS NOT NULL THEN 1 ELSE 0 END) AS has_itemised_fee,
  SUM(CASE WHEN A.IRBM_STATE <> 'N' AND f.E_INVOICE_ID IS NOT NULL THEN 1 ELSE 0 END) AS both_ok
FROM CC.E_INVOICE A
INNER JOIN CC.ACCT_ATTR_VALUE B ON A.ACCT_ID = B.ACCT_ID
INNER JOIN CC.BILL E ON A.E_INVOICE_ID = E.E_INVOICE_ID
LEFT JOIN CC.E_INVOICE_ITEMISED_FEE f ON f.E_INVOICE_ID = A.E_INVOICE_ID
WHERE B.ATTR_ID = '907207'
  AND A.E_INVOICE_TYPE = '7'                       -- Regular Invoice
  AND B.ATTR_VALUE NOT IN ('TESTLINE')
  AND A.CREATE_DATE >= DATE '2026-06-16'
  AND E.RECV_CHARGE <> 0
  AND NOT EXISTS (
      SELECT 1 FROM CC.ACCT_ITEM C
      INNER JOIN CC.BILLING_CYCLE D ON C.BILLING_CYCLE_ID = D.BILLING_CYCLE_ID
      WHERE A.ACCT_ID = C.ACCT_ID
        AND D.INVOICE_DATE >= DATE '2026-06-16'
  )
GROUP BY ()
HAVING COUNT(*) > 0;
```

**判定**:

- `total_invoice = both_ok` → ✅ 完全修复
- `irbm_not_n < total_invoice` → ❌ 部分发票还停留在 N
- `has_itemised_fee < total_invoice` → ❌ 部分发票未自动写 ITEMISED_FEE

### 9.6 主动构造场景(如果 ytlc-test 自然数据不足)

如果测试库没有"无费用项 + 收款"的自然样本, 需要手工触发:

**方式 A — 在 ytlc-test 直接调用 billing 流程**:

- 用一个只有 payment 没有 charge 的 BA
- 触发 invoice 生成 / BillGen
- 查 `CC.E_INVOICE` 的 `IRBM_STATE`(确认不等于 'N')
- 查 `CC.E_INVOICE_ITEMISED_FEE` 是否被自动写入
- 确认 `E_INVOICE_TYPE = '7'`

**方式 B — 直接 INSERT 模拟**(仅测试环境允许):

- 手工 INSERT 一条 `E_INVOICE_TYPE='7'` 的 invoice
- 触发 IRBM 提交流程
- 检查 `IRBM_STATE` 和 `ITEMISED_FEE`

**方式 C — 用 R&D 测试脚本**:

- 问 Chai 拿 v9m.2.23 的 R&D 测试脚本/用例
- 直接跑他们的 case 验证

### 9.7 完整验证 checklist(更新后)

- [ ] **Step 1** ytlc-test 已部署 v9m.2.23
- [ ] **Step 2 A** 反向 (9.2): 6.16 之后 Type=7 零金额发票还是 N 状态的数量, 期望 0
- [ ] **Step 2 B** 正向 (9.3): 6.16 之后 Type=7 零金额发票的 IRBM_STATE 分布, 期望全部非 N
- [ ] **Step 2 C** ITEMISED_FEE 验证 (9.4): 6.16 之后 Type=7 非 N 发票 ITEMISED_FEE 行数, 期望 > 0
- [ ] **Step 2 D** 端到端 (9.5): IRBM_STATE<>N + ITEMISED_FEE 有行, 期望覆盖 100%
- [ ] **Step 3** (可选)自然数据不足时主动构造场景
- [ ] **Step 4** 特征切分(确认是否某类账户 / 某类发票被遗漏)

### 9.8 完整结论模板

```
✅ 修复有效:
  - 反向 (9.2): dirty_count = 0
  - 正向 (9.3): 6.16 之后 Type=7 零金额发票 IRBM_STATE 全部分布在 A/C/F, N=0
  - ITEMISED_FEE (9.4): fee_count > 0 占绝大多数
  - 端到端 (9.5): both_ok = total_invoice (100% 满足)

❌ 修复失败(任一):
  - 反向: dirty_count > 0(仍有新生成的脏数据)
  - 正向: 仍有 N 状态(代码分支仍短路)
  - ITEMISED_FEE: 非 N 发票中仍有大量 fee_count=0(系统未自动补行)
  - 端到端: both_ok < total_invoice(部分异常)
```

---

## 七、待确认 / 待验证

- [ ] ytlc-test 是否已部署 v9m.2.23
- [ ] ytlc-test 是否存在"无费用项 + 收款"场景的样本数据
- [ ] 修复代码覆盖范围(VIP / NON_VIP / 全部?)
- [ ] `RECV_CHARGE < 0` 是否 = 退款凭证(可能本来就不该提交 IRBM)
- [ ] 测试环境能否手工触发场景做正向验证

---

## 八、文件清单

```
~/Desktop/billing-kb/cases/ZTPD-1542/
└── verification_record.md  ← 本文件
```

---

## 十一、认知更新历程(留作下次排查参考)

### 2026-06-22 第一次理解(错)

- 以为 ZTPD-1542 修复是 "判断是否提交 IRBM" 的逻辑 bug
- 验证方向: 跑 SQL 看修复后 `IRBM_STATE='N'` 数量是否 = 0

### 2026-06-22 第二次纠正(用户原话)

> "这样验证还缺一环 还要补上 生成了 itemfee 为0的数据 才算功能正常"

- 补充正向验证: 零金额 invoice 生成时 ITEMISED_FEE 应该有数据

### 2026-06-22 第三次纠正(用户原话,关键)

> "哎 当初这些0费用不写表的啊。客户要求了 我进行了数据补充才入了ITEMISED_FEE,但版本升级后 这些数据会入表 明白了吗"

- **修复本质**: v9m.2.23 修复后, 系统会**自动写** ITEMISED_FEE 行(即使费用为 0 也写占位行)
- 修复前: 零金额发票 ITEMISED_FEE **不写**, 系统判 `IRBM_STATE='N'`, 不提交
- chen.jing 历史上手工补过 ITEMISED_FEE 数据
- **判定修复有效的标志**: `IRBM_STATE='N'` 的新生成发票数量应该 ≈ 0, 且 `IRBM_STATE` 应分布在 A/C/F(走完 IRBM 流程)

### 2026-06-22 第四次精确化(用户原话,定稿)

> "正常测试思路是6.16以后,符合0费用逻辑 会生成的记录 应该是irbm state不为N的记录, 同时 ITEMISED_FEE 也产生了对应了展位记录, 同时只针对 e invoice type 为 7 的记录"

- 验证范围收窄: 只看 `E_INVOICE_TYPE = '7'` (Regular Invoice, BILL_FLOW 体系后付费)
- 验证逻辑收窄: 6.16 之后 + 零费用逻辑 + `IRBM_STATE <> 'N'` + `ITEMISED_FEE` 有占位行 — **四条件必须同时满足**
- ZTPD-1542 修复只针对 Regular Invoice 后付费常规发票

### 关键表实际状态(2026-06-22 生产实测)


| 表                           | 字段                      | 实际状态                                              |
| --------------------------- | ----------------------- | ------------------------------------------------- |
| `CC.E_INVOICE`              | `IRBM_STATE`            | N=无需通知, F=校验通过(6M 条), A/B/C/D/E 各有分布              |
| `CC.E_INVOICE_ITEMISED_FEE` | `AMOUNT` 等              | 历史手工补齐, 不能用"是否有行"判定修复                             |
| `CC.E_INVOICE_GEN_LOG`      | `EMPTY_BILL`, `BILL_ID` | **不要用这表关联 E_INVOICE**, 全表 EMPTY_BILL='Y', 关联匹配率极低 |
| `CC.BILL`                   | `E_INVOICE_ID`          | E_INVOICE 跟 BILL 通过 `E_INVOICE_ID` 关联             |


### 关联路径(正确)

```
CC.E_INVOICE (主表)
  ↓ E_INVOICE_ID
CC.E_INVOICE_ITEMISED_FEE (逐项费用行)
  ↓ CLASS_ID
CC.E_INVOICE_CLASSIFICATION (税码)
  ↓ E_INVOICE_ID
CC.E_INVOICE_IRBM_LOG (提交日志)

CC.BILL (通过 E_INVOICE_ID 关联 E_INVOICE, 提供 RECV_CHARGE)
```

---

**创建日**: 2026-06-22
**作者**: chen.jing (计费诊断)
**目的**: ytlc-test 修复验证交接记录
**更新**: 2026-06-22 三次纠正后定稿 §9, 加 §11 认知历程