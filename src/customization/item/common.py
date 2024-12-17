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
    sql = 'UPDATE item_template AS it JOIN locales_item AS li ON it.entry = li.entry SET it.name = li.name_loc4;'
    instace.execute_multi_sqls(sql)
def item_template_localeZH_2(instace):
    sql = 'UPDATE item_template AS it JOIN item_template_locale AS itl ON it.entry = itl.id and itl.locale="zhCN" SET it.name = itl.name;'
    instace.execute_multi_sqls(sql)

def customize(instance):
    print(f'{__name__:<45}start to costomize!')
    # 合成宝石
    # instance.make_merge_jewel(instance)

    # 汉化 item_template
    # item_template_localeZH_1(instance)
    # item_template_localeZH_2(instance)

    helper = Helper(instance)
    # helper.rough_stone_finder()