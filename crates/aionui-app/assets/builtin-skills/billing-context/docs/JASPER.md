# JasperReports 发票模板管理流程

## 目录结构

```
jasper-build/
  templates/             ← .jrxml 模板源文件
    regular/              ← Regular Invoice (type 7)
    sharedplan/           ← 子报表/共享模板
    salesinvoice/         ← Sales Invoice (type 5)
    einvoice/             ← E-Invoice
  output/                 ← 编译产物 .jasper
  history/                ← 快照 (带时间戳)
  lib/                    ← JasperReports JAR 依赖
  build.sh                ← 编译/快照/部署脚本
  deploy.conf             ← 模板目录 → 服务器路径映射
  CompileJrxml.java       ← .jrxml → .jasper 编译器
```

## 工作流

### 1. 编辑模板

```bash
# 编辑 .jrxml 文件
vim templates/regular/C_REGULAR_INVOICE_V1.regular.jrxml
vim templates/sharedplan/group.jrxml
```

### 2. 编译 + 快照

```bash
cd jasper-build
./build.sh build
# → 编译 templates/*/ → output/*/*.jasper
# → 快照存到 history/20260613_070400/
```

### 3. 对比变更

```bash
./build.sh diff
# → 对比当前 templates/ 和上次快照的差异
```

### 4. 预览

```bash
./build.sh preview output/regular/C_REGULAR_INVOICE_V1.regular.jasper test_data.xml
# → 生成 PDF 并打开
```

### 5. 部署到服务器

编译产物 (.jasper) 上传至目标服务器：

```
output/regular/     → 192.168.123.1:/web/cvbs/r13/report/billing/regular/
output/sharedplan/  → 192.168.123.1:/web/cvbs/r13/report/billing/sharedplan/
output/salesinvoice/→ 192.168.123.1:/web/cvbs/r13/report/billing/salesinvoice/
output/einvoice/    → 192.168.123.1:/web/cvbs/r13/report/billing/eInvoice/
```

配置见 `jasper-build/deploy.conf`。

## BILL_FLOW 模板 → 数据源链路

```
BILL_SRC (60+ SQL)
  → BILL_FIELD (字段映射)
    → .jrxml ($F{field_name} 绑定)
      → 编译 → .jasper
        → JasperReports 引擎 + BILL_DATA XML → PDF
```

## 常见模板修改场景

| 场景 | 文件 | 改动 |
|---|---|---|
| 加折扣列显示 VOUCHER_CODE | group.jrxml (Add-On table) | 加 66px 列, $F{VOUCHER_CODE} |
| 改支付标签 + 宽度 | C_REGULAR_INVOICE_V1.regular.jrxml | staticText + 131→182px |
| 拆分行显示 IMEI | group.jrxml (MODEL_NAME) | CHR(10) 换行 |
| 金额居中/透明底色 | group.jrxml (amount fields) | isBlankWhenNull, center, opaque=false |
| 改金额格式 (4位→2位小数) | group.jrxml | FM999999990.00 |
| 子报表路径修正 | 各子报表 jrxml | SUBREPORT_DIR defaultValueExpression |
| VOUCHER_CODE 无值回退 '0.0000' | group.jrxml | ternary: $F{VOUCHER_CODE}==null ? "0.0000" : ... |

## DOC 模板流程

```
DOC_FORMAT_TEMPLATE_APPLY_RULE (INVOICE_TYPE → DOC_FORMAT_ID)
  → DOC_FORMAT_VER (版本, STATE=A 生效)
    → DOC_FORMAT_DATASOURCE (→ DOC_EXT_SRC)
    → DOC_FORMAT_ITEM (→ DOC_ITEM 字段标签)
      → DOC_EXT_SRC (SRC_SCRIPT, 带 :E_INVOICE_NBR 参数)
```

⚠️ DOC_FORMAT_DATASOURCE 才是数据源关联表（不是 DOC_ITEM）
