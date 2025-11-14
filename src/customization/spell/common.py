def cond_conv2server(cond):
    condition = cond
    condition = condition.replace('s.id', 's.entry')
    condition = condition.replace('s.spellname4', 'l.name_loc4')
    condition = condition.replace('s.spellrank4', 'l.nameSubtext_loc4')
    condition = condition.replace('s.SpellDescription4', 'l.description_loc4')
    return condition

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

def sql_update_trigger_time(table, trigger_time, cond, effect_type):
    sql = f'''
        update {table} s set s.ProcCharges={trigger_time}
        WHERE
        s.procchance!=-1 and s.procchance!=0 and 
        (
            (s.Effect1={effect_type} and s.effectapplyauraname1=42 and s.EffectTriggerSpell1>0) or
            (s.Effect2={effect_type} and s.effectapplyauraname2=42 and s.EffectTriggerSpell2>0) or
            (s.Effect3={effect_type} and s.effectapplyauraname3=42 and s.EffectTriggerSpell3>0)
        ) and ({cond});
    '''
    return sql

def sql_update_duration(table, idx, cond, effect_type):
    sql = f'''
        update {table} s set s.DurationIndex={idx}
        WHERE ({cond});
    '''
    return sql

def sql_query(table, cond):
    return f'''
        select DISTINCT s.entry id
        from {table} s
        INNER JOIN locales_spell l ON s.entry = l.entry
        WHERE {cond};
    '''

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
        elif sql_type == 'duration':
            sql_update = sql_update_duration
        elif sql_type == 'trigger_time':
            sql_update = sql_update_trigger_time
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

    def mod_duration(self, spellnames):
            cond = self._cond
            duration_dict = {
                '100ms' : 407,
                '250ms' : 328,
                '500ms' : 327,
                   '1s' :  36,
                 '1.5s' :  65,
                   '2s' :  39,
                 '2.5s' :  66,
                   '3s' :  27,
                   '4s' :  35,
                   '5s' :   7,
                   '5s' :  28,
                   '6s' :  32,
                   '7s' : 165,
                   '8s' :  31,
                   '9s' : 105,
                  '10s' :   1,
                  '11s' :  38,
                  '12s' :  29,
                  '14s' : 305,
                  '15s' :   8,
                  '16s' : 387,
                  '18s' :  85,
                  '20s' :  18,
                  '21s' :  86,
                  '22s' : 467,
                  '24s' : 106,
                  '25s' :  63,
                  '26s' : 468,
                  '27s' : 205,
                  '30s' :   9,
                  '30s' :   2,
                  '35s' : 125,
                  '36s' : 325,
                  '40s' :  64,
                  '44s' : 326,
                  '45s' :  22,
                  '50s' : 245,
                  '55s' : 265,
                  '60s' :  10,
                  '75s' :  62,
                  '90s' :  23,
                 '120s' :   4,
                 '160s' :  24,
                 '180s' :  25,
                 '210s' : 552,
                 '230s' :  16,
                 '240s' :  26,
                 '300s' :   5,
                 '360s' :  41,
                 '600s' :   6,
                 '900s' : 347,
                '1200s' :  40,
                '1800s' :  30,
                '2700s' : 145,
                '3600s' :  42,
                '5400s' : 547,
                '7200s' : 367,
               '10800s' : 548,
               '14400s' : 527,
               'infinit': 21,
            }
            for spellname, duration in spellnames.items():
                if spellname in cond.keys():
                    if duration in duration_dict:
                        duration_idx = duration_dict[duration]
                        self.multi_effect_on_spell('spell',          duration_idx, cond[spellname], 6, sql_type='duration')
                        self.multi_effect_on_spell('spell_template', duration_idx, cond[spellname], 6, sql_type='duration')
                    else:
                        print(f'WARNING: {spellname} duration {duration} not in duration_dict')

    def mod_trigger_time(self, spellnames):
        cond = self._cond
        for spellname, trigger_time in spellnames.items():
            if spellname in cond.keys():
                self.multi_effect_on_spell('spell',          trigger_time, cond[spellname], 6, sql_type='trigger_time')
                self.multi_effect_on_spell('spell_template', trigger_time, cond[spellname], 6, sql_type='trigger_time')

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
    def mod_duration(self, spell_and_multiratios):
        self._helper.search(spell_and_multiratios.keys())
        self._mod.mod_duration(spell_and_multiratios)
        self._helper.search(spell_and_multiratios.keys())
    def mod_trigger_time(self, spell_and_multiratios):
        self._helper.search(spell_and_multiratios.keys())
        self._mod.mod_trigger_time(spell_and_multiratios)
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
            ,EffectAmplitude1 as amp1,EffectAmplitude2 as amp2
            ,DurationIndex dur_idx
            ,EffectTriggerSpell1 trig1,procchance trig_c,procflags proc_f,ProcCharges trig_time,EffectMiscValue1 as misc1
            ,CastingTimeIndex cast_idx,StartRecoveryCategory as r_class,StartRecoveryTime as r_time
            # ,SpellDescription4 d
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
            ,EffectAmplitude1 as amp1,EffectAmplitude2 as amp2
            ,DurationIndex dur_idx
            ,EffectTriggerSpell1 trig1,procchance trig_c,procflags proc_f,ProcCharges trig_time,EffectMiscValue1 as misc1
            ,CastingTimeIndex cast_idx,StartRecoveryCategory as r_class,StartRecoveryTime as r_time
            # ,description_loc4 d
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