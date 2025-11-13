def _sql(table, multi, cond, effect_type):
    sql = f'''
        update {table} s set s.EffectBasePoints1=(s.EffectBasePoints1+1)*{multi}-1
        WHERE s.Effectbasepoints1!=-1 and s.Effectbasepoints1!=0 and s.Effect1={effect_type} and ({cond});
        update {table} s set EffectBasePoints2=(EffectBasePoints2+1)*{multi}-1
        WHERE s.Effectbasepoints2!=-1 and s.Effectbasepoints2!=0 and s.Effect2={effect_type} and ({cond});
        update {table} s set EffectBasePoints3=(EffectBasePoints3+1)*{multi}-1
        WHERE s.Effectbasepoints3!=-1 and s.Effectbasepoints3!=0 and s.Effect3={effect_type} and ({cond});
    '''
    return sql

def cond_conv2server(cond):
    condition = cond
    condition = condition.replace('s.id', 's.entry')
    condition = condition.replace('s.spellname4', 'l.name_loc4')
    condition = condition.replace('s.spellrank4', 'l.nameSubtext_loc4')
    condition = condition.replace('s.SpellDescription4', 'l.description_loc4')
    return condition
# x倍率 放大 直接伤害法术
def multi_effect_on_spell(instance, table, multi, cond, effect_type):
    def _query(table, cond):
        return f'''
            select DISTINCT s.entry id
            from spell_template s
            INNER JOIN locales_spell l ON s.entry = l.entry
            WHERE {cond};
        '''
    if table == 'spell':
        instance.execute_multi_sqls(_sql(table, multi, cond, effect_type))
    elif table == 'spell_template':
        results = instance.execute_sql_with_retval(_query(table, cond_conv2server(cond)))
        entry_condition_str = ' or '.join([f"s.entry={item[0]}" for item in results])
        # print(entry_condition_str)
        instance.execute_multi_sqls(_sql(table, multi, entry_condition_str, effect_type))

def multi_effect_on_direct_dmg_spell(instance, table, multi, cond):
    multi_effect_on_spell(instance, table, multi, cond, 2)

def multi_effect_on_talent_spell(instance, table, multi, cond):
    multi_effect_on_spell(instance, table, multi, cond, 6)