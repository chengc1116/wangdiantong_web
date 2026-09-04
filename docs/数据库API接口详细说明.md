# 旺店通 SQLite 数据 API 接口详细说明

> **文档版本：1.0.0**  
> **更新日期：2026-09-04**  
> **适用对象：** 业务人员、数据分析人员、前端/后端二次开发人员。  
> **在线调试入口：** 服务启动后访问 `https://<API域名>/docs`。本文件用于解释每个接口的业务作用、请求参数、传参规则及调用示例。

---

## 1. 使用前必读

### 1.1 服务地址与访问规则

以下用 `https://<API域名>` 代表正式公网地址；本机调试通常为：

```text
http://127.0.0.1:8000
```

例如通用查询接口的完整地址为：

```text
https://<API域名>/api/v1/query
```

- 服务为**只读 API**：只能查询数据，不能新增、修改或删除数据。
- 当前按既定要求**不需要登录/Token**。任何能访问到 API 地址的人都可以读到公开的数据，调用方应自行确认数据公开范围。
- 请求和响应均使用 UTF-8 编码的 JSON；`POST` 请求须带请求头：`Content-Type: application/json`。
- API 不允许提交 SQL 语句。所有表、字段、筛选条件、聚合方式都受接口白名单限制。
- 原库的 `raw_json` 字段不会对外提供；该字段体积大、结构不稳定，且可能含上游不适合公开的字段。

### 1.2 日期格式、时区与默认时间范围

| 项目 | 规则 |
|---|---|
| 日期参数 | 使用 `YYYY-MM-DD`，例如 `2026-09-04`。 |
| 日期区间 | `start`、`end` 均为**包含当天**的闭区间。 |
| 默认范围 | 未传 `start` / `end` 时，以 **API 服务器当天**为 `end`，向前取 30 个自然日（含当天）为 `start`。例如服务器日期是 `2026-09-04`，默认范围是 `2026-08-06` 至 `2026-09-04`。 |
| 时区 | 日期默认按部署服务器的系统日期解释；生产环境建议服务器设置为中国标准时间（Asia/Shanghai）。 |

> 说明：通用接口 `POST /api/v1/query` 不会自动添加日期条件。查询历史大表（如销售、出入库、退货）时，应主动使用日期字段筛选，避免一次获取大量历史记录。

### 1.3 分页规则

有分页的接口统一遵循下列规则：

| 参数 | 类型 | 默认值 | 范围 | 含义 |
|---|---:|---:|---:|---|
| `page` | integer | `1` | 1 ～ 100000 | 页码，从 1 开始。 |
| `page_size` | integer | `100` | 1 ～ 1000 | 每页返回记录数。一次最多 1000 条。 |

计算方式：

```text
offset = (page - 1) × page_size
```

如果接口响应中有 `total` 或 `pagination.total`，可按以下方式计算总页数：

```text
总页数 = ceil(total / page_size)
```

### 1.4 通用错误返回

发生错误时，服务会返回 HTTP 非 200 状态码和 JSON 错误体：

```json
{
  "detail": "unknown dataset: abc"
}
```

| HTTP 状态码 | 含义 | 常见原因与处理方式 |
|---:|---|---|
| `200` | 调用成功 | 正常处理响应数据。 |
| `400` | 业务参数不合法 | 数据集、字段、筛选符、聚合字段不允许，或参数组合不符合规则。检查 `detail`。 |
| `404` | 资源不存在 | 数据集名称错误，或查询的 SKU 不存在。 |
| `422` | 请求格式/类型校验失败 | `POST` JSON 格式错误、必填字段缺失，或 `page_size` 不是合法整数等。 |
| `503` | 数据库暂不可读 | 同步任务可能正在切换数据库文件，或 API 进程没有读取 SQLite 文件的权限。稍后重试并检查服务日志。 |

---

## 2. 接口总览

| 分类 | 方法 | 路径 | 用途 | 推荐对象 |
|---|---|---|---|---|
| 系统 | GET | `/api/v1/health` | 检查 API 与数据库是否可用 | 运维、监控 |
| 系统 | GET | `/api/v1/status` | 查看服务环境和最近一次同步记录 | 业务、运维 |
| 元数据 | GET | `/api/v1/datasets` | 获取可查询数据集、字段清单、日期字段 | 所有二开程序，**首次调用建议先查** |
| 元数据 | GET | `/api/v1/warehouses` | 获取仓库列表 | 前端下拉、筛选条件 |
| 通用查询 | POST | `/api/v1/query` | 按字段、条件、粒度、指标查询数据 | **推荐的主接口** |
| 通用查询 | GET | `/api/v1/table/{dataset}` | 简单明细查询，适合浏览器/curl | 临时查询、快速验证 |
| 业务查询 | GET | `/api/v1/inventory` | 库存经营汇总 | 现有网页兼容、业务报表 |
| 业务查询 | GET | `/api/v1/sales` | 按仓库 + SKU 汇总销量 | 现有网页兼容、业务报表 |
| 业务查询 | GET | `/api/v1/shop-sales` | 按店铺 + SKU 汇总销量 | 现有网页兼容、业务报表 |
| 业务查询 | GET | `/api/v1/inbound` | 入库分析 | 现有网页兼容、业务报表 |
| 业务查询 | GET | `/api/v1/purchase-plan` | 采购建议 | 现有网页兼容、业务报表 |
| 业务查询 | GET | `/api/v1/transfer-plan` | 调拨建议 | 现有网页兼容、业务报表 |
| 业务查询 | GET | `/api/v1/skus/{sku_no}` | 单个 SKU 的商品、库存、日趋势与流水 | SKU 详情页、业务分析 |

> 对新开发的程序，优先使用 **`POST /api/v1/query`**。后面的“业务查询”接口保留了当前网页的统计口径和复杂计算结果，适合直接显示原有业务页面，但其字段和计算口径会随网页功能迭代。

---

## 3. 元数据与系统接口

### 3.1 健康检查：`GET /api/v1/health`

**用途：** 验证 API 进程正在运行，并且能以只读方式打开 SQLite 数据库。适合负载均衡、监控探针或部署后的快速检查。

**请求参数：** 无。

```bash
curl 'https://<API域名>/api/v1/health'
```

**成功响应示例：**

```json
{
  "status": "ok",
  "database": "reachable",
  "read_only": true
}
```

| 返回字段 | 类型 | 说明 |
|---|---|---|
| `status` | string | 成功时为 `ok`。 |
| `database` | string | 成功时为 `reachable`，表示数据库可连接。 |
| `read_only` | boolean | 恒为 `true`，表示本服务不会写入数据库。 |

---

### 3.2 服务状态：`GET /api/v1/status`

**用途：** 查询 API 所在环境、当前使用的数据库文件名及最近一条同步执行记录。数据库的服务器绝对路径不会返回。

**请求参数：** 无。

```bash
curl 'https://<API域名>/api/v1/status'
```

**响应示例：**

```json
{
  "status": "ok",
  "read_only": true,
  "database": "inventory_production.db",
  "environment": "production",
  "last_sync": {
    "id": 123,
    "sync_date": "2026-09-04",
    "status": "success",
    "movement_count": 100,
    "inventory_count": 200,
    "sales_count": 300,
    "return_count": 20,
    "cancellation_count": 0,
    "started_at": "2026-09-04T02:00:00",
    "finished_at": "2026-09-04T02:10:00",
    "error_message": null
  }
}
```

| 返回字段 | 类型 | 说明 |
|---|---|---|
| `status` | string | 服务状态，成功时为 `ok`。 |
| `read_only` | boolean | 恒为 `true`。 |
| `database` | string | 正在使用的 SQLite 文件名，不包含服务器目录。 |
| `environment` | string | 服务环境，例如 `production`、`test`。 |
| `last_sync` | object / `null` | `sync_runs` 表中最近一次同步记录；尚无记录时为 `null`。 |

`last_sync` 中的字段含义：

| 字段 | 说明 |
|---|---|
| `sync_date` | 这次同步归属的业务日期。 |
| `status` | 同步状态，由现有同步任务写入。 |
| `movement_count` / `inventory_count` / `sales_count` / `return_count` | 本次同步的相应数据量。 |
| `cancellation_count` | 本次处理的取消记录数量。 |
| `started_at` / `finished_at` | 同步开始/结束时间。 |
| `error_message` | 同步失败时的错误信息；正常时通常为 `null` 或空。 |

---

### 3.3 数据集和字段目录：`GET /api/v1/datasets`

**用途：** 返回当前运行中数据库的真实公开字段。由于数据库字段可能随同步版本变化，二开程序应在接入或升级时以本接口为准，不要仅依赖本文档中的字段清单。

**请求参数：** 无。

```bash
curl 'https://<API域名>/api/v1/datasets'
```

**响应结构：**

```json
{
  "items": [
    {
      "dataset": "sales_lines",
      "table": "sales_lines",
      "date_field": "sale_date",
      "fields": ["sale_key", "sale_date", "sku_no"]
    }
  ]
}
```

| 返回字段 | 类型 | 说明 |
|---|---|---|
| `items` | array | 所有公开数据集。 |
| `items[].dataset` | string | 调用通用查询时传给 `dataset` 的名称。 |
| `items[].table` | string | SQLite 中的实际表名，供理解数据来源使用；不能在 API 中直接写 SQL。 |
| `items[].date_field` | string / `null` | 推荐用于日期筛选的字段。没有固定日期字段时为 `null`。 |
| `items[].fields` | string array | 该数据集允许放在 `fields`、`filters.field`、`group_by`、`metrics.field` 中的字段。 |

---

### 3.4 仓库列表：`GET /api/v1/warehouses`

**用途：** 获取仓库主数据。业务接口中的 `warehouse` 参数应传 `warehouse_id`，建议先调用本接口获得可选值。

**请求参数：** 无。

```bash
curl 'https://<API域名>/api/v1/warehouses'
```

**响应示例：**

```json
{
  "total": 1,
  "items": [
    {
      "warehouse_id": "W-1",
      "warehouse_no": "001",
      "warehouse_name": "主仓",
      "warehouse_type": "",
      "is_disabled": 0,
      "role": "sales",
      "transfer_source_enabled": 1
    }
  ]
}
```

| 返回字段 | 类型 | 说明 |
|---|---|---|
| `total` | integer | 仓库总数。 |
| `items[].warehouse_id` | string | 仓库唯一标识；业务接口的 `warehouse` 参数、通用接口的 `warehouse_id` 条件都应使用它。 |
| `items[].warehouse_no` | string | 仓库编码。 |
| `items[].warehouse_name` | string | 仓库名称。 |
| `items[].warehouse_type` | string | 仓库类型。 |
| `items[].is_disabled` | integer / boolean | 是否停用。具体存储值以数据库为准。 |
| `items[].role` | string | 仓库角色，例如 `sales`。 |
| `items[].transfer_source_enabled` | integer / boolean | 是否允许作为调拨来源仓。 |

---

## 4. 主接口：通用查询 `POST /api/v1/query`

### 4.1 适用场景

这是给数据二开和外部程序使用的主接口。它支持：

1. 查询原始明细，例如某一日期范围的销售行；
2. 按 SKU、仓库、店铺、日期等任意公开字段进行筛选；
3. 按一个或多个字段分组，决定统计粒度；
4. 对数量、金额等字段进行 `sum`、`avg`、`min`、`max`、`count` 聚合；
5. 对结果排序和分页。

**请求方式：** `POST`  
**请求地址：** `/api/v1/query`  
**请求头：** `Content-Type: application/json`

### 4.2 请求体完整结构

```json
{
  "dataset": "sales_lines",
  "fields": ["sale_date", "sku_no", "quantity"],
  "filters": [
    {"field": "sale_date", "op": "gte", "value": "2026-09-01"}
  ],
  "group_by": [],
  "metrics": [],
  "order_by": [
    {"field": "sale_date", "direction": "desc"}
  ],
  "page": 1,
  "page_size": 100
}
```

### 4.3 顶层参数说明

| 参数 | 是否必填 | 类型 | 默认值 | 可用值/限制 | 说明 |
|---|---|---|---|---|---|
| `dataset` | 是 | string | 无 | 见 `/api/v1/datasets` | 要查询的数据集名称，例如 `sales_lines`。不是 SQLite 表名随意输入位置，仅允许公开数据集。 |
| `fields` | 否 | string array | `[]` | 必须是该 `dataset` 的公开字段 | 要返回的**明细字段**。普通明细查询不传时，返回该数据集全部公开字段。分组查询中，`fields` 只能是 `group_by` 的子集，通常可不传。 |
| `filters` | 否 | object array | `[]` | 每项见 4.4 | 筛选条件。多个条件之间为 **AND（且）** 关系。 |
| `group_by` | 否 | string array | `[]` | 必须是公开字段 | 分组字段，决定汇总统计的粒度。例：`["warehouse_name", "shop_name"]` 表示“按仓库 + 店铺”统计。 |
| `metrics` | 否 | object array | `[]` | 每项见 4.5 | 聚合指标。存在 `metrics` 或 `group_by` 时即为统计查询。 |
| `order_by` | 否 | object array | `[]` | 每项见 4.6 | 排序规则。排序字段必须是最终响应中出现的字段或指标别名。 |
| `page` | 否 | integer | `1` | 1 ～ 100000 | 页码，从 1 开始。 |
| `page_size` | 否 | integer | `100` | 1 ～ 1000 | 每页返回条数。 |

### 4.4 `filters`：筛选条件传参

`filters` 是数组，每一项是一个筛选对象：

```json
{
  "field": "warehouse_id",
  "op": "eq",
  "value": "W-1"
}
```

| 子参数 | 是否必填 | 类型 | 默认值 | 说明 |
|---|---|---|---|---|
| `field` | 是 | string | 无 | 用于筛选的公开字段名。字段必须属于当前 `dataset`。 |
| `op` | 否 | string | `eq` | 筛选运算符，见下表；大小写不敏感，但建议统一使用小写。 |
| `value` | 视 `op` 而定 | 任意 JSON 值 | `null` | 筛选值。`in` 必须为非空数组；`is_null` 不能传实际筛选值。 |

支持的运算符：

| `op` | 含义 | `value` 应传什么 | JSON 示例 | 说明 |
|---|---|---|---|---|
| `eq` | 等于 | 字符串、数字、布尔等单值 | `{"field":"sku_no","op":"eq","value":"SKU-1"}` | 最常用。 |
| `ne` | 不等于 | 单值 | `{"field":"status","op":"ne","value":0}` | 空值比较请使用 `is_null`，不要用 `eq: null`。 |
| `gt` | 大于 | 数字、可比较的日期字符串等 | `{"field":"quantity","op":"gt","value":0}` | 数值字段建议传 JSON 数字，而非字符串。 |
| `gte` | 大于等于 | 数字、日期字符串等 | `{"field":"sale_date","op":"gte","value":"2026-09-01"}` | 常用于起始日期。 |
| `lt` | 小于 | 数字、日期字符串等 | `{"field":"available_num","op":"lt","value":10}` |  |
| `lte` | 小于等于 | 数字、日期字符串等 | `{"field":"sale_date","op":"lte","value":"2026-09-30"}` | 常用于结束日期。 |
| `contains` | 文本包含 | 字符串 | `{"field":"goods_name","op":"contains","value":"保温杯"}` | 相当于 SQL 的包含匹配；大表上可能较慢。 |
| `in` | 在给定集合中 | **非空数组** | `{"field":"warehouse_id","op":"in","value":["W-1","W-2"]}` | 适合多个 SKU、多个仓库、多种状态。 |
| `is_null` | 为空（SQL NULL） | `null`、空字符串、`true` 或 `false` 均可 | `{"field":"supplier_id","op":"is_null","value":null}` | 实际查询只判断字段是否为 SQL `NULL`。推荐传 `null`，语义最清楚。 |

**筛选组合示例：** 查询 2026 年 9 月、主仓、SKU 为两个指定值之一的销售明细：

```json
"filters": [
  {"field": "sale_date", "op": "gte", "value": "2026-09-01"},
  {"field": "sale_date", "op": "lte", "value": "2026-09-30"},
  {"field": "warehouse_id", "op": "eq", "value": "W-1"},
  {"field": "sku_no", "op": "in", "value": ["SKU-1", "SKU-2"]}
]
```

等价逻辑：

```text
sale_date >= '2026-09-01'
AND sale_date <= '2026-09-30'
AND warehouse_id = 'W-1'
AND sku_no IN ('SKU-1', 'SKU-2')
```

**当前限制：** 不支持在一次请求中构造 OR（或）条件或嵌套逻辑，例如“不属于 A 或 B”的复杂组合。需要 OR 时，请拆成多次请求后由调用方合并结果。

### 4.5 `group_by` 和 `metrics`：统计粒度与指标

#### A. `group_by`：决定“按什么维度统计”

`group_by` 是字段数组。数组中每增加一个字段，结果就增加一个统计维度。

| 需求 | `group_by` 示例 | 得到的粒度 |
|---|---|---|
| 全部销售合计 | `[]` | 整个筛选范围一行合计 |
| 按仓库 | `["warehouse_name"]` | 每个仓库一行 |
| 按 SKU | `["sku_no"]` | 每个 SKU 一行 |
| 按仓库 + SKU | `["warehouse_name", "sku_no"]` | 每个仓库内每个 SKU 一行 |
| 按日期 + 店铺 | `["sale_date", "shop_name"]` | 每日、每店铺一行 |

> 分组字段必须属于当前数据集。例如 `shop_name` 是 `sales_lines` 的字段，不能用于 `inventory_current`。

#### B. `metrics`：决定“统计什么数值”

每个指标对象格式：

```json
{
  "field": "quantity",
  "agg": "sum",
  "alias": "sales_qty"
}
```

| 子参数 | 是否必填 | 类型 | 默认值 | 说明 |
|---|---|---|---|---|
| `field` | 否 | string | `"*"` | 要聚合的字段。只有 `count` 时可使用 `"*"` 表示统计记录行数。其他聚合应传真实字段名。 |
| `agg` | 否 | string | `"count"` | 聚合函数：`count`、`sum`、`avg`、`min`、`max`。大小写不敏感，建议小写。 |
| `alias` | 否 | string | 自动生成 | 指标输出字段名。建议总是填写，便于排序和调用方解析；只允许字母、数字、下划线，且不能以数字开头。 |

聚合函数说明：

| `agg` | 作用 | 示例 |
|---|---|---|
| `count` | 计数。`field:"*"` 时统计记录条数；传具体字段时统计该字段非空值数量。 | `{"field":"*","agg":"count","alias":"line_count"}` |
| `sum` | 求和。适合数量、金额、成本等数值字段。 | `{"field":"quantity","agg":"sum","alias":"sales_qty"}` |
| `avg` | 平均值。 | `{"field":"paid_amount","agg":"avg","alias":"avg_paid_amount"}` |
| `min` | 最小值。 | `{"field":"sale_date","agg":"min","alias":"first_sale_date"}` |
| `max` | 最大值。 | `{"field":"sale_date","agg":"max","alias":"last_sale_date"}` |

**参数组合规则（必须遵守）：**

1. **纯明细查询：** 不传 `group_by`、不传 `metrics`；`fields` 可传可不传。
2. **按维度统计：** 传 `group_by` + `metrics`；`fields` 通常不传。若传 `fields`，其中每个字段都必须同时存在于 `group_by`。
3. **全局合计：** 仅传 `metrics`，且 `fields` 必须为空。结果通常只有一行。
4. 如果只传 `group_by`，不传 `metrics`，接口自动补充 `COUNT(*) AS count`，用于计算每组记录数。
5. `order_by.field` 只能写分组字段或指标的 `alias`（或未设置别名时接口生成的指标名）。

**示例 1：按仓库和店铺统计销售数量、成交金额、记录数：**

```json
{
  "dataset": "sales_lines",
  "filters": [
    {"field": "sale_date", "op": "gte", "value": "2026-09-01"},
    {"field": "sale_date", "op": "lte", "value": "2026-09-30"}
  ],
  "group_by": ["warehouse_name", "shop_name"],
  "metrics": [
    {"field": "quantity", "agg": "sum", "alias": "sales_qty"},
    {"field": "paid_amount", "agg": "sum", "alias": "paid_total"},
    {"field": "*", "agg": "count", "alias": "line_count"}
  ],
  "order_by": [
    {"field": "sales_qty", "direction": "desc"}
  ],
  "page": 1,
  "page_size": 100
}
```

**示例 2：查询全库当前库存合计（不分组）：**

```json
{
  "dataset": "inventory_current",
  "metrics": [
    {"field": "stock_num", "agg": "sum", "alias": "total_stock_num"},
    {"field": "available_num", "agg": "sum", "alias": "total_available_num"}
  ]
}
```

### 4.6 `order_by`：排序传参

`order_by` 是排序对象数组，可依次指定多个排序优先级：

```json
"order_by": [
  {"field": "sales_qty", "direction": "desc"},
  {"field": "warehouse_name", "direction": "asc"}
]
```

| 子参数 | 是否必填 | 类型 | 默认值 | 说明 |
|---|---|---|---|---|
| `field` | 是 | string | 无 | 必须是最终响应字段。例如明细查询中的 `sale_date`，或统计查询的 `sales_qty` 指标别名。 |
| `direction` | 否 | string | `desc` | `asc` 为升序，`desc` 为降序；大小写不敏感。 |

### 4.7 通用查询的响应结构

无论明细或分组统计，响应外层结构相同：

```json
{
  "dataset": "sales_lines",
  "table": "sales_lines",
  "fields": ["warehouse_name", "sales_qty"],
  "page": 1,
  "page_size": 100,
  "total": 2,
  "items": [
    {"warehouse_name": "主仓", "sales_qty": 100}
  ]
}
```

| 返回字段 | 类型 | 说明 |
|---|---|---|
| `dataset` | string | 本次实际查询的数据集。 |
| `table` | string | 对应 SQLite 表名。 |
| `fields` | string array | 当前结果每一行包含的字段名称及顺序。 |
| `page` | integer | 当前页码。 |
| `page_size` | integer | 当前每页数量。 |
| `total` | integer | 条件筛选后的总行数；分组查询时是**分组后的组数**，不是原始明细行数。 |
| `items` | object array | 当前页结果。字段值类型以 SQLite 实际数据为准，空值会以 JSON `null` 返回。 |

### 4.8 三种典型请求示例

#### 示例 A：查询销售明细

```bash
curl -X POST 'https://<API域名>/api/v1/query' \
  -H 'Content-Type: application/json' \
  -d '{
    "dataset": "sales_lines",
    "fields": ["sale_date", "sku_no", "warehouse_name", "shop_name", "quantity", "paid_amount"],
    "filters": [
      {"field": "sale_date", "op": "gte", "value": "2026-09-01"},
      {"field": "sale_date", "op": "lte", "value": "2026-09-30"},
      {"field": "warehouse_id", "op": "eq", "value": "W-1"}
    ],
    "order_by": [{"field": "sale_date", "direction": "desc"}],
    "page": 1,
    "page_size": 100
  }'
```

#### 示例 B：按 SKU 汇总当前库存

```json
{
  "dataset": "inventory_current",
  "group_by": ["sku_no"],
  "metrics": [
    {"field": "stock_num", "agg": "sum", "alias": "stock_qty"},
    {"field": "available_num", "agg": "sum", "alias": "available_qty"}
  ],
  "order_by": [
    {"field": "available_qty", "direction": "asc"}
  ],
  "page": 1,
  "page_size": 200
}
```

#### 示例 C：按日统计退货数量与退款额

```json
{
  "dataset": "return_lines",
  "filters": [
    {"field": "return_date", "op": "gte", "value": "2026-09-01"},
    {"field": "return_date", "op": "lte", "value": "2026-09-30"}
  ],
  "group_by": ["return_date"],
  "metrics": [
    {"field": "quantity", "agg": "sum", "alias": "return_qty"},
    {"field": "refund_amount", "agg": "sum", "alias": "refund_total"}
  ],
  "order_by": [
    {"field": "return_date", "direction": "asc"}
  ]
}
```

---

## 5. 简单 GET 查询：`GET /api/v1/table/{dataset}`

### 5.1 适用场景与限制

此接口把简单查询放在 URL 中，适合浏览器地址栏、Postman、curl 的临时验证。复杂的分组、聚合、多值 `in` 查询请使用 `POST /api/v1/query`。

**请求地址格式：**

```text
/api/v1/table/{dataset}?field=<字段>&field=<字段>&filter=<字段:操作符:值>&page=1&page_size=100
```

### 5.2 路径参数

| 参数位置 | 参数 | 是否必填 | 类型 | 说明 |
|---|---|---|---|---|
| Path | `dataset` | 是 | string | 数据集名称，例如 `products`、`sales_lines`。可用值见 `/api/v1/datasets`。 |

### 5.3 查询参数

| 参数 | 是否必填 | 类型 | 默认值 | 限制与说明 |
|---|---|---|---:|---|
| `page` | 否 | integer | `1` | 1 ～ 100000。 |
| `page_size` | 否 | integer | `100` | 1 ～ 1000。 |
| `field` | 否 | string，可重复 | 不传时返回全部公开字段 | 每传一次选择一个返回字段。例如 `field=sku_no&field=goods_name`。 |
| `filter` | 否 | string，可重复 | 无 | 格式固定为 `字段:操作符:值`。多个 `filter` 为 AND 关系。 |

### 5.4 `filter` 参数格式

格式：

```text
filter=<field>:<op>:<value>
```

示例：

```text
filter=warehouse_id:eq:W-1
filter=available_num:gte:10
filter=goods_name:contains:保温杯
```

实际 URL 示例：

```bash
curl -G 'https://<API域名>/api/v1/table/inventory_current' \
  --data-urlencode 'field=sku_no' \
  --data-urlencode 'field=warehouse_name' \
  --data-urlencode 'field=available_num' \
  --data-urlencode 'filter=warehouse_id:eq:W-1' \
  --data-urlencode 'filter=available_num:gte:10' \
  --data-urlencode 'page=1' \
  --data-urlencode 'page_size=50'
```

| 运算符 | GET 接口是否可用 | 示例 | 说明 |
|---|---|---|---|
| `eq` / `ne` / `gt` / `gte` / `lt` / `lte` | 是 | `filter=quantity:gt:0` | 值从 URL 传入，通常按字符串传给 SQLite；数值比较建议使用主 POST 接口传 JSON 数字。 |
| `contains` | 是 | `filter=goods_name:contains:保温杯` | URL 中中文、空格、`&` 等字符应进行 URL 编码。 |
| `is_null` | 是 | `filter=supplier_id:is_null:` | 第三个部分保留为空。 |
| `in` | **否** | — | `in` 需要数组，本 GET 接口不能可靠传递数组；请改用 `POST /api/v1/query`。 |

**响应结构：** 与 `POST /api/v1/query` 完全一致，参见 4.7。

---

## 6. 业务查询接口（兼容现有网页）

### 6.1 公共查询参数

除 SKU 详情接口外，下列六个业务查询接口均使用下列公共参数：

| 参数 | 是否必填 | 类型 | 默认值 | 说明 |
|---|---|---|---|---|
| `start` | 否 | string | 服务器当天向前 30 日的起始日 | 查询开始日期，格式 `YYYY-MM-DD`，包含当天。 |
| `end` | 否 | string | 服务器当天 | 查询结束日期，格式 `YYYY-MM-DD`，包含当天。 |
| `page` | 否 | integer | `1` | 页码，1 ～ 100000。 |
| `page_size` | 否 | integer | `100` | 每页数量，1 ～ 1000。 |
| `search` | 否 | string | 空字符串 | 商品搜索关键词。当前会匹配 SKU、货号、商品名、简称、规格、条码等业务字段。 |
| `warehouse` | 否 | string | 空字符串 | 仓库 ID，即 `/api/v1/warehouses` 返回的 `warehouse_id`，**不要传仓库名称**。空字符串表示不限制仓库。 |

> 日期参数在 URL 中示例：`?start=2026-09-01&end=2026-09-30`。如果参数中出现中文或特殊字符，请让 HTTP 客户端自动进行 URL 编码。

---

### 6.2 库存汇总：`GET /api/v1/inventory`

**用途：** 返回库存、销售、退货、出入库等组合后的 SKU 经营汇总数据，适合库存总览页面。

**专有参数：**

| 参数 | 是否必填 | 类型 | 默认值 | 可用值 | 说明 |
|---|---|---|---|---|---|
| `stock_status` | 否 | string | 空字符串 | `positive`、`zero`、`negative`、`unavailable` | 按库存状态过滤；为空表示全部。 |

`stock_status` 的含义：

| 值 | 过滤规则 |
|---|---|
| `positive` | 汇总库存数量大于 0。 |
| `zero` | 汇总库存数量等于 0。 |
| `negative` | 汇总库存数量小于 0。 |
| `unavailable` | 汇总可用库存数量小于等于 0。 |

**调用示例：**

```bash
curl -G 'https://<API域名>/api/v1/inventory' \
  --data-urlencode 'start=2026-09-01' \
  --data-urlencode 'end=2026-09-30' \
  --data-urlencode 'warehouse=W-1' \
  --data-urlencode 'stock_status=unavailable' \
  --data-urlencode 'search=保温杯' \
  --data-urlencode 'page=1' \
  --data-urlencode 'page_size=100'
```

**响应外层字段：**

| 字段 | 说明 |
|---|---|
| `summary` | 当前条件下的汇总统计。 |
| `items` | 当前页 SKU 汇总行。 |
| `range` | 实际生效的 `start`、`end`。 |
| `rolling_ranges` | 用于 7/15/30 日销量计算的滚动时间范围。 |
| `pagination` | `total`、`limit`、`offset` 分页信息。 |

---

### 6.3 仓库 SKU 销量：`GET /api/v1/sales`

**用途：** 按“仓库 + SKU”汇总销售、退货、净销量及销售金额。

**参数：** 仅使用 6.1 中的公共参数，无专有参数。

```bash
curl -G 'https://<API域名>/api/v1/sales' \
  --data-urlencode 'start=2026-09-01' \
  --data-urlencode 'end=2026-09-30' \
  --data-urlencode 'warehouse=W-1' \
  --data-urlencode 'search=SKU-1001' \
  --data-urlencode 'page=1' \
  --data-urlencode 'page_size=100'
```

**响应外层字段：**

| 字段 | 说明 |
|---|---|
| `summary` | 统计摘要，例如记录数、SKU 数、销量、退货量、销售金额等。 |
| `items` | 当前页“仓库 + SKU”汇总结果。 |
| `range` | 实际统计日期范围。 |
| `pagination` | `total`、`limit`、`offset`。 |

---

### 6.4 店铺 SKU 销量：`GET /api/v1/shop-sales`

**用途：** 按“店铺 + SKU”汇总销售、退货、净销量和销售金额。

**专有参数：**

| 参数 | 是否必填 | 类型 | 默认值 | 说明 |
|---|---|---|---|---|
| `shop` | 否 | string | 空字符串 | 店铺编号 `shop_no`，不是店铺显示名称。空字符串表示所有店铺。 |

其他参数见 6.1。

```bash
curl -G 'https://<API域名>/api/v1/shop-sales' \
  --data-urlencode 'start=2026-09-01' \
  --data-urlencode 'end=2026-09-30' \
  --data-urlencode 'warehouse=W-1' \
  --data-urlencode 'shop=SHOP-1' \
  --data-urlencode 'page=1' \
  --data-urlencode 'page_size=100'
```

**响应外层字段：**

| 字段 | 说明 |
|---|---|
| `summary` | 店铺数、SKU 数、销售/退货/净销量、销售金额等摘要。 |
| `items` | 当前页“店铺 + SKU”汇总结果。 |
| `shops` | 当前日期范围内可用的店铺列表与销量，可用于前端店铺下拉。 |
| `range` | 实际统计日期范围。 |
| `pagination` | `total`、`limit`、`offset`。 |

---

### 6.5 入库分析：`GET /api/v1/inbound`

**用途：** 基于出入库流水，按“仓库 + SKU”分析采购入库、调拨入库、退货入库和其他入库。

**专有参数：**

| 参数 | 是否必填 | 类型 | 默认值 | 可用值 | 说明 |
|---|---|---|---|---|---|
| `inbound_type` | 否 | integer | 不限制 | `1`、`2`、`3` 或其他实际流水类型值 | 指定单一入库流水类型。为空时统计所有入库类型。 |

常见 `inbound_type` 口径：

| 值 | 含义 |
|---:|---|
| `1` | 采购入库。 |
| `2` | 调拨入库。 |
| `3` | 退货入库。 |
| 其他正整数 | 归入其他入库；具体名称可通过 `movements.movement_name` 查询确认。 |

```bash
curl -G 'https://<API域名>/api/v1/inbound' \
  --data-urlencode 'start=2026-09-01' \
  --data-urlencode 'end=2026-09-30' \
  --data-urlencode 'warehouse=W-1' \
  --data-urlencode 'inbound_type=1' \
  --data-urlencode 'page=1' \
  --data-urlencode 'page_size=100'
```

**响应外层字段：**

| 字段 | 说明 |
|---|---|
| `summary` | 入库量、采购入库量、调拨入库量、退货入库量、其他入库量、SKU/仓库/流水数等汇总。 |
| `daily` | 按日入库统计。 |
| `items` | 当前页“仓库 + SKU”入库分析行。 |
| `range` | 实际统计日期范围。 |
| `filters.inbound_type` | 本次实际使用的入库类型筛选值；未筛选时为 `null`。 |
| `pagination` | `total`、`limit`、`offset`。 |

---

### 6.6 采购计划：`GET /api/v1/purchase-plan`

**用途：** 根据当前库存、历史销售、生产周期、MOQ、在途及系统已有的采购规则，返回采购建议。该接口属于已存在的业务算法接口，不是原始明细表的直接查询。

**专有参数：**

| 参数 | 是否必填 | 类型 | 默认值 | 范围 | 说明 |
|---|---|---|---:|---|---|
| `target_days` | 否 | integer | `30` | 1 ～ 3650 | 计划目标覆盖天数。数值越大，目标库存和建议采购量通常越高。 |

其他参数见 6.1。

```bash
curl -G 'https://<API域名>/api/v1/purchase-plan' \
  --data-urlencode 'start=2026-09-01' \
  --data-urlencode 'end=2026-09-30' \
  --data-urlencode 'warehouse=W-1' \
  --data-urlencode 'target_days=30' \
  --data-urlencode 'page=1' \
  --data-urlencode 'page_size=100'
```

**响应外层字段：**

| 字段 | 说明 |
|---|---|
| `items` | 当前页采购建议 SKU。每行包含库存、销量预测、生产/交期、建议下单量、状态和原因等字段。 |
| `summary` | 需立即下单、计划下单、参数待补充、存在风险等数量与建议采购总量统计。 |
| `range` | 实际使用的历史销量日期范围及天数。 |
| `target_days` | 本次生效的目标覆盖天数。 |
| `planning_basis` | 当前采购算法口径的文字说明。调用方展示采购建议时应同时理解此口径。 |
| `trend_filter` | 算法使用的趋势筛选上下界。 |
| `snapshot_date` | 用于库存计算的最新库存快照日期。 |
| `pagination` | `total`、`limit`、`offset`。 |

> 注意：采购计划是业务计算结果，建议用于辅助决策，不能直接等同于采购订单。修改生产周期、MOQ、商品属性或算法规则后，返回结果可能变化。

---

### 6.7 调拨计划：`GET /api/v1/transfer-plan`

**用途：** 根据销售仓库存和未来缺货情况，给出仓库间调拨建议。

**参数：** 仅使用 6.1 中的公共参数，无专有参数。

```bash
curl -G 'https://<API域名>/api/v1/transfer-plan' \
  --data-urlencode 'start=2026-09-01' \
  --data-urlencode 'end=2026-09-30' \
  --data-urlencode 'search=SKU-1001' \
  --data-urlencode 'page=1' \
  --data-urlencode 'page_size=100'
```

**响应外层字段：**

| 字段 | 说明 |
|---|---|
| `items` | 当前页调拨建议；包括来源仓、目标仓、建议调拨量、目标仓缺货量、目标日销、预计缺货日等。 |
| `summary` | 建议调拨记录数、调拨总量、涉及 SKU 数、目标仓数量。 |
| `range` | 实际统计日期范围。 |
| `planning_basis` | 调拨算法口径说明。 |
| `pagination` | `total`、`limit`、`offset`。 |

---

### 6.8 SKU 详情：`GET /api/v1/skus/{sku_no}`

**用途：** 获取一个 SKU 的商品主数据、各仓库存、指定日期区间内日销售/退货/采购趋势、财务汇总及最近出入库流水。

#### 路径参数

| 参数位置 | 参数 | 是否必填 | 类型 | 说明 |
|---|---|---|---|---|
| Path | `sku_no` | 是 | string | SKU 编码，例如 `SKU-1001`。如含空格、`/`、中文等特殊字符，客户端必须进行 URL 编码。 |

#### 查询参数

| 参数 | 是否必填 | 类型 | 默认值 | 说明 |
|---|---|---|---|---|
| `start` | 否 | string | 服务器当天向前 30 日的起始日 | 趋势和流水的开始日期，格式 `YYYY-MM-DD`。 |
| `end` | 否 | string | 服务器当天 | 趋势和流水的结束日期，格式 `YYYY-MM-DD`。 |

```bash
curl -G 'https://<API域名>/api/v1/skus/SKU-1001' \
  --data-urlencode 'start=2026-09-01' \
  --data-urlencode 'end=2026-09-30'
```

SKU 不存在时返回：

```http
404 Not Found
```

```json
{
  "detail": "SKU not found"
}
```

**响应外层字段：**

| 字段 | 类型 | 说明 |
|---|---|---|
| `product` | object | 商品主数据（不含 `raw_json`）。 |
| `warehouses` | array | 该 SKU 在各仓的库存信息。 |
| `daily` | array | 日期范围内逐日销售、退货、采购、销售额、退款额、净收入。 |
| `financials` | object | 日期范围内的 `sales_amount`、`refund_amount`、`net_revenue`。 |
| `recent_movements` | array | 日期范围内最近 30 条出入库流水，按事件时间倒序。 |

---

## 7. 数据集、字段与常用筛选字段

### 7.1 数据集名称

| `dataset` | SQLite 表 | 推荐日期字段 | 常见用途 |
|---|---|---|---|
| `products` | `products` | 无 | 商品、SKU、供应商、价格、生产和采购属性。 |
| `warehouses` | `warehouse_master` | 无 | 仓库主数据。 |
| `inventory_current` | `inventory_current` | 无 | 当前实时/最近同步库存。 |
| `inventory_snapshots` | `inventory_snapshots` | `snapshot_date` | 每日库存历史快照。 |
| `clearance_weekly_snapshots` | `clearance_weekly_snapshots` | `snapshot_date` | 清仓/周库存快照。 |
| `movements` | `movements` | `movement_date` | 出入库流水。 |
| `sales_lines` | `sales_lines` | `sale_date` | 销售出库明细。 |
| `return_lines` | `return_lines` | `return_date` | 退货入库明细。 |
| `sync_runs` | `sync_runs` | `sync_date` | 每日同步运行记录。 |

### 7.2 当前公开字段清单

> 下表基于当前数据库结构整理。运行中的服务以 `GET /api/v1/datasets` 返回的 `fields` 为唯一准则。所有表的 `raw_json` 均已被 API 隐藏。

#### `products`（商品主数据）

```text
sku_no, goods_no, goods_name, spec_name, barcode, unit_name,
retail_price, wholesale_price, updated_at, short_name, category,
product_structure, moq, production_days, metadata_status,
metadata_source, metadata_updated_at, supplier_id, supplier_no,
supplier_name, supplier_updated_at, purchase_price, production_line,
production_capacity, spec_remark, erp_price, goods_remark
```

常用条件：`sku_no`、`goods_no`、`goods_name`、`barcode`、`supplier_no`、`supplier_name`、`category`。

#### `warehouses`（仓库主数据）

```text
warehouse_id, warehouse_no, warehouse_name, warehouse_type,
is_disabled, role, modified, transfer_source_enabled
```

常用条件：`warehouse_id`、`warehouse_no`、`warehouse_name`、`role`、`is_disabled`。

#### `inventory_current`（当前库存）

```text
sku_no, warehouse_id, warehouse_no, warehouse_name, stock_num,
available_num, cost_price, avg_cost_price, modified, synced_at,
purchase_in_transit_num
```

常用条件：`sku_no`、`warehouse_id`、`warehouse_name`、`stock_num`、`available_num`。

#### `inventory_snapshots`（每日库存快照）

```text
snapshot_date, sku_no, warehouse_id, stock_num, available_num,
cost_price, purchase_in_transit_num
```

常用条件：`snapshot_date`、`sku_no`、`warehouse_id`。

#### `clearance_weekly_snapshots`（清仓/周库存快照）

```text
snapshot_week, snapshot_date, sku_no, warehouse_id, stock_num,
available_num, unit_cost, stock_cost, recorded_at, purchase_price,
purchase_cost
```

常用条件：`snapshot_week`、`snapshot_date`、`sku_no`、`warehouse_id`。

#### `movements`（出入库流水）

```text
movement_key, movement_date, event_time, sku_no, warehouse_id,
warehouse_no, warehouse_name, movement_type, movement_name, in_num,
out_num, quantity, src_order_no, source_id, source_detail_id
```

常用条件：`movement_date`、`sku_no`、`warehouse_id`、`movement_type`、`movement_name`、`src_order_no`。

#### `sales_lines`（销售出库明细）

```text
sale_key, sale_date, consign_time, sku_no, warehouse_id, warehouse_no,
warehouse_name, stockout_id, detail_id, source_detail_id, src_order_no,
order_no, quantity, paid_amount, share_amount, retail_price, sell_price,
cost_price, status, modified, shop_id, shop_no, shop_name
```

常用条件：`sale_date`、`sku_no`、`warehouse_id`、`shop_no`、`shop_name`、`status`、`order_no`。

#### `return_lines`（退货入库明细）

```text
return_key, return_date, stockin_time, sku_no, warehouse_id,
warehouse_no, warehouse_name, stockin_id, detail_id, source_detail_id,
src_order_no, order_no, quantity, refund_amount, source_price,
cost_price, status, modified
```

常用条件：`return_date`、`sku_no`、`warehouse_id`、`order_no`、`src_order_no`、`status`。

#### `sync_runs`（同步运行记录）

```text
id, sync_date, status, movement_count, inventory_count, sales_count,
return_count, cancellation_count, started_at, finished_at, error_message
```

常用条件：`sync_date`、`status`。

### 7.3 常用字段含义

| 字段 | 常见含义 |
|---|---|
| `sku_no` | SKU 编码；跨商品、库存、销售、退货、流水表的核心关联字段。 |
| `warehouse_id` | 仓库唯一 ID；业务接口的 `warehouse` 参数应传此值。 |
| `warehouse_no` / `warehouse_name` | 仓库编码 / 显示名称。 |
| `shop_id` / `shop_no` / `shop_name` | 店铺 ID / 店铺编号 / 显示名称。 |
| `stock_num` | 库存数量。 |
| `available_num` | 可用库存数量。 |
| `purchase_in_transit_num` | 采购在途数量。 |
| `quantity` | 单据或明细行数量。 |
| `in_num` / `out_num` | 入库 / 出库数量。 |
| `paid_amount` | 实付或已支付金额。 |
| `share_amount` | 分摊金额。 |
| `refund_amount` | 退款金额。 |
| `cost_price` / `avg_cost_price` | 成本单价 / 平均成本单价。 |
| `sale_date` / `return_date` / `movement_date` | 销售、退货、出入库的业务日期。 |
| `status` | 上游业务状态码。状态值的具体业务含义以旺店通源数据为准。 |

---

## 8. 二开调用建议

### 8.1 Python 调用主接口

```python
import requests

BASE_URL = "https://<API域名>"

payload = {
    "dataset": "sales_lines",
    "filters": [
        {"field": "sale_date", "op": "gte", "value": "2026-09-01"},
        {"field": "sale_date", "op": "lte", "value": "2026-09-30"},
    ],
    "group_by": ["sku_no"],
    "metrics": [
        {"field": "quantity", "agg": "sum", "alias": "sales_qty"},
        {"field": "paid_amount", "agg": "sum", "alias": "sales_amount"},
    ],
    "order_by": [{"field": "sales_qty", "direction": "desc"}],
    "page": 1,
    "page_size": 100,
}

response = requests.post(
    f"{BASE_URL}/api/v1/query",
    json=payload,
    timeout=60,
)
response.raise_for_status()
result = response.json()

print("总记录/分组数：", result["total"])
for row in result["items"]:
    print(row)
```

### 8.2 分页拉取全部数据

对于可能超过 1000 条的明细，必须循环翻页，不能试图把 `page_size` 设为超过 1000：

```python
import requests

url = "https://<API域名>/api/v1/query"
page = 1
page_size = 1000
all_rows = []

while True:
    payload = {
        "dataset": "inventory_snapshots",
        "fields": ["snapshot_date", "sku_no", "warehouse_id", "stock_num", "available_num"],
        "filters": [
            {"field": "snapshot_date", "op": "gte", "value": "2026-09-01"},
            {"field": "snapshot_date", "op": "lte", "value": "2026-09-30"},
        ],
        "page": page,
        "page_size": page_size,
    }
    body = requests.post(url, json=payload, timeout=60).json()
    all_rows.extend(body["items"])
    if page * page_size >= body["total"]:
        break
    page += 1

print(f"共获取 {len(all_rows)} 条")
```

### 8.3 查询性能建议

1. 查询 `sales_lines`、`return_lines`、`movements`、`inventory_snapshots` 等历史表时，优先加日期范围。
2. 只在 `fields` 中请求需要的列，不要无条件返回所有字段。
3. 可先按 `warehouse_id`、`sku_no`、`shop_no` 缩小范围，再做 `contains` 文本搜索。
4. 大范围统计时优先用 `group_by + metrics`，不要先拉取明细后在前端汇总。
5. 查询所有历史数据时务必分页；若一次请求响应很慢，应缩小日期范围或增加维度筛选。
6. 程序应正确处理 `503` 并进行有限次数重试，避免在每日同步短暂占用 SQLite 时直接判定服务永久不可用。

---

## 9. 接入验收清单

在将 API 交给业务人员或二开方前，建议逐项确认：

- [ ] `GET /api/v1/health` 返回 `200` 与 `read_only: true`。
- [ ] `GET /api/v1/status` 中最近同步记录日期符合预期。
- [ ] `GET /api/v1/datasets` 中存在需要使用的数据集和字段。
- [ ] `GET /api/v1/warehouses` 返回的 `warehouse_id` 可用于业务接口筛选。
- [ ] 使用 `POST /api/v1/query` 完成至少一次明细查询、一次分组求和查询。
- [ ] 对超过 1000 条数据的调用实现了分页。
- [ ] 客户端能够处理 `400`、`404`、`422`、`503` 错误。
- [ ] 已确认商品、库存、销售、供应商等公开数据符合公司的对外数据范围要求。

---

## 10. 文档与代码位置

| 内容 | 位置 |
|---|---|
| 本接口说明 | `docs/数据库API接口详细说明.md` |
| 服务架构、启动、部署和公网发布说明 | `docs/数据库只读 FastAPI 服务说明.md` |
| FastAPI 代码 | `src/wangdian_inventory/api.py` |
| 自动化测试 | `tests/test_api.py` |
| 在线 Swagger 文档 | `https://<API域名>/docs` |
| OpenAPI 标准定义 | `https://<API域名>/openapi.json` |
