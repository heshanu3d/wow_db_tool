def mod_quest_request_item_count(instance):

    # instance.fast_select(f'''select title, RequiredItemCount1 cnt1, RequiredItemCount2 cnt2, RequiredItemCount3 cnt3, RequiredItemCount4 cnt4, RequiredItemCount5 cnt5, RequiredItemCount6 cnt6
    #     from quest_template 
    #     where title like "%完美宝石%" or title like "%又是铲齿鹿汤%" or title like "%非标准炮弹%";
    # ''')
    sql = ''' UPDATE quest_template
                SET 
                    RequiredItemCount1 = LEAST(RequiredItemCount1, 5),
                    RequiredItemCount2 = LEAST(RequiredItemCount2, 5),
                    RequiredItemCount3 = LEAST(RequiredItemCount3, 5),
                    RequiredItemCount4 = LEAST(RequiredItemCount4, 5),
                    RequiredItemCount5 = LEAST(RequiredItemCount5, 5),
                    RequiredItemCount6 = LEAST(RequiredItemCount6, 5);
    '''
    instance.execute_multi_sqls(sql)

def customize(instance):
    print(f'{__name__:<45}start to customize!')

    # 将任务所需的物品数量限制在5个，避免玩家需要收集过多的物品来完成任务，提升游戏体验。
    mod_quest_request_item_count(instance)



# quest_template