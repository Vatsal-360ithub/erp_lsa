# Copyright (c) 2024, Mohan and contributors
# For license information, please see license.txt

import frappe


def execute(filters=None):
	columns, data = [], []
	columns = [
        # Customer details columns
        {"label": "CID", "fieldname": "customer_id", "fieldtype": "Link", "options": "Customer", "width": 120},
        {"label": "IT Assessee File", "fieldname": "it_assessee_file", "fieldtype": "Link", "options": "IT Assessee File", "width": 150},
		{"label": "FY", "fieldname": "fy", "fieldtype": "Link", "options": "IT Assessee File Yearly Report", "width": 150},
        {"label": "IT Assessee Filing Data Status", "fieldname": "it_assessee_filing_data_status", "fieldtype": "Data", "width": 50, "color": "blue"},
        {"label": "IT Assessee Filing Data", "fieldname": "it_assessee_filing_data", "fieldtype": "Link", "options": "IT Assessee Filing Data", "width": 300},
	]

	data=get_data(filters)
	return columns, data

def get_data(filters):
	data = []


	it_assessee_files_records = frappe.get_all(
		"IT Assessee File",
		filters={"enabled": 1},
		fields=["customer_id", "name"]
	)

	fy_s = frappe.get_all("IT Assessee File Yearly Report", fields=["name"])

	for fy in fy_s:
		for it_assessee_files_record in it_assessee_files_records:
			it_assessee_filing_data = frappe.get_all(
				"IT Assessee Filing Data",
				filters={
					"it_assessee_file": it_assessee_files_record.name,
					"ay": fy.name,
				},
				fields=["name"]
			)
			if it_assessee_filing_data:
				data_row = {
					"customer_id": it_assessee_files_record.customer_id,
					"it_assessee_file": it_assessee_files_record.name,
					"fy": fy.name,
					"it_assessee_filing_data_status": True,
					"it_assessee_filing_data": it_assessee_filing_data[0].name,
				}
				if (filters.get("it_assessee_filing_data_status_filter") in ["All","With Filing Data"]):
					data.append(data_row)
			else:
				data_row = {
					"customer_id": it_assessee_files_record.customer_id,
					"it_assessee_file": it_assessee_files_record.name,
					"fy": fy.name,
					"it_assessee_filing_data_status": False,
					"it_assessee_filing_data": None,
				}
				if (filters.get("it_assessee_filing_data_status_filter") in ["All","Without Filing Data"]):
					data.append(data_row)

	return data


