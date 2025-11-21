

class Helper:
    def __init__(self, instance, cond):
        self._instance = instance
        self._cond = cond
    
    def _get_trainer_id(self, condition):
        sql = f'''
                select c.entry,l.name_loc4,l.subname_loc4, c2.map,c2.position_x x,c2.position_y y,c2.position_z z from creature_template c
                inner join locales_creature l on c.entry=l.entry
                inner join creature c2 on c2.id=c.entry
                WHERE {condition};
        '''
        results = self._instance.execute_sql_with_retval(sql)
        if results is None:
            print(f'sql execute failed:\n    {sql}')
            return

        trainer_id = []
        for result in results:
            trainer_id.append(result[0])
        return trainer_id

    def _get_trainer_spell(self, npc_entry):
        sql = f'''
                select s.id,s.spellname4,s.castingtimeindex,s.effecttriggerspell1,t.castingtimeindex from spell s
                join npc_trainer n on s.id=n.spell and n.entry={npc_entry} and n.reqskill=197
                join spell t on t.id=s.effecttriggerspell1;
        '''
        results = self._instance.execute_sql_with_retval(sql)
        if results is None:
            print(f'sql execute failed:\n    {sql}')
            return
        
        spells = []
        for result in results:
            spells.append(result[3])
        return spells

    def _search_trainer(self, condition):
        sql = f'''
                select c.entry,l.name_loc4,l.subname_loc4, c2.map,c2.position_x x,c2.position_y y,c2.position_z z from creature_template c
                inner join locales_creature l on c.entry=l.entry
                inner join creature c2 on c2.id=c.entry
                WHERE {condition};
        '''
        self._instance.fast_select(sql)
    def _search_trainer_spell(self, npc_entry):
        sql = f'''
                select s.id,s.spellname4,s.castingtimeindex,s.effecttriggerspell1,t.castingtimeindex from spell s
                join npc_trainer n on s.id=n.spell and n.entry={npc_entry} and n.reqskill=197
                join spell t on t.id=s.effecttriggerspell1;
        '''
        self._instance.fast_select(sql)

    # 获取 指定 subname 的职业训练师 的技能, eg: 大师级裁缝
    def get_trainer_spell(self, npc_subname):
        trainer_ids = self._get_trainer_id(self._cond[npc_subname])

        spells = []
        if len(trainer_ids) > 0:
            spells = spells + self._get_trainer_spell(trainer_ids[0])

        return spells

    def get_trainer_spell_cond(self, npc_subname):
        spells = self.get_trainer_spell(npc_subname)
        spells_condition = ' or '.join([f"s.id={item}" for item in spells])
        return f"({spells_condition}) and s.castingtimeindex > 1"
