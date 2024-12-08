import mysql.connector, csv, time, re
from mysql.connector import Error
from functools import wraps

from src import core
from src import customization

if __name__ == "__main__":
    instance = core.Mysql()
    instance.debug = True
    instance.debug = False

    # instance.save_sql('item_update')
    # instance.gen_item_csv()

    # customization
    customization.profession.inscription.customize(instance)
    customization.profession.jewel.customize(instance)
    customization.profession.alchemy.customize(instance)
    customization.item.equipment.customize(instance)
    customization.dungeon.common.customize(instance)
    customization.dungeon.raid.customize(instance)
