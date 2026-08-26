-- 一次性迁移：分离旺店通的货品备注和规格备注
--
-- 执行前请先备份 inventory_production.db。
-- 本脚本针对当前数据库结构执行一次；如果已经执行过，请不要重复执行
-- ALTER TABLE 语句。

BEGIN IMMEDIATE;

ALTER TABLE products ADD COLUMN goods_remark TEXT NOT NULL DEFAULT '';

-- MZ07-K 的已知历史错误：旺店通货品备注为“4月10日”，三个规格备注均为空。
UPDATE products
SET goods_remark = '4月10日',
    spec_remark = ''
WHERE goods_no = 'TTDA033F'
  AND short_name = 'MZ07-K';

COMMIT;

