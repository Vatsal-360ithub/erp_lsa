// Copyright (c) 2024, Mohan and contributors
// For license information, please see license.txt

frappe.query_reports["Dummy Sales Order Custom Report"] = {
	"filters": [
		

		{
			"fieldname": "customer_id",
			"label": __("CID"),
			"fieldtype": "Link",
			"options": "Customer",
		},

		{
			fieldname: "doc_status",
			label: __("Doc Status"),
			fieldtype: "MultiSelect",
			options:["Draft","Submitted","Cancelled"],
			default: "Draft,Submitted",
		},
		{
			fieldname: "custom_payment_status",
			label: __("Payment Status"),
			fieldtype: "MultiSelect",  // Change fieldtype to "MultiSelect" for multi-select filter
			options: ["Unpaid","Cleared","Partially Paid"],
			default: "Unpaid,Partially Paid",
		},
	]
};
