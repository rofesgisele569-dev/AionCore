-- ============================================================
-- 导出 SALE_INVOICE 数据源脚本（生产环境用）
-- 用法: sqlplus cc/password@db @export_sales_invoice_src.sql
-- ============================================================
SET PAGESIZE 0
SET LONG 999999
SET LINESIZE 500
SET TRIMSPOOL ON
SET FEEDBACK OFF
SET VERIFY OFF

SPOOL sales_invoice_datasources.lst

-- 1. 列出所有 SALE_INVOICE 数据源
PROMPT ===== SALE_INVOICE 数据源列表 =====
SELECT DOC_EXT_SRC_ID || '  ' || SRC_NAME AS SRC_LIST
FROM CC.DOC_EXT_SRC 
WHERE SRC_NAME LIKE 'SALE_INVOICE%' 
ORDER BY DOC_EXT_SRC_ID;

PROMPT

-- 2. 逐个导出 SQL
SELECT '===== ' || DOC_EXT_SRC_ID || ' ' || SRC_NAME || ' ====='
FROM CC.DOC_EXT_SRC 
WHERE SRC_NAME LIKE 'SALE_INVOICE%' 
ORDER BY DOC_EXT_SRC_ID;

SELECT SRC_SCRIPT || CHR(10) || CHR(10)
FROM CC.DOC_EXT_SRC 
WHERE SRC_NAME LIKE 'SALE_INVOICE%' 
ORDER BY DOC_EXT_SRC_ID;

SPOOL OFF

PROMPT
PROMPT Done. 输出文件: sales_invoice_datasources.lst
EXIT;
