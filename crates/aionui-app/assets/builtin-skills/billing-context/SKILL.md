---
name: billing-context
description: SM81 billing domain knowledge — invoice types, billing flows, Jasper templates, and terminology. Use when user asks about billing concepts, invoice types, billing cycle processes, or Jasper template deployment.
---

# 账务领域知识

SM81 出账系统核心知识。按需查阅以下子模块：

## 发票类型（9种）

详细：[docs/CONTEXT.md](docs/CONTEXT.md)

| type | 名称 | 体系 | 说明 |
|------|------|------|------|
| 1 | Proforma Invoice | DOC | 形式发票 |
| 2 | Monthly Statement | DOC | 月度对账单 |
| 3 | Annual Statement | DOC | 年度对账单 |
| 4 | Prepaid E-Invoice | DOC/独立 | 预付电子发票 |
| 5 | Postpaid Sales-Invoice | DOC | 后付费发票 |
| 6 | Hotbill Sales-Invoice | DOC | 热账单 |
| 7 | Regular Invoice | BILL_FLOW | 常规发票 |
| 8 | Postpaid Reverse Sales-Invoice | DOC(cancel) | 后付费红冲 |
| 9 | Prepaid Reverse E-Invoice | DOC(cancel) | 预付红冲 |

## 出账流水线
EVENT_CHARGE/EVENT_RECURRING → LedgerCollect → ACCT_ITEM_BILLING → 按类型分发

## MRC 月租取值链
OFFER_ATTR[292] → PRICE_PLAN覆盖价 → proration(按天折算)

## Jasper 模板
详见 [docs/JASPER.md](docs/JASPER.md)
