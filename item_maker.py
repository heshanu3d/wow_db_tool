import mysql.connector, csv, time
from mysql.connector import Error
from functools import wraps

local_config_1 = {
    'host':'localhost',
    'user':'root',
    'password':'root',
    'database':'acore_world'
}

local_config_2 = {
    'host':'localhost',
    'user':'root',
    'password':'ascent',
    'database':'mangos_world'
}

remote_config_1 = {
    'host':'192.168.71.71',
    'user':'root',
    'password':'root',
    'database':'acore_world'
}

local_configs = [local_config_1, local_config_2]
remote_configs = [remote_config_1]

# mysql_configs = remote_configs
mysql_configs = local_configs

class Mysql:
    def __init__(self):
        self._status = False
        self._connection = None
        self._config = None
        self._cursor = None
        self._sqls = []
        self._entrys = []
    def connect(self, configs=mysql_configs):
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
            for config in configs:
                if _connect(config):
                    break

    def db_operation_decorator(func):
        @wraps(func)
        def wrapper(self, *args, **kwargs):
            start_time = time.time()
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
            end_time = time.time()
            delta_time = end_time - start_time
            if delta_time > 0 and debug:
                print(f'{func.__name__} 耗时 {delta_time}秒')
            return ret
        return wrapper

    @db_operation_decorator
    def get_column_names_and_cnt(self, table):
        self._cursor.execute(f'SHOW COLUMNS FROM {table}')
        columns = self._cursor.fetchall()
        column_names = [column[0] for column in columns]
        return '('+','.join(column_names)+')', len(column_names)

    @db_operation_decorator
    def _copy_item(self, origin_entry, new_entry, sql, table='item_template', primary_key='entry'):
        # 查询item_template表中指定entry的行，除了entry以外的所有列
        query_select = f'SELECT * FROM {table} WHERE {primary_key} = {origin_entry};'
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

    def copy_item(self, origin_entry, new_entry, table='item_template', primary_key='entry'):
        s, c = self.get_column_names_and_cnt(table)

        sql_1 = f'INSERT INTO {table} {s}'
        sql_2 = 'VALUES (' + ','.join(['%s' for i in range(c)]) + ');'
        sql_insert = f'{sql_1} {sql_2}'

        self._copy_item(origin_entry, new_entry, sql_insert, table, primary_key)

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

    def gen_item_from_item_template(self, SoundOverrideSubclass='SoundOverrideSubclass'):
        sql = f'''
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
                    {SoundOverrideSubclass} AS sound_override_subclassid,
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
        columns, _ = self.get_column_names_and_cnt('item_template')
        if 'SoundOverrideSubclass' in columns:
            self.gen_item_from_item_template()
        else:
            self.gen_item_from_item_template('unk0')
        self.gen_csv_from_item()

    # 合成宝石
    def make_merge_jewel(self):
        instance.copy_item(18262, 81000)
        sql = '''
            CREATE TABLE IF NOT EXISTS item_up(id INT UNSIGNED NOT NULL,id1 INT UNSIGNED,id2 INT UNSIGNED,amount INT UNSIGNED,amount1 INT UNSIGNED,amount2 INT UNSIGNED,upid INT UNSIGNED, PRIMARY KEY (id));
            update item_template set class=12,quality=1,name='合成宝石',itemlevel=1,requiredlevel=1,buyprice=0,sellprice=0,spellid_1=13262 where entry=81000;
        '''
        self.execute_multi_sqls(sql)

    @db_operation_decorator
    def get_max_column_in_table(self, column='entry', table='item_template'):
        self._cursor.execute(f'select max({column}) from {table};')
        columns = self._cursor.fetchall()
        return columns[0][0]

    def multi_attr_value_in_item_template(self, entry, stat_rate=2,dmg_rate=1.4):
        sql = f'''
        UPDATE item_template SET stat_value1=stat_value1*{stat_rate},stat_value2=stat_value2*{stat_rate},stat_value3=stat_value3*{stat_rate},stat_value4=stat_value4*{stat_rate},stat_value5=stat_value5*{stat_rate},stat_value6=stat_value6*{stat_rate},stat_value7=stat_value7*{stat_rate},stat_value8=stat_value8*{stat_rate},stat_value9=stat_value9*{stat_rate},stat_value10=stat_value10*{stat_rate},dmg_min1=dmg_min1*{dmg_rate},dmg_max1=dmg_max1*{dmg_rate} WHERE entry={entry};
        '''
        self.execute_multi_sqls(sql)

    def update_tbl_item_up(self, old_entry, new_entry):
        # id, id1, id2, amount, amount1, amount2, upid
        sql = f'insert into item_up(id,id1,id2,amount,amount1,amount2,upid) values({old_entry},{old_entry},0,1,1,0,{new_entry});'
        self.execute_multi_sqls(sql)

    # 1156， 90000
    def add_update_item(self, old_entry, new_entry_ofs, max_up_cnt):
        for i in range(max_up_cnt):
            new_entry = new_entry_ofs + i
            self.copy_item(old_entry, new_entry)
            self.multi_attr_value_in_item_template(new_entry)
            self.update_tbl_item_up(old_entry, new_entry)
            old_entry = new_entry
        return new_entry_ofs + max_up_cnt

    @db_operation_decorator
    def get_equipment_entry_by_quality(self, quality): # green : 2, blue : 3, purple : 4
        self._cursor.execute(f'select entry from item_template where class in (2,4) and quality={quality};')
        columns = self._cursor.fetchall()
        return [column[0] for column in columns]

    def item_template_localeZH_1(self):
        sql = 'UPDATE item_template AS it JOIN locales_item AS li ON it.entry = li.entry SET it.name = li.name_loc4;'
        self.execute_multi_sqls(sql)
    def item_template_localeZH_2(self):
        sql = 'UPDATE item_template AS it JOIN item_template_locale AS itl ON it.entry = itl.id and itl.locale="zhCN" SET it.name = itl.name;'
        self.execute_multi_sqls(sql)

if __name__ == "__main__":
    debug = True
    instance = Mysql()
    # instance.copy_item(5201, 90000)

    # 合成宝石
    # instance.copy_item(18262, 81000)
    # instance.make_merge_jewel()
    # instance.add_update_item()

    # instance.item_template_localeZH_1()
    # instance.item_template_localeZH_2()

    # instance.save_sql('item_template')
    # instance.gen_item_csv()

    # print(instance.get_max_column_in_table())
    # print(instance.get_equipment_entry_by_quality(4))

    debug = False
    new_entry_ofs = instance.get_max_column_in_table() + 1
    # 蓝装最多强化到+3
    for old_entry in instance.get_equipment_entry_by_quality(3):
        new_entry_ofs = instance.add_update_item(old_entry, new_entry_ofs, 3)
    # 紫装最多强化到+5
    for old_entry in instance.get_equipment_entry_by_quality(4):
        new_entry_ofs = instance.add_update_item(old_entry, new_entry_ofs, 5)
    debug = True

    instance.gen_item_csv()