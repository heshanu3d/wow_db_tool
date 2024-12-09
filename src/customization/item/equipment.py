class Helper:
    def __init__(self, instance):
        self._instance = instance

# {id : upid, ...}
# @db_operation_decorator
# def get_item_up_dict(self):
#     self._cursor.execute(f'select id,upid from item_up;')
#     columns = self._cursor.fetchall()
#     item_up = {}
#     for column in columns:
#         item_up[column[0]] = column[1]
#     return item_up

# verification success and delete upper function
# {id : upid, ...}
def get_item_up_dict(instance):
    sql = f'select id,upid from item_up;'
    columns = instance.execute_sql_with_retval(sql)
    if columns is None:
        print(f'sql execute failed:\n    {sql}')
        return

    item_up = {}
    for column in columns:
        item_up[column[0]] = column[1]
    return item_up

def multi_attr_value_in_item_template(instance, entry, stat_rate=2, dmg_rate=1.4, gen_sql_mode=False):
    sql = f'''
    UPDATE item_template SET stat_value1=stat_value1*{stat_rate},stat_value2=stat_value2*{stat_rate},stat_value3=stat_value3*{stat_rate},stat_value4=stat_value4*{stat_rate},stat_value5=stat_value5*{stat_rate},stat_value6=stat_value6*{stat_rate},stat_value7=stat_value7*{stat_rate},stat_value8=stat_value8*{stat_rate},stat_value9=stat_value9*{stat_rate},stat_value10=stat_value10*{stat_rate},dmg_min1=dmg_min1*{dmg_rate},dmg_max1=dmg_max1*{dmg_rate} WHERE entry={entry};
    '''
    if not gen_sql_mode:
        instance.execute_multi_sqls(sql)
    else:
        instance._sqls.append(f'{sql}\n')

def update_tbl_item_up(instance, id, id1, new_entry, gen_sql_mode=False):
    # id, id1, id2, amount, amount1, amount2, upid
    sql = f'insert into item_up(id,id1,id2,amount,amount1,amount2,upid) values({id},{id1},0,1,1,0,{new_entry});'
    if not gen_sql_mode:
        instance.execute_multi_sqls(sql)
    else:
        instance._sqls.append(f'{sql}\n')
    return sql

# 1156， 90000
def add_update_item(instance, old_entry, new_entry_ofs, max_up_cnt, gen_sql_mode=False):
    for i in range(max_up_cnt):
        new_entry = new_entry_ofs + i
        instance.copy_item(old_entry, new_entry, gen_sql_mode=gen_sql_mode)
        multi_attr_value_in_item_template(instance, new_entry, gen_sql_mode=gen_sql_mode)
        update_tbl_item_up(instance, old_entry, old_entry, new_entry, gen_sql_mode=gen_sql_mode)
        old_entry = new_entry
    return new_entry_ofs + max_up_cnt

def gen_add_update_item_sql(instance, old_entry, new_entry_ofs, max_up_cnt):
    add_update_item(instance, old_entry, new_entry_ofs, max_up_cnt, gen_sql_mode=True)

# 'select entry,name from item_template where entry>90000 and not name like "%+%";'
def fix_upitem_name(instance):
    item_up = get_item_up_dict(instance)

    for idx, id in enumerate(instance.get_origin_update_item_id()):
        upid = id
        lvl = 0
        sqls = ''
        while upid in item_up.keys():
            upid = item_up[upid]
            lvl += 1
            sqls += f'update item_template set name=concat(name,"+{lvl}") where entry={upid};'
        instance.execute_multi_sqls(sqls)
        if idx % 100 == 99:
            print(__name__, f'execute {idx} items')
# 修改合成公式为 升级物品（+N）+原始物品 = 升级物品(+ N+1)
def modify_upitem_id1(instance):
    item_up = get_item_up_dict(instance)
    sqls = ''
    for idx, id in enumerate(instance.get_origin_update_item_id()):
        upid = id
        while upid in item_up.keys():
            if id != upid:
                sqls += f'update item_up set id1={id} where id={upid};\n'
            upid = item_up[upid]
        # instance.execute_multi_sqls(sqls)
        if idx % 100 == 99:
            print('modify_upitem_id1', f'execute {idx} items')
    print(sqls)
    print(len(sqls.split('\n')))
    instance.execute_multi_sqls(sqls)

# 去掉装备和武器的唯一属性
def remove_unique_attr_on_equip(instance):
    sql = 'update item_template set maxcount=0 where class in (2,4) and maxcount=1;'
    instance.execute_multi_sqls(sql)

# 生成蓝装、紫装的强化+1 -> +5的 item_template和item_up 信息
def gen_item_update_v1(instance):
    _debug = instance.debug
    instance.debug = False
    new_entry_ofs = instance.get_max_column_in_table() + 1
    # 蓝装最多强化到+3
    for old_entry in instance.get_equipment_entry_by_quality(3):
        new_entry_ofs = add_update_item(instance, old_entry, new_entry_ofs, 3)
    # 紫装最多强化到+5
    for old_entry in instance.get_equipment_entry_by_quality(4):
        new_entry_ofs = add_update_item(instance, old_entry, new_entry_ofs, 5)
    
    # 修复强化装备的名字: 原始名字->原始名字+强化等级， 如：豪华珠宝戒指+1，豪华珠宝戒指+2，豪华珠宝戒指+3，etc...
    fix_upitem_name(instance)
    instance.debug = _debug
    instance.gen_item_csv()

    modify_upitem_id1(instance)

# 生成蓝装、紫装的强化+1 -> +5的 item_template和item_up 信息
def gen_item_update_v2(instance):
    _debug = instance.debug
    instance.debug = False
    new_entry_ofs = instance.get_max_column_in_table() + 1
    # 蓝装最多强化到+3
    for old_entry in instance.get_equipment_entry_by_quality(3):
        new_entry_ofs = gen_add_update_item_sql(instance, old_entry, new_entry_ofs, 3)
    # 紫装最多强化到+5
    for old_entry in instance.get_equipment_entry_by_quality(4):
        new_entry_ofs = gen_add_update_item_sql(instance, old_entry, new_entry_ofs, 5)

    instance.debug = _debug

def customize(instance):
    print(f'{__name__:<45}start to costomize!')
    # 去掉装备和武器的唯一属性
    # remove_unique_attr_on_equip(instance)

    # 生成蓝装、紫装的强化+1 -> +5的 item_template和item_up 信息
    # gen_item_update_v1(instance)
    # gen_item_update_v2(instance)

    helper = Helper(instance)