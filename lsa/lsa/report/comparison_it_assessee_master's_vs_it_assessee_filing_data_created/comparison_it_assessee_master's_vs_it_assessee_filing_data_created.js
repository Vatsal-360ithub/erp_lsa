// Copyright (c) 2024, Mohan and contributors
// For license information, please see license.txt

frappe.query_reports["Comparison IT Assessee Master's Vs IT Assessee Filing Data created"] = {
	"filters": [
		{
			fieldname: "it_assessee_filing_data_status_filter",
			label: __("Master with Filing Data"),
			fieldtype: "Select",
			options:["All","With Filing Data","Without Filing Data"],
			default: "All",
		},	

	]
};
