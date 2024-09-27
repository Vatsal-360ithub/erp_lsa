// Copyright (c) 2024, Mohan and contributors
// For license information, please see license.txt

frappe.query_reports["Sales Order with Mismatch Items"] = {

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
		// {
		// 	fieldname: "custom_payment_status",
		// 	label: __("Payment Status"),
		// 	fieldtype: "MultiSelect",  // Change fieldtype to "MultiSelect" for multi-select filter
		// 	options: ["Unpaid","Cleared","Partially Paid"],
		// 	default: "Unpaid,Partially Paid",
		// },
		{
			fieldname: "customer_enabled_filter",
			label: __("Customer Enabled"),
			fieldtype: "Select",
			options:["","Customer Enabled","Customer Disabled"],
			default: "Customer Enabled",
			
		},
		// {
		// 	fieldname: "custom_customer_status_",
		// 	label: __("Customer Status"),
		// 	fieldtype: "MultiSelect",  // Change fieldtype to "MultiSelect" for multi-select filter
		// 	options: ["ACTIVE","ON NOTICE","HOLD"],
		// 	//default: "ACTIVE,ON NOTICE",
		// },
		// {
		// 	fieldname: "sales_invoice",
		// 	label: __("Sales Invoice"),
		// 	fieldtype: "Select",
		// 	options:["Yes","No",""],
		// 	default: "No",
		// },
				{
			fieldname: "from_date",
			label: __("From Date"),
			fieldtype: "Date",
			reqd: true,
			default: "2023-04-01",
		},
		{
			fieldname: "to_date",
			label: __("To Date"),
			fieldtype: "Date",
			reqd: true,
			default: "2024-03-31",
		},
		// {
		// 	fieldname: "followup_range",
		// 	label: __("Followup Date Range"),
		// 	fieldtype: "Date Range",
		// 	// reqd: true,
		// 	// default: "2025-03-31",
		// },
	]
};





