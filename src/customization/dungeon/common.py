
# 取消副本进入限制(成就、任务、物品)
def remove_dungeon_requirements(instance):
    instance.backup_table('dungeon_access_requirements')
    instance.clear_table_content('dungeon_access_requirements')

def customize(instance):
    print(f'{__name__:<45}start to costomize!')
    # 取消副本进入限制(成就、任务、物品)
    # remove_dungeon_requirements(instance)