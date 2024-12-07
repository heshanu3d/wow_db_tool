
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
```

## ERROR 1045 (28000): Access denied for user 'root'@'192.168.71.87' (using password: YES)
```
create user 'root'@'%' IDENTIFIED with mysql_native_password by 'root';
```

## user权限查询
```
SELECT host, user, authentication_string, plugin FROM user WHERE user='hs';
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
