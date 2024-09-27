// Copyright (c) 2024, Mohan and contributors
// For license information, please see license.txt

frappe.query_reports["IT Assessee Files Custom Report View"] = {
	"filters": [
		{
			"fieldname": "name",
			"label": __("ID"),
			"fieldtype": "Link",
			"options": "IT Assessee File"
		},
		{
			"fieldname": "customer_id",
			"label": __("Customer ID"),
			"fieldtype": "Link",
			"options": "Customer"
		},

		{
			"fieldname": "assessee_name",
			"label": __("Assessee Name"),	
			"fieldtype": "Data",
		},
		{
			"fieldname": "pan",
			"label": __("PAN"),	
			"fieldtype": "Data",
		},
	]
};

