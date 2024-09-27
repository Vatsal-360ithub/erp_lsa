// Copyright (c) 2024, Mohan and contributors
// For license information, please see license.txt

frappe.query_reports["Missing IT Assessee File"] = {
	"filters": [
		{
			fieldname: "financial_year",
			label: __("Financial Year"),
			fieldtype: "Link",
			options:"IT Assessee File Yearly Report",
		},	
		{
			fieldname: "file_availability",
			label: __("File Availablilty"),
			fieldtype: "Select",
			options:["All","Available","Unavailable"],
			//default: "Unavailable",
		},	
		{
			fieldname: "it_assessee_file_enabled",
			label: __("IT Assessee File Enabled"),
			fieldtype: "Select",
			options:["All","Enabled","Disabled"],
			//default: "Enabled",
		},	

	]
};
