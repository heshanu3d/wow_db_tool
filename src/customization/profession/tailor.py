from ..base import spell
from ..base import profession

cond_s = {
}

cond_profession = {
    '初级裁缝' : "l.subname_loc4 ='初级裁缝'",
    '中级裁缝' : "l.subname_loc4 ='中级裁缝'",
    '高级裁缝' : "l.subname_loc4 ='高级裁缝'",
    '大师级裁缝' : "l.subname_loc4 ='大师级裁缝'",
    '裁缝'    : "l.subname_loc4 like '%裁缝'",
}

all_spellnames = cond_s.keys()

def customize(instance):
    print(f'{__name__:<45}start to customize!')

    helper_s = spell.Helper(instance, cond_s)
    mod = spell.Mod(instance, cond_s)
    test = spell.Test(helper_s, mod)

    # test.mod_cast_time_with_condition('250ms', 's.id=18402')
    # test.mod_cast_time_with_condition('30s', 's.id=18402')

    # helper_s.search(['裁缝'])
    # helper_s.search(all_spellnames)

    helper_p = profession.Helper(instance, cond_profession)
    # helper_p._search_trainer(cond_profession['裁缝'])

    trainer_spells_condition = helper_p.get_trainer_spell_cond('大师级裁缝')
    # helper_s.search_with_cond(trainer_spells_condition)

    # test.mod_cast_time_with_condition('250ms', trainer_spells_condition)
    # test.mod_cast_time_with_condition('30s', trainer_spells_condition)
    # 裁缝 训练师学到的技能施法时间调整为 250ms
    mod.mod_cast_time_with_condition('250ms', trainer_spells_condition)
