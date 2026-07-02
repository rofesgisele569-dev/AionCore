# Port-In Rebate 排查总结

**日期**: 2026-06  |  **目标号码**: 01133222101  |  **SUBS_ID**: 1460011673

---

## 一、排查背景

客户要求验证号码 01133222101（Port-In from CELCOM）的 rebate 数据是否正确。

---

## 二、发现的问题

### 问题1：PAP Refund 58×1 ✅ 正确

已触发的 rebate（OFFER_REBATE_ID=70005）：
- REBATE_NAME: Plan Advance Payment Refund
- VALUE: 58 RM × 1 次
- ACCT_ITEM_TYPE_ID: 19 (PAP Refund)
- EVENT_CHARGE STATE: 3（合账完成）
- 账单 Cycle 2899 正确出账 −58

### 问题2：MNP Promotion 12×6 ❌ 应返未返

未触发的 rebate（OFFER_REBATE_ID=1115153）：
- REBATE_NAME: MNP Promotion - 6mths rebates
- VALUE: 20 RM × 6 个月 = 120 RM
- ACCT_ITEM_TYPE_ID: 803 (Promotion Waiver)
- **状态**: 未写入 SUBS_AGREEMENT_INST_FEE，未出账

---

## 三、根因

### 直接原因：RE_ID 选择错误

```
同样的 Port-In 客户（PORT_IN_TYPE=1, NP_ORDER TYPE=3 Port In, OFFER=27408 Infinite Basic）：

  正确路径: RE_ID=10209 (Port-In Add Agreement) → 触发 70007 + 1115153 (MNP) ✅
  错误路径: RE_ID=13203 (New Agreement)         → 只触发 70005           ❌
```

01133222101 走了 **13203**，不是 **10209**。决定 RE_ID 的是 **CRM 创建 NP_ORDER 时的逻辑**，跟时间差、临时号码、订单完成时间等无关（有相差 105 天仍正确走了 10209 的案例）。

### 排除的因素

| 可能原因 | 验证结果 |
|---|---|
| NP_ORDER 与 ORDER 时间差 | ❌ 无关（差105天也有走对的） |
| TEMP_NUMBER（临时号码） | ❌ 无关（TEMP=None 也有走对的） |
| DONOR_OPERATOR（来源运营商） | ❌ 无关（各运营商都有对错） |
| 计费侧规则配置 | ✅ 配置正确（10209 走 MNP 正常） |

---

## 四、影响范围

| 状态 | 数量 | 说明 |
|---|---|---|
| OFFER=27408, RE_ID=13203 总计 | 205 | 含普通 New Connection |
| 其中有关联 NP_ORDER 的 | **35** | **真正 Port-In 受影响** |
| NP_STATE=E（已完成） | **22** | **已完成 Port-In，MNP 缺失** |
| NP_STATE=J（已取消） | 12 | 已取消 |
| NP_STATE=A（创建中） | 1 | 待处理 |

**22 个已完成客户 × 72 RM = 约 1,584 RM 应返未返。**

详见 `cases/affected-portin-mnp-missing.md`。

---

## 五、排查链路

```
ACC_NBR '01133222101'
  → CC.SUBS → SUBS_ID=1460011673, ACCT_ID=1252065901
  → CC.PROD → OFFER_ID=1310, SUBS_PLAN_ID=12003
  → CRM.ORDER_ITEM → SUBS_EVENT_ID=1, PORT_IN_TYPE=1 ✅
  → CC.SUBS_AGREEMENT_INST_FEE → OFFER_REBATE_ID=70005（PAP Refund）
                                   ❌ 无 1115153（MNP Promotion）
  → CC.OFFER_REBATE（70005）= Plan Advance Payment Refund, 58×1
  → CC.OFFER_REBATE（1115153）= MNP Promotion - 6mths rebates, 20×6
  → CC.OFFER_REBATE_TYPE（3）= PLAN_ADVANCE_PAYMENT_REFUND
  → CC.RE_CC_INST → RE_ID=13203（New Agreement）❌ 应为 10209
  → CRM.NP_ORDER → STATE=E, TYPE=3(Port In), PORT_IN_TYPE=1
```

---

## 六、规则梳理（业务方确认的 Port-In 逻辑）

### 有临时号码（PORT_IN_TYPE=0）
- 607 (Port-In Add Agreement) → `IS_RESERVE_NEW_CONNECTION=Y` 返还
- 607 → `IS_RESERVE_NEW_CONNECTION=NULL/N`（MNP Waiver）**不给**
- 606 (Port-In Change MSISDN) 换号时 → 给 MNP Waiver
- 606 **只能配 MNP Waiver**，不能配其他返还

### 无临时号码（PORT_IN_TYPE=1）
- 607 上返还全部是 R 状态
- a: PortIn 通过 → R → 1（激活）
- b: cancelMNP Only → `IS_RESERVE_NEW_CONNECTION=Y` 保留为 1，NULL/N 改为 7

---

## 七、结论

**不是计费的 bug。** OFFER 27408 的 rebate 配置、RE_ID 对应的触发条件、计费算费逻辑全部正确。

问题在 **CRM 创建 NP_ORDER 时选错了 RE_ID**——22 个已完成的 Port-In 客户走了 13203 (New Agreement) 而不是 10209 (Port-In Add Agreement)，导致 MNP 12×6 未触发。需要 CRM 侧排查为什么同一条配置链路有时选 13203、有时选 10209。
