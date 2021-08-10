import FlatPlugin
import os
import uuid
import csv
from datetime import datetime , timedelta
import Helper
import DBPlugin

db=DBPlugin.get_connection()

def find_flat(cursor,building,flat_number):
    #print("Looking for flat {} {}".format(building,str(flat_number)))
    find_sql = 'SELECT * FROM FLAT WHERE BUILDING=%s AND FLAT_NUMBER=%s'
    cursor.execute(find_sql, (building, flat_number))
    existing = cursor.fetchone();
    return existing

def add_flats():
    flats=Helper.get_flat_details()
    cursor = db.cursor(dictionary=True)
    for flat in flats:
        existing=find_flat(cursor,flat.get('BUILDING'),flat.get('FLAT_NUMBER'))
        if existing is None :
            Helper.insert_dict(cursor,'FLAT',flat)
        else:
            id=existing.get("ID")
            Helper.update_dict_by_id(cursor,'FLAT',flat,id)
    db.commit()