
# allow mysql remote login on Ubuntu
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
