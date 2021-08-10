import mysql.connector
import os
import uuid
import csv
db = mysql.connector.connect(host="localhost", user="root" , password="pass@123",database="VARDHAMAN_PARK")

def find_member(flat_number):
    sql='SELECT * FROM MEMBER';
    cursor=db.cursor();
    cursor.execute(sql)
    rows=cursor.fetchall()
    for row in rows:
        print(row)

def insert_member_details_by_file(file_path):
    print('Processing '+file_path)
    with open(file_path) as csv_file:
        csv_reader = csv.DictReader(csv_file, delimiter=',')
        cursor=db.cursor();
        for row in csv_reader:
            if len(str(row.get('Flat No.'))) >0 :
                building=str(row.get('Building')).rstrip()
                flat_number=int(str(row.get('Flat No.').rstrip()))
                name=row.get('Name of Resident')
                email=row.get('Email ID')
                flat_size = 0 if row.get('Flat Area in Sq Feet') == "" else int(str(row.get('Flat Area in Sq Feet')).rstrip())
                flat_type=str(row.get('BHK')).rstrip()
                find_sql='SELECT ID FROM MEMBER WHERE BUILDING=%s AND FLAT_NUMBER=%s'
                cursor.execute(find_sql,(building,flat_number ))
                existing=cursor.fetchone();
                sql=""
                vars=""
                if existing is None :
                    id=  str(uuid.uuid4())
                    sql='INSERT INTO MEMBER ( ID , BUILDING , FLAT_NUMBER , NAME ,EMAIL,FLAT_TYPE , FLAT_SIZE ) VALUES ( %s , %s  , %s , %s , %s , %s , %s )'
                    vars=(id, building, flat_number,name,email,flat_type,flat_size)
                else:
                    id=existing[0]
                    sql = 'UPDATE TABLE MEMBER SET NAME=%s ,EMAIL=%s , FLAT_TYPE=%s , FLAT_SIZE=$s  WHERE ID=%s '
                    vars = ( name, email, flat_type, flat_size,id)

                cursor.execute(sql,vars)
    db.commit()

if __name__ == '__main__':
    file_path='references'+os.path.sep+"May 2021_rev 00"+os.path.sep+"Dec-20-Table 1.csv"
    insert_member_details_by_file(file_path=file_path)