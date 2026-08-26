# 旺店通库存、运营与采购日报系统

本项目通过旺店通正式 OpenAPI 同步商品、仓库、库存、销售出库、退货入库和出入库流水，数据保存到本地 SQLite，并提供：

- 浏览器库存工作台
- 仓库 SKU 销量与退货分析
- 库存积压、清仓、调拨和采购计划
- 每日及每周 Excel 报表
- Windows、Linux、macOS 自动同步与日报生成
- 可独立使用的旺店通 Python SDK

系统当前以“仓库 + SKU”为主要计算粒度。采购计划仅计算五个运营仓，具体算法见 [采购计划规则](docs/purchase-planning-rules.md)。

## 1. 项目目录

```text
wangyewangdian/
├── src/
│   ├── wangdian/                   # 旺店通 OpenAPI SDK、签名和异常处理
│   └── wangdian_inventory/         # 网页、同步、数据库和日报代码
├── data/
│   ├── inventory_production.db     # 正式生产数据库，务必备份
│   ├── daily-sync.log              # 每日任务标准输出
│   └── daily-sync-error.log        # 每日任务错误日志
├── outputs/                        # 自动或手动生成的 Excel 日报
├── docs/                           # 业务规则文档
├── deploy/
│   ├── windows/                    # Windows 计划任务脚本
│   ├── linux/                      # systemd service/timer
│   └── macos/                      # launchd plist
├── examples/                       # API 查询、资料导入和核对脚本
├── scripts/                        # 运维/导出辅助脚本
├── tests/                          # 自动化测试和接口核对数据
├── pyproject.toml
└── README.md
```

以下目录或文件可以自动重建，不应作为业务数据备份：

- `.venv/`
- `__pycache__/`
- `*.pyc`
- `dist/`
- `data/*.db-wal`
- `data/*.db-shm`

不要直接删除正在运行中的 `*.db-wal` 或 `*.db-shm`。需要回收 WAL 空间时，应先停止网页和同步进程，再执行本文“数据库维护”中的检查点命令。

## 2. 系统要求

- Python 3.9 及以上，建议 Python 3.11 或 3.12
- 能访问旺店通正式网关 `openapi.huice.com`
- 正式环境的 SID、App Key 和 App Secret
- 推荐至少 4GB 可用内存
- 数据库会随历史明细增长，建议预留至少 20GB 磁盘空间

当前数据量下，数据库正常增长约 24–27MB/天，即约 0.75GB/月。销售明细中的接口原始 JSON 是主要空间来源。

## 3. 安装

### 3.1 macOS / Linux

```bash
cd /path/to/wangyewangdian
python3 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -e .
```

### 3.2 Windows PowerShell

```powershell
cd C:\path\to\wangyewangdian
py -3.12 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -e .
```

如果 PowerShell 禁止激活脚本，可为当前用户执行一次：

```powershell
Set-ExecutionPolicy -Scope CurrentUser RemoteSigned
```

## 4. 配置旺店通凭证

推荐使用项目根目录的配置文件。先将模板复制为 `wangdian_config.py`：

```bash
cp wangdian_config.example.py wangdian_config.py
```

Windows PowerShell：

```powershell
Copy-Item wangdian_config.example.py wangdian_config.py
```

然后填写：

```python
SID = "你的卖家账号"
APP_KEY = "你的接口账号"
APP_SECRET = "你的接口密钥"
ENVIRONMENT = "production"
```

`wangdian_config.py` 已被 `.gitignore` 排除，不能提交或发送给他人。在 macOS/Linux 上建议限制权限：

```bash
chmod 600 wangdian_config.py
```

以后只需要直接编辑项目根目录的 `wangdian_config.py`，不用再到终端设置环境变量。Linux 云服务器上可以用编辑器打开：

```bash
nano /home/ecs-user/wangyewangdian/wangdian_config.py
```

保存后重启网页服务即可；定时任务也会自动读取同一个文件。环境变量仍可作为临时覆盖方式。

也可以使用环境变量：

```bash
export WDT_SID='...'
export WDT_APP_KEY='...'
export WDT_APP_SECRET='...'
export WDT_ENV='production'
export WDT_DATABASE='/absolute/path/to/data/inventory_production.db'
```

配置读取优先级为：环境变量优先，其次是项目根目录 `wangdian_config.py`，最后兼容旧路径 `examples/wangdian_config.py`。

如果没有配置凭证，系统默认进入演示模式并使用 `data/inventory_demo.db`。正式运行前请通过状态接口确认：

```bash
curl http://127.0.0.1:5052/api/status
```

返回结果中应满足：

```json
{
  "configured": true,
  "demo_mode": false,
  "environment": "production"
}
```

## 5. 启动网页

仅本机访问：

```bash
cd /path/to/wangyewangdian
PYTHONPATH=src .venv/bin/python -m wangdian_inventory.app --port 5050
```

当前 macOS 工区可直接执行：

```bash
cd /Users/tmt/wangyewangdian
PYTHONPATH=src .venv/bin/python -m wangdian_inventory.app --lan --port 5052 --no-browser
```

局域网访问：

```bash
PYTHONPATH=src .venv/bin/python -m wangdian_inventory.app --lan --port 5052 --no-browser
```

然后访问：

- 本机：`http://127.0.0.1:5052`
- 局域网：`http://电脑的局域网IP:5052`

`--lan` 会监听 `0.0.0.0`。请只在可信局域网使用，并在系统防火墙中仅开放需要的来源。

Windows PowerShell 对应命令：

```powershell
$env:PYTHONPATH = "$PWD\src"
.\.venv\Scripts\python.exe -m wangdian_inventory.app --lan --port 5052 --no-browser
```

## 6. 同步命令

所有命令都应在项目根目录执行。

### 6.1 同步指定日期

完整同步某一天的流水、销量、退货、取消单、商品资料和当前库存：

```bash
PYTHONPATH=src .venv/bin/python -m wangdian_inventory.app --sync 2026-08-23 --no-browser
```

该命令使用 UPSERT，可用于失败后的单日重跑。

### 6.2 每日完整同步

同步系统日期的前一天：

```bash
PYTHONPATH=src .venv/bin/python -m wangdian_inventory.app --daily-sync --no-browser
```

`--daily-sync` 当前包含：

- 出入库流水
- 销售出库
- 退货入库
- 取消出库单状态
- 当日更新的商品资料及自定义字段
- 仓库资料
- 当前库存与当天库存快照

### 6.3 每日任务：同步并生成日报

三平台定时任务统一使用：

```bash
PYTHONPATH=src .venv/bin/python -m wangdian_inventory.app --daily-job --no-browser
```

该命令会：

1. 完整同步昨天的数据；
2. 刷新当前库存；
3. 生成昨天的 Excel 日报；
4. 保存到：

```text
outputs/daily-report-YYYY-MM-DD/wangdian-supply-chain-daily-YYYY-MM-DD.xlsx
```

只有同步成功后才会生成日报。任务输出中的 `report_path` 是最终文件路径。

### 6.4 只刷新当前库存

```bash
PYTHONPATH=src .venv/bin/python -m wangdian_inventory.app --inventory-sync --no-browser
```

### 6.5 补录店铺维度销量

```bash
PYTHONPATH=src .venv/bin/python -m wangdian_inventory.app \
  --backfill-shop-sales 2026-08-01 2026-08-23 --no-browser
```

## 7. Excel 日报和周报

网页顶部可直接导出日报和周报，也可以调用：

```text
GET /api/reports/daily.xlsx?date=YYYY-MM-DD
GET /api/reports/weekly.xlsx?date=YYYY-MM-DD
```

例如网页服务运行在 5052 端口时：

```bash
curl -o daily.xlsx "http://127.0.0.1:5052/api/reports/daily.xlsx?date=2026-08-23"
```

当前日报包括：

| 工作表 | 内容 |
| --- | --- |
| `01_日报总览` | 同步、库存、运营和采购摘要 |
| `02_运营_清仓预警` | 清仓 SKU、库存天数和处理建议 |
| `03_运营_库存积压预警` | 含/不含在途覆盖、价格和供应商 |
| `04_运营_采购在途预警` | 五仓库存、销量、采购在途和覆盖天数 |
| `05_运营_结构调整建议` | 商品结构调整候选 |
| `06_运营_零销量与新品` | 零销量、新品和库存观察 |
| `07_采购_采购计划` | 五仓启用且非清仓 SKU 的采购日期、数量和优先级 |
| `08_采购_供应商分析` | 按供应商汇总采购计划 |
| `09_采购_在途与入库` | 采购、调拨和退货入库 |
| `10_共享_同步日志` | 最后一次同步状态和数量 |
| `11_共享_计算口径` | 报表核心算法说明 |

采购计划颜色：

- 红色：含在途库存天数严格小于完整交付周期，今天下单仍可能晚于缺货
- 黄色：建议下单日在未来 7 天内
- 蓝色：建议下单日在 7 天以后
- 紫色：低销量观察/清仓候选，不产生实际采购量
- 无颜色：生产周期等关键参数缺失，只展示不计算

宏博、博凯基础款的每月 5 日和 15 日仅作为执行参考。理论下单日先按“预计缺货日 − 完整交付周期”计算，不使用固定日放大紧急等级。

## 8. 三个平台的每日定时任务

默认时间均为每天 `01:10`，同步并生成前一天的日报。服务器时区必须是中国标准时间。

### 8.1 macOS：launchd

现成配置：

```text
deploy/macos/com.wangdian.inventory-daily.plist
```

当前配置路径是 `/Users/tmt/wangyewangdian`。迁移到其他 Mac 时，先修改 plist 中的 Python、项目、日志绝对路径。

检查并安装：

```bash
cd /Users/tmt/wangyewangdian
plutil -lint deploy/macos/com.wangdian.inventory-daily.plist
cp deploy/macos/com.wangdian.inventory-daily.plist \
  ~/Library/LaunchAgents/com.wangdian.inventory-daily.plist
launchctl bootout gui/$(id -u) \
  ~/Library/LaunchAgents/com.wangdian.inventory-daily.plist 2>/dev/null || true
launchctl bootstrap gui/$(id -u) \
  ~/Library/LaunchAgents/com.wangdian.inventory-daily.plist
launchctl enable gui/$(id -u)/com.wangdian.inventory-daily
```

立即试运行：

```bash
launchctl kickstart -k gui/$(id -u)/com.wangdian.inventory-daily
```

检查状态：

```bash
launchctl print gui/$(id -u)/com.wangdian.inventory-daily
tail -f data/daily-sync.log data/daily-sync-error.log
```

卸载：

```bash
launchctl bootout gui/$(id -u) \
  ~/Library/LaunchAgents/com.wangdian.inventory-daily.plist
```

### 8.2 Linux：systemd user timer

现成配置：

```text
deploy/linux/wangdian-inventory-daily.service
deploy/linux/wangdian-inventory-daily.timer
```

模板默认项目路径为 `/opt/wangyewangdian`。如果使用其他路径，需要同时修改 service 中的 `WorkingDirectory`、`PYTHONPATH`、`ExecStart` 和日志路径。

设置时区并安装：

```bash
sudo timedatectl set-timezone Asia/Shanghai
mkdir -p ~/.config/systemd/user
cp deploy/linux/wangdian-inventory-daily.service ~/.config/systemd/user/
cp deploy/linux/wangdian-inventory-daily.timer ~/.config/systemd/user/
systemctl --user daemon-reload
systemctl --user enable --now wangdian-inventory-daily.timer
```

如果服务器退出登录后也要继续执行：

```bash
sudo loginctl enable-linger "$(whoami)"
```

立即试运行：

```bash
systemctl --user start wangdian-inventory-daily.service
```

检查状态和下次执行时间：

```bash
systemctl --user status wangdian-inventory-daily.service
systemctl --user list-timers wangdian-inventory-daily.timer
journalctl --user -u wangdian-inventory-daily.service -n 100
```

卸载：

```bash
systemctl --user disable --now wangdian-inventory-daily.timer
```

### 8.3 Windows：任务计划程序

现成脚本：

```text
deploy\windows\run-daily-job.ps1
deploy\windows\install-daily-task.ps1
```

使用管理员或具有“创建计划任务”权限的 PowerShell：

```powershell
cd C:\path\to\wangyewangdian
Set-TimeZone -Id "China Standard Time"
powershell.exe -NoProfile -ExecutionPolicy Bypass `
  -File .\deploy\windows\install-daily-task.ps1 `
  -ProjectRoot "C:\path\to\wangyewangdian" `
  -RunAt "01:10"
```

立即试运行：

```powershell
Start-ScheduledTask -TaskName "WangDian Inventory Daily"
```

检查任务：

```powershell
Get-ScheduledTask -TaskName "WangDian Inventory Daily"
Get-ScheduledTaskInfo -TaskName "WangDian Inventory Daily"
Get-Content .\data\daily-sync.log -Tail 50
Get-Content .\data\daily-sync-error.log -Tail 50
```

卸载：

```powershell
Unregister-ScheduledTask -TaskName "WangDian Inventory Daily" -Confirm:$false
```

## 9. macOS 网页自启动

`deploy/macos/com.wangdian.inventory-web.plist` 用于启动局域网页服务，当前监听 5052 端口。安装方式与每日任务相同：

```bash
cp deploy/macos/com.wangdian.inventory-web.plist \
  ~/Library/LaunchAgents/com.wangdian.inventory-web.plist
launchctl bootstrap gui/$(id -u) \
  ~/Library/LaunchAgents/com.wangdian.inventory-web.plist
```

网页服务与每日任务是两个独立进程：网页停止不会删除数据；每日任务也不依赖浏览器保持打开。

## 10. 数据库维护和备份

正式数据库默认是：

```text
data/inventory_production.db
```

### 10.1 查看大小

```bash
ls -lh data/inventory_production.db*
du -h data/inventory_production.db*
```

### 10.2 安全回收 WAL

先停止网页和同步任务，确认没有进程占用：

```bash
lsof data/inventory_production.db*
```

然后执行：

```bash
sqlite3 data/inventory_production.db "PRAGMA wal_checkpoint(TRUNCATE); PRAGMA quick_check;"
```

正常输出应包含：

```text
0|0|0
ok
```

不要在数据库运行时直接删除 `inventory_production.db-wal`。

### 10.3 在线备份

推荐使用 SQLite 自带备份命令，而不是在服务运行时直接复制三个数据库文件：

```bash
mkdir -p backups
sqlite3 data/inventory_production.db \
  ".backup 'backups/inventory_production-$(date +%F).db'"
```

Windows PowerShell：

```powershell
New-Item -ItemType Directory -Force backups | Out-Null
$BackupDate = Get-Date -Format "yyyy-MM-dd"
sqlite3.exe data\inventory_production.db ".backup 'backups/inventory_production-$BackupDate.db'"
```

至少保留最近 7 份日备份和最近 3 份月备份，并定期复制到另一块磁盘或对象存储。

### 10.4 查看最后同步记录

```bash
sqlite3 -header -column data/inventory_production.db \
  "SELECT id,sync_date,status,movement_count,inventory_count,sales_count,return_count,error_message,started_at,finished_at FROM sync_runs ORDER BY id DESC LIMIT 10;"
```

## 11. 常见问题

### 11.1 `curl https://openapi.huice.com` 返回 404

如果返回类似：

```json
{"error_msg":"404 Route Not Found"}
```

通常说明 DNS、HTTPS 和旺店通网关可以连接，只是访问了没有具体 API 路由的根地址。实际请求必须由 SDK 调用 `/openapi/*.php` 并携带签名参数。

### 11.2 无法连接旺店通网关

依次检查：

```bash
curl -I https://openapi.huice.com
python -c "import socket; print(socket.gethostbyname('openapi.huice.com'))"
```

同时检查代理、防火墙、DNS、系统时间和旺店通接口频率限制。定时任务环境不会自动继承交互式终端中的代理或环境变量，因此优先使用本地配置文件或在服务配置中显式设置。

### 11.3 定时任务没有执行

先手动运行同一命令：

```bash
PYTHONPATH=src .venv/bin/python -m wangdian_inventory.app --daily-job --no-browser
```

如果手动成功但定时失败，通常是绝对路径、文件权限、时区或凭证环境不同。查看：

- `data/daily-sync.log`
- `data/daily-sync-error.log`
- macOS：`launchctl print ...`
- Linux：`journalctl --user -u ...`
- Windows：`Get-ScheduledTaskInfo ...`

### 11.4 报表数据为空

先检查 `sync_runs` 最后一条是否成功，再确认报表日期与同步日期一致。库存是当前快照，销量和退货按实际业务日期统计；补同步历史日期时，当前库存仍以执行同步当天从旺店通查询到的库存为准。

## 12. 开发和测试

运行全部自动化测试：

```bash
PYTHONPATH=src .venv/bin/python -m unittest discover -s tests -p 'test_*.py' -q
```

查看命令帮助：

```bash
PYTHONPATH=src .venv/bin/python -m wangdian_inventory.app --help
```

重新构建安装包（仅发布 SDK 时需要）：

```bash
.venv/bin/python -m pip install build
.venv/bin/python -m build
```

`dist/` 是可重建的发布产物，不属于生产业务数据。

## 13. SDK 单独调用示例

```python
from wangdian import WangdianClient

with WangdianClient(
    sid="...",
    app_key="...",
    app_secret="...",
    environment="production",
) as client:
    result = client.call(
        "warehouse_query",
        {"page_no": 0, "page_size": 100},
    )
    print(result)
```

SDK 会处理公共参数、Sign 签名、复杂参数 JSON 序列化、HTTP 请求和旺店通业务异常。创建类接口不会自动重试，以免产生重复业务单据。
