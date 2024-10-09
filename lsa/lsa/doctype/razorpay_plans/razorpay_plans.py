# Copyright (c) 2024, Mohan and contributors
# For license information, please see license.txt


import frappe
import requests
import json
from frappe.model.document import Document


class RazorpayPlans(Document):
	pass




@frappe.whitelist()
def create_plan():
    freq_map = {
        "Monthly": ("M", "monthly",1),
        "Quarterly": ("Q", "monthly",3),
        "Yearly": ("Y", "yearly",1),
    }
    rsp_doc = frappe.get_doc(
            "Recurring Service Pricing","PR-2024-2025-20131037-20")
    for add in rsp_doc.recurring_services:
        print(add.effective_to)

    admin_settings = frappe.get_doc('Admin Settings')
    razorpay_base_url = admin_settings.razorpay_base_url
    razorpay_key_id = admin_settings.razorpay_api_key
    # razorpay_secret = admin_settings.get_password('razorpay_secret')
    razorpay_secret = "QdnuRxUHrPGeiJc9lDTXYPO7"

    # Razorpay API URL
    razorpay_api_url = razorpay_base_url + "plans"

    # Authentication credentials
    auth = (razorpay_key_id, razorpay_secret)

    for freq in freq_map:
        period = freq_map[freq][1]
        interval = freq_map[freq][2]
        currency = "INR"
        gst = 18

        all_cust_array = frappe.get_all(
            "Customer",
            filters={
                "disabled": 0,
                "custom_billable": 1,
                "name": "20131037",
            },
            fields=["name", "custom_state"]
        )
        all_cust = {i.name: i.custom_state for i in all_cust_array}

        all_rsp = frappe.get_all(
            "Recurring Service Pricing",
            filters={
                "status": "Approved",
            },
            fields=["name", "customer_id", "customer_name"]
        )

        all_rsp_addons = frappe.get_all(
            "Recurring Service Item",
            filters={"parenttype": "Recurring Service Pricing", 
					 "frequency": freq, 
					 "revised_charges": [">", 0],
					#  "effective_to": ("not in",[None]), 
                    #  "effective_to": ("=","null"), 
                    "effective_to": ['is', 'not set'], 
                     },
            fields=["service_type", "service_id", "service_name", "revised_charges", "frequency", "parent"]
        )
        # print(all_rsp_addons)
        # print(freq)
        rsp_addons_map = {}
        for addon in all_rsp_addons:
            # print(addon.parent)
            if addon.parent in rsp_addons_map:
                rsp_addons_map[addon.parent].append(addon)
            else:
                rsp_addons_map[addon.parent] = [addon]  # Initialize with a list
        # print(rsp_addons_map)
        all_active_rsp = [rsp_cu for rsp_cu in all_rsp if rsp_cu.customer_id in all_cust]
        
        for rsp in all_active_rsp:
            customer_exists = frappe.db.exists("Razorpay Customer", {"customer_id":rsp.customer_id,"status":"Active"})
            if not customer_exists:
                customer_exists = create_customer(rsp.customer_id)

            # print(rsp)
            if rsp.name in rsp_addons_map:
                print("Yes")
                existing_plan = frappe.db.exists("Razorpay Plans", {"period":period,"interval":interval,"customer_id":rsp.customer_id,"status":"Active"})
                if existing_plan:
                    print("Plan already exists")
                    frappe.log_error(f"Plan for already exists for {freq} for customer {rsp.customer_id}",f"period:{period},interval:{interval},customer_id:{rsp.customer_id},status:Active")
                    continue
                # print(rsp_addons_map[rsp.name])
                # Plan data to be sent to Razorpay
                plan_name = f"{rsp.customer_name}({rsp.customer_id}) {freq} Plan"

                notes = {}
                amount = 0
                for add_on in rsp_addons_map[rsp.name]:
                    notes[add_on.service_name] = f"{add_on.service_type}({add_on.service_id}) at fees {add_on.revised_charges} + GST "
                    amount += (add_on.revised_charges * (100 + gst) / 100)

                amount = round(amount)
                amount = 100
                data = {
                    "period": period,
                    "interval": interval,
                    "item": {
                        "name": plan_name,
                        "amount": amount,   # Amount in paise (100 paise = 1 INR)
                        "currency": currency,
                    },
                    "notes": notes,  # Fixed assignment operator here
                }
                # print(data)

                # API request to create the plan
                try:
                    response = requests.post(razorpay_api_url, auth=auth, data=json.dumps(data), headers={"Content-Type": "application/json"})
                    plan_response = response.json()
                    # print(plan_response)
                    # Raise an error if the request fails
                    response.raise_for_status()

                    # Parse the JSON response
                    
                    print(plan_response)

                    # Call function to store the plan response in the Razorpay Api doctype
                    save_plan_in_razorpay_doctype(plan_response,rsp.customer_id,customer_exists)

                    # return plan_response

                except requests.exceptions.RequestException as e:
                    # print(data)
                    print(f"Error creating plan: {str(e)}")
            else:
                print("No0000000000000000000000000000000000000000000000")
	


def save_plan_in_razorpay_doctype(plan_response,customer_id,razorpay_customer_id):
    try:
        # Store Razorpay Plan details in the Frappe doctype
        doc = frappe.new_doc("Razorpay Plans")
        doc.plan_id = plan_response.get("id")
        doc.plan_name = plan_response.get("item", {}).get("name")
        doc.amount = plan_response.get("item", {}).get("amount")
        doc.currency = plan_response.get("item", {}).get("currency")
        doc.period = plan_response.get("period")
        doc.interval = plan_response.get("interval")
        doc.razorpay_customer_id = razorpay_customer_id
        doc.customer_id = customer_id
        doc.notes=str(plan_response.get("notes", {}))
        # # Store notes (if any)
        # notes = plan_response.get("notes", {})
        # for key, value in notes.items():
        #     doc.append("notes", {
        #         "key": key,
        #         "value": value
        #     })

        doc.insert()
        frappe.db.commit()

    except Exception as e:
        print(f"Error saving plan to Razorpay Plans doctype: {str(e)}")


@frappe.whitelist()
def create_customer(customer_id):
    customer_doc = frappe.get_doc("Customer",customer_id)
    # Fetch Razorpay credentials from Admin Settings
    admin_settings = frappe.get_doc('Admin Settings')
    razorpay_base_url = admin_settings.razorpay_base_url
    razorpay_key_id = admin_settings.razorpay_api_key
    razorpay_secret = "QdnuRxUHrPGeiJc9lDTXYPO7"  # Replace with your actual secret

    # Customer data
    customer_data = {
        "name": customer_doc.customer_name,
        # "email": customer_doc.custom_primary_email,
        "email": "vatsal.k@360ithub.com",
        # "contact": customer_doc.custom_primary_mobile_no,
        "contact": "9098543046",
        "type": "individual",  # Set the customer type; it could be 'individual' or 'company'
        # You can add more fields as needed
    }

    # Make the API request to create the customer
    try:
        response = requests.post(
            f"{razorpay_base_url}customers",
            auth=(razorpay_key_id, razorpay_secret),
            data=json.dumps(customer_data),
            headers={"Content-Type": "application/json"}
        )
        
        # Parse the response
        customer_response = response.json()

        # Check if the request was successful
        response.raise_for_status()  # Raises an error for bad responses (4xx, 5xx)
        
        # Print or log the response
        print("Customer created successfully:", customer_response)

        # Optionally, save the customer ID and other details in your Frappe app
        save_customer_in_frappe(customer_response,customer_id)

        return customer_response.get("id")  # Return the customer response for further use

    except requests.exceptions.RequestException as e:
        # Handle any errors during the API call
        print(f"Error creating customer: {str(e)}")
        return {"error": str(e)}

def save_customer_in_frappe(customer_response,customer_id):
    try:
        # Store Razorpay Customer details in a Frappe doctype
        doc = frappe.new_doc("Razorpay Customer")
        doc.razorpay_customer_id = customer_response.get("id")
        doc.razorpay_customer_name = customer_response.get("name")
        doc.razorpay_customer_email = customer_response.get("email")
        doc.razorpay_customer_mobile = customer_response.get("contact")
        doc.customer_id = customer_id
        doc.notes = json.dumps(customer_response.get("notes", {}))  # Convert notes to JSON string if necessary
        
        doc.insert()
        frappe.db.commit()
    except Exception as e:
        print(f"Error saving customer to Frappe: {str(e)}")
