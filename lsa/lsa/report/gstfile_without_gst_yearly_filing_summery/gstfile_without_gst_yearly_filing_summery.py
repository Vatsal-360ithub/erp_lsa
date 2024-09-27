# Copyright (c) 2024, Mohan and contributors
# For license information, please see license.txt

# import frappe


def execute(filters=None):
	columns, data = [], []
	return columns, data
# Copyright (c) 2024, Mohan and contributors
# For license information, please see license.txt

import frappe


def execute(filters=None):
	columns, data = [], []
	columns = [
        # Customer details columns
        {"label": "CID", "fieldname": "customer_id", "fieldtype": "Link", "options": "Customer", "width": 150},
        {"label": "GSTIN", "fieldname": "gstfile", "fieldtype": "Link", "options": "Gstfile", "width": 200},
		{"label": "GST Type", "fieldname": "gst_type", "fieldtype": "Data", "width": 150},
        {"label": "FY", "fieldname": "fy", "fieldtype": "Link", "options": "Gst Yearly Summery Report", "width": 100},	
	]

	data=get_data(filters)
	return columns, data

def get_data(filters):
	data=[]

	gstfiles_records=frappe.get_all("Gstfile",
								 filters={"enabled":1},
								 fields=["customer_id","name","gst_type"])
	fy_s=frappe.get_all("Gst Yearly Summery Report",fields=["name"])
	gst_yearly_filling_summery=frappe.get_all("Gst Yearly Filing Summery",
													fields=["name","gstin","fy"])
	gst_yearly_filling_summery=[(i.gstin,i.fy) for i in gst_yearly_filling_summery]

	for fy in fy_s:
		for gstfiles_record in gstfiles_records:
			if (gstfiles_record.name,fy.name) not in gst_yearly_filling_summery :
				data_row = {
							"customer_id": gstfiles_record.customer_id,
							"gstfile": gstfiles_record.name,
							"gst_type":gstfiles_record.gst_type,
							"fy": fy.name,
							}
				data.append(data_row)


	return data



