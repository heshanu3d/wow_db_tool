from ..base import spell

cond = {
    # 研磨、选矿、采矿、熔炼、剥皮、采药、分解、全部瞬间完成，5秒钓鱼
    '研磨' : "s.id=51005",
    '选矿' : "s.id=31252",
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
    '研磨'     : '0',
    '选矿'     : '0',
    '采矿'     : '0',
    '熔炼'     : '0',
    '剥皮'     : '0',
    '分解'     : '0',
    '采集草药' : '0',
}
mod_gcd_time_skills = {
    '研磨'     : 0,
    '选矿'     : 0,
    '采矿'     : 0,
    '熔炼'     : 0,
    '剥皮'     : 0,
    '分解'     : 0,
    '采集草药' : 0,
}

mod_duration_skills = {
    '钓鱼' : '5s',
}

#  获得所有专业技能
def get_profession_spell(instance):
    profession_skillID = {
        '锻造' : 164,
        '制革' : 165,
        '炼金' : 171,
        '裁缝' : 197,
        '工程' : 202,
        '珠宝' : 755,
        '铭文' : 773,
        '附魔' : 333,

        '采矿' : 186,
        '草药' : 182,

        '急救' : 129,
        '烹饪' : 185,
        # '钓鱼' : 356,
    }
    spells = []
    for k, v in profession_skillID.items():
        # instance.fast_select(f'''
        #     select s.id,s.SpellName4 as name,s.SpellRank4 as lvl,s.Effect1 as e1,s.Effect2 as e2,s.Effect3 as e3,s.EffectBasePoints1 as base1,s.EffectBasePoints2 as base2,s.EffectBasePoints3 as base3
        #     ,s.effectapplyauraname1 as aura1,s.effectapplyauraname2 as aura2,s.effectapplyauraname3 as aura3
        #     ,EffectAmplitude1 as amp1,EffectAmplitude2 as amp2
        #     ,DurationIndex dur_idx
        #     ,EffectTriggerSpell1 trig1,procchance trig_c,procflags proc_f,ProcCharges trig_t,EffectMiscValue1 as misc1
        #     ,CastingTimeIndex cast_idx,RecoveryTime cd, CategoryRecoveryTime cd2, StartRecoveryCategory gcd_c,StartRecoveryTime gcd,effectItemType1 eit,spellfamilyflags1 sff1,spellfamilyflags1 sff2,spellFamilyName sfn
        #     from skilllineability sk
        #     join spell s on s.id=sk.spellid and s.CastingTimeIndex>1 and (s.Effect1=24 or s.Effect1=53 or s.Effect1=157)
        #     where skillid={v};
        # ''')
        # 24 制作物品， 53 附魔物品， 157 宝石/铭文类制作
        # s.Effect1=24 or s.Effect1=53 or s.Effect1=157
        results = instance.execute_sql_with_retval(f'''
            select s.id,s.Effect1 as e1,s.Effect2 as e2,s.Effect3 as e3,CastingTimeIndex cast_idx
            from skilllineability sk
            join spell s on s.id=sk.spellid and s.CastingTimeIndex>1 and (s.Effect1=24 or s.Effect1=53 or s.Effect1=157)
            where skillid={v};
        ''')

        if results is None:
            print(f'sql execute failed:\n    {sql}')
            return

        for result in results:
            spells.append(result[0])

    return spells

def get_profession_spell_cond(instance):
    spells = get_profession_spell(instance)
    spells_condition = ' or '.join([f"s.id={item}" for item in spells])
    return f"({spells_condition}) and s.castingtimeindex > 1"

# 获取 所有图纸学到 的技能, eg: 图样：邪恶皮甲
def get_draft_spell(instance):
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

# 生成图纸技能sql条件 "(s.id=xxx or s.id=yyy ... s.id=zzz) and s.castingtimeindex>1"
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

    # 调整 采矿、熔炼、剥皮、采药、分解、全部瞬间完成, gcd也调整为0
    mod.mod_cast_time(mod_cast_time_skills)
    mod.mod_gcd_time(mod_gcd_time_skills)
    # 调整 钓鱼时间 30s -> 5s
    mod.mod_duration(mod_duration_skills)

    draft_spell_cond = get_draft_spell_cond(instance)
    # helper.search_with_cond(draft_spell_cond)
    # test.mod_cast_time_with_condition('250ms', draft_spell_cond)
    # test.mod_cast_time_with_condition('30s', draft_spell_cond)
    # 调整所有图纸 学到的技能施法时间 为 250ms
    mod.mod_cast_time_with_condition('250ms', draft_spell_cond)

    # 包含了图纸学到的技能，但主要是针对技能师学到的技能
    profession_spell_cond = get_profession_spell_cond(instance)
    # helper.search_with_cond(profession_spell_cond)
    # test.mod_cast_time_with_condition('250ms', profession_spell_cond)
    # test.mod_cast_time_with_condition('30s', profession_spell_cond)
    # 调整所有专业技能施法时间 为 250ms
    mod.mod_cast_time_with_condition('250ms', profession_spell_cond)