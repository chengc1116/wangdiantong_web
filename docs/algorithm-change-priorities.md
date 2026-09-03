# 旺店通库存算法重点修改清单

> 日期：2026-09-02  
> 仅列改造重点，不包含 WorkBuddy，本次不修改算法代码。

## 1. 销量预测（优先级：最高）

**当前：**

```text
预测日销量 = 近7日日均 × 40% + 近30日日均 × 60%
```

**重点修改：**

- 缺货日期不能按零销量处理，需要修正被低估的需求。
- 稳定款、增长款、低频款和新品采用不同预测规则。
- 使用历史数据回测预测误差。

**代码位置：**

- `src/wangdian_inventory/db.py`
  - `_warehouse_planning_rows()`
  - `replenishment_analysis()`

## 2. 采购数量（优先级：最高）

**当前：**采购目标量不扣减可用库存、采购在途和调拨量。

**建议增加净需求算法：**

```text
目标库存 = 交期需求 + 安全库存 + 审核周期需求
净采购需求 = 目标库存 - 可用库存 - 有效在途 - 已确认调拨
```

先同时展示“原采购量”和“净需求采购量”，暂时不要直接替换现有结果。

**代码位置：**

- `src/wangdian_inventory/db.py`
  - `purchase_plan()`
  - `_warehouse_planning_rows()`
  - `_target_week_multiplier()`
  - `_trend_purchase_multiplier()`
  - `_round_purchase_qty_to_50()`

## 3. 安全库存和交付周期（优先级：高）

**重点修改：**

- 安全库存加入销量波动，不再只依赖固定周销量倍数。
- 交付周期加入生产、物流和供应商延期情况。
- 爆款、普通款、测款、低销量款使用不同安全库存。

```text
补货点 = 交期需求 + 安全库存
```

**代码位置：**

- `src/wangdian_inventory/db.py`
  - `_is_lead_time_shortage()`
  - `_warehouse_planning_rows()`

## 4. 积压、清仓和资金占用（优先级：高）

**重点修改：**

不能只看库存件数和覆盖天数，还要加入：

- 库存金额
- 近30日和近90日销量
- 库龄
- 销量趋势
- 采购在途

优先处理“金额高、销量低、库龄长”的 SKU。

```text
积压金额 = 超出合理库存的数量 × 单位成本
长库龄资金占用 = 长库龄库存数量 × 单位成本
```

**代码位置：**

- `src/wangdian_inventory/db.py`
  - `replenishment_analysis()`
  - `clearance_summary()`
- `src/wangdian_inventory/report_export.py`

## 5. 仓间调拨（优先级：中）

**重点修改：**

调拨决策加入：

- 来源仓调拨后的库存安全性
- 目标仓预计缺货日期
- 运输时间和成本
- 调拨与直接采购的比较

```text
只有来源仓调拨后仍安全，且目标仓能在缺货前收到，才建议调拨。
```

**代码位置：**

- `src/wangdian_inventory/db.py`
  - `_warehouse_planning_rows()` 中的调拨逻辑
  - `transfer_plan()`

## 建议实施顺序

1. 增加“原采购量”和“净需求采购量”的对比。
2. 增加缺货修正和预测回测。
3. 增加动态安全库存。
4. 增加库存金额、周转和库龄分析。
5. 最后优化仓间调拨。

## 第一阶段涉及文件

```text
src/wangdian_inventory/db.py
src/wangdian_inventory/report_export.py
tests/test_purchase_rules.py
tests/test_inventory_app.py
docs/purchase-planning-rules.md
```

暂时不需要修改 `src/wangdian/client.py`，因为它主要负责从旺店通取数。

## 改造原则

- 不删除旧算法，新旧算法先并行对比。
- 每个采购结果必须可以解释计算依据。
- 修改规则后必须补充自动化测试。
- 正式替换前，使用历史数据回测缺货率、库存金额和采购量变化。
