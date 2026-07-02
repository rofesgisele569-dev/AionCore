# SM81 计费系统 — 领域语言

## 发票类型 (Invoice Types)

| Type | 名称 | 体系 |
|---|---|---|
| 1 | Proforma Invoice | DOC |
| 2 | Monthly Statement | DOC |
| 3 | Annual Statement | DOC |
| 4 | Prepaid E-Invoice | DOC |
| 5 | Postpaid Sales-Invoice | DOC |
| 6 | Hotbill Sales-Invoice | DOC (HB_* 表在 INV schema，暂无 VOUCHER_CODE) |
| 4 | Prepaid E-Invoice | 独立流程 (EVENT_CHARGE → E_INVOICE，不走 DOC_FORMAT 也不走 INV) |
| 7 | Regular Invoice | BILL_FLOW |
| 8 | Postpaid Reverse Sales-Invoice | DOC (cancel) |
| 9 | Prepaid Reverse E-Invoice | DOC |

术语: Invoice Type = E_INVOICE_TYPE，来自 CC.INVOICE_TYPE 参考表

## 五层数据源体系

```
一层 事件源（费用从哪来）
  CC: EVENT_CHARGE（一次性） EVENT_PAYMENT INSTANT_PAYMENT DEPOSIT_CHARGE
  RB@LINK_RB: EVENT_RECURRING_<CYCLE>（月租） EVENT_USAGE_<CYCLE> EVENT_USAGE_C_<CYCLE>

二层 合账
  LedgerCollect (Step 2-8) → RB.ACCT_ITEM_BILLING_<CYCLE>

三层 中间层（三条路，按发票类型分流）
  Regular(type 7): YTL_BILL_RUN → INV_* (35表) → BILL_SRC → BILL_DATA → .jrxml
  Sales(type 5):   DOC_EXT_SRC → YTLC_SALES_INVOICE (DOC_FORMAT 10296)
  Prepaid(type 4): E_INVOICE_ITEMISED_FEE → DOC_EXT_SRC → PREPAID_E_INVOICE (10224)
  Hotbill(type 6): PKG_YTLC_HOTBILL → HB_* 表

四层 IRBM 电子发票
  E_INVOICE → E_INVOICE_ITEMISED_FEE → E_INVOICE_CLASSIFICATION → IRBM API

五层 订单根因
  CRM.ORDER_ITEM@LINK_CRM → SUBS_EVENT → EVENT_CHARGE / EVENT_RECURRING
```

## 两大体系

| 体系 | 发票类型 | 数据源 | 模版 | 参数 |
|---|---|---|---|---|
| DOC | 1-6, 8-9 | DOC_EXT_SRC.SRC_SCRIPT | DOC_FORMAT + Apply Rule | :E_INVOICE_NBR |
| BILL_FLOW | 7 | BILL_SRC.BILL_SRC_SQL_LOB | BILL_FLOW + BILL_FIELD → .jrxml | &BILLING_CYCLE_ID |

## DOC 体系链路

```
DOC_FORMAT_TEMPLATE_APPLY_RULE (INVOICE_TYPE → DOC_FORMAT_ID)
  → DOC_FORMAT
    → DOC_FORMAT_VER (版本管理, STATE=A 为生效)
      → DOC_FORMAT_DATASOURCE (VER → DOC_EXT_SRC)  ← 数据源
      → DOC_FORMAT_ITEM (VER → DOC_ITEM)            ← 字段标签
        → DOC_EXT_SRC (SRC_SCRIPT)
          → 参数 :E_INVOICE_NBR
```

⚠️ DOC_FORMAT_DATASOURCE 才是数据源关联表（不是 DOC_ITEM）
⚠️ DOC_ITEM 是字段标签/代码，不存 SQL

## BILL_FLOW 体系链路

```
源数据层
  CC.EVENT_CHARGE  CC.EVENT_PAYMENT
  CC.PAYMENT(SUBMIT_AMOUNT) ← ⚠️ 没有AMOUNT列  CC.INSTANT_PAYMENT
  RB.EVENT_RECURRING  RB.EVENT_USAGE  RB.EVENT_USAGE_C      (RB schema, 按账期分表 _2917)
      ↓ LedgerCollect (合账，13步出账 Step 2-8)
  RB.ACCT_ITEM_BILLING_2917                                 (RB schema, 按账期分表)
      ↓ INV.YTL_BILL_RUN 包体 (Step_10~Step_105)            ⬅ 关键！ETL 存储过程
INV 中间层（INV schema，在 RB 库内，共 35+ 表）：
  核心: INV_SUBS_DETAIL  INV_PAYMENT  INV_CDR_DATA  INV_CDR_VOICE
  明细: INV_SUBS_MRC  INV_ADD_ON_PURCHASE  INV_PLAN_ADVANCE_PAYMENT
  汇总: INV_SUBS_INFO  INV_SUBS_SUMMARY_BY_SERVICE  INV_BILL
  Hotbill: HB_SUBS_DETAIL  HB_PAYMENT  HB_ADD_ON_PURCHASE  HB_CDR_DATA (type 6，独立 SP: PKG_YTLC_HOTBILL，暂缺 VOUCHER_CODE)
      ↓ BILL_SRC (60+ SQL，从 INV/HB 视图取数)
  BILL_DATA (XML)                                           (出账结果文件)
      ↓ BILL_FIELD (字段映射，BILL_SRC SQL列 → 发票列)
Report Template (.jrxml)                                    (JasperReports 渲染)
      ↓
  PDF / 电子发票
```

## 术语表

| 术语    | 定义 |
|---|---|
| 出账     | billing run — 从 LedgerCollect 到 LedgerExport 的完整流程 |
| 重出     | rerun — Rollback → Clean → Bill → Report 的全流程重跑 |
| 回滚     | rollback — LedgerExport/LedgerCollect -D 撤销已有出账数据 |
| 账期     | billing cycle — CC.BILLING_CYCLE，一个月的计费周期 |
| 分拣     | sort_rule — SM81 计费规则路由，决定号码走哪组规则 |
| PAP      | Plan Advance Payment — 套餐预付款 (ACCT_ITEM_TYPE_ID=307) |
| MRC      | Monthly Recurring Charge — 月租费 |
| ETC      | Early Termination Charge — 提前终止费 (ACCT_ITEM_TYPE_CODE='ETC') |
| Rounding | 舍入调整 — 金额取整产生的微小调整 |
| CDR      | Call Detail Record — 话单 |
| OTC      | One Time Charges — 一次性费用 (含PAP等) |
| NB       | New Billing — 新版出账系统 (NB_* 表，当前未启用) |

## 数据库关系

```
CC  (主库)    — 账户、发票、EVENT_CHARGE、PAYMENT(SUBMIT_AMOUNT)、ACCT_BOOK(ACCT_BOOK_TYPE: F=赠送 I=账单 P=收款)、DOC/BLL配置
INV (RB库)    — 出账中间视图，通过 @LINK_RB 访问
CRM           — 客户关系、订单、商品，通过 @LINK_CRM 访问
RB            — 出账运行时表 (ACCT_ITEM_BILLING, BILL_DATA)
```

⚠️ CRM 用 `@LINK_CRM`（不是 @LINK_CC）

## 账户类型判断

查 `CC.ACCT.POSTPAID` 字段：
- `POSTPAID = 'Y'` → 后付费（走 Regular Invoice type 7 / Inv pipeline）
- `POSTPAID = 'N'` → 预付费（走 Prepaid type 4 / 直接 E_INVOICE）
- 不在 E_INVOICE 类型里绕

## 编号体系

| 编号 | 含义 | 示例 | 所在表 |
|---|---|---|---|
| BA 号 (ACCT_NBR) | 账号短号，用户可见 | 300323585 | CC.ACCT.ACCT_NBR |
| ACCT_ID | 账号内部数字ID | 1250396101 | CC.ACCT.ACCT_ID |
| ACC_NBR | 手机号/服务号（CRM用） | 01892427500 | CRM.ORDER_ITEM.ACC_NBR |
| SUBS_ID | 订户ID | 1262370965 | 多表通用 |

## 支付账本类型

`CC.ACCT_BOOK.ACCT_BOOK_TYPE` 区分交易性质：

| 类型 | 含义 | 示例 |
|---|---|---|
| F | 赠送/免费资源 | 买套餐送100条短信、赠送流量 |
| I | 账单扣费 | 后付费月结扣款 |
| P | 收款/充值 | 预付费充值、现金支付 |

⚠️ `CC.PAYMENT` 没有 `AMOUNT` 列，金额用 `SUBMIT_AMOUNT`。没有 `ACCT_ID`，通过 `ACCT_BOOK(PAYMENT_ID=ACCT_BOOK_ID)` 关联账号。

⚠️ ACC_NBR ≠ ACCT_NBR：CRM 的 ACC_NBR 是手机号，不是 BA 号。
关联 CRM 用 ACCT_ID，不要用 ACC_NBR。

## EVENT_CHARGE 状态码

| STATE | 含义 |
|---|---|
| 1 | 初始（待出账，如合约优惠每期待写入） |
| 3 | 出账合账完成（LedgerCollect 已处理，写入账单） |
| 4 | 现金购买已付款（钱已付，费用仍显示在账单上） |
| 7 | 作废 |

## 订单→计费链路

```
CRM.ORDER_ITEM.ACCT_ID
  └─ SUBS_EVENT_ID → CRM.SUBS_EVENT.EVENT_NAME (New Connection / Modify VAS / ...)
      └─ CC.EVENT_RECURRING / CC.EVENT_CHARGE (EVENT_INST_ID)
          └─ LedgerCollect → RB.ACCT_ITEM_BILLING
              └─ YTL_BILL_RUN → INV.inv_subs_detail
```

关键关联字段：
- CRM.ORDER_ITEM.ACCT_ID → CC.ACCT.ACCT_ID
- CRM.ORDER_ITEM.SUBS_ID → INV.inv_subs_detail.SUBS_ID（同值）
- ORDER_ITEM.ACCT_ID = 查订单的正确入口（不用 ACC_NBR）

## 费用交叉比对

所有 EVENT_* 源表在 RB schema，按账期分表（后缀 `_<CYCLE_ID>`），通过 `@LINK_RB` 访问。

```sql
-- ① 合账结果
SELECT ACCT_ITEM_TYPE_ID, SUM(CHARGE)
FROM RB.ACCT_ITEM_BILLING_2917@LINK_RB
WHERE ACCT_ID = ? GROUP BY ACCT_ITEM_TYPE_ID

-- ② 对比各源表（都在 RB，都是分表）
SELECT 'EVENT_RECURRING' src, ACCT_ITEM_TYPE_ID, SUM(CHARGE)
FROM RB.EVENT_RECURRING_2917@LINK_RB WHERE ACCT_ID = ? GROUP BY ACCT_ITEM_TYPE_ID
UNION ALL
SELECT 'EVENT_USAGE', ACCT_ITEM_TYPE_ID, SUM(CHARGE)
FROM RB.EVENT_USAGE_2917@LINK_RB WHERE ACCT_ID = ? GROUP BY ACCT_ITEM_TYPE_ID
UNION ALL
SELECT 'EVENT_USAGE_C', ACCT_ITEM_TYPE_ID, SUM(CHARGE)
FROM RB.EVENT_USAGE_C_2917@LINK_RB WHERE ACCT_ID = ? GROUP BY ACCT_ITEM_TYPE_ID
UNION ALL
SELECT 'EVENT_CHARGE', ACCT_ITEM_TYPE_ID, SUM(CHARGE), SUM(DISCOUNT_CHARGE)
FROM CC.EVENT_CHARGE WHERE ACCT_ID = ? AND BILLING_CYCLE_ID = ? GROUP BY ACCT_ITEM_TYPE_ID
UNION ALL
SELECT 'DEPOSIT_CHARGE', ACCT_ITEM_TYPE_ID, SUM(CHARGE)
FROM CC.DEPOSIT_CHARGE WHERE ACCT_ID = ? AND BILLING_CYCLE_ID = ? GROUP BY ACCT_ITEM_TYPE_ID
```

⚠️ EVENT_RECURRING / EVENT_USAGE / EVENT_USAGE_C 在 **RB** schema（`@LINK_RB`），按账期分表
⚠️ EVENT_CHARGE / DEPOSIT_CHARGE 在 **CC** schema，有 BILLING_CYCLE_ID 列

---

ACCT_ITEM_TYPE 从合账表查（ACCT_ITEM_BILLING 已合并全部数据源），不扫全表不硬编码：
```sql
-- 查这个账号在某个账期实际产生的费用类型
-- ACCT_ITEM_BILLING = EVENT_RECURRING + EVENT_USAGE + EVENT_CHARGE + DEPOSIT_CHARGE 合账结果
SELECT DISTINCT a.ACCT_ITEM_TYPE_ID, t.ACCT_ITEM_TYPE_CODE, t.ACCT_ITEM_TYPE_NAME
FROM RB.ACCT_ITEM_BILLING@LINK_RB a
JOIN CC.ACCT_ITEM_TYPE t ON a.ACCT_ITEM_TYPE_ID = t.ACCT_ITEM_TYPE_ID
WHERE a.ACCT_ID = 1250396101 AND a.BILLING_CYCLE_ID = 2917
```

## 关键存储过程

INV schema 下有三套包（通过 @LINK_RB 访问）：

| 包 | 用途 | 输出表 |
|---|---|---|
| YTL_BILL_RUN | Regular Invoice (type 7) | INV_* 表 |
| PKG_YTLC_HOTBILL | Hotbill (type 6) | HB_* 表 |
| YTL_BILL_RECON | 对账/Reconciliation | RECON_* 表 |

`INV.YTL_BILL_RUN` 包体（Regular Invoice）：

| 存储过程 | 输入 | 输出 |
|---|---|---|
| Step_10_CLCT_CDR | CC.EVENT_CHARGE (话单) | INV.inv_cdr_voice / inv_cdr_data |
| Step_12_CLCT_MRC | RB.EVENT_RECURRING (月租) | INV.inv_mrc |
| Step_15_ADJUSTMENT | ACCT_ITEM_BILLING (调账) | INV.inv_subs_detail |
| Step_20_CLCT_AIB | ACCT_ITEM_BILLING 全集 | INV.inv_subs_detail |
| Step_22_CLCT_PAYMENT | CC.PAYMENT | INV.inv_payment |
| Step_23_CLCT_TRANSFER | 转入转出 | — |
| Step_24_Addon_Purchase | CC.EVENT_CHARGE + INSTANT_PAYMENT | INV_ADD_ON_PURCHASE |
| Step_26_Subs_Detail | **聚合最终数据** | INV.inv_subs_detail (含 VOUCHER_CODE) |
| Step_30_Subs_Summary | 聚合 | INV.inv_subs_info / INV_BILL |
| Step_100_Bill_RPT | — | BILL_DATA |
| Step_105_Bill_Compare | — | 比对校验 |

> ⚠️ Step_24 加 ROW_NUMBER() 防 PAP 重复（2026-06-12 修复）
> ⚠️ Step_26 UPDATE 设 VOUCHER_CODE（2026-06-12 新增）

## IRBM 电子发票(马来西亚 LHDN)

```
E_INVOICE.E_INVOICE_ID (主键,关联全链路)
  ├─ E_INVOICE_ITEMISED_FEE.E_INVOICE_ID    — 逐项费用行 (修复后才自动写, 历史数据由 chen.jing 手工补充)
  │     └─ CLASS_ID → E_INVOICE_CLASSIFICATION.CLASS_ID (税码)
  ├─ E_INVOICE_IRBM_LOG.E_INVOICE_ID         — IRBM 提交日志
  └─ E_INVOICE_GEN_LOG (ACCT_ID + BILLING_CYCLE_ID 关联) — 生成日志 (历史表, 与 E_INVOICE 无强关联)
```

**重要 — IRBM_STATE 值域**:
| 值 | 含义 |
|---|---|
| A | 待校验 |
| B | Portal 校验失败 |
| C | Portal 校验通过 |
| D | Portal 网络异常 |
| E | IRBM 校验失败 |
| F | IRBM 校验通过 |
| N | **无需通知**(ZTPD-1542 修复目标: 即使零金额发票也要走 IRBM, 不再停留 N) |

**重要 — E_INVOICE_ITEMISED_FEE 写入时机**:
- **v9m.2.23 修复前**:系统对"零金额发票"(只有 payment, 无费用项)不写 `ITEMISED_FEE` → 系统判 `IRBM_STATE='N'`, 不提交 IRBM
- **v9m.2.23 修复后**:即使发票费用为 0, 系统也写 `ITEMISED_FEE` 行(可能金额 = 0) → 走完整 IRBM 校验流程
- **历史数据 chen.jing 已手工补**:修复前残留的 `IRBM_STATE='N'` 发票,已手工往 `ITEMISED_FEE` 补行, 用以应付 IRBM 监管要求

**⚠️ E_INVOICE_GEN_LOG 的实际状态(2026-06-22 chen.jing 实测)**:
- 全表 553 万行, `EMPTY_BILL` 字段全部为 'Y'
- 按 (ACCT_ID, BILLING_CYCLE_ID) 关联 E_INVOICE, 90 天内仅 6 行匹配
- ZTPD-1542 样本 INV202509019068993 在 GEN_LOG 中**无对应记录**
- 结论: 这是一个历史 / 辅助日志表, 不是 e-invoice 生成的主流程表. KB 旧描述有误, 排查时**不要通过 GEN_LOG 关联 E_INVOICE**

**⚠️ E_INVOICE_GEN_LOG.BILL_ID 关联误区**:
- 直接 `GEN_LOG.BILL_ID = BILL.BILL_ID` 几乎 0 匹配(90 天内 0 行)
- 这表的 BILL_ID 可能指老的 paper bill 系统, 跟 e-invoice 的 BILL_ID 不是同一体系
- 正确关联方式(如果非要用 GEN_LOG):按 `(ACCT_ID, BILLING_CYCLE_ID)` 关联, 但匹配率极低

IRBM 发票关键字段（CC.E_INVOICE）：
| 字段 | 说明 |
|---|---|
| E_INVOICE_ID | 主键，关联所有子表 |
| IRBM_INVOICE_NBR | IRBM 签发的发票号 |
| IRBM_STATE | A=待校验(14M) B=Portal校验失败(23K) C=Portal校验通过(33K) D=Portal网络异常(1K) E=IRBM校验失败(66K) F=IRBM校验通过(6M) N=无需通知(19K) |
| IRBM_DIGITALSIGNATURE | 数字签名 |
| IRBM_QRCODELINK | 验证二维码链接 |
| UNSIGNED_E_INVOICE_PATH | 未签名 XML 路径 |
| SIGNED_E_INVOICE_PATH | 已签名 XML 路径 |
| ERROR_MSG / ERROR_CODE | IRBM 返回的校验错误 |

入口：`billing trigger-einvoice --cycle 2917`
后端：
- Regular (type 7): `PostpaidRegularEInvoiceGenerateToIRBM` JobServer 任务
- Prepaid (type 4): 直接从 EVENT_CHARGE → E_INVOICE_TMP → E_INVOICE，不走 INV pipeline

STATE (发票生命周期): A=CREATE B=未签名生成中 C=生成成功 D=含签名生成中 E=未签名失败 F=含签名失败
CONSOLIDATE_STATE (税务合并): A=Wait B=Consolidating C=Success D=Failure E=Network Error N=No Need

## 已知问题/ADR

1. BILL_SRC[29] OTC VOUCHER_CODE + BILL_SRC[17] Add-On Discount_Charge/Ori_Charge/VOUCHER_CODE 已补全（2026-06-13）
2. BILL_FIELD[606-609] VOUCHER_CODE/Discount_Charge/Ori_Charge 字段映射已就绪（2026-06-13）
3. Subreport ADD_ON_DETAILS_LIST 加 Discount/Ori/VOUCHER 字段 + 66px Discount 列（2026-06-13）
4. Step_24 INV_ADD_ON_PURCHASE INSERT 加 ROW_NUMBER() 防 PAP 重复（2026-06-12）
5. SALE_INVOICE_PAYMENTMETHOD_INFO(10251) 均摊改 SUBMIT_AMOUNT（2026-06-11）
6. SALE_INVOICE_CHARGE_DETAILS_INFO(10265) EVENT_CHARGE_DISCOUNT JOIN 缺 DEDUCT_SEQ（2026-06-11）

## CRM 查询

DB Link: `@LINK_CRM`（不是 @LINK_CC）

核心表：
| 表 | 说明 | 关联字段 |
|---|---|---|
| CRM.ORDER_ITEM | 订单主表 | ACCT_ID, SUBS_ID, SUBS_EVENT_ID, ACC_NBR |
| CRM.SUBS_EVENT | 事件类型 | SUBS_EVENT_ID, EVENT_NAME (New Connection / Modify VAS) |
| CRM.GOODS_ORDER | 商品/设备 | ORDER_ITEM_ID |

```sql
-- 查账号的订单
SELECT o.ORDER_NBR, e.EVENT_NAME, o.STATE_DATE, o.ORDER_STATE
FROM CRM.ORDER_ITEM@LINK_CRM o
LEFT JOIN CRM.SUBS_EVENT@LINK_CRM e ON o.SUBS_EVENT_ID = e.SUBS_EVENT_ID
WHERE o.ACCT_ID = 1250396101
```

## 分摊 (Proration)

场景: 后付费月中开户。如 5.15 开户，billing_cycle BC01 (5.1-5.30)。

| 阶段 | 数据流 |
|---|---|
| 开户时 | EVENT_RECURRING 写入按天分摊的 MRC (5.15-5.30) |
| 出账日(5.30晚) | 采集订户下期全额 MRC (6.1-6.30) |
| 合账 (LedgerCollect) | 两条 EVENT_RECURRING → ACCT_ITEM_BILLING，自动合并 |
| Step_26 | INV_SUBS_DETAIL.PRORATE_CHARGE 标记分摊行 |

关键概念:
- billing_cycle / billing_cycle_type: 账期定义，控制周期边界
- EVENT_RECURRING: 循环费用事件表 (含MRC、Addon等)
- 合账: LedgerCollect 阶段将多条费用记录合并为账单科目

## 出账流程 (13步)

来源: YTLC出账手册

| 步 | 操作 | 输入 | 输出 |
|---|---|---|---|
| 1 | State → B | billing_cycle | 锁账期 |
| 2 | event_recurring 合账 | EVENT_RECURRING | ACCT_ITEM_BILLING (循环费) |
| 3 | event_usage 合账 | EVENT_USAGE | ACCT_ITEM_BILLING (用量) |
| 4 | event_usage_c 合账 | EVENT_USAGE_C | ACCT_ITEM_BILLING (子用量) |
| 5 | BillDiscount 算税 | — | ACCT_ITEM_BILLING (折扣) |
| 6 | Event_Charge 合账 | EVENT_CHARGE | ACCT_ITEM_BILLING (一次性) |
| 7 | DEPOSIT_CHARGE 合账 | DEPOSIT_CHARGE | ACCT_ITEM_BILLING (押金) |
| 8 | LedgerRound | — | 舍入调整 |
| 9 | BillGen | ACCT_ITEM_BILLING | CC.BILL + 账单号 |
| 10 | YTL_BILL_RUN SPs | ACCT_ITEM_BILLING | INV.* 视图 |
| 11 | LedgerReport | — | BILL_DATA |
| 12 | LedgerExport | — | 导出 |
| 13 | Bill Assurance | — | 校验报告 |

> 合账 = 将 EVENT_* 表的多条费用记录按账期合并为账单科目，写入 RB.ACCT_ITEM_BILLING。
> BillGen 不是合账——合账在第2-7步完成，BillGen 是生成 CC.BILL 和账单号。

## 出账前操作

| 操作 | 说明 |
|---|---|
| 数据检查 | pkg_data_check.Run_All_Data_Check(BillingCycleID) |
| 采集下期租费 | 采集订户下一账期的 MRC，写入 EVENT_RECURRING |
| 租费预收 | 对于 prorate 合约 (EXP_HAS_PRORATE_FEE=Y)，开户/Plan Conversion 时多发一条 2013=1 的租费补收消息 |
