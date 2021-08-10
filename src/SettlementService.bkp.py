import datetime

import BuildingService
import DBPlugin
import BillingService
import PaymentService
from Domain import Flat , Settlement
import Helper
import math
import xlsxwriter
import os


def settlement_service(cursor,flat):
    bills=BillingService.find_all_unsettle_bill(cursor,flat.ID)
    previous_outstanding =0
    previous_misc_bal =0
    previous_interest =0
    previous_advance =0
    print(flat.OWNER)
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
        advance_payment=0
        misc_payment=0
        misc_bal=0
        interest = math.ceil((bill.OUT_STANDING * (18 / 100)) / 12)
        bill.INTEREST_CHARGE=interest
        print("Billing Month {} | Outstanding : {} | Interest : {}".format(bill.BILLING_MONTH, previous_outstanding,
                                                                           interest))
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
                           bill.MISC , bill.INSURANCE_CHARGE , bill.CARRY_FORWARD_AMOUNT ,  bill.TOTAL_PAYABLE   ,
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

def settle_payment(building,flat_number):
    db = DBPlugin.db
    cursor = db.cursor(dictionary=True)
    flat=BuildingService.find_flat(cursor=cursor, building=building, flat_number=flat_number)
    bills = BillingService.find_all_unsettle_bill(cursor, flat.ID)
    for bill in bills:
        #payments = PaymentService.find_all_inprogress_payment_till_date(cursor, flat_id=flat.ID, date=bill.DUE_DATE)
        #print(bill.BILLING_MONTH)
        advance_over_due=0
        last_settlement=find_last_settlement(cursor,flat.ID)
        if last_settlement is not None:
            bill.OUT_STANDING=last_settlement.PENDING_AMOUNT
            bill.ADVANCE_AMOUNT=last_settlement.ADVANCE_AMOUNT
            bill.INTEREST_CHARGE=last_settlement.PENALTY
            bill.OVER_DUE_ADVANCE_AMOUNT=last_settlement.ADVANCE_OVER_DUE_AMOUNT
            bill.generate()
            advance_over_due=last_settlement.ADVANCE_OVER_DUE_AMOUNT
            #print(advance_over_due)
        payments=PaymentService.find_all_inprogress_payment(cursor,flat.ID)
        no_payment=len(payments)
        if no_payment > 0:
            for payment in payments:
                penalty=penalty_amt(payment.PAYMENT_DATE,bill.DUE_DATE,bill.TOTAL_PAYABLE)
                if penalty > 0: bill.OUT_STANDING = bill.TOTAL_PAYABLE
                bill.generate()
                is_over_due=payment.PAYMENT_DATE>bill.DUE_DATE

                payment.PREVIOUS_ADV_AMT =  advance_over_due
                print('[ Bill = {} | Payment = {} | Over Due : {} ]'.format(bill.TOTAL_PAYABLE,payment.AMOUNT,advance_over_due))
                total_payemnt_amount= payment.AMOUNT+advance_over_due
                settled_amt , settling_amt , pending_amt , advance_amt,advance_over_due=amount_settlement(bill.TOTAL_PAYABLE,total_payemnt_amount,is_over_due)
                settlement=add_settlement_detail(flat.ID,bill.ID,payment.ID,bill.TOTAL_PAYABLE ,
                                                 settled_amt,pending_amt,advance_amt,penalty,
                                                 bill.BILLING_MONTH,payment.MONTH,payment.PAYMENT_DATE,advance_over_due)
                DBPlugin.insert_dict(cursor,'SETTLEMENT',settlement)
                payment.IS_PROCESSED=1
                DBPlugin.update_dict_by_id(cursor, 'PAYMENT_HISTORY', payment.__dict__,payment.ID)
                db.commit()
                break;
        else:
            payment_id=0
            is_over_due = True
            penalty = penalty_amt(None, bill.DUE_DATE, bill.TOTAL_PAYABLE)
            if penalty >0:bill.OUT_STANDING=bill.TOTAL_PAYABLE
            bill.generate()
            payment_amount=advance_over_due
            settled_amt, settling_amt, pending_amt, advance_amt ,advance_over_due= amount_settlement(bill.TOTAL_PAYABLE, payment_amount,is_over_due)
            settlement={}
            settlement = add_settlement_detail(flat.ID, bill.ID, payment_id, bill.TOTAL_PAYABLE,
                                               settled_amt, pending_amt, advance_amt, penalty,
                                               bill.BILLING_MONTH,'-' , None,advance_over_due)
            DBPlugin.insert_dict(cursor, 'SETTLEMENT', settlement)
            #payment.IS_PROCESSED = 1
            #DBPlugin.update_dict_by_id(cursor, 'PAYMENT_HISTORY', payment.__dict__, payment.ID)
            db.commit()
        bill.IS_SETTLED=1
        DBPlugin.update_dict_by_id(cursor, 'BILL', bill.__dict__,bill.ID)
        db.commit()

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

def settle_bill(building, flat_number):
    db = DBPlugin.db
    cursor = db.cursor(dictionary=True)
    flat = BuildingService.find_flat(cursor=cursor, building=building, flat_number=flat_number)
    bills = BillingService.find_all_unsettle_bill(cursor, flat.ID)
    out_standing=0
    interest_on_out_standing=0
    carry_forward=0
    for bill in bills:
        print(bill.BILLING_MONTH)
        payments = PaymentService.find_all_inprogress_payment_till_date(cursor, flat_id=flat.ID, date=bill.DUE_DATE)

        amount_paid=carry_forward
        bill.OUT_STANDING=out_standing
        bill.ADVANCE_AMOUNT=carry_forward
        bill.INTEREST_CHARGE=interest_on_out_standing
        updated_payments=[]
        for payment in payments:
            amount_paid=amount_paid+payment.AMOUNT
            payment.IS_PROCESSED = 1
            DBPlugin.update_dict_by_id(cursor, 'PAYMENT_HISTORY', payment.__dict__, payment.ID)
            settlement = add_settlement_detail(flat_id=flat.ID, bill_id=bill.ID, payment_id=payment.ID,
                                               actual_amt=bill.TOTAL_PAYABLE,
                                               settled_amt=payments_made_after_due_date, pending_amt=out_standing,
                                               advance_amt=carry_forward)
            DBPlugin.insert_dict(cursor,'SETTLEMENT',settlement)
            db.commit()
            #db.commit()
        next_bill_generation_date=Helper.add_no_days_to_date(bill.DUE_DATE,no_days=10)
        payments_made_after_due_date=PaymentService.find_all_inprogress_payment_between_date(cursor, flat_id=flat.ID, start=bill.DUE_DATE,end=next_bill_generation_date.date())
        amount_paid_after_due_date = 0
        for payment in payments_made_after_due_date:
            amount_paid_after_due_date=amount_paid_after_due_date+payment.AMOUNT
            payment.IS_PROCESSED = 1
            #flat_id, bill_id, payment_id, actual_amt, settling_amt, pending_amt, advance_amt
            DBPlugin.update_dict_by_id(cursor, 'PAYMENT_HISTORY', payment.__dict__, payment.ID)

        bill_amount=bill.TOTAL_PAYABLE
        bill_amount_gt_amount_paid = ( bill_amount > amount_paid )
        bill_amount_lt_amount_paid = ( bill_amount < amount_paid )
        bill_amount_eq_amount_paid = ( bill_amount == amount_paid )
        bill_settled=False
        if bill_amount_gt_amount_paid:
            ## Partial Payment Case
            bill_amount=bill_amount-amount_paid
            out_standing=bill_amount
        if bill_amount_lt_amount_paid:
            out_standing=0
            carry_forward=bill_amount-amount_paid
        if bill_amount_eq_amount_paid:
            out_standing=0
            carry_forward=0
            bill_amount=0
            bill_settled=True


        settlement = add_settlement_detail(flat_id=flat.ID, bill_id=bill.ID, payment_id=payment.ID,
                                           actual_amt=bill.TOTAL_PAYABLE,settled_amt=payments_made_after_due_date, pending_amt=out_standing,
                                           advance_amt=carry_forward)
        #DBPlugin.insert_dict(cursor=cursor,table='SETTLEMENT',data=settlement)
        #
        interest_on_out_standing= round(((18 / 100) * out_standing) / 12)

        if not bill_settled :
            if bill_amount >0 and amount_paid_after_due_date > 0:
                bill_amount_gt_amount_paid_after_due_date = (bill_amount > amount_paid_after_due_date)
                bill_amount_lt_amount_paid_after_due_date = (bill_amount < amount_paid_after_due_date)
                bill_amount_eq_amount_paid_after_due_date = (bill_amount == amount_paid_after_due_date)
                if bill_amount_gt_amount_paid_after_due_date:
                    out_standing=bill_amount-amount_paid_after_due_date
                    carry_forward=0
                if bill_amount_lt_amount_paid_after_due_date:
                    out_standing=0
                    carry_forward=amount_paid_after_due_date-bill_amount
                if bill_amount_eq_amount_paid_after_due_date:
                    out_standing=0
                    carry_forward=0
            else :
                carry_forward=amount_paid_after_due_date
        bill.IS_SETTLED=1

        settlement = add_settlement_detail(flat_id=flat.ID, bill_id=bill.ID, payment_id=payment.ID,
                                           actual_amt=bill.TOTAL_PAYABLE, pending_amt=out_standing,
                                           advance_amt=carry_forward )
        DBPlugin.insert_dict(cursor=cursor,table='SETTLEMENT',data=settlement)
        db.commit()
        DBPlugin.update_dict_by_id(cursor, 'BILL', bill.__dict__, bill.ID)
        db.commit()
    print('Completed')






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


def prerequiste():
    db = DBPlugin.db
    cursor = db.cursor(dictionary=True)
    cursor.execute("UPDATE PAYMENT_HISTORY SET IS_PROCESSED=0")
    #cursor.execute("TRUNCATE TABLE SETTLEMENT")
    #BillingService.add_bill_july20_nov20()
    BillingService.generate_bill_per_flat()

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
    settlement_service(cursor,flat)
    print('Settled')

def settlebill():
    prerequiste()
    settle_bill(building='B-2', flat_number=406)

def bills():
    prerequiste()
    db = DBPlugin.db
    cursor = db.cursor(dictionary=True)
    flats = BuildingService.find_all_flats(cursor)
    for flat in flats:
        settle_payment(building=flat.BUILDING, flat_number=flat.FLAT_NUMBER)
    print('Payment Settled')
    generate_bill(flats)

def main():
    #prerequiste()
    bill_payment()
    #bill()

def bill():
    prerequiste()
    db = DBPlugin.db
    cursor = db.cursor(dictionary=True)
    flats = BuildingService.find_all_flats(cursor)
    for flat in flats:
        settlement_service(cursor, flat)
    generate_bill(flats)





if __name__ == '__main__':
    main()