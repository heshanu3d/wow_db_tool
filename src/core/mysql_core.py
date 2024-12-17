import mysql.connector, csv, time, re, copy, tabulate
from mysql.connector import Error
from functools import wraps

fast_select_f = open('tmp.txt', 'a', encoding='utf-8')

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
        self.debug = True
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
            if delta_time > 0 and self.debug:
                print(f'{func.__name__} 耗时 {delta_time}秒')
            return ret
        return wrapper

    @db_operation_decorator
    def get_column_names_and_cnt(self, table):
        self._cursor.execute(f'SHOW COLUMNS FROM {table}')
        columns = self._cursor.fetchall()
        column_names = [column[0] for column in columns]
        return column_names

    def conv_key_2_idx(self, options:list, column_names:list):
        column_names_dict = {item.lower(): idx for idx, item in enumerate(column_names)}
        for opt in options:
            col = opt[0].lower()
            val = opt[1]
            if col in column_names_dict.keys():
                opt[0] = column_names_dict[col]

    def option_op(self, results:list, options:list=[]):
        if len(options) == 0:
            return

        null_op_suffixs = ['级','秒']
        null_op_suffixs_regex = {'|'.join(null_op_suffixs)}

        for opt in options:
            if len(opt) == 2:
                results[opt[0]] = opt[1]
            elif len(opt) == 3:
                if opt[2].startswith('plus'):
                    results[opt[0]] += opt[1]
                elif opt[2].startswith('multi'):
                    results[opt[0]] *= opt[1]
                elif opt[2].startswith('div'):
                    results[opt[0]] /= opt[1]
                elif opt[2].startswith('compo_multi'):
                    results[opt[0]] = (results[opt[0]] + 1) * opt[1] - 1
                elif opt[2].startswith('compo_div'):
                    results[opt[0]] = (results[opt[0]] + 1) / opt[1] - 1
                elif opt[2].startswith('add_update_suffix'):
                    results[opt[0]] = re.sub(r"\+(\d+)", "{}".format(opt[1]), results[opt[0]])
                elif opt[2].startswith('digit_in_str'):
                    idx = len('digit_in_str')
                    def str_op(match):
                        if match.group(3) in null_op_suffixs:
                            return match.group(0)
                        else:
                            if opt[2][idx:] == '_multi':
                                return str(int(int(match.group(1)) * opt[1]))
                            elif opt[2][idx:] == '_div':
                                return str(int(int(match.group(1)) / opt[1]))
                    results[opt[0]] = re.sub(f'(\d+)(\.\d+)?([{null_op_suffixs_regex}]?)', str_op, results[opt[0]])
                    
    @db_operation_decorator
    def update_item(self, entry, options:list=[], table:str='', primary_key:str='', gen_sql_mode=False):
        _options = copy.deepcopy(options)

        column_names = [opt[0] for opt in _options]
        query_sql = f'SELECT {", ".join(column_names)} FROM {table} WHERE {primary_key}={entry};'
        # print(query_sql)
        self._cursor.execute(query_sql)
        results = self._cursor.fetchone()

        self.conv_key_2_idx(_options, column_names)

        _results = list(results)
        self.option_op(_results, _options)

        column_values = _results
        set_parts = []
        for name, value in zip(column_names, column_values):
            if isinstance(value, str):
                set_parts.append(f"{name}='{value}'")
            else:
                set_parts.append(f"{name}={value}")
        set_assign = ", ".join(set_parts)

        update_sql = f"UPDATE {table} SET {set_assign} WHERE {primary_key}={entry};"

        if gen_sql_mode:
            self._sqls.append(update_sql)
        else:
            self._cursor.execute(update_sql)

        return update_sql

    @db_operation_decorator
    def _copy_item(self, origin_entry, new_entry, sql, options, last_result, table='item_template', primary_key='entry', gen_sql_mode=False):
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
            self.option_op(_result, options)
            # if len(options) > 0:
                # for mod in options:
                #     if len(mod) == 2:
                #         _result[mod[0]] = mod[1]
                #     elif len(mod) == 3:
                #         if mod[2].startswith('plus'):
                #             _result[mod[0]] += mod[1]
                #         elif mod[2].startswith('multi'):
                #             _result[mod[0]] *= mod[1]
                #         elif mod[2].startswith('compo_multi'):
                #             _result[mod[0]] = (_result[mod[0]] + 1) * mod[1] - 1
                #         elif mod[2].startswith('add_update_suffix'):
                #             _result[mod[0]] = re.sub(r"\+(\d+)", "{}".format(mod[1]), _result[mod[0]])
                #         elif mod[2].startswith('digit_in_str_multi'):
                #             def multiply_digits(match):
                #                 return str(int(match.group(0)) * mod[1])
                #             _result[mod[0]] = re.sub(r'\d+', multiply_digits, _result[mod[0]])

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

    # option = [['id',3], ['type',5]] 表示把复制的结果集里的id列的值改为3，type列的值改为5
    def copy_item(self, origin_entry, new_entry, options:list=[], last_result:tuple=(), table='item_template', primary_key='entry', gen_sql_mode=False):
        if len(last_result) == 0:
            column_names = self.get_column_names_and_cnt(table)
        else:
            column_names = last_result[2]
        s = '('+','.join(column_names)+')'
        c = len(column_names)

        options.append([primary_key, new_entry])
        self.conv_key_2_idx(options, column_names)
        # column_names_dict = {item.lower(): idx for idx, item in enumerate(column_names)}
        # for opt in options:
        #     col = opt[0].lower()
        #     val = opt[1]
        #     if col in column_names_dict.keys():
        #         opt[0] = column_names_dict[col]
        

        sql_1 = f'INSERT INTO {table} {s}'
        sql_2 = 'VALUES (' + ','.join(['%s' for i in range(c)]) + ');'
        sql_insert = f'{sql_1} {sql_2}'

        _sql, _vals = self._copy_item(origin_entry, new_entry, sql_insert, options, last_result, table, primary_key, gen_sql_mode=gen_sql_mode)
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

    @db_operation_decorator
    def execute_sql_with_retval_with_col_names(self, sql):
        self._cursor.execute(sql.strip())
        results = self._cursor.fetchall()
        column_names = [i[0] for i in self._cursor.description]

        return [column_names] + results

    @db_operation_decorator
    def execute_sql_with_retval(self, sql):
        self._cursor.execute(sql.strip())
        results = self._cursor.fetchall()

        return results

    def fast_select(self, sql, tablefmt='markdown'):
        headers = 'firstrow'
        results = self.execute_sql_with_retval_with_col_names(sql)
        if results is None:
            headers=''
            tablefmt='grid'
            results = [['Error']]

        tablefmts = ['plain', 'grid', 'fancy_grid', 'pipe', 'html', 'latex', 'markdown', 'all']
        if not tablefmt in tablefmts:
            print('in function call instace.fast_select(sql, tablefmt):')
            print(f'    tablefmt could be one of {tablefmts}')
            return
        if tablefmt == 'all':
            for fmt in tablefmts[:-1]:
                output = tabulate.tabulate(results, headers=headers, tablefmt=fmt)
                output += '\n'
                fast_select_f.writelines(output)
                print(output)
        else:
            output = tabulate.tabulate(results, headers=headers, tablefmt=tablefmt)
            output += '\n'
            fast_select_f.writelines(output)
            print(output)

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

    @db_operation_decorator
    def get_max_column_in_table(self, column='entry', table='item_template'):
        self._cursor.execute(f'select max({column}) from {table};')
        columns = self._cursor.fetchall()
        return columns[0][0]

    @db_operation_decorator
    def get_origin_update_item_id(self):
        self._cursor.execute(f'select id from item_up where id < 60000;')
        columns = self._cursor.fetchall()
        return [column[0] for column in columns]

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
    
    def backup_table(self, table):
        sql = f'CREATE TABLE {table}_b AS SELECT * FROM {table};'
        self.execute_multi_sqls(sql)
    def clear_table_content(self, table):
        sql = f'DELETE FROM {table};'
        self.execute_multi_sqls(sql)