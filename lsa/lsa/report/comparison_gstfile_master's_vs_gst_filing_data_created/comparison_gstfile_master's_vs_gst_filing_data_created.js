// Copyright (c) 2024, Mohan and contributors
// For license information, please see license.txt

frappe.query_reports["Comparison Gstfile Master's Vs GST Filing Data created"] = {
	"filters": [
		{
			fieldname: "gst_yearly_filling_summery_status_filter",
			label: __("GST Yearly Filling Summery"),
			fieldtype: "Select",
			options:["All","With Yearly Filling Summery","Without Yearly Filling Summery"],
			default: "All",
		},	
		{
			fieldname: "gst_filing_data_status_filter",
			label: __("GST Filing Data"),
			fieldtype: "Select",
			options:["All","With Filing Data","Without Filing Data"],
			default: "All",
		},
	]
};
