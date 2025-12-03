from ..base import spell

# 速效毒药 表关联关系
#  8700(effect=36 LEARN_SPELL) ->  8681(effect=24 CREATE_ITEM) -> 6947(item_template.id  spellid_1) ->  8679[modify duration in spell_effect_mod](effect=54, misc1) -> 323(SpellItemEnchantment.dbc effect_arg1) ->  8680
#  8701(effect=36 LEARN_SPELL) ->  8687(effect=24 CREATE_ITEM) -> 6949(item_template.id  spellid_1) ->  8686[modify duration in spell_effect_mod](effect=54, misc1) -> 324(SpellItemEnchantment.dbc effect_arg1) ->  8685
#  8810(effect=36 LEARN_SPELL) ->  8691(effect=24 CREATE_ITEM) -> 6950(item_template.id  spellid_1) ->  8688[modify duration in spell_effect_mod](effect=54, misc1) -> 325(SpellItemEnchantment.dbc effect_arg1) ->  8689
# 11344(effect=36 LEARN_SPELL) -> 11341(effect=24 CREATE_ITEM) -> 8926(item_template.id  spellid_1) -> 11338[modify duration in spell_effect_mod](effect=54, misc1) -> 623(SpellItemEnchantment.dbc effect_arg1) -> 11335
# 11345(effect=36 LEARN_SPELL) -> 11342(effect=24 CREATE_ITEM) -> 8927(item_template.id  spellid_1) -> 11339[modify duration in spell_effect_mod](effect=54, misc1) -> 624(SpellItemEnchantment.dbc effect_arg1) -> 11336
# 11346(effect=36 LEARN_SPELL) -> 11343(effect=24 CREATE_ITEM) -> 8928(item_template.id  spellid_1) -> 11340[modify duration in spell_effect_mod](effect=54, misc1) -> 625(SpellItemEnchantment.dbc effect_arg1) -> 11337

cond = {
    # 'test' : 's.id in (674,1424,30798)',
    # 'test1' : 's.id in (8680, 8685, 8689,11335,11336,11337)',
    # '双武器'   : "s.spellname4='双武器'",
    '速效毒药_伤害'     : "s.spellname4 like'速效毒药%'        and s.spellrank4 like '等级%' and spellfamilyname=8 and effect1=2",
    '速效毒药_几率'     : "s.spellname4 like'速效毒药%'        and s.spellrank4 like '等级%' and spellfamilyname=8 and effect1=54",
    '强化速效毒药'      : "s.spellname4='强化毒药'             and s.spellrank4 like '等级%'",
    # '暗影之舞' : "s.spellname4='暗影之舞'",
    # '毒刃'     : "s.spellname4='毒刃'        and s.id=5938",
    # '佯攻'     : "s.spellname4='佯攻'        and s.spellrank4 like '等级%'",
    # '刺骨'     : "s.spellname4='刺骨'        and s.spellrank4 like '等级%' and s.EffectBasePoints1<500",
    # '闪避'     : "s.spellname4='闪避'        and s.spellrank4 like '等级%' and s.spelldescription4 like '%使你的躲闪几率%'",
    # '剑刃乱舞' : "s.spellname4='剑刃乱舞'    and s.spellrank4='' and s.id<15000",
    # '暗影步'   : "s.spellname4='暗影步'      and s.spelldescription4 like '%移动速度提高%' and s.EffectBasePoints1=0 and s.EffectBasePoints2=0",
    # '鬼魅攻击' : "s.spellname4='鬼魅攻击'    and s.spelldescription4 like '%如果装备匕首则造成%'",
    # '刀扇'     : "s.spellname4='刀扇'        and s.spelldescription4 like '%若使用其它武器则%' and s.id<55000",
    # '偷袭'     : "s.spellname4='偷袭'        and s.EffectBasePoints1=-1",
    # '火球术'   : "s.spellname4='火球术'      and s.spellrank4 like '等级%' and startrecoverytime>0",
    # '腐蚀术'   : "s.spellname4='腐蚀术'      and s.spellrank4 like '等级%' and startrecoverytime>0",
    # '痛苦诅咒' : "s.spellname4='痛苦诅咒'    and s.spellrank4 like '等级%' and startrecoverytime>0",

    '闪电箭'   : "s.spellname4='闪电箭'     and s.spellrank4 like '等级%' and startrecoverytime>0 and ((s.id<10393 or s.id=15207 or s.id=15208) and s.id!=8246)",
    '闪电链'   : "s.spellname4='闪电链'     and s.spellrank4 like '等级%' and startrecoverytime>0",
    '闪电之盾' : "s.spellname4='闪电之盾'   and s.spellrank4 like '等级%' and startrecoverytime>0 and EffectTriggerSpell1>0 and procflags=139944",
    '地震术'   : "s.spellname4='地震术'     and s.spellrank4 like '等级%' and startrecoverytime>0",
    '烈焰震击' : "s.spellname4='烈焰震击'   and s.spellrank4 like '等级%' and startrecoverytime>0",
    '冰霜震击' : "s.spellname4='冰霜震击'   and s.spellrank4 like '等级%' and startrecoverytime>0",

    # TODO 1
    '石化武器'      : "s.spellname4='石化武器' and s.spellrank4 like '等级%' and startrecoverytime>0",
    '火舌武器'      : "s.spellname4='火舌武器' and s.spellrank4 like '等级%' and startrecoverytime>0",
    '冰封武器'      : "s.spellname4='冰封武器' and s.spellrank4 like '等级%' and startrecoverytime>0",
    '风怒武器'      : "s.spellname4='风怒武器' and s.spellrank4 like '等级%' and startrecoverytime>0",
    # get from this sql
    # '''    select s.id
    #         from spell s
    #         join (select EffectArg_1 id from spellitemenchantment ench
    #         join spell s on s.EffectMiscValue1=ench.id
    #         where (s.spellname4='风怒武器' and s.spellrank4 like '等级%' and startrecoverytime>0)) s1 on s1.id=s.id;'''
    '石化武器_效果' : "s.id in (10400,15567,15568,15569,16311,16312,16313)",
    '火舌武器_效果' : "s.id in (8026, 8028, 8029,10445,16343,16344)",
    '冰封武器_效果' : "s.id in (8034, 8037,10458,16352,16353)",
    '风怒武器_效果' : "s.id in (8233, 8236,10484,16361)",
 

    # 火焰新星图腾 机制: e1=87 召唤misc1 的creature_template ct, ct.entry=s.misc1的生物释放ct.spell_id1的技能， ct.spell_id1 触发 trig1的技能，最终trig1技能造成伤害
    '火焰新星图腾'      : "s.spellname4='火焰新星图腾' and s.spellrank4 like '等级%' and startrecoverytime>0",
    '火焰新星图腾_伤害' : "s.id in (8349, 8502, 8503,11306,11307)",
    '灼热图腾'          : "s.spellname4='灼热图腾' and s.spellrank4 like '等级%' and startrecoverytime>0",
    '灼热图腾_伤害'     : "s.id in (22048, 6350, 6351, 6352,10435,10436)",
    '大地之力图腾'      : "s.spellname4='大地之力图腾' and s.spellrank4 like '等级%' and startrecoverytime>0",
    '大地之力图腾_Buff' : "s.id in (8076, 8162, 8163, 10441,25362)",
    '地缚图腾'          : "s.spellname4='地缚图腾' and s.spellrank4 like '等级%' and startrecoverytime>0",
    '石爪图腾'          : "s.spellname4='石爪图腾' and s.spellrank4 like '等级%' and startrecoverytime>0",
    '清毒图腾'          : "s.spellname4='大地之力图腾' and s.spellrank4 like '等级%' and startrecoverytime>0",

    '次级治疗波' : "s.spellname4='次级治疗波'    and s.spellrank4 like '等级%' and startrecoverytime>0",
    '治疗波'     : "s.spellname4='治疗波'    and s.spellrank4 like '等级%' and startrecoverytime>0",
    '治疗链'     : "s.spellname4='治疗链'    and s.spellrank4 like '等级%' and startrecoverytime>0",
    '消毒术'     : "s.spellname4='消毒术'    and startrecoverytime>0 and s.id=526",
    '祛病术'     : "s.spellname4='祛病术'    and startrecoverytime>0 and s.id=2870",

    '幽魂之狼' : "s.spellname4='幽魂之狼'    and spellfamilyname=11",

    # 元素天赋
    '震荡'         : "s.spellname4='震荡'            and s.spellrank4 like '等级%'",
    '传导'         : "s.spellname4='传导'            and s.spellrank4 like '等级%'",
    '大地之握'     : "s.spellname4='大地之握'        and s.spellrank4 like '等级%'",
    '元素防护'     : "s.spellname4='元素防护'        and s.spellrank4 like '等级%'",
    '烈焰召唤'     : "s.spellname4='烈焰召唤'        and s.spellrank4 like '等级%'",
    '元素集中'     : "s.spellname4='元素集中'        and s.EffectTriggerSpell1>0",
    '回响'         : "s.spellname4='回响'            and s.spellrank4 like '等级%'",
    '雷霆召唤'     : "s.spellname4='雷霆召唤'        and s.spellrank4 like '等级%'",
    '强化火焰图腾' : "s.spellname4='强化火焰图腾'    and s.spellrank4 like '等级%'",
    '风暴之眼'     : "s.spellname4='风暴之眼'        and s.spellrank4 like '等级%'",
    '元素浩劫'     : "s.spellname4='元素浩劫'        and s.spellrank4 like '等级%' and effectapplyauraname1=52",
    '风暴来临'     : "s.spellname4='风暴来临'        and s.spellrank4 like '等级%'",
    '元素之怒'     : "s.spellname4='元素之怒'        and s.effectapplyauraname1=108",
    '闪电掌握'     : "s.spellname4='闪电掌握'        and s.spellrank4 like '等级%'",
    '元素掌握'     : "s.spellname4='元素掌握'        and s.effectbasepoints2!=0",

    # 增强天赋
    '先祖知识'     : "s.spellname4='先祖知识'        and s.spellrank4 like '等级%'",
    '盾牌专精'     : "s.spellname4='盾牌专精'        and s.spellrank4 like '等级%' and effectapplyauraname2=150",
    '守护图腾'     : "s.spellname4='守护图腾'        and s.spellrank4 like '等级%'",
    '雷鸣猛击'     : "s.spellname4='雷鸣猛击'        and s.spellrank4 like '等级%'",
    '强化幽魂之狼' : "s.spellname4='强化幽魂之狼'    and s.spellrank4 like '等级%'",
    '强化闪电之盾' : "s.spellname4='强化闪电之盾'    and s.spellrank4 like '等级%'",
    '强化图腾'     : "s.spellname4='强化图腾'        and s.spellrank4 like '等级%' and effectapplyauraname2!=0",
    '双手斧和锤'   : "s.spellname4='双手斧和锤'",
    '预知'         : "s.spellname4='预知'            and s.spellrank4 like '等级%' and effectapplyauraname1=49",
    '乱舞'         : "s.spellname4='乱舞'            and s.spellrank4 like '等级%' and effectapplyauraname1=138 and (s.id=16257 or s.id=16277 or s.id=16278 or s.id=16279 or s.id=16280) and procflags=4",
    '坚韧'         : "s.spellname4='坚韧'            and s.spellrank4 like '等级%' and (s.id=16252 or s.id=16306 or s.id=16307 or s.id=16308 or s.id=16309) and EffectMiscValue1=1",
    '强化武器图腾' : "s.spellname4='强化武器图腾'    and s.spellrank4 like '等级%'",
    '元素武器'     : "s.spellname4='元素武器'        and s.spellrank4 like '等级%' and Effect2!=0",
    '武器掌握'     : "s.spellname4='武器掌握'        and s.spellrank4 like '等级%'",
    '风暴打击'     : "s.spellname4='风暴打击'        and s.spellrank4 like '等级%' and startrecoverytime>0 and s.effect1=58",

    # 治疗天赋
    '强化治疗波'   : "s.spellname4='强化治疗波'         and s.spellrank4 like '等级%'",
    '潮汐集中'     : "s.spellname4='潮汐集中'         and s.spellrank4 like '等级%'",
    '强化复生'     : "s.spellname4='强化复生'         and s.spellrank4 like '等级%'",
    '先祖治疗'     : "s.spellname4='先祖治疗'         and s.spellrank4 like '等级%'",
    '图腾集中'     : "s.spellname4='图腾集中'         and s.spellrank4 like '等级%'",
    '自然指引'     : "s.spellname4='自然指引'         and s.spellrank4 like '等级%'",
    '治疗专注'     : "s.spellname4='治疗专注'         and s.spellrank4 like '等级%' and spellfamilyname=11",
    '图腾掌握'     : "s.spellname4='图腾掌握'                                       and spellfamilyname=11",
    '治疗之赐'     : "s.spellname4='治疗之赐'         and s.spellrank4 like '等级%'",
    '恢复图腾'     : "s.spellname4='恢复图腾'         and s.spellrank4 like '等级%'",
    '潮汐掌握'     : "s.spellname4='潮汐掌握'         and s.spellrank4 like '等级%'",
    '治疗之道'     : "s.spellname4='治疗之道'         and s.spellrank4 like '等级%'",
    '自然迅捷'     : "s.spellname4='自然迅捷'         and spellfamilyname=11",
    '净化'         : "s.spellname4='净化'             and s.spellrank4 like '等级%' and effectItemType1!=0",
    '法力之潮图腾' : "s.spellname4='法力之潮图腾'",
}

mod_dmg_skills = {
    '闪电箭'    : 1.5,
    '闪电链'    : 1.5,
    '地震术'    : 1.5,
    '烈焰震击'  : 1.5,
    '冰霜震击'  : 1.5,

    '次级治疗波': 1.5,
    '治疗波'    : 1.5,
    '治疗链'    : 1.5,

    '火焰新星图腾_伤害'  : 1.5,
    '灼热图腾_伤害'  : 1.5,

    '冰封武器_效果' : 10
}

mod_talent_dummy_skills = {
    '火舌武器_效果' : 2,
}

mod_talent_extra_attack_skills = {
    '风怒武器_效果' : 2
}

mod_talent_skills = {
    '烈焰震击'     : 2,
    '闪电之盾'     : 2,

    '石化武器_效果': 2,
    '风怒武器_效果': 2,

    '震荡'         : 10,
    '传导'         : 5,
    '大地之握'     : 3,
    '元素防护'     : 3,
    '烈焰召唤'     : 10,
    '回响'         : 3,
    '雷霆召唤'     : 2,
    '强化火焰图腾' : 2,
    # '风暴之眼'     : 2,  3点天赋已经100%触发几率了，没必要 mod
    '元素浩劫'     : 2,
    '风暴来临'     : 2,
    '元素之怒'     : 2,
    '闪电掌握'     : 1.5,
    '元素掌握'     : 1.5,

    '先祖知识'     : 10,
    '盾牌专精'     : 4,
    '守护图腾'     : 5,
    '雷鸣猛击'     : 2,
    '强化幽魂之狼' : 1.5,
    '强化闪电之盾' : 10,
    '强化图腾'     : 10,
    '预知'         : 4,
    '乱舞'         : 4,
    '坚韧'         : 4,
    '强化武器图腾' : 10,
    '元素武器'     : 10,
    '武器掌握'     : 4,
    '风暴打击'     : 3,

    '强化治疗波'   : 3,
    '潮汐集中'     : 10,
    '强化复生'     : 2.5,
    '图腾集中'     : 3,
    '自然指引'     : 3,
    '治疗专注'     : 1.5,
    '图腾掌握'     : 3,
    '治疗之赐'     : 5,
    '恢复图腾'     : 4,
    '潮汐掌握'     : 2,
    '净化'         : 5,

    '幽魂之狼'     : 3, # 千金狗！
}

mod_dot_interval_skills = {
    '烈焰震击' : 0.6,
}

mod_trigger_chance_skills = {
    '元素集中' : 2,
}

mod_duration_skills = {
    '闪电之盾' : '1800s',
}

mod_trigger_time_skills = {
    '闪电之盾' : 60,
}

mod_cooldown_time_skills = {
    "风暴打击" : 6000,
}

mod_cast_time_skills = {
    '闪电箭'   : '2500ms',
    '闪电链'   : '2000ms',
}

mod_gcd_time_skills = {
    '闪电箭'       : 200,
    '闪电链'       : 200,
    '闪电之盾'     : 200,
    '大地震击'     : 200,
    '烈焰震击'     : 200,
    '冰霜震击'     : 200,
    '次级治疗波'   : 200,
    '治疗波'       : 200,
    '治疗链'       : 200,
    '石化武器'     : 200,
    '火舌武器'     : 200,
    '冰封武器'     : 200,
    '风怒武器'     : 200,
    '火焰新星图腾' : 200,
    '灼热图腾'     : 200,
    '地缚图腾'     : 200,
    '石爪图腾'     : 200,
    '大地之力图腾' : 200,
    '清毒图腾'     : 200,
    '消毒术'       : 200,
    '祛病术'       : 200,
    '幽魂之狼'     : 200,

    '风暴打击'     : 200,
}

mod_trigger_skills = {
    '先祖治疗' : 4,
    '治疗之道' : 5,
}

mod_enchant_spell_trigger_chance_skills = {
    '风怒武器' : 2,
}

all_spellnames = cond.keys()

# 双手斧和锤
# 196:单手斧，197:双手斧，198:单手锤，199:双手锤，200:长柄武器，201:单手剑，202:双手剑，227:法杖
def mod_spell_16269(instance):
    # 使你可以使用双手斧和双手锤 -> 使你可以使用双手斧,双手锤和双手剑
    spellname = '双手斧和锤'
    description = '使你可以使用双手斧,双手锤和双手剑'
    if spellname in cond:
        results = instance.execute_sql_with_retval(spell.sql_query('spell_template', spell.cond_conv2server(cond[spellname])))
        entry_condition_str = ' or '.join([f"s.entry={item[0]}" for item in results])
        sqls = f'''
                update spell s set Effect3=36,EffectImplicitTargetA3=1,EffectTriggerSpell3=202,SpellDescription4='{description}'
                where ({cond[spellname]});
                update spell_template s set Effect3=36,EffectImplicitTargetA3=1,EffectTriggerSpell3=202
                where ({entry_condition_str});
                update locales_spell s set description_loc4='{description}'
                where ({entry_condition_str});
        '''
        # print(sqls)
        instance.execute_multi_sqls(sqls)

def mod_element_weapon_duration(instance, multi):
    weapon_skills = [
        '石化武器',
        '火舌武器',
        '冰封武器',
        '风怒武器',
    ]
    for spell in weapon_skills:
        results = instance.execute_sql_with_retval(f'select id from spell s where ({cond[spell]})')
        entry_condition_str = ' or '.join([f"id={item[0]}" for item in results])
        sql = f'''
            update spell_effect_mod set EffectBasePoints=(EffectBasePoints+1)*{multi} - 1
            where ({entry_condition_str});
        '''
        instance.execute_multi_sqls(sql)

def customize(instance):
    print(f'{__name__:<45}start to customize!')
    Helper = spell.Helper
    Mod = spell.Mod
    Test = spell.Test

    helper = Helper(instance, cond)
    mod = Mod(instance, cond)
    test = Test(helper, mod)

    # helper.search(['风暴打击', ''])

    # test.mod_dmg({'烈焰震击':1.5})
    # test.mod_talent({'震荡':10})
    # test.mod_dot_interval({'烈焰震击':0.8})
    # test.mod_dot_interval({'烈焰震击':1.25})
    # test.mod_trigger_chance({'元素集中':2})
    # test.mod_duration({'闪电之盾' : '1800s'})
    test.mod_trigger_time({'闪电之盾' : 60})
    # test.mod_cooldown_time({'烈焰震击':2000, '火焰冲击':3000})
    # test.mod_gcd_time({"风暴打击": 100})
    # test.mod_trigger(mod_trigger_skills)

    # helper.search(all_spellnames, 'spell')
    # helper.search(all_spellnames, 'spell_template')
    # 等价于以上两句
    # helper.search(all_spellnames)

    helper.search([
        # # '双武器',
        # '石化武器',
        # '速效毒药_伤害',
        # '速效毒药_几率',
        # '强化速效毒药',
        # 'test1',
    ])
    # test.mod_enchant_spell_trigger_chance({'风怒武器': 1.5})
    # test.mod_enchant_spell_trigger_chance({'速效毒药_几率' : 0.5})
    # test.mod_talent_extra_attack({'风怒武器_效果' : 2})

    # 查询 受指定天赋受益的技能
    # helper.search_affected_spell_by_talent("强化治疗波")
    # helper.search_affected_spell_by_talent("强化幽魂之狼")
    # helper.search_affected_spell_by_talent("闪电掌握")
    # helper.search_affected_spell_by_talent("强化火焰图腾")
    # helper.search_spell_by_class('', 'spell')
    # helper.search_spell_by_class('', 'spell', True)
    # helper.search_spell_by_class('', 'spell_template')
    # helper.search_spell_by_class('', 'spell_template', True)
    # helper.search_spell_by_class('')

    # 调整 部分萨满技能伤害至 x倍
    # mod.mod_dmg(mod_dmg_skills)
    # 调整 部分萨满天赋加成至 x倍
    # mod.mod_talent(mod_talent_skills)
    # 调整 部分萨满dummy天赋加成至 x倍
    # mod.mod_talent_dummy(mod_talent_dummy_skills)
    # 调整 部分萨满dot每条间隔时间至 x倍
    # mod.mod_dot_interval(mod_dot_interval_skills)
    # 调整 部分萨满技能触发几率至 x倍
    # mod.mod_trigger_chance(mod_trigger_chance_skills)
    # 调整 部分萨满技能持续时间至指定数值
    # mod.mod_duration(mod_duration_skills)
    # 调整 部分萨满技能触发次数至 指定数量
    # mod.mod_trigger_time(mod_trigger_time_skills)
    # 调整 部分萨满技能冷却时间
    # mod.mod_cooldown_time(mod_cooldown_time_skills)
    # 调整 部分萨满技能的 gcd 时间
    # mod.mod_gcd_time(mod_gcd_time_skills)
    # 调整 部分萨满触发技能的效果
    # mod.mod_trigger(mod_trigger_skills)
    # 调整 萨满 风怒额外攻击次数 加成至 x倍
    # mod.mod_talent_extra_attack(mod_talent_extra_attack_skills)
    # 调整 萨满风怒武器触发概率
    # mod.mod_enchant_spell_trigger_chance(mod_enchant_spell_trigger_chance_skills)
    # 调整 萨满 各 元素武器的 持续时间 至12倍
    # mod_element_weapon_duration(instance, 12)

    # mod spell : 双手斧和锤
    # 使你可以使用双石化武器手斧和双手锤 -> 使你可以使用双手斧,双手锤和双手剑
    # mod_spell_16269(instance)
