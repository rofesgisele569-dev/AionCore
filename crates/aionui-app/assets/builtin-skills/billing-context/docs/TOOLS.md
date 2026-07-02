# SM81 Billing 工具参考

> ⚠️ 生产/测试环境严格区分，表名/SQL 通用，连接信息不同。

---

## 一、环境连接

### 生产环境

```
Oracle: 192.168.123.1:51008/cc
User:   bss_ms_chenjing
DB Link: @LINK2RB  (→ RB / INV schema)
CRM:    直连 CRM.ORDER_ITEM, 无需 LINK
```

```python
import oracledb
conn = oracledb.connect(user='bss_ms_chenjing', password='ChenJing123@@.', dsn='192.168.123.1:51008/cc')

# 跨库查 RB 表
cur.execute("SELECT * FROM RB.EVENT_RECURRING_2909@LINK2RB WHERE ...")
```

### 测试环境

```
Oracle: 192.168.123.1:51005/cc
User:   cc
DB Link: @LINK_RB  (→ RB / INV schema)
CRM:    需 @LINK_CRM
```

```python
import oracledb
conn = oracledb.connect(user='cc', password='Jsmart.868', dsn='192.168.123.1:51005/cc')

# 跨库查 RB 表
cur.execute("SELECT * FROM RB.EVENT_RECURRING_2909@LINK_RB WHERE ...")
```

### 环境差异速查

| | 生产 | 测试 |
|---|---|---|
| 端口 | 51008 | 51005 |
| 用户 | bss_ms_chenjing | cc |
| RB LINK | **LINK2RB** | **LINK_RB** |
| CRM LINK | 直连 | @LINK_CRM |
| EVENT_RECURRING 表 | `RB.EVENT_RECURRING_${CYCLE}@LINK2RB` | `RB.EVENT_RECURRING_${CYCLE}@LINK_RB` |

---

## 二、查询方式

### 方式 A：Python 直连（推荐，本次排查使用的）

优势：灵活，可直接跑多步逻辑、用正则解析 ATTR_LIST、逐行对比。无额外工具依赖。

```python
import oracledb
# 生产
conn = oracledb.connect(user='bss_ms_chenjing', password='ChenJing123@@.', dsn='192.168.123.1:51008/cc')
cur = conn.cursor()
cur.execute("SELECT * FROM RB.EVENT_RECURRING_2909@LINK2RB WHERE SUBS_ID = 61892269")
for r in cur: print(r)
```

### 方式 B：bl-billing CLI（备用）

路径: `~/.hermes/node/bin/bl-billing`

```bash
# 单条 SQL 查询（JSON 输出）
bl-billing database query --db cc --sql "SELECT COUNT(*) FROM CC.SUBS" --output json
bl-billing database query --db link2rb --sql "SELECT ... FROM RB.EVENT_RECURRING_2909@LINK2RB WHERE ..." --output json

# 出账操作（生产禁用！）
bl-billing billing rerun --cycle 2914 --account 1252571521
```

> ⚠️ bl-billing 适合单条查询和运维操作。多步排查建议 Python 直连。

---

## 三、排查步骤 × 工具对照

| 步骤 | Python 直连 | bl-billing CLI |
|---|---|---|
| Step 1 账号定位 | `cur.execute("SELECT ...")` + bind vars | `bl-billing db query --db cc --sql "..." --output json` |
| Step 2 MRC 明细 | 逐行打印 ATTR_LIST + 正则解析 | `bl-billing db query --db link2rb --sql "..." --output json`（需手动解析 ATTR_LIST） |
| Step 3 时间对齐 | Python 多表查询 + 时间比较 | 三条 CLI 命令分别查，人工对齐 |
| PROD_HIS 状态 | Python | CLI |
| Balance Share | Python | CLI |
| Rebate 链 | Python 多步 JOIN | 多次 CLI 查询 |

> ⚠️ ATTR_LIST 正则解析、三步时间对齐、逐行验证金额 → Python 直连更适合。CLI 只返回 JSON 行，需手动分析。

## 四、常用排查 SQL（环境无关）

> 替换 `${CYCLE}`、`${SUBS_ID}`、`${ACCT_ID}`、`${LINK}`(LINK2RB/LINK_RB)

```sql
-- ① 账号定位
SELECT s.SUBS_ID, s.ACCT_ID FROM CC.SUBS s WHERE s.ACC_NBR = '${PHONE}';

-- ② 账期定位
SELECT a.BILLING_CYCLE_TYPE_ID, bc.BILLING_CYCLE_ID, bc.CYCLE_BEGIN_DATE, bc.CYCLE_END_DATE
FROM CC.ACCT a JOIN CC.BILLING_CYCLE bc ON a.BILLING_CYCLE_TYPE_ID = bc.BILLING_CYCLE_TYPE_ID
WHERE a.ACCT_ID = ${ACCT_ID} AND bc.CYCLE_BEGIN_DATE <= DATE'${TARGET}' AND bc.CYCLE_END_DATE >= DATE'${TARGET}';

-- ③ MRC 明细
SELECT CHARGE1/10000, ACCT_ID1, PAID_ACCT_ID, SELF_FLAG,
       EVENT_BEGIN_TIME, EVENT_END_TIME, CREATED_DATE, ATTR_LIST
FROM RB.EVENT_RECURRING_${CYCLE}@${LINK} WHERE SUBS_ID = ${SUBS_ID}
ORDER BY CREATED_DATE;

-- ④ 计费触发消息
SELECT ID, CREATED_DATE FROM CC.ASYN_CALL_TO_BILLING
WHERE ACCT_ID = ${ACCT_ID} AND CREATED_DATE >= DATE'${RANGE}' ORDER BY CREATED_DATE;

-- ⑤ CRM 订单
SELECT ORDER_ITEM_ID, SUBS_EVENT_ID, CREATED_DATE
FROM CRM.ORDER_ITEM WHERE ACC_NBR = '${PHONE}' AND CREATED_DATE >= DATE'${RANGE}'
ORDER BY CREATED_DATE;

-- ⑥ 状态变更
SELECT PROD_STATE, PROD_STATE_DATE FROM CC.PROD_HIS
WHERE PROD_ID = ${SUBS_ID} ORDER BY PROD_STATE_DATE;

-- ⑦ Balance Share
SELECT bsd.EFF_DATE, bsd.EXP_DATE, bs.ACCT_ID FROM CC.BAL_SHARE_DETAIL bsd
JOIN CC.BAL_SHARE bs ON bsd.BAL_SHARE_ID = bs.BAL_SHARE_ID WHERE bsd.SUBS_ID = ${SUBS_ID};

-- ⑧ PROD → 月租
SELECT soa.DEFAULT_VALUE FROM CC.SUBS_PLAN_OFFER_ATTR soa
WHERE soa.OFFER_ID = (SELECT OFFER_ID FROM CC.PROD WHERE PROD_ID = ${SUBS_ID})
AND soa.ATTR_ID = 292;

-- ⑨ Rebate
SELECT f.FEE_VALUE/10000, f.ACCT_ITEM_TYPE_ID, f.OFFER_REBATE_ID
FROM CC.SUBS_AGREEMENT_INST_FEE f WHERE f.SUBS_ID = ${SUBS_ID};

-- ⑩ 合账对比
SELECT SUM(CHARGE1)/10000 FROM RB.EVENT_RECURRING_${CYCLE}@${LINK} WHERE ACCT_ID1 = ${ACCT_ID};
SELECT SUM(CHARGE)/10000 FROM RB.ACCT_ITEM_BILLING_${CYCLE}@${LINK} WHERE ACCT_ID = ${ACCT_ID};
```
