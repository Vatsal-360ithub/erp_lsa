import frappe
import requests
from frappe import _
# from frappe.utils import today
# from datetime import datetime,timedelta,time
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.mime.base import MIMEBase
from email import encoders


@frappe.whitelist()
def single_mail(email_account,recipients,subject,html_message,cc_email=None):
    # recipients = ["vatsal.k@360ithub.com"]
    email_account = frappe.get_doc("Email Account", email_account)
    sender_email = email_account.email_id
    sender_password = email_account.get_password()
    

    message = MIMEMultipart()
    message['From'] = sender_email
    message['To'] = ",".join(recipients)
    if cc_email:  # Add CC if provided
        #cc_email.append("vatsal.k@360ithub.com")
        message['Cc'] = ",".join(cc_email)
        # print(",".join(cc_email))
    message['Subject'] = subject
    message.attach(MIMEText(html_message, 'html'))


    # Connect to the SMTP server and send the email
    smtp_server = 'smtp-mail.outlook.com'
    # smtp_server = "smtp.gmail.com"
    smtp_port = 587
    with smtplib.SMTP(smtp_server, smtp_port) as server:
        server.starttls()
        server.login(sender_email, sender_password)
        try:
            # Send email
            recipients_all = recipients + (cc_email if cc_email else [])
            resp=server.sendmail(sender_email, recipients_all , message.as_string())
            # print("Mail sent successfully!")
            # print(",".join(recipients))
            # print(resp)
            # print(sender_email,sender_password)
            return {"status":True,"msg": "Mail sent successfully!"}
        except Exception as er:
            # print(f"Failed to send email. Error: {er}")
            return {"status":False,"msg": f"Failed to send notification:{er}"}



def create_smtp_server(email_account):
    try:
        """Create and return an SMTP server instance."""
        email_account_doc = frappe.get_doc("Email Account", email_account)
        # sender_email = email_account_doc.email_id
        # sender_password = email_account_doc.get_password()

        sender_email = "mohan360ithub@gmail.com"
        sender_password = "dbor izwx rmny ydmh"

        # smtp_server = smtplib.SMTP('smtp-mail.outlook.com', 587)
        smtp_server = smtplib.SMTP('smtp.gmail.com', 587)
        smtp_server.starttls()  # Secure the connection
        smtp_server.login(sender_email, sender_password)

        print("smtp server startedddddddddddddddddddddddddddddddddddddddddddddddd")
        
        return {"status":True,"smtp_server":smtp_server, "sender_email":sender_email}
    except Exception as e:
        print(f"FFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFailed to create SMTP server. Error: {e}")
        return {"status":False,"msg":f"Error creating mail server: {e}"}

def terminate_smtp_server(smtp_server):
    """Terminate the SMTP server."""
    smtp_server.quit()

def single_mail_with_attachment_with_server(smtp_server, sender_email, recipients, subject, html_message,pdf_link,pdf_filename, cc_email=None):
    """Send an email using the provided SMTP server."""
    # Ensure recipients and cc_email are lists
    
    try:
        # if isinstance(recipients, str):
        #     recipients = [recipients]
        # if cc_email and isinstance(cc_email, str):
        #     cc_email = [cc_email]

        message = MIMEMultipart()
        message['From'] = sender_email
        message['To'] = recipients
        if cc_email: 
            message['Cc'] = cc_email
        message['Subject'] = subject
        message.attach(MIMEText(html_message, 'html'))

        recipients_all = recipients + ","+(cc_email if cc_email else "")

        # Attach the PDF file

        attachment = get_file_from_link(pdf_link)
        if attachment:
            part = MIMEBase("application", "octet-stream")
            part.set_payload(attachment)
            encoders.encode_base64(part)
            part.add_header(
                "Content-Disposition",
                f"attachment; filename= {pdf_filename}",
            )
            message.attach(part)
            
            # Send email
            response=smtp_server.sendmail(sender_email, recipients_all.split(','), message.as_string())
            return {"status":True,"msg":"Email sent successfully!"}
        else:
            return {"status": False, "msg": "Failed to download PDF file"}
    except Exception as e:
        return {"status": False, "msg": f"Failed to send email. Error: {e}"}





def get_file_from_link(link):
    try:
        response = requests.get(link)
        if response.status_code == 200:
            return response.content
        else:
            # print(f"Failed to fetch file from link. Status code: {response.status_code}")
            return None
    except Exception as e:
        # print(f"Error fetching file from link: {e}")
        frappe.log_error(f"An error occurred in fetching file from Link: {e}")
        return None
   