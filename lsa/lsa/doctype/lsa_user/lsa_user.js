// Copyright (c) 2024, Mohan and contributors
// For license information, please see license.txt

frappe.ui.form.on("LSA User", {
    before_submit: function (frm) {
        // Perform actions after form submission

        console.log("User is Created");

        // Reload the form
        // frm.reload_doc();
        location.reload(true);
    },
    onload: function (frm) {
        // Clear existing roles wrapper content
        frm.fields_dict.lsa_roles.$wrapper.empty();

        if (frm.doc.docstatus === 1) {
            frappe.call({
                method: 'lsa.lsa.doctype.lsa_user.lsa_user.get_lsa_roles_and_core_user_roles',
                args: {
                    u_id: frm.doc.name,
                },
                callback: function (r) {
                    var lsaRoles = r.message.lsa_roles;
                    var coreUserRoles = r.message.core_user_roles;

                    // Create the role editor div
                    var roleEditorDiv = $('<div class="role-editor">').appendTo(frm.fields_dict.lsa_roles.wrapper);

                    // Create the inner div with class "frappe-control"
                    var innerDiv = $('<div class="frappe-control" data-fieldtype="MultiCheck" data-fieldname="roles">')
                        .append($('<span class="tooltip-content">').text("roles"))
                        .appendTo(roleEditorDiv);

                    // Create the checkbox options div
                    var checkboxOptionsDiv = $('<div class="checkbox-options">')
                        .append($('<div class="load-state text-muted small">').text("Loading...").hide())
                        .appendTo(innerDiv);

                    // Create a container for the columns
                    var columnsContainer = $('<div class="columns-container" style="display:flex;justify-content:space-around;">')
                        .appendTo(checkboxOptionsDiv);

                    // Calculate the number of roles per column
                    var rolesPerColumn = Math.ceil(lsaRoles.length / 3);

                    // Create three columns
                    for (var i = 0; i < 3; i++) {
                        // Create a column div
                        var columnDiv = $('<div class="column" >').appendTo(columnsContainer);

                        // Populate roles in the column
                        for (var j = i * rolesPerColumn; j < (i + 1) * rolesPerColumn && j < lsaRoles.length; j++) {
                            var role = lsaRoles[j];
                            var isChecked = coreUserRoles.some(userRole => userRole.role === role);

                            // Create checkbox div
                            var checkboxDiv = $('<div class="checkbox unit-checkbox">')
                                .append($('<label title="">')
                                    .append($('<input class ="lsa_roles" type="checkbox" data-unit="' + role + '"' + (isChecked ? ' checked' : '') + '>'))
                                    .append($('<span class="label-area" data-unit="' + role + '">').text(role))
                                )
                                .appendTo(columnDiv);
                        }
                    }

                    // Create button div
                    var buttonDiv = $('<div class="button-div" style="text-align: right;">').appendTo(checkboxOptionsDiv);

                    // Create update button
                    var updateButton = $('<button class="btn btn-primary" style="margin:20px;">Update Roles</button>')
                        .appendTo(buttonDiv)
                        .on('click', function () {
                            frappe.confirm(
                                "Are you sure you want to update core user roles?",
                                function () {
                                    var rolesHTML = $('#page-LSA\\ User [data-fieldname="roles_for_user"]').html();
                                    var rolesData = extractRolesFromHTML(rolesHTML);

                                    frappe.call({
                                        method: 'lsa.lsa.doctype.lsa_user.lsa_user.update_core_user_roles',
                                        args: {
                                            u_id: frm.doc.name,
                                            roles: JSON.stringify(rolesData),
                                        },
                                        callback: function (r) {
                                            if (r.message) {
                                                frappe.msgprint(__('User roles updated successfully.'));
                                                frm.refresh();
                                            } else {
                                                frappe.msgprint("Server Side Error");
                                            }
                                        }
                                    });
                                },
                                function () {
                                    console.log("Update Roles canceled.");
                                }
                            );
                        });
                },
            });
        }
        else{
            var targetDiv = $('.section-head:contains("LSA Roles")');
            // Empty the content of the targeted div
            targetDiv.empty();
        }
    },
});

// Function to extract selected roles from HTML
function extractRolesFromHTML(html) {
    var roles = [];
    var selectedCheckboxes = document.querySelectorAll('.lsa_roles:checked');

    selectedCheckboxes.forEach(function (checkbox) {
        var dataUnit = checkbox.getAttribute('data-unit');
        roles.push(dataUnit);
    });

    return roles;
}

