from ..base import spell

cond = {
    # '暗影之舞': "s.spellname4='暗影之舞'",
    # '毒刃'    : "s.spellname4='毒刃'        and s.id=5938",
    # '佯攻'    : "s.spellname4='佯攻'        and s.spellrank4 like '等级%'",
    # '刺骨'    : "s.spellname4='刺骨'        and s.spellrank4 like '等级%' and s.EffectBasePoints1<500",
    # '闪避'    : "s.spellname4='闪避'        and s.spellrank4 like '等级%' and s.spelldescription4 like '%使你的躲闪几率%'",
    # '剑刃乱舞': "s.spellname4='剑刃乱舞'     and s.spellrank4='' and s.id<15000",
    # '暗影步'  : "s.spellname4='暗影步'      and s.spelldescription4 like '%移动速度提高%' and s.EffectBasePoints1=0 and s.EffectBasePoints2=0",
    # '鬼魅攻击': "s.spellname4='鬼魅攻击'     and s.spelldescription4 like '%如果装备匕首则造成%'",
    # '刀扇'    : "s.spellname4='刀扇'        and s.spelldescription4 like '%若使用其它武器则%' and s.id<55000",
    # '偷袭'    : "s.spellname4='偷袭'        and s.EffectBasePoints1=-1",
    # '火球术' : "s.spellname4='火球术'    and s.spellrank4 like '等级%' and startrecoverytime>0",
    # '腐蚀术' : "s.spellname4='腐蚀术'    and s.spellrank4 like '等级%' and startrecoverytime>0",
    # '痛苦诅咒' : "s.spellname4='痛苦诅咒'    and s.spellrank4 like '等级%' and startrecoverytime>0",

    '闪电箭' : "s.spellname4='闪电箭'    and s.spellrank4 like '等级%' and startrecoverytime>0 and ((s.id<10393 or s.id=15207 or s.id=15208) and s.id!=8246)",
    '闪电链' : "s.spellname4='闪电链'    and s.spellrank4 like '等级%' and startrecoverytime>0",
    '闪电之盾' : "s.spellname4='闪电之盾'    and s.spellrank4 like '等级%' and startrecoverytime>0 and EffectTriggerSpell1>0 and procflags=139944",
    '地震术' : "s.spellname4='地震术'    and s.spellrank4 like '等级%' and startrecoverytime>0",
    '烈焰震击' : "s.spellname4='烈焰震击' and s.spellrank4 like '等级%' and startrecoverytime>0",
    '冰霜震击' : "s.spellname4='冰霜震击' and s.spellrank4 like '等级%' and startrecoverytime>0",

    # TODO 1
    '石化武器' : "s.spellname4='石化武器' and s.spellrank4 like '等级%' and startrecoverytime>0",
    '火舌武器' : "s.spellname4='火舌武器' and s.spellrank4 like '等级%' and startrecoverytime>0",
    '冰封武器' : "s.spellname4='冰封武器' and s.spellrank4 like '等级%' and startrecoverytime>0",
    '风怒武器' : "s.spellname4='风怒武器' and s.spellrank4 like '等级%' and startrecoverytime>0",

    # TODO 2
    '火焰新星图腾' : "s.spellname4='火焰新星图腾' and s.spellrank4 like '等级%' and startrecoverytime>0",
    '灼热图腾' : "s.spellname4='灼热图腾' and s.spellrank4 like '等级%' and startrecoverytime>0",
    '地缚图腾' : "s.spellname4='地缚图腾' and s.spellrank4 like '等级%' and startrecoverytime>0",
    '石爪图腾' : "s.spellname4='石爪图腾' and s.spellrank4 like '等级%' and startrecoverytime>0",
    '大地之力图腾' : "s.spellname4='大地之力图腾' and s.spellrank4 like '等级%' and startrecoverytime>0",
    '清毒图腾' : "s.spellname4='大地之力图腾' and s.spellrank4 like '等级%' and startrecoverytime>0",

    # TODO 3
    '次级治疗波' : "s.spellname4='次级治疗波'    and s.spellrank4 like '等级%' and startrecoverytime>0",
    '治疗波' : "s.spellname4='治疗波'    and s.spellrank4 like '等级%' and startrecoverytime>0",
    '治疗链' : "s.spellname4='治疗链'    and s.spellrank4 like '等级%' and startrecoverytime>0",
    '消毒术' : "s.spellname4='消毒术'    and startrecoverytime>0",
    '祛病术' : "s.spellname4='祛病术'    and startrecoverytime>0",

    # '幽魂之狼' : "s.spellname4='幽魂之狼' and s.spellrank4 like '等级%'",

    # '剑专精' : "s.spellname4='剑类武器专精' and s.spellrank4 like '等级%' and effectapplyauraname1=42 and effectbasepoints1!=-1",
    # 'test' : "s.id=16459",
    # 'test1' : "s.effect1=19 and s.effectbasepoints1>0",
    

    # 元素天赋
    '震荡'    : "s.spellname4='震荡'            and s.spellrank4 like '等级%'",
    '传导'    : "s.spellname4='传导'            and s.spellrank4 like '等级%'",
    '大地之握' : "s.spellname4='大地之握'        and s.spellrank4 like '等级%'",
    '元素防护' : "s.spellname4='元素防护'        and s.spellrank4 like '等级%'",
    '烈焰召唤' : "s.spellname4='烈焰召唤'        and s.spellrank4 like '等级%'",
    '元素集中' : "s.spellname4='元素集中'        and s.EffectTriggerSpell1>0",
    '回响'    : "s.spellname4='回响'            and s.spellrank4 like '等级%'",
    '雷霆召唤' : "s.spellname4='雷霆召唤'        and s.spellrank4 like '等级%'",
    '强化火焰图腾' : "s.spellname4='强化火焰图腾' and s.spellrank4 like '等级%'",
    '风暴之眼' : "s.spellname4='风暴之眼'        and s.spellrank4 like '等级%'",
    '元素浩劫' : "s.spellname4='元素浩劫'        and s.spellrank4 like '等级%' and effectapplyauraname1=52",
    '风暴来临' : "s.spellname4='风暴来临'        and s.spellrank4 like '等级%'",
    '元素之怒' : "s.spellname4='元素之怒'        and s.effectapplyauraname1=108",
    '闪电掌握' : "s.spellname4='闪电掌握'        and s.spellrank4 like '等级%'",
    '元素掌握' : "s.spellname4='元素掌握'        and s.effectbasepoints2!=0",

    # 增强天赋
    '先祖知识' : "s.spellname4='先祖知识'        and s.spellrank4 like '等级%'",
    '盾牌专精' : "s.spellname4='盾牌专精'        and s.spellrank4 like '等级%' and effectapplyauraname2=150",
    '守护图腾' : "s.spellname4='守护图腾'        and s.spellrank4 like '等级%'",
    '雷鸣猛击' : "s.spellname4='雷鸣猛击'        and s.spellrank4 like '等级%'",
    '强化幽魂之狼' : "s.spellname4='强化幽魂之狼' and s.spellrank4 like '等级%'",
    '强化闪电之盾' : "s.spellname4='强化闪电之盾' and s.spellrank4 like '等级%'",
    '强化图腾' : "s.spellname4='强化图腾' and s.spellrank4 like '等级%' and effectapplyauraname2!=0",
    '双手斧和锤' : "s.spellname4='双手斧和锤'",
    '预知' : "s.spellname4='预知' and s.spellrank4 like '等级%' and effectapplyauraname1=49",
    '乱舞' : "s.spellname4='乱舞' and s.spellrank4 like '等级%' and effectapplyauraname1=138 and (s.id=16257 or s.id=16277 or s.id=16278 or s.id=16279 or s.id=16280) and procflags=4",
    '坚韧' : "s.spellname4='坚韧' and s.spellrank4 like '等级%' and (s.id=16252 or s.id=16306 or s.id=16307 or s.id=16308 or s.id=16309) and EffectMiscValue1=1",
    '强化武器图腾' : "s.spellname4='强化武器图腾' and s.spellrank4 like '等级%'",
    '元素武器' : "s.spellname4='元素武器' and s.spellrank4 like '等级%' and Effect2!=0",
    '武器掌握' : "s.spellname4='武器掌握' and s.spellrank4 like '等级%'",
    '风暴打击' : "s.spellname4='风暴打击' and s.spellrank4 like '等级%' and startrecoverytime>0",

    
}

mod_dmg_skills = {
    '闪电箭'   : 1.5,
    '闪电链'   : 1.5,
    '地震术'   : 1.5,
    '烈焰震击' : 1.5,
    '冰霜震击' : 1.5,
}

mod_talent_skills = {
    '烈焰震击' : 2,
    '闪电之盾' : 2,

    '震荡'    : 10,
    '传导'    : 5,
    '大地之握' : 3,
    '元素防护' : 3,
    '烈焰召唤' : 10,
    '回响'    : 3,
    '雷霆召唤' : 2,
    '强化火焰图腾' : 2,
    # '风暴之眼' : 2,  3点天赋已经100%触发几率了，没必要 mod
    '元素浩劫' : 2,
    '风暴来临' : 2,
    '元素之怒' : 2,
    '闪电掌握' : 1.5,
    '元素掌握' : 1.5,

    '先祖知识' : 10,
    '盾牌专精' : 4,
    '守护图腾' : 5,
    '雷鸣猛击' : 2,
    '强化幽魂之狼' : 1.5,
    '强化闪电之盾' : 10,
    '强化图腾' : 10,
    '预知' : 4,
    '乱舞' : 4,
    '坚韧' : 4,
    '强化武器图腾' : 10,
    '元素武器' : 10,
    '武器掌握' : 4,
    '风暴打击': 3
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

mod_cast_time_skills = {
    '闪电箭'   : '2500ms',
    '闪电链'   : '250ms',
}

gcd_eq0_skills = [

]

gcd_gt0_skills = [
    '闪电箭',
    # '闪电链',
    # '大地震击',
    # '烈焰震击',
    # '冰霜震击',
]

all_spellnames = cond.keys()

# gcd_ms : 1000ms, 1500ms
def mod_gcd(instance, gcd_ms, spellnames):
    sqls = []
    for spellname in spellnames:
        if spellname in cond.keys():
            if gcd_ms == 0:
                sql = f'''
                    update spell s set StartRecoveryCategory=0,StartRecoveryTime=0
                    WHERE StartRecoveryCategory=133 and StartRecoveryTime>0 and {cond[spellname]};
                '''
            elif gcd_ms > 0:
                sql = f'''
                    update spell s set StartRecoveryTime={gcd_ms},StartRecoveryCategory=133
                    WHERE StartRecoveryCategory=133 and StartRecoveryTime>0 and {cond[spellname]};
                '''
            else:
                print(f'err gcd_ms value: {gcd_ms} < 0')
                return
            sqls.append(sql)
    # for sql in sqls:
    #     print(sql)
    instance.execute_multi_sqls(sqls)

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
    # test.mod_trigger_time({'闪电之盾' : 60})
    # test.mod_cooldown_time({'烈焰震击':2000, '火焰冲击':3000})

    
    # helper.search(all_spellnames, 'spell')
    # helper.search(all_spellnames, 'spell_template')
    # 等价于以上两句
    # helper.search(all_spellnames)
    helper.search(['次级治疗波','治疗波','治疗链','消毒术','祛病术','闪电链'])

    # 调整 部分萨满技能伤害至 x倍
    # mod.mod_dmg(mod_dmg_skills)
    # 调整 部分萨满天赋加成至 x倍
    # mod.mod_talent(mod_talent_skills)
    # 调整 部分萨满dot每条间隔时间至 x倍
    # mod.mod_dot_interval(mod_dot_interval_skills)
    # 调整 部分萨满技能触发几率至 x倍
    # mod.mod_trigger_chance(mod_trigger_chance_skills)
    # 调整 部分萨满技能持续时间至指定数值
    # mod.mod_duration(mod_duration_skills)
    # 调整 部分萨满技能触发次数至 指定数量
    # mod.mod_trigger_time(mod_trigger_time_skills)

    # mod spell : 双手斧和锤
    # 使你可以使用双手斧和双手锤 -> 使你可以使用双手斧,双手锤和双手剑
    # mod_spell_16269(instance)


    # 调整 部分萨满技能gcd调整1000ms -> 250ms
    # mod.mod_gcd(250, gcd_gt0_skills)
    # 调整 部分萨满技能gcd调整 至 0ms
    # mod.mod_gcd(0, gcd_eq0_skills)
