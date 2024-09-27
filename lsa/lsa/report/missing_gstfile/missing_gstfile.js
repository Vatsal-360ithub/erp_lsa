// Copyright (c) 2024, Mohan and contributors
// For license information, please see license.txt

frappe.query_reports["Missing Gstfile"] = {
	"filters": [
		{
			fieldname: "financial_year",
			label: __("Financial Year"),
			fieldtype: "Link",
			options:"Gst Yearly Summery Report",
		},	
		{
			fieldname: "file_availability",
			label: __("File Availablilty"),
			fieldtype: "Select",
			options:["All","Available","Unavailable"],
			default: "Unavailable",
		},	
		{
			fieldname: "gstfile_enabled",
			label: __("GST File Enabled"),
			fieldtype: "Select",
			options:["All","Enabled","Disabled"],
			default: "Enabled",
		},	

	]
};

