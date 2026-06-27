import email
import database
from flask import Flask, render_template, request, redirect, url_for, session, flash
from pydantic import ValidationError
import login_data
from datetime import datetime
import re
from cam import upload_photo
from Assistant import app as assistant_app
from langchain_core.messages import HumanMessage
import mailer

app = Flask(__name__, template_folder="templates")
app.secret_key = login_data.super_secret

@app.route('/')
def index():
    if 'user_email' in session:
        return redirect(url_for('dashboard'))
    return render_template('index.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if 'user_email' in session:
        return redirect(url_for('dashboard'))
        
    if request.method == 'POST':
        email = request.form.get('email')
        password = request.form.get('password')
        
        try:
            login_data.loginInput(email=email, password=password)
        except ValidationError as err:
            error_msg = err.errors()[0]['msg']
            if error_msg.startswith("Value error, "):
                error_msg = error_msg[13:]
            flash(error_msg, "error")
            return render_template('login.html')
            
        result = login_data.login(email, password)
        if result and result.get("success"):
            token = result['user']['idToken']
            uid = result['user']['localId']
            
            res = login_data.is_email_verified(token)
            if res.get("success") and not res.get("verified"):
                session['signup_email'] = email
                session['signup_uid'] = uid
                session['signup_token'] = token
                flash("Please verify your email address to continue.", "warning")
                login_data.send_verification_email(token)
                return redirect(url_for('verify_email'))
            
            user = database.get_user(email)  
            if not user:
                session['signup_email'] = email
                session['signup_uid'] = uid
                session['signup_token'] = token
                flash("Please complete your profile details.", "info")
                return redirect(url_for('additional_info'))
            
            if not user.get('verified'):
                try:
                    database.update_user_verification(email, True)
                except Exception as e:
                    print(f"Error syncing user verification flag to Supabase: {e}")

            session['user_email'] = email
            session['user_token'] = token
            flash("Welcome back! Successfully logged in.", "success")
            return redirect(url_for('dashboard'))
        else:
            error_msg = result.get("error", "Invalid credentials.") if result else "Invalid credentials."
            if "INVALID_LOGIN_CREDENTIALS" in error_msg:
                flash("Invalid EMAIL or PASSWORD. Try again!", "error")
            elif "USER_DISABLED" in error_msg:
                flash("This account has been disabled.", "error")
            else:
                flash(f"Login failed: {error_msg}", "error")
                
    return render_template('login.html')

@app.route('/signup', methods=['GET', 'POST'])
def signup():
    if 'user_email' in session:
        return redirect(url_for('dashboard'))
        
    if request.method == 'POST':
        email = request.form.get('email')
        password = request.form.get('password')
        confirm_password = request.form.get('confirm_password')
        
        try:
            login_data.signupInput(email=email, password=password, confirm_password=confirm_password)
        except ValidationError as err:
            error_msg = err.errors()[0]['msg']
            if error_msg.startswith("Value error, "):
                error_msg = error_msg[13:]
            flash(error_msg, "error")
            return render_template('signup.html')
            
        result = login_data.signup(email, password)
        if result and result.get("success"):
            session['signup_email'] = email
            session['signup_uid'] = result['user']['localId']
            session['signup_token'] = result['user']['idToken']
            flash("Account created, Need to complete profile! Please complete your profile to continue.", "success")
            return redirect(url_for('additional_info'))
        else:
            error_msg = result.get("error", "") if result else ""
            if "EMAIL_EXISTS" in error_msg:
                flash("This email is already registered. Please login.", "error")
            elif "INVALID_EMAIL" in error_msg:
                flash("Please enter a valid email address.", "error")
            else:
                flash(f"Signup failed: {error_msg}", "error")
                
    return render_template('signup.html')

@app.route('/additional-info', methods=['GET', 'POST'])
def additional_info():
    if 'signup_email' not in session or 'signup_uid' not in session:
        return redirect(url_for('signup'))
        
    if request.method == 'POST':
        display_name = request.form.get('displayName')
        contact_number = request.form.get('contactNumber')
        
        if not display_name or not display_name.strip():
            flash("Display name is required.", "error")
            return render_template('additional_info.html')
        
        if "admin" in display_name.lower():
            flash("Admin and all his relatives are registered! Please come with your real ID", "error")
            return redirect(url_for('additional_info'))
            
        email = session['signup_email']
        uid = session['signup_uid']
        token = session.get('signup_token')
        
        try:
            res = login_data.is_email_verified(token)
            if res.get("success") and res.get("verified"):
                database.create_user(
                    firebase_uid=uid,
                    email=email,
                    display_name=display_name.strip(),
                    contact_number=contact_number.strip() if contact_number else None,
                    verified_email=True
                )
                session['user_email'] = email
                session['user_token'] = token
                
                session.pop('signup_email', None)
                session.pop('signup_uid', None)
                session.pop('signup_token', None)
                session.pop('signup_display_name', None)
                session.pop('signup_contact_number', None)
                
                flash("Profile setup complete! Welcome aboard.", "success")
                return redirect(url_for('dashboard'))
            else:
                database.create_user(
                    firebase_uid=uid,
                    email=email,
                    display_name=display_name.strip(),
                    contact_number=contact_number.strip() if contact_number else None,
                    verified_email=False
                )
                
                res_send = login_data.send_verification_email(token)
                if not res_send.get("success"):
                    flash(f"Failed to send verification email: {res_send.get('error')}", "warning")
                else:
                    flash("Verification email sent! Please verify your email to complete registration.", "info")
                return redirect(url_for('verify_email'))
                
        except Exception as e:
            flash(f"Error saving profile details: {str(e)}", "error")
            return render_template('additional_info.html')
            
    return render_template('additional_info.html')

@app.route('/verify-email', methods=['GET', 'POST'])
def verify_email():
    if 'signup_email' not in session or 'signup_token' not in session:
        return redirect(url_for('login'))
        
    email = session['signup_email']
    token = session['signup_token']
    
    if request.method == 'POST':
        action = request.form.get('action')
        
        if action == 'resend':
            res = login_data.send_verification_email(token)
            if res.get("success"):
                flash("Verification email resent. Please check your inbox.", "success")
            else:
                flash(f"Failed to send verification email: {res.get('error')}", "error")
                
        elif action == 'check':
            res = login_data.is_email_verified(token)
            if res.get("success"):
                if res.get("verified"):
                    user = database.get_user(email)
                    if user:
                        try:
                            database.update_user_verification(email, True)
                        except Exception as e:
                            flash(f"Error updating verification status in database: {str(e)}", "error")
                            return render_template('verify_email.html', email=email)
                    else:
                        flash("Email verified successfully! Now complete your profile details.", "success")
                        return redirect(url_for('additional_info'))

                    session['user_email'] = email
                    session['user_token'] = token
                    
                    session.pop('signup_email', None)
                    session.pop('signup_uid', None)
                    session.pop('signup_token', None)
                    session.pop('signup_display_name', None)
                    session.pop('signup_contact_number', None)
                    
                    flash("Email verified successfully! Welcome aboard.", "success")
                    return redirect(url_for('dashboard'))
                else:
                    flash("Your email is not verified yet. Please check your inbox and click the link.", "error")
            else:
                flash(f"Error checking verification status: {res.get('error')}", "error")
                
        elif action == 'revoke':
            res = login_data.delete_account(token)
            if res.get("success"):
                session.pop('signup_email', None)
                session.pop('signup_uid', None)
                session.pop('signup_token', None)
                session.pop('signup_display_name', None)
                session.pop('signup_contact_number', None)
                flash("Registration cancelled. Your unverified account was removed.", "info")
                return redirect(url_for('signup'))
            else:
                flash(f"Failed to cancel registration: {res.get('error')}", "error")
                
    return render_template('verify_email.html', email=email)


@app.route('/forgot-password', methods=['GET', 'POST'])
def forgot_password():
    if request.method == 'POST':
        email = request.form.get('email')
        
        try:
            login_data.forgetPasswordInput(email=email)
        except ValidationError as err:
            error_msg = err.errors()[0]['msg']
            if error_msg.startswith("Value error, "):
                error_msg = error_msg[13:]
            flash(error_msg, "error")
            return render_template('forgot-password.html')
            
        result = login_data.forget_password(email)
        if result and result.get("success"):
            flash("Password reset link sent to your email.", "success")
            return redirect(url_for('login'))
        else:
            error_msg = result.get("error", "") if result else ""
            if "EMAIL_NOT_FOUND" in error_msg:
                flash("No account found with that email address.", "error")
            else:
                flash(f"Reset failed: {error_msg}", "error")
                
    return render_template('forgot-password.html')

@app.route('/dashboard')
def dashboard():
    if 'user_email' not in session:
        flash("Please log in to access the dashboard.", "error")
        return redirect(url_for('login'))

    user = database.get_user(session['user_email'])

    lost_entries = database.get_lost_entries()
    found_entries = database.get_found_entries()

    lost_unresolved_entries = []
    lost_resolved_entries = []

    found_unresolved_entries = []
    found_resolved_entries = []

    for entry in lost_entries:
        if entry['status'] == 'active':
            lost_unresolved_entries.append(entry)
        else:
            lost_resolved_entries.append(entry)

    for entry in found_entries:
        if entry['status'] == 'active':
            found_unresolved_entries.append(entry)
        else:
            found_resolved_entries.append(entry)

    return render_template('dashboard.html', email=session['user_email'], user =user, 
                        lost_unresolved_entries = lost_unresolved_entries,
                        lost_resolved_entries = lost_resolved_entries,
                        found_unresolved_entries = found_unresolved_entries,
                        found_resolved_entries = found_resolved_entries)

@app.route('/profile')
def profile():
    if 'user_email' not in session:
        flash("Please log in to access the profile.", "error")
        return redirect(url_for('login'))
    
    user_email = session['user_email']
    user = database.get_user(user_email)
    
    try:
        user_lost_entries = database.get_lost_entries_by_user(user_email)
    except Exception as e:
        print(f"Error fetching user's reported lost items: {e}")
        user_lost_entries = []

    try:
        user_found_entries = database.get_found_entries_by_user(user_email)
    except Exception as e:
        print(f"Error fetching user's reported found items: {e}")
        user_found_entries = []
        
    return render_template('profile.html', email=user_email, user=user, user_lost_entries=user_lost_entries, user_found_entries=user_found_entries)

@app.route('/update-profile', methods=["GET", "POST"])
def update_profile():
    if 'user_email' not in session:
        flash("Please log in to access the profile.", "error")
        return redirect(url_for('login'))
    user = database.get_user(session['user_email'])

    if request.method == 'POST':
        display_name = request.form.get('displayName')
        contact_number = request.form.get('contactNumber')
        
        if not display_name or not display_name.strip():
            flash("Display name is required.", "error")
            return render_template('update_profile.html', email=session['user_email'], user=user)
        
        try:
            database.update_user(
                email=session['user_email'],
                display_name=display_name.strip() if display_name else user['displayName'],
                contact_number=contact_number.strip() if contact_number else user['contactNumber']
            )
            flash("Profile updated successfully!", "success")
            return redirect(url_for('profile'))
        except Exception as e:
            flash(f"Error updating profile details to SQL database: {str(e)}", "error")
            return render_template('update_profile.html', email=session['user_email'], user=user)
            
    return render_template('update_profile.html', email=session['user_email'], user=user)

@app.route('/logout')
def logout():
    login_data.logout()
    session.clear()
    flash("Successfully logged out.", "success")
    return redirect(url_for('login'))

@app.route('/report-lost', methods=['GET', 'POST'])
def report_lost():
    if 'user_email' not in session:
        flash("Please log in to access the lost report.", "error")
        return redirect(url_for('login'))

    user_email = session['user_email']
    try:
        user_lost_entries = database.get_lost_entries_by_user(user_email)
    except Exception as e:
        print(f"Error fetching user's reported lost items: {e}")
        user_lost_entries = []

    if request.method == 'POST':
        title = request.form.get('title')
        category = request.form.get('category')
        location = request.form.get('location')
        description = request.form.get('description')
        losttime = request.form.get('lost-time')

        photo_file = request.files.get('photo')
        photo_base64 = request.form.get('photoBase64')

        if not title or not title.strip():
            flash("Title is required.", "error")
            return render_template('report-lost.html', email=user_email, user_lost_entries=user_lost_entries)
        
        if not description or not description.strip():
            flash("Description is required.", "error")
            return render_template('report-lost.html', email=user_email, user_lost_entries=user_lost_entries)

        if not category or not category.strip():
            flash("Category is required.", "error")
            return render_template('report-lost.html', email=user_email, user_lost_entries=user_lost_entries)
        
        try:
            selected_time = datetime.fromisoformat(losttime)

            if selected_time > datetime.now():
                flash("Date and time cannot be in the future.", "error")
                return render_template(
                    'report-lost.html',
                    email=user_email,
                    user_lost_entries=user_lost_entries
                )

        except (ValueError, TypeError):
            flash("Invalid date and time.", "error")
            return render_template(
                'report-lost.html',
                email=user_email,
                user_lost_entries=user_lost_entries
            )

        try:
            photo_url = upload_photo(photo_file, photo_base64)

            item = {
                "reporterid" : user_email,
                "type" : "lost",
                "title" : title.strip(),
                "category" : category,
                "location" : location.strip() or None,
                "description" : description.strip(),
                "photourl" : photo_url or None,
                "losttime" : losttime or None,
            }
            database.create_lost_entry(item)
            flash("Lost item reported successfully!", "success")
            return redirect(url_for('dashboard'))
        except Exception as e:
            flash(f"Error reporting lost item to SQL database: {str(e)}", "error")
            return render_template('report-lost.html', email=user_email, user_lost_entries=user_lost_entries)
    
    return render_template('report-lost.html', email=user_email, user_lost_entries=user_lost_entries)

@app.route('/report-found', methods=['GET', 'POST'])
def report_found():
    if 'user_email' not in session:
        flash("Please log in to access the found report.", "error")
        return redirect(url_for('login'))

    user_email = session['user_email']
    try:
        user_found_entries = database.get_found_entries_by_user(user_email)
    except Exception as e:
        print(f"Error fetching user's reported found items: {e}")
        user_found_entries = []

    if request.method == 'POST':
        title = request.form.get('title')
        category = request.form.get('category')
        location = request.form.get('location')
        description = request.form.get('description')
        losttime = request.form.get('lost-time')

        photo_file = request.files.get('photo')
        photo_base64 = request.form.get('photoBase64')

        has_file = photo_file and photo_file.filename != ""
        has_camera = photo_base64 and photo_base64.strip() != ""

        if not has_file and not has_camera:
            flash("Please upload a photo or capture one using the camera.", "error")
            return render_template(
                'report-found.html',
                email=user_email,
                user_found_entries=user_found_entries
    )

        if not title or not title.strip():
            flash("Title is required.", "error")
            return render_template('report-found.html', email=user_email, user_found_entries=user_found_entries)

        if not location or not location.strip():
            flash("Location is required.", "error")
            return render_template('report-found.html', email=user_email, user_found_entries=user_found_entries)
        
        if not description or not description.strip():
            flash("Description is required.", "error")
            return render_template('report-found.html', email=user_email, user_found_entries=user_found_entries)

        if not category or not category.strip():
            flash("Category is required.", "error")
            return render_template('report-found.html', email=user_email, user_found_entries=user_found_entries)
        
        if not losttime or not losttime.strip():
            flash("Lost time is required.", "error")
            return render_template('report-found.html', email=user_email, user_found_entries=user_found_entries)
        
        try:
            selected_time = datetime.fromisoformat(losttime)

            if selected_time > datetime.now():
                flash("Date and time cannot be in the future.", "error")
                return render_template(
                    'report-found.html',
                    email=user_email,
                    user_found_entries=user_found_entries
                )

        except (ValueError, TypeError):
            flash("Invalid date and time.", "error")
            return render_template(
                'report-found.html',
                email=user_email,
                user_found_entries=user_found_entries
            )

        try:
            photo_url = upload_photo(photo_file, photo_base64)
            if not photo_url:
                flash("Failed to upload the photo to storage. Please try again.", "error")
                return render_template('report-found.html', email=user_email, user_found_entries=user_found_entries)

            item = {
                "reporterid" : user_email,
                "type" : "found",
                "title" : title.strip(),
                "category" : category,
                "location" : location.strip(),
                "description" : description.strip(),
                "losttime" : losttime,
                "photourl" : photo_url
            }
            database.create_found_entry(item)
            flash("Found item reported successfully!", "success")
            return redirect(url_for('dashboard'))
        except Exception as e:
            flash(f"Error reporting found item to SQL database: {str(e)}", "error")
            return render_template('report-found.html', email=user_email, user_found_entries=user_found_entries)
    
    return render_template('report-found.html', email=user_email, user_found_entries=user_found_entries)

@app.route('/resolve-item/<item_id>', methods=['POST'])
def resolve_item(item_id):
    if 'user_email' not in session:
        flash("Please log in to resolve items.", "error")
        return redirect(url_for('login'))
    
    resolved_to = request.form.get("resolved_to")
    item = database.get_item_by_id(item_id)
    if not item:
        flash("Item not found.", "error")
        return redirect(request.referrer or url_for('dashboard'))
        
    if not resolved_to:
        flash("Please select a claimant to resolve the item to.", "error")
        return redirect(request.referrer or url_for('dashboard'))
        
    try:
        database.resolve_claim(session['user_email'], item_id, resolved_to)
        flash(f"Item resolved and successfully handed over to {resolved_to}!", "success")
        item_title = item.get("title", "your item")
        subject = f"Listing Resolved: {item_title}"
        heading = f"Good news! The listing for '{item_title}' has been resolved to you!"
        text_body = f"The reporter ({session['user_email']}) has marked the item as successfully resolved/handed over to you.\n\nThank you for using LostLinks!"
        link_url = request.host_url + f"chat/{item_id}"
            
        mailer.send_notification_async(resolved_to, subject, heading, text_body, link_url)
    except Exception as e:
        flash(f"Error resolving report: {str(e)}", "error")
        
    return redirect(request.referrer or url_for('dashboard'))

@app.route('/delete-item/<item_id>', methods=['POST'])
def delete_item(item_id):
    if 'user_email' not in session:
        flash("Please log in to delete items.", "error")
        return redirect(url_for('login'))
        
    item = database.get_item_by_id(item_id)
    if not item:
        flash("Item not found.", "error")
        return redirect(request.referrer or url_for('dashboard'))
        
    if item.get('reporterid') != session['user_email']:
        flash("You do not have permission to delete this item.", "error")
        return redirect(request.referrer or url_for('dashboard'))

    try:
        database.delete_entry(item_id, session['user_email'])
        flash("Item deleted successfully!", "success")
    except Exception as e:
        flash(f"Error deleting item: {str(e)}", "error")
    return redirect(request.referrer or url_for('dashboard'))

@app.route('/update-item/<item_id>', methods=['GET', 'POST'])
def update_item(item_id):
    if 'user_email' not in session:
        flash("Please log in to update items.", "error")
        return redirect(url_for('login'))

    item = database.get_item_by_id(item_id)
    if not item:
        flash("Item not found.", "error")
        return redirect(url_for('dashboard'))

    if item.get('reporterid') != session['user_email']:
        flash("You do not have permission to update this item.", "error")
        return redirect(url_for('dashboard'))

    if request.method == 'POST':
        title = request.form.get('title')
        category = request.form.get('category')
        location = request.form.get('location')
        description = request.form.get('description')
        losttime = request.form.get('lost-time')

        photo_file = request.files.get('photo')
        photo_base64 = request.form.get('photoBase64')
        photo_url = None
        if (photo_file and photo_file.filename != "") or (photo_base64 and photo_base64.strip() != ""):
            photo_url = upload_photo(photo_file, photo_base64)

        title = title.strip() if title and title.strip() else item.get('title')
        category = category if category and category.strip() else item.get('category')
        location = location.strip() if location and location.strip() else item.get('location')
        description = description.strip() if description and description.strip() else item.get('description')
        losttime = losttime if losttime and losttime.strip() else item.get('losttime')

        try:
            database.update_item_entry(
                item_id=item_id,
                email=session['user_email'],
                title=title,
                category=category,
                location=location,
                description=description,
                losttime=losttime,
                photourl=photo_url
            )
            flash("Item updated successfully!", "success")
            if item.get('type') == 'found':
                return redirect(url_for('report_found'))
            else:
                return redirect(url_for('report_lost'))
        except Exception as e:
            flash(f"Error updating item: {str(e)}", "error")
            return render_template('update_item.html', item=item)

    return render_template('update_item.html', item=item)

@app.route('/chat/<item_id>', methods=['GET'])
def chat(item_id):
    if 'user_email' not in session:
        return redirect(url_for('login'))
    user_email = session['user_email']
    item = database.get_item_by_id(item_id)
    if not item:
        flash("Item not found.", "error")
        return redirect(url_for('dashboard'))
    
    claims = item.get('claimsmade')
    if not claims:
        item['claimsmade'] = []
    elif isinstance(claims, str):
        item['claimsmade'] = [claims]
    elif not isinstance(claims, list):
        item['claimsmade'] = list(claims)
        
    messages = database.load_chat(item_id)
    return render_template('chat.html', email=user_email, item=item, messages=messages)

@app.route('/send-chat', methods=['POST'])
def send_chat():
    if 'user_email' not in session:
        return redirect(url_for('login'))
    
    item_id = request.form.get('item_id')
    message = request.form.get('message')

    item = database.get_item_by_id(item_id)
    if not item:
        flash("Item not found.", "error")
        return redirect(url_for('dashboard'))
        
    if item.get("status") == "resolved":
        flash("This item has been resolved. You cannot chat anymore.", "error")
        return redirect(url_for('chat', item_id=item_id))

    queryowner = database.get_reporter_id(item_id)
    sender = session['user_email']
    
    if item_id and message and message.strip():
        database.save_chat({
            "itemid": item_id,
            "sender": sender,
            "receiver": queryowner if queryowner else "public",
            "message": message.strip()
        })
        
        item_title = item.get("title", "your item")
        subject = f"New Discussion Message: {item_title}"
        heading = f"New message in discussion for '{item_title}'"
        text_body = f"{sender} wrote:\n\"{message.strip()}\""
        link_url = request.host_url + f"chat/{item_id}"
        
        if sender != queryowner:
            if queryowner:
                mailer.send_notification_async(queryowner, subject, heading, text_body, link_url)
        else:
            try:
                chat_history = database.load_chat(item_id)
                claimants = item.get("claimsmade") or []
                if isinstance(claimants, str):
                    claimants = [claimants]
                    
                recipients = set(claimants)
                for msg in chat_history:
                    if msg.get("sender") and msg.get("sender") != queryowner:
                        recipients.add(msg.get("sender"))
                        
                for recipient in recipients:
                    mailer.send_notification_async(recipient, subject, heading, text_body, link_url)
            except Exception as ex:
                print(f"Error resolving chat notification recipients: {ex}")
        
    return redirect(url_for('chat', item_id=item_id))

def format_assistant_message(text):
    if not text:
        return ""
    # Escape HTML to prevent injection while maintaining styling tags
    html = text.replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;')
    
    # 1. Parse Markdown Tables
    table_pattern = r'((?:\|[^\n]*\|(?:\n|$))+)'
    def table_repl(match):
        lines = match.group(1).strip().split('\n')
        if len(lines) < 2:
            return match.group(1)
        
        table_html = '<div class="overflow-x-auto my-3 border border-slate-200 rounded-xl bg-white shadow-sm"><table class="min-w-full divide-y divide-slate-200 text-xs">'
        has_header = False
        
        headers = []
        for line in lines:
            if re.match(r'^[|\s:-]+$', line.replace('|', '').strip()):
                continue
            cells = [c.strip() for c in line.split('|') if c.strip() != '']
            if not cells:
                continue
            
            if not has_header:
                table_html += '<thead class="bg-slate-50"><tr>'
                for cell in cells:
                    table_html += f'<th class="px-3 py-2 text-left font-semibold text-slate-700 uppercase tracking-wider">{cell}</th>'
                    headers.append(cell.lower().replace(" ", "").replace("_", ""))
                table_html += '</tr></thead><tbody class="divide-y divide-slate-100 bg-white">'
                has_header = True
            else:
                table_html += '<tr class="hover:bg-slate-50/50 transition-colors">'
                for idx, cell in enumerate(cells):
                    cell_content = cell
                    
                    # 1. Parse datetime values (e.g. 2026-06-12T22:00)
                    dt_match = re.match(r'^(\d{4})-(\d{2})-(\d{2})[T ](\d{2}):(\d{2})(?::(\d{2}))?$', cell)
                    if dt_match:
                        try:
                            val = cell.replace('T', ' ')
                            if len(val) > 16:
                                dt = datetime.strptime(val[:19], '%Y-%m-%d %H:%M:%S')
                            else:
                                dt = datetime.strptime(val, '%Y-%m-%d %H:%M')
                            cell_content = dt.strftime('%b %d, %Y - %I:%M %p')
                        except Exception:
                            pass
                    
                    else:
                        # 2. Check for statuses only in status/type columns OR if the cell matches exactly
                        is_status_col = idx < len(headers) and any(x in headers[idx] for x in ['status', 'type', 'stat'])
                        cell_lower = cell.strip().lower()
                        if is_status_col or cell_lower in ['lost', 'found', 'resolved']:
                            if 'lost' in cell_lower:
                                cell_content = f'<span class="inline-flex items-center px-2.5 py-0.5 rounded-full text-[10px] font-semibold bg-rose-50 text-rose-700 border border-rose-100">🔴 Lost</span>'
                            elif 'found' in cell_lower:
                                cell_content = f'<span class="inline-flex items-center px-2.5 py-0.5 rounded-full text-[10px] font-semibold bg-emerald-50 text-emerald-700 border border-emerald-100">🟢 Found</span>'
                            elif 'resolved' in cell_lower:
                                cell_content = f'<span class="inline-flex items-center px-2.5 py-0.5 rounded-full text-[10px] font-semibold bg-slate-100 text-slate-700 border border-slate-200">✅ Resolved</span>'
                    
                    table_html += f'<td class="px-3 py-2 text-slate-600 font-medium whitespace-nowrap">{cell_content}</td>'
                table_html += '</tr>'
        if has_header:
            table_html += '</tbody>'
        table_html += '</table></div>'
        return table_html
        
    html = re.sub(table_pattern, table_repl, html)
    
    # 2. Parse Bold (**text**)
    html = re.sub(r'\*\*([^*]+)\*\*', r'<strong>\1</strong>', html)
    
    # 3. Parse Links ([text](url))
    html = re.sub(r'\[([^\]]+)\]\(([^)]+)\)', r'<a href="\2" class="text-indigo-600 hover:text-indigo-800 font-semibold underline decoration-2 transition">\1</a>', html)
    
    # 4. Convert escaped HTML links (e.g. &lt;a href="/chat/..."&gt;text&lt;/a&gt;) back to styled HTML anchors
    html = re.sub(
        r'&lt;a\s+href="([^"]+)"&gt;((?:(?!&lt;).)*)&lt;/a&gt;',
        r'<a href="\1" class="text-indigo-600 hover:text-indigo-800 font-semibold underline decoration-2 transition">\2</a>',
        html
    )
    
    # 5. Parse Bullet Lists
    list_pattern = r'((?:^[ \t]*[-*+]\s+[^\n]*(?:\n|$))+)'
    def list_repl(match):
        list_html = '<ul class="list-disc pl-5 my-3 space-y-1.5 text-slate-600 font-medium">'
        items = match.group(1).strip().split('\n')
        for item in items:
            content = re.sub(r'^\s*[-*+]\s+', '', item)
            list_html += f'<li>{content}</li>'
        list_html += '</ul>'
        return list_html
        
    html = re.sub(list_pattern, list_repl, html, flags=re.MULTILINE)
    
    # 6. Parse Linebreaks
    html = html.replace('\n', '<br>')
    return html

@app.template_filter('markdown_format')
def markdown_format_filter(text):
    return format_assistant_message(text)

@app.route("/assistant_page", methods=["GET", "POST"])
def assistant_page():
    if 'user_email' not in session:
        flash("Please log in to access the AI assistant.", "error")
        return redirect(url_for('login'))
    
    email = session['user_email']

    if request.method == 'POST':
        message = request.form.get('message', '').strip()
        photo_file = request.files.get('photo')
        
        photo_url = None
        if photo_file and photo_file.filename != "":
            try:
                photo_url = upload_photo(photo_file, None)
            except Exception as e:
                print(f"Error uploading assistant attachment: {e}")

        if message or photo_url:
            agent_msg_content = message
            display_message = message

            if photo_url:
                if agent_msg_content:
                    agent_msg_content += f"\n\n[Attached Image: {photo_url}]"
                else:
                    agent_msg_content = f"[Attached Image: {photo_url}]"
                
                if display_message:
                    display_message += f"\n\n[Attached Image]({photo_url})"
                else:
                    display_message = f"[Attached Image]({photo_url})"

            database.save_assistant_query(email, "user", display_message)

            response_text =""
            try:
                config = {"configurable": {"thread_id": email}}
                result = assistant_app.invoke({"messages": [HumanMessage(content=agent_msg_content)]}, config=config)
                response_text = result["messages"][-1].content
            except Exception as e:
                print(f"Error invoking AI assistant: {e}")
                err_msg = str(e).lower()
                if any(x in err_msg for x in ["429", "rate_limit", "rate limit", "tpm", "rpm", "limit exceeded", "exhausted"]):
                    response_text = "⚠️ **Rate Limit Exceeded:** The AI assistant is currently receiving too many requests (TPM/RPM exceeded). Please wait a few seconds and try again."
                else:
                    response_text = f"Sorry, I am facing an issue processing your request right now. (Error: {str(e)})"
            database.save_assistant_query(email, "assistant", response_text)
        return redirect(url_for('assistant_page', active=1))
    show_history = (request.args.get('active') == '1') or (request.args.get('show_history') == 'true')

    try:
        history = database.get_assistant_history(email)
    except Exception as e:
        print(f"Error loading assistant history: {e}")
        history = []
        
    try:
        all_entries = database.get_entries()
        active_items = [item for item in all_entries if item.get('status') == 'active']
    except Exception as e:
        print(f"Error fetching active items for map: {e}")
        active_items = []
        
    return render_template("assistant.html", email=email, history=history, show_history=show_history, active_items=active_items)

#====>
@app.route('/claim_item', methods=['POST'])
def claim_item():
    if 'user_email' not in session:
        flash("Please log in to claim items.", "error")
        return redirect(url_for('login'))
    
    email = session["user_email"]
    item_id = request.form.get("item_id")
    
    if not item_id:
        flash("Item ID is missing.", "error")
        return redirect(url_for("dashboard"))
    
    item = database.get_item_by_id(item_id)
    if not item:
        flash("Item not found.", "error")
        return redirect(url_for("dashboard"))
    
    if item.get("status") == "resolved":
        flash("Item already resolved.", "error")
        return redirect(url_for("chat", item_id=item_id))

    if item.get("reporterid") == email:
        flash("You cannot claim your own item.", "error")
        return redirect(url_for("chat", item_id=item_id))

    try:
        database.make_claim(email, item_id)
        flash("Claim has been made for item successfully.", "success")
        
        reporter_email = item.get("reporterid")
        if reporter_email:
            item_title = item.get("title", "your item")
            item_type = item.get("type", "lost")
            claim_type = "claimed they found a matching item" if item_type == "lost" else "claimed this item belongs to them"
            
            subject = f"New Claim Notification: {item_title}"
            heading = f"Your reported item '{item_title}' has a new claim!"
            text_body = f"User {email} has {claim_type}.\n\nPlease check the discussion board to coordinate and verify their claim."
            link_url = request.host_url + f"chat/{item_id}"
            
            mailer.send_notification_async(reporter_email, subject, heading, text_body, link_url)
    except Exception as e:
        flash(f"Error making claim: {str(e)}", "error")
        
    return redirect(url_for("chat", item_id=item_id))



@app.route("/send_email", methods=["POST"])
def send_email():
    if "user_email" not in session:
        flash("Please log in to send email.", "error")
        return redirect(url_for('login'))
    sender_email = session["user_email"]
    receiver_email = request.form.get("email-to")
    subject = request.form.get("email-subject")
    message = request.form.get("email-body")
    item_id = request.form.get("item_id")
    
    if not receiver_email or not subject or not message:
        flash("All email fields are required.", "error")
        return redirect(request.referrer or url_for("dashboard"))
        
    try:
        mailer.send_inquiry(sender_email, receiver_email, subject, message, item_id)
        flash(f"Email sent successfully to {receiver_email}!", "success")
    except Exception as e:
        print(f"Error sending SMTP email: {e}")
        flash(f"Email Error: {e}", "error")
        
    return redirect(request.referrer or url_for("dashboard"))

if __name__ == '__main__':
    database.init_db()
    app.run(debug=True, port=5000)
