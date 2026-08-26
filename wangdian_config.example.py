"""旺店通配置模板。

复制为项目根目录的 ``wangdian_config.py`` 后填写真实值。
该真实配置文件已被 .gitignore 排除，不会被提交到 Git。
"""

SID = "在这里填写卖家账号"
APP_KEY = "在这里填写接口账号"
APP_SECRET = "在这里填写接口密钥"

# 正式环境填写 production；测试环境填写 test。
ENVIRONMENT = "production"

# 可选：不填写时默认使用 data/inventory_production.db（正式环境）。
# DATABASE = "/home/ecs-user/wangyewangdian/data/inventory_production.db"
