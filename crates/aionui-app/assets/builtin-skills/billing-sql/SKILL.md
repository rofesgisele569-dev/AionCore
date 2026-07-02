---
name: billing-sql
description: SM81 billing SQL queries reference — charge details, invoice export, sales invoice source. Use when user needs to query billing data or understand billing table structures.
---

# 账务 SQL 查询

常见数据查询 SQL。详见 [doc-sql/](doc-sql/) 目录。

| SQL 文件 | 用途 |
|----------|------|
| 10265-charge-details.sql | 出账明细查询 |
| export_sales_invoice_src.sql | 销售发票导出 |
| sale_invoice_charge_details_info.sql | 发票出账明细 |
| sales_invoice_src.sql | 销售发票源数据 |

## 核心表
- CC.SUBS — 用户
- CC.ACCT — 账户
- CC.BILLING_CYCLE — 账期
- RB.EVENT_RECURRING — 月租话单
