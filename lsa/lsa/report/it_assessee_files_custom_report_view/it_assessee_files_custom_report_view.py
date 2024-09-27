# Copyright (c) 2024, Mohan and contributors
# For license information, please see license.txt

import frappe

def execute(filters=None):
    columns = [
        {"fieldname": "customer_id", "label": ("CID"), "fieldtype": "Link", "options": "Customer","width": 100},
        {"fieldname": "id", "label": ("ID"), "fieldtype": "Link", "options": "IT Assessee File","width": 100},
        {"fieldname": "enabled", "label": ("Enables"), "fieldtype": "Check", "width": 50},
        {"fieldname": "assessee_name", "label": ("Assessee Name"), "fieldtype": "Data", "width": 150},
        {"fieldname": "date_of_birth", "label": ("Date Of Birth"), "fieldtype": "Date", "width": 100},
        {"fieldname": "registered_mob", "label": ("Registered Mob"), "fieldtype": "Data", "width": 100},
		{"fieldname": "email_id", "label": ("Email id"), "fieldtype": "Data", "width": 100},
        {"fieldname": "pan", "label": ("PAN"), "fieldtype": "Data", "width": 100},
        {"fieldname": "it_password", "label": ("IT Password"), "fieldtype": "Data", "width": 100},
        {"fieldname": "aadhaar_number", "label": ("Aadhaar Number"), "fieldtype": "Data", "width": 100},
        {"fieldname": "assessee_type", "label": ("Assessee Type"), "fieldtype": "Data", "width": 100},
        {"fieldname": "gst_registered", "label": ("GST Registered"), "fieldtype": "Data", "width": 100},
		{"fieldname": "gstin_company", "label": ("GSTIN Company Name"), "fieldtype": "Data", "width": 100},
		{"fieldname": "gst_type", "label": ("GST Type"), "fieldtype": "Data", "width": 100},
    ]

	# Construct additional filters based on the provided filters
    additional_filters = {}
    if filters.get("name"):
        additional_filters["name"] = ["like", f"%{filters['name']}%"]
    if filters.get("customer_id"):
        additional_filters["customer_id"] = ["like", f"%{filters['customer_id']}%"]
    if filters.get("enabled"):
        additional_filters["enabled"] = filters.get("enabled")
    if filters.get("assessee_name"):
        additional_filters["assessee_name"] = ["like", f"%{filters['assessee_name']}%"]
    if filters.get("pan"):
        additional_filters["pan"] = ["like", f"%{filters['pan']}%"]
        
    # Fetch data using Frappe ORM
    data = frappe.get_all(
        "IT Assessee File",
        filters=additional_filters,
        fields=["customer_id","name", "enabled", "assessee_name","date_of_birth","registered_mob",
                "email_id","pan","it_password", "aadhaar_number", "assessee_type",
                # "assessee_first_name","assessee_middle_name","assessee_last_name",
                ],
        as_list=True
    )
    print(data)
    data=list(data)
    for i in range(len(data)):
        gst = frappe.get_all(
        "Gstfile",
        filters={"pan":data[i][7]},
        fields=["name", "customer_name", "gst_type"])
        print(gst)
        if gst:
            gst_comp=[]
            type=[]
            for j in gst:
                gst_comp+=[j.name+"-"+j.customer_name]
                if j.gst_type not in type:
                	type+=[j.gst_type]
            data[i]=list(data[i])
            data[i]+=["Yes",", ".join(gst_comp),", ".join(type)]
            data[i]=tuple(data[i])
        else:
            data[i]=list(data[i])
            data[i]+=["No","",""]
            data[i]=tuple(data[i])
    data=tuple(data)


    return columns, data







