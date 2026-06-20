from json import decoder
from flask import Flask, render_template, request, redirect, url_for, session, flash
from pydantic import ValidationError
import login_data
import database
from cam import upload_photo

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
    user = database.get_user(session['user_email'])
    return render_template('profile.html', email=session['user_email'], user=user)

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
            return render_template('update_profile.html')
        
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

        if not location or not location.strip():
            flash("Location is required.", "error")
            return render_template('report-lost.html', email=user_email, user_lost_entries=user_lost_entries)
        
        if not description or not description.strip():
            flash("Description is required.", "error")
            return render_template('report-lost.html', email=user_email, user_lost_entries=user_lost_entries)

        if not category or not category.strip():
            flash("Category is required.", "error")
            return render_template('report-lost.html', email=user_email, user_lost_entries=user_lost_entries)

        try:
            photo_url = upload_photo(photo_file, photo_base64)

            item = {
                "reporterid" : user_email,
                "type" : "lost",
                "title" : title.strip(),
                "category" : category,
                "location" : location.strip(),
                "description" : description.strip(),
                "photourl" : photo_url,
                "losttime" : losttime,
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

        try:
            photo_url = upload_photo(photo_file, photo_base64)

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
    
    try:
        database.resolve_entry(item_id, session['user_email'])
        flash("Report marked as resolved successfully!", "success")
    except Exception as e:
        flash(f"Error resolving report: {str(e)}", "error")
        
    return redirect(request.referrer or url_for('dashboard'))

@app.route('/delete-item/<item_id>', methods=['POST'])
def delete_item(item_id):
    if 'user_email' not in session:
        flash("Please log in to delete items.", "error")
        return redirect(url_for('login'))
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
    messages = database.load_chat(item_id)
    return render_template('chat.html', email=user_email, item=item, messages=messages)

@app.route('/send-chat', methods=['POST'])
def send_chat():
    if 'user_email' not in session:
        return redirect(url_for('login'))
    
    item_id = request.form.get('item_id')
    message = request.form.get('message')

    queryowner = database.get_reporter_id(item_id)
    
    if item_id and message and message.strip():
        database.save_chat({
            "itemid": item_id,
            "sender": session['user_email'],
            "receiver": queryowner if queryowner else "public",
            "message": message.strip()
        })
        
    return redirect(url_for('chat', item_id=item_id))

if __name__ == '__main__':
    database.init_db()
    app.run(debug=True, port=5000)