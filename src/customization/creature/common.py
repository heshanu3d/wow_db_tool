class Helper:
    def __init__(self, instance):
        self._instance = instance
    def xxx(self):
        sql = """
        """
        self._instance.fast_select(sql)

def creature_template_localeZH(instace):
    sql = '''
        UPDATE creature_template AS c
        JOIN locales_creature AS lc
            ON c.entry = lc.entry
        SET
            c.name =
                CASE
                    -- 1. 检查 name_loc4 (如果非NULL且非空字符串)
                    WHEN lc.name_loc4 IS NOT NULL AND lc.name_loc4 != '' THEN lc.name_loc4

                    -- 2. 否则，检查 name_loc5 (如果非NULL且非空字符串)
                    WHEN lc.name_loc5 IS NOT NULL AND lc.name_loc5 != '' THEN lc.name_loc5

                    -- 3. 否则 (如果 loc4 和 loc5 都为空)，保持原值
                    ELSE c.name
                END,
            c.subname =
                CASE
                    -- 1. 检查 subname_loc4 (如果非NULL且非空字符串)
                    WHEN lc.subname_loc4 IS NOT NULL AND lc.subname_loc4 != '' THEN lc.subname_loc4

                    -- 2. 否则，检查 subname_loc5 (如果非NULL且非空字符串)
                    WHEN lc.subname_loc5 IS NOT NULL AND lc.subname_loc5 != '' THEN lc.subname_loc5

                    -- 3. 否则 (如果 loc4 和 loc5 都为空)，保持原值
                    ELSE c.subname
                END;
    '''
    instace.execute_multi_sqls(sql)
def customize(instance):
    print(f'{__name__:<45}start to customize!')

    # 汉化 creature_template
    creature_template_localeZH(instance)

    helper = Helper(instance)
