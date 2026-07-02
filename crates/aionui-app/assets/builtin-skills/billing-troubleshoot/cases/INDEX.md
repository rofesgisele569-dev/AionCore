# YTLC 案例索引

| JIRA | SUBS_ID | 标题 | 状态 | 根因 | 排查日 |
|---|---|---|---|---|---|
| [ZTPD-2332](https://ytlcomms.jira.com/browse/ZTPD-2332) | 61892269 | BS停用+切套餐 dealMode=0 取旧月租致多收多退 | 🔴 已确诊 | dealMode=0 取了旧 88 套餐月租算 5 天 prorate → ±14.19 (应 ±5.65) | 2026-06-18 |
| [ZTPD-2373](https://ytlcomms.jira.com/browse/ZTPD-2373) | 67652714 | 多次挂起/复机 5/23 22:13 复机 ASYN_CALL 漏发 | 🔴 已确诊 | ORDER 66334233 (EVENT 29 复机) 没触发 ASYN_CALL → 缺 ~31.81 补收 (月租 58) | 2026-06-18 |

## 使用

- 每个 case 一个文件：`case-ZTPD-XXXX.md`
- 案例文件路径：`~/Desktop/billing-kb/cases/`
- 添加新案例：复制模板 → 填字段 → 在本索引表加一行
- 模板字段：JIRA / SUBS_ID / 标题 / 状态 / 根因 / 排查日

## 状态取值

- 🔴 已确诊 (根因锁定，待修复)
- 🟡 排查中 (方向锁定，未定根因)
- 🟢 已修复 (数据已修 + 验证)
- ⚫ 暂缓 (等用户/上游)
