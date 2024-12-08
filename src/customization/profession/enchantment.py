class Helper:
    def __init__(self, instance):
        self._instance = instance
    # 查找跟附魔相关的spell，方便一键生成学习脚本
    def enchant_spell_finder(self):
        sql = """
            select s.id,s.SpellName4 from spell s
            where s.SpellIconID in (241, 578) and (s.spellname4 like '附魔' or s.spellname4 like '附魔%-%');
        """
        self._instance.fast_select(sql)

def customize(instance):
    print(f'{__name__:<45}start to costomize!')
    
    helper = Helper(instance)
    # 查找跟附魔相关的spell，方便一键生成学习脚本
    # helper.enchant_spell_finder()