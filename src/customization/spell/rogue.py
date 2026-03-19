from ..base import spell

cond = {
    '暗影之舞': "s.spellname4='暗影之舞'",
    '预谋'    : "s.spellname4='预谋'",
    '伺机待发': "s.spellname4='伺机待发'",
    '拆卸'    : "s.spellname4='拆卸'",
    '毒刃'    : "s.spellname4='毒刃'        and s.id=5938",
    '佯攻'    : "s.spellname4='佯攻'        and s.spellrank4 like '等级%'",
    '背刺'    : "s.spellname4='背刺'        and s.spellrank4 like '等级%'",
    '影袭'    : "s.spellname4='影袭'        and s.spellrank4 like '等级%'",
    '出血'    : "s.spellname4='出血'        and s.spellrank4 like '等级%'",
    '凿击'    : "s.spellname4='凿击'        and s.spellrank4 like ''     and s.EffectBasePoints1=0",
    '毁伤'    : "s.spellname4='毁伤'        and s.spellrank4 like '等级%' and s.EffectBasePoints1=1",
    '毒伤'    : "s.spellname4='毒伤'        and s.spellrank4 like '等级%' and s.EffectBasePoints2!=0",
    '伏击'    : "s.spellname4='伏击'        and s.spellrank4 like '等级%'",
    '致命投掷': "s.spellname4='致命投掷'     and s.spellrank4 like '等级%'",
    '刺骨'    : "s.spellname4='刺骨'        and s.spellrank4 like '等级%' and s.EffectBasePoints1<500",
    '闪避'    : "s.spellname4='闪避'        and s.spellrank4 like '等级%' and s.SpellDescription4 like '%使你的躲闪几率%'",
    '疾跑'    : "s.spellname4='疾跑'        and s.spellrank4 like '等级%' and s.SpellDescription4 like '%使你的移动速度提高%'",
    '肾击'    : "s.spellname4='肾击'        and s.spellrank4 like '等级%' and s.SpellDescription4 like '%根据连击点数的数量决定效果持续时间%'",
    '切割'    : "s.spellname4='切割'        and s.spellrank4 like '等级%' and s.SpellDescription4 like '%根据连击点数的数量决定效果持续时间%'",
    '割裂'    : "s.spellname4='割裂'        and s.spellrank4 like '等级%' and s.SpellDescription4 like '%dur%'",
    '锁喉'    : "s.spellname4='锁喉'        and s.spellrank4 like '等级%' and s.SpellDescription4 like '%猛勒敌人的脖子%'",
    '剑刃乱舞': "s.spellname4='剑刃乱舞'     and s.spellrank4='' and s.id<15000",
    '暗影步'  : "s.spellname4='暗影步'      and s.SpellDescription4 like '%移动速度提高%' and s.EffectBasePoints1=0 and s.EffectBasePoints2=0",
    '杀戮盛筵': "s.spellname4='杀戮盛筵'     and s.SpellDescription4 like '%你造成的所有伤害提高%'",
    '破甲'    : "s.spellname4='破甲'        and s.SpellDescription4 like '%终结技，使目标的护甲值降低%'",
    '还击'    : "s.spellname4='还击'        and s.SpellDescription4 like '%连击点数%'",
    '鬼魅攻击': "s.spellname4='鬼魅攻击'     and s.SpellDescription4 like '%如果装备匕首则造成%'",
    '刀扇'    : "s.spellname4='刀扇'        and s.SpellDescription4 like '%若使用其它武器则%' and s.id<55000",
    '偷袭'    : "s.spellname4='偷袭'        and s.EffectBasePoints1=-1",
}

all_spellnames = cond.keys()

mod_gcd_time_skills = {
    '还击'     : 0,
    '暗影之舞' : 0,
    '暗影步'   : 0,
    '预谋'     : 0,
    '伺机待发' : 0,
    '剑刃乱舞' : 0,
    '疾跑'     : 0,
    '闪避'     : 0,
    '影袭'     : 250,
    '刺骨'     : 250,
    '割裂'     : 250,
    '锁喉'     : 250,
    '破甲'     : 250,
    '致命投掷' : 250,
    '伏击'     : 250,
    '偷袭'     : 250,
    '肾击'     : 250,
    '切割'     : 250,
    '毁伤'     : 250,
    '鬼魅攻击' : 250,
    '出血'     : 250,
    '杀戮盛筵' : 250,
    '毒伤'     : 250,
    '拆卸'     : 250,
    '背刺'     : 250,
    '凿击'     : 250,
    '佯攻'     : 250,
    '毒刃'     : 250,
    '刀扇'     : 250,
}

def customize(instance):
    print(f'{__name__:<45}start to customize!')

    Helper = spell.Helper
    Mod = spell.Mod
    Test = spell.Test

    helper = Helper(instance, cond)
    mod = Mod(instance, cond)
    test = Test(helper, mod)

    # helper.search(all_spellnames)

    # test.mod_gcd_time(mod_gcd_time_skills)

    # 调整 部分盗贼技能的 gcd 时间
    mod.mod_gcd_time(mod_gcd_time_skills)