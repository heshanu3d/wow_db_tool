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

    def search_vendor4selled_by_npcid(self, entry):
        sql = f'''
            select n.*,i.name,i.buy_count,i.buy_price,i.sell_price from npc_vendor n
            inner join item_template i on n.item=i.entry
            where n.entry={entry};
        '''
        self._instance.fast_select(sql)

    def get_item_entry_by_name(self, name):
        sql = f'''
            select entry, name, description from item_template where name = "{name}";
        '''
        result = self._instance.execute_sql_with_retval(sql)
        if not result or len(result) != 1:
            print('get_item_entry_by_name get result!=1, ', 0 if not result else len(result))
            exit(1)
        return result[0][0]


def add_vendor_to_npc(instance, npc_entry, item_entry, free=True):
    result = instance.execute_sql_with_retval(f'SELECT IFNULL(MAX(slot), 0) + 1 FROM npc_vendor WHERE entry = {npc_entry};')
    slot = result[0][0]
    sqls = ''
    if free:
        sqls = sqls + f'UPDATE item_template SET sell_price=0, buy_price=0 WHERE entry = {item_entry};'
    sqls = sqls + f'''
        INSERT INTO npc_vendor (entry, slot, item) VALUES ({npc_entry}, {slot}, {item_entry});
    '''
    instance.execute_multi_sqls(sqls)

def add_vendor_npc(instance, old_npc_entry, new_npc_entry, new_guid, x, y, z, name, subname):
    instance.copy(old_npc_entry, new_npc_entry, 'creature_template', 'entry')
    result = instance.execute_sql_with_retval(f'select guid from creature where id={old_npc_entry};')
    if result:
        old_guid = result[0][0]
        instance.copy(old_guid, new_guid, 'creature', 'guid')
        sqls = f'''
            update creature set id={new_npc_entry},
            position_x={x},position_y={y},position_z={z}
            # position_x=-8902.506,position_y=-114.446,position_z=81.86
            where guid = {new_guid};
        '''
        if name is not None:
            sqls += f'update creature_template set name="{name}" where entry={new_npc_entry};'
        if subname is not None:
            sqls += f'update creature_template set subname="{subname}" where entry={new_npc_entry};'
        instance.execute_multi_sqls(sqls)

def add_vendor_npcs(instance, npc_info_lists):
    for npc in npc_info_lists:
        add_vendor_npc(instance, npc[0], npc[1], npc[2], npc[3], npc[4], npc[5], npc[6], npc[7])
        for item in npc[8]:
            add_vendor_to_npc(instance, npc[1], item)
        for item in npc[9]:
            add_vendor_to_npc(instance, npc[1], item, False)

def delete_npc_vendor(instance, npc_entry, item_entry):
    sqls = f'delete from npc_vendor where entry={npc_entry} and item={item_entry};'
    instance.execute_multi_sqls(sqls)

def delete_npc(instance, npc_entry):
    sqls = f'''
        delete from creature_template where entry={npc_entry};
        delete from creature where id={npc_entry};
    '''
    instance.execute_multi_sqls(sqls)

def delete_npcs(instance, npc_info_lists):
    for npc in npc_info_lists:
        delete_npc(instance, npc[1])
        for item in npc[8] + npc[9]:
            delete_npc_vendor(instance, npc[1], item)

def customize(instance):
    print(f'{__name__:<45}start to customize!')

    helper = Helper(instance)
    _item = helper.get_item_entry_by_name

    npc_info_lists = [
        #源entry 新entry  新guid      x           y      z        name           subname       item_free           item_not_setfree     
        (152,   20000,    310000, -8902.506, -114.446, 81.86, '丹尼尔修士11', '杂货供应商22', [4500], [_item('大地图腾'),_item('火焰图腾'),_item('水之图腾'),_item('空气图腾')]),
    ]
    

    # obsolete
    # delete_npc(instance, 20000)
    # add_vendor_npc(instance, 152, 20000, 310000, -8902.506, -114.446, 81.86)
    # helper.search_npc_by_name('丹尼尔')
    # helper.search_vendor4selled_by_npcid(20000)

    delete_npcs(instance, npc_info_lists)
    add_vendor_npcs(instance, npc_info_lists)


    for npc in npc_info_lists:
        helper.search_npc_by_name(npc[6])
        helper.search_vendor4selled_by_npcid(npc[1])


