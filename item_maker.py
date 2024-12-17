from src import core, customization

if __name__ == "__main__":
    instance = core.Mysql()
    instance.debug = True
    instance.debug = False

    # instance.save_sql('item_update')
    # instance.gen_item_csv()

    # customization
    customization.profession.alchemy.customize(instance)
    customization.profession.black_smithing.customize(instance)
    customization.profession.enchantment.customize(instance)
    customization.profession.engineering.customize(instance)
    customization.profession.inscription.customize(instance)
    customization.profession.jewel.customize(instance)
    customization.item.common.customize(instance)
    customization.item.equipment.customize(instance)
    customization.dungeon.common.customize(instance)
    customization.dungeon.raid.customize(instance)
