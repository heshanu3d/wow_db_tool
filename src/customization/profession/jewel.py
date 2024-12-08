class Helper:
    def __init__(self, instance):
        self._instance = instance

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

        opt_sp = [
            ['minAmount1',rate,'multi'],['maxAmount1',rate,'multi'],
            ['minAmount2',rate,'multi'],['maxAmount2',rate,'multi'],
            ['minAmount3',rate,'multi'],['maxAmount3',rate,'multi'],
            ['sRefName4',rate,'digit_in_str_multi']
        ]

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

                last_result_sp = instance.copy_item(old_entry_sp, new_entry_sp, options=opt_sp, last_result=last_result_sp, table='spellitemenchantment', primary_key='id', gen_sql_mode=True)

                opt_ge = [['SpellItemEnchantmentRef',new_entry_sp]]
                last_result_ge = instance.copy_item(old_entry_ge, new_entry_ge, options=opt_ge, last_result=last_result_ge, table='GemProperties', primary_key='id', gen_sql_mode=True)

                opt_it = [['GemProperties',new_entry_ge],['name',f'+{i+1}','add_update_suffix' if i else 'plus']]
                last_result_it = instance.copy_item(old_entry_it, new_entry_it, options=opt_it, last_result=last_result_it, table='item_template', primary_key='entry', gen_sql_mode=True)
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


def customize(instance):
    print(f'{__name__:<45}start to costomize!')
    # 删除强化蓝宝石、黄宝石信息
    # del_update_jewel_dbinfo(instance)

    # 生成蓝宝石、紫宝石的强化+1 -> +5的 item_template、gemproperties、spellitemenchantment和item_up 信息
    # gen_jewel_update(instance, 2)

    helper = Helper(instance)