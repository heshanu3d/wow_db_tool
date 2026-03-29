from src import core, customization

if __name__ == "__main__":
    instance = core.Mysql()
    instance.debug = True
    # instance.debug = False

    # instance.save_sql('item_update')
    # instance.gen_item_csv()

    # customization
    # customization.profession.alchemy.customize(instance)
    # customization.profession.black_smithing.customize(instance)
    # customization.profession.enchantment.customize(instance)
    # customization.profession.engineering.customize(instance)
    # customization.profession.inscription.customize(instance)
    # customization.profession.jewel.customize(instance)
    # customization.item.equipment.customize(instance)
    # customization.dungeon.common.customize(instance)
    # customization.dungeon.raid.customize(instance)
    # customization.spell.rogue.customize(instance)

    # item customization
    # customization.item.common.customize(instance)

    # creature customization
    # customization.creature.common.customize(instance)
    # customization.creature.vendor.customize(instance)
    # customization.creature.trainer.customize(instance)

    # quest customization
    # customization.quest.common.customize(instance)

    # profession customization
    # customization.profession.common.customize(instance)
    # customization.profession.tailor.customize(instance)

    # class customization
    # customization.spell.rogue.customize(instance)
    # customization.spell.dk.customize(instance)
