

# x倍率 放大 药剂效果
def multi_effect_on_potion(instance, multi):
    def _sql(subclass):
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
    instance.execute_multi_sqls(_sql(2))
    #合剂
    instance.execute_multi_sqls(_sql(3))

def customize(instance):
    print(f'{__name__:<45}start to costomize!')
    # 25倍率 放大 药剂效果
    # multi_effect_on_potion(instance, 25)