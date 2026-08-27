# Azeroth DB Forge GUI

本项目现在提供桌面 GUI，不再需要在 `main.py` 中反复打开/关闭注释。

## 启动

```bash
cd /usr1/test/code/wow/db_tool
python main.py
```

界面基于 Python 自带的 Tkinter。项目原有数据库依赖仍为：

```bash
pip install mysql-connector-python tabulate
```

如果系统缺少 Tkinter（Ubuntu/Debian），安装：

```bash
sudo apt install python3-tk
```

## GUI 能力

- 从界面选择数据库连接，并可新增、编辑、删除、测试连接。
- 按“世界与任务 / 物品与装备 / 专业技能 / 职业技能 / 萨满增强”分类展示功能。
- “职业技能”按死亡骑士、牧师、盗贼、萨满祭司分别展示，每个职业卡片都有“配置技能”入口。
- 职业配置页按 GCD、持续时间、伤害/治疗、天赋、触发几率等修改类型拆分；每个技能都可通过复选框决定是否执行，并可在输入框中修改数值、倍率或时长。最右侧会从当前选择的 `spell` 表读取 `SpellDescription4`（为空时读取 `SpellToolTip4`）并显示技能描述；当前数据库没有匹配记录时会明确标记为未找到。
- 技能输入框默认读取对应职业源码中的 `mod_*_skills` 字典；“恢复代码默认值”可随时恢复当前源码值。
- 搜索和状态筛选，支持单个应用或勾选后批量应用。
- 每次执行前明确显示目标数据库；高影响功能和重复应用会二次确认。
- 在**目标数据库**中自动创建 `db_tool_feature_runs` 表，保存成功、失败、耗时、日志和功能版本；职业技能执行日志会记录实际启用的技能及对应输入值。
- 功能源码或已保存的职业技能配置发生变化后，原来的记录会显示为“代码/配置有更新”，而不是错误地继续显示为当前版本已应用。
- 对于以前通过旧脚本执行、没有历史记录的功能，可点击“仅标记已应用”补录状态，不会再次修改游戏数据。
- “执行历史”页面可查看全部执行记录；双击记录可查看日志。

数据库连接和职业技能配置都保存在项目根目录的 `.db_tool_gui.json`。技能配置点击“保存配置”后持久化，重新启动 GUI 仍会保留。该文件可能包含数据库密码，已加入 `.gitignore`，请不要手动提交。

> 倍率、生成和删除类功能重复执行可能继续叠加或覆盖数据。GUI 会提示，但不能替代数据库备份。生产数据库执行高影响功能前仍应先使用 `mysqldump` 备份。

---

# 原项目说明

# I 准备工作
## allow mysql remote login on Ubuntu
```
sudo vim /etc/mysql/mysql.conf.d/mysqld.cnf

change
bind-address		= 127.0.0.1 -> 0.0.0.0
mysqlx-bind-address	= 127.0.0.1 -> 0.0.0.0

mysql -u root -p

create user 'root'@'%' IDENTIFIED with mysql_native_password by 'root';
grant all privileges on *.* to 'root'@'%' with grant option;
flush privileges;

sudo systemctl restart mysql

```
after this will support remote login
```
mysql -h x.x.x.x -u hs -p
```

## ERROR 2059 (HY000): Authentication plugin 'caching_sha2_password' cannot be loaded
```
ALTER USER 'root'@'%' IDENTIFIED WITH mysql_native_password BY 'root';

# on non-root user
ALTER USER 'mangos'@'localhost' IDENTIFIED WITH mysql_native_password BY 'mangos';

# 更改回原来的 caching_sha2_password 认证方式
ALTER USER 'mangos'@'localhost' IDENTIFIED WITH caching_sha2_password BY '你的密码，如mangos';
ALTER USER 'mangos'@'localhost' IDENTIFIED WITH caching_sha2_password BY 'mangos';
```

## ERROR 1045 (28000): Access denied for user 'root'@'192.168.71.87' (using password: YES)
```
create user 'root'@'%' IDENTIFIED with mysql_native_password by 'root';
```

## user权限查询
```
SELECT host, user, authentication_string, plugin FROM user WHERE user='hs';
```

## 数据库导出及导入
```
# 步骤1：导出表结构及数据
mysqldump -u 用户名 -p 数据库A 表t > table_t.sql

# 只导出数据（如果表结构已存在）
mysqldump -u 用户名 -p --no-create-info 数据库A 表t > table_t_data.sql

# 步骤2：导入到数据库B
mysql -u 用户名 -p 数据库B < table_t.sql
```

# II 宝石强化
生成 蓝宝石强化+1 -> +3、紫宝石的强化+1 -> +5的 item_template、gemproperties、spellitemenchantment和item_up 信息
## 双端操作 windows开发，linux部署
**双端操作最重要的事保证两端的数据一致性**

1. 先将版本的 gemproperties、spellitemenchantment 信息导入到开发数据库中（因为服务端是读取dbc的形式获取信息的，
操作为方便数据修改，使用WoW Spell Editor v2.x.x 或 更高的版本导入到数据库中）
```
    WoW Spell Editor v2.x.x
    1. 软件config 配置正确的dbc路径
    2. import 勾选gemproperties.dbc和spellitemenchantment.dbc后点击IMPORT CHECKED DBC FILES
```

2. 为了确保 windows 端的item_template和item_up表和运行环境linux数据的一致，先dump linux里的这两个表的数据
```
    mysqldump -u root --password=root acore_world item_template > dump_item_template.sql
    mysqldump -u root --password=root acore_world item_up > dump_item_up.sql
```
- (选)为方便dump, 在linux特意制作了快捷命令如下

```
    hs@hs-Virtual-Machine:~/code/wow/wow_db_tool$ cat /usr/bin/dump
    #!/usr/bin/bash
    table=$1
    mysqldump -u root --password=root acore_world $table > $(pwd)/dump_$1.sql
```
- (选)实际dump只需要 dump item_template
```
    dump item_template
    dump item_up
```

3. 拷贝item_template、item_up两个表的dump_sql文件在windows上导入到开发数据库中
```
    mysqldump -u root --password=root acore_world < dump_item_template.sql
    mysqldump -u root --password=root acore_world < dump_item_up.sql
```

4. 在windows侧生成 宝石升级 所需要的 item_template、gemproperties、spellitemenchantment和item_up 信息.
    - 对应的生成命令是gen_jewel_update
    - 也可以先执行del_update_jewel_dbinfo清除表里已有的 升级宝石信息
    - 执行完成后会生成三个sql文件all.sql是windows端导入升级宝石信息用的，
    item_template.sql和item_up.sql是给linux端导入升级宝石信息用的(
    相比all.sql，少了gemproperties、spellitemenchantment的相关信息，这部分将会采用dbc方式导入
    )

```
    # 删除强化蓝宝石、黄宝石信息
    del_update_jewel_dbinfo(instance)

    # 生成蓝宝石、紫宝石的强化+1 -> +5的 item_template、gemproperties、spellitemenchantment和item_up 信息
    gen_jewel_update(instance, 2)

    生成文件在py脚本同目录下
    G:\code\wow_tool\wow_db_tool\all.sql
    G:\code\wow_tool\wow_db_tool\item_template.sql
    G:\code\wow_tool\wow_db_tool\item_up.sql
```

5. windows侧导入宝石升级信息
```
    mysqldump -u root --password=root acore_world < all.sql
```

6. windows生成与item_template对应的item表信息
    - 执行命令gen_item_csv
```
    instance.gen_item_csv()
```

7. 使用 WoW Spell Editor 导出 windows数据库里的gemproperties、spellitemenchantment和item表信息到dbc文件
```
    1. export 勾选gemproperties.dbc、spellitemenchantment.dbc和item.dbc后点击 EXPORT CHECKED TO DBC FILES
    2. 生成文件默认在WoW Spell Editor/Export下
    D:\Game\wow\tools\WoW Spell Editor\Export\gemproperties.dbc
    D:\Game\wow\tools\WoW Spell Editor\Export\spellitemenchantment.dbc
    D:\Game\wow\tools\WoW Spell Editor\Export\item.dbc
```

8. linux侧导入相关升级宝石信息
    - 导入item_template、item_up表信息
    - 使用windows侧(7.里生成的)的gemproperties.dbc、spellitemenchantment.dbc文件覆盖linux侧的对应文件（服务端是没有gemproperties、spellitemenchantment这两个表的，其内容是采用读取dbc的方式）
```
    mysqldump -u root --password=root acore_world < item_template.sql
    mysqldump -u root --password=root acore_world < item_up.sql

    /usr1/test/code/c++/wow/azerothcore-wotlk-Latest/install/release/bin/data/dbc/gemproperties.dbc
    /usr1/test/code/c++/wow/azerothcore-wotlk-Latest/install/release/bin/data/dbc/dbc、spellitemenchantment.dbc
```

9. wow客户端导入新生成的item.dbc、gemproperties.dbc、spellitemenchantment.dbc文件
```
    使用 MPQ Editor V3.2.1.629 原版.exe 打开G:\Game\wow_client\逍遥335高清客户端\Data\PATCH-Z.MPQ下进行dbc覆盖
```

## 单端操作(windows)
只需执行双端操作力的 1、4、5、6、7、9 步骤即可
