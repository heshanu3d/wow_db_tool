from ..base import spell

cond = {
    '亡者复生': "s.spellname4='亡者复生' and s.id=46584",
    '邪恶灵气': "s.spellname4='邪恶灵气' and s.id=48265",
    '鲜血灵气': "s.spellname4='鲜血灵气' and s.id=48266",
    '死亡之握': "s.spellname4='死亡之握' and s.id=49576",
    '冰霜之路': "s.spellname4='冰霜之路' and s.id=3714",
    '复活盟友': "s.spellname4='复活盟友' and s.id=61999",
    '活力分流': "s.spellname4='活力分流' and s.id=45529",

    '传染': "s.spellname4='传染' and s.id=50842",
    '湮没': "s.spellname4='湮没' and s.spellrank4 like '等级%' and spellfamilyname=15 and s.id < 51500",
    '凋零缠绕': "s.spellname4='凋零缠绕'     and s.spellrank4 like '等级%' and spellfamilyname=15 and s.id < 49900",
    '暗影打击': "s.spellname4='暗影打击'     and s.spellrank4 like '等级%' and spellfamilyname=15 and s.id < 50000",
    '灵界打击': "s.spellname4='灵界打击'     and s.spellrank4 like '等级%' and spellfamilyname=15 and s.id < 50000",
    '鲜血打击': "s.spellname4='鲜血打击'     and s.spellrank4 like '等级%' and s.id < 50000",
    '冰霜打击': "s.spellname4='冰霜打击'     and s.spellrank4 like '等级%' and s.id <= 55268",
    
    '冰霜灵气': "s.spellname4='冰霜灵气'     and s.SpellDescription4 like '死亡骑士%'",
    '反魔法护罩': "s.spellname4='反魔法护罩' and spellfamilyname=15",
    '符文武器增效': "s.spellname4='符文武器增效'",
    '黑暗命令': "s.spellname4='黑暗命令'",
    '天灾契约': "s.spellname4='天灾契约' and spellfamilyname=15",
    '心灵冰冻': "s.spellname4='心灵冰冻' and StartRecoveryTime=0",
    '冰封之韧': "s.spellname4='冰封之韧' and spellfamilyname=15",
    '寒冬号角': "s.spellname4='寒冬号角'",
    '绞袭': "s.spellname4='绞袭' and s.spellrank4 like '等级%' and spellfamilyname=15",
    '邪爆': "s.spellname4='邪爆' and s.spellrank4 like '等级%' and spellfamilyname=15",
    '寒冰锁链': "s.spellname4='寒冰锁链'     and s.spellrank4 like '等级%'",
    '枯萎凋零': "s.spellname4='枯萎凋零'     and s.spellrank4 like '等级%'",
    '天灾打击': "s.spellname4='天灾打击'     and s.spellrank4 like '等级%'",
    '血液沸腾': "s.spellname4='血液沸腾'     and s.spellrank4 like '等级%'",
    '心脏打击': "s.spellname4='心脏打击'     and s.spellrank4 like '等级%'",
    '冰冷触摸': "s.spellname4='冰冷触摸'     and s.spellrank4 like '等级%' and Effect2=64",
    '符文打击': "s.spellname4='符文打击'     and s.spellrank4 like '等级%'",
    '凛风冲击': "s.spellname4='凛风冲击'     and s.spellrank4 like '等级%'",
}

all_spellnames = cond.keys()

mod_gcd_time_skills = {
    '传染'         : 0,
    '绞袭'         : 0,
    '亡者复生'     : 0,
    '邪恶灵气'     : 0,
    '鲜血灵气'     : 0,
    '死亡之握'     : 0,
    '冰霜之路'     : 0,
    '复活盟友'     : 0,
    '活力分流'     : 0,
    '冰霜灵气'     : 0,
    '黑暗命令'     : 0,
    '天灾契约'     : 0,
    '心灵冰冻'     : 0,
    '冰封之韧'     : 0,
    '寒冬号角'     : 0,
    '反魔法护罩'   : 0,
    '符文武器增效' : 0,

    '湮灭'         : 250,
    '邪爆'         : 250,
    '凋零缠绕'     : 250,
    '暗影打击'     : 250,
    '灵界打击'     : 250,
    '鲜血打击'     : 250,
    '冰霜打击'     : 250,
    '寒冰锁链'     : 250,
    '枯萎凋零'     : 250,
    '天灾打击'     : 250,
    '血液沸腾'     : 250,
    '心脏打击'     : 250,
    '冰冷触摸'     : 250,
    '符文打击'     : 250,
    '凛风冲击'     : 250,
}

mod_duration_skills = {
    '寒冬号角' : '3600s',
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

    # test.mod_duration({'寒冬号角' : '3600s'})

    # test.mod_gcd_time(mod_gcd_time_skills)

    # 调整 部分死亡骑士技能的 gcd 时间
    mod.mod_gcd_time(mod_gcd_time_skills)
    # 调整 部分死亡骑士技能持续时间至指定数值
    mod.mod_duration(mod_duration_skills)