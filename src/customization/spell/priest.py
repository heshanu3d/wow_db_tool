from ..base import spell

cond = {
    '复活术': "s.spellname4='复活术'     and s.spellrank4 like '等级%'",
    '次级治疗术': "s.spellname4='次级治疗术' and s.spellrank4 like '等级%' and s.id != 29170",
    '治疗术': "s.spellname4='治疗术' and s.spellrank4 like '等级%' and s.id != 8812",
    '强效治疗术': "s.spellname4='强效治疗术' and s.spellrank4 like '等级%' and s.id != 34119",
    '快速治疗': "s.spellname4='快速治疗' and s.spellrank4 like '等级%' and s.id != 27608 and s.id < 50000",
    '联结治疗': "s.spellname4='联结治疗' and s.spellrank4 like '等级%' and s.id < 50000",
    '愈合祷言': "s.id=33076 or s.id=48112 or s.id=48113",
    '希望圣歌': "s.id=64901",
    '治疗祷言': "s.spellname4='治疗祷言' and s.spellrank4 like '等级%' and s.id < 50000",
    '治疗之环': "s.spellname4='治疗之环' and s.spellrank4 like '等级%' and s.id != 49306",
    '神圣新星': "s.id=15237 or s.id=15430 or s.id=15431 or s.id=27799 or s.id=27800 or s.id=27801 or s.id=25331 or s.id=48077 or s.id=48078",
    '绝望祷言': "s.spellname4='绝望祷言' and s.spellrank4 like '等级%' and s.id < 50000",
    '神圣赞美诗': "s.spellname4='神圣赞美诗' and s.spellrank4 like '等级%'",
    '祛病术': "s.spellname4='祛病术' and s.id < 50000",
    '驱除疾病': "s.spellname4='驱除疾病' and s.id < 50000",
    '惩击': "s.spellname4='惩击'     and s.spellrank4 like '等级%' and s.id != 46224 and s.id != 71842",
    '神圣之火': "s.spellname4='神圣之火'     and s.spellrank4 like '等级%'",
    '恢复': "s.spellname4='恢复' and s.spellrank4 like '等级%' and s.id != 11359 and s.id != 23396 and s.id != 27606 and s.id != 37563 and s.id < 50000",

    '渐隐术': "s.id=586",
    '暗影恶魔': "s.spellname4='暗影恶魔' and s.id < 50000",
    '暗影防护': "s.spellname4='暗影防护' and s.id < 50000",
    '暗影防护祷言': "s.spellname4='暗影防护祷言' and s.id < 50000 and s.id!=39236",
    '心灵尖啸': "s.spellname4='心灵尖啸' and s.id<=10890",
    '安抚心灵': "s.spellname4='安抚心灵' and s.id<=10890",
    '心灵视界': "s.spellname4='心灵视界' and s.id<=40000",
    '心灵震爆': "s.spellname4='心灵震爆' and s.spellrank4 like '等级%' ",
    '精神控制': "s.id=605",
    '精神鞭笞': "s.spellname4='精神鞭笞' and s.spellrank4 like '等级%' and s.id < 50000",
    '精神灼烧': "s.id=48045 or s.id=53023",
    '吸血鬼之触': "s.spellname4='吸血鬼之触' and s.spellrank4 like '等级%' and s.id < 50000",
    '噬灵疫病': "s.spellname4='噬灵疫病' and s.spellrank4 like '等级%' ",
    '暗言术：痛': "s.spellname4='暗言术：痛'     and s.spellrank4 like '等级%' and s.id != 27605",
    '暗言术：灭': "s.spellname4='暗言术：灭'     and s.spellrank4 like '等级%' and s.id != 27605",

    '法力燃烧': "s.id=8129  ",
    '真言术：盾': "s.spellname4='真言术：盾'     and s.spellrank4 like '等级%' and s.id != 27607",
    '真言术：韧': "s.spellname4='真言术：韧'     and s.spellrank4 like '等级%' and s.id != 23947 and s.id != 23948",
    '坚韧祷言': "s.spellname4='坚韧祷言'     and s.spellrank4 like '等级%' and s.id != 43939 and s.id != 39231",
    '神圣之灵': "s.spellname4='神圣之灵'     and s.spellrank4 like '等级%' and s.id!=16875 and s.id!=39234",
    '精神祷言': "s.spellname4='精神祷言'     and s.spellrank4 like '等级%' ",
    '群体驱散': "s.id=32375",
    '心灵之火': "s.spellname4='心灵之火'     and s.spellrank4 like '等级%'",
    '束缚亡灵': "s.spellname4='束缚亡灵'     and s.spellrank4 like '等级%'",
    '苦修': "s.id=47540 or s.id=53005 or s.id=53006 or s.id=53007",
    '驱散魔法': "s.spellname4='驱散魔法'     and s.spellrank4 like '等级%' and s.id < 1000",
    '能量灌注': "s.id=10060",
    '痛苦压制': "s.id=33206",

    # talent
    '灼热之光': "s.spellname4='灼热之光'     and s.spellrank4 like '等级%'",
    '神圣之怒': "s.spellname4='神圣之怒'     and s.spellrank4 like '等级%'",
    '圣光涌动': "s.spellname4='圣光涌动'     and s.spellrank4 like '等级%' and s.id!=33151",


}

all_spellnames = cond.keys()

mod_gcd_time_skills = {
    '惩击': 250,
    '恢复': 250,
    '苦修': 250,
    '治疗术': 250,
    '快速治疗': 250,
    '联结治疗': 250,
    '愈合祷言': 250,
    '希望圣歌': 250,
    '治疗祷言': 250,
    '治疗之环': 250,
    '神圣新星': 250,
    '神圣之火': 250,
    '心灵震爆': 250,
    '精神控制': 250,
    '精神鞭笞': 250,
    '精神灼烧': 250,
    '噬灵疫病': 250,
    '法力燃烧': 250,
    '群体驱散': 250,
    '次级治疗术': 250,
    '强效治疗术': 250,
    '吸血鬼之触': 250,
    '暗言术：痛': 250,
    '暗言术：灭': 250,

    '复活术': 0,
    '绝望祷言': 0,
    '神圣赞美诗': 0,
    '祛病术': 0,
    '驱除疾病': 0,
    '渐隐术': 0,
    '暗影恶魔': 0,
    '暗影防护': 0,
    '暗影防护祷言': 0,
    '心灵尖啸': 0,
    '安抚心灵': 0,
    '心灵视界': 0,
    '真言术：盾': 0,
    '真言术：韧': 0,
    '坚韧祷言': 0,
    '神圣之灵': 0,
    '精神祷言': 0,
    '心灵之火': 0,
    '束缚亡灵': 0,
    '驱散魔法': 0,
    '能量灌注': 0,
    '痛苦压制': 0,
}

mod_duration_skills = {
    '暗影恶魔'   : '300s',

    '真言术：盾' : '1800s',
    '恢复'       : '1800s',

    '神圣之火' : '1800s',
    '暗言术：痛' : '1800s',
    '噬灵疫病'   : '1800s',
    '吸血鬼之触' : '1800s',

    '能量灌注'   : '3600s',
    '痛苦压制'   : '3600s',

    '暗影防护'   : '3600s',
    '真言术：韧' : '3600s',
    '心灵之火'   : '3600s',
    '神圣之灵'   : '3600s',

    '坚韧祷言'    : '10800s',
    '精神祷言'    : '10800s',
    '暗影防护祷言': '10800s',
}

mod_talent_skills = {
    '灼热之光'     : 2,
    '神圣之怒'     : 2,
}

mod_trigger_chance_skills = {
    '圣光涌动' : 2,
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
    # helper.search(['神圣之火'])

    # test.mod_gcd_time(mod_gcd_time_skills)

    # 调整 部分牧师技能的 gcd 时间
    mod.mod_gcd_time(mod_gcd_time_skills)
    # 调整 部分牧师技能持续时间至指定数值
    mod.mod_duration(mod_duration_skills)
    # 调整 部分牧师天赋加成至 x倍
    mod.mod_talent(mod_talent_skills)
    # 调整 部分牧师技能触发几率至 x倍
    mod.mod_trigger_chance(mod_trigger_chance_skills)