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
        {"label": "CID", "fieldname": "customer_id", "fieldtype": "Link", "options": "Customer", "width": 100, "height": 100},
        {"label": "GSTIN", "fieldname": "gstfile", "fieldtype": "Link", "options": "Gstfile", "width": 170, "height": 100},
		{"label": "GST Type", "fieldname": "gst_type", "fieldtype": "Data", "width": 100, "height": 100},
        {"label": "Month", "fieldname": "month", "fieldtype": "Data", "width": 80, "height": 100},
        {"label": "GST Yearly Filling Summery Status", "fieldname": "gst_yearly_filling_summery_status", "fieldtype": "Data", "width": 70, "height": 100},
        {"label": "GST Yearly Filling Summery", "fieldname": "gst_yearly_filling_summery", "fieldtype": "Link", "options": "Gst Yearly Filing Summery", "width": 280, "height": 100},
		{"label": "Files of Year Possible", "fieldname": "files_of_year_possible", "fieldtype": "Link", "options": "Gst Filing Data Report", "width": 220, "height": 100},
		{"label": "GST Filling Data Status", "fieldname": "gst_filling_data_status", "fieldtype": "Data", "width": 70, "height": 100},
		{"label": "GST Filling Data", "fieldname": "actual_customer_file", "fieldtype": "Link", "options": "Gst Filling Data", "width": 280, "height": 100},
		# {"label": "GST Filling Data", "fieldname": "actual_customer_file", "fieldtype": "Data", "width": 150, "height": 100},
		
	]

	data=get_data(filters)
	return columns, data

def get_data(filters):
	data=[]

	gstfiles_records=frappe.get_all("Gstfile",
								 filters={"enabled":1},
								 fields=["customer_id","name","gst_type"])
	fy_s=frappe.get_all("Gst Yearly Summery Report",fields=["name"])
	

	for fy in fy_s:
		for gstfiles_record in gstfiles_records:
			gst_yearly_filling_summery=frappe.get_all("Gst Yearly Filing Summery",
													filters={"gstin":gstfiles_record.name},
													fields=["name","gstin"])
			if gst_yearly_filling_summery:
				gst_filing_data_reports=frappe.get_all("Gst Filing Data Report",
								 filters={"gst_type":gstfiles_record.gst_type,
				 						"gst_yearly_summery_report":fy.name},
								 fields=["name","month","quarterly"])
				if gst_filing_data_reports[0].month:
					data_row_month=gst_filing_data_reports[0].month
				else:
					data_row_month=gst_filing_data_reports[0].quarterly

				for gst_filing_data_report in gst_filing_data_reports:
					gst_filling_data=frappe.get_all("Gst Filling Data",
								 filters={"gst_filling_report_id":gst_filing_data_report.name,
				  						 "gst_yearly_filling_summery_id":gst_yearly_filling_summery[0].name},
								 fields=["name","month"])
					if gst_filling_data:
						data_row = {
									"customer_id": gstfiles_record.customer_id,
									"gstfile": gstfiles_record.name,
									"gst_type":gstfiles_record.gst_type,
									"month": data_row_month,
									"gst_yearly_filling_summery":gst_yearly_filling_summery[0].name,
									"gst_yearly_filling_summery_status": True ,
									"files_of_year_possible": gst_filing_data_report.name,
									"gst_filling_data_status":True,
									"actual_customer_file":gst_filling_data[0].name,
									}
						if (filters.get("gst_yearly_filling_summery_status_filter") in ["All","With Yearly Filling Summery"]) \
							and (filters.get("gst_filing_data_status_filter") in ["All","With Filing Data"]):
							data.append(data_row)
					else:
						data_row = {
									"customer_id": gstfiles_record.customer_id,
									"gstfile": gstfiles_record.name,
									"gst_type":gstfiles_record.gst_type,
									"month": data_row_month,
									"gst_yearly_filling_summery":gst_yearly_filling_summery[0].name,
									"gst_yearly_filling_summery_status": True ,
									"files_of_year_possible": gst_filing_data_report.name,
									"gst_filling_data_status":False,
									"actual_customer_file":None,
									}
						if (filters.get("gst_yearly_filling_summery_status_filter") in ["All","With Yearly Filling Summery"]) \
							and (filters.get("gst_filing_data_status_filter") in ["All","Without Filing Data"]):
							data.append(data_row)
			else:
				gst_filing_data_reports=frappe.get_all("Gst Filing Data Report",
									filters={"gst_type":gstfiles_record.gst_type,
										"gst_yearly_summery_report":fy.name},
									fields=["name"])
				if gst_filing_data_reports[0].month:
					data_row_month=gst_filing_data_reports[0].month
				else:
					data_row_month=gst_filing_data_reports[0].quarterly

				for gst_filing_data_report in gst_filing_data_reports:
					data_row = {
								"customer_id": gstfiles_record.customer_id,
								"gstfile": gstfiles_record.name,
								"gst_type":gstfiles_record.gst_type,
								"month": data_row_month,
								"gst_yearly_filling_summery":None,
								"gst_yearly_filling_summery_status": False ,
								"files_of_year_possible": gst_filing_data_report.name,
								"gst_filling_data_status":False,
								"actual_customer_file":None,
								}
					if (filters.get("gst_yearly_filling_summery_status_filter") in ["All","Without Yearly Filling Summery"]) \
							and (filters.get("gst_filing_data_status_filter") in ["All","Without Filing Data"]):
							data.append(data_row)

	return data


