import inspect

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
            (s.Effect1={effect_type} and (s.effectapplyauraname1=42 or s.effectapplyauraname1=4) and s.EffectTriggerSpell1>0) or
            (s.Effect2={effect_type} and (s.effectapplyauraname2=42 or s.effectapplyauraname2=4) and s.EffectTriggerSpell2>0) or
            (s.Effect3={effect_type} and (s.effectapplyauraname3=42 or s.effectapplyauraname3=4) and s.EffectTriggerSpell3>0)
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

def sql_update_gcd_time(table, gcd_ms, cond, effect_type):
    sql = ''
    if gcd_ms == 0:
        sql = f'''
            update {table} s set StartRecoveryCategory=0,StartRecoveryTime=0
            WHERE StartRecoveryCategory=133 and StartRecoveryTime>0 and ({cond});
        '''
    elif gcd_ms > 0:
        sql = f'''
            update {table} s set StartRecoveryTime={gcd_ms},StartRecoveryCategory=133
            WHERE StartRecoveryCategory=133 and StartRecoveryTime>0 and ({cond});
        '''
    else:
        print(f'err gcd_ms value: {gcd_ms} < 0')
    return sql

def sql_update_enchant_spell_trigger_chance(table, multi, cond, effect_type):
    return f'''
            update spellitemenchantment set
            EffectPointsMin_1=EffectPointsMin_1*{multi}, EffectPointsMin_2=EffectPointsMin_2*{multi},EffectPointsMin_3=EffectPointsMin_3*{multi}
            where ({cond});
    '''

def sql_query(table, cond):
    return f'''
        select DISTINCT s.entry id
        from {table} s
        INNER JOIN locales_spell l ON s.entry = l.entry
        WHERE {cond};
    '''

def sql_query_trigger(table, cond):
    sql_dbc = f'''
        select EffectTriggerSpell1 from {table} s
        where {cond}
    '''
    if table == 'spell':
        sql = sql_dbc
    else:
        return ''
    return sql



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
        elif sql_type == 'gcd_time':
            sql_update = sql_update_gcd_time
        elif sql_type == 'enchant_spell_trigger_chance':
            sql_update = sql_update_enchant_spell_trigger_chance
        else:
            raise Exception('sql_type error')

        if table == 'spell':
            instance.execute_multi_sqls(sql_update(table, multi, condition, effect_type))

    # x倍率 放大 数值
    def mod_dmg(self, spellnames):
        cond = self._cond
        for spellname, multi_rate in spellnames.items():
            if spellname in cond.keys():
                self.mod_effect_on_spell('spell',          multi_rate, cond[spellname], 2)

    # x倍率 放大 多倍攻击次数
    def mod_talent_extra_attack(self, spellnames):
        cond = self._cond
        for spellname, multi_rate in spellnames.items():
            if spellname in cond.keys():
                self.mod_effect_on_spell('spell',          multi_rate, cond[spellname], 19)

    # x倍率 放大 法术效果
    def mod_talent_dummy(self, spellnames):
        cond = self._cond
        for spellname, multi_rate in spellnames.items():
            if spellname in cond.keys():
                self.mod_effect_on_spell('spell',          multi_rate, cond[spellname], 3)

    # x倍率 放大 法术效果
    def mod_talent(self, spellnames):
        cond = self._cond
        for spellname, multi_rate in spellnames.items():
            if spellname in cond.keys():
                self.mod_effect_on_spell('spell',          multi_rate, cond[spellname], 6)

    # x倍率 dot间隔
    def mod_dot_interval(self, spellnames):
        cond = self._cond
        for spellname, multi_rate in spellnames.items():
            if spellname in cond.keys():
                self.mod_effect_on_spell('spell',          multi_rate, cond[spellname], 6, sql_type='dot_interval')

    # x倍率 触发几率
    def mod_trigger_chance(self, spellnames):
        cond = self._cond
        for spellname, multi_rate in spellnames.items():
            if spellname in cond.keys():
                self.mod_effect_on_spell('spell',          multi_rate, cond[spellname], 6, sql_type='trigger_chance')

    # 更改 持续时间
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
                else:
                    print(f'WARNING: {spellname} duration {duration} not in duration_dict')

    # 更改 可以触发的次数，（如闪电盾 3次->60次）
    def mod_trigger_time(self, spellnames):
        cond = self._cond
        for spellname, trigger_time in spellnames.items():
            if spellname in cond.keys():
                self.mod_effect_on_spell('spell',          trigger_time, cond[spellname], 6, sql_type='trigger_time')

    # 更改 冷却时间
    def mod_cooldown_time(self, spellnames):
        cond = self._cond
        for spellname, cooldown_time in spellnames.items():
            if spellname in cond.keys():
                self.mod_effect_on_spell('spell',          cooldown_time, cond[spellname], 6, sql_type='cooldown_time')

    # 更改 施法时间， 专业使用此函数
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
        else:
            # print(f'WARNING: cast_time {cast_time} not in duration_dict')
            raise Exception(f'WARNING: cast_time {cast_time} not in duration_dict')

    # 更改 施法时间， 职业技能使用此函数
    def mod_cast_time(self, spellnames):
        cond = self._cond
        for spellname, cast_time in spellnames.items():
            if spellname in cond.keys():
                self.mod_cast_time_with_condition(cast_time, cond[spellname])

    # 更改 gcd 时间
    def mod_gcd_time(self, spellnames):
        cond = self._cond
        for spellname, gcd_time in spellnames.items():
            if spellname in cond.keys():
                self.mod_effect_on_spell('spell',          gcd_time, cond[spellname], 6, sql_type='gcd_time')

    # x倍率 触发技能的 效果
    def mod_trigger(self, spellnames):
        cond = self._cond
        for spellname, multi_rate in spellnames.items():
            if spellname in cond.keys():
                table = 'spell'
                id_name = "s.id"
                results = self._instance.execute_sql_with_retval(sql_query_trigger(table, cond[spellname]))
                entry_condition_str = ' or '.join([f"{id_name}={item[0]}" for item in results])
                self.mod_effect_on_spell(table,          multi_rate, entry_condition_str, 6)

    def mod_enchant_spell_trigger_chance(self, spellnames):
        cond = self._cond
        for spellname, multi_rate in spellnames.items():
            if spellname in cond.keys():
                condition = cond[spellname]
                results = self._instance.execute_sql_with_retval(f'select EffectMiscValue1 from spell s where ({condition})')
                entry_condition_str = ' or '.join([f"id={item[0]}" for item in results])
                self.mod_effect_on_spell('spell',          multi_rate, entry_condition_str, 6, sql_type='enchant_spell_trigger_chance')
# 减少技能cd
# 天赋 effectItemType & spellfamilyflags 有值， 位于方式绑定技能
# vmangos_mangos: spellfamilyName
# vmangos_mangos: spellfamilyflags
# dbc: spellfamilyName
# dbc: spellfamilyflag1
# dbc: spellfamilyflag2

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

# struct SpellItemEnchantmentEntry
# {
#     uint32      ID;                                         // 0        m_ID
#     uint32      type[3];                                    // 1-3      m_effect[3]
#     uint32      amount[3];                                  // 4-6      m_effectPointsMin[3]
#     //uint32      amount2[3]                                // 7-9      m_effectPointsMax[3]
#     uint32      spellid[3];                                 // 10-12    m_effectArg[3]
#     char*       description[8];                             // 13-20    m_name_lang[8]
#                                                             // 21 string flags
#     uint32      aura_id;                                    // 22       m_itemVisual
#     uint32      slot;                                       // 23       m_flags
# };

# // Use first rank to access spell item enchant procs
# float ppmRate = sSpellMgr.GetItemEnchantProcChance(spellInfo->Id);
# float chance = ppmRate
#                 ? GetPPMProcChance(WeaponSpeed, ppmRate)
#                 : pEnchant->amount[s] != 0
#                     ? float(pEnchant->amount[s])
#                     : GetPPMProcChance(WeaponSpeed, 1.0f);
    def mod_enchant_spell_trigger_chance(self, spellnames):
        self._helper.search_enchant_spell_trigger_chance(spellnames)
        self._mod.mod_enchant_spell_trigger_chance(spellnames)
        self._helper.search_enchant_spell_trigger_chance(spellnames)
    def mod_trigger(self, spellnames):
        self._helper.search_triggered_spell(spellnames)
        self._mod.mod_trigger(spellnames)
        self._helper.search_triggered_spell(spellnames)

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
            ,CastingTimeIndex cast_idx,RecoveryTime cd, CategoryRecoveryTime cd2, StartRecoveryCategory gcd_c,StartRecoveryTime gcd,effectItemType1 eit,spellfamilyflags1 sff1,spellfamilyflags1 sff2,spellFamilyName sfn
            # ,SpellDescription4 d
            from spell s
            WHERE {condition};
        '''
        self._instance.fast_select(sql)

    def search(self, spellnames=[], table=''):
        cond = self._cond
        for spellname in spellnames:
            if table == 'spell':
                if spellname in cond:
                    self._search(cond[spellname])
            elif table == '':
                if spellname in cond:
                    self._search(cond[spellname])

    def search_triggered_spell(self, spellnames):
        cond = self._cond
        for spellname, multi_rate in spellnames.items():
            if spellname in cond.keys():
                table = 'spell'
                id_name = "s.id"
                results = self._instance.execute_sql_with_retval(sql_query_trigger(table, cond[spellname]))
                entry_condition_str = ' or '.join([f"{id_name}={item[0]}" for item in results])
                self._search(entry_condition_str)

    def search_with_cond(self, condition, table=''):
        if table == 'spell':
            self._search(condition)
        elif table == '':
            self._search(condition)

    def search_spell_by_class(self, clz, table='', verbose=False):
        clz
        clz_id = 11
        sql_dbc = f'''
            select {"s.id," if verbose else ""} s.SpellName4 as name,{"s.SpellRank4 as lvl," if verbose else ""} effectItemType1 eit,spellfamilyflags1 sff1,spellfamilyflags1 sff2,spellFamilyName sfn
            from spell s
            where spellFamilyName={clz_id} and effectItemType1=0;
            group by spellfamilyflags1
            order by spellfamilyflags1 asc
            '''
        sql = sql_dbc
        self._instance.fast_select(sql)

    def _search_affected_spell_by_talent(self, condition):
        sql = f'''
            select s.id,s.SpellName4 as name,s.SpellRank4 as lvl,s.Effect1 as e1,s.Effect2 as e2,s.Effect3 as e3,s.EffectBasePoints1 as base1,s.EffectBasePoints2 as base2,s.EffectBasePoints3 as base3
            ,s.effectapplyauraname1 as aura1,s.effectapplyauraname2 as aura2,s.effectapplyauraname3 as aura3
            ,EffectAmplitude1 as amp1,EffectAmplitude2 as amp2
            ,DurationIndex dur_idx
            ,EffectTriggerSpell1 trig1,procchance trig_c,procflags proc_f,ProcCharges trig_t,EffectMiscValue1 as misc1
            ,CastingTimeIndex cast_idx,RecoveryTime cd, CategoryRecoveryTime cd2, StartRecoveryCategory gcd_c,StartRecoveryTime gcd,effectItemType1 eit,spellfamilyflags1 sff1,spellfamilyflags1 sff2,spellFamilyName sfn
            # ,SpellDescription4 d
            from spell s
            INNER JOIN (
                SELECT s.SpellFamilyName _SpellFamilyName, s.effectItemType1 _effectItemType1
                FROM spell s
                WHERE {condition} limit 1
            ) s2 ON s.spellFamilyName = s2._SpellFamilyName
                AND (s.spellfamilyflags1 & s2._effectItemType1) != 0;
        '''
        self._instance.fast_select(sql)

    def search_affected_spell_by_talent(self, spellnames, table=''):
        cond = self._cond
        for spellname in spellnames:
            if table == 'spell':
                if spellname in cond:
                    self._search_affected_spell_by_talent(cond[spellname])
            elif table == '':
                self._search_affected_spell_by_talent(cond[spellname])

    def search_enchant_spell_trigger_chance(self, spellnames, table=''):
        cond = self._cond
        for spellname in spellnames.keys():
            if spellname in cond:
                sql = f'''
                    select id, EnchantmentType_1,EffectPointsMin_1,EffectPointsMax_1,EffectArg_1,Name_deDE,Name_enCN,Name_zhCN,Name_enTW,Name_Mask,ItemVisual,Flags
                    from spellitemenchantment where id in (
                        select EffectMiscValue1 from spell s where ({cond[spellname]})
                    );
                '''
                self._instance.fast_select(sql)

    def search_spell_by_enchant_spell(self, spellname, table=''):
        cond = self._cond
        sql_dbc = f'''
            select s.id,s.SpellName4 as name,s.SpellRank4 as lvl,s.Effect1 as e1,s.Effect2 as e2,s.Effect3 as e3,s.EffectBasePoints1 as base1,s.EffectBasePoints2 as base2,s.EffectBasePoints3 as base3
                ,s.effectapplyauraname1 as aura1,s.effectapplyauraname2 as aura2,s.effectapplyauraname3 as aura3
                ,EffectAmplitude1 as amp1,EffectAmplitude2 as amp2
                ,DurationIndex dur_idx
                ,EffectTriggerSpell1 trig1,procchance trig_c,procflags proc_f,ProcCharges trig_t,EffectMiscValue1 as misc1
                ,CastingTimeIndex cast_idx,RecoveryTime cd, CategoryRecoveryTime cd2, StartRecoveryCategory gcd_c,StartRecoveryTime gcd,effectItemType1 eit,spellfamilyflags1 sff1,spellfamilyflags1 sff2,spellFamilyName sfn
                from spell s
                join (
                    select EffectArg_1 id from spellitemenchantment ench
                    join spell s on s.EffectMiscValue1=ench.id
                    where ({cond[spellname]})
                ) s1 on s1.id=s.id;
        '''
        sql = sql_dbc
        self._instance.fast_select(sql)

# enum SpellFamily
# {
#     SPELLFAMILY_GENERIC     = 0,
#     SPELLFAMILY_UNK1        = 1,                            // events, holidays
#     // 2 - unused
#     SPELLFAMILY_MAGE        = 3,
#     SPELLFAMILY_WARRIOR     = 4,
#     SPELLFAMILY_WARLOCK     = 5,
#     SPELLFAMILY_PRIEST      = 6,
#     SPELLFAMILY_DRUID       = 7,
#     SPELLFAMILY_ROGUE       = 8,
#     SPELLFAMILY_HUNTER      = 9,
#     SPELLFAMILY_PALADIN     = 10,
#     SPELLFAMILY_SHAMAN      = 11,
#     SPELLFAMILY_UNK2        = 12,
#     SPELLFAMILY_POTION      = 13,
#     // 14 - unused
#     SPELLFAMILY_DEATHKNIGHT = 15,
#     // 16 - unused
#     SPELLFAMILY_UNK3        = 17
# };