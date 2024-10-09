import frappe
import requests
import json
from frappe.model.document import Document
import datetime as dt
import time
from datetime import datetime, timedelta
from dateutil.relativedelta import relativedelta

class RazorpaySubscription(Document):
    pass

@frappe.whitelist()
def create_subscription(start_at, months):
    months = int(months)
    start_at_unix = get_next_month_start_timestamp(start_at)
    end_at = get_date_after_n_months_minus_one_day(start_at, months)
    
    # Fetch Razorpay credentials from Admin Settings
    admin_settings = frappe.get_doc('Admin Settings')
    razorpay_base_url = admin_settings.razorpay_base_url
    razorpay_key_id = admin_settings.razorpay_api_key
    razorpay_secret = "QdnuRxUHrPGeiJc9lDTXYPO7"

    # Razorpay API URLs
    razorpay_subscription_url = f"{razorpay_base_url}subscriptions"
    razorpay_mandate_url = f"{razorpay_base_url}mandates"

    # Authentication credentials
    auth = (razorpay_key_id, razorpay_secret)

    # Fetch active Razorpay plans
    active_plans = frappe.get_all(
        "Razorpay Plans",
        filters={"status": "Active"},
        fields=["name", "customer_id", "amount", "period", "interval", "plan_name", "plan_id"]
    )

    for plan in active_plans:
        billing_cycles = calculate_billing_cycles(months, plan)
        
        existing_subscription = check_existing_subscription(plan, end_at, start_at)
        customer_exists = check_customer_exists(plan.customer_id)

        if not customer_exists:
            log_error(f"Razorpay Customer does not exist for Customer {plan.customer_id} for creating subscription for Plan {plan.plan_id}")
            continue
        
        if existing_subscription:
            log_error(f"Subscription already exists for {plan.plan_id} for customer {plan.customer_id}")
            continue
        
        mandate_id = create_mandate(plan,customer_exists, billing_cycles, razorpay_mandate_url, auth)

        if mandate_id:
            subscription_response = create_subscription_in_razorpay(plan,customer_exists, start_at_unix, billing_cycles, mandate_id, auth, razorpay_subscription_url)
            if subscription_response:
                save_subscription_in_frappe(subscription_response, plan.customer_id, plan, start_at, end_at, customer_exists, mandate_id)


def calculate_billing_cycles(months, plan):
    if plan.period == "yearly":
        return months / (plan.interval * 12)
    elif plan.period == "monthly":
        return months / plan.interval
    return None

def check_existing_subscription(plan, end_at, start_at):
    return frappe.db.exists(
        "Razorpay Subscription", 
        {
            "plan_id": plan.plan_id,
            "customer_id": plan.customer_id,
            "status": "Active",
            "start_date": ("<=", end_at),
            "end_date": (">=", start_at),
        }
    )

def check_customer_exists(customer_id):
    return frappe.db.exists("Razorpay Customer", {"customer_id": customer_id, "status": "Active"})

# def create_mandate(plan,razorpay_customer_id, billing_cycles, razorpay_mandate_url, auth):
#     mandate_data = {
#         "customer_id": razorpay_customer_id,
#         "amount": plan.amount,
#         "description": f"Mandate for Plan {plan.plan_name}",
#         "frequency": plan.period,
#         "currency": "INR",
#         "max_amount": plan.amount * billing_cycles,
#         # "type": "upi"  # Specify UPI mandate
#          "upi": {"vpa": "vatsalkanojiya-3@okicici"          
#     			},
#     }

#     try:
#         mandate_response = requests.post(
#             razorpay_mandate_url,
#             auth=auth,
#             data=json.dumps(mandate_data),
#             headers={"Content-Type": "application/json"}
#         )
#         print("razorpay_mandate_url",razorpay_mandate_url)
#         print("auth",auth)
#         print("mandate_data",mandate_data)
#         mandate_data_response = mandate_response.json()
#         print("Response Data",mandate_data_response)
#         mandate_response.raise_for_status()
#         print("Mandate created successfully:", mandate_data_response)

#         # Check for short_url to share with the client
#         short_url = mandate_data_response.get("short_url")
#         if short_url:
#             print(f"Short URL for client approval: {short_url}")
#             # Send the short_url to the client
#             send_short_url_to_client(short_url, plan.client_email)  # Assuming plan has a client_email attribute

#         create_local_mandate(mandate_data_response, plan,razorpay_customer_id)
#         return mandate_data_response.get("id")

#     except requests.exceptions.RequestException as e:
#         print(f"Error creating mandate: {str(e)}")
#         frappe.log_error(f"Error creating mandate: {str(e)}")
#         return None
def create_mandate(plan, razorpay_customer_id, billing_cycles, razorpay_mandate_url, auth):
    mandate_data = {
        "customer_id": razorpay_customer_id,
        "amount": int(plan.amount * 100),  # Amount in paise
        "description": f"Mandate for Plan {plan.plan_name}",
        "frequency": plan.period,
        "currency": "INR",
        "max_amount": int(plan.amount * billing_cycles * 100),  # Max amount in paise
        "upi": {"vpa": "vatsalkanojiya-3@okicici"}  # Ensure this is valid
    }

    try:
        mandate_response = requests.post(
            razorpay_mandate_url,
            auth=auth,
            data=json.dumps(mandate_data),
            headers={"Content-Type": "application/json"}
        )
        mandate_response.raise_for_status()  # Check for HTTP errors

        mandate_data_response = mandate_response.json()  # Now access the JSON
        print("Response Data", mandate_data_response)

        # Check for short_url to share with the client
        short_url = mandate_data_response.get("short_url")
        if short_url:
            print(f"Short URL for client approval: {short_url}")
            # Send the short_url to the client
            send_short_url_to_client(short_url, plan.client_email)  # Assuming plan has a client_email attribute

        create_local_mandate(mandate_data_response, plan, razorpay_customer_id)
        return mandate_data_response.get("id")

    except requests.exceptions.RequestException as e:
        print(f"Error creating mandate: {str(e)}")
        frappe.log_error(f"Error creating mandate: {str(e)}")
        return None


def send_short_url_to_client(short_url, client_email):
    subject = "Approval Required: UPI Mandate"
    message = f"Please approve your UPI mandate using the following link: {short_url}"

    # frappe.sendmail(
    #     recipients=[client_email],
    #     subject=subject,
    #     message=message
    # )


def create_local_mandate(mandate_data, plan,razorpay_customer_id):
    try:
        mandate_doc = frappe.new_doc("Razorpay Mandate")
        mandate_doc.customer_id = plan.customer_id
        mandate_doc.razorpay_customer_id = razorpay_customer_id
        mandate_doc.status = mandate_data.get("status")
        mandate_doc.notes = mandate_data.get("description", "No description provided.")
        mandate_doc.razorpay_plan_id = plan.plan_id
        mandate_doc.razorpay_mandate_id = mandate_data.get("id")
        mandate_doc.mandate_amount = mandate_data.get("amount")
        mandate_doc.insert()
        frappe.db.commit()
        print(f"Mandate created in Frappe: {mandate_doc.name}")
    except Exception as e:
        print(f"Error creating mandate in Frappe: {str(e)}")

def create_subscription_in_razorpay(plan,razorpay_customer_id, start_at_unix, billing_cycles, mandate_id, auth, razorpay_subscription_url):
    data = {
        "plan_id": plan.plan_id,
        "total_count": billing_cycles,
        "customer_notify": 0,
        "quantity": 1,
        "notes": {
            "Plan Name": plan.plan_name,
            "Customer ID": plan.customer_id,
        },
        "start_at": start_at_unix,
        "customer_id": razorpay_customer_id,
        "mandate_id": mandate_id,
    }

    try:
        response = requests.post(
            razorpay_subscription_url, 
            auth=auth, 
            data=json.dumps(data), 
            headers={"Content-Type": "application/json"}
        )
        response.raise_for_status()
        subscription_response = response.json()
        print("Subscription created successfully:", subscription_response)
        return subscription_response

    except requests.exceptions.RequestException as e:
        print(f"Error creating subscription: {str(e)}")
        raise

def save_subscription_in_frappe(subscription_response, customer_id, plan, start_at, end_at, customer_exists, mandate_id):
    try:
        doc = frappe.new_doc("Razorpay Subscription")
        doc.subscription_id = subscription_response.get("id")
        doc.plan = plan.name
        doc.customer_id = customer_id
        doc.quantity = subscription_response.get("quantity")
        doc.total_count = subscription_response.get("total_count")
        doc.start_date = start_at
        doc.end_date = end_at
        doc.amount = plan.amount
        doc.mandate_id = mandate_id
        doc.status = "Created"
        doc.insert()
        frappe.db.commit()
    except Exception as e:
        print(f"Error saving subscription to Frappe: {str(e)}")

def log_error(message):
    print(message)
    frappe.log_error(message)

def get_next_month_start_timestamp(custom_date_str):
    date_format = "%Y-%m-%d"
    given_date = datetime.strptime(custom_date_str, date_format).date()

    # next_month_start = (given_date + relativedelta(months=1)).replace(day=1)
    next_month_start = given_date 
    return int(time.mktime(next_month_start.timetuple()))

def get_date_after_n_months_minus_one_day(custom_date_str, n):
    date_format = "%Y-%m-%d"
    given_date = datetime.strptime(custom_date_str, date_format).date()
    new_date = given_date + relativedelta(months=n) - timedelta(days=1)
    return new_date
