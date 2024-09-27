// Copyright (c) 2023, Mohan and contributors
// For license information, please see license.txt

frappe.query_reports["Sales Order Payment Status"] = {
	"filters": [
		{
			fieldname: "status",
			label: __("Document Status"),
			fieldtype: "Select",
			options:["  ","Draft","To Deliver and Bill","Cancelled"],
			// reqd: 1,
			default: "  ",
			// description:"af",
		},
		{
			fieldname: "payment_status",
			label: __("Payment Status"),
			fieldtype: "MultiSelect",  // Change fieldtype to "MultiSelect" for multi-select filter
			options: ["Due","Cleared","Partially Paid"],
			default: "Due ,Partially Paid",
		},
		{
		    fieldname: "custom_so_date_range",
		    label: __("SO To Date"),
		    fieldtype: "DateRange",
		    default: [frappe.datetime.add_days(frappe.datetime.now_date(), -30), frappe.datetime.now_date()],
		},
		
	]
};

