import mysql.connector, csv
from mysql.connector import Error
from functools import wraps

mysql_config_1 = {
    'host':'localhost',
    'user':'root',
    'password':'root',
    'database':'acore_world'
}

mysql_config_2 = {
    'host':'localhost',
    'user':'root',
    'password':'ascent',
    'database':'mangos_world'
}

mysql_configs = [mysql_config_1, mysql_config_2]


class Mysql:
    def __init__(self):
        self._status = False
        self._connection = None
        self._config = None
        self._cursor = None
        self._sqls = []
        self._entrys = []
    def connect(self):
        def _connect(config):
            try:
                self._connection = mysql.connector.connect(
                    host=config['host'],
                    user=config['user'],
                    password=config['password'],
                    database=config['database']
                )
                if self._connection.is_connected():
                    self._db_info = self._connection.get_server_info()
                    if not self._status:
                        print(f"----------**---------\n成功连接到MySQL数据库，版本：{self._db_info}\n----------**---------")
                    self._status = True
                    self._cursor = self._connection.cursor()
                    self._config = config
                    return True
            except Error as e:
                print(f"数据库连接错误：{e}")
                return False
        if self._config:
            _connect(self._config)
        else:
            for config in mysql_configs:
                if _connect(config):
                    break


    def db_operation_decorator(func):
        @wraps(func)
        def wrapper(self, *args, **kwargs):
            self.connect()
            ret = None
            try:
                if self._connection.is_connected():
                    ret = func(self, *args, **kwargs)
                else:
                    print('Mysql is not connected')
            except Error as e:
                print(f"数据库操作错误：{e}")
            finally:
                # 关闭游标和连接
                if self._connection and self._connection.is_connected():
                    self._cursor.close()
                    self._connection.close()
                    # print("MySQL连接已关闭")
            return ret
        return wrapper

    @db_operation_decorator
    def get_column_names_and_cnt(self, table):
        self._cursor.execute(f'SHOW COLUMNS FROM {table}')
        columns = self._cursor.fetchall()
        column_names = [column[0] for column in columns]
        return '('+','.join(column_names)+')', len(column_names)

    @db_operation_decorator
    def _copy_item(self, origin_entry, new_entry, sql):
        # 查询item_template表中指定entry的行，除了entry以外的所有列
        query_select = f'SELECT * FROM item_template WHERE entry = {origin_entry};'
        self._cursor.execute(query_select)
        result = self._cursor.fetchone()

        if result:
            # 插入新行，entry设置为60000，其他列与id=20的行相同
            # 将result元组中的值（除了第一个值，即id）作为参数
            new_row = (new_entry,) + result[1:]

            self._cursor.execute(sql, new_row)
            self._connection.commit()
            print(f'新行entry={new_entry}已成功插入。')
            _i = sql.find('VALUES')
            self._entrys.append(new_entry)
            self._sqls.append(f'{sql[:_i]} VALUES{(*new_row,)};\n')
        else:
            print(f'未找到entry={new_entry}的行!')

    def copy_item(self, origin_entry, new_entry):
        table = 'item_template'
        s, c = self.get_column_names_and_cnt(table)

        sql_1 = f'INSERT INTO item_template {s}'
        sql_2 = 'VALUES (' + ','.join(['%s' for i in range(c)]) + ');'
        sql_insert = f'{sql_1} {sql_2}'

        self._copy_item(origin_entry, new_entry, sql_insert)

    def save_sql(self, filename):
        with open(filename + '_sql.txt', 'a') as f:
            f.writelines(self._sqls)
        with open(filename + '_entry.txt', 'a') as f:
            entrys = [str(entry) for entry in self._entrys]
            print(','.join(entrys))
            f.writelines(','.join(entrys) + ',')

    @db_operation_decorator
    def execute_multi_sqls(self, sqls):
        if isinstance(sqls, list):
            for sql in sqls:
                for s in sqls.split(';'):
                    self._cursor.execute(s.strip())                
        else:
            for s in sqls.split(';'):
                self._cursor.execute(s.strip())
        self._connection.commit()

    def gen_item_from_item_template(self):
        sql = '''
                DROP TABLE IF EXISTS item;
                CREATE TABLE IF NOT EXISTS item (
                    itemID INT(10) UNSIGNED NOT NULL,
                    ItemClass INT(10) UNSIGNED NOT NULL,
                    ItemSubClass INT(10) UNSIGNED NOT NULL,
                    sound_override_subclassid INT(11) DEFAULT NULL,
                    MaterialID INT(11) DEFAULT NULL,
                    ItemDisplayInfo INT(10) UNSIGNED DEFAULT NULL,
                    InventorySlotID INT(10) UNSIGNED DEFAULT NULL,
                    SheathID INT(10) UNSIGNED DEFAULT NULL,
                    PRIMARY KEY (itemID)
                );

                INSERT INTO item (itemID, ItemClass, ItemSubClass, sound_override_subclassid, MaterialID, ItemDisplayInfo, InventorySlotID, SheathID)
                SELECT entry AS itemID,
                    Class AS ItemClass,
                    Subclass AS ItemSubClass,
                    unk0 AS sound_override_subclassid,
                    Material AS MaterialID,
                    DisplayId AS ItemDisplayInfo,
                    InventoryType AS InventorySlotID,
                    Sheath AS SheathID
                FROM item_template;
        '''
        self.execute_multi_sqls(sql)

    @db_operation_decorator
    def gen_csv_from_item(self):
        sql = 'select * from item;'
        self._cursor.execute(sql)
        column_names = [i[0] for i in self._cursor.description]
        with open('item.csv', mode='w', newline='', encoding='utf-8') as f:
            writer = csv.writer(f)

            # 写入列名
            writer.writerow(column_names)

            # 写入数据行
            for row in self._cursor.fetchall():
                writer.writerow(row)

    def gen_item_csv(self):
        self.gen_item_from_item_template()
        self.gen_csv_from_item()

if __name__ == "__main__":
    instance = Mysql()
    # instance.copy_item(5201, 90000)

    # instance.save_sql('item_template')

    instance.gen_item_csv()

