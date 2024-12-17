class Helper:
    def __init__(self, instance):
        self._instance = instance
    # 查找跟磨刀石相关的spell，方便一键生成学习脚本
    def enchant_enchantstone_finder(self):
        sql = """
            # select s.id,s.SpellName4,s.Effect1,s.EffectMiscValue1 from spell s
            # left join spellitemenchantment sp on s.EffectMiscValue1=sp.id
            # where s.spellname4 like '%磨刀石%' or s.spellname4 like '%平衡石%';
            select * from spell
            where id in (2660,2665,2674);
        """
        self._instance.fast_select(sql)

def customize(instance):
    print(f'{__name__:<45}start to costomize!')
    
    helper = Helper(instance)
    # 查找跟磨刀石相关的spell，方便一键生成学习脚本
    # helper.enchant_enchantstone_finder()
