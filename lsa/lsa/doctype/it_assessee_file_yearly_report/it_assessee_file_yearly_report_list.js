frappe.listview_settings['IT Assessee File Yearly Report'] = {
    // ... (other settings remain unchanged)

    button: {
        show: function (doc) {
            return doc.name;
        },
        get_label: function () {
            return __("Open", null, "Access");
        },
        get_description: function (doc) {
            return __("Open {0}", [`${__(doc.name)}`]);
        },
        action: function (doc) {
            console.log(doc.name);

            // Check if 'name' is present in the document and is a string
            if (typeof doc.name === 'string') {
                // Your logic here
                frappe.route_options = {
                    'ay': ['=', doc.name]
                };

                frappe.set_route("List", "IT Assessee Filing Data");
            } else {
                // Handle the case where 'name' is not a string
                console.error('Invalid value for name:', doc.name);
            }
        },
    },
};

