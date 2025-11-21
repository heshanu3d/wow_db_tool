import inspect

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

def sql_update_duration(table, idx, cond, effect_type):
    sql = f'''
        update {table} s set s.DurationIndex={idx}
        WHERE ({cond});
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

def sql_update_cooldown_time(table, cooldown_time, cond, effect_type):
    sql = f'''
        update {table} s set s.CategoryRecoveryTime={cooldown_time}
        WHERE RecoveryTime=0 and CategoryRecoveryTime!=0 and ({cond});
    '''
    return sql

def sql_update_cast_time(table, idx, cond, effect_type):
    sql = f'''
        update {table} s set s.CastingTimeIndex={idx}
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
    def mod_effect_on_spell(self, table, multi, condition, effect_type, sql_type='dmg'):
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
        elif sql_type == 'cooldown_time':
            sql_update = sql_update_cooldown_time
        elif sql_type == 'cast_time':
            sql_update = sql_update_cast_time
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
                self.mod_effect_on_spell('spell',          multi_rate, cond[spellname], 2)
                self.mod_effect_on_spell('spell_template', multi_rate, cond[spellname], 2)

    def mod_talent(self, spellnames):
        cond = self._cond
        for spellname, multi_rate in spellnames.items():
            if spellname in cond.keys():
                self.mod_effect_on_spell('spell',          multi_rate, cond[spellname], 6)
                self.mod_effect_on_spell('spell_template', multi_rate, cond[spellname], 6)
    
    def mod_dot_interval(self, spellnames):
        cond = self._cond
        for spellname, multi_rate in spellnames.items():
            if spellname in cond.keys():
                self.mod_effect_on_spell('spell',          multi_rate, cond[spellname], 6, sql_type='dot_interval')
                self.mod_effect_on_spell('spell_template', multi_rate, cond[spellname], 6, sql_type='dot_interval')

    def mod_trigger_chance(self, spellnames):
        cond = self._cond
        for spellname, multi_rate in spellnames.items():
            if spellname in cond.keys():
                self.mod_effect_on_spell('spell',          multi_rate, cond[spellname], 6, sql_type='trigger_chance')
                self.mod_effect_on_spell('spell_template', multi_rate, cond[spellname], 6, sql_type='trigger_chance')

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
                    self.mod_effect_on_spell('spell',          duration_idx, cond[spellname], 6, sql_type='duration')
                    self.mod_effect_on_spell('spell_template', duration_idx, cond[spellname], 6, sql_type='duration')
                else:
                    print(f'WARNING: {spellname} duration {duration} not in duration_dict')

    def mod_trigger_time(self, spellnames):
        cond = self._cond
        for spellname, trigger_time in spellnames.items():
            if spellname in cond.keys():
                self.mod_effect_on_spell('spell',          trigger_time, cond[spellname], 6, sql_type='triggermod_trigger_time_time')

    def mod_cooldown_time(self, spellnames):
        cond = self._cond
        for spellname, cooldown_time in spellnames.items():
            if spellname in cond.keys():
                self.mod_effect_on_spell('spell',          cooldown_time, cond[spellname], 6, sql_type='cooldown_time')
                self.mod_effect_on_spell('spell_template', cooldown_time, cond[spellname], 6, sql_type='cooldown_time')

    def mod_cast_time_with_condition(self, cast_time, condition):
        cast_time_dict = {
                 '0' :   1,
               '0ms' :   1,
             '100ms' : 190,
             '250ms' :   2,
             '500ms' :   3,
             '600ms' :  36,
             '750ms' : 110,
            '1000ms' :   4,
            '1300ms' :  50,
            '1500ms' :  16,
            '1600ms' : 130,
            '1700ms' :  90,
            '1800ms' :  23,
            '2000ms' :   5,
            '2200ms' :  24,
            '2300ms' :  31,
            '2500ms' :  19,
            '2500ms' :  20,
            '2600ms' :  21,
            '2700ms' : 151,
            '2800ms' :  91,
            '2900ms' :  25,
            '3000ms' :  14,
            '3100ms' : 152,
            '3200ms' :  28,
            '3400ms' : 153,
            '3500ms' :  22,
            '3700ms' :  26,
            '3800ms' : 150,
            '4000ms' :  15,
            '4100ms' :  27,
            '4500ms' :  30,
            '4700ms' :  29,
            '5000ms' :   6,
            '6000ms' : 171,
            '7000ms' :  32,
            '8000ms' : 170,
               '10s' :   7,
               '20s' :   8,
               '30s' :   9,
              '300s' :  70,
        }
        if cast_time in cast_time_dict:
            cast_time_idx = cast_time_dict[cast_time]
            self.mod_effect_on_spell('spell',          cast_time_idx, condition, 6, sql_type='cast_time')
            self.mod_effect_on_spell('spell_template', cast_time_idx, condition, 6, sql_type='cast_time')
        else:
            # print(f'WARNING: cast_time {cast_time} not in duration_dict')
            raise Exception(f'WARNING: cast_time {cast_time} not in duration_dict')

    def mod_cast_time(self, spellnames):
        cond = self._cond
        for spellname, cast_time in spellnames.items():
            if spellname in cond.keys():
                self.mod_cast_time_with_condition(cast_time, cond[spellname])

class Test:
    def __init__(self, helper, mod):
        self._helper = helper
        self._mod = mod

    # 复制 Mod里的mod方法，并在调用前后，查询数据库
    def __getattr__(self, name):
        # 当属性不存在时，检查B是否有该方法
        if hasattr(self._mod, name) and callable(getattr(self._mod, name)):
            signature = inspect.signature(getattr(self._mod, name))
            num_params = len(signature.parameters)

            # 返回一个包装函数
            # 1参数的对应函数 mod_xxx(self, spellnames):
            def wrapper_1_param(*args, **kwargs):
                if args and len(args) > 0:
                    spell_mods = args[0]
                    self._helper.search(list(spell_mods.keys()))
                    getattr(self._mod, name)(spell_mods)  # 调用B的方法
                    self._helper.search(list(spell_mods.keys()))

            # 2参数的对应函数 mod_xxx_with_condition(self, xxx, condition):
            def wrapper_2_param(*args, **kwargs):
                if args and len(args) > 1:
                    self._helper.search_with_cond(args[1])
                    getattr(self._mod, name)(*args, **kwargs)  # 调用B的方法
                    self._helper.search_with_cond(args[1])

            if num_params == 1:
                return wrapper_1_param
            elif num_params == 2:
                return wrapper_2_param
        raise AttributeError(f"'{type(self).__name__}' object has no attribute '{name}'")

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
            ,EffectTriggerSpell1 trig1,procchance trig_c,procflags proc_f,ProcCharges trig_t,EffectMiscValue1 as misc1
            ,CastingTimeIndex cast_idx,RecoveryTime cd, CategoryRecoveryTime cd2, StartRecoveryCategory gcd_c,StartRecoveryTime gcd
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
            ,EffectTriggerSpell1 trig1,procchance trig_c,procflags proc_f,ProcCharges trig_t,EffectMiscValue1 as misc1
            ,CastingTimeIndex cast_idx,RecoveryTime cd, CategoryRecoveryTime cd2, StartRecoveryCategory gcd_c,StartRecoveryTime gcd
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

    def search_with_cond(self, condition, table=''):
        if table == 'spell':
            self._search(condition)
        elif table == 'spell_template':
            self._search_server(cond_conv2server(condition))
        elif table == '':
            self._search(condition)
            self._search_server(cond_conv2server(condition))
