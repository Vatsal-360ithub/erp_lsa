# Copyright (c) 2024, Mohan and contributors
# For license information, please see license.txt
import frappe, os,csv,requests,boto3,calendar,time
from frappe.model.document import Document
from datetime import datetime,timedelta, date
from dateutil.relativedelta import relativedelta

import datetime as dt
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.mime.base import MIMEBase
from email import encoders
from frappe.utils.print_format import download_pdf
from lsa.custom_mail import single_mail, create_smtp_server, terminate_smtp_server, single_mail_with_attachment_with_server


from lsa.custom_customer import sync_customer
from lsa.lsa.doctype.payment_link_log.payment_link_log import cancel_link
from lsa.custom_sales_order import create_razorpay_payment_link_sales_order
from lsa.custom_customer import wa_followup_customer
from lsa.custom_whatsapp_api import validate_whatsapp_instance, send_custom_whatsapp_message_with_file



class RecurringServicePricing(Document):

    def on_update(self):
        frequency_dict =    {
                "Monthly": "M",
                "Quarterly": "Q",
                "Half-yearly": "H",
                "Yearly": "Y"
            }
        if self.status == "Approved" :
            # print("Approved Trigered!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!")
            # print(type(self.effective_from))
            # print(self.effective_from)
            all_active_service_prices = frappe.get_all("Recurring Service Pricing",
                                               filters={"customer_id": self.customer_id,
                                                        "status": "Approved",
                                                        "name": ("not in", [self.name])})
            if all_active_service_prices:
                # frappe.throw(f"An Active Pricing {all_active_service_prices[0].name} for the customer Already Exist, first Discontinue it")
                for rsp in all_active_service_prices:
                    rsp_doc= frappe.get_doc("Recurring Service Pricing",rsp.name)
                    rsp_doc.effective_to=datetime.strptime(str(self.effective_from), '%Y-%m-%d').date()- timedelta(days=1)
                    rsp_doc.status = "Discontinued"
                    rsp_doc.save()
            elif not self.effective_from:
                frappe.throw("Effective From date is necessary before setting the doc status to 'Approved'")
            elif not self.mode_of_approval:
                frappe.throw("Mode of Approval is necessary before setting the doc status to 'Approved'")
            elif not self.approval_doc:
                pass
                #frappe.throw("Approval Attachment is necessary before setting the doc status to 'Approved'")

            all_inactive_service_prices = frappe.get_all("Recurring Service Pricing",
                                                        filters={"customer_id": self.customer_id,
                                                                "status": "Discontinued",
                                                                "name": ("not in", [self.name])},
                                                        fields=["effective_to"])
            doc_frm_dt=datetime.strptime(str(self.effective_from), '%Y-%m-%d').date()
            for pr in all_inactive_service_prices:
                # frappe.msgprint(str(pr["effective_to"]))
                # print(doc_frm_dt,pr["effective_to"])
                if doc_frm_dt <= pr["effective_to"]:
                    pass
                    # frappe.throw("Pricing for selected Effective From Date already exists")


            ##############################################################################

            service_ids=[i.service_id for i in self.recurring_services if i.price_revised=="Yes"]
            last_active_service_prices = frappe.get_all("Recurring Service Pricing",
                                                        filters={"customer_id":self.customer_id,
                                                                    "status":"Discontinued",},
                                                        order_by="effective_to desc",
                                                        limit=1)
            
            old_service_id_effective_date={}
            prev_price_doc=self.name
            if last_active_service_prices:
                price_doc = frappe.get_doc("Recurring Service Pricing",last_active_service_prices[0].name)
                for price_item in price_doc.recurring_services:
                    old_service_id_effective_date[price_item.service_id]=price_item.effective_from
                price_doc.next_pricing=self.name
                price_doc.save()
                prev_price_doc=price_doc.name
            if self.service_active==0:      
                # print("Service Masters GEtting Updatedddddddddddddddddddddddddddddddddddd!!!!!!!!!!!!!!select * from `tabSessions`;!!!!!!!!!!!!!!!!29BPOPM7873K2ZS bench --site lsa.local mariadb") 
                for item in self.recurring_services:
                    if item.price_revised=="Yes":
                        item.effective_from = self.effective_from
                    elif item.service_id in old_service_id_effective_date:
                        item.effective_from = old_service_id_effective_date[item.service_id]
                    else:
                        item.effective_from = self.effective_from
                    item.enabled = 1
                    item.save()
                    # print(item.service_name,item.revised_charges,frequency_dict[item.frequency],item.frequency )
                    master_service_doc = frappe.get_doc(item.service_type,item.service_id)
                    item_master_list=frappe.get_all("Service Master Addon",
                                                        filters={
                                                            'parent':item.service_id,
                                                            "addon_service_name":item.service_name
                                                        },)
                    if item_master_list:
                        frappe.delete_doc("Service Master Addon",item_master_list[0].name)
                    master_service_doc.reload()

                    new_item = master_service_doc.append('addon_services', {})
            
                    # Set values for fields in the new row
                    new_item.addon_service_name = item.service_name
                    new_item.current_charges = item.revised_charges
                    new_item.frequency = frequency_dict[item.frequency] 
                    master_service_doc.save()
                    # print(master_service_doc.addon_services)

                self.service_active=1
                self.previous_pricing=prev_price_doc
                self.save()
        elif self.status == "Discontinued" :
            
            if not self.effective_to:
                frappe.throw("Effective To date is necessary before setting the doc status to 'Discontinued'")
            doc_frm_dt=datetime.strptime(str(self.effective_from), '%Y-%m-%d').date()
            doc_to_dt=datetime.strptime(str(self.effective_to), '%Y-%m-%d').date()
            if doc_frm_dt >= doc_to_dt:
                frappe.throw(f"Invalid Effective To Date {self.customer_id}")

            for item in self.recurring_services:
                # # print(self.effective_to)
                # item_master_list=frappe.get_all("Service Master Addon",
                #                                 filters={
                #                                             'parent':item.service_id,
                #                                             "addon_service_name":item.service_name
                #                                         },
                #                                         )
                # if item_master_list:
                #     # frappe.delete_doc("Service Master Addon",item_master_list[0].name)
                #     print("HEy")
                item.effective_to=self.effective_to
                item.enabled=0
                item.save()
            if self.service_active!=0:
                self.service_active=0
                self.save()


    # def on_update(self):
    #     if self.status == "Approved" :
    #         # print(type(self.effective_from))
    #         # print(self.effective_from)
    #         all_active_service_prices = frappe.get_all("Recurring Service Pricing",
    #                                            filters={"customer_id": self.customer_id,
    #                                                     "status": "Approved",
    #                                                     "name": ("not in", [self.name])})
    #         if all_active_service_prices:
    #             # frappe.throw(f"An Active Pricing {all_active_service_prices[0].name} for the customer Already Exist, first Discontinue it")
    #             for rsp in all_active_service_prices:
    #                 rsp_doc= frappe.get_doc("Recurring Service Pricing",rsp.name)
    #                 rsp_doc.effective_to=datetime.strptime(str(self.effective_from), '%Y-%m-%d').date()- timedelta(days=1)
    #                 rsp_doc.status = "Discontinued"
    #                 rsp_doc.save()
    #         elif not self.effective_from:
    #             frappe.throw("Effective From date is necessary before setting the doc status to 'Approved'")
    #         elif not self.mode_of_approval:
    #             frappe.throw("Mode of Approval is necessary before setting the doc status to 'Approved'")
    #         elif not self.approval_doc:
    #             pass
    #             #frappe.throw("Approval Attachment is necessary before setting the doc status to 'Approved'")

    #         all_inactive_service_prices = frappe.get_all("Recurring Service Pricing",
    #                                                     filters={"customer_id": self.customer_id,
    #                                                             "status": "Discontinued",
    #                                                             "name": ("not in", [self.name])},
    #                                                     fields=["effective_to"])
    #         doc_frm_dt=datetime.strptime(str(self.effective_from), '%Y-%m-%d').date()
    #         for pr in all_inactive_service_prices:
    #             # frappe.msgprint(str(pr["effective_to"]))
    #             # print(doc_frm_dt,pr["effective_to"])
    #             if doc_frm_dt <= pr["effective_to"]:
    #                 pass
    #                 # frappe.throw("Pricing for selected Effective From Date already exists")


    #         ##############################################################################

    #         service_ids=[i.service_id for i in self.recurring_services if i.price_revised=="Yes"]
    #         last_active_service_prices = frappe.get_all("Recurring Service Pricing",
    #                                                     filters={"customer_id":self.customer_id,
    #                                                                 "status":"Discontinued",},
    #                                                     order_by="effective_to desc",
    #                                                     limit=1)
            
    #         old_service_id_effective_date={}
    #         prev_price_doc=self.name
    #         if last_active_service_prices:
    #             price_doc = frappe.get_doc("Recurring Service Pricing",last_active_service_prices[0].name)
    #             for price_item in price_doc.recurring_services:
    #                 old_service_id_effective_date[price_item.service_id]=price_item.effective_from
    #             price_doc.next_pricing=self.name
    #             price_doc.save()
    #             prev_price_doc=price_doc.name
    #         if self.service_active==0:       
    #             for item in self.recurring_services:
    #                 if item.price_revised=="Yes":
    #                     item.effective_from = self.effective_from
    #                 elif item.service_id in old_service_id_effective_date:
    #                     item.effective_from = old_service_id_effective_date[item.service_id]
    #                 else:
    #                     item.effective_from = self.effective_from
    #                 item.enabled = 1
    #                 item.save()
    #                 master_service_doc = frappe.get_doc(item.service_type,item.service_id)
    #                 if master_service_doc.current_recurring_fees!=item.revised_charges:
    #                     master_service_doc.current_recurring_fees=item.revised_charges
    #                 master_service_doc.save()
    #             self.service_active=1
    #             self.previous_pricing=prev_price_doc
    #             self.save()
    #     elif self.status == "Discontinued" :
            
    #         if not self.effective_to:
    #             frappe.throw("Effective To date is necessary before setting the doc status to 'Discontinued'")
    #         doc_frm_dt=datetime.strptime(str(self.effective_from), '%Y-%m-%d').date()
    #         doc_to_dt=datetime.strptime(str(self.effective_to), '%Y-%m-%d').date()
    #         if doc_frm_dt >= doc_to_dt:
    #             frappe.throw(f"Invalid Effective To Date {self.customer_id}")

    #         for item in self.recurring_services:
    #             # print(self.effective_to)
    #             item.effective_to=self.effective_to
    #             item.enabled=0
    #             item.save()
    #         if self.service_active!=0:
    #             self.service_active=0
    #             self.save()
            



@frappe.whitelist()
def fetch_services(customer_id=None):
    frequency_map={"M":"Monthly","Q":"Quarterly","H":"Half-yearly","Y":"Yearly"}
    all_services = frappe.get_all("Customer Chargeable Doctypes")
    existing_pricing=frappe.get_all("Recurring Service Pricing",
                                    filters={"customer_id":customer_id,
                                             "status":"Approved"},)
    existing_pricing_items={}
    if existing_pricing and len(existing_pricing)==1:
        existing_pricing=frappe.get_doc("Recurring Service Pricing",existing_pricing[0].name)
        for row in existing_pricing.recurring_services:
            existing_pricing_items[(row.service_id,row.service_name)]=row.revised_charges

    # print(existing_pricing_items)
    c_services=[]
    for service in all_services:
        # print(service["name"])
        # if service["name"] in ("IT Assessee File","Gstfile"):
            # print(service["name"])
            
        c_services_n= (frappe.get_all(service["name"], 
                                        filters={'customer_id': customer_id,"enabled":1},
                                        fields=["name","description"]))
        for c_service in c_services_n:
            c_services_addons= (frappe.get_all("Service Master Addon", 
                                            filters={"parenttype":service["name"],'parent': c_service.name},
                                            fields=["name","parent","parenttype","addon_service_name","current_charges","frequency"]))
            for c_services_addon in c_services_addons:
                # c_service["service_type"]=service["name"]
                # print(c_service["name"])
                c_services_addon["description"]=c_service["description"]
                c_services_addon["frequency"]=frequency_map[c_services_addon["frequency"]]
                c_services_addon["service_type"]=c_services_addon["parenttype"]
                if (c_services_addon["parent"],c_services_addon["addon_service_name"]) in existing_pricing_items:
                    c_services_addon["current_recurring_fees"]=existing_pricing_items[(c_services_addon["parent"],c_services_addon["addon_service_name"])]
                else:
                    c_services_addon["current_recurring_fees"]=c_services_addon["current_charges"]
                c_services_addon["name"]=c_service.name
                c_services+=[(c_services_addon)]
            # for c_service in c_services_n:
            #   pass
    
    if c_services:
        # For demonstration purposes, let's just send back a response.
        data = c_services
        return data
    else:
        return "No data found for the given parameters."


@frappe.whitelist()
def fetch_price_revisions(customer_id=None,cur_pricing=None):
    pricings=frappe.get_all("Recurring Service Pricing",
                            filters={"customer_id":customer_id,
                                     "name":("not in",[cur_pricing])},
                            fields=["customer_id","name","effective_from","effective_to","status","fy"])
    cur_pricings=frappe.get_doc("Recurring Service Pricing",cur_pricing)
    old_pricings=[]
    new_pricings=[]
    for pricing in pricings:
        if (cur_pricings.effective_from is None) or (cur_pricings.effective_to is None and pricing.effective_from is not None) \
            or ( pricing.effective_to is not None and pricing.effective_to <=cur_pricings.effective_from):
            old_pricings.append(pricing)
        else:
            new_pricings.append(pricing)
    return {"old_pricings":old_pricings,"new_pricings":new_pricings,}

    
@frappe.whitelist()
def fetch_recent_pricings(customer_id=None):
    pricings=frappe.get_all("Recurring Service Pricing",
                            filters={"customer_id":customer_id},
                            fields=["name","effective_from","effective_to"],
                            order_by="effective_from desc",
                            limit=4)
    return [(f"{i.name}({i.effective_from}-{i.effective_to})",) for i in pricings]

@frappe.whitelist()
def fetch_service_pricing(customer_id=None,service_id=None):

    pr_rev=[]

    pricing_approved=frappe.get_all("Recurring Service Pricing",
                            filters={"customer_id":customer_id,
                                     "status":"Approved"},
                            order_by="effective_from desc",)
    if pricing_approved:
        pr_doc_ap=frappe.get_doc("Recurring Service Pricing",pricing_approved[0].name)
        for item in pr_doc_ap.recurring_services:
            if item.service_id==service_id:
                pr_rev.append({"name":pr_doc_ap.name,"status":pr_doc_ap.status,"current_charges":item.current_charges,"revised_charges":item.revised_charges,
                               "effective_from":item.effective_from,"effective_to":item.effective_to})
                
    pricings=frappe.get_all("Recurring Service Pricing",
                        filters={"customer_id":customer_id,
                                    "status":"Discontinued"},
                        order_by="effective_from desc",)
    for pr in pricings:
        pr_doc=frappe.get_doc("Recurring Service Pricing",pr.name)
        for item in pr_doc.recurring_services:
            # print(item.service_id,service_id ,item.price_revised)
            if item.service_id==service_id and item.price_revised=="Yes":
                pr_rev.append({"name":pr_doc.name,"status":pr_doc.status,"current_charges":item.current_charges,"revised_charges":item.revised_charges,
                               "effective_from":item.effective_from,"effective_to":item.effective_to})
    
    return {"pricing_revision":pr_rev}



# @frappe.whitelist()
# def bulk_first_pricing(customer_id=None,service_id=None):
#     customer_list=frappe.get_all("Customer",
#                                 #  filters={'name': "20130009"},
#                                  fields=["name","disabled"])
#     count=1
#     customer_count=1
#     error_count=1
#     customer_service_list={}
#     for customer in customer_list:
#         exceptions=[]
#         # print(customer)
#         try:
            
#             customer_service=fetch_services(customer.name)
#             # print(customer_service)

#             new_doc = frappe.new_doc('Recurring Service Pricing')

#             new_doc.customer_id = customer.name
#             new_doc.service_active = 1



#             new_doc.status = "Need to Revise"

#             effective_from_date = dt.date(2024, 4, 1)

#             for service in customer_service:
#                 service_item = new_doc.append("recurring_services")
#                 service_item.service_type=service["service_type"]
#                 service_item.service_id = service.name
#                 service_item.company_name=service.description.split("-")[0]
#                 service_item.effective_from=effective_from_date
#                 service_item.current_charges=service.current_recurring_fees
#                 service_item.revised_charges=service.current_recurring_fees
#                 service_item.enabled = 1
#                 service_item.price_revised="Yes"
#                 service_item.frequency=""
#                 service_item.service_enabled=service.enabled
#                 # print("Service Count: ",count)
#                 count+=1
#             # print("Customer Count: ",customer_count)
#             customer_count+=1
#             new_doc.effective_from = effective_from_date
            
#             new_doc.fy = "2023-2024"
#             new_doc.save()

#             new_doc.status = "Revised"
#             new_doc.save()

#             new_doc.status = "Informed to Client"
#             new_doc.save()

#             new_doc.mode_of_approval = "Meeting"
#             # new_doc.status = "Approved"
#             # new_doc.previous_pricing=new_doc.name
#             # new_doc.save()
#         except Exception as e:
#             exceptions.append(e)
#             # print("Error Count: ",error_count)
#             error_count+=1
#             # print(e)
#     return {"msg":"Pricing Created","errors":exceptions}
        

    

    

# @frappe.whitelist()
# def bulk_price_revision_from_excel():
#     file_path = "/home/frappeuser/bench-lsa/apps/lsa/lsa/modified_15_May.csv"
#     customer_list = []
#     service_price_map = {}
#     exceptions = []
#     exception_record = []

#     # Read the CSV file
#     try:
#         with open(file_path, mode='r') as file:
#             csv_reader = csv.reader(file)
#             next(csv_reader)  # Skip the header row if there is one
#             for row in csv_reader:
#                 try:
#                     if row[3].strip().isnumeric():
#                         price = float(row[3].strip())
#                         service_price_map[(row[0].strip(), row[1].strip(), row[2].strip())] = price
#                         if row[0].strip() not in customer_list:
#                             customer_list.append(row[0].strip())
#                     else:
#                         exception_record.append(row)
#                         frappe.log_error(f"Non-numeric price found: {row}", "CSV Parsing Error")
#                 except Exception as er:
#                     exception_record.append(row)
#                     frappe.log_error(f"Error processing row: {row} - {str(er)}", "CSV Row Processing Error")
#     except Exception as e:
#         frappe.log_error(f"Error opening file: {str(e)}", "File Read Error")
#         return {"status": False, "message": "File read error", "error": str(e)}

#     count = 0
#     customer_count = 0
#     error_count = 1
#     old_serv_count = 0
#     new_serv_count = 0

#     for customer in customer_list:
#         try:
#             customer_service = fetch_services(customer)
#             if customer_service:
#                 new_doc = frappe.new_doc('Recurring Service Pricing')
#                 new_doc.customer_id = customer
#                 new_doc.status = "Need to Revise"
#                 effective_from_date = dt.date(2024, 4, 1)
#                 new_doc.effective_from = effective_from_date
#                 new_doc.fy = "2024-2025"

#                 for service in customer_service:
#                     service_item = new_doc.append("recurring_services")
#                     service_item.service_type = service["service_type"]
#                     service_item.service_id = service["name"]
#                     service_item.company_name = service["description"].split("-")[0]
#                     service_item.frequency = service.frequency
#                     service_item.current_charges = service.current_recurring_fees

#                     key = (customer, service["service_type"], service["name"])
#                     if key in service_price_map:
#                         service_item.revised_charges = service_price_map[key]
#                         new_serv_count += 1
#                         del service_price_map[key]
#                     else:
#                         service_item.revised_charges = service.current_recurring_fees
#                         old_serv_count += 1

#                     service_item.enabled = 1
#                     service_item.price_revised = "Yes" if service_item.revised_charges != service_item.current_charges else "No"
#                     service_item.service_enabled = service.enabled
#                     count += 1

#                 new_doc.save()
#                 frappe.db.commit()
#                 customer_count += 1

#         except Exception as e:
#             frappe.log_error(f"Error processing customer: {customer} - {str(e)}", "Customer Processing Error")
#             exceptions.append(str(e))
#             error_count += 1

#     return {
#         "msg": "Pricing Created",
#         "errors": exceptions,
#         "exception_record": exception_record,
#         "customer_count": customer_count,
#         "service_count": count,
#         "old_service_count": old_serv_count,
#         "new_service_count": new_serv_count,
#         "remaining_service_price_map": service_price_map
#     }






@frappe.whitelist()
def rsp_revision_mail(rsp_id=None, recipient=None, subject=None, bodyh=None,bodyf=None):
    if rsp_id and recipient and subject and bodyh and bodyf:
        rsp_doc = frappe.get_doc("Recurring Service Pricing", rsp_id)

        email_account = frappe.get_doc("Email Account", "LSA Accounts")
        sender_email = email_account.email_id
        sender_password = email_account.get_password()
        # cc_email = "360ithub.developers@gmail.com"
        
        body=""
        for i in (bodyh.split("\n")):
            
            if i:
                body+=f'<pre style="font-family: Arial, sans-serif;margin: 0; padding: 0;">{i}</pre>'
            else:
                body+='<br>'

            # print(i1)

        body += """
                <br><table class="table table-bordered" style="border-color: #444444; border-collapse: collapse; width: 100%;">
                    <thead>
                        <tr style="background-color:#3498DB;color:white;text-align: left;">
                            <th style="vertical-align: middle;border: solid 2px #bcb9b4; width: 10%;">S. No.</th>
                            <th style="vertical-align: middle;border: solid 2px #bcb9b4; width: 15%;">Service Type</th>
                            <th style="vertical-align: middle;border: solid 2px #bcb9b4; width: 15%;">Service ID</th>
                            <th style="vertical-align: middle;border: solid 2px #bcb9b4; width: 35%;">Company Name</th>
                            <th style="vertical-align: middle;border: solid 2px #bcb9b4; width: 15%;">Revised Charges(INR)</th>
                            <th style="vertical-align: middle;border: solid 2px #bcb9b4; width: 10%;">Payment Terms</th>
                        </tr>
                    </thead>
                    <tbody>
                """
        count=1
        for service in rsp_doc.recurring_services:
            body += f"""
                <tr>
                    <td style="border: solid 2px #bcb9b4;">{count}</td>
                    <td style="border: solid 2px #bcb9b4;">{service.service_type}</td>
                    <td style="border: solid 2px #bcb9b4;">{service.service_id}</td>
                    <td style="border: solid 2px #bcb9b4;">{service.company_name}</td>
                    <td style="border: solid 2px #bcb9b4;">{service.revised_charges}</td>
                    <td style="border: solid 2px #bcb9b4;">{service.frequency}</td>
                </tr>
            """
            count+=1

        body += """
                    </tbody>
                </table><br>

        """



        for j in (bodyf.split("\n")):
            if j:
                body+=f'<pre style="font-family: Arial, sans-serif;margin: 0; padding: 0;">{j}</pre>'
            else:
                body+='<br>'

        # print(body)
        # Create the email message
        message = MIMEMultipart()
        message['From'] = sender_email
        message['To'] = recipient
        # message['Cc'] = cc_email
        message['Subject'] = subject
        message.attach(MIMEText(body, 'html'))

        # Attach the PDF file
        pdf_link = f"https://online.lsaoffice.com/api/method/frappe.utils.print_format.download_pdf?doctype=Recurring%20Service%20Pricing&name={rsp_id}&format=Recurring%20Service%20Pricing%20default&no_letterhead=0&letterhead=LSA&settings=%7B%7D&_lang=en/{rsp_id}.pdf"
        pdf_filename = "quotation_service_price_revision.pdf"
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
        smtp_server = 'smtp-mail.outlook.com'
        smtp_port = 587
        with smtplib.SMTP(smtp_server, smtp_port) as server:
            server.starttls()
            server.login(sender_email, sender_password)
            try:
                # Send email
                server.sendmail(sender_email, recipient.split(',') , message.as_string())
                return "Email sent successfully!"
            except Exception as e:
                # print(f"Failed to send email. Error: {e}")
                return "Failed to send email."
    else:
        return "Invalid parameters passed."
    
def get_file_from_link(link):
    try:
        response = requests.get(link)
        if response.status_code == 200:
            return response.content
        else:
            # print(f"Failed to fetch file from link. Status code: {response.status_code}")
            return None
    except Exception as e:
        # print(f"Error fetching file from link: {e}")
        return None
    


@frappe.whitelist()
def store_rsp_in_s3(rsp_id=None):
    rsp_doc = frappe.get_doc("Recurring Service Pricing", rsp_id)
    # Configure boto3 client
    s3_doc=frappe.get_doc("S3 360 Dev Test")
    # Configure boto3 client
    s3_client = boto3.client(
        's3',
        aws_access_key_id=s3_doc.access_key,
        aws_secret_access_key=s3_doc.secret_key,
        region_name=s3_doc.region_name,
    )

    file_link = f"https://online.lsaoffice.com/api/method/frappe.utils.print_format.download_pdf?doctype=Recurring%20Service%20Pricing&name={rsp_id}&format=Recurring%20Service%20Pricing%20default&no_letterhead=0&letterhead=LSA&settings=%7B%7D&_lang=en/{rsp_id}.pdf"

    # Fetch file content from link
    file_content = get_pdf_for_record(rsp_id)

    if file_content:
        # Bucket name and file name
        bucket_name = 'devbucketindia'
        folder_name = f'vatsal_test/CID/{rsp_doc.customer_id}'
        file_name = f'{rsp_id}.pdf'
        # print(file_content)
        # Upload file to S3
        try:
            response = s3_client.put_object(Bucket=bucket_name, Key=f"{folder_name}/{file_name}", Body=file_content)
            # print(response)
            # print(response.json())
            if response['ResponseMetadata']['HTTPStatusCode'] == 200:
                return "File uploaded successfully"
            else:
                return f"Failed to upload file to S3: {response['ResponseMetadata']['HTTPStatusCode']}"
        except Exception as e:
            # print(e)
            return f"Error uploading file to S3: {e}"
    else:
        return f"Failed to fetch file from link."



def get_pdf_for_record(rsp_id):
    try:
        doc=frappe.get_doc("Recurring Service Pricing",rsp_id)
        # pdf_file = download_pdf(
        doctype="Recurring Service Pricing"
        name=rsp_id
        format="Recurring Service Pricing default"
        doc=doc
        no_letterhead=0
        letterhead="LSA"
        # )
        pdf_file = frappe.get_print(
			doctype, name, format, doc=doc, as_pdf=True, letterhead=letterhead, no_letterhead=no_letterhead
		)
        # print(pdf_file)
        return pdf_file
    except Exception as er:
        # print(er)
        frappe.msgprint(f"Error fetching file: {er}")

# def get_file_from_link(link):
#     try:
#         response = requests.get(link)
#         if response.status_code == 200:
#             return response.status_code, response.content
#         else:
#             print(f"Failed to fetch file from link. Status code: {response.status_code}")
#             return response.status_code, None
#     except Exception as e:
#         print(f"Error fetching file from link: {e}")
#         return 404, None

    

# @frappe.whitelist()
# def rsp_revision_mail_0(rsp_id=None, recipient=None, subject=None, body=None):
#     if rsp_id and recipient and subject and body:
#         emp_ls = frappe.get_doc("Recurring Service Pricing", rsp_id)

#         email_account = frappe.get_doc("Email Account", "LSA OFFICE")
#         sender_email = email_account.email_id
#         sender_password = email_account.get_password()

#         cc_email = "360ithub.developers@gmail.com"

#         # Create the email message
#         message = MIMEMultipart()
#         message['From'] = sender_email
#         message['To'] = recipient
#         message['Cc'] = cc_email
#         message['Subject'] = subject
#         message.attach(MIMEText(body, 'plain'))

#         # Attach the PDF file
#         pdf_link = "https://online.lsaoffice.com/api/method/frappe.utils.print_format.download_pdf?doctype=Recurring%20Service%20Pricing&name=PR-2024-2025-20131037-03&format=Recurring%20Service%20Pricing%20default&no_letterhead=0&letterhead=LSA&settings=%7B%7D&_lang=en/PR-2024-2025-20131037-03.pdf"
#         pdf_filename = "quotation_service_price_revision.pdf"
#         attachment = get_file_from_link(pdf_link)
#         if attachment:
#             part = MIMEBase("application", "octet-stream")
#             part.set_payload(attachment)
#             encoders.encode_base64(part)
#             part.add_header(
#                 "Content-Disposition",
#                 f"attachment; filename= {pdf_filename}",
#             )
#             message.attach(part)

#         # Connect to the SMTP server and send the email
#         smtp_server = 'smtp.gmail.com'
#         smtp_port = 587
#         with smtplib.SMTP(smtp_server, smtp_port) as server:
#             server.starttls()
#             server.login(sender_email, sender_password)
#             try:
#                 # Send email
#                 server.sendmail(sender_email, recipient.split(',') + cc_email.split(','), message.as_string())
#                 return "Email sent successfully!"
#             except Exception as e:
#                 print(f"Failed to send email. Error: {e}")
#                 return "Failed to send email."
#     else:
#         return "Invalid parameters passed."
    


######################################### WhatsApp #####################################################



########################################Single RSP template with PDF###########################################################

@frappe.whitelist()
def whatsapp_RSP_template(docname,new_mobile):
    #new_mobile="9098543046"

    whatsapp_demo = frappe.get_all('WhatsApp Instance',filters={'module':'Accounts','connection_status':1,'active':1})
    if whatsapp_demo:
        sales_invoice_whatsapp_log = frappe.new_doc('WhatsApp Message Log')
        whatsapp_items = []

        invoice_doc = frappe.get_doc('Recurring Service Pricing', docname)
        customer = invoice_doc.customer_id
        effective_from = invoice_doc.effective_from
        customer_name = invoice_doc.customer_name
        docname = invoice_doc.name

        instance = frappe.get_doc('WhatsApp Instance',whatsapp_demo[0].name)
        ins_id = instance.instance_id


        try:
            # Check if the mobile number has 10 digits
            if len(new_mobile) != 10:
                frappe.msgprint("Please provide a valid 10-digit mobile number.")
                return
            parsed_date = datetime.strptime(str(effective_from), '%Y-%m-%d')
            formatted_effective_from = parsed_date.strftime('%B %d, %Y')
            
            message = f'''Dear Sir/Madam,

Please be informed that there will be a revision in pricing effective from {formatted_effective_from}. Should you have any questions or require further discussion, please do not hesitate to contact us.

For continued service, kindly acknowledge this notice by taking a printout, signing it, and returning the signed copy to our office. Alternatively, you may email a scanned copy to accounts@lsaoffice.com at your earliest convenience.

Thank you for your attention to this matter.

Regards
Accounts Team
LSA Office
8951692788'''
            
            ########################### Below commented link is work on Live #######################
            link=f"https://online.lsaoffice.com/api/method/frappe.utils.print_format.download_pdf?doctype=Recurring%20Service%20Pricing&name={docname}&format=Recurring%20Service%20Pricing%20default&no_letterhead=0&letterhead=LSA&settings=%7B%7D&_lang=en/{docname}.pdf"
            # link = f"https://online.lsaoffice.com/api/method/frappe.utils.print_format.download_pdf?doctype=Sales%20Order&name={docname}&format=Sales%20Order%20Format&no_letterhead=0&letterhead=LSA&settings=%7B%7D&_lang=en/{docname}.pdf"
            # link = "https://online.lsaoffice.com/api/method/frappe.utils.print_format.download_pdf?doctype=Sales%20Order&name=SAL-ORD-2023-00262&format=Sales%20Order%20Format&no_letterhead=0&letterhead=LSA&settings=%7B%7D&_lang=en/Invoice.pdf"

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
                                    "customer":customer,})
            
            response = requests.post(url, params=params_1)
            response.raise_for_status()  # Raise an error for HTTP errors (status codes other than 2xx)
            response_data = response.json()
            message_id = response_data['data']['messageIDs'][0]


            # Check if the response status is 'success'
            if response_data.get('status') == 'success':
                # Log the success

                frappe.logger().info("WhatsApp message sent successfully")
                sales_invoice_whatsapp_log.append("details", {
                                                "type": "Recurring Service Pricing",
                                                "document_id": invoice_doc.name,
                                                "mobile_number": new_mobile,
                                                "customer":customer,
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
                return {"status":False,"error":f"{response.json()}","msg":"An error occurred while sending the WhatsApp message."}
            # return {"status":True,"msg":f"{invoice_doc.effective_from},{formatted_effective_from}","template":message}

        except requests.exceptions.RequestException as e:
            # Log the exception and provide feedback to the user
            frappe.logger().error(f"Network error: {e}")
            return {"status":False,"error":e,"msg":"An error occurred while sending the WhatsApp message. Please try again later."}
        except Exception as er:
            # Log the exception and provide feedback to the user
            frappe.logger().error(f"Error: {er}")
            return {"status":False,"error":er,"msg":"An unexpected error occurred while sending the WhatsApp message. Please contact the system administrator."}
    else:
        return {"status":False,"msg":"Your WhatApp API instance is not connected"}


#####################################################################################################
########################## Selected RSP Whatsapp(BULK)  ##################
################################## (RSP with PDF Button)###########################


@frappe.whitelist()
def send_rsp_whatsapp_bulk(new_mobile):
    pass
#     new_mobile_dict = json.loads(new_mobile)
#     count = 0
#     success_number = []
#     success_sales_invoices = []
#     whatsapp_items = []
#     # instance_id=whatsapp_demo.instance_id
#     whatsapp_demo = frappe.get_all('WhatsApp Instance',filters={'module':'Accounts','connection_status':1,'active':1})
#     if whatsapp_demo:
#         whatsapp_demo_doc = instance = frappe.get_doc('WhatsApp Instance',whatsapp_demo[0].name)
#         connection_status = whatsapp_demo_doc.connection_status
#         mobile_numbers =[]
        
#         sales_invoice_whatsapp_log = frappe.new_doc('WhatsApp Message Log')
#         for invoice_key in new_mobile_dict:
#                 # Fetch the sales invoice document based on the key
#                 invoice_doc = frappe.get_doc('Sales Order', invoice_key)
                
#                 from_date = invoice_doc.custom_so_from_date
#                 to_date = invoice_doc.custom_so_to_date
#                 customer = invoice_doc.customer
#                 total = invoice_doc.rounded_total
#                 customer_name = invoice_doc.customer_name
#                 docname = invoice_doc.name
                
#                 ins_id = whatsapp_demo_doc.instance_id


#                 try:
#                     # Check if the mobile number has 10 digits
#                     if len(new_mobile_dict[invoice_key]) != 10:
#                         frappe.msgprint("Please provide a valid 10-digit mobile number.")
#                         return
#                     payment_link=""
#                     if (invoice_doc.custom_razorpay_payment_url):
#                         payment_link=f"Payment Link is : {invoice_doc.custom_razorpay_payment_url}"
                    
#                     mobile_numbers.append(new_mobile_dict[invoice_key])


                    
            
#                     message = f'''Dear {customer_name},
            
# Your Sale Invoice for {from_date} to {to_date} period is due for amount of Rs {total}/- Kindly pay on below bank amount details
        
# Our Bank Account
# Lokesh Sankhala and ASSOSCIATES
# Account No = 73830200000526
# IFSC = BARB0VJJCRO
# Bank = Bank of Baroda,JC Road,Bangalore-560002
# UPI id = LSABOB@UPI
# Gpay / Phonepe no = 9513199200
# {payment_link}
        
# Call us immediately in case of query.
        
# Best Regards,
# LSA Office Account Team
# accounts@lsaoffice.com'''
                    
#                     ########################### Below commented link is work on Live #######################
#                     link = f"https://online.lsaoffice.com/api/method/frappe.utils.print_format.download_pdf?doctype=Sales%20Order&name={invoice_key}&format=Sales%20Order%20Format&no_letterhead=0&letterhead=LSA&settings=%7B%7D&_lang=en/{invoice_key}.pdf"
#                     # link = "https://online.lsaoffice.com/api/method/frappe.utils.print_format.download_pdf?doctype=Sales%20Order&name=SAL-ORD-2023-00262&format=Sales%20Order%20Format&no_letterhead=0&letterhead=LSA&settings=%7B%7D&_lang=en/Invoice.pdf"
            
#                     url = "https://wts.vision360solutions.co.in/api/sendFileWithCaption"
#                     params_1 = {
#                         "token": ins_id,
#                         "phone": f"91{new_mobile_dict[invoice_key]}",
#                         "message": message,
#                         "link": link
#                     }
#                     # print(new_mobile_dict[invoice_key])
#                     # whatsapp_items.append( {"type": "Sales Invoice",
#                     #                         "document_id": invoice_doc.name,
#                     #                         "mobile_number": new_mobile_dict[invoice_key],
#                     #                         "customer":invoice_doc.customer,})
                    
#                     response = requests.post(url, params=params_1)
#                     response.raise_for_status()  # Raise an error for HTTP errors (status codes other than 2xx)
#                     response_data = response.json()

#                     message_id = response_data['data']['messageIDs'][0]

#                     # Check if the response status is 'success'
#                     if response_data.get('status') == 'success':
#                         # Log the success

#                         frappe.logger().info("WhatsApp message sent successfully")
#                         # print("send succesfully")
#                         sales_invoice_whatsapp_log.append("details", {
#                                                         "type": "Sales Order",
#                                                         "document_id": invoice_doc.name,
#                                                         "mobile_number": new_mobile_dict[invoice_key],
#                                                         "customer":invoice_doc.customer,
#                                                         "message_id":message_id
                                                                    
#                                                         # Add other fields of the child table row as needed
#                                                     })
#                     else:
#                         frappe.logger().error(f"Failed to send Whatsapp Message for {invoice_doc.name}")
            
            
#                     frappe.logger().info(f"Sales Order response: {response.text}")
            
#                     # Create a new WhatsApp Message Log document
                    
                    
#                     count += 1 
#                     success_number+=[new_mobile_dict[invoice_key]]
#                     success_sales_invoices+=[invoice_key]

                
            
#                 except requests.exceptions.RequestException as e:
#                     # Log the exception and provide feedback to the user
#                     frappe.logger().error(f"Network error: {e}")
#                     # frappe.msgprint("An error occurred while sending the WhatsApp message. Please try again later.")
#                 except Exception as e:
#                     # Log the exception and provide feedback to the user
#                     frappe.logger().error(f"Error: {e}")
#                     # frappe.msgprint("An unexpected error occurred while sending the WhatsApp message. Please contact the system administrator.")
#         message = '''Dear {customer_name},
            
# Your Sale Invoice for {from_date} to {due_date} period is due for amount of Rs {total}/- Kindly pay on below bank amount details
            
# Our Bank Account
# Lokesh Sankhala and ASSOSCIATES
# Account No = 73830200000526
# IFSC = BARB0VJJCRO
# Bank = Bank of Baroda,JC Road,Bangalore-560002
# UPI id = LSABOB@UPI
# Gpay / Phonepe no = 9513199200
# {payment_link}
        
# Call us immediately in case of query.
        
# Best Regards,
# LSA Office Account Team
# accounts@lsaoffice.com'''
        
#         # sales_invoice_whatsapp_log.sales_invoice = ",".join(success_sales_invoices)
#         # sales_invoice_whatsapp_log.customer = invoice_doc.customer
#         # sales_invoice_whatsapp_log.posting_date = from_date
#         sales_invoice_whatsapp_log.send_date = frappe.utils.now_datetime()
#         # sales_invoice_whatsapp_log.total_amount = total
#         # sales_invoice_whatsapp_log.mobile_no = ",".join(success_number)
#         sales_invoice_whatsapp_log.sender = frappe.session.user
#         # sales_invoice_whatsapp_log.sales_invoice =  docname
#         sales_invoice_whatsapp_log.type = "Template"
#         sales_invoice_whatsapp_log.message = message
#         # sales_invoice_whatsapp_log.file = link
#         # sales_invoice_whatsapp_log.details = whatsapp_items
#         # print( "Sales Invoice",invoice_salesinvoice,mobile_number,invoice_doc.customer)
#         # print(whatsapp_items)
#         sales_invoice_whatsapp_log.insert()
#         if len(success_number)==len(new_mobile_dict):
#             return {"status":True,"msg":"WhatsApp messages sent successfully"}
#         else:
#             msg=f"{len(success_number)} of {len(new_mobile_dict)} WhatsApp messages sent successfully"
#             return {"status":True,"msg":msg}
       
#     else:
#         return {"status":False,"msg":"Your WhatApp API instance is not connected"}

###################################################### RSP with GST Regular ####################################################

# @frappe.whitelist()
# def mark_gst_regular():
#     try:
#         gst_pricing=frappe.get_all("Recurring Service Item",
#                                 filters={"service_type":"Gstfile"},
#                                 fields=["name","parent","service_id"],)
#         gst_pricing_dict={pr.service_id:pr.parent for pr in gst_pricing}
#         if gst_pricing_dict:
#             gst_reg=frappe.get_all("Gstfile",
#                                 filters={"gst_type":"Regular","enabled":1})
#             gst_reg=[gst.name for gst in gst_reg]
#             for gst_pr in gst_pricing_dict :
#                 if gst_pr in gst_reg:
#                     pr_doc=frappe.get_doc("Recurring Service Pricing",gst_pricing_dict[gst_pr])
#                     pr_doc.gst_type="Regular"
#                     pr_doc.save()
#         return {"status":True,"msg":"RSP with GST Regular have been Marked"}
#     except Exception as er:
#         return {"status":False,"msg":f"Error: {er}"}


####################################Srikanth code start ###############################################################################
##########################################  USER AUTH ######################################
import frappe
 
@frappe.whitelist()
def check_user_permission(service_master):
    try:
        # Print the current user for debugging
        # print(frappe.session.user)
        
        # Get all Department Manager documents
        department_managers = frappe.get_all(
            "Department Manager",
            filters={"master_file": service_master},
            fields=["department_head"]
        )

        user_roles = frappe.get_all('Has Role', filters={'parent': frappe.session.user}, fields=['role'])
        

        enable_status=False
        mail_status=False
        for role in user_roles:
            if role.get('role') =="Customer Onboarding Officer":
                enable_status=True
                break
        
        # Check if the department_head matches the current user
        if department_managers and frappe.session.user in [department_managers[0].department_head] :
            mail_status=True
        
        if frappe.session.user in ["Administrator"] :
            mail_status=True
            enable_status=True
        
        return {"status":True,"enable_status":enable_status,"mail_status":mail_status,"msg":"User Authentication"}
    except Exception as e:
        frappe.log_error(frappe.get_traceback(), "Failed to check user permission")
        return {"status":False,"msg":f"Error authenticating user{e}"}

@frappe.whitelist()
def check_and_send_email(recipients, subject, message):
    try:
        # Check if all necessary fields are provided
        if recipients and subject and message:
            send_email(recipients, subject, message)
            return {"status":True,"msg":"Mail sent successfully"}
        else:
            frappe.throw("Recipients, subject, and message are all required to send an email.")
            return {"status":False,"msg":"Error sending mail"}
    except Exception as e:
        frappe.log_error(frappe.get_traceback(), "Failed to check and send email")
        return {"status":False,"msg":f"Error sending mail: {e}"}
 
def send_email(recipients, subject, message):
    # frappe.sendmail(
    #     recipients=recipients.split(','),
    #     subject=subject,
    #     message=message,
    # )
    # frappe.db.commit()
    ########################################################## modified by Vatsal #################################################
    recipients=recipients.split(',')
    resp=single_mail("LSA Accounts",recipients,subject,message)
    if not resp["status"]:
        msg=resp['msg']
        # print(f"Failed to send notification: {msg}")
        frappe.log_error(message=f"Failed to send mail for service master {subject}", title=f"Failed to send mail for service master {subject}")
        return {"status":False,"msg": f"Failed to send mail for service master {subject}"}
    
    return {"status":True,"msg": "Mail sent successfully!"}

    ########################################################## modified by Vatsal #################################################



#################################################################Srikanth Code End####################################################



@frappe.whitelist()
def disable_service_file(doctype,file_id,reason):
    try:
    
        service_masters_doc = frappe.get_doc(doctype,file_id)
        old_status=service_masters_doc.enabled
        new_status=None
        if old_status==1:
            old_status="Enabled"
            new_status="Disabled"
            service_masters_doc.enabled=0
        else:
            old_status="Disabled"
            new_status="Enabled"
            service_masters_doc.enabled=1


        service_masters_doc.append('service_status_history', {
            'previous_status': old_status,  # Item name
            'status_changed_to': new_status,
            'reason': reason,
            'modified_by1': frappe.session.user,  # Quantity of the item
            "time_of_change":datetime.now(),
        })

        service_masters_doc.save()
        frappe.db.commit()
        return {"status":True,"msg": f"Service {new_status} successfully"}
    except Exception as e:
        frappe.log_error(frappe.get_traceback(), "Failed to change service status")
        return {"status":False,"msg":f"Error changing service status: {e}"}


@frappe.whitelist()
def fetch_services_for_item(customer_id,item,service_master):
    try:
        service_master_for_customer=frappe.get_all(service_master,
                                                                filters={
                                                                    "customer_id":customer_id,
                                                                    "enabled":1,
                                                                    },
                                                                fields=["name", "description"])
        return {"status":True, "service_master_list":service_master_for_customer}
    except Exception as e:
        frappe.log_error(frappe.get_traceback(), f"Failed to fetch services for item {item} for Customer {customer_id} in Sales Order")
        return {"status":False, "msg":f"Failed to fetch services for item {item} for Customer {customer_id} in Sales Order: {e}"}

@frappe.whitelist()
def fetch_service_master_and_frequency(item_code, description):
    # Fetch all relevant Customer Chargeable Doctypes
    # chargeable_doctype = frappe.get_all(
    #                                     'Customer Chargeable Doctypes',
    #                                     fields=['name'],
    #                                     filters={'service_item': ("like",item_code)}
    #                                 )
    chargeable_doctype = frappe.get_all(
                                        'Lead Items',
                                        fields=['parent'],
                                        filters={'service_name': item_code,
                                                 "parenttype":"Customer Chargeable Doctypes"}
                                    )
    # print(chargeable_doctype)
    if not chargeable_doctype:
        return {"service_master": None, "frequency": "M"}

    # Find the relevant service master
    service_master = chargeable_doctype[0].parent
    # print(service_master)

    if not service_master:
        return {"service_master": None, "frequency": "M"}
    
    service_master_record = frappe.get_all(
                                            service_master,
                                            filters={'description': description},
                                            fields=['name']
                                        )
    # print(service_master_record)
    service_master_record_id=service_master_record[0].name
    # Fetch frequency from Service Master Addon
    service_master_record_doc = frappe.get_doc(service_master,service_master_record_id)
    frequency=None
    for addons in service_master_record_doc.addon_services:
        # print(addons.addon_service_name)
        if item_code==addons.addon_service_name and addons.status=="Running":
            frequency=addons.frequency
            break
    # Default to "M" if no frequency is found
    if not frequency:
        frequency = "M"

    return {
        "service_master": service_master,
        "frequency": frequency
    }

#!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!111
#!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!111
#!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!111
#!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!111
#!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!111
#!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!111






class MonthlySO(Document):
    def on_update(self):
        # scheduler_list=frappe.get_all("Monthly SO Remainder",
        #                                                     filters={"active":"Yes","remainder_type":"Email"},
        #                                                     fields=["name","effective_from"],
        #                                                     order_by="effective_from desc")
        # print(scheduler_list)
        # if len(scheduler_list)>1:
        #     effective_fromdate_list=[i.effective_from for i in scheduler_list]
        #     effective_fromdate_set=set(effective_fromdate_list)
        #     if len(effective_fromdate_list)!=len(effective_fromdate_set):
        #         frappe.throw("Your SO reminder's date range is overlaping")
        #     for scheduler in scheduler_list[1:]:
        #         scheduler_doc=frappe.get_doc("Monthly SO Remainder",scheduler.name)
        #         scheduler_doc.effective_to=scheduler_list[0].effective_from - timedelta(1)
        #         scheduler_doc.active="No"
        #         scheduler_doc.save()
        #     frappe.reload_doc('lsa', 'Monthly SO', self.name)
        
        # scheduler_list=frappe.get_all("Monthly SO Remainder",
        #                                                     filters={"active":"Yes","remainder_type":"WhatsApp"},
        #                                                     fields=["name","effective_from"],
        #                                                     order_by="effective_from desc")
        # print(scheduler_list)
        # if len(scheduler_list)>1:
        #     effective_fromdate_list=[i.effective_from for i in scheduler_list]
        #     effective_fromdate_set=set(effective_fromdate_list)
        #     if len(effective_fromdate_list)!=len(effective_fromdate_set):
        #         frappe.throw("Your SO reminder's date range is overlaping")
        #     for scheduler in scheduler_list[1:]:
        #         scheduler_doc=frappe.get_doc("Monthly SO Remainder",scheduler.name)
        #         scheduler_doc.effective_to=scheduler_list[0].effective_from - timedelta(1)
        #         scheduler_doc.active="No"
        #         scheduler_doc.save()
        #     frappe.reload_doc('lsa', 'Monthly SO', self.name)
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

# frappe.enqueue('tnc_frappe_custom_app.tnc_custom_app.doctype.student_exam.student_exam.process_students_in_background', 
#                         queue='long', 
#                         timeout=6000, 
#                         name=name, 
#                         # limit=limit
#                         )

            
        

@frappe.whitelist()
def generate_bulk_so(fy,month,frequency):
    # print("generate_bulk_so_triggered")
    # print(type(services))
    # services = services.split(",")
    # services = [element.strip() for element in services if element.strip()]
    # services = [element.split("(") for element in services]
    # services = [(element[0],element[1][:1]) for element in services]

    # print(services)

    # self=frappe.get_doc("Recurring Service Pricing",rsp_id)
    success_count = 0
    email_account="LSA Info"
    wa_account="Operations"
    
    # cur_month = self.month.lower()
    # cur_year = today.year
    # first_day_of_month, last_day_of_month = get_date_range_of_so(cur_month, cur_year)
    month_num=datetime.strptime(month, "%B").month
    year =int(fy.split('-')[0] if month_num>3 else fy.split('-')[1])

    # today = datetime.today()
    today = date(year, month_num, 1)
    # print(str(today))
    # frequency = frequency[:-2].replace(" ", "")
    frequency =frequency[:-2].split(', ')
    # print(frequency)
    # print("|".join(frequency[:-2].split(', ')))

    # Get the first day of the current month
    first_day_of_month = today.replace(day=1)

    # Get the last day of the current month
    last_day_of_month = today.replace(day=calendar.monthrange(today.year, today.month)[1])

    all_cust_array = frappe.get_all("Customer",
                                     filters={
                                         "name":"20131037",
                                         "disabled": 0,
                                         "custom_billable": 1,
                                         # "custom_state": ("not in",[None]),
                                     },
                                     fields=["name", "custom_state"])
    all_cust = {i.name: i.custom_state for i in all_cust_array}

    all_rsp = frappe.get_all("Recurring Service Pricing",
                             filters={"status": "Approved",
                                      "automatic_so_creation":1,
                                      "customer_id":"20131037",
                                      },
                             fields=["name", "customer_id","payment_link_generation","share_with_client_via_wa","share_with_client_via_mail",]
                             )
    
    all_rsp_active = [rsp_cu for rsp_cu in all_rsp if rsp_cu.customer_id in all_cust]

    all_rsp = all_rsp_active

    customer_service_map = {}
    customer_failed_service_map = []
    for fr in frequency:
        if all_rsp:
            
            
            # total_rsp=len(all_rsp)
            # in_progress_rsp=0

            for rsp in all_rsp:
                try:
                    customer_so_map = get_so_map(rsp.name, all_cust[rsp.customer_id], first_day_of_month, last_day_of_month,fr)
                    if customer_so_map["status"]:

                        # print(customer_so_map)
                        so_creation_response = create_sales_order(customer_so_map["customer_so_map"])
                        so_id=None
                        if so_creation_response["status"]:
                            customer_service_map[rsp.customer_id] = True
                            so_id=so_creation_response["so_id"]
                            rsp["new_so_id"]=so_id
                            success_count += 1
                        else:
                            er_dict={}
                            er_dict["doctype"]= "Custom Error Log"
                            er_dict["master_type"]= "Recurring Service Pricing"
                            er_dict["master_reference"]= rsp.name
                            er_dict["type"]="Customer"
                            er_dict["record_reference"]= rsp.customer_id
                            er_dict["context"]="Auto postpaid Sales Order creation "
                            er_dict["error_statement"]= f'''Error  creating Monthly SO for {customer_so_map["customer"]}: {so_creation_response["error"]}
                            '''
                            er_doc = frappe.get_doc(er_dict)
                            er_doc.insert()
                            rsp["new_so_id"]=so_id
                            customer_failed_service_map.append(customer_so_map)
                            # print("failed SO: ", customer_so_map["customer"], so_creation_response["error"])
                        if so_id:
                            if rsp.payment_link_generation: 
                                generate_payment_link(so_id,rsp.name)
                            # if rsp.share_with_client_via_wa: 
                            #     autogen_so_mail(so_id, smtp_server,sender_email,rsp.name)
                            # if rsp.share_with_client_via_mail:
                            #     whatsapp_so_template(so_id,rsp.name)
                                
                    elif customer_so_map["status"] in [False]:
                        # print(customer_so_map["error"])
                        
                        er_dict={}
                        er_dict["doctype"]= "Custom Error Log"
                        er_dict["master_type"]= "Recurring Service Pricing"
                        er_dict["master_reference"]= rsp.name
                        er_dict["type"]= "Customer"
                        er_dict["record_reference"]= rsp.customer_id
                        er_dict["context"]="Auto postpaid Sales Order creation "
                        er_dict["error_statement"]= f'''Error fetching details for Monthly SO creation for {customer_so_map["customer"]}: {customer_so_map["error"]}
                        '''
                        er_doc = frappe.get_doc(er_dict)
                        er_doc.insert()
                        rsp["new_so_id"]=None
                        # pass
                        
                except Exception as er:
                    frappe.log_error(f"An error occurred in bulk creation of Sales Orders: {er}")
                    customer_service_map[rsp["customer_id"]] = False
                    er_dict={}
                    er_dict["doctype"]= "Custom Error Log"
                    er_dict["master_type"]= "Recurring Service Pricing"
                    er_dict["master_reference"]= rsp.name
                    er_dict["type"]= "Customer"                 
                    er_dict["record_reference"]= rsp.customer_id
                    er_dict["context"]="Auto postpaid Sales Order creation "
                    er_dict["error_statement"]= f'''Exception Error  creating Monthly SO for {rsp["customer_id"]}: {er}
                    '''
                    er_doc = frappe.get_doc(er_dict)
                    er_doc.insert()
                    rsp["new_so_id"]=None
                    # print(er)
                    # print("failed: ", rsp["customer_id"], str(er))
                # in_progress_rsp+=1
                # frappe.publish_realtime("progress", {
                #                                 "total": total_rsp,
                #                                 "created": in_progress_rsp
                #                             }, user=frappe.session.user)
            try:
                resp_mail_server=create_smtp_server(email_account)
                if resp_mail_server["status"]:
                    smtp_server,sender_email=resp_mail_server["smtp_server"],resp_mail_server["sender_email"]
                    for rsp in all_rsp:
                        if rsp["new_so_id"] and rsp.share_with_client_via_mail: 
                            autogen_so_mail(so_id, smtp_server,sender_email,rsp.name)
                else:
                    er_dict={}
                    er_dict["doctype"]= "Custom Error Log"
                    er_dict["master_type"]= "Email Account"
                    er_dict["master_reference"]= email_account
                    er_dict["type"]= "Recurring Service Pricing"                 
                    # er_dict["record_reference"]= rsp.customer_id
                    er_dict["context"]="Bulk Auto postpaid Sales Order sharing via Email Failed "
                    er_dict["error_statement"]= f'''Exception Error sending bulk Mail for {all_rsp}: {resp_mail_server["msg"]}
                    '''
                    er_doc = frappe.get_doc(er_dict)
                    er_doc.insert()
            except Exception as er:
                er_dict={}
                er_dict["doctype"]= "Custom Error Log"
                er_dict["master_type"]= "Email Account"
                er_dict["master_reference"]= email_account
                er_dict["type"]= "Recurring Service Pricing"                 
                # er_dict["record_reference"]= rsp.customer_id
                er_dict["context"]="Bulk Auto postpaid Sales Order sharing via Email Failed "
                er_dict["error_statement"]= f'''Exception Error sending bulk Mail for {all_rsp}: {er}
                '''
                er_doc = frappe.get_doc(er_dict)
                er_doc.insert()

            try:
                resp_wa_instance=validate_whatsapp_instance(wa_account)
                if resp_wa_instance["status"] :
                    whatsapp_instance_doc=resp_wa_instance["whatsapp_instance_doc"]
                    if int(whatsapp_instance_doc.remaining_credits) >= len(all_rsp):
                        whatsapp_log = frappe.new_doc('WhatsApp Message Log')
                        whatsapp_log.send_date = frappe.utils.now_datetime()
                        whatsapp_log.sender = frappe.session.user
                        whatsapp_log.type = "Template"
                        whatsapp_log.message = '''Dear {customer_name},

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
                        
                        for rsp in all_rsp:
                            if rsp["new_so_id"] and rsp.share_with_client_via_wa: 
                                resp_wa_sent=whatsapp_so_template(whatsapp_instance_doc,so_id,rsp.name)
                                whatsapp_log.append("details",resp_wa_sent["msg_detail"])
                        whatsapp_log.insert()
                    else:
                        er_dict={}
                        er_dict["doctype"]= "Custom Error Log"
                        er_dict["master_type"]= "WhatsApp Instance"
                        er_dict["master_reference"]= wa_account
                        er_dict["type"]= "Recurring Service Pricing"                 
                        # er_dict["record_reference"]= rsp.customer_id
                        er_dict["context"]="Bulk Auto postpaid Sales Order sharing via WhatsaApp Failed due to insufficient credits"
                        er_dict["error_statement"]= f'''Exception Error sending bulk WhatsaApp for {all_rsp}: Actuall Credits {whatsapp_instance_doc.remaining_credits}, Required Credits {len(all_rsp)}
                        '''
                        er_doc = frappe.get_doc(er_dict)
                        er_doc.insert()
                else:
                    er_dict={}
                    er_dict["doctype"]= "Custom Error Log"
                    er_dict["master_type"]= "WhatsApp Instance"
                    er_dict["master_reference"]= wa_account
                    er_dict["type"]= "Recurring Service Pricing"                 
                    # er_dict["record_reference"]= rsp.customer_id
                    er_dict["context"]="Bulk Auto postpaid Sales Order sharing via WhatsaApp Failed "
                    er_dict["error_statement"]= f'''Exception Error sending bulk WhatsaApp for {all_rsp}: {resp_wa_instance["msg"]}
                    '''
                    er_doc = frappe.get_doc(er_dict)
                    er_doc.insert()
            except Exception as er:
                er_dict={}
                er_dict["doctype"]= "Custom Error Log"
                er_dict["master_type"]= "WhatsApp Instance"
                er_dict["master_reference"]= wa_account
                er_dict["type"]= "Recurring Service Pricing"                 
                # er_dict["record_reference"]= rsp.customer_id
                er_dict["context"]="Bulk Auto postpaid Sales Order sharing via WhatsaApp Failed "
                er_dict["error_statement"]= f'''Exception Error sending bulk WhatsaApp for {all_rsp}: {er}
                '''
                er_doc = frappe.get_doc(er_dict)
                er_doc.insert()


            # print(len(customer_service_map))
            # print(customer_failed_service_map)
            # if not customer_failed_service_map:
            #     self.so_generated=1
            #     self.status="SO Created"
            # self.autogenerated_so_count = success_count
            # self.save()




def get_so_map(rsp_id,cust_state,first_day_of_month,last_day_of_month,fr):
    rsp_doc = frappe.get_doc("Recurring Service Pricing", rsp_id)
    so_fields = ["customer", "transaction_date", "custom_so_from_date", "custom_so_to_date",
                    "custom_auto_generated",
                    "tax_category", "taxes_and_charges"]

    customer_so_map = {}

    customer_so_map["customer"] = rsp_doc.customer_id
    customer_so_map["transaction_date"] = first_day_of_month
    
    customer_so_map["custom_auto_generated"] = 1
    customer_so_map["custom_rsp"] = rsp_id

    status,tax_category,taxes_and_charges,taxes=get_taxes(cust_state)
    if status:
        customer_so_map["tax_category"]=tax_category
        customer_so_map["taxes_and_charges"]=taxes_and_charges
        customer_so_map["taxes"]=taxes
    else:
        return {"status":False,"error":f"Taxes Not Mapped properly for {rsp_doc.customer_id}, check customer's State field"}

    services_map, first_day_of_so =get_services(rsp_doc.recurring_services,first_day_of_month,last_day_of_month,fr)

    customer_so_map["custom_so_from_date"] = first_day_of_so 
    customer_so_map["custom_so_to_date"] = first_day_of_month - timedelta(days=1)
    customer_so_map["delivery_date"] = first_day_of_month + timedelta(days=1)
    
    
    if services_map: 
        customer_so_map["items"] = services_map
        # print(len(services_map))
        # print(customer_so_map)
        print(customer_so_map)
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

def get_services(rsp_services,first_day_of_month,last_day_of_month,fr):
    # mon_freq = {
    #             "apr": ["M", "Q", "Y",], 
    #             "may": ["M"], 
    #             "jun": ["M"], 
    #             "jul": ["M", "Q",], 
    #             "aug": ["M"],
    #             "sep": ["M"],
    #             "oct": ["M", "Q" ], 
    #             "nov": ["M"], 
    #             "dec": ["M"], 
    #             "jan": ["M", "Q",], 
    #             "feb": ["M"], 
    #             "mar": ["M"]
    #         }
    mon_freq = {
                4: ["M", "Q", "Y",], 
                5: ["M"], 
                6: ["M"], 
                7: ["M", "Q",], 
                8: ["M"],
                9: ["M"],
                10: ["M", "Q" ], 
                11: ["M"], 
                12: ["M"], 
                1: ["M", "Q",], 
                2: ["M"], 
                3: ["M"]
            }
    freq_map = {"Monthly":"M",
                "Quarterly":"Q",
                "Half-yearly":"H",
                "Yearly":"Y",
                }
    first_day_of_so= first_day_of_month-timedelta(days=1)

    cur_month_freq = mon_freq[first_day_of_month.month]
    services_map = []
    for item in rsp_services:
        service_dict = {}
        service_doc = frappe.get_doc(item.service_type, item.service_id)
        # service_addon_doc = frappe.get_all(filters={"":item.service_type, "":item.service_id},fields:["","","",])
        serv_frequency = freq_map[item.frequency]

        soi_from_date=get_first_day_of_service(serv_frequency,first_day_of_month)
        soi_to_date = first_day_of_month- timedelta(days=1)
        response_validation=validate_service_addons(item.service_name,item.service_id,soi_from_date,soi_to_date)
        if not response_validation["status"]:
            er_dict={}
            er_dict["doctype"]= "Custom Error Log"
            er_dict["master_type"]= "Recurring Service Pricing"
            er_dict["master_reference"]= item.parent
            er_dict["type"]= item.service_type                
            er_dict["record_reference"]= item.service_id
            er_dict["context"]="One addon adding for auto postpaid Sales Order creation"
            er_dict["error_statement"]= f'''Exception Error  creating Monthly SO for {item.parent}: {response_validation['msg']}
            '''
            er_doc = frappe.get_doc(er_dict)
            er_doc.insert()
            # print(f"Service Addon Validation Failed: {response_validation['error']}")
            continue

        # if serv_frequency in cur_month_freq and (item.service_type,serv_frequency) in services:
        if serv_frequency in cur_month_freq and serv_frequency==fr:
            items_fields = ["item_code", "custom_soi_from_date", "custom_soi_to_date", "description",
                            "gst_hsn_code", "qty", "uom", "rate",
                                            "gst_treatment"]
            
            service_dict["item_code"] = item.service_name
            service_dict["custom_soi_from_date"] = soi_from_date
            service_dict["description"] = service_doc.description
            service_dict["custom_service_master"]=service_doc.description
            service_dict["custom_master_order_id"] = item.service_id
            service_dict["gst_hsn_code"] = service_doc.hsn_code
            service_dict["qty"] = 1
            service_dict["rate"] = item.revised_charges
            # service_dict["custom_soi_to_date"] = get_last_day_of_service(serv_frequency)
            service_dict["custom_soi_to_date"] = soi_to_date
            if first_day_of_so>soi_from_date:
                first_day_of_so=soi_from_date
            
            services_map.append(service_dict)
    return services_map,first_day_of_so

def validate_service_addons(item_code,service_master_id,soi_from_date,soi_to_date):

    service_masters_addon_for_current_duration = frappe.get_all(
            "Sales Order Item",
            filters={
                "docstatus": ("in", [0, 1]),  # Only check for draft and submitted records
                "item_code": item_code,  # Match the item code
                "custom_master_order_id": service_master_id,  # Match the master order ID
                # Date range intersection logic:
                # 1. Existing 'from date' <= new 'to date'
                # 2. Existing 'to date' >= new 'from date'
                "custom_soi_from_date": ("<=", soi_to_date),  
                "custom_soi_to_date": (">=", soi_from_date),
            },
            fields=["name","parent"]
        )
    # print("service master itemmmmmmmmmmmmmmmmmmmmmmmmmmmmmm",item_code,service_masters_addon_for_current_duration)
    
    # If overlapping records are found, prevent further processing
    if service_masters_addon_for_current_duration:
        return {"status":False,"msg":f"Not able to add service addon with Auto Bulk SO creation as SO {service_masters_addon_for_current_duration[0].parent} is already existing for the master {service_master_id} addon {item_code} overlaping with the date range {soi_from_date} to {soi_to_date}"}
    return {"status":True}

# def get_last_day_of_service(serv_frequency):
#     month_num = {
#                         "apr": 1, 
#                         "may": 2, 
#                         "jun": 3, 
#                         "jul": 4, 
#                         "aug": 5, 
#                         "sep": 6, 
#                         "oct": 7, 
#                         "nov": 8, 
#                         "dec": 9,
#                         "jan": 10, 
#                         "feb": 11, 
#                         "mar": 12
#                     }
#     freq_mon_num = {
#                         "Y": 12, 
#                         "Q": 3, 
#                         "M": 1,
#                         }
#     serv_frequency_mon_num = freq_mon_num[serv_frequency]
#     last_day_of_serv_month=None
#     last_month_of_serv=month_num[cur_month] + 3 +serv_frequency_mon_num - 1
#     if last_month_of_serv > 12:
#         _, last_day_serv = calendar.monthrange(cur_year[1], last_month_of_serv-12)
#         last_day_of_serv_month = datetime(cur_year[1], last_month_of_serv-12, last_day_serv).date()
#     else:
#         _, last_day_serv = calendar.monthrange(cur_year[0], last_month_of_serv)
#         last_day_of_serv_month = datetime(cur_year[0], last_month_of_serv, last_day_serv).date()
#     return last_day_of_serv_month


def get_first_day_of_service(serv_frequency,first_day_of_month):
    
    freq_mon_num = {
                        "Y": 12, 
                        "Q": 3, 
                        "M": 1,
                        }
    # serv_frequency_mon_num = freq_mon_num[serv_frequency]
    # last_day_of_serv_month=None
    # last_month_of_serv=month_num[cur_month] + 3 +serv_frequency_mon_num - 1
    # if last_month_of_serv > 12:
    #     _, last_day_serv = calendar.monthrange(cur_year[1], last_month_of_serv-12)
    #     last_day_of_serv_month = datetime(cur_year[1], last_month_of_serv-12, last_day_serv).date()
    # else:
    #     _, last_day_serv = calendar.monthrange(cur_year[0], last_month_of_serv)
    #     last_day_of_serv_month = datetime(cur_year[0], last_month_of_serv, last_day_serv).date()
    # return last_day_of_serv_month
    current_month = first_day_of_month.month
    if current_month<4:
        first_day_of_serv_month=first_day_of_month-relativedelta(months=freq_mon_num[serv_frequency])
    else:
        first_day_of_serv_month=first_day_of_month-relativedelta(months=freq_mon_num[serv_frequency])
    return first_day_of_serv_month

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
            # print(f"SO created for {so_doc.customer} {so_doc.name}")
            return {"status":True, "msg":"SO for {customer} created successfully","so_id":so_doc.name}
        except Exception as er:
            # print("Error",er)
            frappe.log_error(f"An error occurred in creating Sales Orders: {er}")

            return {"status":False, "error":f"{er}"}

# @frappe.whitelist()
# def go_to_month_so(rsp_id):
#     month_so_doc = frappe.get_doc("Monthly SO", mon_id)
#     cur_month = month_so_doc.month.lower()
#     cur_year = [int(y) for y in month_so_doc.fy.split("-")]
#     first_day_of_month, last_day_of_month = get_date_range_of_so(cur_month, cur_year)
#     filters={}
#     filters["custom_auto_generated"]=1
#     filters["custom_so_from_date"]=(">=",first_day_of_month)
#     filters["custom_so_to_date"]=("<=",last_day_of_month)

#     return filters


# @frappe.whitelist()
# def update_so_count(rsp_id):
#     month_so_doc = frappe.get_doc("Monthly SO", mon_id)
#     cur_month = month_so_doc.month.lower()
#     cur_year = [int(y) for y in month_so_doc.fy.split("-")]
#     first_day_of_month, last_day_of_month = get_date_range_of_so(cur_month, cur_year)
#     so_cur_mon_auto = frappe.get_all("Sales Order", filters={
#         "custom_so_from_date": (">=", first_day_of_month),
#         "custom_so_to_date": ("<=", last_day_of_month),
#         "custom_auto_generated": 1,
#         "docstatus":("not in",[2]),
#     })
#     new_autogenerated_so_count = len(so_cur_mon_auto)
    
#     so_cur_mon = frappe.get_all("Sales Order", filters={
#         "custom_so_from_date": (">=", first_day_of_month),
#         "custom_so_to_date": ("<=", last_day_of_month),
#         "docstatus":("not in",[2]),
#     })
#     new_so_count = len(so_cur_mon)
#     print(new_so_count,new_autogenerated_so_count)
#     if month_so_doc.auto_generated_so_this_month != new_autogenerated_so_count or month_so_doc.total_so_this_month!=new_so_count:
#         month_so_doc.auto_generated_so_this_month = new_autogenerated_so_count
#         month_so_doc.total_so_this_month = new_so_count
#         month_so_doc.save()
#         return True
    

@frappe.whitelist()
def generate_payment_link(so_id,rsp_id):
    try:
        so_doc = frappe.get_doc("Sales Order", so_id)
        grand_total = so_doc.rounded_total * 1.02
        resp=create_razorpay_payment_link_sales_order(grand_total, so_doc.name,so_doc.customer,
                                                      so_doc.customer_name,so_doc.custom_so_from_date,
                                                      so_doc.custom_so_to_date,so_doc.rounded_total)
        
        if not resp["status"]:
            # print(f"failed for {so_doc.name} with customer {so_doc.customer}: {resp['msg']}")
            er_dict={}
            er_dict["doctype"]= "Custom Error Log"
            er_dict["master_type"]= "Recurring Service Pricing"
            er_dict["master_reference"]= rsp_id
            er_dict["type"]= "Sales Order"
            er_dict["record_reference"]= so_id
            er_dict["context"]="Payment Link Creation for Auto-gen SO"
            er_dict["error_statement"]= f'''Error creating Payment Link for SO bulk creation for {so_doc.customer}: {resp['msg']}
            '''
            er_doc = frappe.get_doc(er_dict)
            er_doc.insert()
    except Exception as er:
        er_dict={}
        er_dict["doctype"]= "Custom Error Log"
        er_dict["master_type"]= "Recurring Service Pricing"
        er_dict["master_reference"]= rsp_id
        er_dict["type"]= "Sales Order"
        er_dict["record_reference"]= so_id
        er_dict["context"]="Payment Link Creation for Auto-gen SO"
        er_dict["error_statement"]= f'''Error creating Payment Link for SO bulk creation for {so_doc.customer}: {er}
        '''
        er_doc = frappe.get_doc(er_dict)
        er_doc.insert()




def autogen_so_mail(so_id, smtp_server,sender_email,rsp_id):
    try:
        so_doc=frappe.get_doc("Sales Order",so_id)

        # sender_password = email_account.get_password()
        base_url = frappe.utils.get_url()

        recipients = so_doc.custom_primary_email

        recipients = "lokesh.bwr@gmail.com"
        cc_email = "vatsal.k@360ithub.com"

        subject = f"New Sales Order generated from {so_doc.custom_so_from_date} to {so_doc.custom_so_to_date}"

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
                # <td style="border: solid 2px #bcb9b4;width: 15%;">{item.custom_service_master.split("-")[-1]}</td>
                <td style="border: solid 2px #bcb9b4;width: 30%;">{item.custom_service_master.split("-")[0]}</td>
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

        

        # Attach the PDF file
        pdf_link = f"{base_url}/api/method/frappe.utils.print_format.download_pdf?doctype=Sales%20Order&name=SAL-ORD-2023-00436&format=Sales%20Order%20Format&no_letterhead=0&letterhead=LSA&settings=%7B%7D&_lang=en/SAL-ORD-2023-00436.pdf"
        pdf_filename = f"sales_order_{so_doc.custom_so_from_date}.pdf"
        

        # Connect to the SMTP server and send the email
    
    
        # Send email
        response=single_mail_with_attachment_with_server(smtp_server, sender_email, recipients, subject, body,pdf_link,pdf_filename, cc_email)
        if response["status"]:
            return {"status":True,"msg":"Email sent successfully!"}
        else:
            # frappe.log_error(f"An error occurred in sending mail : {e}")

            er_dict={}
            er_dict["doctype"]= "Custom Error Log"
            er_dict["master_type"]= "Recurring Service Pricing"
            er_dict["master_reference"]= rsp_id
            er_dict["type"]= "Sales Order"
            er_dict["record_reference"]= so_doc.name
            er_dict["context"]="Email Notification for Auto-gen SO"
            er_dict["error_statement"]= f'''Error Sending Mail Notification Monthly SO bulk operation for {so_doc.customer}: {response['msg']}
            '''
            er_doc = frappe.get_doc(er_dict)
            er_doc.insert()
            return {"status":True,"msg":"Failed to send email."}
    except Exception as e:
        # print(f"Failed to send email. Error: {e}")
        # frappe.log_error(f"An error occurred in sending mail : {e}")

        er_dict={}
        er_dict["doctype"]= "Custom Error Log"
        er_dict["master_type"]= "Recurring Service Pricing"
        er_dict["master_reference"]= rsp_id
        er_dict["type"]= "Sales Order"
        er_dict["record_reference"]= so_doc.name
        er_dict["context"]="Email Notification for Auto-gen SO"
        er_dict["error_statement"]= f'''Error Sending Mail Notification Monthly SO bulk operation for {so_doc.customer}: {e}
        '''
        er_doc = frappe.get_doc(er_dict)
        er_doc.insert()
        return {"status":True,"msg":"Failed to send email."}
        

@frappe.whitelist()
def whatsapp_so_template(whatsapp_instance_doc,so_id,rsp_id):
    
    so_doc=frappe.get_doc("Sales Order",so_id)
    new_mobile= so_doc.custom_primary_mobile_no
    new_mobile="9986892788"
    msg_detail={
                    "type": "Sales Order",
                    "document_id": so_doc.name,
                    "mobile_number": new_mobile,
                    "customer":so_doc.customer,
                }
    try:
        
        base_url = frappe.utils.get_url()
        
        
        # Check if the mobile number has 10 digits
        
        payment_link=""
        if so_doc.custom_razorpay_payment_url:
            payment_link=f"Payment Link is : {so_doc.custom_razorpay_payment_url}"
        
        due_amount_message=f"with pending amount of ₹ {so_doc.rounded_total}/-"

        from_date=so_doc.custom_so_from_date.strftime('%d-%m-%Y')
        to_date=so_doc.custom_so_to_date.strftime('%d-%m-%Y')
        
        message = f'''Dear {so_doc.customer_name},

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
        
        ########################### Below commented link is work on Live #######################
        # pdflink = f"{base_url}/api/method/frappe.utils.print_format.download_pdf?doctype=Sales%20Order&name={so_doc.name}&format=Sales%20Order%20Format&no_letterhead=0&letterhead=LSA&settings=%7B%7D&_lang=en/{so_doc.name}.pdf"
        dummy_pdf = "https://morth.nic.in/sites/default/files/dd12-13_0.pdf"
        pdflink=dummy_pdf
        resp_wa_sent_pdf=send_custom_whatsapp_message_with_file(whatsapp_instance_doc, new_mobile, message ,pdflink)


        # Check if the response status is 'success'
        if resp_wa_sent_pdf['status'] :
            # Log the success

            
            msg_detail={
                            "type": "Sales Order",
                            "document_id": so_doc.name,
                            "mobile_number": new_mobile,
                            "customer":so_doc.customer,
                            "message_id":resp_wa_sent_pdf["message_id"],
                            "sent_successfully":1,
                        }
            
            return {"status":True,"msg":"WhatsApp message sent successfully","msg_detail":msg_detail}
        else:
            er_dict={}
            er_dict["doctype"]= "Custom Error Log"
            er_dict["master_type"]= "Recurring Service Pricing"
            er_dict["master_reference"]= rsp_id
            er_dict["type"]= "Sales Order"
            er_dict["record_reference"]= so_doc.name
            er_dict["context"]="WhatsApp Notification for Auto-gen SO"
            er_dict["error_statement"]= f'''Error Sending WhatsApp Notification Monthly SO bulk operation for {so_doc.customer}: {resp_wa_sent_pdf['msg']}
            '''
            er_doc = frappe.get_doc(er_dict)
            er_doc.insert()
            return {"status":False,"msg":"An error occurred while sending the WhatsApp message.","msg_detail":msg_detail}


    except Exception as er:
        # Log the exception and provide feedback to the user
        frappe.logger().error(f"Error: {er}")
        er_dict={}
        er_dict["doctype"]= "Custom Error Log"
        er_dict["master_type"]= "Recurring Service Pricing"
        er_dict["master_reference"]= rsp_id
        er_dict["type"]= "Sales Order"
        er_dict["record_reference"]= so_doc.name
        er_dict["context"]="WhatsApp Notification for Auto-gen SO"
        er_dict["error_statement"]= f'''Error Sending WhatsApp Notification Monthly SO bulk operation for {so_doc.customer}: {er}
        '''
        er_doc = frappe.get_doc(er_dict)
        er_doc.insert()
        return {"status":False,"error":er,"msg":"An unexpected error occurred while sending the WhatsApp message. Please contact the system administrator.","msg_detail":msg_detail}


    




# @frappe.whitelist()
# def generate_payment_link_bulk(rsp_id):
#     self=frappe.get_doc("Monthly SO",mon_id)
#     cur_month = self.month.lower()
#     cur_year = [int(y) for y in self.fy.split("-")]
#     first_day_of_month, last_day_of_month = get_date_range_of_so(cur_month, cur_year)
#     so_cur_mon_auto = frappe.get_all("Sales Order", filters={
#         "custom_so_from_date": (">=", first_day_of_month),
#         "custom_so_to_date": ("<=", last_day_of_month),
#         "custom_auto_generated": 1,
#         # "custom_razorpay_payment_url":("in",[None])
#     })
#     print(len(so_cur_mon_auto))
#     total_pl=len(so_cur_mon_auto)
#     in_progress_pl=0
#     status_dict={"success":[],"failure":[]}
#     for so in so_cur_mon_auto:
#         so_doc = frappe.get_doc("Sales Order", so.name)
#         grand_total = so_doc.rounded_total * 1.02
#         resp=create_razorpay_payment_link_sales_order(grand_total, so_doc.name,so_doc.customer,
#                                                       so_doc.customer_name,so_doc.custom_so_from_date,
#                                                       so_doc.custom_so_to_date,so_doc.rounded_total)
#         print(resp)
#         if resp["status"]:
#             print(resp)
#             print(f"payment link success for {so_doc.name} with customer {so_doc.customer}")
#             status_dict["success"]+=[so.name]
#         else:
#             print(f"failed for {so_doc.name} with customer {so_doc.customer}: {resp['msg']}")
#             er_dict={}
#             er_dict["doctype"]= "Custom Error Log"
#             er_dict["master_type"]= "Monthly SO"
#             er_dict["master_reference"]= mon_id
#             er_dict["type"]= "Sales Order"
#             er_dict["record_reference"]= so.name
#             er_dict["context"]="Payment Link Creation for Auto-gen SO"
#             er_dict["error_statement"]= f'''Error creating Payment Link for Monthly SO bulk operation for {so_doc.customer}: {resp['msg']}
#             '''
#             er_doc = frappe.get_doc(er_dict)
#             er_doc.insert()
#             # status_dict["failure"]+=[so.name]
#         in_progress_pl+=1
#         frappe.publish_realtime("progress", {
#                                         "total": total_pl,
#                                         "created": in_progress_pl
#                                     }, user=frappe.session.user)
#         # print(in_progress_pl)
#     # print(status_dict["failure"])
#     if not status_dict["failure"]:
#         self.payment_link_generated=1
#         self.status="Payment Links Created"
#         self.save()
    
#     return status_dict

# @frappe.whitelist()
# def inform_to_client(rsp_id):
#     self=frappe.get_doc("Monthly SO",mon_id)
#     cur_month = self.month.lower()
#     cur_year = [int(y) for y in self.fy.split("-")]
#     first_day_of_month, last_day_of_month = get_date_range_of_so(cur_month, cur_year)
#     so_cur_mon_auto = frappe.get_all("Sales Order", filters={
#         "custom_so_from_date": (">=", first_day_of_month),
#         "custom_so_to_date": ("<=", last_day_of_month),
#         "custom_auto_generated": 1,
#         # "customer":("in",["20130669","20130894","20130546","20130884","20130501","20130806"])
#     })
    
#     status_dict={"success":[],"failure":[]}
#     wa_status_dict={"success":[],"failure":[]}


#     email_account = frappe.get_doc("Email Account", "LSA OFFICE")
#     sender_email = email_account.email_id
#     sender_password = email_account.get_password()
#     smtp_server = 'smtp.gmail.com'
#     smtp_port = 587
#     server = smtplib.SMTP(smtp_server, smtp_port)
#     server.starttls()
#     server.login(sender_email, sender_password)
#     total_noti=len(so_cur_mon_auto)
#     noti_done=0
#     for so in so_cur_mon_auto:
#         so_doc = frappe.get_doc("Sales Order", so.name)
#         month_full=first_day_of_month.strftime("%B")
#         resp=new_autogen_so_mail(so_doc,month_full,self.fy,server,mon_id)
#         if resp["status"]:
#             status_dict["success"]+=[so.name]
#         else:
#             status_dict["failure"]+=[so.name]
        
#         resp_wa=whatsapp_so_template(so_doc,mon_id)
#         if resp["status"]:
#             wa_status_dict["success"]+=[so.name]
#         else:
#             wa_status_dict["failure"]+=[so.name]
            
#         noti_done+=1
#         frappe.publish_realtime("progress", {
#                                         "total": total_noti,
#                                         "created": noti_done
#                                     }, user=frappe.session.user)

#     print(status_dict["failure"])

#     server.quit()

#     if not status_dict["failure"]:
#         self.informed_to_client=1
#         self.status="Informed to Client"
#         self.save()

#     return status_dict




# def new_autogen_so_mail(so_doc, month, fy,server,rsp_id):

#     email_account = frappe.get_doc("Email Account", "LSA OFFICE")
#     sender_email = email_account.email_id
#     sender_password = email_account.get_password()
#     recipient = "360ithub.developers@gmail.com"
#     cc_email = "360ithub.developers@gmail.com"

#     subject = f"New Sales Order for {month} of FY {fy}"

#     body = f"""
#     <html>
#     <body>
#     <p>Dear {so_doc.customer_name},</p>
#     <p style="margin: 0; padding: 0;">Please find attached the Sales Order {so_doc.name} for your reference.</p>
#     <p style="margin: 0; padding: 0;">Details are as follows:</p>"""
#     body += """
#     <table class="table table-bordered" style="border-collapse: collapse; width: 100%;">
#         <thead>
#             <tr style="background-color: #3498DB; color: white; text-align: left;">
#                 <th style="border: solid 2px #bcb9b4; width: 5%;">S.No.</th>
#                 <th style="border: solid 2px #bcb9b4; width: 15%;">Item Code</th>
#                 <th style="border: solid 2px #bcb9b4; width: 15%;">File ID</th>
#                 <th style="border: solid 2px #bcb9b4; width: 30%;">Description</th>
#                 <th style="border: solid 2px #bcb9b4; width: 5%;">Quantity</th>
#                 <th style="border: solid 2px #bcb9b4; width: 10%;">Rate</th>
#                 <th style="border: solid 2px #bcb9b4; width: 10%;">Amount</th>
#             </tr>
#         </thead>
#         <tbody>
#     """
#     count = 1
#     for item in so_doc.items:
#         body += f"""
#         <tr style="color: black;">
#             <td style="border: solid 2px #bcb9b4;width: 5%;">{count}</td>
#             <td style="border: solid 2px #bcb9b4;width: 15%;">{item.item_code}</td>
#             <td style="border: solid 2px #bcb9b4;width: 15%;">{item.name}</td>
#             <td style="border: solid 2px #bcb9b4;width: 30%;">{item.description.split("-")[0]}</td>
#             <td style="border: solid 2px #bcb9b4;width: 5%;">{item.qty}</td>
#             <td style="border: solid 2px #bcb9b4;width: 10%;">{item.rate}</td>
#             <td style="border: solid 2px #bcb9b4;width: 10%;">{item.amount}</td>
#         </tr>
#         """
#         count += 1
#     discount_row=""
#     if so_doc.discount_amount>0:
#         discount_row=f"""<div style="margin: 0px; padding: 0; display: flex;justify-content: space-between;">
#                             <div style="width: 50%;">Discount:</div>
#                             <div style="width: 50%;">₹ { so_doc.discount_amount }</div>
#                         </div>"""
#     body += f"""
#         </tbody>
#     </table><br>

#     <div style="float: right;width:30%">
#         <div style="margin: 0px; padding: 0; display: flex;justify-content: space-between;">
#             <div style="width: 50%;">Total:</div>
#             <div style="width: 50%;">₹ { so_doc.total }</div>
#         </div>
#         <div style="margin: 0px; padding: 0; display: flex;justify-content: space-between;">
#             <div style="width: 50%;">Taxes:</div>
#             <div style="width: 50%;">₹ { so_doc.total_taxes_and_charges }</div>
#         </div>
#         {discount_row}
#         <div style="margin: 0px; padding: 0; display: flex;justify-content: space-between;">
#             <div style="width: 50%;">Grand Total:</div>
#             <div style="width: 50%;"><strong>₹ { so_doc.rounded_total }</strong></div>
#         </div>
#     </div>
#     <div style="clear: both;"></div>
#     <p>Thank you for your business!</p><br>

#     <p>Regards,<br>LSA Office</p>
#     </body>
#     </html>
#     """

#     # print(body)
#     # Create the email message
#     message = MIMEMultipart()
#     message['From'] = sender_email
#     message['To'] = recipient
#     message['Cc'] = cc_email
#     message['Subject'] = subject
#     message.attach(MIMEText(body, 'html'))

#     # Attach the PDF file
#     pdf_link = f"https://online.lsaoffice.com/api/method/frappe.utils.print_format.download_pdf?doctype=Sales%20Order&name=SAL-ORD-2023-00436&format=Sales%20Order%20Format&no_letterhead=0&letterhead=LSA&settings=%7B%7D&_lang=en/SAL-ORD-2023-00436.pdf"
#     pdf_filename = f"sales_order_{month}_{fy}.pdf"
#     attachment = get_file_from_link(pdf_link)
#     if attachment:
#         part = MIMEBase("application", "octet-stream")
#         part.set_payload(attachment)
#         encoders.encode_base64(part)
#         part.add_header(
#             "Content-Disposition",
#             f"attachment; filename= {pdf_filename}",
#         )
#         message.attach(part)

#     # Connect to the SMTP server and send the email
    
#     try:
#         # Send email
#         response=server.sendmail(sender_email, recipient.split(',') + cc_email.split(','), message.as_string())
#         print(so_doc.name,"res",response,)
#         return {"status":True,"msg":"Email sent successfully!"}
#     except Exception as e:
#         print(f"Failed to send email. Error: {e}")
#         frappe.log_error(f"An error occurred in sending mail : {e}")

#         er_dict={}
#         er_dict["doctype"]= "Custom Error Log"
#         er_dict["master_type"]= "Monthly SO"
#         er_dict["master_reference"]= mon_id
#         er_dict["type"]= "Sales Order"
#         er_dict["record_reference"]= so_doc.name
#         er_dict["context"]="Email Notification for Auto-gen SO"
#         er_dict["error_statement"]= f'''Error Sending Mail Notification Monthly SO bulk operation for {so_doc.customer}: {e}
#         '''
#         er_doc = frappe.get_doc(er_dict)
#         er_doc.insert()
#         return {"status":True,"msg":"Failed to send email."}
        

# @frappe.whitelist()
# def whatsapp_so_template(so_doc,rsp_id):
#     new_mobile="9098543046"

#     whatsapp_demo = frappe.get_all('WhatsApp Instance',filters={'module':'Accounts','connection_status':1,'active':1})
#     if whatsapp_demo:
#         sales_invoice_whatsapp_log = frappe.new_doc('WhatsApp Message Log')
#         whatsapp_items = []

#         invoice_doc = so_doc
#         customer = invoice_doc.customer
#         total = invoice_doc.rounded_total
#         customer_name = invoice_doc.customer_name
#         docname = invoice_doc.name

#         advance_paid_amount=0
#         balance_amount=invoice_doc.rounded_total

#         sales_invoice = frappe.get_all('Sales Invoice Item',filters={'sales_order':invoice_doc.name,'docstatus':("in",[0,1])},fields=["parent"])
#         if sales_invoice:
#             return {"status":False,"msg":f"A Sales Invoice <a href='https://online.lsaoffice.com/app/sales-invoice/{sales_invoice[0].parent}'>{sales_invoice[0].parent}</a> already exist for the Sales Order"}
        
#         instance = frappe.get_doc('WhatsApp Instance',whatsapp_demo[0].name)
#         ins_id = instance.instance_id


#         try:
#             # Check if the mobile number has 10 digits
#             if len(new_mobile) != 10:
#                 frappe.msgprint("Please provide a valid 10-digit mobile number.")
#                 return
            
#             payment_link=""
#             if invoice_doc.custom_razorpay_payment_url:
#                 payment_link=f"Payment Link is : {invoice_doc.custom_razorpay_payment_url}"
            
#             due_amount_message=f"with net total amount of ₹ {total}/-"

#             # pe_list = frappe.get_all('Payment Entry Reference',filters={"reference_doctype":"Sales Order",'reference_name':invoice_doc.name,'docstatus':1},fields=["name","allocated_amount","parent"])
#             # if pe_list:
#             #     for pe in pe_list:
#             #         advance_paid_amount+=pe.allocated_amount
#             #         balance_amount-=pe.allocated_amount
#             #     due_amount_message=f"partially paid. You have paid Rs {advance_paid_amount}/- out of net total of Rs {total}/-"
#             #     payment_link=""
            


#             from_date=invoice_doc.custom_so_from_date.strftime('%d-%m-%Y')
#             to_date=invoice_doc.custom_so_to_date.strftime('%d-%m-%Y')
            
#             message = f'''Dear {customer_name},

# Please find attached Sale Order from {from_date} to {to_date} period {due_amount_message}. Kindly pay on below bank account details

# Our Bank Account
# Lokesh Sankhala and ASSOSCIATES
# Account No = 73830200000526
# IFSC = BARB0VJJCRO
# Bank = Bank of Baroda,JC Road,Bangalore-560002
# UPI id = LSABOB@UPI
# Gpay / Phonepe no = 9513199200
# {payment_link}

# Call us immediately in case of query.

# Best Regards,
# LSA Office Account Team
# accounts@lsaoffice.com
# 8951692788'''
#             if balance_amount<1:
#                 message=""
            
#             ########################### Below commented link is work on Live #######################
#             link = f"https://online.lsaoffice.com/api/method/frappe.utils.print_format.download_pdf?doctype=Sales%20Order&name={docname}&format=Sales%20Order%20Format&no_letterhead=0&letterhead=LSA&settings=%7B%7D&_lang=en/{docname}.pdf"
            
#             url = "https://wts.vision360solutions.co.in/api/sendFileWithCaption"
#             params_1 = {
#                 "token": ins_id,
#                 "phone": f"91{new_mobile}",
#                 "message": message,
#                 "link": link
#             }

#             whatsapp_items.append( {"type": "Sales Order",
#                                     "document_id": invoice_doc.name,
#                                     "mobile_number": new_mobile,
#                                     "customer":invoice_doc.customer,})
            
#             response = requests.post(url, params=params_1)
#             response.raise_for_status()  # Raise an error for HTTP errors (status codes other than 2xx)
#             response_data = response.json()
#             message_id = response_data['data']['messageIDs'][0]


#             # Check if the response status is 'success'
#             if response_data.get('status') == 'success':
#                 # Log the success

#                 frappe.logger().info("WhatsApp message sent successfully")
#                 sales_invoice_whatsapp_log.append("details", {
#                                                 "type": "Sales Order",
#                                                 "document_id": invoice_doc.name,
#                                                 "mobile_number": new_mobile,
#                                                 "customer":invoice_doc.customer,
#                                                 "message_id":message_id
                                                            
#                                                 # Add other fields of the child table row as needed
#                                             })
#                 sales_invoice_whatsapp_log.send_date = frappe.utils.now_datetime()
#                 sales_invoice_whatsapp_log.sender = frappe.session.user
#                 sales_invoice_whatsapp_log.type = "Template"
#                 sales_invoice_whatsapp_log.message = message
#                 sales_invoice_whatsapp_log.insert()
#                 return {"status":True,"msg":"WhatsApp message sent successfully"}
#             else:
#                 er_dict={}
#                 er_dict["doctype"]= "Custom Error Log"
#                 er_dict["master_type"]= "Monthly SO"
#                 er_dict["master_reference"]= mon_id
#                 er_dict["type"]= "Sales Order"
#                 er_dict["record_reference"]= so_doc.name
#                 er_dict["context"]="WhatsApp Notification for Auto-gen SO"
#                 er_dict["error_statement"]= f'''Error Sending WhatsApp Notification Monthly SO bulk operation for {so_doc.customer}
#                 '''
#                 er_doc = frappe.get_doc(er_dict)
#                 er_doc.insert()
#                 return {"status":False,"error":f"{response.json()}","msg":"An error occurred while sending the WhatsApp message."}


#         except requests.exceptions.RequestException as e:
#             # Log the exception and provide feedback to the user
#             frappe.logger().error(f"Network error: {e}")
#             er_dict={}
#             er_dict["doctype"]= "Custom Error Log"
#             er_dict["master_type"]= "Monthly SO"
#             er_dict["master_reference"]= mon_id
#             er_dict["type"]= "Sales Order"
#             er_dict["record_reference"]= so_doc.name
#             er_dict["context"]="WhatsApp Notification for Auto-gen SO"
#             er_dict["error_statement"]= f'''Error Sending WhatsApp Notification Monthly SO bulk operation for {so_doc.customer}: {e}
#             '''
#             er_doc = frappe.get_doc(er_dict)
#             er_doc.insert()
#             return {"status":False,"error":e,"msg":"An error occurred while sending the WhatsApp message. Please try again later."}
#         except Exception as er:
#             # Log the exception and provide feedback to the user
#             frappe.logger().error(f"Error: {er}")
#             er_dict={}
#             er_dict["doctype"]= "Custom Error Log"
#             er_dict["master_type"]= "Monthly SO"
#             er_dict["master_reference"]= mon_id
#             er_dict["type"]= "Sales Order"
#             er_dict["record_reference"]= so_doc.name
#             er_dict["context"]="WhatsApp Notification for Auto-gen SO"
#             er_dict["error_statement"]= f'''Error Sending WhatsApp Notification Monthly SO bulk operation for {so_doc.customer}: {er}
#             '''
#             er_doc = frappe.get_doc(er_dict)
#             er_doc.insert()
#             return {"status":False,"error":er,"msg":"An unexpected error occurred while sending the WhatsApp message. Please contact the system administrator."}
#     else:
#         er_dict={}
#         er_dict["doctype"]= "Custom Error Log"
#         er_dict["master_type"]= "Monthly SO"
#         er_dict["master_reference"]= mon_id
#         er_dict["type"]= "Sales Order"
#         er_dict["record_reference"]= so_doc.name
#         er_dict["context"]="WhatsApp Notification for Auto-gen SO"
#         er_dict["error_statement"]= f'''Error Sending WhatsApp Notification Monthly SO bulk operation for {so_doc.customer}: Your WhatApp API instance is not connected
#         '''
#         er_doc = frappe.get_doc(er_dict)
#         er_doc.insert()
#         return {"status":False,"msg":"Your WhatApp API instance is not connected"}

    
# def get_file_from_link(link):
#     try:
#         response = requests.get(link)
#         if response.status_code == 200:
#             return response.content
#         else:
#             print(f"Failed to fetch file from link. Status code: {response.status_code}")
#             return None
#     except Exception as e:
#         print(f"Error fetching file from link: {e}")
#         frappe.log_error(f"An error occurred in fetching file from Link: {e}")
#         return None
    
# @frappe.whitelist()
# def create_new_followups(rsp_id,next_followup_date_mon):
#     next_followup_date_mon = datetime.strptime(next_followup_date_mon, '%Y-%m-%d').date()

#     self=frappe.get_doc("Monthly SO",mon_id)
#     cur_month = self.month.lower()
#     cur_year = [int(y) for y in self.fy.split("-")]
#     first_day_of_month, last_day_of_month = get_date_range_of_so(cur_month, cur_year)
#     so_cur_mon_auto = frappe.get_all("Sales Order", filters={
# 															"custom_so_from_date": (">=", first_day_of_month),
# 															"custom_so_to_date": ("<=", last_day_of_month),
# 															"custom_auto_generated": 1,
# 														},
#                                                     fields=["customer","name"]              
# 														)
#     cust_to_generate_fu={i.customer:i.name for i in so_cur_mon_auto}
#     status_dict={"success":[],"failure":[]}
#     total=len(cust_to_generate_fu)
#     created=0
#     for cust in cust_to_generate_fu:
#         try:
#             open_fu = frappe.get_all("Customer Followup",filters={
#                                                                 "status":"Open",
#                                                                 "customer_id":cust,
#                                                                 })
#             next_followup_date=None
#             new_followup=True
#             if open_fu:
#                 open_fu_doc=frappe.get_doc("Customer Followup",open_fu[0].name)
#                 if cust_to_generate_fu[cust] in open_fu_doc.sales_order_summary:
#                     status_dict["success"]+=[cust]
#                     new_followup=False
#                 else:
#                     next_followup_date=open_fu_doc.next_followup_date
#                     open_fu_doc.status="Closed"
#                     open_fu_doc.followup_note="New Followup created with newly added SO"
#                     open_fu_doc.save()
#             # print(next_followup_date)
#             # print(type(next_followup_date))

#             response=sync_customer(cust)
#             if response["status"]!="Sync Failed." and new_followup:
#                 doc = frappe.new_doc("Customer Followup")
#                 doc.customer_id = cust
#                 doc.followup_type="Call"
#                 doc.sales_order_summary = response["values"][3]
#                 doc.total_remaining_balance=response["values"][2]
                
#                 if not next_followup_date:
#                     doc.next_followup_date=next_followup_date_mon
#                 elif next_followup_date>=first_day_of_month and next_followup_date>= datetime.now().date():
#                     doc.next_followup_date=next_followup_date
#                 else:
#                     frappe.throw("Enter a valid Next Followup Date")
#                 # print(next_followup_date,next_followup_date_mon,doc.next_followup_date)
#                 doc.executive="latha.st@lsaoffice.com"
#                 doc.insert()
#                 status_dict["success"]+=[cust]
#             elif new_followup:
#                 er_dict={}
#                 er_dict["doctype"]= "Custom Error Log"
#                 er_dict["master_type"]= "Monthly SO"
#                 er_dict["master_reference"]= mon_id
#                 er_dict["type"]= "Customer"
#                 er_dict["record_reference"]= cust
#                 er_dict["context"]="New Followup Creation for Auto-gen SO"
#                 er_dict["error_statement"]= f'''Error fetching details for new followups creating in Monthly SO bulk operation for {cust}
#                 '''
#                 er_doc = frappe.get_doc(er_dict)
#                 er_doc.insert()
#                 status_dict["failure"]+=[cust]
#         except Exception as er:
#             status_dict["failure"]+=[cust]
#             print(er)
#             frappe.log_error(f"An error occurred in creating new followup: {er}")
#             er_dict={}
#             er_dict["doctype"]= "Custom Error Log"
#             er_dict["master_type"]= "Monthly SO"
#             er_dict["master_reference"]= mon_id
#             er_dict["type"]= "Customer"
#             er_dict["record_reference"]= cust
#             er_dict["context"]="New Followup Creation for Auto-gen SO"
#             er_dict["error_statement"]= f'''Error creating new followups in Monthly SO bulk operation for {cust}: {er}
#             '''
#             er_doc = frappe.get_doc(er_dict)
#             er_doc.insert()
#         created+=1
#         frappe.publish_realtime("progress", {
#                                         "total": total,
#                                         "created": created
#                                     }, user=frappe.session.user)
#     print(status_dict["failure"])
#     if not status_dict["failure"]:
#         self.followup_created=1
#         self.status="Followup Created"
#         self.save()
#     return status_dict
        

# @frappe.whitelist()
# def cancel_so_payment_links(rsp_id):
#     month_so_doc = frappe.get_doc("Monthly SO", mon_id)
#     cur_month = month_so_doc.month.lower()
#     cur_year = [int(y) for y in month_so_doc.fy.split("-")]
#     first_day_of_month, last_day_of_month = get_date_range_of_so(cur_month, cur_year)
#     so_cur_mon_auto = frappe.get_all("Sales Order", filters={
#         "custom_so_from_date": (">=", first_day_of_month),
#         "custom_so_to_date": ("<=", last_day_of_month),
#         "custom_auto_generated": 1,
#         "custom_razorpay_payment_url":("not in",[None])},
#         fields=["name","customer","custom_razorpay_payment_url"])
#     status_dict={"success":[],"failure":[]}

#     cancelled_payment_links=0
#     total_payment_links=len(so_cur_mon_auto)
#     for so in so_cur_mon_auto:
#         payment_link_list= frappe.get_all("Payment Link Log",filters={"link_short_url": so.custom_razorpay_payment_url},fields=["name","enabled"])
#         if payment_link_list:
#             resp=cancel_link(payment_link_list[0].name)
            
#             if resp["status"]:
#                 status_dict["success"]+=[so.name]
#                 cancelled_payment_links += 1
#                 # Send progress information to the client side
#                 frappe.publish_realtime("progress", {
#                                         "total": total_payment_links,
#                                         "cancelled": cancelled_payment_links
#                                     }, user=frappe.session.user)
#             else:
#                 status_dict["failure"]+=[so.name]
#                 er_dict={}
#                 er_dict["doctype"]= "Custom Error Log"
#                 er_dict["master_type"]= "Monthly SO"
#                 er_dict["master_reference"]= mon_id
#                 er_dict["type"]= "Sales Order"
#                 er_dict["record_reference"]= so.name
#                 er_dict["context"]="Payment Link Cancellation for Auto-gen SO"
#                 er_dict["error_statement"]= f'''Error cancelling payment link in Monthly SO bulk operation for {so.customer} for {so.name}: {resp["msg"]}
#                 '''
#                 er_doc = frappe.get_doc(er_dict)
#                 er_doc.insert()
#             print(so.name,resp["status"],resp["msg"])
#         else:
#             so_doc = frappe.get_doc('Sales Order',so.name)
#             so_doc.custom_razorpay_payment_url=None
#             so_doc.save()

#     # print(status_dict["failure"])
#     if len(so_cur_mon_auto)==len(status_dict["success"]):
#         month_so_doc.payment_link_generated=0
#         month_so_doc.informed_to_client=0
#         month_so_doc.status="Payment Links Cancelled"
#         month_so_doc.save()
#         return {"status":True,"msg":"All Payment Links are cancelled"}
#     elif len(status_dict["success"])>0:
#         return {"status":True,"msg":"Partial Payment Links are cancelled"}
    
#     return {"status":False,"msg":"Failed to cancel Payment Links"}


# @frappe.whitelist()
# def generate_bulk_customer_followup():

#     status_dict={"success":[],"failure":[]}
#     email_status_dict={"success":[],"failure":[]}
#     whatsapp_status_dict={"success":[],"failure":[]}
#     remainder_freq=frappe.get_all("Monthly SO Remainder",filters={"active":"Yes"},fields=["name","parent","remainder_type"],order_by="effective_from desc")
#     if remainder_freq and len(remainder_freq) in (1,2):
#         remainder_freq_dict={rem.remainder_type:(rem.name,rem.parent) for rem in remainder_freq}
#         print(remainder_freq_dict)

#         mail_mon_id=None
#         if "Email" in remainder_freq_dict:
#             mail_remainder_freq_doc=frappe.get_doc("Monthly SO Remainder",remainder_freq_dict["Email"][0])
#             mail_mon_id=mail_remainder_freq_doc.parent
        
#             next_followup_date_mon=mail_remainder_freq_doc.effective_from
#             if mail_remainder_freq_doc.last_bulk_creation:
#                 next_followup_date_mon=mail_remainder_freq_doc.last_bulk_creation
#             next_followup_date=next_followup_date_mon+timedelta(mail_remainder_freq_doc.frequency)
            
#             today=datetime.now().date()

#             # if True:
#             if  today==next_followup_date:
            

#                 self=frappe.get_doc("Monthly SO",mail_mon_id)
#                 cur_month = self.month.lower()
#                 cur_year = [int(y) for y in self.fy.split("-")]
#                 first_day_of_month, last_day_of_month = get_date_range_of_so(cur_month, cur_year)
#                 so_cur_mon_auto = frappe.get_all("Sales Order", filters={
#                                                                         "custom_so_from_date": (">=", first_day_of_month),
#                                                                         "custom_so_to_date": ("<=", last_day_of_month),
#                                                                         "custom_auto_generated": 1,
#                                                                         # "customer":"20130669",
#                                                                     },
#                                                                 fields=["name","customer"]              
#                                                                     )
#                 # print(so_cur_mon_auto)
#                 cust_to_generate_fu={i.name:i.customer for i in so_cur_mon_auto}
#                 total=len(cust_to_generate_fu)
#                 created=0

#                 email_account = frappe.get_doc("Email Account", "LSA OFFICE")
#                 sender_email = email_account.email_id
#                 sender_password = email_account.get_password()
#                 smtp_server = 'smtp.gmail.com'
#                 smtp_port = 587
#                 server = smtplib.SMTP(smtp_server, smtp_port)
#                 server.starttls()
#                 server.login(sender_email, sender_password)

#                 for so in cust_to_generate_fu:
#                     try:
#                         # open_fu = frappe.get_all("Customer Followup",filters={
#                         #                                                     "status":"Open",
#                         #                                                     "customer_id":cust_to_generate_fu[so],
#                         #                                                     })
#                         # create_new_fu=True
#                         # next_followup_date=None
#                         # if open_fu:
#                         #     # print("open fu")
#                         #     open_fu_doc=frappe.get_doc("Customer Followup",open_fu[0].name)
#                         #     if so in open_fu_doc.sales_order_summary:
#                         #         create_new_fu=False
#                         #         status_dict["success"]+=[cust_to_generate_fu[so]]
#                         #     else:
#                         #         next_followup_date=open_fu_doc.next_followup_date
#                         #         open_fu_doc.status="Closed"
#                         #         open_fu_doc.followup_note="New Followup created with newly added SO"
#                         #         open_fu_doc.save()
#                         #     # print("open fu executed")
#                         response=sync_customer(cust_to_generate_fu[so])
#                         # # response=False
#                         # # print("response",response,cust_to_generate_fu[so])
#                         # if create_new_fu:
#                         #     if response["status"]!="Sync Failed.":
#                         #         print("new fu")
#                         #         doc = frappe.new_doc("Customer Followup")
#                         #         doc.customer_id = cust_to_generate_fu[so]
#                         #         doc.followup_type="Call"
#                         #         doc.sales_order_summary = response["values"][3]
#                         #         doc.total_remaining_balance=response["values"][2]
#                         #         if not next_followup_date or next_followup_date<next_followup_date_mon:
#                         #             doc.next_followup_date=next_followup_date_mon
#                         #         elif next_followup_date>first_day_of_month:
#                         #             doc.next_followup_date=next_followup_date
#                         #         # print(next_followup_date,next_followup_date_mon,doc.next_followup_date)
#                         #         doc.executive="latha.st@lsaoffice.com"
#                         #         doc.insert()
#                         #         status_dict["success"]+=[cust_to_generate_fu[so]]
#                         #     else:
#                         #         status_dict["failure"]+=[cust_to_generate_fu[so]]

#                         # print("customer fu execution completed")

#                         c_doc = frappe.get_doc("Customer",cust_to_generate_fu[so])
#                         customer_name=c_doc.customer_name

#                         email_fu_response=generate_bulk_email_followup(response,customer_name,server,sender_email)
#                         if email_fu_response["status"]:
#                             email_status_dict["success"]+=[cust_to_generate_fu[so]]
#                         else:
#                             er_dict={}
#                             er_dict["doctype"]= "Custom Error Log"
#                             er_dict["master_type"]= "Monthly SO"
#                             er_dict["master_reference"]= mail_mon_id
#                             er_dict["type"]= "Sales Order"
#                             er_dict["record_reference"]= so
#                             er_dict["context"]="Email Followup for Auto-gen SO"
#                             er_dict["error_statement"]= f'''Error sending email followup in Monthly SO bulk operation for {cust_to_generate_fu[so]} for {so} on {today}:{email_fu_response["msg"]}
#                             '''
#                             er_doc = frappe.get_doc(er_dict)
#                             er_doc.insert()
#                             email_status_dict["failure"]+=[cust_to_generate_fu[so]]

                        
#                     except Exception as er:
#                         print(er)
#                         # print("cfu error: ",er)
#                         frappe.log_error(f"An error occurred in creating new followup: {er}")
#                         er_dict={}
#                         er_dict["doctype"]= "Custom Error Log"
#                         er_dict["master_type"]= "Monthly SO"
#                         er_dict["master_reference"]= mail_mon_id
#                         er_dict["type"]= "Sales Order"
#                         er_dict["record_reference"]= so
#                         er_dict["context"]="Exception in Email Followup for Auto-gen SO"
#                         er_dict["error_statement"]= f'''Exception Error sending email followup in Monthly SO bulk operation for {cust_to_generate_fu[so]} for {so} on {today}:{er}
#                         '''
#                         er_doc = frappe.get_doc(er_dict)
#                         er_doc.insert()
#                     created+=1
#                     frappe.publish_realtime("progress", {
#                                                     "total": total,
#                                                     "created": created
#                                                 }, user=frappe.session.user)
#                     # print(cust_to_generate_fu[so])
#                 # print(status_dict["failure"])
#                 # print(email_status_dict["failure"])
#                 # print(whatsapp_status_dict["failure"])
#                 server.quit()
#                 if not email_status_dict["failure"]:
#                     mail_remainder_freq_doc.last_bulk_creation=datetime.now()
#                     mail_remainder_freq_doc.save()
           
#         #################################################WhatsApp#####################################################


#         whatsapp_mon_id=None
#         if "WhatsApp" in remainder_freq_dict:
#             whatsapp_remainder_freq_doc=frappe.get_doc("Monthly SO Remainder",remainder_freq_dict["WhatsApp"][0])
#             whatsapp_mon_id=whatsapp_remainder_freq_doc.parent
        
#             next_followup_date_mon=whatsapp_remainder_freq_doc.effective_from
#             if whatsapp_remainder_freq_doc.last_bulk_creation:
#                 next_followup_date_mon=whatsapp_remainder_freq_doc.last_bulk_creation
#             next_followup_date=next_followup_date_mon+timedelta(whatsapp_remainder_freq_doc.frequency)
            
#             today=datetime.now().date()

#             # if True:
#             if  today==next_followup_date:
            

#                 self=frappe.get_doc("Monthly SO",whatsapp_mon_id)
#                 cur_month = self.month.lower()
#                 cur_year = [int(y) for y in self.fy.split("-")]
#                 first_day_of_month, last_day_of_month = get_date_range_of_so(cur_month, cur_year)
#                 so_cur_mon_auto = frappe.get_all("Sales Order", filters={
#                                                                         "custom_so_from_date": (">=", first_day_of_month),
#                                                                         "custom_so_to_date": ("<=", last_day_of_month),
#                                                                         "custom_auto_generated": 1,
#                                                                     },
#                                                                 fields=["name","customer"]              
#                                                                     )
#                 # print(so_cur_mon_auto)
#                 cust_to_generate_fu={i.name:i.customer for i in so_cur_mon_auto}
#                 total=len(cust_to_generate_fu)
#                 created=0

#                 email_account = frappe.get_doc("Email Account", "LSA OFFICE")
#                 sender_email = email_account.email_id
#                 sender_password = email_account.get_password()
#                 smtp_server = 'smtp.gmail.com'
#                 smtp_port = 587
#                 server = smtplib.SMTP(smtp_server, smtp_port)
#                 server.starttls()
#                 server.login(sender_email, sender_password)

#                 for so in cust_to_generate_fu:
#                     try:
                        
#                         response=sync_customer(cust_to_generate_fu[so])
#                         whatsapp_fu_response=generate_bulk_whatsapp_followup(c_doc.name,customer_name,c_doc.custom_primary_mobile_no)
#                         if whatsapp_fu_response["status"]:
#                             whatsapp_status_dict["success"]+=[cust_to_generate_fu[so]]
#                         else:
#                             er_dict={}
#                             er_dict["doctype"]= "Custom Error Log"
#                             er_dict["master_type"]= "Monthly SO"
#                             er_dict["master_reference"]= whatsapp_mon_id
#                             er_dict["type"]= "Sales Order"
#                             er_dict["record_reference"]= so
#                             er_dict["context"]="Email Followup for Auto-gen SO"
#                             er_dict["error_statement"]= f'''Error sending WhatsApp followup in Monthly SO bulk operation for {cust_to_generate_fu[so]} for {so} on {today}:{whatsapp_fu_response["msg"]}
#                             '''
#                             er_doc = frappe.get_doc(er_dict)
#                             er_doc.insert()
#                             whatsapp_status_dict["failure"]+=[cust_to_generate_fu[so]]
                        
#                     except Exception as er:
#                         # print("cfu error: ",er)
#                         frappe.log_error(f"An error occurred in creating new followup: {er}")
#                         er_dict={}
#                         er_dict["doctype"]= "Custom Error Log"
#                         er_dict["master_type"]= "Monthly SO"
#                         er_dict["master_reference"]= whatsapp_mon_id
#                         er_dict["type"]= "Sales Order"
#                         er_dict["record_reference"]= so
#                         er_dict["context"]="Exception in WhatsApp Followup for Auto-gen SO"
#                         er_dict["error_statement"]= f'''Exception Error sending WhatsApp followup in Monthly SO bulk operation for {cust_to_generate_fu[so]} for {so} on {today}:{er}
#                         '''
#                         er_doc = frappe.get_doc(er_dict)
#                         er_doc.insert()
#                     created+=1
#                     frappe.publish_realtime("progress", {
#                                                     "total": total,
#                                                     "created": created
#                                                 }, user=frappe.session.user)
#                     print(cust_to_generate_fu[so])
#                 server.quit()
#                 if not whatsapp_status_dict["failure"]:
#                     whatsapp_remainder_freq_doc.last_bulk_creation=datetime.now()
#                     whatsapp_remainder_freq_doc.save()
#         return {"status_dict":status_dict,"email_status_dict":email_status_dict,"whatsapp_status_dict":whatsapp_status_dict}



# @frappe.whitelist()
# def generate_bulk_email_followup(response,customer_name,server,sender_email):
    
#     details_of_so_due=response["values"]
#     print(details_of_so_due)
#     # [{'SAL-ORD-2024-03173': [1770.0, 0, 1770.0, datetime.date(2024, 4, 1), datetime.date(2024, 4, 30), 
#     #                          'Drafted', 1, 'GANPATHI TEXTILES', '20130009', 'Unpaid', None]}, 
#     #  1, 1770.0, 'SAL-ORD-2024-03173']
#     if not details_of_so_due:
#         return False
#     pending_so=details_of_so_due[0]

#     message = MIMEMultipart()


#     # print(list(details_of_so_due.keys()))
#     # so_doc_first=frappe.get_doc("Sales Order",list(details_of_so_due.keys())[0])
#     pending_so_table=f'''
#     <table class="table table-bordered" style="border-collapse: collapse;width: 100%;">
#         <thead>
#             <tr style="background-color:#3498DB;color:white;text-align: left;">
#                 <th style="vertical-align: middle;border: solid 2px #bcb9b4;width: 5%;">S. No.</th>
#                 <th style="vertical-align: middle;border: solid 2px #bcb9b4;width: 20%;">Sales Order Name</th>
#                 <th style="vertical-align: middle;border: solid 2px #bcb9b4;width: 15%;">From Date</th>
#                 <th style="vertical-align: middle;border: solid 2px #bcb9b4;width: 15%;">To Date</th>
#                 <th style="vertical-align: middle;border: solid 2px #bcb9b4;width: 15%;">Payment Status</th>
#                 <th style="vertical-align: middle;border: solid 2px #bcb9b4;width: 10%;">Total</th>
#                 <th style="vertical-align: middle;border: solid 2px #bcb9b4;width: 10%;">Advance Paid</th>
#                 <th style="vertical-align: middle;border: solid 2px #bcb9b4;width: 10%;">Pending</th>
#             </tr>
#         </thead>
#         <tbody>'''
#     total=0.00
#     balance=0.00
#     count=0
#     for so in pending_so:
#         if not pending_so[so][10] or so!= "SAL-ORD-2024-03177":
#             total+=pending_so[so][0]
#             balance+=pending_so[so][2]
#             count+=1
#             from_date=pending_so[so][3].strftime('%d-%m-%Y')
#             to_date= pending_so[so][4].strftime('%d-%m-%Y')
#             pending_so_table+=f'''
#                                 <tr>
#                                     <td style="border: solid 2px #bcb9b4;">{count}</td>
#                                     <td style="border: solid 2px #bcb9b4;">{so}</td>
#                                     <td style="border: solid 2px #bcb9b4;">{ from_date }</td>
#                                     <td style="border: solid 2px #bcb9b4;">{ to_date}</td>
#                                     <td style="border: solid 2px #bcb9b4;">{ pending_so[so][9] }</td>
#                                     <td style="border: solid 2px #bcb9b4;">{ pending_so[so][0] }</td>
#                                     <td style="border: solid 2px #bcb9b4;">{ pending_so[so][1] }</td>
#                                     <td class="indian-currency2" style="border: solid 2px #bcb9b4;">{ pending_so[so][2] }</td>
#                                 </tr>'''
#             pdf_link=None
#             if pending_so[so][9]=="Unpaid":
#                 pdf_link = f"https://online.lsaoffice.com/api/method/frappe.utils.print_format.download_pdf?doctype=Sales%20Order&name={so}&format=Sales%20Order%20Format&no_letterhead=0&letterhead=LSA&settings=%7B%7D&_lang=en/{so}.pdf"
#             elif pending_so[so][9]=="Partially Paid":
#                 pdf_link=f"https://online.lsaoffice.com/api/method/frappe.utils.print_format.download_pdf?doctype=Sales%20Order&name={so}&format=Sales%20Order%20with%20payment%20details&no_letterhead=0&letterhead=LSA&settings=%7B%7D&_lang=en/{so}.pdf"

#             if pdf_link:
#                 attachment = get_file_from_link(pdf_link)
#                 if attachment:
#                     part = MIMEBase("application", "octet-stream")
#                     part.set_payload(attachment)
#                     encoders.encode_base64(part)
#                     part.add_header(
#                         "Content-Disposition",
#                         f"attachment; filename= SalesOrder_{so}.pdf",
#                     )
#                     message.attach(part)
                    
#     pending_so_table+="</tbody></table>"


#     recipient = "360ithub.developers@gmail.com"
#     cc_email = "360ithub.developers@gmail.com"



    
#     message['From'] = sender_email
#     message['To'] = recipient
#     message['Cc'] = cc_email
#     message['Subject'] = "Payment Reminder for Pending Sales Orders"

#     body = f'''<pre style="font-family: Arial, sans-serif; font-size: 14px; color: #000000;">Dear {customer_name},

# I hope this email finds you well.

# This is a friendly reminder regarding the due amount for following Sales Order details with ₹ {balance} balance out of net total of ₹ {total}:</pre>'''

#     body +=pending_so_table
#     body += f'''<pre style="font-family: Arial, sans-serif; font-size: 14px; color: #000000;">We kindly request you to make the payment using the below bank account details:

# Bank Account Details:

# Account Name: Lokesh Sankhala and Associates
# Account Number: 73830200000526
# IFSC Code: BARB0VJJCRO
# Bank: Bank of Baroda, JC Road, Bangalore-560002
# UPI ID: LSABOB@UPI
# GPay / PhonePe Number: 9513199200

# Please reach out to us immediately if you have any queries or need further assistance.

# Best Regards,

# LSA Office Account Team
# Email: accounts@lsaoffice.com
# Phone: 8951692788 </pre>'''

#     message.attach(MIMEText(body, 'html'))
#     status=None
#     msg=""
#     try:
#         # Send email
#         server.sendmail(sender_email, recipient.split(',') + cc_email.split(','), message.as_string())
#         # print("Follow-up email sent successfully!")
#         status= True
#         msg="Success"
#     except Exception as e:
#         print(f"Failed to send follow-up email. Error: {e}")
#         msg=f"Failed to send follow-up email. Error: {e}"
#         status= False
    
#     return {"status":status,"msg":msg}

# def get_file_from_link(link):
#     try:
#         response = requests.get(link)
#         if response.status_code == 200:
#             return response.content
#         else:
#             print(f"Failed to fetch file from link. Status code: {response.status_code}")
#             return None
#     except Exception as e:
#         print(f"Error fetching file from link: {e}")
#         return None



# @frappe.whitelist()
# def generate_bulk_whatsapp_followup(customer_id,customer_name,new_mobile):
#     new_mobile="9098543046"
#     resp=wa_followup_customer(customer_id,customer_name,new_mobile)
#     status=resp["status"]
#     msg=resp["msg"]
#     return {"status":status,"msg":msg}




#################################System console script#######################################################################

# approved_docs = frappe.get_all('Recurring Service Pricing', filters={'status': 'Approved'})

# # Example of processing the result
# for doc in approved_docs:
#     frappe.db.set_value('Recurring Service Pricing', doc.name, "automatic_so_creation", 1)
#     frappe.db.set_value('Recurring Service Pricing', doc.name, "payment_link_generation", 1)
#     frappe.db.set_value('Recurring Service Pricing', doc.name, "new_followup_creation", 1)
#     frappe.db.set_value('Recurring Service Pricing', doc.name, "share_with_client_via_wa", 1)
#     frappe.db.set_value('Recurring Service Pricing', doc.name, "share_with_client_via_mail", 1)
#     log(doc.name)

