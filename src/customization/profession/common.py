from ..base import spell

cond = {
    # 采矿、熔炼、剥皮、采药、分解、全部瞬间完成，5秒钓鱼
    '采矿' : "s.spellname4='采矿' and Effect1=33 and Effect2=118",
    '熔炼' : "s.spellname4 like'熔炼%' and effect1=24",
    '剥皮' : "s.spellname4='剥皮' and Effect1=95 and Effect2=118",
    '采集草药' : "s.spellname4='采集草药' and Effect1=33 and Effect2=118",
    '分解' : "s.spellname4='分解'",
    '钓鱼' : "s.spellname4='钓鱼' and Effect1=50 and Effect2=118",
}

item_cond = {
    '图样' : "name like'%图样%' ",
    '图鉴' : "name like'%图鉴%' ",
    '食谱' : "name like'%食谱%' ",
    '公式：' : "name like'%公式：%' ",
    '配方：' : "name like'%配方：%' ",
    '设计图' : "name like'%设计图%' ",
    '结构图' : "name like'%结构图%' ",
}

all_spellnames = cond.keys()

mod_cast_time_skills = {
    '采矿'    : '0',
    '熔炼'    : '0',
    '剥皮'    : '0',
    '分解'    : '0',
    '采集草药' : '0',
}

mod_duration_skills = {
    '钓鱼' : '5s',
}

# 获取 所有图纸学到 的技能, eg: 图样：邪恶皮甲
def get_draft_spell(instance):
    # sql = f'''
    #         select s.id,s.spellname4,s.castingtimeindex,s.effecttriggerspell1,t.castingtimeindex from spell s
    #         join spell t on (t.id=s.effecttriggerspell1 or t.id=s.effecttriggerspell2 or t.id=s.effecttriggerspell3)
    #         where ({item_cond['图样']});
    # '''

    # sql = f'''
    #             select entry, name, spellid_1,spelltrigger_1,spellid_2,spelltrigger_2 from item_template
    #             where (spellid_1=483 and spelltrigger_2=6);
    #     '''
    # instance.fast_select(sql)
    # results = instance.execute_sql_with_retval(sql)
    # spells = []
    # for result in results:
    #     spells.append(result[1])
    # print(spells, len(spells))
    # return

    spells = []
    for i in ['图样', '图鉴', '设计图', '结构图', '公式：', '食谱', '配方：']:
        sql = f'''
                select entry, name, spellid_1,spelltrigger_1,spellid_2,spelltrigger_2 from item_template
                where ({item_cond[i]} and spellid_1=483 and spelltrigger_2=6);
        '''
        # instance.fast_select(sql)
        results = instance.execute_sql_with_retval(sql)
        if results is None:
            print(f'sql execute failed:\n    {sql}')
            return

        for result in results:
            spells.append(result[4])
    # print(spells, len(spells))
    return spells

def get_draft_spell_cond(instance):
    spells = get_draft_spell(instance)
    spells_condition = ' or '.join([f"s.id={item}" for item in spells])
    return f"({spells_condition}) and s.castingtimeindex > 1"

def customize(instance):
    print(f'{__name__:<45}start to customize!')
    Helper = spell.Helper
    Mod = spell.Mod
    Test = spell.Test

    helper = Helper(instance, cond)
    mod = Mod(instance, cond)
    test = Test(helper, mod)

    # test.mod_cast_time({'采集草药' : '5000ms'})
    # test.mod_duration({'钓鱼' : '30s'})
    # helper.search(all_spellnames)

    # 调整 采矿、熔炼、剥皮、采药、分解、全部瞬间完成
    mod.mod_cast_time(mod_cast_time_skills)
    # 调整 钓鱼时间 30s -> 5s
    mod.mod_duration(mod_duration_skills)

    draft_spell_cond = get_draft_spell_cond(instance)
    # helper.search_with_cond(draft_spell_cond)
    # test.mod_cast_time_with_condition('250ms', draft_spell_cond)
    # test.mod_cast_time_with_condition('30s', draft_spell_cond)
    # 调整所有图纸 学到的技能施法时间 为 250ms
    mod.mod_cast_time_with_condition('250ms', draft_spell_cond)