
import frappe, os,csv,requests,boto3,calendar,time
from frappe.model.document import Document
from datetime import datetime,timedelta
import datetime as dt
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.mime.base import MIMEBase
from email import encoders
from lsa.custom_customer import sync_customer
from lsa.lsa.doctype.payment_link_log.payment_link_log import cancel_link
from lsa.custom_sales_order import create_razorpay_payment_link_sales_order
from lsa.custom_customer import wa_followup_customer




class MonthlySO(Document):
    def on_update(self):
        scheduler_list=frappe.get_all("Monthly SO Remainder",
                                                            filters={"active":"Yes","remainder_type":"Email"},
                                                            fields=["name","effective_from"],
                                                            order_by="effective_from desc")
        print(scheduler_list)
        if len(scheduler_list)>1:
            effective_fromdate_list=[i.effective_from for i in scheduler_list]
            effective_fromdate_set=set(effective_fromdate_list)
            if len(effective_fromdate_list)!=len(effective_fromdate_set):
                frappe.throw("Your SO reminder's date range is overlaping")
            for scheduler in scheduler_list[1:]:
                scheduler_doc=frappe.get_doc("Monthly SO Remainder",scheduler.name)
                scheduler_doc.effective_to=scheduler_list[0].effective_from - timedelta(1)
                scheduler_doc.active="No"
                scheduler_doc.save()
            frappe.reload_doc('lsa', 'Monthly SO', self.name)
        
        scheduler_list=frappe.get_all("Monthly SO Remainder",
                                                            filters={"active":"Yes","remainder_type":"WhatsApp"},
                                                            fields=["name","effective_from"],
                                                            order_by="effective_from desc")
        print(scheduler_list)
        if len(scheduler_list)>1:
            effective_fromdate_list=[i.effective_from for i in scheduler_list]
            effective_fromdate_set=set(effective_fromdate_list)
            if len(effective_fromdate_list)!=len(effective_fromdate_set):
                frappe.throw("Your SO reminder's date range is overlaping")
            for scheduler in scheduler_list[1:]:
                scheduler_doc=frappe.get_doc("Monthly SO Remainder",scheduler.name)
                scheduler_doc.effective_to=scheduler_list[0].effective_from - timedelta(1)
                scheduler_doc.active="No"
                scheduler_doc.save()
            frappe.reload_doc('lsa', 'Monthly SO', self.name)
        pass
        # if self.status == "SO Created" and self.so_generated!=1:
        #     generate_bulk_so(self)
        #     self.so_generated=1
        #     self.save()
        # elif self.status == "Payment Links Created" and self.payment_link_generated!=1:
        #     generate_payment_link(self)
        #     self.payment_link_generated=1
        #     self.save()
        # elif self.status == "Informed to Client" and self.informed_to_client!=1:
        #     start_time = time.time()
        #     inform_to_client(self)
        #     end_time = time.time()

        #     execution_time = end_time - start_time
        #     print(execution_time)
        #     self.informed_to_client=1
        #     self.save()
        # elif self.status == "Followup Created" and self.followup_created!=1:
        #     create_new_followups(self)
        #     self.followup_created=1
        #     self.save()



            
        

@frappe.whitelist()
def generate_bulk_so(mon_id,services):
    print(type(services))
    services = services.split(",")
    services = [element.strip() for element in services if element.strip()]
    services = [element.split("(") for element in services]
    services = [(element[0],element[1][:1]) for element in services]

    print(services)

    self=frappe.get_doc("Monthly SO",mon_id)
    success_count = 0
    cur_month = self.month.lower()
    cur_year = [int(y) for y in self.fy.split("-")]
    first_day_of_month, last_day_of_month = get_date_range_of_so(cur_month, cur_year)

    all_cust_array = frappe.get_all("Customer",
                                     filters={
                                        #  "name":"20131037",
                                         "disabled": 0,
                                         "custom_billable": 0,
                                        #  "name": "20130039",
                                         # "custom_state": ("not in",[None]),
                                     },
                                     fields=["name", "custom_state"])
    all_cust = {i.name: i.custom_state for i in all_cust_array}

    all_rsp = frappe.get_all("Recurring Service Pricing",
                             filters={"status": "Approved"},
                             fields=["name", "customer_id"]
                             )
    all_rsp_active = [rsp_cu for rsp_cu in all_rsp if rsp_cu.customer_id in all_cust]

    all_rsp = all_rsp_active

    customer_service_map = {}
    customer_failed_service_map = []
    if all_rsp:
        total_rsp=len(all_rsp)
        in_progress_rsp=0
        for rsp in all_rsp:
            try:
                customer_so_map = get_so_map(rsp.name, all_cust[rsp.customer_id], cur_month, cur_year, first_day_of_month, last_day_of_month, services)
                if customer_so_map["status"]:
                    print(customer_so_map)
                    so_creation_response = create_sales_order(customer_so_map["customer_so_map"])
                    
                    if so_creation_response["status"]:
                        customer_service_map[rsp.customer_id] = True
                        success_count += 1
                    else:
                        er_dict={}
                        er_dict["doctype"]= "Custom Error Log"
                        er_dict["master_type"]= "Monthly SO"
                        er_dict["master_reference"]= mon_id
                        er_dict["type"]="Customer"
                        er_dict["record_reference"]= rsp.customer_id
                        er_dict["context"]="Sales Order Creation"
                        er_dict["error_statement"]= f'''Error  creating Monthly SO for {customer_so_map["customer"]}: {so_creation_response["error"]}
                        '''
                        er_doc = frappe.get_doc(er_dict)
                        er_doc.insert()
                        customer_failed_service_map.append(customer_so_map)
                        # print("failed SO: ", customer_so_map["customer"], so_creation_response["error"])
                elif customer_so_map["status"] in [False]:
                    print(customer_so_map["error"])
                    
                    er_dict={}
                    er_dict["doctype"]= "Custom Error Log"
                    er_dict["master_type"]= "Monthly SO"
                    er_dict["master_reference"]= mon_id
                    er_dict["type"]= "Customer"
                    er_dict["record_reference"]= rsp.customer_id
                    er_dict["context"]="Sales Order Creation"
                    er_dict["error_statement"]= f'''Error fetching details for Monthly SO creation for {customer_so_map["customer"]}: {customer_so_map["error"]}
                    '''
                    er_doc = frappe.get_doc(er_dict)
                    er_doc.insert()
                    # pass
                    
            except Exception as er:
                frappe.log_error(f"An error occurred in bulk creation of Sales Orders: {er}")
                customer_service_map[rsp["customer_id"]] = False
                er_dict={}
                er_dict["doctype"]= "Custom Error Log"
                er_dict["master_type"]= "Monthly SO"
                er_dict["master_reference"]= mon_id
                er_dict["type"]= "Customer"                 
                er_dict["record_reference"]= rsp.customer_id
                er_dict["context"]="Sales Order Creation"
                er_dict["error_statement"]= f'''Exception Error  creating Monthly SO for {rsp["customer_id"]}: {er}
                '''
                er_doc = frappe.get_doc(er_dict)
                er_doc.insert()
                print(er)
                print("failed: ", rsp["customer_id"], str(er))
            in_progress_rsp+=1
            frappe.publish_realtime("progress", {
                                            "total": total_rsp,
                                            "created": in_progress_rsp
                                        }, user=frappe.session.user)
        # print(len(customer_service_map))
        # print(customer_failed_service_map)
        if not customer_failed_service_map:
            self.so_generated=1
            self.status="SO Created"
        self.autogenerated_so_count = success_count
        self.save()



def get_so_map(rsp_id,cust_state,cur_month,cur_year,first_day_of_month,last_day_of_month,services):
    rsp_doc = frappe.get_doc("Recurring Service Pricing", rsp_id)
    so_fields = ["customer", "transaction_date", "custom_so_from_date", "custom_so_to_date",
                    "custom_auto_generated",
                    "tax_category", "taxes_and_charges"]

    customer_so_map = {}

    customer_so_map["customer"] = rsp_doc.customer_id
    customer_so_map["transaction_date"] = first_day_of_month
    customer_so_map["custom_so_from_date"] = first_day_of_month
    customer_so_map["custom_so_to_date"] = last_day_of_month
    customer_so_map["custom_auto_generated"] = 1

    status,tax_category,taxes_and_charges,taxes=get_taxes(cust_state)
    if status:
        customer_so_map["tax_category"]=tax_category
        customer_so_map["taxes_and_charges"]=taxes_and_charges
        customer_so_map["taxes"]=taxes
    else:
        return {"status":False,"error":f"Taxes Not Mapped properly for {rsp_doc.customer_id}, check customer's State field"}

    services_map=get_services(rsp_doc.recurring_services,first_day_of_month,cur_month,cur_year,services)
    if services_map: 
        customer_so_map["items"] = services_map
        # print(len(services_map))
        # print(customer_so_map)
        return {"status":True,"customer_so_map": customer_so_map}
    else:
        return {"status":None,"error":f"No Services Mapped for {rsp_doc.customer_id}"}

def get_date_range_of_so(cur_month,cur_year):
    month_num = {
                        "apr": 1, 
                        "may": 2, 
                        "jun": 3, 
                        "jul": 4, 
                        "aug": 5, 
                        "sep": 6, 
                        "oct": 7, 
                        "nov": 8, 
                        "dec": 9,
                        "jan": 10, 
                        "feb": 11, 
                        "mar": 12
                    }
    first_day_of_month = ""
    last_day_of_month = ""
    if month_num[cur_month] < 10:
        first_day_of_month = datetime(cur_year[0], month_num[cur_month] + 3, 1).date()
        _, last_day = calendar.monthrange(cur_year[0], month_num[cur_month] + 3)
        last_day_of_month = datetime(cur_year[0], month_num[cur_month] + 3, last_day).date()
    else:
        first_day_of_month = datetime(cur_year[1], (month_num[cur_month] - 12 + 3), 1).date()
        _, last_day = calendar.monthrange(cur_year[1], (month_num[cur_month] - 12 + 3))
        last_day_of_month = datetime(cur_year[1], (month_num[cur_month] - 12 + 3), last_day).date()
    return first_day_of_month,last_day_of_month

def get_services(rsp_services,first_day_of_month,cur_month,cur_year,services):
    mon_freq = {
                "apr": ["M"], 
                "may": ["M"], 
                "jun": ["M", "Q",], 
                "jul": ["M"], 
                "aug": ["M"],
                "sep": ["M", "Q" ],
                "oct": ["M"], 
                "nov": ["M"], 
                "dec": ["M", "Q",], 
                "jan": ["M"], 
                "feb": ["M"], 
                "mar": ["M", "Q", "Y",]
            }

    cur_month_freq = mon_freq[cur_month]
    services_map = []
    for item in rsp_services:
        service_dict = {}
        service_doc = frappe.get_doc(item.service_type, item.service_id)
        serv_frequency = service_doc.frequency

        if serv_frequency in cur_month_freq and (item.service_type,serv_frequency) in services:
            items_fields = ["item_code", "custom_soi_from_date", "custom_soi_to_date", "description",
                            "gst_hsn_code", "qty", "uom", "rate",
                                            "gst_treatment"]
            service_dict["item_code"] = service_doc.service_name
            service_dict["custom_soi_from_date"] = first_day_of_month
            service_dict["description"] = service_doc.description
            service_dict["gst_hsn_code"] = service_doc.hsn_code
            service_dict["qty"] = 1
            service_dict["rate"] = item.revised_charges
            service_dict["custom_soi_to_date"] = get_last_day_of_service(serv_frequency,cur_month,cur_year)
            
            services_map.append(service_dict)
    return services_map

def get_last_day_of_service(serv_frequency,cur_month,cur_year):
    month_num = {
                        "apr": 1, 
                        "may": 2, 
                        "jun": 3, 
                        "jul": 4, 
                        "aug": 5, 
                        "sep": 6, 
                        "oct": 7, 
                        "nov": 8, 
                        "dec": 9,
                        "jan": 10, 
                        "feb": 11, 
                        "mar": 12
                    }
    freq_mon_num = {
                        "Y": 12, 
                        "Q": 3, 
                        "M": 1,
                        }
    serv_frequency_mon_num = freq_mon_num[serv_frequency]
    last_day_of_serv_month=None
    last_month_of_serv=month_num[cur_month] + 3 +serv_frequency_mon_num - 1
    if last_month_of_serv > 12:
        _, last_day_serv = calendar.monthrange(cur_year[1], last_month_of_serv-12)
        last_day_of_serv_month = datetime(cur_year[1], last_month_of_serv-12, last_day_serv).date()
    else:
        _, last_day_serv = calendar.monthrange(cur_year[0], last_month_of_serv)
        last_day_of_serv_month = datetime(cur_year[0], last_month_of_serv, last_day_serv).date()
    return last_day_of_serv_month

def get_taxes(cust_state):
    cmp_doc = frappe.get_doc("Company", "LOKESH SANKHALA AND ASSOCIATES")
    comp_state = cmp_doc.custom_state

    tax_category=""
    taxes_and_charges=""
    taxes=[]
    if comp_state == cust_state:
        tax_category = "In-state"
        taxes_and_charges = "Output GST In-state - IND"
        tax_item={}
        tax_item["charge_type"]="On Net Total"
        tax_item["account_head"]="Tax SGST - IND"
        tax_item["rate"]=9.00
        tax_item["description"]="Output Tax SGST @ 9.0"
        taxes.append(tax_item)
        tax_item={}
        tax_item["charge_type"]="On Net Total"
        tax_item["account_head"]="Tax CGST - IND"
        tax_item["rate"]=9.00
        tax_item["description"]="Output Tax CGST @ 9.0"
        taxes.append(tax_item)
        return True,tax_category,taxes_and_charges,taxes
    elif cust_state:
        tax_category = "Out-state"
        taxes_and_charges = "Output GST Out-state - IND"
        tax_item={}
        tax_item["charge_type"]="On Net Total"
        tax_item["account_head"]="Output Tax IGST - IND"
        tax_item["rate"]=18.00
        tax_item["description"]="Output Tax IGST @ 18.0"
        taxes.append(tax_item)
        return True,tax_category,taxes_and_charges,taxes
    else:
        return False,None,None,None

            
            

def create_sales_order(customer_so_map=None):  
    if customer_so_map:
        try:
            so_dict={}
            so_dict["doctype"]= "Sales Order"
            for so_field in customer_so_map:
                if so_field not in ["taxes", "items"]:
                    so_dict[so_field] = customer_so_map[so_field] 
            
            items_list=[]
            for item in customer_so_map["items"]:
                item_dict={}
                if item:
                    for field in item:
                        item_dict[field] = item[field]
                    items_list.append(item_dict)
                    
            tax_item_list=[]
            for tax_item in customer_so_map["taxes"]:
                tax_item_dict={}
                if tax_item:
                    for field in tax_item:
                        tax_item_dict[field] = tax_item[field]
                    tax_item_list.append(tax_item_dict)

            so_dict["items"] = items_list
            so_dict["taxes"] = tax_item_list
            # print(so_dict)
            so_doc = frappe.get_doc(so_dict)
            
            so_doc.insert()
            print(f"SO created for {so_doc.customer} {so_doc.name}")
            return {"status":True, "msg":"SO for {customer} created successfully"}
        except Exception as er:
            print("Error",er)
            frappe.log_error(f"An error occurred in creating Sales Orders: {er}")

            return {"status":False, "error":f"{er}"}

@frappe.whitelist()
def go_to_month_so(mon_id):
    month_so_doc = frappe.get_doc("Monthly SO", mon_id)
    cur_month = month_so_doc.month.lower()
    cur_year = [int(y) for y in month_so_doc.fy.split("-")]
    first_day_of_month, last_day_of_month = get_date_range_of_so(cur_month, cur_year)
    filters={}
    filters["custom_auto_generated"]=1
    filters["custom_so_from_date"]=(">=",first_day_of_month)
    filters["custom_so_to_date"]=("<=",last_day_of_month)

    return filters


@frappe.whitelist()
def update_so_count(mon_id):
    month_so_doc = frappe.get_doc("Monthly SO", mon_id)
    cur_month = month_so_doc.month.lower()
    cur_year = [int(y) for y in month_so_doc.fy.split("-")]
    first_day_of_month, last_day_of_month = get_date_range_of_so(cur_month, cur_year)
    so_cur_mon_auto = frappe.get_all("Sales Order", filters={
        "custom_so_from_date": (">=", first_day_of_month),
        "custom_so_to_date": ("<=", last_day_of_month),
        "custom_auto_generated": 1,
        "docstatus":("not in",[2]),
    })
    new_autogenerated_so_count = len(so_cur_mon_auto)
    
    so_cur_mon = frappe.get_all("Sales Order", filters={
        "custom_so_from_date": (">=", first_day_of_month),
        "custom_so_to_date": ("<=", last_day_of_month),
        "docstatus":("not in",[2]),
    })
    new_so_count = len(so_cur_mon)
    print(new_so_count,new_autogenerated_so_count)
    if month_so_doc.auto_generated_so_this_month != new_autogenerated_so_count or month_so_doc.total_so_this_month!=new_so_count:
        month_so_doc.auto_generated_so_this_month = new_autogenerated_so_count
        month_so_doc.total_so_this_month = new_so_count
        month_so_doc.save()
        return True
    

@frappe.whitelist()
def generate_payment_link(mon_id):
    self=frappe.get_doc("Monthly SO",mon_id)
    cur_month = self.month.lower()
    cur_year = [int(y) for y in self.fy.split("-")]
    first_day_of_month, last_day_of_month = get_date_range_of_so(cur_month, cur_year)
    so_cur_mon_auto = frappe.get_all("Sales Order", filters={
        "custom_so_from_date": (">=", first_day_of_month),
        "custom_so_to_date": ("<=", last_day_of_month),
        "custom_auto_generated": 1,
        # "custom_razorpay_payment_url":("in",[None])
    })
    print(len(so_cur_mon_auto))
    total_pl=len(so_cur_mon_auto)
    in_progress_pl=0
    status_dict={"success":[],"failure":[]}
    for so in so_cur_mon_auto:
        so_doc = frappe.get_doc("Sales Order", so.name)
        grand_total = so_doc.rounded_total * 1.02
        resp=create_razorpay_payment_link_sales_order(grand_total, so_doc.name,so_doc.customer,
                                                      so_doc.customer_name,so_doc.custom_so_from_date,
                                                      so_doc.custom_so_to_date,so_doc.rounded_total)
        print(resp)
        if resp["status"]:
            print(resp)
            print(f"payment link success for {so_doc.name} with customer {so_doc.customer}")
            status_dict["success"]+=[so.name]
        else:
            print(f"failed for {so_doc.name} with customer {so_doc.customer}: {resp['msg']}")
            er_dict={}
            er_dict["doctype"]= "Custom Error Log"
            er_dict["master_type"]= "Monthly SO"
            er_dict["master_reference"]= mon_id
            er_dict["type"]= "Sales Order"
            er_dict["record_reference"]= so.name
            er_dict["context"]="Payment Link Creation for Auto-gen SO"
            er_dict["error_statement"]= f'''Error creating Payment Link for Monthly SO bulk operation for {so_doc.customer}: {resp['msg']}
            '''
            er_doc = frappe.get_doc(er_dict)
            er_doc.insert()
            # status_dict["failure"]+=[so.name]
        in_progress_pl+=1
        frappe.publish_realtime("progress", {
                                        "total": total_pl,
                                        "created": in_progress_pl
                                    }, user=frappe.session.user)
        # print(in_progress_pl)
    # print(status_dict["failure"])
    if not status_dict["failure"]:
        self.payment_link_generated=1
        self.status="Payment Links Created"
        self.save()
    
    return status_dict

@frappe.whitelist()
def inform_to_client(mon_id):
    self=frappe.get_doc("Monthly SO",mon_id)
    cur_month = self.month.lower()
    cur_year = [int(y) for y in self.fy.split("-")]
    first_day_of_month, last_day_of_month = get_date_range_of_so(cur_month, cur_year)
    so_cur_mon_auto = frappe.get_all("Sales Order", filters={
        "custom_so_from_date": (">=", first_day_of_month),
        "custom_so_to_date": ("<=", last_day_of_month),
        "custom_auto_generated": 1,
        # "customer":("in",["20130669","20130894","20130546","20130884","20130501","20130806"])
    })
    
    status_dict={"success":[],"failure":[]}
    wa_status_dict={"success":[],"failure":[]}


    email_account = frappe.get_doc("Email Account", "LSA OFFICE")
    sender_email = email_account.email_id
    sender_password = email_account.get_password()
    smtp_server = 'smtp.gmail.com'
    smtp_port = 587
    server = smtplib.SMTP(smtp_server, smtp_port)
    server.starttls()
    server.login(sender_email, sender_password)
    total_noti=len(so_cur_mon_auto)
    noti_done=0
    for so in so_cur_mon_auto:
        so_doc = frappe.get_doc("Sales Order", so.name)
        month_full=first_day_of_month.strftime("%B")
        resp=new_autogen_so_mail(so_doc,month_full,self.fy,server,mon_id)
        if resp["status"]:
            status_dict["success"]+=[so.name]
        else:
            status_dict["failure"]+=[so.name]
        
        resp_wa=whatsapp_so_template(so_doc,mon_id)
        if resp["status"]:
            wa_status_dict["success"]+=[so.name]
        else:
            wa_status_dict["failure"]+=[so.name]
            
        noti_done+=1
        frappe.publish_realtime("progress", {
                                        "total": total_noti,
                                        "created": noti_done
                                    }, user=frappe.session.user)

    print(status_dict["failure"])

    server.quit()

    if not status_dict["failure"]:
        self.informed_to_client=1
        self.status="Informed to Client"
        self.save()

    return status_dict




def new_autogen_so_mail(so_doc, month, fy,server,mon_id):

    email_account = frappe.get_doc("Email Account", "LSA OFFICE")
    sender_email = email_account.email_id
    sender_password = email_account.get_password()
    recipient = "360ithub.developers@gmail.com"
    cc_email = "360ithub.developers@gmail.com"

    subject = f"New Sales Order for {month} of FY {fy}"

    body = f"""
    <html>
    <body>
    <p>Dear {so_doc.customer_name},</p>
    <p style="margin: 0; padding: 0;">Please find attached the Sales Order {so_doc.name} for your reference.</p>
    <p style="margin: 0; padding: 0;">Details are as follows:</p>"""
    body += """
    <table class="table table-bordered" style="border-collapse: collapse; width: 100%;">
        <thead>
            <tr style="background-color: #3498DB; color: white; text-align: left;">
                <th style="border: solid 2px #bcb9b4; width: 5%;">S.No.</th>
                <th style="border: solid 2px #bcb9b4; width: 15%;">Item Code</th>
                <th style="border: solid 2px #bcb9b4; width: 15%;">File ID</th>
                <th style="border: solid 2px #bcb9b4; width: 30%;">Description</th>
                <th style="border: solid 2px #bcb9b4; width: 5%;">Quantity</th>
                <th style="border: solid 2px #bcb9b4; width: 10%;">Rate</th>
                <th style="border: solid 2px #bcb9b4; width: 10%;">Amount</th>
            </tr>
        </thead>
        <tbody>
    """
    count = 1
    for item in so_doc.items:
        body += f"""
        <tr style="color: black;">
            <td style="border: solid 2px #bcb9b4;width: 5%;">{count}</td>
            <td style="border: solid 2px #bcb9b4;width: 15%;">{item.item_code}</td>
            <td style="border: solid 2px #bcb9b4;width: 15%;">{item.name}</td>
            <td style="border: solid 2px #bcb9b4;width: 30%;">{item.description.split("-")[0]}</td>
            <td style="border: solid 2px #bcb9b4;width: 5%;">{item.qty}</td>
            <td style="border: solid 2px #bcb9b4;width: 10%;">{item.rate}</td>
            <td style="border: solid 2px #bcb9b4;width: 10%;">{item.amount}</td>
        </tr>
        """
        count += 1
    discount_row=""
    if so_doc.discount_amount>0:
        discount_row=f"""<div style="margin: 0px; padding: 0; display: flex;justify-content: space-between;">
                            <div style="width: 50%;">Discount:</div>
                            <div style="width: 50%;">₹ { so_doc.discount_amount }</div>
                        </div>"""
    body += f"""
        </tbody>
    </table><br>

    <div style="float: right;width:30%">
        <div style="margin: 0px; padding: 0; display: flex;justify-content: space-between;">
            <div style="width: 50%;">Total:</div>
            <div style="width: 50%;">₹ { so_doc.total }</div>
        </div>
        <div style="margin: 0px; padding: 0; display: flex;justify-content: space-between;">
            <div style="width: 50%;">Taxes:</div>
            <div style="width: 50%;">₹ { so_doc.total_taxes_and_charges }</div>
        </div>
        {discount_row}
        <div style="margin: 0px; padding: 0; display: flex;justify-content: space-between;">
            <div style="width: 50%;">Grand Total:</div>
            <div style="width: 50%;"><strong>₹ { so_doc.rounded_total }</strong></div>
        </div>
    </div>
    <div style="clear: both;"></div>
    <p>Thank you for your business!</p><br>

    <p>Regards,<br>LSA Office</p>
    </body>
    </html>
    """

    # print(body)
    # Create the email message
    message = MIMEMultipart()
    message['From'] = sender_email
    message['To'] = recipient
    message['Cc'] = cc_email
    message['Subject'] = subject
    message.attach(MIMEText(body, 'html'))

    # Attach the PDF file
    pdf_link = f"https://online.lsaoffice.com/api/method/frappe.utils.print_format.download_pdf?doctype=Sales%20Order&name=SAL-ORD-2023-00436&format=Sales%20Order%20Format&no_letterhead=0&letterhead=LSA&settings=%7B%7D&_lang=en/SAL-ORD-2023-00436.pdf"
    pdf_filename = f"sales_order_{month}_{fy}.pdf"
    attachment = get_file_from_link(pdf_link)
    if attachment:
        part = MIMEBase("application", "octet-stream")
        part.set_payload(attachment)
        encoders.encode_base64(part)
        part.add_header(
            "Content-Disposition",
            f"attachment; filename= {pdf_filename}",
        )
        message.attach(part)

    # Connect to the SMTP server and send the email
    
    try:
        # Send email
        response=server.sendmail(sender_email, recipient.split(',') + cc_email.split(','), message.as_string())
        print(so_doc.name,"res",response,)
        return {"status":True,"msg":"Email sent successfully!"}
    except Exception as e:
        print(f"Failed to send email. Error: {e}")
        frappe.log_error(f"An error occurred in sending mail : {e}")

        er_dict={}
        er_dict["doctype"]= "Custom Error Log"
        er_dict["master_type"]= "Monthly SO"
        er_dict["master_reference"]= mon_id
        er_dict["type"]= "Sales Order"
        er_dict["record_reference"]= so_doc.name
        er_dict["context"]="Email Notification for Auto-gen SO"
        er_dict["error_statement"]= f'''Error Sending Mail Notification Monthly SO bulk operation for {so_doc.customer}: {e}
        '''
        er_doc = frappe.get_doc(er_dict)
        er_doc.insert()
        return {"status":True,"msg":"Failed to send email."}
        

@frappe.whitelist()
def whatsapp_so_template(so_doc,mon_id):
    new_mobile="9098543046"

    whatsapp_demo = frappe.get_all('WhatsApp Instance',filters={'module':'Accounts','connection_status':1,'active':1})
    if whatsapp_demo:
        sales_invoice_whatsapp_log = frappe.new_doc('WhatsApp Message Log')
        whatsapp_items = []

        invoice_doc = so_doc
        customer = invoice_doc.customer
        total = invoice_doc.rounded_total
        customer_name = invoice_doc.customer_name
        docname = invoice_doc.name

        advance_paid_amount=0
        balance_amount=invoice_doc.rounded_total

        sales_invoice = frappe.get_all('Sales Invoice Item',filters={'sales_order':invoice_doc.name,'docstatus':("in",[0,1])},fields=["parent"])
        if sales_invoice:
            return {"status":False,"msg":f"A Sales Invoice <a href='https://online.lsaoffice.com/app/sales-invoice/{sales_invoice[0].parent}'>{sales_invoice[0].parent}</a> already exist for the Sales Order"}
        
        instance = frappe.get_doc('WhatsApp Instance',whatsapp_demo[0].name)
        ins_id = instance.instance_id


        try:
            # Check if the mobile number has 10 digits
            if len(new_mobile) != 10:
                frappe.msgprint("Please provide a valid 10-digit mobile number.")
                return
            
            payment_link=""
            if invoice_doc.custom_razorpay_payment_url:
                payment_link=f"Payment Link is : {invoice_doc.custom_razorpay_payment_url}"
            
            due_amount_message=f"with net total amount of ₹ {total}/-"

            # pe_list = frappe.get_all('Payment Entry Reference',filters={"reference_doctype":"Sales Order",'reference_name':invoice_doc.name,'docstatus':1},fields=["name","allocated_amount","parent"])
            # if pe_list:
            #     for pe in pe_list:
            #         advance_paid_amount+=pe.allocated_amount
            #         balance_amount-=pe.allocated_amount
            #     due_amount_message=f"partially paid. You have paid Rs {advance_paid_amount}/- out of net total of Rs {total}/-"
            #     payment_link=""
            


            from_date=invoice_doc.custom_so_from_date.strftime('%d-%m-%Y')
            to_date=invoice_doc.custom_so_to_date.strftime('%d-%m-%Y')
            
            message = f'''Dear {customer_name},

Please find attached Sale Order from {from_date} to {to_date} period {due_amount_message}. Kindly pay on below bank account details

Our Bank Account
Lokesh Sankhala and ASSOSCIATES
Account No = 73830200000526
IFSC = BARB0VJJCRO
Bank = Bank of Baroda,JC Road,Bangalore-560002
UPI id = LSABOB@UPI
Gpay / Phonepe no = 9513199200
{payment_link}

Call us immediately in case of query.

Best Regards,
LSA Office Account Team
accounts@lsaoffice.com
8951692788'''
            if balance_amount<1:
                message=""
            
            ########################### Below commented link is work on Live #######################
            link = f"https://online.lsaoffice.com/api/method/frappe.utils.print_format.download_pdf?doctype=Sales%20Order&name={docname}&format=Sales%20Order%20Format&no_letterhead=0&letterhead=LSA&settings=%7B%7D&_lang=en/{docname}.pdf"
            
            url = "https://wts.vision360solutions.co.in/api/sendFileWithCaption"
            params_1 = {
                "token": ins_id,
                "phone": f"91{new_mobile}",
                "message": message,
                "link": link
            }

            whatsapp_items.append( {"type": "Sales Order",
                                    "document_id": invoice_doc.name,
                                    "mobile_number": new_mobile,
                                    "customer":invoice_doc.customer,})
            
            response = requests.post(url, params=params_1)
            response.raise_for_status()  # Raise an error for HTTP errors (status codes other than 2xx)
            response_data = response.json()
            message_id = response_data['data']['messageIDs'][0]


            # Check if the response status is 'success'
            if response_data.get('status') == 'success':
                # Log the success

                frappe.logger().info("WhatsApp message sent successfully")
                sales_invoice_whatsapp_log.append("details", {
                                                "type": "Sales Order",
                                                "document_id": invoice_doc.name,
                                                "mobile_number": new_mobile,
                                                "customer":invoice_doc.customer,
                                                "message_id":message_id
                                                            
                                                # Add other fields of the child table row as needed
                                            })
                sales_invoice_whatsapp_log.send_date = frappe.utils.now_datetime()
                sales_invoice_whatsapp_log.sender = frappe.session.user
                sales_invoice_whatsapp_log.type = "Template"
                sales_invoice_whatsapp_log.message = message
                sales_invoice_whatsapp_log.insert()
                return {"status":True,"msg":"WhatsApp message sent successfully"}
            else:
                er_dict={}
                er_dict["doctype"]= "Custom Error Log"
                er_dict["master_type"]= "Monthly SO"
                er_dict["master_reference"]= mon_id
                er_dict["type"]= "Sales Order"
                er_dict["record_reference"]= so_doc.name
                er_dict["context"]="WhatsApp Notification for Auto-gen SO"
                er_dict["error_statement"]= f'''Error Sending WhatsApp Notification Monthly SO bulk operation for {so_doc.customer}
                '''
                er_doc = frappe.get_doc(er_dict)
                er_doc.insert()
                return {"status":False,"error":f"{response.json()}","msg":"An error occurred while sending the WhatsApp message."}


        except requests.exceptions.RequestException as e:
            # Log the exception and provide feedback to the user
            frappe.logger().error(f"Network error: {e}")
            er_dict={}
            er_dict["doctype"]= "Custom Error Log"
            er_dict["master_type"]= "Monthly SO"
            er_dict["master_reference"]= mon_id
            er_dict["type"]= "Sales Order"
            er_dict["record_reference"]= so_doc.name
            er_dict["context"]="WhatsApp Notification for Auto-gen SO"
            er_dict["error_statement"]= f'''Error Sending WhatsApp Notification Monthly SO bulk operation for {so_doc.customer}: {e}
            '''
            er_doc = frappe.get_doc(er_dict)
            er_doc.insert()
            return {"status":False,"error":e,"msg":"An error occurred while sending the WhatsApp message. Please try again later."}
        except Exception as er:
            # Log the exception and provide feedback to the user
            frappe.logger().error(f"Error: {er}")
            er_dict={}
            er_dict["doctype"]= "Custom Error Log"
            er_dict["master_type"]= "Monthly SO"
            er_dict["master_reference"]= mon_id
            er_dict["type"]= "Sales Order"
            er_dict["record_reference"]= so_doc.name
            er_dict["context"]="WhatsApp Notification for Auto-gen SO"
            er_dict["error_statement"]= f'''Error Sending WhatsApp Notification Monthly SO bulk operation for {so_doc.customer}: {er}
            '''
            er_doc = frappe.get_doc(er_dict)
            er_doc.insert()
            return {"status":False,"error":er,"msg":"An unexpected error occurred while sending the WhatsApp message. Please contact the system administrator."}
    else:
        er_dict={}
        er_dict["doctype"]= "Custom Error Log"
        er_dict["master_type"]= "Monthly SO"
        er_dict["master_reference"]= mon_id
        er_dict["type"]= "Sales Order"
        er_dict["record_reference"]= so_doc.name
        er_dict["context"]="WhatsApp Notification for Auto-gen SO"
        er_dict["error_statement"]= f'''Error Sending WhatsApp Notification Monthly SO bulk operation for {so_doc.customer}: Your WhatApp API instance is not connected
        '''
        er_doc = frappe.get_doc(er_dict)
        er_doc.insert()
        return {"status":False,"msg":"Your WhatApp API instance is not connected"}

    
def get_file_from_link(link):
    try:
        response = requests.get(link)
        if response.status_code == 200:
            return response.content
        else:
            print(f"Failed to fetch file from link. Status code: {response.status_code}")
            return None
    except Exception as e:
        print(f"Error fetching file from link: {e}")
        frappe.log_error(f"An error occurred in fetching file from Link: {e}")
        return None
    
@frappe.whitelist()
def create_new_followups(mon_id,next_followup_date_mon):
    next_followup_date_mon = datetime.strptime(next_followup_date_mon, '%Y-%m-%d').date()

    self=frappe.get_doc("Monthly SO",mon_id)
    cur_month = self.month.lower()
    cur_year = [int(y) for y in self.fy.split("-")]
    first_day_of_month, last_day_of_month = get_date_range_of_so(cur_month, cur_year)
    so_cur_mon_auto = frappe.get_all("Sales Order", filters={
															"custom_so_from_date": (">=", first_day_of_month),
															"custom_so_to_date": ("<=", last_day_of_month),
															"custom_auto_generated": 1,
														},
                                                    fields=["customer","name"]              
														)
    cust_to_generate_fu={i.customer:i.name for i in so_cur_mon_auto}
    status_dict={"success":[],"failure":[]}
    total=len(cust_to_generate_fu)
    created=0
    for cust in cust_to_generate_fu:
        try:
            open_fu = frappe.get_all("Customer Followup",filters={
                                                                "status":"Open",
                                                                "customer_id":cust,
                                                                })
            next_followup_date=None
            new_followup=True
            if open_fu:
                open_fu_doc=frappe.get_doc("Customer Followup",open_fu[0].name)
                if cust_to_generate_fu[cust] in open_fu_doc.sales_order_summary:
                    status_dict["success"]+=[cust]
                    new_followup=False
                else:
                    next_followup_date=open_fu_doc.next_followup_date
                    open_fu_doc.status="Closed"
                    open_fu_doc.followup_note="New Followup created with newly added SO"
                    open_fu_doc.save()
            # print(next_followup_date)
            # print(type(next_followup_date))

            response=sync_customer(cust)
            if response["status"]!="Sync Failed." and new_followup:
                doc = frappe.new_doc("Customer Followup")
                doc.customer_id = cust
                doc.followup_type="Call"
                doc.sales_order_summary = response["values"][3]
                doc.total_remaining_balance=response["values"][2]
                
                if not next_followup_date:
                    doc.next_followup_date=next_followup_date_mon
                elif next_followup_date>=first_day_of_month and next_followup_date>= datetime.now().date():
                    doc.next_followup_date=next_followup_date
                else:
                    frappe.throw("Enter a valid Next Followup Date")
                # print(next_followup_date,next_followup_date_mon,doc.next_followup_date)
                doc.executive="latha.st@lsaoffice.com"
                doc.insert()
                status_dict["success"]+=[cust]
            elif new_followup:
                er_dict={}
                er_dict["doctype"]= "Custom Error Log"
                er_dict["master_type"]= "Monthly SO"
                er_dict["master_reference"]= mon_id
                er_dict["type"]= "Customer"
                er_dict["record_reference"]= cust
                er_dict["context"]="New Followup Creation for Auto-gen SO"
                er_dict["error_statement"]= f'''Error fetching details for new followups creating in Monthly SO bulk operation for {cust}
                '''
                er_doc = frappe.get_doc(er_dict)
                er_doc.insert()
                status_dict["failure"]+=[cust]
        except Exception as er:
            status_dict["failure"]+=[cust]
            print(er)
            frappe.log_error(f"An error occurred in creating new followup: {er}")
            er_dict={}
            er_dict["doctype"]= "Custom Error Log"
            er_dict["master_type"]= "Monthly SO"
            er_dict["master_reference"]= mon_id
            er_dict["type"]= "Customer"
            er_dict["record_reference"]= cust
            er_dict["context"]="New Followup Creation for Auto-gen SO"
            er_dict["error_statement"]= f'''Error creating new followups in Monthly SO bulk operation for {cust}: {er}
            '''
            er_doc = frappe.get_doc(er_dict)
            er_doc.insert()
        created+=1
        frappe.publish_realtime("progress", {
                                        "total": total,
                                        "created": created
                                    }, user=frappe.session.user)
    print(status_dict["failure"])
    if not status_dict["failure"]:
        self.followup_created=1
        self.status="Followup Created"
        self.save()
    return status_dict
        

@frappe.whitelist()
def cancel_so_payment_links(mon_id):
    month_so_doc = frappe.get_doc("Monthly SO", mon_id)
    cur_month = month_so_doc.month.lower()
    cur_year = [int(y) for y in month_so_doc.fy.split("-")]
    first_day_of_month, last_day_of_month = get_date_range_of_so(cur_month, cur_year)
    so_cur_mon_auto = frappe.get_all("Sales Order", filters={
        "custom_so_from_date": (">=", first_day_of_month),
        "custom_so_to_date": ("<=", last_day_of_month),
        "custom_auto_generated": 1,
        "custom_razorpay_payment_url":("not in",[None])},
        fields=["name","customer","custom_razorpay_payment_url"])
    status_dict={"success":[],"failure":[]}

    cancelled_payment_links=0
    total_payment_links=len(so_cur_mon_auto)
    for so in so_cur_mon_auto:
        payment_link_list= frappe.get_all("Payment Link Log",filters={"link_short_url": so.custom_razorpay_payment_url},fields=["name","enabled"])
        if payment_link_list:
            resp=cancel_link(payment_link_list[0].name)
            
            if resp["status"]:
                status_dict["success"]+=[so.name]
                cancelled_payment_links += 1
                # Send progress information to the client side
                frappe.publish_realtime("progress", {
                                        "total": total_payment_links,
                                        "cancelled": cancelled_payment_links
                                    }, user=frappe.session.user)
            else:
                status_dict["failure"]+=[so.name]
                er_dict={}
                er_dict["doctype"]= "Custom Error Log"
                er_dict["master_type"]= "Monthly SO"
                er_dict["master_reference"]= mon_id
                er_dict["type"]= "Sales Order"
                er_dict["record_reference"]= so.name
                er_dict["context"]="Payment Link Cancellation for Auto-gen SO"
                er_dict["error_statement"]= f'''Error cancelling payment link in Monthly SO bulk operation for {so.customer} for {so.name}: {resp["msg"]}
                '''
                er_doc = frappe.get_doc(er_dict)
                er_doc.insert()
            print(so.name,resp["status"],resp["msg"])
        else:
            so_doc = frappe.get_doc('Sales Order',so.name)
            so_doc.custom_razorpay_payment_url=None
            so_doc.save()

    # print(status_dict["failure"])
    if len(so_cur_mon_auto)==len(status_dict["success"]):
        month_so_doc.payment_link_generated=0
        month_so_doc.informed_to_client=0
        month_so_doc.status="Payment Links Cancelled"
        month_so_doc.save()
        return {"status":True,"msg":"All Payment Links are cancelled"}
    elif len(status_dict["success"])>0:
        return {"status":True,"msg":"Partial Payment Links are cancelled"}
    
    return {"status":False,"msg":"Failed to cancel Payment Links"}


@frappe.whitelist()
def generate_bulk_customer_followup():

    status_dict={"success":[],"failure":[]}
    email_status_dict={"success":[],"failure":[]}
    whatsapp_status_dict={"success":[],"failure":[]}
    remainder_freq=frappe.get_all("Monthly SO Remainder",filters={"active":"Yes"},fields=["name","parent","remainder_type"],order_by="effective_from desc")
    if remainder_freq and len(remainder_freq) in (1,2):
        remainder_freq_dict={rem.remainder_type:(rem.name,rem.parent) for rem in remainder_freq}
        print(remainder_freq_dict)

        mail_mon_id=None
        if "Email" in remainder_freq_dict:
            mail_remainder_freq_doc=frappe.get_doc("Monthly SO Remainder",remainder_freq_dict["Email"][0])
            mail_mon_id=mail_remainder_freq_doc.parent
        
            next_followup_date_mon=mail_remainder_freq_doc.effective_from
            if mail_remainder_freq_doc.last_bulk_creation:
                next_followup_date_mon=mail_remainder_freq_doc.last_bulk_creation
            next_followup_date=next_followup_date_mon+timedelta(mail_remainder_freq_doc.frequency)
            
            today=datetime.now().date()

            # if True:
            if  today==next_followup_date:
            

                self=frappe.get_doc("Monthly SO",mail_mon_id)
                cur_month = self.month.lower()
                cur_year = [int(y) for y in self.fy.split("-")]
                first_day_of_month, last_day_of_month = get_date_range_of_so(cur_month, cur_year)
                so_cur_mon_auto = frappe.get_all("Sales Order", filters={
                                                                        "custom_so_from_date": (">=", first_day_of_month),
                                                                        "custom_so_to_date": ("<=", last_day_of_month),
                                                                        "custom_auto_generated": 1,
                                                                        # "customer":"20130669",
                                                                    },
                                                                fields=["name","customer"]              
                                                                    )
                # print(so_cur_mon_auto)
                cust_to_generate_fu={i.name:i.customer for i in so_cur_mon_auto}
                total=len(cust_to_generate_fu)
                created=0

                email_account = frappe.get_doc("Email Account", "LSA OFFICE")
                sender_email = email_account.email_id
                sender_password = email_account.get_password()
                smtp_server = 'smtp.gmail.com'
                smtp_port = 587
                server = smtplib.SMTP(smtp_server, smtp_port)
                server.starttls()
                server.login(sender_email, sender_password)

                for so in cust_to_generate_fu:
                    try:
                        # open_fu = frappe.get_all("Customer Followup",filters={
                        #                                                     "status":"Open",
                        #                                                     "customer_id":cust_to_generate_fu[so],
                        #                                                     })
                        # create_new_fu=True
                        # next_followup_date=None
                        # if open_fu:
                        #     # print("open fu")
                        #     open_fu_doc=frappe.get_doc("Customer Followup",open_fu[0].name)
                        #     if so in open_fu_doc.sales_order_summary:
                        #         create_new_fu=False
                        #         status_dict["success"]+=[cust_to_generate_fu[so]]
                        #     else:
                        #         next_followup_date=open_fu_doc.next_followup_date
                        #         open_fu_doc.status="Closed"
                        #         open_fu_doc.followup_note="New Followup created with newly added SO"
                        #         open_fu_doc.save()
                        #     # print("open fu executed")
                        response=sync_customer(cust_to_generate_fu[so])
                        # # response=False
                        # # print("response",response,cust_to_generate_fu[so])
                        # if create_new_fu:
                        #     if response["status"]!="Sync Failed.":
                        #         print("new fu")
                        #         doc = frappe.new_doc("Customer Followup")
                        #         doc.customer_id = cust_to_generate_fu[so]
                        #         doc.followup_type="Call"
                        #         doc.sales_order_summary = response["values"][3]
                        #         doc.total_remaining_balance=response["values"][2]
                        #         if not next_followup_date or next_followup_date<next_followup_date_mon:
                        #             doc.next_followup_date=next_followup_date_mon
                        #         elif next_followup_date>first_day_of_month:
                        #             doc.next_followup_date=next_followup_date
                        #         # print(next_followup_date,next_followup_date_mon,doc.next_followup_date)
                        #         doc.executive="latha.st@lsaoffice.com"
                        #         doc.insert()
                        #         status_dict["success"]+=[cust_to_generate_fu[so]]
                        #     else:
                        #         status_dict["failure"]+=[cust_to_generate_fu[so]]

                        # print("customer fu execution completed")

                        c_doc = frappe.get_doc("Customer",cust_to_generate_fu[so])
                        customer_name=c_doc.customer_name

                        email_fu_response=generate_bulk_email_followup(response,customer_name,server,sender_email)
                        if email_fu_response["status"]:
                            email_status_dict["success"]+=[cust_to_generate_fu[so]]
                        else:
                            er_dict={}
                            er_dict["doctype"]= "Custom Error Log"
                            er_dict["master_type"]= "Monthly SO"
                            er_dict["master_reference"]= mail_mon_id
                            er_dict["type"]= "Sales Order"
                            er_dict["record_reference"]= so
                            er_dict["context"]="Email Followup for Auto-gen SO"
                            er_dict["error_statement"]= f'''Error sending email followup in Monthly SO bulk operation for {cust_to_generate_fu[so]} for {so} on {today}:{email_fu_response["msg"]}
                            '''
                            er_doc = frappe.get_doc(er_dict)
                            er_doc.insert()
                            email_status_dict["failure"]+=[cust_to_generate_fu[so]]

                        
                    except Exception as er:
                        print(er)
                        # print("cfu error: ",er)
                        frappe.log_error(f"An error occurred in creating new followup: {er}")
                        er_dict={}
                        er_dict["doctype"]= "Custom Error Log"
                        er_dict["master_type"]= "Monthly SO"
                        er_dict["master_reference"]= mail_mon_id
                        er_dict["type"]= "Sales Order"
                        er_dict["record_reference"]= so
                        er_dict["context"]="Exception in Email Followup for Auto-gen SO"
                        er_dict["error_statement"]= f'''Exception Error sending email followup in Monthly SO bulk operation for {cust_to_generate_fu[so]} for {so} on {today}:{er}
                        '''
                        er_doc = frappe.get_doc(er_dict)
                        er_doc.insert()
                    created+=1
                    frappe.publish_realtime("progress", {
                                                    "total": total,
                                                    "created": created
                                                }, user=frappe.session.user)
                    # print(cust_to_generate_fu[so])
                # print(status_dict["failure"])
                # print(email_status_dict["failure"])
                # print(whatsapp_status_dict["failure"])
                server.quit()
                if not email_status_dict["failure"]:
                    mail_remainder_freq_doc.last_bulk_creation=datetime.now()
                    mail_remainder_freq_doc.save()
           
        #################################################WhatsApp#####################################################


        whatsapp_mon_id=None
        if "WhatsApp" in remainder_freq_dict:
            whatsapp_remainder_freq_doc=frappe.get_doc("Monthly SO Remainder",remainder_freq_dict["WhatsApp"][0])
            whatsapp_mon_id=whatsapp_remainder_freq_doc.parent
        
            next_followup_date_mon=whatsapp_remainder_freq_doc.effective_from
            if whatsapp_remainder_freq_doc.last_bulk_creation:
                next_followup_date_mon=whatsapp_remainder_freq_doc.last_bulk_creation
            next_followup_date=next_followup_date_mon+timedelta(whatsapp_remainder_freq_doc.frequency)
            
            today=datetime.now().date()

            # if True:
            if  today==next_followup_date:
            

                self=frappe.get_doc("Monthly SO",whatsapp_mon_id)
                cur_month = self.month.lower()
                cur_year = [int(y) for y in self.fy.split("-")]
                first_day_of_month, last_day_of_month = get_date_range_of_so(cur_month, cur_year)
                so_cur_mon_auto = frappe.get_all("Sales Order", filters={
                                                                        "custom_so_from_date": (">=", first_day_of_month),
                                                                        "custom_so_to_date": ("<=", last_day_of_month),
                                                                        "custom_auto_generated": 1,
                                                                    },
                                                                fields=["name","customer"]              
                                                                    )
                # print(so_cur_mon_auto)
                cust_to_generate_fu={i.name:i.customer for i in so_cur_mon_auto}
                total=len(cust_to_generate_fu)
                created=0

                email_account = frappe.get_doc("Email Account", "LSA OFFICE")
                sender_email = email_account.email_id
                sender_password = email_account.get_password()
                smtp_server = 'smtp.gmail.com'
                smtp_port = 587
                server = smtplib.SMTP(smtp_server, smtp_port)
                server.starttls()
                server.login(sender_email, sender_password)

                for so in cust_to_generate_fu:
                    try:
                        
                        response=sync_customer(cust_to_generate_fu[so])
                        whatsapp_fu_response=generate_bulk_whatsapp_followup(c_doc.name,customer_name,c_doc.custom_primary_mobile_no)
                        if whatsapp_fu_response["status"]:
                            whatsapp_status_dict["success"]+=[cust_to_generate_fu[so]]
                        else:
                            er_dict={}
                            er_dict["doctype"]= "Custom Error Log"
                            er_dict["master_type"]= "Monthly SO"
                            er_dict["master_reference"]= whatsapp_mon_id
                            er_dict["type"]= "Sales Order"
                            er_dict["record_reference"]= so
                            er_dict["context"]="Email Followup for Auto-gen SO"
                            er_dict["error_statement"]= f'''Error sending WhatsApp followup in Monthly SO bulk operation for {cust_to_generate_fu[so]} for {so} on {today}:{whatsapp_fu_response["msg"]}
                            '''
                            er_doc = frappe.get_doc(er_dict)
                            er_doc.insert()
                            whatsapp_status_dict["failure"]+=[cust_to_generate_fu[so]]
                        
                    except Exception as er:
                        # print("cfu error: ",er)
                        frappe.log_error(f"An error occurred in creating new followup: {er}")
                        er_dict={}
                        er_dict["doctype"]= "Custom Error Log"
                        er_dict["master_type"]= "Monthly SO"
                        er_dict["master_reference"]= whatsapp_mon_id
                        er_dict["type"]= "Sales Order"
                        er_dict["record_reference"]= so
                        er_dict["context"]="Exception in WhatsApp Followup for Auto-gen SO"
                        er_dict["error_statement"]= f'''Exception Error sending WhatsApp followup in Monthly SO bulk operation for {cust_to_generate_fu[so]} for {so} on {today}:{er}
                        '''
                        er_doc = frappe.get_doc(er_dict)
                        er_doc.insert()
                    created+=1
                    frappe.publish_realtime("progress", {
                                                    "total": total,
                                                    "created": created
                                                }, user=frappe.session.user)
                    print(cust_to_generate_fu[so])
                server.quit()
                if not whatsapp_status_dict["failure"]:
                    whatsapp_remainder_freq_doc.last_bulk_creation=datetime.now()
                    whatsapp_remainder_freq_doc.save()
        return {"status_dict":status_dict,"email_status_dict":email_status_dict,"whatsapp_status_dict":whatsapp_status_dict}



@frappe.whitelist()
def generate_bulk_email_followup(response,customer_name,server,sender_email):
    
    details_of_so_due=response["values"]
    print(details_of_so_due)
    # [{'SAL-ORD-2024-03173': [1770.0, 0, 1770.0, datetime.date(2024, 4, 1), datetime.date(2024, 4, 30), 
    #                          'Drafted', 1, 'GANPATHI TEXTILES', '20130009', 'Unpaid', None]}, 
    #  1, 1770.0, 'SAL-ORD-2024-03173']
    if not details_of_so_due:
        return False
    pending_so=details_of_so_due[0]

    message = MIMEMultipart()


    # print(list(details_of_so_due.keys()))
    # so_doc_first=frappe.get_doc("Sales Order",list(details_of_so_due.keys())[0])
    pending_so_table=f'''
    <table class="table table-bordered" style="border-collapse: collapse;width: 100%;">
        <thead>
            <tr style="background-color:#3498DB;color:white;text-align: left;">
                <th style="vertical-align: middle;border: solid 2px #bcb9b4;width: 5%;">S. No.</th>
                <th style="vertical-align: middle;border: solid 2px #bcb9b4;width: 20%;">Sales Order Name</th>
                <th style="vertical-align: middle;border: solid 2px #bcb9b4;width: 15%;">From Date</th>
                <th style="vertical-align: middle;border: solid 2px #bcb9b4;width: 15%;">To Date</th>
                <th style="vertical-align: middle;border: solid 2px #bcb9b4;width: 15%;">Payment Status</th>
                <th style="vertical-align: middle;border: solid 2px #bcb9b4;width: 10%;">Total</th>
                <th style="vertical-align: middle;border: solid 2px #bcb9b4;width: 10%;">Advance Paid</th>
                <th style="vertical-align: middle;border: solid 2px #bcb9b4;width: 10%;">Pending</th>
            </tr>
        </thead>
        <tbody>'''
    total=0.00
    balance=0.00
    count=0
    for so in pending_so:
        if not pending_so[so][10] or so!= "SAL-ORD-2024-03177":
            total+=pending_so[so][0]
            balance+=pending_so[so][2]
            count+=1
            from_date=pending_so[so][3].strftime('%d-%m-%Y')
            to_date= pending_so[so][4].strftime('%d-%m-%Y')
            pending_so_table+=f'''
                                <tr>
                                    <td style="border: solid 2px #bcb9b4;">{count}</td>
                                    <td style="border: solid 2px #bcb9b4;">{so}</td>
                                    <td style="border: solid 2px #bcb9b4;">{ from_date }</td>
                                    <td style="border: solid 2px #bcb9b4;">{ to_date}</td>
                                    <td style="border: solid 2px #bcb9b4;">{ pending_so[so][9] }</td>
                                    <td style="border: solid 2px #bcb9b4;">{ pending_so[so][0] }</td>
                                    <td style="border: solid 2px #bcb9b4;">{ pending_so[so][1] }</td>
                                    <td class="indian-currency2" style="border: solid 2px #bcb9b4;">{ pending_so[so][2] }</td>
                                </tr>'''
            pdf_link=None
            if pending_so[so][9]=="Unpaid":
                pdf_link = f"https://online.lsaoffice.com/api/method/frappe.utils.print_format.download_pdf?doctype=Sales%20Order&name={so}&format=Sales%20Order%20Format&no_letterhead=0&letterhead=LSA&settings=%7B%7D&_lang=en/{so}.pdf"
            elif pending_so[so][9]=="Partially Paid":
                pdf_link=f"https://online.lsaoffice.com/api/method/frappe.utils.print_format.download_pdf?doctype=Sales%20Order&name={so}&format=Sales%20Order%20with%20payment%20details&no_letterhead=0&letterhead=LSA&settings=%7B%7D&_lang=en/{so}.pdf"

            if pdf_link:
                attachment = get_file_from_link(pdf_link)
                if attachment:
                    part = MIMEBase("application", "octet-stream")
                    part.set_payload(attachment)
                    encoders.encode_base64(part)
                    part.add_header(
                        "Content-Disposition",
                        f"attachment; filename= SalesOrder_{so}.pdf",
                    )
                    message.attach(part)
                    
    pending_so_table+="</tbody></table>"


    recipient = "360ithub.developers@gmail.com"
    cc_email = "360ithub.developers@gmail.com"



    
    message['From'] = sender_email
    message['To'] = recipient
    message['Cc'] = cc_email
    message['Subject'] = "Payment Reminder for Pending Sales Orders"

    body = f'''<pre style="font-family: Arial, sans-serif; font-size: 14px; color: #000000;">Dear {customer_name},

I hope this email finds you well.

This is a friendly reminder regarding the due amount for following Sales Order details with ₹ {balance} balance out of net total of ₹ {total}:</pre>'''

    body +=pending_so_table
    body += f'''<pre style="font-family: Arial, sans-serif; font-size: 14px; color: #000000;">We kindly request you to make the payment using the below bank account details:

Bank Account Details:

Account Name: Lokesh Sankhala and Associates
Account Number: 73830200000526
IFSC Code: BARB0VJJCRO
Bank: Bank of Baroda, JC Road, Bangalore-560002
UPI ID: LSABOB@UPI
GPay / PhonePe Number: 9513199200

Please reach out to us immediately if you have any queries or need further assistance.

Best Regards,

LSA Office Account Team
Email: accounts@lsaoffice.com
Phone: 8951692788 </pre>'''

    message.attach(MIMEText(body, 'html'))
    status=None
    msg=""
    try:
        # Send email
        server.sendmail(sender_email, recipient.split(',') + cc_email.split(','), message.as_string())
        # print("Follow-up email sent successfully!")
        status= True
        msg="Success"
    except Exception as e:
        print(f"Failed to send follow-up email. Error: {e}")
        msg=f"Failed to send follow-up email. Error: {e}"
        status= False
    
    return {"status":status,"msg":msg}

def get_file_from_link(link):
    try:
        response = requests.get(link)
        if response.status_code == 200:
            return response.content
        else:
            print(f"Failed to fetch file from link. Status code: {response.status_code}")
            return None
    except Exception as e:
        print(f"Error fetching file from link: {e}")
        return None



@frappe.whitelist()
def generate_bulk_whatsapp_followup(customer_id,customer_name,new_mobile):
    new_mobile="9098543046"
    resp=wa_followup_customer(customer_id,customer_name,new_mobile)
    status=resp["status"]
    msg=resp["msg"]
    return {"status":status,"msg":msg}



# @frappe.whitelist()
# def generate_bulk_customer_followup():
#     remainder_freq=frappe.get_all("Monthly SO Remainder",filters={"active":"Yes"},order_by="effective_from desc")
#     if remainder_freq and len(remainder_freq)==1:
#         remainder_freq_doc=frappe.get_doc("Monthly SO Remainder",remainder_freq[0].name)
#         mon_id=remainder_freq_doc.parent
        
#         next_followup_date_mon=remainder_freq_doc.effective_from
#         if remainder_freq_doc.last_bulk_creation:
#             next_followup_date_mon=remainder_freq_doc.last_bulk_creation
#         next_followup_date=next_followup_date_mon+timedelta(remainder_freq_doc.frequency)
        
#         today=datetime.now().date()
#         # if True:
#         # if today!=remainder_freq_doc.last_bulk_creation and today==next_followup_date:
#         if True:

#             self=frappe.get_doc("Monthly SO",mon_id)
#             cur_month = self.month.lower()
#             cur_year = [int(y) for y in self.fy.split("-")]
#             first_day_of_month, last_day_of_month = get_date_range_of_so(cur_month, cur_year)
#             so_cur_mon_auto = frappe.get_all("Sales Order", filters={
#                                                                     "custom_so_from_date": (">=", first_day_of_month),
#                                                                     "custom_so_to_date": ("<=", last_day_of_month),
#                                                                     "custom_auto_generated": 1,
#                                                                     # "customer":"20130669",
#                                                                 },
#                                                             fields=["name","customer"]              
#                                                                 )
#             # print(so_cur_mon_auto)
#             cust_to_generate_fu={i.name:i.customer for i in so_cur_mon_auto}
#             status_dict={"success":[],"failure":[]}
#             email_status_dict={"success":[],"failure":[]}
#             whatsapp_status_dict={"success":[],"failure":[]}
#             total=len(cust_to_generate_fu)
#             created=0
#             for so in cust_to_generate_fu:
#                 try:
#                     open_fu = frappe.get_all("Customer Followup",filters={
#                                                                         "status":"Open",
#                                                                         "customer_id":cust_to_generate_fu[so],
#                                                                         })
#                     create_new_fu=True
#                     next_followup_date=None
#                     if open_fu:
#                         # print("open fu")
#                         open_fu_doc=frappe.get_doc("Customer Followup",open_fu[0].name)
#                         if so in open_fu_doc.sales_order_summary:
#                             create_new_fu=False
#                             status_dict["success"]+=[cust_to_generate_fu[so]]
#                         else:
#                             next_followup_date=open_fu_doc.next_followup_date
#                             open_fu_doc.status="Closed"
#                             open_fu_doc.followup_note="New Followup created with newly added SO"
#                             open_fu_doc.save()
#                         # print("open fu executed")
#                     response=sync_customer(cust_to_generate_fu[so])
#                     # response=False
#                     # print("response",response,cust_to_generate_fu[so])
#                     if create_new_fu:
#                         if response["status"]!="Sync Failed.":
#                             print("new fu")
#                             doc = frappe.new_doc("Customer Followup")
#                             doc.customer_id = cust_to_generate_fu[so]
#                             doc.followup_type="Call"
#                             doc.sales_order_summary = response["values"][3]
#                             doc.total_remaining_balance=response["values"][2]
#                             if not next_followup_date or next_followup_date<next_followup_date_mon:
#                                 doc.next_followup_date=next_followup_date_mon
#                             elif next_followup_date>first_day_of_month:
#                                 doc.next_followup_date=next_followup_date
#                             # print(next_followup_date,next_followup_date_mon,doc.next_followup_date)
#                             doc.executive="latha.st@lsaoffice.com"
#                             doc.insert()
#                             status_dict["success"]+=[cust_to_generate_fu[so]]
#                         else:
#                             status_dict["failure"]+=[cust_to_generate_fu[so]]

#                     # print("customer fu execution completed")

#                     email_fu_response=generate_bulk_email_followup(response)
#                     if email_fu_response:
#                         email_status_dict["success"]+=[cust_to_generate_fu[so]]
#                     else:
#                         email_status_dict["failure"]+=[cust_to_generate_fu[so]]



#                     # whatsapp_fu_response=generate_bulk_whatsapp_followup(response)
#                     # if whatsapp_fu_response:
#                     #     whatsapp_status_dict["success"]+=[cust_to_generate_fu[so]]
#                     # else:
#                     #     whatsapp_status_dict["failure"]+=[cust_to_generate_fu[so]]
                    
#                 except Exception as er:
#                     status_dict["failure"]+=[cust_to_generate_fu[so]]
#                     # print("cfu error: ",er)
#                     frappe.log_error(f"An error occurred in creating new followup: {er}")
#                 created+=1
#                 frappe.publish_realtime("progress", {
#                                                 "total": total,
#                                                 "created": created
#                                             }, user=frappe.session.user)
#                 print(cust_to_generate_fu[so])
#             # print(status_dict["failure"])
#             # print(email_status_dict["failure"])
#             # print(whatsapp_status_dict["failure"])
#             if not status_dict["failure"]:
#                 remainder_freq_doc.last_bulk_creation=datetime.now()
#                 remainder_freq_doc.save()
#             # return {"status_dict":status_dict,"email_status_dict":email_status_dict,"whatsapp_status_dict":whatsapp_status_dict}
#             return {"status_dict":status_dict,"email_status_dict":email_status_dict}