import datetime
import math

import xlsxwriter

import BillingService
import BuildingService
import DBPlugin
import PaymentService
from Domain import Settlement


def settle_bill_payment(cursor,flat):
    bills=BillingService.find_all_unsettle_bill(cursor,flat.ID)
    previous_outstanding =0
    previous_misc_bal =0
    previous_interest =0
    previous_advance =0
    #print(flat.OWNER)
    previous_misc_bal=0
    for bill in bills:
        bill.OUT_STANDING=previous_outstanding
        bill.INTEREST_CHARGE=previous_interest
        bill.ADVANCE_AMOUNT=previous_advance
        bill.MISC=bill.MISC+previous_misc_bal
        bill.generate()
        payments=PaymentService.find_all_inprogress_payment_between_date(cursor,flat_id=flat.ID,start=bill.BILLING_DATE,end=bill.DUE_DATE)
        outstanding=0
        interest=0
        advance_payment=bill.ADVANCE_AMOUNT
        misc_payment=0
        misc_bal=0
        interest = math.ceil((bill.OUT_STANDING * (18 / 100)) / 12)
        bill.INTEREST_CHARGE=interest
        #print("Billing Month {} | Outstanding : {} | Interest : {}".format(bill.BILLING_MONTH, previous_outstanding,
        #                                                                   interest))
        bill.generate()
        if len(payments)==0:
            outstanding=bill.TOTAL_PAYABLE
            misc_bal=bill.MISC
            maintenance_payment = 0
            misc_payment=0
        else:
            maintenance_payment=0
            misc_payment=0
            for payment in payments:
                comment=payment.COMMENT
                if comment is None:
                    comment=""
                if 'Maintenance'.lower() in comment.lower():
                    maintenance_payment=maintenance_payment+payment.AMOUNT
                else:
                    if 'CCTV'.lower() in comment.lower():
                      bill.MISC=3500
                      bill.COMMENT="CCTV Contribution of Rs : 3500"
                      misc_payment = misc_payment + payment.AMOUNT
                    else:
                      misc_payment=misc_payment+payment.AMOUNT
                payment.IS_PROCESSED = 1
                DBPlugin.update_dict_by_id(cursor, 'PAYMENT_HISTORY', payment.__dict__, payment.ID)
            #print("Maintenance Money : {} | Miscellanies : {}".format(maintenance_payment,misc_payment))
            maintenance_payment=maintenance_payment+bill.ADVANCE_AMOUNT
            if maintenance_payment > bill.TOTAL_PAYABLE:
                advance_payment=maintenance_payment-bill.TOTAL_PAYABLE
            if bill.TOTAL_PAYABLE > maintenance_payment:
                outstanding=bill.TOTAL_PAYABLE-maintenance_payment
            if bill.TOTAL_PAYABLE == maintenance_payment: outstanding=0
            if misc_payment > 0:
                if misc_payment > bill.MISC :
                    advance_payment=advance_payment+(misc_payment-bill.MISC)
                if misc_payment == bill.MISC:
                    misc_bal=0
                    bill.MISC=0
                if misc_payment < bill.MISC :
                    misc_bal = bill.MISC-misc_payment
                    bill.MISC=misc_bal
            else:
                misc_bal=bill.MISC
            #if bill.MISC>0:
            #   misc_bal=bill.MISC
        bill.MAINTENANCE_PAYMENT_RECEIVED=maintenance_payment
        bill.MISC_PAYMENT_RECEIVED=misc_payment
        bill.IS_SETTLED=1
        DBPlugin.update_dict_by_id(cursor,'BILL',bill.__dict__,bill.ID)
        previous_outstanding=outstanding
        previous_misc_bal=misc_bal
        previous_interest=interest
        previous_advance=advance_payment



def generate_bill(flats):
    db = DBPlugin.db
    draft_bills=[['BILLING MONTH' ,'OWNER','BUILDING','FLAT NO','AREA' ,
                 'NO OF TAP' , 'SERVICE CHARGES'
                , 'WATER CHARGES','SINKING_FUND' , 'REPAIR FUND'
                ,  'PARKING CHARGES' , 'INSURANCE CHARGE' , 'EMERGENCY FUND'
                ,  'SUB LETTING CHARGE' , 'MISC' , 'INTEREST ON LATE PAYMENT' , 'ADVANCE PAYMENT' , 'TOTAL PAYABLE' , 'LAST PAYMENT'
                 , 'LAST PAYMENT DATE'
                  ]]
    cursor = db.cursor(dictionary=True)
    billing_month=''
    for flat in flats:
        bill = BillingService.find_latest_bill(cursor=cursor,flat_id=flat.ID)
        payment=PaymentService.find_latest_payment(cursor=cursor,flat_id=flat.ID)
        payment_amt=0
        payment_dt=''
        billing_month=bill.BILLING_MONTH
        if payment is not None:
            payment_amt=payment.AMOUNT
            payment_dt=payment.PAYMENT_DATE
        draft_bill=[ bill.BILLING_MONTH,flat.OWNER,flat.BUILDING,flat.FLAT_NUMBER,flat.AREA,flat.WATER_CONNECTION,
                           bill.SERVICE_CHARGE , bill.WATER_CHARGE,bill.SINKING_FUND,bill.REPAIR_FUND,
                           bill.PARKING_CHARGE,bill.INSURANCE_CHARGE,bill.EMERGENCY_FUND , bill.SUB_LETTING_CHARGE ,
                           bill.MISC , bill.INSURANCE_CHARGE , bill.ADVANCE_AMOUNT ,  bill.TOTAL_PAYABLE  ,
                           payment_amt,payment_dt
                     ]
        draft_bills.append(draft_bill)
    file_path=("Maintanence-"+billing_month).upper()+".xlsx"
    workbook=xlsxwriter.Workbook(file_path)
    worksheet=workbook.add_worksheet()
    print('Data : '+str(len(draft_bills)))
    row=0
    for draft_bill in draft_bills:
      col=0
      for draft in draft_bill:
          worksheet.write(row,col,str(draft))
          col = col + 1
      row=row+1
    workbook.close()
    print('Bill Printed')


def find_last_settlement(cursor,flat_id):
    find_sql = 'SELECT * FROM SETTLEMENT WHERE FLAT_ID=%s ORDER BY SETTLEMENT_DATE DESC LIMIT 1'
    cursor.execute(find_sql, [flat_id])
    settlement = cursor.fetchone()
    if settlement is None :
        return None
    return Settlement(settlement)

def penalty_amt(payment_date,due_date,bill_amt):
    penalty=0
    if payment_date is None:
        penalty = ((bill_amt * (18 / 100)) / 12)
    else:
        if payment_date > due_date:
         penalty=((bill_amt*(18/100))/12)
    return math.ceil(penalty)

def amount_settlement(bill_amount , payment_amount,is_over_due):
    advance_amt = 0
    pending_amt = 0
    settled_amt=0
    advance_over_due=0
    settling_amt=bill_amount
    if bill_amount > payment_amount:
        settled_amt = payment_amount
        pending_amt = bill_amount - payment_amount
        advance_amt=0
    elif payment_amount > bill_amount:
        if is_over_due:
            advance_over_due = payment_amount - bill_amount
        advance_amt = 0
        settled_amt = bill_amount
        pending_amt=0
    else :
        if payment_amount == bill_amount:
            advance_amt = 0
            pending_amt = 0
            settled_amt = bill_amount
    return settled_amt ,settling_amt , pending_amt , advance_amt,advance_over_due



def add_settlement_detail(flat_id,bill_id,payment_id,actual_amt,
                          settled_amt,pending_amt,advance_amt,penalty,
                          billing_month ,  payment_month,settlement_date,advance_over_due):
    if settlement_date == None: settlement_date=datetime.datetime.now()
    settlement=\
        {
            "BILL_ID":bill_id,
            "FLAT_ID": flat_id,
            "PAYMENT_ID":payment_id,
            "ACTUAL_AMOUNT":actual_amt,
            'SETTLED_AMOUNT':settled_amt ,
            "PENDING_AMOUNT": pending_amt ,
            "ADVANCE_AMOUNT": advance_amt,
            "BILLING_MONTH":billing_month,
            "PAYMENT_MONTH": payment_month,
            "SETTLEMENT_DATE":settlement_date,
            "PENALTY":penalty,
            "ADVANCE_OVER_DUE_AMOUNT":advance_over_due

        }
    return settlement


def bill_payment():
    db = DBPlugin.db
    cursor = db.cursor(dictionary=True)
    cursor.execute("TRUNCATE TABLE BILL")
    cursor.execute("UPDATE PAYMENT_HISTORY SET IS_PROCESSED=0")
    flat=BuildingService.find_flat(cursor,'B-2',406)
    years_month = {2020: [8, 9, 10, 11, 12], 2021: [1, 2, 3, 4, 5, 6, 7]}
    BillingService.generate_bills(cursor,years_month,flat)
    BillingService.update_special_bill()
    db.commit()
    settle_bill_payment(cursor,flat)
    print('Settled')


def bill_payments():
    db = DBPlugin.db
    cursor = db.cursor(dictionary=True)
    cursor.execute("TRUNCATE TABLE BILL")
    cursor.execute("UPDATE PAYMENT_HISTORY SET IS_PROCESSED=0")
    flats=BuildingService.find_all_flats(cursor)
    counter=1
    for flat in flats:
        if flat.IS_RENTED==0:
            print(str(counter)+". " +flat.BUILDING+" / "+str(flat.FLAT_NUMBER )+" : "+flat.OWNER)
            years_month = {2020: [8, 9, 10, 11, 12], 2021: [1, 2, 3, 4, 5, 6, 7]}
            BillingService.generate_bills(cursor,years_month,flat)
            if flat.BUILDING =='B-2' and flat.FLAT_NUMBER==406:
                BillingService.update_special_bill()
            july_bill=BillingService.find_bill_for_month(cursor,'JULY-2020',flat.ID)
            july_bill.DUE_DATE=datetime.datetime(2020, 9, 30)
            DBPlugin.update_dict_by_id(cursor,'BILL',july_bill.__dict__,july_bill.ID)
            settle_bill_payment(cursor, flat)
            db.commit()
            counter=counter+1
    print('Bill Settled')
    generate_bill(flats)


def main():
    bill_payments()





if __name__ == '__main__':
    main()