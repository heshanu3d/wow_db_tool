class Helper:
    def __init__(self, instance):
        self._instance = instance

    def search_npc_by_name(self, name):
        sql = f'''
            select c.entry,c.name,c.subname, c2.map,c2.position_x x,c2.position_y y,c2.position_z z from creature_template c
            inner join creature c2 on c2.id=c.entry
            where c.name like "%{name}%";
        '''
        self._instance.fast_select(sql)


    def search_npc_by_subname(self, subname):
        sql = f'''
            select c.entry,c.name,c.subname, c2.map,c2.position_x x,c2.position_y y,c2.position_z z from creature_template c
            inner join creature c2 on c2.id=c.entry
            where c.subname like "%{subname}%";
        '''
        self._instance.fast_select(sql)

    def search_weapon_trained_skill(self):
        sql = '''
            select n.spell,s.spellname4 from npc_trainer n
            join creature_template c on c.entry=n.entry
            join spell s on s.id=n.spell
            where c.subname like "%武器大师%" group by n.spell;
        '''
        self._instance.fast_select(sql)

    def search_trained_skill_by_entry(self, npc_entry):
        sql = f'''
            select s.spellname4,n.* from npc_trainer_template n
            join creature_template c on c.trainer_id=n.entry
            join spell s on s.id=n.spell
            where c.entry={npc_entry};
        '''
        self._instance.fast_select(sql)


def customize(instance):
    print(f'{__name__:<45}start to customize!')
    helper = Helper(instance)
    # helper.search_npc_by_subname('萨满祭司训练师')
    # helper.search_npc_by_subname('法师训练师')
    # helper.search_npc_by_subname('武器大师')
    # helper.search_trained_skill_by_entry(3173)
    # 3173  斯瓦特       萨满祭司训练师      1     307.114  -4839.91    10.6075
    # 7312  丁克                   法师训练师      0  -4614.48    -928.362   501.151

    # select n.* from npc_trainer_template n join creature_template c on c.trainer_id=n.entry where c.entry=

    # helper.search_weapon_trained_skill()