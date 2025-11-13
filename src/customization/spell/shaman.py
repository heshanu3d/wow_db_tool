cond = {
    # '暗影之舞': "s.spellname4='暗影之舞';",
    # '毒刃'    : "s.spellname4='毒刃'        and s.id=5938;",
    # '佯攻'    : "s.spellname4='佯攻'        and s.spellrank4 like '等级%';",
    # '刺骨'    : "s.spellname4='刺骨'        and s.spellrank4 like '等级%' and s.EffectBasePoints1<500;",
    # '闪避'    : "s.spellname4='闪避'        and s.spellrank4 like '等级%' and s.SpellDescription4 like '%使你的躲闪几率%';",
    # '剑刃乱舞': "s.spellname4='剑刃乱舞'     and s.spellrank4='' and s.id<15000;",
    # '暗影步'  : "s.spellname4='暗影步'      and s.SpellDescription4 like '%移动速度提高%' and s.EffectBasePoints1=0 and s.EffectBasePoints2=0;",
    # '鬼魅攻击': "s.spellname4='鬼魅攻击'     and s.SpellDescription4 like '%如果装备匕首则造成%';",
    # '刀扇'    : "s.spellname4='刀扇'        and s.SpellDescription4 like '%若使用其它武器则%' and s.id<55000;",
    # '偷袭'    : "s.spellname4='偷袭'        and s.EffectBasePoints1=-1;",
    '火球术' : "s.spellname4='火球术'    and s.spellrank4 like '等级%' and startrecoverytime>0;",
    '腐蚀术' : "s.spellname4='腐蚀术'    and s.spellrank4 like '等级%' and startrecoverytime>0;",
    '痛苦诅咒' : "s.spellname4='痛苦诅咒'    and s.spellrank4 like '等级%' and startrecoverytime>0;",
    # '闪电箭' : "s.spellname4='闪电箭'    and s.spellrank4 like '等级%' and startrecoverytime>0 and ((s.id<10393 or s.id=15207 or s.id=15208) and s.id!=8246);",
    # '闪电链' : "s.spellname4='闪电链'    and s.spellrank4 like '等级%' and startrecoverytime>0;",
    # '大地震击' : "s.spellname4='震击'    and s.spellrank4 like '等级%' and startrecoverytime>0;",
    '烈焰震击' : "s.spellname4='烈焰震击' and s.spellrank4 like '等级%' and startrecoverytime>0;",
    # '冰霜震击' : "s.spellname4='冰霜震击' and s.spellrank4 like '等级%' and startrecoverytime>0;",
}

gcd_eq0_skills = [

]

gcd_gt0_skills = [

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

class Helper:
    def __init__(self, instance):
        self._instance = instance
    
    def _search(self, condition):
        # s.SpellName4 as name,s.SpellRank4 as lvl,
        sql = f'''
            select s.id,s.Effect1 as e1,s.Effect2 as e2,s.Effect3 as e3,s.EffectBasePoints1 as base1,s.EffectBasePoints2 as base2,s.EffectBasePoints3 as base3
            ,s.effectapplyauraname1 as aura1,s.effectapplyauraname2 as aura2,s.effectapplyauraname3 as aura3
            ,EffectAmplitude1 as amp1,EffectAmplitude2 as amp2,EffectAmplitude3 as amp3
            ,CastingTimeIndex,StartRecoveryCategory,StartRecoveryTime
            # ,SpellDescription4 
            from spell s
            WHERE {condition};
        '''
        self._instance.fast_select(sql)
    def search(self, spellnames=[]):
        for spellname in spellnames:
            if spellname in cond:
                self._search(cond[spellname])


def customize(instance):
    print(f'{__name__:<45}start to costomize!')

    helper = Helper(instance)
    helper.search(all_spellnames)

    # 调整 部分萨满技能gcd调整1000ms -> 250ms
    # mod_gcd(instance, 250, gcd_gt0_skills)
    # 调整 部分萨满技能gcd调整 至 0ms
    # mod_gcd(instance, 0, gcd_eq0_skills)