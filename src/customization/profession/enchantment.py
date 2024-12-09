class Helper:
    def __init__(self, instance):
        self._instance = instance
    # 查找跟附魔相关的spell，方便一键生成学习脚本
    def enchant_spell_finder(self):
        sql = """
            select s.id,s.SpellName4 from spell s
            where s.SpellIconID in (241, 578) and (s.spellname4 like '附魔' or s.spellname4 like '附魔%-%');
        """
        self._instance.fast_select(sql)
    # 查找附魔spell的数值都存在哪，并找到修改方法
    def enchant_spell_multi(self):
        sql = """
            select s.id,s.SpellName4,s.Effect1,s.EffectMiscValue1,sRefName4,minAmount1,maxAmount1,minAmount2,maxAmount2,minAmount3,maxAmount3 from spell s
            left join spellitemenchantment sp on s.EffectMiscValue1=sp.id
            where s.SpellIconID in (241, 578) and s.spellname4 like '附魔%-%' and minAmount1!=0 and minAmount1!=-1;
        """
        # sql = """
        #     select s.id,s.SpellName4,s.Effect1,s.EffectMiscValue1,sRefName4,minAmount1,maxAmount1,minAmount2,maxAmount2,minAmount3,maxAmount3 from spell s
        #     left join spellitemenchantment sp on s.EffectMiscValue1=sp.id
        #     where s.SpellIconID in (241, 578) and s.spellname4 like '附魔%-%' and minAmount1!=0 and minAmount1!=-1 and s.id in (60691,20016);
        # """
        self._instance.fast_select(sql)

def muiti_enchantment_spell(instance, rate):
    sql = '''
        select s.id,s.EffectMiscValue1 from spell s
        left join spellitemenchantment sp on s.EffectMiscValue1=sp.id
        where s.SpellIconID in (241, 578) and s.spellname4 like '附魔%-%' and minAmount1!=0 and minAmount1!=-1;
        # where s.SpellIconID in (241, 578) and s.spellname4 like '附魔%-%' and minAmount1!=0 and minAmount1!=-1 and s.id in (60691,20016);
    '''

    options_spim = [
        ['minAmount1',rate,'multi'],['maxAmount1',rate,'multi'],
        ['minAmount2',rate,'multi'],['maxAmount2',rate,'multi'],
        ['minAmount3',rate,'multi'],['maxAmount3',rate,'multi'],
        ['sRefName4',rate,'digit_in_str_multi']
    ]
    options_sp = [
        ['SpellDescription4',rate,'digit_in_str_multi']
    ]

    gen_sqls = []
    results = instance.execute_sql_with_retval(sql)
    if results is None:
        print(f'sql execute failed:\n    {sql}')
        return

    for ids in results:
        id_spell = ids[0]
        id_EffectMisc = ids[1]
        gen_sqls.append(instance.update_item(id_EffectMisc, options=options_spim, table='spellitemenchantment', primary_key='id', gen_sql_mode=True))
        gen_sqls.append(instance.update_item(id_spell,      options=options_sp,   table='spell',                primary_key='id', gen_sql_mode=True))
    
    instance.execute_multi_sqls(gen_sqls)
    # for sql in gen_sqls:
    #     print(sql)
    print(f"{__name__:<45}generate dbc from tbl spell、spellitemenchantment and replace the corresponding server's dbc file and client's mpq file")

def customize(instance):
    print(f'{__name__:<45}start to costomize!')
    
    helper = Helper(instance)
    # 查找跟附魔相关的spell，方便一键生成学习脚本
    # helper.enchant_spell_finder()


    # 20倍附魔效果
    # muiti_enchantment_spell(instance, 20)

    # 查看当前所有附魔技能的数值
    # helper.enchant_spell_multi()

    # revert 20倍附魔效果
    # muiti_enchantment_spell(instance, 1/20)
    # helper.enchant_spell_multi()