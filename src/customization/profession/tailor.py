from ..base import spell
from ..base import profession

cond_s = {
}

cond_profession = {
    '初级裁缝'         : "subname ='初级裁缝'",
    '中级裁缝'         : "subname ='中级裁缝'",
    '高级裁缝'         : "subname ='高级裁缝'",
    '月布裁缝大师'     : "subname ='月布裁缝大师'",
    '暗纹裁缝大师'     : "subname ='暗纹裁缝大师'",
    '魔焰裁缝大师'     : "subname ='魔焰裁缝大师'",
    '宗师级裁缝训练师' : "subname ='宗师级裁缝训练师'",
    '裁缝'             : "subname like '%裁缝'",
}

all_spellnames = cond_s.keys()

# 锻造 SKILL_BLACKSMITHING            = 164,
# 制革 SKILL_LEATHERWORKING           = 165,
# 炼金 SKILL_ALCHEMY                  = 171,
# 裁缝 SKILL_TAILORING                = 197,
# 工程 SKILL_ENGINEERING              = 202,
# 珠宝 755
# 铭文 773
# 附魔 333

# 采矿 SKILL_MINING                   = 186,
# 草药 SKILL_HERBALISM                = 182,

# 急救 129
# 烹饪 SKILL_COOKING                  = 185,
# 钓鱼 SKILL_FISHING                  = 356,

# 查找 裁缝npc
# select c.entry,c.name, c.subname, c2.map,c2.position_x x,c2.position_y y,c2.position_z z from creature_template c inner join creature c2 on c2.id=c.entry where subname like '%裁缝%';
def customize(instance):
    print(f'{__name__:<45}start to customize!')

    helper_s = spell.Helper(instance, cond_s)
    mod = spell.Mod(instance, cond_s)
    test = spell.Test(helper_s, mod)

    # test.mod_cast_time_with_condition('250ms', 's.id=18402')
    # test.mod_cast_time_with_condition('30s', 's.id=18402')

    helper_p = profession.Helper(instance, cond_profession)

