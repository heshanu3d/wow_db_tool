def sql_update_dmg(table, multi, cond, effect_type):
    sql = f'''
        update {table} s set s.EffectBasePoints1=(s.EffectBasePoints1+1)*{multi}-1
        WHERE s.Effectbasepoints1!=-1 and s.Effect1={effect_type} and ({cond});
        update {table} s set EffectBasePoints2=(EffectBasePoints2+1)*{multi}-1
        WHERE s.Effectbasepoints2!=-1 and s.Effect2={effect_type} and ({cond});
        update {table} s set EffectBasePoints3=(EffectBasePoints3+1)*{multi}-1
        WHERE s.Effectbasepoints3!=-1 and s.Effect3={effect_type} and ({cond});
    '''
    return sql
def sql_update_dot_interval(table, multi, cond, effect_type):
    sql = f'''
        update {table} s set s.EffectAmplitude1=s.EffectAmplitude1*{multi}
        WHERE s.EffectAmplitude1!=-1 and s.EffectAmplitude1!=0 and s.Effect1={effect_type} and ({cond});
        update {table} s set EffectAmplitude2=EffectAmplitude2*{multi}
        WHERE s.EffectAmplitude2!=-1 and s.EffectAmplitude2!=0 and s.Effect2={effect_type} and ({cond});
        update {table} s set EffectAmplitude3=EffectAmplitude3*{multi}
        WHERE s.EffectAmplitude3!=-1 and s.EffectAmplitude3!=0 and s.Effect3={effect_type} and ({cond});
    '''
    return sql
def sql_update_trigger_chance(table, multi, cond, effect_type):
    sql = f'''
        update {table} s set s.procchance=s.procchance*{multi}
        WHERE
        s.procchance!=-1 and s.procchance!=0 and 
        (
            (s.Effect1={effect_type} and s.effectapplyauraname1=42 and s.EffectTriggerSpell1>0) or
            (s.Effect2={effect_type} and s.effectapplyauraname2=42 and s.EffectTriggerSpell2>0) or
            (s.Effect3={effect_type} and s.effectapplyauraname3=42 and s.EffectTriggerSpell3>0)
        ) and ({cond});
    '''
    return sql

def sql_query(table, cond):
    return f'''
        select DISTINCT s.entry id
        from {table} s
        INNER JOIN locales_spell l ON s.entry = l.entry
        WHERE {cond};
    '''

def cond_conv2server(cond):
    condition = cond
    condition = condition.replace('s.id', 's.entry')
    condition = condition.replace('s.spellname4', 'l.name_loc4')
    condition = condition.replace('s.spellrank4', 'l.nameSubtext_loc4')
    condition = condition.replace('s.SpellDescription4', 'l.description_loc4')
    return condition

class Mod:
    def __init__(self, instance, cond):
        self._instance = instance
        self._cond = cond

    # x倍率 放大 法术效果(伤害/增益)
    def multi_effect_on_spell(self, table, multi, condition, effect_type, sql_type='dmg'):
        instance = self._instance

        if sql_type == 'dmg':
            sql_update = sql_update_dmg
        elif sql_type == 'dot_interval':
            sql_update = sql_update_dot_interval
        elif sql_type == 'trigger_chance':
            sql_update = sql_update_trigger_chance
        else:
            raise Exception('sql_type error')

        if table == 'spell':
            instance.execute_multi_sqls(sql_update(table, multi, condition, effect_type))
        elif table == 'spell_template':
            results = instance.execute_sql_with_retval(sql_query(table, cond_conv2server(condition)))
            entry_condition_str = ' or '.join([f"s.entry={item[0]}" for item in results])
            instance.execute_multi_sqls(sql_update(table, multi, entry_condition_str, effect_type))

    def mod_dmg(self, spellnames):
        cond = self._cond
        for spellname, multi_rate in spellnames.items():
            if spellname in cond.keys():
                self.multi_effect_on_spell('spell',          multi_rate, cond[spellname], 2)
                self.multi_effect_on_spell('spell_template', multi_rate, cond[spellname], 2)

    def mod_talent(self, spellnames):
        cond = self._cond
        for spellname, multi_rate in spellnames.items():
            if spellname in cond.keys():
                self.multi_effect_on_spell('spell',          multi_rate, cond[spellname], 6)
                self.multi_effect_on_spell('spell_template', multi_rate, cond[spellname], 6)
    
    def mod_dot_interval(self, spellnames):
        cond = self._cond
        for spellname, multi_rate in spellnames.items():
            if spellname in cond.keys():
                self.multi_effect_on_spell('spell',          multi_rate, cond[spellname], 6, sql_type='dot_interval')
                self.multi_effect_on_spell('spell_template', multi_rate, cond[spellname], 6, sql_type='dot_interval')

    def mod_trigger_chance(self, spellnames):
        cond = self._cond
        for spellname, multi_rate in spellnames.items():
            if spellname in cond.keys():
                self.multi_effect_on_spell('spell',          multi_rate, cond[spellname], 6, sql_type='trigger_chance')
                self.multi_effect_on_spell('spell_template', multi_rate, cond[spellname], 6, sql_type='trigger_chance')
class Test:
    def __init__(self, helper, mod):
        self._helper = helper
        self._mod = mod
    def mod_talent(self, spell_and_multiratios):
        self._helper.search(spell_and_multiratios.keys())
        self._mod.mod_talent(spell_and_multiratios)
        self._helper.search(spell_and_multiratios.keys())
    def mod_dmg(self, spell_and_multiratios):
        self._helper.search(spell_and_multiratios.keys())
        self._mod.mod_dmg(spell_and_multiratios)
        self._helper.search(spell_and_multiratios.keys())

    def mod_dot_interval(self, spell_and_multiratios):
        self._helper.search(spell_and_multiratios.keys())
        self._mod.mod_dot_interval(spell_and_multiratios)
        self._helper.search(spell_and_multiratios.keys())
    
    def mod_trigger_chance(self, spell_and_multiratios):
        self._helper.search(spell_and_multiratios.keys())
        self._mod.mod_trigger_chance(spell_and_multiratios)
        self._helper.search(spell_and_multiratios.keys())

class Helper:
    def __init__(self, instance, cond):
        self._instance = instance
        self._cond = cond

    def _search(self, condition):
        # s.SpellName4 as name,s.SpellRank4 as lvl,
        sql = f'''
            select s.id,s.SpellName4 as name,s.SpellRank4 as lvl,s.Effect1 as e1,s.Effect2 as e2,s.Effect3 as e3,s.EffectBasePoints1 as base1,s.EffectBasePoints2 as base2,s.EffectBasePoints3 as base3
            ,s.effectapplyauraname1 as aura1,s.effectapplyauraname2 as aura2,s.effectapplyauraname3 as aura3
            ,EffectAmplitude1 as amp1,EffectAmplitude2 as amp2,EffectAmplitude3 as amp3
            ,EffectTriggerSpell1 trig1,procchance trigchance,procflags,EffectMiscValue1 as misc1
            ,CastingTimeIndex cast_idx,StartRecoveryCategory as r_class,StartRecoveryTime as r_time
            # ,spelldescription4
            from spell s
            WHERE {condition};
        '''
        self._instance.fast_select(sql)
    def _search_server(self, condition):
        # ,spelldescription4
        # name_loc4,nameSubtext_loc4,description_loc4
        sql = f'''
            select DISTINCT s.entry id,l.name_loc4 name,l.nameSubtext_loc4 as lvl,s.Effect1 as e1,s.Effect2 as e2,s.Effect3 as e3,s.EffectBasePoints1 as base1,s.EffectBasePoints2 as base2,s.EffectBasePoints3 as base3
            ,s.effectapplyauraname1 as aura1,s.effectapplyauraname2 as aura2,s.effectapplyauraname3 as aura3
            ,EffectAmplitude1 as amp1,EffectAmplitude2 as amp2,EffectAmplitude3 as amp3
            ,EffectTriggerSpell1 trig1,procchance trigchance,procflags,EffectMiscValue1 as misc1
            ,CastingTimeIndex cast_idx,StartRecoveryCategory as r_class,StartRecoveryTime as r_time
            from spell_template s
            INNER JOIN locales_spell l ON s.entry = l.entry
            WHERE {condition};
        '''
        self._instance.fast_select(sql)
    def search(self, spellnames=[], table=''):
        cond = self._cond
        for spellname in spellnames:
            if table == 'spell':
                if spellname in cond:
                    self._search(cond[spellname])
            elif table == 'spell_template':
                if spellname in cond:
                    self._search_server(cond_conv2server(cond[spellname]))
            elif table == '':
                if spellname in cond:
                    self._search(cond[spellname])
                if spellname in cond:
                    self._search_server(cond_conv2server(cond[spellname]))