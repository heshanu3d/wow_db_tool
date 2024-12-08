class Helper:
    def __init__(self, instance):
        self._instance = instance
    # 查找跟大师的xx铭文相关的spellitemenchant，方便倍率修改该附魔数值
    def find_master_inspiration(self):
        sql = """
            select s.id,s.SpellName4,s.SpellDescription4,s.Effect1,s.EffectMiscValue1,sRefName4,minAmount1,maxAmount1,minAmount2,maxAmount2,minAmount3,maxAmount3 from spell s
            left join spellitemenchantment sp on s.EffectMiscValue1=sp.id
            where s.Spellname4 like "大师的%铭文" and s.Effect1=53;
        """
        self._instance.fast_select(sql)

# x倍率 放大 卷轴效果
def multi_effect_on_scroll(instance, multi):
    sql = f'''
            update spell s set s.EffectBasePoints1=(s.EffectBasePoints1+1)*{multi}-1
            WHERE EXISTS (
                SELECT 1 FROM item_template it
                WHERE s.id = it.spellid_1 and s.Effectbasepoints1!=-1 and s.Effectbasepoints1!=0 and it.class=0 and it.subclass=4
            );
    '''
    instance.execute_multi_sqls(sql)


# 61117	大师的利斧铭文	53	3835	+360 攻击强度，+45 爆击等级	360	360	45	45	0	0
# 61118	大师的峭壁铭文	53	3836	+210 法术强度，每5秒法力回复+24	210	210	24	24	0	0
# 61119	大师的巅峰铭文	53	3837	+180躲闪等级，+45 防御等级	180	180	45	45	0	0
# 61120	大师的风暴铭文	53	3838	+210法术强度，+45 爆击等级	210	210	45	45	0	0
def muiti_master_inspiration(instance, rate):
    sql = '''
        select s.id,s.EffectMiscValue1,sRefName4 from spell s
        left join spellitemenchantment sp on s.EffectMiscValue1=sp.id
        where s.Spellname4 like "大师的%铭文" and s.Effect1=53;
    '''

    options_spim = [
        ['minAmount1',rate,'multi'],['maxAmount1',rate,'multi'],
        ['minAmount2',rate,'multi'],['maxAmount2',rate,'multi'],
        ['minAmount3',rate,'multi'],['maxAmount3',rate,'multi'],
        ['sRefName4',rate,'digit_in_str_multi']
    ]
    options_sp = [
        ['SpellDescription4',rate,'digit_in_str_multi']
    ]

    gen_sqls = []
    results, _ = instance.execute_sql_with_ret(sql)
    for ids in results:
        id_spell = ids[0]
        id_EffectMisc = ids[1]
        # gen_sqls.append(instance.update_item(id_EffectMisc, options=options_spim, table='spellitemenchantment', primary_key='id', gen_sql_mode=True))
        gen_sqls.append(instance.update_item(id_spell,      options=options_sp,   table='spell',                primary_key='id', gen_sql_mode=True))
    
    # instance.execute_multi_sqls(gen_sqls)
    # for sql in gen_sqls:
    #     print(sql)
    print(f"{__name__:<45}generate dbc from tbl spell、spellitemenchantment and replace the corresponding server's dbc file and client's mpq file")

def customize(instance):

    print(f'{__name__:<45}start to costomize!')
    # 5倍率 放大 卷轴效果
    # multi_effect_on_scroll(instance, 5)

    # 15倍率 放大 大师的xx铭文 效果
    # muiti_master_inspiration(instance, 15)

    helper = Helper(instance)
    # 查找跟大师的xx铭文相关的spellitemenchant，方便倍率修改该附魔数值
    # helper.find_master_inspiration()