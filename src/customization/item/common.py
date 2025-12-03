class Helper:
    def __init__(self, instance):
        self._instance = instance
    def rough_stone_finder(self):
        sql = """
            select i.entry,i.name,i.class,i.subclass from item_template i
            # limit 10;
            # where i.name like "虎%";
            WHERE i.class = 3 AND i.subclass = 7;
        """
        self._instance.fast_select(sql)

# 合成宝石
def make_merge_jewel(instace):
    instace.copy_item(18262, 81000)
    sql = '''
        CREATE TABLE IF NOT EXISTS item_up(id INT UNSIGNED NOT NULL,id1 INT UNSIGNED,id2 INT UNSIGNED,amount INT UNSIGNED,amount1 INT UNSIGNED,amount2 INT UNSIGNED,upid INT UNSIGNED, PRIMARY KEY (id));
        update item_template set class=12,quality=1,name='合成宝石',itemlevel=1,requiredlevel=1,buyprice=0,sellprice=0,spellid_1=13262 where entry=81000;
    '''
    instace.execute_multi_sqls(sql)

def item_template_localeZH_1(instace):
    # sql = 'UPDATE item_template AS it JOIN locales_item AS li ON it.entry = li.entry SET it.name = li.name_loc4;'
    sql = '''
        UPDATE item_template AS it
        JOIN locales_item AS li
            ON it.entry = li.entry
        SET
            it.name =
                CASE
                    -- 1. 检查 name_loc4 (如果非NULL且非空字符串)
                    WHEN li.name_loc4 IS NOT NULL AND li.name_loc4 != '' THEN li.name_loc4

                    -- 2. 否则，检查 name_loc5 (如果非NULL且非空字符串)
                    WHEN li.name_loc5 IS NOT NULL AND li.name_loc5 != '' THEN li.name_loc5

                    -- 3. 否则 (如果 loc4 和 loc5 都为空)，保持原值
                    ELSE it.name
                END;
    '''
    instace.execute_multi_sqls(sql)
def item_template_localeZH_2(instace):
    sql = 'UPDATE item_template AS it JOIN item_template_locale AS itl ON it.entry = itl.id and itl.locale="zhCN" SET it.name = itl.name;'
    instace.execute_multi_sqls(sql)
# 修改可堆叠物品的数量
def mod_stackable_item(instance, max_stack_num=255):
    sql = f'update item_template it set stackable={max_stack_num} where stackable>1;'
    instance.execute_multi_sqls(sql)

def customize(instance):
    print(f'{__name__:<45}start to customize!')
    # 合成宝石
    # instance.make_merge_jewel(instance)

    # 汉化 item_template
    item_template_localeZH_1(instance)
    # item_template_localeZH_2(instance)

    # 修改可堆叠物品的数量 至255
    mod_stackable_item(instance, 255)

    helper = Helper(instance)
    # helper.rough_stone_finder()
