class Helper:
    def __init__(self, instance):
        self._instance = instance
    # 查找 合剂(非药剂) 相关信息
    def lookup_potion(self):
        sql = f'''
            select s.id,s.SpellName4,s.SpellDescription4,s.EffectBasePoints1,s.EffectBasePoints2,s.EffectBasePoints3 from spell s
            left join item_template it on s.id = it.spellid_1
            WHERE s.Effectbasepoints1!=-1 and s.Effectbasepoints1!=0 and it.class=0 and it.subclass=3;
        '''
        self._instance.fast_select(sql)

# x倍率 放大 药剂效果
def multi_effect_on_potion(instance, multi):
    def _sql(subclass, multi):
        return f'''
                update spell s set s.EffectBasePoints1=(s.EffectBasePoints1+1)*{multi}-1
                WHERE EXISTS (
                    SELECT 1 FROM item_template it
                    WHERE s.id = it.spellid_1 and s.Effectbasepoints1!=-1 and s.Effectbasepoints1!=0 and it.class=0 and it.subclass={subclass}
                );
                update spell s set EffectBasePoints2=(EffectBasePoints2+1)*{multi}-1
                WHERE EXISTS (
                    SELECT 1 FROM item_template it
                    WHERE s.id = it.spellid_1 and s.EffectBasePoints2!=-1 and s.EffectBasePoints2!=0 and it.class=0 and it.subclass={subclass}
                );
                update spell s set EffectBasePoints3=(EffectBasePoints3+1)*{multi}-1
                WHERE EXISTS (
                    SELECT 1 FROM item_template it
                    WHERE s.id = it.spellid_1 and s.EffectBasePoints3!=-1 and s.EffectBasePoints3!=0 and it.class=0 and it.subclass={subclass}
                );
        '''
    #药剂
    instance.execute_multi_sqls(_sql(2, multi))
    #合剂
    instance.execute_multi_sqls(_sql(3, multi//2))

def customize(instance):
    print(f'{__name__:<45}start to costomize!')
    # 25倍率 放大 药剂效果, 12.5倍率放大药剂效果
    # multi_effect_on_potion(instance, 25)

    helper = Helper(instance)
    # 查找 合剂(非药剂) 相关信息
    # helper.lookup_potion()
