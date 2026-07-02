# ZTPD-1542 修复测试 Checklist

> **给测试人员用** — 一步一步跑,跑完打勾即可。
> 内部细节 / 字段名考据见 `verification_record.md`。

---

## 0. 背景速览

- **Bug**: 发票只含支付、分类代码全 0 时,系统标 `IRBM_STATE='N'`(无需通知)→ 不提交 IRBM。BRD 要求所有发票都应提交。
- **修复版本**: v9m.2.23(R&D Task 5588)
- **修复后行为**: 即使费用为 0, 系统也会自动写 `E_INVOICE_ITEMISED_FEE` 占位行, `IRBM_STATE` 走完整流程(A → C/F), 不再是 `N`。
- **本次修复只针对 Regular Invoice**: `E_INVOICE_TYPE = '7'`(BILL_FLOW 体系后付费)。Type 1-6 / 8-9 不在本次范围。

---

## 1. 前置条件(动手前先确认)

| # | 检查项 | 怎么验 | 通过标志 |
|---|---|---|---|
| 1.1 | 当前 profile 是 `ytlc-test` | `hermes profile show` 或看 `~/.hermes/profiles/ytlc-test/.env` 有 `TEST_DB_PWD` | ✅ 是 ytlc-test |
| 1.2 | 测试库连得上 | `python3 -c "import oracledb, os; print(oracledb.connect(user='cc', password=os.environ['TEST_DB_PWD'], dsn='192.168.123.1:51005/cc').version)"` | ✅ 输出 Oracle 版本号 |
| 1.3 | **测试库部署的是 v9m.2.23** | 问 R&D / Ops / 查部署日志 | ✅ 是 v9m.2.23 或更新 |
| 1.4 | 6.16 之后有"零费用发票"自然数据 | 跑第 2.2 节 SQL 看 `total_invoice > 0` | ✅ 有数据 |

> ⚠️ **1.3 是关键**: 不是 v9m.2.23 跑出来的结果无效, 别浪费时间。

---

## 2. 测试用例

### 2.1 反向验证(脏数据清零)

**目的**: 修复后, 6.16 之后再也不应产生 `IRBM_STATE='N'` 的零费用发票。

**SQL**:

```sql
SELECT COUNT(*) AS dirty_count
FROM CC.E_INVOICE A
INNER JOIN CC.ACCT_ATTR_VALUE B ON A.ACCT_ID = B.ACCT_ID
INNER JOIN CC.BILL E ON A.E_INVOICE_ID = E.E_INVOICE_ID
WHERE B.ATTR_ID = '907207'
  AND A.IRBM_STATE = 'N'
  AND A.E_INVOICE_TYPE = '7'
  AND B.ATTR_VALUE NOT IN ('TESTLINE')
  AND A.CREATE_DATE >= DATE '2026-06-16'
  AND E.RECV_CHARGE <> 0
  AND NOT EXISTS (
      SELECT 1 FROM CC.ACCT_ITEM C
      INNER JOIN CC.BILLING_CYCLE D ON C.BILLING_CYCLE_ID = D.BILLING_CYCLE_ID
      WHERE A.ACCT_ID = C.ACCT_ID
        AND D.INVOICE_DATE >= DATE '2026-06-16'
  );
```

**预期**:
- `dirty_count = 0` → ✅ PASS
- `dirty_count > 0` → ❌ FAIL → 转第 5 节「失败排查」

---

### 2.2 正向验证(状态分布)

**目的**: 6.16 之后所有零费用发票都应该走完 IRBM 流程, 不再停留 `N`。

**SQL**:

```sql
SELECT A.IRBM_STATE, COUNT(*) AS cnt
FROM CC.E_INVOICE A
INNER JOIN CC.ACCT_ATTR_VALUE B ON A.ACCT_ID = B.ACCT_ID
INNER JOIN CC.BILL E ON A.E_INVOICE_ID = E.E_INVOICE_ID
WHERE B.ATTR_ID = '907207'
  AND A.E_INVOICE_TYPE = '7'
  AND B.ATTR_VALUE NOT IN ('TESTLINE')
  AND A.CREATE_DATE >= DATE '2026-06-16'
  AND E.RECV_CHARGE <> 0
  AND NOT EXISTS (
      SELECT 1 FROM CC.ACCT_ITEM C
      INNER JOIN CC.BILLING_CYCLE D ON C.BILLING_CYCLE_ID = D.BILLING_CYCLE_ID
      WHERE A.ACCT_ID = C.ACCT_ID
        AND D.INVOICE_DATE >= DATE '2026-06-16'
  )
GROUP BY A.IRBM_STATE
ORDER BY cnt DESC;
```

**预期分布**:

| IRBM_STATE | 含义 | 期望 |
|---|---|---|
| N | 无需通知 | **= 0 行**(bug 状态, 应被消除) |
| A | 待校验 | OK(短期过渡) |
| C | Portal 校验通过 | OK |
| F | IRBM 校验通过 | OK(大部分) |
| B / D / E | 失败/异常 | 个别, 不应大量 |

✅ PASS 条件: `N = 0` 且 C/F 占大多数。

---

### 2.3 ITEMISED_FEE 自动写入验证

**目的**: 修复后, 零费用发票应该被自动写 `E_INVOICE_ITEMISED_FEE` 占位行。

**SQL**:

```sql
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
  AND A.E_INVOICE_TYPE = '7'
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

**预期**:
- `fee_count > 0` 的发票应该占绝大多数
- ❌ 如果 `fee_count = 0` 的还很多 → 修复未生效 / 代码分支没走到

---

### 2.4 端到端验证(综合)

**目的**: 一次性检查 `IRBM_STATE <> 'N'` **且** `ITEMISED_FEE` 有行, 两个条件必须同时满足。

**SQL**:

```sql
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
  AND A.E_INVOICE_TYPE = '7'
  AND B.ATTR_VALUE NOT IN ('TESTLINE')
  AND A.CREATE_DATE >= DATE '2026-06-16'
  AND E.RECV_CHARGE <> 0
  AND NOT EXISTS (
      SELECT 1 FROM CC.ACCT_ITEM C
      INNER JOIN CC.BILLING_CYCLE D ON C.BILLING_CYCLE_ID = D.BILLING_CYCLE_ID
      WHERE A.ACCT_ID = C.ACCT_ID
        AND D.INVOICE_DATE >= DATE '2026-06-16'
  )
HAVING COUNT(*) > 0;
```

**判定**:

| 检查项 | 通过条件 |
|---|---|
| `total_invoice > 0` | 测试库得有零费用发票数据 |
| `irbm_not_n = total_invoice` | 100% 走完 IRBM, 无 N |
| `has_itemised_fee = total_invoice` | 100% 自动写 ITEMISED_FEE |
| **`both_ok = total_invoice`** | ⭐ **核心 PASS 标志** |

---

## 3. 主动构造场景(测试库无自然数据时)

如果 2.1 跑出来 `dirty_count = 0` 但 `total_invoice = 0`(没数据), 这不算修复有效, 是测试库没样本。**必须主动构造**:

### 方式 A — 触发 billing 流程(推荐)

1. 在 ytlc-test 找一个 BA, 该 BA 只有 payment 没有 charge item
2. 触发 invoice 生成(等账期 / 手动跑 BillGen)
3. 等 IRBM 提交完成后查:
   ```sql
   SELECT A.E_INVOICE_NBR, A.E_INVOICE_TYPE, A.IRBM_STATE, 
          (SELECT COUNT(*) FROM CC.E_INVOICE_ITEMISED_FEE f WHERE f.E_INVOICE_ID = A.E_INVOICE_ID) AS fee_count
   FROM CC.E_INVOICE A
   WHERE A.CREATE_DATE >= DATE '2026-06-16'
     AND A.E_INVOICE_TYPE = '7'
     AND A.ACCT_ID = <BA 的 ACCT_ID>
   ORDER BY A.CREATE_DATE DESC
   FETCH FIRST 5 ROWS ONLY;
   ```
4. **预期**: `IRBM_STATE ∈ (A, C, F)` **且** `fee_count > 0`

### 方式 B — 找 R&D 测试脚本

问 Chai / R&D 拿 v9m.2.23 的测试用例, 直接跑他们写的 case。

---

## 4. 测试结论

把结果填下面, 发给 R&D / Ops:

```
【ZTPD-1542 修复验证】
测试环境: ytlc-test (192.168.123.1:51005)
部署版本: v9m.2.23 ✓
测试日期: YYYY-MM-DD
测试人: <name>

[ ] 2.1 反向: dirty_count = ___(期望 0)
[ ] 2.2 正向: IRBM_STATE 分布 ___(期望 N=0)
[ ] 2.3 ITEMISED_FEE: fee_count>0 占比 ___(期望 > 95%)
[ ] 2.4 端到端: both_ok / total_invoice = ___(期望 100%)
[ ] 3.   主动构造场景(若适用): PASS / FAIL / N/A

结论: ✅ 修复有效 / ❌ 修复失败(详见 5)
```

---

## 5. 失败排查

如果任一检查 FAIL, 按下面顺序查:

| 现象 | 排查方向 |
|---|---|
| 2.1 `dirty_count > 0` | ① 确认 1.3 版本号对不对; ② 抓样本看 `ATTR_VALUE` / 客户类型有没有规律 |
| 2.2 `N` 还有残留 | 同上, 看是否某类账户(NON_VIP/VIP)被遗漏 |
| 2.3 `fee_count = 0` 多 | 系统没自动补 ITEMISED_FEE 行, 代码分支走偏 |
| 2.4 `both_ok < total_invoice` | 看具体哪些发票 IRBM_STATE=N 或 ITEMISED_FEE 没行, 切样本 |
| 1.4 测试库没数据 | 走第 3 节主动构造场景 |

---

## 6. 关键环境 / 表参考

```
测试库连接:
  Oracle:   192.168.123.1:51005/cc
  User:     cc
  RB Link:  @LINK_RB
  凭证:     ~/.hermes/profiles/ytlc-test/.env (TEST_DB_PWD)

涉及表:
  CC.E_INVOICE                  主表, 含 IRBM_STATE, E_INVOICE_TYPE, CREATE_DATE
  CC.E_INVOICE_ITEMISED_FEE     占位行验证
  CC.BILL                       通过 E_INVOICE_ID 关联
  CC.ACCT_ATTR_VALUE            ATTR_ID=907207 是客户分类
  CC.ACCT_ITEM / BILLING_CYCLE  判断当月是否无费用项

关键字段值域:
  IRBM_STATE: A/B/C/D/E/F/N(没有 Y/P/U, 别猜)
  E_INVOICE_TYPE: 7 = Regular Invoice(BILL_FLOW 后付费常规发票)
  ATTR_ID: 907207 = 客户分类
```

---

## 7. 变更记录

| 日期 | 版本 | 说明 |
|---|---|---|
| 2026-06-22 | v1.0 | 初版, 基于 verification_record 提炼 |