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
		{"label": "Gst Yearly Filing Summery Status", "fieldname": "gst_yearly_filling_summery_status", "fieldtype": "Data", "width": 50, "color": "blue"},
		{"label": "Gst Yearly Filing Summery", "fieldname": "gst_yearly_filling_summery", "fieldtype": "Link", "options": "Gst Yearly Filing Summery", "width": 300},
		
	]

	data=get_data(filters)
	return columns, data

def get_data(filters):
	data = []

	gstfiles_filter={}
	if (filters.get("gstfile_enabled")):
		if (filters.get("gstfile_enabled"))=="Enabled":
			gstfiles_filter["enabled"]=1
		elif (filters.get("gstfile_enabled"))=="Disabled":
			gstfiles_filter["enabled"]=0

	gst_files_records = frappe.get_all(
		"Gstfile",
		filters=gstfiles_filter,
		fields=["customer_id", "name","gst_type"]
	)

	fy_s = frappe.get_all("Gst Yearly Summery Report", fields=["name"])

	for fy in fy_s:
		for gst_files_record in gst_files_records:
			gst_yearly_filling_summery = frappe.get_all(
				"Gst Yearly Filing Summery",
				filters={
					"gstin": gst_files_record.name,
					"fy": fy.name,
				},
				fields=["name"]
			)
			if gst_yearly_filling_summery:
				data_row = {
					"customer_id": gst_files_record.customer_id,
					"gstfile": gst_files_record.name,
					"gst_type":gst_files_record.gst_type,
					"fy": fy.name,
					"gst_yearly_filling_summery_status": True,
					"gst_yearly_filling_summery": gst_yearly_filling_summery[0].name,
				}
				
				if filters.get("file_availability"):
					if (filters.get("file_availability") in ["All","Available"]):
						if (filters.get("financial_year")):
							if (filters.get("financial_year"))==fy.name:
								data.append(data_row)
						else:
							data.append(data_row)
				else:
					data.append(data_row)
			else:
				data_row = {
					"customer_id": gst_files_record.customer_id,
					"gstfile": gst_files_record.name,
					"gst_type":gst_files_record.gst_type,
					"fy": fy.name,
					"gst_yearly_filling_summery_status": False,
					"gst_yearly_filling_summery": None,
				}
				
				if filters.get("file_availability"):
					if (filters.get("file_availability") in ["All","Unavailable"]):
						if (filters.get("financial_year")):
							if (filters.get("financial_year"))==fy.name:
								data.append(data_row)
						else:
							data.append(data_row)
				else:
					data.append(data_row)

	return data



