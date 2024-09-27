# Copyright (c) 2023, mohan@360ithub.com and contributors
# For license information, please see license.txt
import frappe


def execute(filters=None):
    # Add "Payment Status" and "Document Status" as filters in the report
    columns = [
        {
            "label": "ID",
            "fieldname": "name",
            "fieldtype": "Link",
            "options": "Sales Order",
            "width": 100
        },
        {
            "label": "CID",
            "fieldname": "customer",
            "fieldtype": "Link",
            "options": "Customer",
            "width": 140
        },
        {
            "label": "Customer Name",
            "fieldname": "customer_name",
            "fieldtype": "Data",
            "width": 200
        },
        {
            "label": "Mobile No.",
            "fieldname": "contact_mobile",
            "fieldtype": "Data",
            "width": 140
        },
        {
            "label": "Transaction Date",
            "fieldname": "transaction_date",
            "fieldtype": "Date",
            "width": 100
        },
        {
            "label": "SO From Date",
            "fieldname": "custom_so_from_date",
            "fieldtype": "Date",
            "width": 140
        },
        {
            "label": "SO To Date",
            "fieldname": "custom_so_to_date",
            "fieldtype": "Date",
            "width": 140
        },
        {
            "label": "Total",
            "fieldname": "total",
            "fieldtype": "Currency",
            "width": 100
        },
        {
            "label": "Total Taxes and Charges",
            "fieldname": "total_taxes_and_charges",
            "fieldtype": "Currency",
            "width": 150
        },
        {
            "label": "Rounded Total",
            "fieldname": "rounded_total",
            "fieldtype": "Currency",
            "width": 120
        },
        {
            "label": "Advance Paid",
            "fieldname": "advance_paid",
            "fieldtype": "Currency",
            "width": 100
        },
        {
            "label": "Remaining Bal (INR)",
            "fieldname": "remaining_bal",
            "fieldtype": "Currency",
            "width": 100
        },
        {
            "label": "Payment Status",
            "fieldname": "payment_status",
            "fieldtype": "Data",
            "width": 100
        },
        {
            "label": "Document Status",
            "fieldname": "status",
            "fieldtype": "Data",
            "width": 100
        }
    ]

    # Fetch data from the Sales Order DocType
    data = get_data(filters)

    return columns, data


def get_data(filters):
    # Fetch all relevant data from the Sales Order DocType
    data = frappe.get_all(
        "Sales Order",
        filters={},
        fields=[
            "name",
            "customer",
            "customer_name",
            "contact_mobile",
            "transaction_date",
            "total",
            "advance_paid",
            "total_taxes_and_charges",
            "rounded_total",
            "custom_so_from_date",
            "custom_so_to_date",
            "total",
            "status",
        ],
    )

    # Process the data and calculate additional fields
    processed_data = []

    for row in data:
        advance_paid = row.get("advance_paid", 0)
        amount = row.get("rounded_total", 0)
        remaining_bal = amount - advance_paid
        payment_status = "Cleared" if remaining_bal == 0 else ("Due" if remaining_bal == amount else "Partially Paid")

        # Extract the custom_so_to_date from the row
        custom_so_to_date = row.get("custom_so_to_date")

        # Apply the payment_status, status, and date range filters after fetching the data
        if (
            (not filters.get("payment_status") or payment_status in filters.get("payment_status")) and
            (not filters.get("status") or filters.get("status") == row.get("status")) and
            (not filters.get("custom_so_date_range") or 
                (
                    custom_so_to_date and
                    custom_so_to_date >= frappe.utils.data.getdate(filters.get("custom_so_date_range")[0]) and
                    custom_so_to_date <= frappe.utils.data.getdate(filters.get("custom_so_date_range")[1])
                )
            )
        ):
            processed_data.append({
                "name": row.get("name"),
                "customer": row.get("customer"),
                "customer_name": row.get("customer_name"),
                "contact_mobile": row.get("contact_mobile"),
                "transaction_date": row.get("transaction_date"),
                "total": row.get("total"),
                "advance_paid": advance_paid,
                "payment_status": payment_status,
                "remaining_bal": remaining_bal,
                "total_taxes_and_charges": row.get("total_taxes_and_charges"),
                "rounded_total": row.get("rounded_total"),
                "custom_so_from_date": row.get("custom_so_from_date"),
                "custom_so_to_date": custom_so_to_date,
                "status": row.get("status"),
            })

    return processed_data

# ts
# te
