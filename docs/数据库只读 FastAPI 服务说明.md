# 旺店通 SQLite 只读 FastAPI 服务说明

> 本文面向需要把现有 SQLite 数据提供给业务人员、外部开发人员或二开程序使用的人员。
>
> 服务不负责同步数据。云服务器上原有的每日同步任务继续负责更新 `inventory_production.db`；FastAPI 进程只以 SQLite 只读模式打开同一个文件并提供查询。

## 1. 最终方案

### 1.1 服务边界

- **数据库**：继续使用云服务器上的 SQLite 文件，表名和字段名不改变。
- **API 框架**：FastAPI，使用 Uvicorn 运行。
- **业务数据接口**：`POST /api/v1/query`，通过数据集、字段、筛选条件、分组、聚合和分页完成查询。
- **辅助接口**：健康检查、状态、数据集字段清单、仓库清单，以及现有网页使用的业务查询接口。
- **权限**：按当前要求不设置登录，任何能访问公网地址的人都可以读取已公开的数据。
- **写入**：API 进程使用 SQLite `mode=ro`，不建表、不迁移、不写入业务数据。
- **数据更新**：由既有每日任务完成，API 会读取任务更新后的数据库内容。

`/api/v1/query` 是给二开人员使用的主接口。`/docs` 是 FastAPI 自动生成的在线接口说明页，启动服务后可以直接在浏览器打开测试。

### 1.2 数据库位置

本机开发数据库：

```text
/Users/tmt/wangyewangdian/data/inventory_production.db
```

云服务器当前观察到的路径：

```text
/home/ecs-user/wangdiantong_web/data/inventory_production.db
```

正式部署时不要把路径写死在代码中，使用环境变量：

```bash
export WDT_DATABASE=/home/ecs-user/wangdiantong_web/data/inventory_production.db
export WDT_DEMO_DATA=0
```

也可以在项目根目录的 `wangdian_config.py` 中设置 `DATABASE`。环境变量优先级最高。

## 2. 安装和启动

### 2.1 安装依赖

在项目根目录执行：

```bash
python3 -m venv .venv
.venv/bin/python -m pip install -e .
```

项目依赖中已经包含 `fastapi`、`uvicorn[standard]`、原有的 `requests` 和 `openpyxl`。

### 2.2 本机启动

```bash
WDT_DATABASE=/Users/tmt/wangyewangdian/data/inventory_production.db \
WDT_DEMO_DATA=0 \
PYTHONPATH=src \
.venv/bin/python -m wangdian_inventory.api
```

默认监听 `127.0.0.1:8000`。浏览器访问：

- Swagger UI：`http://127.0.0.1:8000/docs`
- ReDoc：`http://127.0.0.1:8000/redoc`
- OpenAPI JSON：`http://127.0.0.1:8000/openapi.json`

若需要在局域网直接访问，可以设置：

```bash
WDT_API_HOST=0.0.0.0 WDT_API_PORT=8000 \
WDT_DATABASE=/absolute/path/to/inventory_production.db \
PYTHONPATH=src .venv/bin/python -m wangdian_inventory.api
```

### 2.3 云服务器生产启动

建议 API 只监听本机回环地址，由 Nginx 或 Caddy 对外提供 HTTPS：

```bash
cd /home/ecs-user/wangdiantong_web
WDT_DATABASE=/home/ecs-user/wangdiantong_web/data/inventory_production.db \
WDT_DEMO_DATA=0 \
WDT_ENV=production \
PYTHONPATH=src \
.venv/bin/uvicorn wangdian_inventory.api:app \
  --host 127.0.0.1 \
  --port 8000 \
  --workers 1
```

SQLite 场景暂时使用一个 worker。这样可以避免多个进程各自加载同一份大型 SQLite 文件，也便于和现有同步任务协调。若后续并发量明显增长，再考虑数据库迁移到服务型数据库或增加缓存层，而不是简单增加 worker。

### 2.4 systemd 示例

项目提供模板 `deploy/linux/wangdian-inventory-api.service`。安装时按云服务器实际项目目录修改 `WorkingDirectory`、`Environment` 和 `ExecStart`，然后执行：

```bash
sudo cp deploy/linux/wangdian-inventory-api.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now wangdian-inventory-api
sudo systemctl status wangdian-inventory-api
journalctl -u wangdian-inventory-api -f
```

API 服务和每日同步服务是两个独立进程：同步服务负责写库，API 服务负责只读。同步任务执行期间若 SQLite 正在写入数据，API 请求可能短暂出现数据库忙或读取失败；服务恢复后可正常读取，不应让 API 进程去执行同步或修复数据库。

## 3. API 地址和返回格式

将下面的 `https://api.example.com` 替换为云服务器绑定的域名或公网地址。

成功返回通常是 JSON 对象，例如：

```json
{
  "dataset": "products",
  "table": "products",
  "fields": ["sku_no", "goods_name"],
  "page": 1,
  "page_size": 100,
  "total": 2,
  "items": [
    {"sku_no": "SKU-1", "goods_name": "商品一"}
  ]
}
```

常见 HTTP 状态码：`200` 成功；`400` 参数不正确；`404` 数据集或 SKU 不存在；`422` 请求格式不正确；`503` 数据库暂时无法访问。

## 4. 主查询接口：`POST /api/v1/query`

> 接口参数、完整调用示例、数据集字段清单及业务兼容接口的说明，见 [`数据库API接口详细说明.md`](数据库API接口详细说明.md)。


### 4.1 请求字段

| 字段 | 类型 | 默认值 | 说明 |
|---|---|---:|---|
| `dataset` | string | 必填 | 数据集名称，见第 5 节 |
| `fields` | string 数组 | `[]` | 明细字段；不传时返回该数据集全部公开字段 |
| `filters` | object 数组 | `[]` | 多个条件之间是 AND 关系 |
| `group_by` | string 数组 | `[]` | 分组字段 |
| `metrics` | object 数组 | `[]` | 聚合指标，支持 count/sum/avg/min/max |
| `order_by` | object 数组 | `[]` | 排序字段和方向 |
| `page` | integer | `1` | 从 1 开始 |
| `page_size` | integer | `100` | 每页 1～1000 条 |

分页最大值为 1000 条。即使业务人员不小心没有加筛选条件，也不会由一次请求直接返回整个大表。

### 4.2 明细查询示例

查询库存中可用库存大于等于 10 的记录，只返回指定字段：

```bash
curl -X POST 'https://api.example.com/api/v1/query' \
  -H 'Content-Type: application/json' \
  -d '{
    "dataset": "inventory_current",
    "fields": ["sku_no", "warehouse_name", "stock_num", "available_num"],
    "filters": [
      {"field": "available_num", "op": "gte", "value": 10}
    ],
    "order_by": [
      {"field": "available_num", "direction": "desc"}
    ],
    "page": 1,
    "page_size": 100
  }'
```

查询商品名称中包含“护具”的商品：

```json
{
  "dataset": "products",
  "fields": ["sku_no", "goods_name", "category", "supplier_name"],
  "filters": [
    {"field": "goods_name", "op": "contains", "value": "护具"}
  ]
}
```

### 4.3 日期范围查询

日期字段是字符串格式，建议使用 `YYYY-MM-DD`，并同时传开始、结束条件：

```json
{
  "dataset": "sales_lines",
  "fields": ["sale_date", "sku_no", "shop_name", "quantity", "paid_amount"],
  "filters": [
    {"field": "sale_date", "op": "gte", "value": "2026-08-01"},
    {"field": "sale_date", "op": "lte", "value": "2026-08-31"}
  ],
  "page": 1,
  "page_size": 500
}
```

### 4.4 分组和聚合查询

按仓库、店铺汇总 2026 年 8 月的销售数量和销售行数：

```json
{
  "dataset": "sales_lines",
  "filters": [
    {"field": "sale_date", "op": "gte", "value": "2026-08-01"},
    {"field": "sale_date", "op": "lte", "value": "2026-08-31"}
  ],
  "group_by": ["warehouse_name", "shop_name"],
  "metrics": [
    {"field": "quantity", "agg": "sum", "alias": "sales_qty"},
    {"field": "sale_key", "agg": "count", "alias": "line_count"},
    {"field": "paid_amount", "agg": "sum", "alias": "paid_total"}
  ],
  "order_by": [
    {"field": "sales_qty", "direction": "desc"}
  ],
  "page": 1,
  "page_size": 100
}
```

说明：`group_by` 决定统计粒度；`metrics` 决定统计内容；分组查询中 `fields` 只能填写 `group_by` 中的字段；使用指标但不分组时只传 `metrics` 可得到全表合计；指标别名只能使用字母、数字和下划线。

### 4.5 筛选操作符

| 操作符 | 含义 | value 示例 |
|---|---|---|
| `eq` | 等于 | `"SKU-1"` |
| `ne` | 不等于 | `0` |
| `gt` | 大于 | `10` |
| `gte` | 大于等于 | `10` |
| `lt` | 小于 | `100` |
| `lte` | 小于等于 | `100` |
| `contains` | 文本包含 | `"护具"` |
| `in` | 在集合中 | `["SKU-1", "SKU-2"]` |
| `is_null` | 为空 | `null` |

多个筛选条件会使用 AND 连接。当前不支持 OR 嵌套表达式；需要 OR 时，二开程序可以发起多次查询后合并。

### 4.6 Python 调用示例

```python
import requests

url = "https://api.example.com/api/v1/query"
payload = {
    "dataset": "sales_lines",
    "fields": ["sale_date", "sku_no", "shop_name", "quantity"],
    "filters": [
        {"field": "sale_date", "op": "gte", "value": "2026-08-01"},
        {"field": "sale_date", "op": "lte", "value": "2026-08-31"},
        {"field": "warehouse_id", "op": "eq", "value": "W-1"},
    ],
    "page": 1,
    "page_size": 100,
}
response = requests.post(url, json=payload, timeout=60)
response.raise_for_status()
for row in response.json()["items"]:
    print(row)
```

## 5. 数据集和数据库表

`GET /api/v1/datasets` 会返回运行中的 SQLite 实际字段清单。当前公开数据集如下：

| dataset | SQLite 表 | 常见用途 |
|---|---|---|
| `products` | `products` | 商品、SKU、供应商和商品属性 |
| `warehouses` | `warehouse_master` | 仓库主数据 |
| `inventory_current` | `inventory_current` | 当前仓库库存 |
| `inventory_snapshots` | `inventory_snapshots` | 每日库存历史 |
| `clearance_weekly_snapshots` | `clearance_weekly_snapshots` | 每周清仓库存快照 |
| `movements` | `movements` | 出入库流水 |
| `sales_lines` | `sales_lines` | 销售出库明细 |
| `return_lines` | `return_lines` | 退货入库明细 |
| `sync_runs` | `sync_runs` | 同步运行记录和数据量 |

接口会隐藏各表的 `raw_json` 字段。它是旺店通原始响应，内容大、结构可能随上游变化，不适合作为稳定公共接口字段；如确实需要原始字段，应先评估数据安全、响应体大小和长期兼容性。

## 6. 辅助接口

- `GET /api/v1/health`：检查 API 是否能读取数据库。
- `GET /api/v1/status`：返回数据库文件名、环境、只读标记和最近一次同步记录；公网不会返回绝对路径。
- `GET /api/v1/datasets`：返回数据集、真实表名、日期字段和公开字段清单。
- `GET /api/v1/warehouses`：返回仓库清单，适合前端下拉筛选。
- `GET /api/v1/table/{dataset}`：简单 GET 明细查询，示例为 `/api/v1/table/inventory_current?field=sku_no&field=warehouse_name&filter=warehouse_id:eq:W-1&page_size=50`。

为了兼容现有网页，还保留 `/api/v1/inventory`、`/api/v1/sales`、`/api/v1/shop-sales`、`/api/v1/inbound`、`/api/v1/purchase-plan`、`/api/v1/transfer-plan` 和 `/api/v1/skus/{sku_no}`。二开程序优先使用通用查询接口。

## 7. 公网发布检查清单

用户要求不登录、所有人可读，因此发布前必须确认这确实符合数据公开要求。建议至少完成：

1. **只开放 API 端口**：不要暴露 SQLite 文件；SQLite 没有独立数据库端口，客户端只能通过 HTTP API 读取。
2. **使用 HTTPS**：用 Nginx/Caddy 配置域名和 TLS，不建议裸 HTTP。
3. **反向代理**：公网只转发到 `127.0.0.1:8000`，Uvicorn 不直接暴露公网。
4. **CORS**：默认允许跨域；如以后知道前端域名，可设置 `WDT_API_CORS_ORIGINS=https://业务前端域名` 收紧范围。
5. **查询限制**：单页最多 1000 条，表和字段均为白名单，不允许传任意 SQL。
6. **文件权限**：API 运行用户只需要读数据库；每日同步任务继续使用写权限。
7. **数据确认**：已公开数据集包含商品、库存、销售、供应商和同步信息，请确认没有不应公开的价格、供应商或订单信息。
8. **备份**：只读 API 不等于备份，继续保留原有 SQLite 备份策略。

Nginx 反向代理最小示例：

```nginx
server {
    listen 443 ssl;
    server_name api.example.com;

    location / {
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_read_timeout 120s;
    }
}
```

## 8. 数据更新和故障排查

- API 启动时确认数据库文件存在，不会自动创建空库或初始化表结构。
- 每次请求独立打开只读连接，用完即关闭。
- API 不调用旺店通 OpenAPI，不读取 API 凭证，不负责每日任务。
- 数据新旧以云端同步任务和 `sync_runs` 为准；先查 `/api/v1/status`。
- `inventory_current` 是当前库存；`inventory_snapshots`、`clearance_weekly_snapshots` 是历史快照；`sales_lines`、`return_lines`、`movements` 是按日期的明细。
- 查询慢时先增加日期、仓库或 SKU 筛选，并只请求需要的字段；不要对历史大表无条件查询。

启动时报数据库不存在时，检查：

```bash
ls -lh /home/ecs-user/wangdiantong_web/data/inventory_production.db
```

`/docs` 能打开但查询 503 时，检查 API 用户的文件权限和服务日志：

```bash
systemctl status wangdian-inventory-api
journalctl -u wangdian-inventory-api -n 100 --no-pager
```

## 9. 代码和测试位置

- API 实现：`src/wangdian_inventory/api.py`
- SQLite 只读连接：`src/wangdian_inventory/db.py`
- API 自动化测试：`tests/test_api.py`
- 运行全部测试：

```bash
PYTHONPATH=src .venv/bin/python -m unittest discover -s tests -p 'test_*.py' -q
```

当前 API 测试覆盖健康检查、状态、字段元数据、明细筛选、分组聚合、分页、非法字段拒绝、简单 GET 查询和 SQLite 只读保护。
