
def copy(instance, old_entry, new_entry, table, primary_key):
    column_names = instance.get_column_names_and_cnt(table)
    s = '('+','.join(column_names)+')'
    c = len(column_names)

    sql_1 = f"INSERT INTO {table} {s} "
    sql_1 = sql_1.replace(',rank,', ',`rank`,')

    query_select = f'SELECT * FROM {table} WHERE {primary_key} = {old_entry};'
    result = instance.execute_sql_with_retval(query_select)
    if result:
        row = list(result[0])
        row[0] = new_entry
        for i in range(len(row)):
            if row[i] is None:
                row[i] = 'NULL'
        row = tuple(row)
        sql = f'{sql_1} VALUES{(*row,)};\n'
        # print(sql)
        instance.execute_multi_sqls(sql)

def add_creature_template(instance):
    # copy(instance, 152, 20000, 'creature_template', 'entry')
    # copy(instance, 79950, 310000, 'creature', 'guid')
    sqls = '''
        update creature set id=20000,
        position_x=-8902.506,position_y=-114.446,position_z=81.86
        where guid = 310000;
    '''
    instance.execute_multi_sqls(sqls)

def customize(instance):
    print(f'{__name__:<45}start to customize!')

    # add_creature_template(instance, 152, 20000, 'creature_template', 'entry')
    add_creature_template(instance);

    # helper = Helper(instance)

    # npc_vendor