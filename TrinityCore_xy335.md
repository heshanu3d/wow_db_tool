# develop
## eluna patch
```

git apply 0001-PATCH-Add-Eluna-LUA-engine.patch
git apply 0002-Eluna-multistate-update.patch
git apply 0003-Update-Eluna.patch
git apply 0004-Update-Eluna-for-removed-core-functions-and-flags.patch
git apply 0005-Switch-Eluna-objects-from-raw-pointers-to-unique-poi.patch
git apply 0006-Add-RegisterEvent-support-to-World-State.patch
git apply 0007-Remove-compatibility-mode.patch
git apply 0008-Add-new-Eluna-config-options.patch
git apply 0009-Eluna-Timed-event-rework.patch
git apply 0010-Eluna-Change-to-use-ElunaMgr.patch

or

git apply combined.patch

# if src/modules/Eluna exists and is a null directory
rm -rf src/modules/Eluna
git submodule add https://github.com/ElunaLuaEngine/Eluna.git src/modules/Eluna
cd src/modules/Eluna && git checkout ec65104fa5bf72e59b77d262104e08b90f967691
```

## update from upstream
```
git pull --rebase origin development
# resolve conflicts if there are any conflicts

./build.sh
mv /usr1/test/code/wow/install/bin/mangosd /usr1/test/code/wow/install/bin/mangosd.bak
mv /usr1/test/code/wow/install/bin/realmd /usr1/test/code/wow/install/bin/realmd.bak

push_wow /usr1/test/code/wow/install/bin/mangosd /usr1/test/code/wow/install/bin/
push_wow /usr1/test/code/wow/install/bin/realmd  /usr1/test/code/wow/install/bin/
# push mangosd.conf.dist/realmd.conf.dist if they get updated

ll sql/migrations
push_wow <update migrations> /usr1/test/code/wow/migrations
eg:
push_wow 20251106154733_world.sql /usr1/test/code/wow/migrations
push_wow 20251106160849_world.sql /usr1/test/code/wow/migrations
push_wow 20251106170051_world.sql /usr1/test/code/wow/migrations

mysql -u mangos -p mangos < 20251103125545_world.sql
or
mysql -u mangos -p mangos
source 20251103125545_world.sql

eg:
mysql -u mangos -p mangos < 20251103093357_world.sql
mysql -u mangos -p mangos < 20251106154733_world.sql
mysql -u mangos -p mangos < 20251106160849_world.sql
mysql -u mangos -p mangos < 20251106170051_world.sql
or simply insert the migration id (Important Note: Unless you have already inserted the content of this ID into the database, this step will only skip the migrations startup detection and has no practical significance.):
    mysql -u mangos -p mangos
    insert into migrations values (20251103125545);

```

## patch-z 转换到 sql
```
1. 使用 MPQEditor 解析patch-z 到 *dbc
2. 使用 WoW Spell Editor 导入 dbc
(可选， 双端操作)
3.1 从sql中导出 这些表
mysqldump -u root -p vmangos_test_mangos spell spellcasttimes spellduration spellvisual spellvisualeffectname spellvisualkit spellvisualprecasttransitions talent talenttab > wow_spell_tables.sql
3.2 导入到另个 数据库
mysql -u mangos -p mangos < wow_spell_tables.sql
```

## dbc to sql
```
open dbc with 'WDBX Editor'
Export -> To SQL File
ReEdit sql file with vscode, and replace the table name
```

## sql to dbc
```
open dbc with 'WDBX Editor'
Import -> From SQL
input pw -> connect -> select database -> select tables -> select Update Existing -> Load
```


# deploy
## mysql安装
```
on ubuntu
sudo apt install mysql-server

on debian
download mysql-apt-repository-config-file from https://dev.mysql.com/downloads/repo/apt/
sudo dpkg -i ~/Downloads/mysql-apt-config_0.8.36-1_all.deb
sudo apt update

sudo systemctl enable mysql
```

## 数据库创建 及 账号配置
```
sudo mysql -u root
CREATE USER 'mangos'@'localhost' IDENTIFIED BY 'mangos';

CREATE DATABASE realmd; CREATE DATABASE logs; CREATE DATABASE characters; CREATE DATABASE mangos;

use realmd; GRANT ALL PRIVILEGES ON realmd.* TO 'mangos'@'localhost';use characters; GRANT ALL PRIVILEGES ON characters.* TO 'mangos'@'localhost';use mangos; GRANT ALL PRIVILEGES ON mangos.* TO 'mangos'@'localhost';use logs; GRANT ALL PRIVILEGES ON logs.* TO 'mangos'@'localhost';FLUSH PRIVILEGES;
```

## 数据库导入
```
cd db_dump
mysql -u mangos -p
use realmd; source logon.sql;use characters; source characters.sql;use logs; source logs.sql;use mangos; source mangos.sql;
```

## 数据库删除
```
sudo mysql -u root
DROP DATABASE realmd; DROP DATABASE characters; DROP DATABASE mangos; DROP DATABASE logs;
```

## windows 数据库操作
```
cd D:\Game\wow-server\VMangos\db-4de428f
d:
chcp 65001
mysql -u root -p
# ascent
CREATE DATABASE vmangos_realmd; CREATE DATABASE vmangos_logs; CREATE DATABASE vmangos_characters; CREATE DATABASE vmangos_mangos;
use vmangos_realmd; source logon.sql;use vmangos_characters; source characters.sql;use vmangos_logs; source logs.sql;use vmangos_mangos; source mangos.sql;

DROP DATABASE vmangos_mangos;CREATE DATABASE vmangos_mangos;

use vmangos_realmd;     source g:/game/wow_server/VMangos_1.12/db-4de428f/logon.sql;
use vmangos_characters; source g:/game/wow_server/VMangos_1.12/db-4de428f/characters.sql;
use vmangos_logs;       source g:/game/wow_server/VMangos_1.12/db-4de428f/logs.sql;
use vmangos_mangos;     source g:/game/wow_server/VMangos_1.12/db-4de428f/mangos.sql;

DROP DATABASE vmangos_mangos;CREATE DATABASE vmangos_mangos;
DROP DATABASE vmangos_realmd;DROP DATABASE vmangos_logs;DROP DATABASE vmangos_characters;DROP DATABASE vmangos_mangos;

```

## mysql account
```
linux
mangos mangos
windows
root ascent
```

## open port on cloud server
```
open port 8085 3724 on cloud server
8085 for world server port
3724 for auth server port
```

## ban ip
```
遇到这种扫端口的，直接ban
eg:
ERROR:WorldSocket::handle_input_header:client 195.184.76.79 sent malformed packet size=5635, cmd=27656451

# 安装iptables-persistent
sudo apt install iptables-persistent

# 保存当前规则
sudo iptables-save > /etc/iptables/rules.v4

# 禁单个ip
sudo iptables -A INPUT -s 192.168.1.100 -j DROP
# 禁ip网段
sudo iptables -A INPUT -s 192.168.1.0/24 -j DROP

eg:
sudo iptables -A INPUT -s 91.196.0.0/16 -j DROP
sudo iptables -A INPUT -s 195.184.0.0/16 -j DROP
sudo iptables -A INPUT -s 79.124.0.0/16 -j DROP
sudo iptables -A INPUT -s 3.131.0.0/16 -j DROP
sudo iptables -A INPUT -s 180.101.0.0/16 -j DROP
sudo iptables -A INPUT -s 129.211.0.0/16 -j DROP
sudo iptables -A INPUT -s 47.113.0.0/16 -j DROP
sudo iptables -A INPUT -s 172.245.0.0/16 -j DROP
sudo iptables -A INPUT -s 8.134.0.0/16 -j DROP
sudo iptables -A INPUT -s 198.235.0.0/16 -j DROP
sudo iptables -A INPUT -s 220.196.0.0/16 -j DROP
sudo iptables -A INPUT -s 167.172.0.0/16 -j DROP
sudo iptables -A INPUT -s 172.236.0.0/16 -j DROP
sudo iptables -A INPUT -s 178.159.0.0/16 -j DROP
sudo iptables -A INPUT -s 120.48.0.0/16 -j DROP
sudo iptables -A INPUT -s 68.183.0.0/16 -j DROP
sudo iptables -A INPUT -s 3.130.0.0/16 -j DROP
sudo iptables -A INPUT -s 3.131.0.0/16 -j DROP
sudo iptables -A INPUT -s 205.210.0.0/16 -j DROP
sudo iptables -A INPUT -s 85.208.0.0/16 -j DROP
sudo iptables -A INPUT -s 45.43.0.0/16 -j DROP
sudo iptables -A INPUT -s 91.239.0.0/16 -j DROP
sudo iptables -A INPUT -s 3.137.0.0/16 -j DROP
sudo iptables -A INPUT -s 123.160.0.0/16 -j DROP
sudo iptables -A INPUT -s 8.210.0.0/16 -j DROP
sudo iptables -A INPUT -s 147.185.0.0/16 -j DROP
sudo iptables -A INPUT -s 59.83.0.0/16 -j DROP
sudo iptables -A INPUT -s 123.120.0.0/16 -j DROP
sudo iptables -A INPUT -s 139.162.0.0/16 -j DROP
sudo iptables -A INPUT -s 167.71.0.0/16 -j DROP
sudo iptables -A INPUT -s 167.94.0.0/16 -j DROP
sudo iptables -A INPUT -s 172.236.0.0/16 -j DROP
sudo iptables -A INPUT -s 178.22.0.0/16 -j DROP
sudo iptables -A INPUT -s 38.242.0.0/16 -j DROP
sudo iptables -A INPUT -s 45.142.0.0/16 -j DROP
sudo iptables -A INPUT -s 165.154.0.0/16 -j DROP

sudo iptables -A INPUT -s 59.83.208.104 -j DROP
sudo iptables -A INPUT -s 220.196.160.146 -j DROP
sudo iptables -A INPUT -s 180.101.245.251 -j DROP
sudo iptables-save > /etc/iptables/rules.v4
cat /etc/iptables/rules.v4
```

## issues
```
0. dep lib on debina
sudo apt install -qq libace-dev
push_wow /usr/lib/x86_64-linux-gnu/libACE-7.0.6.so /usr/lib

sudo apt-get install libmysqlclient-dev
push_wow /usr/lib/x86_64-linux-gnu/libmysqlclient.so.21.2.43 /usr/lib/x86_64-linux-gnu
ln -sf /usr/lib/x86_64-linux-gnu/libmysqlclient.so.21.2.43 /usr/lib/x86_64-linux-gnu/libmysqlclient.so.21
ln -sf /usr/lib/x86_64-linux-gnu/libmysqlclient.so.21 /usr/lib/x86_64-linux-gnu/libmysqlclient.so

sudo apt install libtbb-dev

1. [Realmd.log]  ERROR: No valid realms specified.
on windows:
SHOW COLUMNS FROM vmangos_realmd.realmlist;
INSERT INTO vmangos_realmd.realmlist (name, address, port, timezone, realmbuilds) VALUES ('vmangos_1.12.1', '127.0.0.1', 8085, 1, '5875 6005 6141');

on linux:
SHOW COLUMNS FROM realmd.realmlist;
INSERT INTO realmd.realmlist (name, address, port, timezone, realmbuilds) VALUES ('vmangos_1.12.1', '43.142.79.214', 8085, 1, '5875 6005 6141');

1.1 局域网
将127.0.0.1 改为 192.168.x.x

1.2 内网穿透
在 Sakura FRP 面板开启两个 TCP 隧道，记录下公网域名和公网端口。
修改数据库 auth.realmlist：
address = 你的公网域名 (例如 moe-1.sakurafrp.com)
port = World 隧道的公网端口
修改客户端 realmlist.wtf：
set realmlist 你的公网域名:Auth隧道的公网端口


2. [Mangos.log] .\5875/dbc is not found
Note that the dbc path must also include the build number of the client from which the files were extracted. If you are unsure what is the exact build, you can see it in the lower left corner of the login screen. The build number of the 1.12.1 client is 5875.
mkdir 5875
mv dbc 5875

3. [Mangos.log] Database `mangos` is missing the following migrations:
    20251103125545
appeared after source code update, but db didn't update with the corresponding version

cd sql/migrations

mysql -u mangos -p mangos < 20251103125545_world.sql
or
mysql -u mangos -p
source 20251103125545_world.sql
```
