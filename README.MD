
# allow mysql remote login on Ubuntu
```
sudo vim /etc/mysql/mysql.conf.d/mysqld.cnf

change
bind-address		= 127.0.0.1 -> 0.0.0.0
mysqlx-bind-address	= 127.0.0.1 -> 0.0.0.0

mysql -u root -p
create user 'hs'@'%' identified by '111';
grant all privileges on *.* to 'hs'@'%' with grant option;
flush privileges;

```
after this will support remote login
```
mysql -h x.x.x.x -u hs -p
```

