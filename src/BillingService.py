import Helper
import os
import DBPlugin
import FlatPlugin
from datetime import datetime , timedelta
from dateutil import relativedelta

db=DBPlugin.db

def add_back_dated_bill():
    basePath = 'references' + os.path.sep + "bill"
    files = os.listdir(basePath)
    #files=['October-2020.csv']
    for file in files:
        file_path = basePath + os.path.sep + file
        bill_month=str(file.split(".")[0]).upper()
        print('Processing ' + file_path)
        rows = Helper.csv_dict(file_path)
        cursor = db.cursor(dictionary=True)
        for row in rows:
            try:
                flat = FlatPlugin.find_flat(cursor, row.get('Building'), row.get('Flat No.'))
                is_refuge=bool(flat.get('IS_REFUGE'))
                if not is_refuge :
                    flat_id = flat.get('ID')
                    misc=row.get('5 months Installment')
                    date=datetime.strptime("10-"+bill_month, '%d-%B-%Y')
                    interest=row.get('Interest')
                    if interest is None or len(interest)==0 :
                        interest=0
                    interest=float(interest)
                    if misc is not None and len(str(misc).rstrip())>0:
                        misc=float(misc)
                    else : misc=float(0)
                    service_charge=float(flat.get('AREA')) * 3
                    sinking_fund =float(0)
                    repair_fund =float(0)
                    emergency_fund =float(0)
                    insurance =float(0)
                    water_charges=float(0)
                    parking_charges=float(0)
                    sub_letting_charges=float(0)
                    comment="1. Total Arreares for April 2020 to June 2020 is "+str(misc*5)+". \n  2. 5 Easy Installment of arrears is "+str(misc)+" ."
                    due_date = Helper.next_month_date(date)
                    if '2021' in bill_month :
                        service_charge=float(Helper.get_value(row,'Common charges per flat',0))
                        sinking_fund=float(Helper.get_value(row,'Sinking Fund',0))
                        repair_fund=float(Helper.get_value(row,'Repair Fund',0))
                        emergency_fund=float(Helper.get_value(row,'Emergency Fund',0))
                        insurance=float(Helper.get_value(row,'Insurance Fund',0))
                        water_charges=float(Helper.get_value(row,'Water Charges',0))
                        parking_charges = float(Helper.get_value(row,'Parking Charges',0))
                        sub_letting_charges=float(Helper.get_value(row,'Sub Letting Charges',0))
                        comment='Maintenance Bill for '+str(date)
                    bill = Helper.get_back_dated_bill_bo(flat_id, service_charge, water_charges
                                                         , sinking_fund, repair_fund, parking_charges
                                                         , insurance, sub_letting_charges, bill_month, due_date, emergency_fund, misc,
                                                         comment,
                     interest, date)
                    existing=find_bill_for_month(cursor,bill_month,flat_id)
                    if existing is None:
                        Helper.insert_dict(cursor, 'BILL', bill)
                    else:
                        bill_id = existing.get('ID')
                        Helper.update_dict_by_id(cursor, 'BILL', bill,bill_id)

            except Exception as e:
                print(row)
                print(e)
                raise e
    db.commit()


def find_bill_for_month(cursor,billing_month,flat_id):
    find_sql = 'SELECT * FROM BILL WHERE BILLING_MONTH=%s AND FLAT_ID=%s'
    cursor.execute(find_sql, (billing_month, flat_id))
    existing = cursor.fetchone();
    return existing


def main():
    add_back_dated_bill()


if __name__ == '__main__' : main()