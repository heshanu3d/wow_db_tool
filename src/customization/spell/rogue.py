cond = {
    '暗影之舞': "s.spellname4='暗影之舞';",
    '预谋'    : "s.spellname4='预谋';",
    '伺机待发': "s.spellname4='伺机待发';",
    '拆卸'    : "s.spellname4='拆卸';",
    '毒刃'    : "s.spellname4='毒刃'        and s.id=5938;",
    '佯攻'    : "s.spellname4='佯攻'        and s.spellrank4 like '等级%';",
    '背刺'    : "s.spellname4='背刺'        and s.spellrank4 like '等级%';",
    '影袭'    : "s.spellname4='影袭'        and s.spellrank4 like '等级%';",
    '出血'    : "s.spellname4='出血'        and s.spellrank4 like '等级%';",
    '凿击'    : "s.spellname4='凿击'        and s.spellrank4 like ''     and s.EffectBasePoints1=0;",
    '毁伤'    : "s.spellname4='毁伤'        and s.spellrank4 like '等级%' and s.EffectBasePoints1=1;",
    '毒伤'    : "s.spellname4='毒伤'        and s.spellrank4 like '等级%' and s.EffectBasePoints2!=0;",
    '伏击'    : "s.spellname4='伏击'        and s.spellrank4 like '等级%';",
    '致命投掷': "s.spellname4='致命投掷'     and s.spellrank4 like '等级%';",
    '刺骨'    : "s.spellname4='刺骨'        and s.spellrank4 like '等级%' and s.EffectBasePoints1<500;",
    '闪避'    : "s.spellname4='闪避'        and s.spellrank4 like '等级%' and s.SpellDescription4 like '%使你的躲闪几率%';",
    '疾跑'    : "s.spellname4='疾跑'        and s.spellrank4 like '等级%' and s.SpellDescription4 like '%使你的移动速度提高%';",
    '肾击'    : "s.spellname4='肾击'        and s.spellrank4 like '等级%' and s.SpellDescription4 like '%根据连击点数的数量决定效果持续时间%';",
    '切割'    : "s.spellname4='切割'        and s.spellrank4 like '等级%' and s.SpellDescription4 like '%根据连击点数的数量决定效果持续时间%';",
    '割裂'    : "s.spellname4='割裂'        and s.spellrank4 like '等级%' and s.SpellDescription4 like '%dur%';",
    '锁喉'    : "s.spellname4='锁喉'        and s.spellrank4 like '等级%' and s.SpellDescription4 like '%猛勒敌人的脖子%';",
    '剑刃乱舞': "s.spellname4='剑刃乱舞'     and s.spellrank4='' and s.id<15000;",
    '暗影步'  : "s.spellname4='暗影步'      and s.SpellDescription4 like '%移动速度提高%' and s.EffectBasePoints1=0 and s.EffectBasePoints2=0;",
    '杀戮盛筵': "s.spellname4='杀戮盛筵'     and s.SpellDescription4 like '%你造成的所有伤害提高%';",
    '破甲'    : "s.spellname4='破甲'        and s.SpellDescription4 like '%终结技，使目标的护甲值降低%';",
    '还击'    : "s.spellname4='还击'        and s.SpellDescription4 like '%连击点数%';",
    '鬼魅攻击': "s.spellname4='鬼魅攻击'     and s.SpellDescription4 like '%如果装备匕首则造成%';",
    '刀扇'    : "s.spellname4='刀扇'        and s.SpellDescription4 like '%若使用其它武器则%' and s.id<55000;",
    '偷袭'    : "s.spellname4='偷袭'        and s.EffectBasePoints1=-1;",
}

gcd_eq0_skills = [
    '还击',
    '暗影之舞',
    '暗影步',
    '预谋',
    '伺机待发',
    '剑刃乱舞',
    '疾跑',
    '闪避',
]

gcd_gt0_skills = [
    '影袭',
    '刺骨',
    '割裂',
    '锁喉',
    '破甲',
    '致命投掷',
    '伏击',
    '偷袭',
    '肾击',
    '切割',
    '毁伤',
    '鬼魅攻击',
    '出血',
    '杀戮盛筵',
    '毒伤',
    '拆卸',
    '背刺',
    '凿击',
    '佯攻',
    '毒刃',
    '刀扇',
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
        sql = f'''
            select s.id,s.SpellName4,s.SpellRank4,s.EffectBasePoints1,s.EffectBasePoints2,s.EffectBasePoints3
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

    # 调整 部分盗贼技能gcd调整1000ms -> 250ms
    # mod_gcd(instance, 250, gcd_gt0_skills)
    # 调整 部分盗贼技能gcd调整 至 0ms
    # mod_gcd(instance, 0, gcd_eq0_skills)