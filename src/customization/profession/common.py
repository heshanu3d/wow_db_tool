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
    # helper.search(['钓鱼'])
    # helper.search(all_spellnames)

    # 调整 采矿、熔炼、剥皮、采药、分解、全部瞬间完成
    # mod.mod_cast_time(mod_cast_time_skills)
    # 调整 钓鱼时间 30s -> 5s
    # mod.mod_duration(mod_duration_skills)