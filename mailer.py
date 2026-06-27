import os
import html
import smtplib
import threading
from email.message import EmailMessage
from email.utils import formataddr
import database

email_user = os.getenv("SMTP_EMAIL")
email_pass = os.getenv("SMTP_PASSWORD")

def send_notification(receiver_email, subject, heading, text_body, link_url=None):
    if not email_user or not email_pass:
        print("SMTP credentials not configured. Skipping notification email.")
        return
        
    try:
        msg = EmailMessage()
        msg["From"] = formataddr(("LostLinks Portal", email_user))
        msg["To"] = receiver_email
        msg["Subject"] = subject
        msg["MIME-Version"] = "1.0"
        
        button_html = ""
        if link_url:
            button_html = f"""
            <div style="margin-top: 24px; text-align: center;">
                <a href="{link_url}" style="background-color: #4f46e5; color: #ffffff; padding: 12px 24px; text-decoration: none; border-radius: 8px; font-weight: bold; display: inline-block;">View in Portal</a>
            </div>
            """
            
        html_content = f"""\
        <!DOCTYPE html>
        <html>
        <head>
            <meta charset="utf-8">
            <style>
                body {{ font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif; line-height: 1.6; color: #334155; margin: 0; padding: 0; background-color: #f8fafc; }}
                .wrapper {{ padding: 24px 12px; background-color: #f8fafc; }}
                .container {{ max-width: 600px; margin: 0 auto; background-color: #ffffff; border: 1px solid #e2e8f0; border-radius: 16px; overflow: hidden; box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.05); }}
                .header {{ background: linear-gradient(135deg, #4f46e5 0%, #7c3aed 100%); padding: 24px; text-align: center; color: #ffffff; }}
                .header h2 {{ margin: 0; font-size: 22px; font-weight: 700; }}
                .content {{ padding: 32px 24px; }}
                .intro {{ font-size: 16px; font-weight: 600; color: #1e293b; margin-top: 0; }}
                .message-box {{ background-color: #f1f5f9; padding: 20px; border-left: 4px solid #6366f1; border-radius: 8px; font-style: italic; color: #475569; margin: 24px 0; font-size: 15px; white-space: pre-wrap; }}
                .footer {{ background-color: #f8fafc; padding: 20px; text-align: center; font-size: 12px; color: #64748b; border-top: 1px solid #e2e8f0; }}
            </style>
        </head>
        <body>
            <div class="wrapper">
                <div class="container">
                    <div class="header">
                        <h2>LostLinks Notification</h2>
                    </div>
                    <div class="content">
                        <p class="intro">{heading}</p>
                        <div class="message-box">{text_body}</div>
                        {button_html}
                    </div>
                    <div class="footer">
                        This is an automated notification from LostLinks Portal. Please do not reply directly to this email.
                    </div>
                </div>
            </div>
        </body>
        </html>
        """
        msg.set_content(text_body)
        msg.add_alternative(html_content, subtype="html")
        
        server = smtplib.SMTP_SSL("smtp.gmail.com", 465, timeout=10)
        server.login(email_user, email_pass)
        server.sendmail(email_user, receiver_email, msg.as_string())
        server.quit()
        print(f"Notification email sent successfully to {receiver_email}")
    except Exception as e:
        print(f"Failed to send notification email to {receiver_email}: {e}")

def send_notification_async(receiver_email, subject, heading, text_body, link_url=None):
    t = threading.Thread(target=send_notification, args=(receiver_email, subject, heading, text_body, link_url))
    t.daemon = True
    t.start()

def send_inquiry(sender_email, receiver_email, subject, message, item_id=None):
    if not email_user or not email_pass:
        raise Exception("SMTP credentials not configured.")
        
    sender_email_esc = html.escape(sender_email)
    message_esc = html.escape(message)
    
    msg = EmailMessage()
    msg["From"] = formataddr(("LostLinks Portal", email_user))
    msg["Reply-To"] = sender_email
    msg["To"] = receiver_email
    msg["Subject"] = subject
    msg["MIME-Version"] = "1.0"
    
    item_html = ""
    item_text = ""
    
    if item_id:
        item = database.get_item_by_id(item_id)
        if item:
            title = html.escape(item.get("title", "N/A"))
            category = html.escape(item.get("category", "N/A"))
            location = html.escape(item.get("location", "N/A"))
            item_type = item.get("type", "lost").upper()
            losttime = item.get("losttime", "N/A")
            if losttime and "T" in losttime:
                losttime = losttime.replace("T", " ")
            losttime = html.escape(losttime)
            
            type_color = "#ef4444" if item.get("type") == "lost" else "#10b981"
            
            photo_url = item.get("photourl")
            photo_html = ""
            if photo_url:
                photo_html = f"""
                <td valign="top" style="width: 120px; padding-right: 20px;">
                    <div style="width: 120px; height: 120px; border-radius: 12px; overflow: hidden; border: 1px solid #cbd5e1;">
                        <img src="{html.escape(photo_url)}" style="width: 100%; height: 100%; object-fit: cover;" alt="Item Photo">
                    </div>
                </td>
                """
            
            item_html = f"""
            <table cellpadding="0" cellspacing="0" border="0" style="width: 100%; background-color: #f8fafc; border: 1px solid #e2e8f0; border-radius: 16px; padding: 16px; margin: 20px 0;">
                <tr>
                    {photo_html}
                    <td valign="top" style="font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif; font-size: 13px; color: #64748b; line-height: 1.5;">
                        <h4 style="margin: 0 0 8px 0; color: #1e293b; font-size: 16px; font-weight: 700;">{title}</h4>
                        <span style="display: inline-block; background-color: {type_color}; color: #ffffff; padding: 2px 8px; border-radius: 9999px; font-size: 10px; font-weight: 800; text-transform: uppercase; margin-bottom: 6px;">{item_type}</span><br>
                        <strong>Category:</strong> {category}<br>
                        <strong>Location:</strong> {location}<br>
                        <strong>Time & Date:</strong> {losttime}
                    </td>
                </tr>
            </table>
            """
            item_text = f"\nListing Details:\n- Title: {title}\n- Category: {category}\n- Location: {location}\n- Type: {item_type}\n- Time: {losttime}\n"

    msg.set_content(f"{message}\n\n{item_text}")
    
    html_content = f"""\
    <!DOCTYPE html>
    <html>
    <head>
        <meta charset="utf-8">
        <style>
            body {{ font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif; line-height: 1.6; color: #334155; margin: 0; padding: 0; background-color: #f8fafc; }}
            .wrapper {{ padding: 24px 12px; background-color: #f8fafc; }}
            .container {{ max-width: 600px; margin: 0 auto; background-color: #ffffff; border: 1px solid #e2e8f0; border-radius: 16px; overflow: hidden; box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.05); }}
            .header {{ background: linear-gradient(135deg, #4f46e5 0%, #7c3aed 100%); padding: 24px; text-align: center; color: #ffffff; }}
            .header h2 {{ margin: 0; font-size: 22px; font-weight: 700; }}
            .content {{ padding: 32px 24px; }}
            .intro {{ font-size: 16px; font-weight: 600; color: #1e293b; margin-top: 0; }}
            .message-box {{ background-color: #f1f5f9; padding: 20px; border-left: 4px solid #6366f1; border-radius: 8px; font-style: italic; color: #475569; margin: 24px 0; font-size: 15px; white-space: pre-wrap; }}
            .footer {{ background-color: #f8fafc; padding: 20px; text-align: center; font-size: 12px; color: #64748b; border-top: 1px solid #e2e8f0; }}
            .accent-text {{ color: #4f46e5; font-weight: 600; }}
        </style>
    </head>
    <body>
        <div class="wrapper">
            <div class="container">
                <div class="header">
                    <h2>LostLinks Portal</h2>
                </div>
                <div class="content">
                    <p class="intro">Hello,</p>
                    <p>You have received a new inquiry from a registered LostLinks user (<span class="accent-text">{sender_email_esc}</span>) regarding your item listing:</p>
                    {item_html}
                    <p><strong>Inquiry Message:</strong></p>
                    <div class="message-box">{message_esc}</div>
                    <p>You can contact the sender directly by replying to this email at <strong class="accent-text">{sender_email_esc}</strong>.</p>
                </div>
                <div class="footer">
                    This is an automated notification from the LostLinks application. Please keep this email chain for references.
                </div>
            </div>
        </div>
    </body>
    </html>
    """
    msg.add_alternative(html_content, subtype="html")
    
    server = smtplib.SMTP_SSL("smtp.gmail.com", 465, timeout=10)
    server.login(email_user, email_pass)
    server.sendmail(email_user, receiver_email, msg.as_string())
    server.quit()
