import mysql.connector, csv, time, re
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
        return column_names

    @db_operation_decorator
    def _copy_item(self, origin_entry, new_entry, sql, modify, last_result, table='item_template', primary_key='entry', gen_sql_mode=False):
        if len(last_result) == 0:
            # 查询item_template表中指定entry的行，除了entry以外的所有列
            query_select = f'SELECT * FROM {table} WHERE {primary_key} = {origin_entry};'
            self._cursor.execute(query_select)
            result = self._cursor.fetchone()
        else:
            query_select=''
            result = last_result[1]

        if result:
            _result = list(result)
            if len(modify) > 0:
                for mod in modify:
                    if len(mod) == 2:
                        _result[mod[0]] = mod[1]
                    elif len(mod) == 3:
                        if mod[2].startswith('plus'):
                            _result[mod[0]] += mod[1]
                        elif mod[2].startswith('multi'):
                            _result[mod[0]] *= mod[1]
                        elif mod[2].startswith('compo_multi'):
                            _result[mod[0]] = (_result[mod[0]] + 1) * mod[1] - 1
                        elif mod[2].startswith('add_update_suffix'):
                            _result[mod[0]] = re.sub(r"\+(\d+)", "{}".format(mod[1]), _result[mod[0]])
                        elif mod[2].startswith('digit_in_str_multi'):
                            def multiply_digits(match):
                                return str(int(match.group(0)) * mod[1])
                            _result[mod[0]] = re.sub(r'\d+', multiply_digits, _result[mod[0]])

            new_row = tuple(_result)

            if not gen_sql_mode:
                self._cursor.execute(sql, new_row)
                self._connection.commit()
                print(f'新行entry={new_entry}已成功插入。')
            else:
                _i = sql.find('VALUES')
                self._entrys.append(new_entry)
                self._sqls.append(f'{sql[:_i]} VALUES{(*new_row,)};\n')
            return f'{sql[:_i]} VALUES{(*new_row,)};\n', new_row
        else:
            print(f'未找到entry={new_entry}的行!  请检查 查询语句:')
            print(f'    {query_select}')
            return "", ()

    # modify = [['id',3], ['type',5]] 表示把复制的结果集里的id列的值改为3，type列的值改为5
    def copy_item(self, origin_entry, new_entry, modify:list=[], last_result:tuple=(), table='item_template', primary_key='entry', gen_sql_mode=False):
        if len(last_result) == 0:
            column_names = self.get_column_names_and_cnt(table)
        else:
            column_names = last_result[2]
        s = '('+','.join(column_names)+')'
        c = len(column_names)

        modify.append([primary_key, new_entry])
        column_names_dict = {item.lower(): idx for idx, item in enumerate(column_names)}
        for mod in modify:
            col = mod[0].lower()
            val = mod[1]
            if col in column_names_dict.keys():
                mod[0] = column_names_dict[col]
        

        sql_1 = f'INSERT INTO {table} {s}'
        sql_2 = 'VALUES (' + ','.join(['%s' for i in range(c)]) + ');'
        sql_insert = f'{sql_1} {sql_2}'

        _sql, _vals = self._copy_item(origin_entry, new_entry, sql_insert, modify, last_result, table, primary_key, gen_sql_mode=gen_sql_mode)
        return _sql, _vals, column_names

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
                for s in sql.split(';'):
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
    def gen_csv_from_table(self, table):
        sql = f'select * from {table};'
        self._cursor.execute(sql)
        column_names = [i[0] for i in self._cursor.description]
        with open(f'{table}.csv', mode='w', newline='', encoding='utf-8') as f:
            writer = csv.writer(f)

            # 写入列名
            writer.writerow(column_names)

            # 写入数据行
            for row in self._cursor.fetchall():
                writer.writerow(row)

    def gen_item_csv(self):
        column_names = self.get_column_names_and_cnt('item_template')
        columns = '('+','.join(column_names)+')'

        if 'SoundOverrideSubclass' in columns:
            self.gen_item_from_item_template()
        else:
            self.gen_item_from_item_template('unk0')
        self.gen_csv_from_table('item')
    
    def gen_sqlfile_from_sqls(self, filename, sqls:list):
        with open(filename+'.sql', 'w', encoding='utf-8') as f:
            f.writelines(sqls)
        print(f'use cmd to import {filename}.sql into mysql:')
        print(f'    mysql -u root --password=root acore_world < {filename}.sql')

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

    def multi_attr_value_in_item_template(self, entry, stat_rate=2, dmg_rate=1.4, gen_sql_mode=False):
        sql = f'''
        UPDATE item_template SET stat_value1=stat_value1*{stat_rate},stat_value2=stat_value2*{stat_rate},stat_value3=stat_value3*{stat_rate},stat_value4=stat_value4*{stat_rate},stat_value5=stat_value5*{stat_rate},stat_value6=stat_value6*{stat_rate},stat_value7=stat_value7*{stat_rate},stat_value8=stat_value8*{stat_rate},stat_value9=stat_value9*{stat_rate},stat_value10=stat_value10*{stat_rate},dmg_min1=dmg_min1*{dmg_rate},dmg_max1=dmg_max1*{dmg_rate} WHERE entry={entry};
        '''
        if not gen_sql_mode:
            self.execute_multi_sqls(sql)
        else:
            self._sqls.append(f'{sql}\n')

    def update_tbl_item_up(self, id, id1, new_entry, gen_sql_mode=False):
        # id, id1, id2, amount, amount1, amount2, upid
        sql = f'insert into item_up(id,id1,id2,amount,amount1,amount2,upid) values({id},{id1},0,1,1,0,{new_entry});'
        if not gen_sql_mode:
            self.execute_multi_sqls(sql)
        else:
            self._sqls.append(f'{sql}\n')
        return sql

    # 1156， 90000
    def add_update_item(self, old_entry, new_entry_ofs, max_up_cnt, gen_sql_mode=False):
        for i in range(max_up_cnt):
            new_entry = new_entry_ofs + i
            self.copy_item(old_entry, new_entry, gen_sql_mode=gen_sql_mode)
            self.multi_attr_value_in_item_template(new_entry, gen_sql_mode=gen_sql_mode)
            self.update_tbl_item_up(old_entry, old_entry, new_entry, gen_sql_mode=gen_sql_mode)
            old_entry = new_entry
        return new_entry_ofs + max_up_cnt
    
    def gen_add_update_item_sql(self, old_entry, new_entry_ofs, max_up_cnt):
        self.add_update_item(old_entry, new_entry_ofs, max_up_cnt, gen_sql_mode=True)

    @db_operation_decorator
    def get_origin_update_item_id(self):
        self._cursor.execute(f'select id from item_up where id < 60000;')
        columns = self._cursor.fetchall()
        return [column[0] for column in columns]

    # {id : upid, ...}
    @db_operation_decorator
    def get_item_up_dict(self):
        self._cursor.execute(f'select id,upid from item_up;')
        columns = self._cursor.fetchall()
        item_up = {}
        for column in columns:
            item_up[column[0]] = column[1]
        return item_up

    # 'select entry,name from item_template where entry>90000 and not name like "%+%";'
    def fix_upitem_name(self):
        item_up = self.get_item_up_dict()

        for idx, id in enumerate(self.get_origin_update_item_id()):
            upid = id
            lvl = 0
            sqls = ''
            while upid in item_up.keys():
                upid = item_up[upid]
                lvl += 1
                sqls += f'update item_template set name=concat(name,"+{lvl}") where entry={upid};'
            self.execute_multi_sqls(sqls)
            if idx % 100 == 99:
                print(__name__, f'execute {idx} items')
    # 修改合成公式为 升级物品（+N）+原始物品 = 升级物品(+ N+1)
    def modify_upitem_id1(self):
        item_up = self.get_item_up_dict()
        sqls = ''
        for idx, id in enumerate(self.get_origin_update_item_id()):
            upid = id
            while upid in item_up.keys():
                if id != upid:
                    sqls += f'update item_up set id1={id} where id={upid};\n'
                upid = item_up[upid]
            # self.execute_multi_sqls(sqls)
            if idx % 100 == 99:
                print('modify_upitem_id1', f'execute {idx} items')
        print(sqls)
        print(len(sqls.split('\n')))
        self.execute_multi_sqls(sqls)

    @db_operation_decorator
    def get_equipment_entry_by_quality(self, quality): # green : 2, blue : 3, purple : 4
        self._cursor.execute(f'select entry from item_template where class in (2,4) and quality={quality};')
        columns = self._cursor.fetchall()
        return [column[0] for column in columns]

    @db_operation_decorator
    def get_entry_of_jewel_needs_updated(self, quality):
        sql = f'''
            select i.entry,i.GemProperties,gem.SpellItemEnchantmentRef
            from item_template i
            left join GemProperties gem on gem.id=i.GemProperties 
            where class = 3 and Quality = {quality} and i.GemProperties!=0 and gem.SpellItemEnchantmentRef!=0;
        '''
        self._cursor.execute(sql)
        columns = self._cursor.fetchall()
        return columns
        # return [(column[0]) for column in columns]

    def item_template_localeZH_1(self):
        sql = 'UPDATE item_template AS it JOIN locales_item AS li ON it.entry = li.entry SET it.name = li.name_loc4;'
        self.execute_multi_sqls(sql)
    def item_template_localeZH_2(self):
        sql = 'UPDATE item_template AS it JOIN item_template_locale AS itl ON it.entry = itl.id and itl.locale="zhCN" SET it.name = itl.name;'
        self.execute_multi_sqls(sql)
    
    def backup_table(self, table):
        sql = f'CREATE TABLE {table}_b AS SELECT * FROM {table};'
        self.execute_multi_sqls(sql)
    def clear_table_content(self, table):
        sql = f'DELETE FROM {table};'
        self.execute_multi_sqls(sql)

# 生成蓝装、紫装的强化+1 -> +5的 item_template和item_up 信息
def gen_item_update_v1(instance):
    debug = False
    new_entry_ofs = instance.get_max_column_in_table() + 1
    # 蓝装最多强化到+3
    for old_entry in instance.get_equipment_entry_by_quality(3):
        new_entry_ofs = instance.add_update_item(old_entry, new_entry_ofs, 3)
    # 紫装最多强化到+5
    for old_entry in instance.get_equipment_entry_by_quality(4):
        new_entry_ofs = instance.add_update_item(old_entry, new_entry_ofs, 5)
    
    # 修复强化装备的名字: 原始名字->原始名字+强化等级， 如：豪华珠宝戒指+1，豪华珠宝戒指+2，豪华珠宝戒指+3，etc...
    instance.fix_upitem_name()
    debug = True
    instance.gen_item_csv()

    instance.modify_upitem_id1()

# 生成蓝装、紫装的强化+1 -> +5的 item_template和item_up 信息
def gen_item_update_v2(instance):
    debug = False
    new_entry_ofs = instance.get_max_column_in_table() + 1
    # 蓝装最多强化到+3
    for old_entry in instance.get_equipment_entry_by_quality(3):
        new_entry_ofs = instance.gen_add_update_item_sql(old_entry, new_entry_ofs, 3)
    # 紫装最多强化到+5
    for old_entry in instance.get_equipment_entry_by_quality(4):
        new_entry_ofs = instance.gen_add_update_item_sql(old_entry, new_entry_ofs, 5)

    debug = True

# 取消副本进入限制(成就、任务、物品)
def remove_dungeon_requirements(instance):
    instance.backup_table('dungeon_access_requirements')
    instance.clear_table_content('dungeon_access_requirements')

# 去掉装备和武器的唯一属性
def remove_unique_attr_on_equip(instance):
    sql = 'update item_template set maxcount=0 where class in (2,4) and maxcount=1;'
    instance.execute_multi_sqls(sql)

# x倍率 放大 卷轴效果
def multi_effect_on_scroll(instance, multi):
    sql = f'''
            update spell s set s.EffectBasePoints1=(s.EffectBasePoints1+1)*{multi}-1
            WHERE EXISTS (
                SELECT 1 FROM item_template it
                WHERE s.id = it.spellid_1 and s.Effectbasepoints1!=-1 and s.Effectbasepoints1!=0 and it.class=0 and it.subclass=4
            );
    '''
    instance.execute_multi_sqls(sql)

# x倍率 放大 药剂效果
def multi_effect_on_potion(instance, multi):
    sql = f'''
            update spell s set s.EffectBasePoints1=(s.EffectBasePoints1+1)*{multi}-1
            WHERE EXISTS (
                SELECT 1 FROM item_template it
                WHERE s.id = it.spellid_1 and s.Effectbasepoints1!=-1 and s.Effectbasepoints1!=0 and it.class=0 and it.subclass=2
            );
            update spell s set EffectBasePoints2=(EffectBasePoints2+1)*{multi}-1
            WHERE EXISTS (
                SELECT 1 FROM item_template it
                WHERE s.id = it.spellid_1 and s.EffectBasePoints2!=-1 and s.EffectBasePoints2!=0 and it.class=0 and it.subclass=2
            );
            update spell s set EffectBasePoints3=(EffectBasePoints3+1)*{multi}-1
            WHERE EXISTS (
                SELECT 1 FROM item_template it
                WHERE s.id = it.spellid_1 and s.EffectBasePoints3!=-1 and s.EffectBasePoints3!=0 and it.class=0 and it.subclass=2
            );
    '''
    instance.execute_multi_sqls(sql)

# 生成蓝宝石、紫宝石的强化+1 -> +5的 item_template、gemproperties、spellitemenchantment和item_up 信息
def gen_jewel_update(instance, rate:int):
    item_template_sqls = []
    item_up_sqls = []

    new_entry_ofs_item_template = instance.get_max_column_in_table(column='entry', table='item_template') + 1
    new_entry_ofs_GemProperties = instance.get_max_column_in_table(column='id', table='GemProperties') + 1
    new_entry_ofs_spellitemenchantment = instance.get_max_column_in_table(column='id', table='spellitemenchantment') + 1

    def _gen_jewel_update(quality, max_up_cnt):
        nonlocal new_entry_ofs_item_template
        nonlocal new_entry_ofs_GemProperties
        nonlocal new_entry_ofs_spellitemenchantment

        # 蓝宝石
        x = 0
        for entry in instance.get_entry_of_jewel_needs_updated(quality):
            x += 1
            old_entry_spellitemenchantment = entry[2]
            old_entry_GemProperties = entry[1]
            old_entry_item_template = entry[0]

            old_entry_sp = old_entry_spellitemenchantment
            old_entry_ge = old_entry_GemProperties
            old_entry_it = old_entry_item_template

            last_result_sp = ()
            last_result_ge = ()
            last_result_it = ()

            for i in range(max_up_cnt):
                new_entry_sp = new_entry_ofs_spellitemenchantment + i
                new_entry_ge = new_entry_ofs_GemProperties + i
                new_entry_it = new_entry_ofs_item_template + i

                mod_sp = [
                    ['minAmount1',rate,'multi'],['maxAmount1',rate,'multi'],
                    ['minAmount2',rate,'multi'],['maxAmount2',rate,'multi'],
                    ['minAmount3',rate,'multi'],['maxAmount3',rate,'multi'],
                    ['sRefName4',rate,'digit_in_str_multi']
                ]
                last_result_sp = instance.copy_item(old_entry_sp, new_entry_sp, modify=mod_sp, last_result=last_result_sp, table='spellitemenchantment', primary_key='id', gen_sql_mode=True)

                mod_ge = [['SpellItemEnchantmentRef',new_entry_sp]]
                last_result_ge = instance.copy_item(old_entry_ge, new_entry_ge, modify=mod_ge, last_result=last_result_ge, table='GemProperties', primary_key='id', gen_sql_mode=True)

                mod_it = [['GemProperties',new_entry_ge],['name',f'+{i+1}','add_update_suffix' if i else 'plus']]
                last_result_it = instance.copy_item(old_entry_it, new_entry_it, modify=mod_it, last_result=last_result_it, table='item_template', primary_key='entry', gen_sql_mode=True)
                item_template_sqls.append(last_result_it[0])

                sql = instance.update_tbl_item_up(old_entry_it, old_entry_item_template, new_entry_it, gen_sql_mode=True)
                item_up_sqls.append(sql)

                old_entry_sp = new_entry_sp
                old_entry_ge = new_entry_ge
                old_entry_it = new_entry_it

            new_entry_ofs_spellitemenchantment += max_up_cnt
            new_entry_ofs_GemProperties += max_up_cnt
            new_entry_ofs_item_template += max_up_cnt

            # for sql in instance._sqls:
            #     print(sql)
            if x % 5 == 0:
                print('---已完成',x,f'{"蓝色" if quality==2 else "紫色"}宝石---')

    # 蓝色宝石(2), 最多强化到+3
    _gen_jewel_update(2, 3)
    # 紫色宝石(3), 最多强化到+5
    _gen_jewel_update(3, 5)

    instance.gen_sqlfile_from_sqls('item_template', item_template_sqls)
    instance.gen_sqlfile_from_sqls('item_up', item_up_sqls)
    instance.gen_sqlfile_from_sqls('all', instance._sqls)

    # instance.execute_multi_sqls(instance._sqls)

# 删除 数据库中所有 强化蓝宝石、强化紫宝石的信息： item_template、gemproperties、spellitemenchantment和item_up
# linux端只用删除item_template和item_up 相关内容，因为不做开发环境不导入的话就没有另外两个表的数据
def del_update_jewel_dbinfo(instance):
    sql = '''
        delete s from spellitemenchantment s
        LEFT JOIN GemProperties g ON s.id = g.SpellItemEnchantmentRef
        LEFT JOIN item_template i ON g.id = i.GemProperties
        WHERE i.class = 3 AND i.Quality IN (2, 3) AND i.name LIKE "%+%";

        delete g from gemproperties g
        LEFT JOIN item_template i ON g.id = i.GemProperties
        WHERE i.class = 3 AND i.Quality IN (2, 3) AND i.name LIKE "%+%";

        delete u from item_up u
        LEFT JOIN item_template i ON i.entry = u.upid
        WHERE i.class = 3 AND i.Quality IN (2, 3) AND i.name LIKE "%+%";

        delete i from item_template i
        WHERE i.class = 3 AND i.Quality IN (2, 3) AND i.name LIKE "%+%";
    '''
    instance.execute_multi_sqls(sql)

if __name__ == "__main__":
    debug = True
    instance = Mysql()

    # 合成宝石
    # instance.make_merge_jewel()

    # 汉化 item_template
    # instance.item_template_localeZH_1()
    # instance.item_template_localeZH_2()

    # 生成蓝装、紫装的强化+1 -> +5的 item_template和item_up 信息
    # gen_item_update_v1(instance)
    # gen_item_update_v2(instance)

    # 取消副本进入限制(成就、任务、物品)
    # remove_dungeon_requirements(instance)

    # 去掉装备和武器的唯一属性
    # remove_unique_attr_on_equip(instance)
    
    # 5倍率 放大 卷轴效果
    # multi_effect_on_scroll(instance, 5)

    # 25倍率 放大 卷轴效果
    # multi_effect_on_potion(instance, 25)

    debug = False

    # 删除强化蓝宝石、黄宝石信息
    # del_update_jewel_dbinfo(instance)

    # 生成蓝宝石、紫宝石的强化+1 -> +5的 item_template、gemproperties、spellitemenchantment和item_up 信息
    # gen_jewel_update(instance, 2)

    # instance.save_sql('item_update')

    # instance.gen_item_csv()