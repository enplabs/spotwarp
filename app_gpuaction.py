import os
import sqlite3
import requests
import json
from datetime import datetime
from flask import Flask, render_template, request, redirect, session, jsonify, send_from_directory
from dotenv import load_dotenv
import resend

# Load env variables (port config, telegram tokens, admin passwords)
load_dotenv()

# Set Resend API key
resend.api_key = os.getenv("GPU_RESEND_API_KEY") or os.getenv("RESEND_API_KEY")

app = Flask(__name__)
app.secret_key = os.getenv("SECRET_KEY", "gpu_action_secret_2026")
ADMIN_PASSWORD = os.getenv("ADMIN_PASSWORD", "gpuaction2026!")
DB_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "gpu_action.db")

def get_db():
    conn = sqlite3.connect(DB_FILE)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = get_db()
    cursor = conn.cursor()
    # Create Demand table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS demands (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            email TEXT NOT NULL,
            gpu_model TEXT NOT NULL,
            quantity INTEGER NOT NULL,
            duration TEXT NOT NULL,
            notes TEXT,
            status TEXT DEFAULT 'Pending',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    # Create Supply table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS supplies (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            email TEXT NOT NULL,
            gpu_model TEXT NOT NULL,
            quantity INTEGER NOT NULL,
            price TEXT NOT NULL,
            specs TEXT,
            status TEXT DEFAULT 'Pending',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    # Create Licenses table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS licenses (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            license_key TEXT UNIQUE NOT NULL,
            email TEXT NOT NULL,
            expire_date TIMESTAMP NOT NULL,
            status TEXT DEFAULT 'Active',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    
    # Add missing columns dynamically
    cursor.execute("PRAGMA table_info(licenses)")
    existing_columns = [row[1] for row in cursor.fetchall()]
    new_cols = [
        ("active_instances_count", "INTEGER DEFAULT 0"),
        ("total_failovers", "INTEGER DEFAULT 0"),
        ("saved_dollars", "REAL DEFAULT 0.0"),
        ("saved_percentage", "INTEGER DEFAULT 0"),
        ("last_reported_at", "TIMESTAMP"),
        ("plan", "TEXT")
    ]
    for col_name, col_type in new_cols:
        if col_name not in existing_columns:
            cursor.execute(f"ALTER TABLE licenses ADD COLUMN {col_name} {col_type}")
            
    conn.commit()
    conn.close()

def send_telegram_alert(message):
    token = os.getenv("TELEGRAM_TOKEN", "8973603845:AAFLCOfbwVdLmUuzT7vqdmfVW3xNsrsViPM")
    chat_id = os.getenv("TELEGRAM_CHAT_ID", "7514482339")
    if not token or not chat_id:
        return
    url = f"https://api.telegram.org/bot{token}/sendMessage"
    payload = {
        "chat_id": chat_id,
        "text": message,
        "parse_mode": "HTML"
    }
    try:
        requests.post(url, json=payload, timeout=5)
    except Exception as e:
        print(f"Telegram alert failed: {e}")

def send_welcome_email(email_address):
    if not resend.api_key:
        print("Resend API key is missing. Skipping welcome email.")
        return
    
    html_content = """<!DOCTYPE html>
    <html>
    <head>
        <meta charset="utf-8">
        <style>
            body {
                font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
                background-color: #090a0f;
                color: #e6edf3;
                margin: 0;
                padding: 0;
            }
        </style>
    </head>
    <body style="background-color: #090a0f; color: #e6edf3; margin: 0; padding: 0;">
        <table width="100%" border="0" cellspacing="0" cellpadding="0" style="background-color: #090a0f; padding: 40px 20px;">
            <tr>
                <td align="center">
                    <table width="100%" max-width="600" border="0" cellspacing="0" cellpadding="0" style="max-width: 600px; background-color: #12131a; border: 1px solid #21262d; border-radius: 8px; box-shadow: 0 8px 24px rgba(0,0,0,0.5); overflow: hidden;">
                        <tr>
                            <td style="padding: 40px 40px 20px 40px; text-align: left; border-bottom: 1px solid #21262d;">
                                <div style="font-size: 22px; font-weight: 800; color: #ffffff; text-transform: uppercase; letter-spacing: 1px;">
                                    GPU<span style="color: #f97316;">-ACTION</span>
                                </div>
                                <div style="font-size: 10px; font-weight: 600; letter-spacing: 2px; color: #8b949e; text-transform: uppercase; margin-top: 4px;">
                                    AI GPU Cost Audit Confirmation
                                </div>
                            </td>
                        </tr>
                        <tr>
                            <td style="padding: 30px 40px 30px 40px; font-size: 15px; line-height: 1.7; color: #c9d1d9;">
                                <p style="margin: 0 0 16px 0; font-weight: 700; color: #ffffff;">Welcome to SpotWarp,</p>
                                <p style="margin: 0 0 16px 0;">Thank you for starting your <b>14-Day Free Trial</b> of the SpotWarp Spot-Instance Failover Guard.</p>
                                <p style="margin: 0 0 12px 0; font-weight: 600; color: #ffffff;">Quick Start Instructions (100% Local Security):</p>
                                <ul style="margin: 0 0 24px 0; padding-left: 20px;">
                                    <li style="margin-bottom: 8px;"><b>1. Install CLI Package:</b> Run <code>pip install spotwarp</code> in your terminal.</li>
                                    <li style="margin-bottom: 8px;"><b>2. Run Guard Daemon:</b> Execute <code>spotwarp start</code> on your host machine or server.</li>
                                    <li style="margin-bottom: 8px;"><b>3. Zero-Key Leakage:</b> Your Vast/RunPod API key stays 100% local on your machine.</li>
                                </ul>
                                <p style="margin: 0 0 16px 0;">If you have any questions or require custom failover rules, simply reply directly to this email.</p>
                            </td>
                        </tr>
                        <tr>
                            <td style="padding: 0 40px 40px 40px; font-size: 14px; color: #8b949e; line-height: 1.6;">
                                <p style="margin: 0; font-weight: 600; color: #ffffff;">The SpotWarp Engineering Team</p>
                                <p style="margin: 0; font-size: 12px; color: #8b949e;">SpotWarp | AI Infrastructure & Inference Gateway</p>
                            </td>
                        </tr>
                        <tr>
                            <td style="background-color: #0d0e14; border-top: 1px solid #21262d; padding: 24px 40px; font-size: 11px; color: #8b949e; line-height: 1.6; text-align: center;">
                                <p style="margin: 0;">© 2026 SpotWarp. All rights reserved.</p>
                            </td>
                        </tr>
                    </table>
                </td>
            </tr>
        </table>
    </body>
    </html>
    """
    try:
        resend.Emails.send({
            "from": "SpotWarp <info@spotwarp.com>",
            "to": email_address,
            "subject": "[SpotWarp] Welcome to the Compute Waitlist",
            "html": html_content
        })
        print(f"Welcome email sent successfully to {email_address}")
    except Exception as e:
        print(f"Failed to send welcome email: {e}")

def send_admin_email_alert(subject, html_content):
    if not resend.api_key:
        print("Resend API key is missing. Skipping admin email alert.")
        return
    admin_email = os.getenv("ADMIN_EMAIL", "choi5844@gmail.com")
    try:
        resend.Emails.send({
            "from": "SpotWarp Admin <info@spotwarp.com>",
            "to": [admin_email, "info@spotwarp.com"],
            "subject": f"[SpotWarp] {subject}",
            "html": html_content
        })
        print(f"Admin email alert sent to {admin_email}")
    except Exception as e:
        print(f"Failed to send admin email alert: {e}")

@app.route('/robots.txt')
def robots():
    return send_from_directory(app.static_folder, 'robots.txt')

@app.route('/sitemap.xml')
def sitemap():
    return send_from_directory(app.static_folder, 'sitemap.xml')

@app.route('/privacy')
def privacy():
    return render_template('privacy.html')

@app.route('/docs')
def docs():
    return render_template('docs.html')

@app.route('/api/v1/verify_license', methods=['POST', 'GET'])
def verify_license():
    data = request.get_json(silent=True) or request.form or {}
    license_key = data.get('license_key') or request.args.get('license_key', '').strip()
    
    if not license_key:
        return jsonify({"valid": False, "message": "License key required"}), 400
        
    conn = get_db()
    cursor = conn.cursor()
    lic = cursor.execute("SELECT * FROM licenses WHERE license_key = ? AND status = 'Active'", (license_key,)).fetchone()
    conn.close()
    
    if lic:
        expire_date_str = lic['expire_date']
        try:
            expire_date = datetime.strptime(expire_date_str, '%Y-%m-%d %H:%M:%S')
        except ValueError:
            try:
                expire_date = datetime.strptime(expire_date_str, '%Y-%m-%d')
            except ValueError:
                expire_date = datetime.now()
                
        if datetime.now() < expire_date:
            return jsonify({
                "valid": True,
                "license_key": license_key,
                "plan": "Developer Pass ($49/mo)" if license_key.startswith("gpu_act_sk_") else "14-Day Free Trial",
                "status": "active",
                "message": "License verified. Spot-Failover Guard Active."
            })
        else:
            return jsonify({
                "valid": False,
                "license_key": license_key,
                "status": "expired",
                "message": f"License expired on {expire_date_str}."
            }), 402
    else:
        if license_key == "DEVELOPMENT_TEST_KEY":
            return jsonify({
                "valid": True,
                "license_key": license_key,
                "plan": "Development Test Pass",
                "status": "active",
                "message": "Development bypass. License verified."
            })
        return jsonify({
            "valid": False,
            "license_key": license_key,
            "status": "invalid",
            "message": "License key not found or inactive."
        }), 401

@app.route('/api/v1/request_trial', methods=['POST'])
def request_trial():
    data = request.get_json(silent=True) or request.form or {}
    email = data.get('email', '').strip()
    name = data.get('name', '').strip() or 'Developer'
    
    if not email:
        return jsonify({"success": False, "message": "Email is required"}), 400
        
    trial_key = f"TRIAL_{email.split('@')[0].upper()}_2026"
    
    try:
        from datetime import timedelta
        expire_date = (datetime.now() + timedelta(days=14)).strftime('%Y-%m-%d %H:%M:%S')
        
        conn = get_db()
        cursor = conn.cursor()
        cursor.execute(
            "INSERT INTO demands (name, email, gpu_model, quantity, duration, notes) VALUES (?, ?, ?, ?, ?, ?)",
            (name, email, "Spot-Failover Guard (Trial)", 1, "14-Day Trial", f"License Key: {trial_key}")
        )
        cursor.execute(
            "INSERT INTO licenses (license_key, email, expire_date) VALUES (?, ?, ?)",
            (trial_key, email, expire_date)
        )
        conn.commit()
        conn.close()
        
        # Send Telegram & Email notification
        alert_msg = (
            f"⚡ <b>[SpotWarp: New 14-Day Trial Request]</b>\n\n"
            f"👤 <b>Developer:</b> {name} ({email})\n"
            f"🔑 <b>Trial License Key:</b> <code>{trial_key}</code>\n"
            f"⏱️ <b>Time:</b> {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
        )
        send_telegram_alert(alert_msg)
        send_welcome_email(email)
        
        return jsonify({
            "success": True,
            "message": "14-Day Free Trial activated! Check your email for your license key.",
            "license_key": trial_key,
            "install_command": f"pip install spotwarp\nspotwarp start --license-key {trial_key}"
        })
    except Exception as e:
        return jsonify({"success": False, "message": str(e)}), 500

@app.route('/api/v1/simulate_upgrade', methods=['POST'])
def simulate_upgrade():
    data = request.get_json(silent=True) or request.form or {}
    license_key = data.get('license_key', '').strip()
    plan_type = data.get('plan_type', 'Developer Pass ($49/mo)').strip()
    
    if not license_key:
        return jsonify({"success": False, "message": "License key is required"}), 400
        
    try:
        from datetime import timedelta
        new_expire = (datetime.now() + timedelta(days=365)).strftime('%Y-%m-%d %H:%M:%S')
        
        conn = get_db()
        cursor = conn.cursor()
        
        # Check if license exists in DB
        lic = cursor.execute("SELECT id FROM licenses WHERE license_key = ?", (license_key,)).fetchone()
        if lic:
            # Upgrade existing license
            cursor.execute(
                "UPDATE licenses SET plan = ?, expire_date = ?, status = 'Active' WHERE license_key = ?",
                (plan_type, new_expire, license_key)
            )
        else:
            # If it doesn't exist, create it as a permanent upgraded key
            cursor.execute(
                "INSERT INTO licenses (license_key, email, plan, expire_date, status) VALUES (?, ?, ?, ?, ?)",
                (license_key, "customer@company.ai", plan_type, new_expire, "Active")
            )
        conn.commit()
        conn.close()
        
        # Send Telegram notification of mock purchase
        alert_msg = (
            f"💰 <b>[SpotWarp: Simulate Stripe Payment]</b>\n\n"
            f"🔑 <b>License Key:</b> <code>{license_key}</code>\n"
            f"📦 <b>Upgraded Plan:</b> <code>{plan_type}</code>\n"
            f"⏱️ <b>Time:</b> {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
        )
        send_telegram_alert(alert_msg)
        
        return jsonify({
            "success": True,
            "message": f"Successfully simulated Stripe payment! Upgraded to {plan_type}.",
            "plan": plan_type,
            "expire_date": new_expire
        })
    except Exception as e:
        return jsonify({"success": False, "message": str(e)}), 500

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/submit-demand', methods=['POST'])
def submit_demand():
    email = request.form.get('email')
    if not email:
        return jsonify({"success": False, "message": "Email is required"}), 400

    name = request.form.get('name', '').strip() or 'Waitlist User'
    gpu_model = request.form.get('gpu_model', 'Unspecified')
    quantity = request.form.get('quantity', 1)
    duration = request.form.get('duration', 'Unspecified')
    notes = request.form.get('notes', 'Joined Compute Waitlist')

    try:
        conn = get_db()
        cursor = conn.cursor()
        
        # Check if email already exists
        existing = cursor.execute("SELECT id FROM demands WHERE email = ?", (email,)).fetchone()
        if existing:
            conn.close()
            alert_msg = (
                f"🔵 <b>[SpotWarp: Duplicate Waitlist Sign-up]</b>\n\n"
                f"📧 <b>Email:</b> {email} (Already registered)\n"
                f"⏱️ <b>Time:</b> {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
            )
            send_telegram_alert(alert_msg)
            
            # Send admin email alert for duplicate
            admin_html = f"""
            <h3>[SpotWarp] Duplicate Waitlist Sign-up</h3>
            <p><b>Email:</b> {email} (Already registered)</p>
            <p><b>Time:</b> {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}</p>
            """
            send_admin_email_alert("Duplicate Waitlist Sign-up", admin_html)
            
            return jsonify({"success": True, "message": "You are already registered on the waitlist!"})

        cursor.execute(
            "INSERT INTO demands (name, email, gpu_model, quantity, duration, notes) VALUES (?, ?, ?, ?, ?, ?)",
            (name, email, gpu_model, int(quantity), duration, notes)
        )
        conn.commit()
        conn.close()

        # Send alert
        alert_msg = (
            f"🔵 <b>[SpotWarp: New Waitlist Sign-up]</b>\n\n"
            f"📧 <b>Email:</b> {email}\n"
            f"⏱️ <b>Registered:</b> {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
        )
        send_telegram_alert(alert_msg)
        
        # Send welcome/confirmation email
        send_welcome_email(email)
        
        # Send admin email alert for new sign-up
        admin_html = f"""
        <h3>[SpotWarp] New Waitlist Sign-up</h3>
        <table border="1" cellpadding="8" style="border-collapse: collapse; border-color: #ddd;">
            <tr><td><b>Name</b></td><td>{name}</td></tr>
            <tr><td><b>Email</b></td><td>{email}</td></tr>
            <tr><td><b>GPU Model</b></td><td>{gpu_model}</td></tr>
            <tr><td><b>Quantity</b></td><td>{quantity}</td></tr>
            <tr><td><b>Duration</b></td><td>{duration}</td></tr>
            <tr><td><b>Notes</b></td><td>{notes}</td></tr>
            <tr><td><b>Time</b></td><td>{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}</td></tr>
        </table>
        """
        send_admin_email_alert("New Waitlist Sign-up", admin_html)
        
        return jsonify({"success": True, "message": "Successfully joined the waitlist!"})
    except Exception as e:
        return jsonify({"success": False, "message": f"Database error: {str(e)}"}), 500

@app.route('/submit-supply', methods=['POST'])
def submit_supply():
    name = request.form.get('name')
    email = request.form.get('email')
    gpu_model = request.form.get('gpu_model')
    quantity = request.form.get('quantity')
    price = request.form.get('price')
    specs = request.form.get('specs', '')

    if not (name and email and gpu_model and quantity and price):
        return jsonify({"success": False, "message": "All fields are required"}), 400

    try:
        conn = get_db()
        cursor = conn.cursor()
        cursor.execute(
            "INSERT INTO supplies (name, email, gpu_model, quantity, price, specs) VALUES (?, ?, ?, ?, ?, ?)",
            (name, email, gpu_model, int(quantity), price, specs)
        )
        conn.commit()
        conn.close()

        # Send alert
        alert_msg = (
            f"🟢 <b>[SpotWarp: 공급 등록 접수]</b>\n\n"
            f"👤 <b>제공자:</b> {name} ({email})\n"
            f"🖥️ <b>보유 GPU:</b> {gpu_model} ({quantity}대)\n"
            f"💰 <b>희망 가격:</b> {price}\n"
            f"⚙️ <b>네트워크/스펙:</b> {specs}"
        )
        send_telegram_alert(alert_msg)

        # Send admin email alert for new supply
        admin_html = f"""
        <h3>[SpotWarp] New Supply Registered</h3>
        <table border="1" cellpadding="8" style="border-collapse: collapse; border-color: #ddd;">
            <tr><td><b>Provider Name</b></td><td>{name}</td></tr>
            <tr><td><b>Email</b></td><td>{email}</td></tr>
            <tr><td><b>GPU Model</b></td><td>{gpu_model}</td></tr>
            <tr><td><b>Quantity</b></td><td>{quantity}</td></tr>
            <tr><td><b>Expected Price</b></td><td>{price}</td></tr>
            <tr><td><b>Specs/Network</b></td><td>{specs}</td></tr>
            <tr><td><b>Time</b></td><td>{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}</td></tr>
        </table>
        """
        send_admin_email_alert("New Supply Registered", admin_html)

        return jsonify({"success": True, "message": "Supply registered successfully!"})
    except Exception as e:
        return jsonify({"success": False, "message": f"Database error: {str(e)}"}), 500

@app.route('/admin', methods=['GET', 'POST'])
def admin():
    if request.method == 'POST':
        password = request.form.get('password')
        if password == ADMIN_PASSWORD:
            session['admin_logged_in'] = True
            return redirect('/admin')
        else:
            return render_template('admin_login.html', error="Invalid password")

    if not session.get('admin_logged_in'):
        return render_template('admin_login.html')

    conn = get_db()
    cursor = conn.cursor()
    demands = cursor.execute("SELECT * FROM demands ORDER BY id DESC").fetchall()
    supplies = cursor.execute("SELECT * FROM supplies ORDER BY id DESC").fetchall()
    licenses = cursor.execute("SELECT * FROM licenses ORDER BY id DESC").fetchall()
    conn.close()

    return render_template('admin.html', demands=demands, supplies=supplies, licenses=licenses)

@app.route('/admin/logout')
def admin_logout():
    session.pop('admin_logged_in', None)
    return redirect('/admin')

@app.route('/admin/update-status', methods=['POST'])
def update_status():
    if not session.get('admin_logged_in'):
        return jsonify({"success": False, "message": "Unauthorized"}), 401

    table = request.json.get('table')  # 'demands' or 'supplies'
    item_id = request.json.get('id')
    status = request.json.get('status')

    if table not in ['demands', 'supplies'] or not item_id:
        return jsonify({"success": False, "message": "Invalid parameters"}), 400

    try:
        conn = get_db()
        cursor = conn.cursor()
        cursor.execute(f"UPDATE {table} SET status = ? WHERE id = ?", (status, int(item_id)))
        conn.commit()
        conn.close()
        return jsonify({"success": True, "message": "Status updated successfully"})
    except Exception as e:
        return jsonify({"success": False, "message": str(e)}), 500


import time

MARKET_PRICES_CACHE = {
    "last_updated": 0,
    "prices": {
        "RTX 3090": 0.22,
        "RTX 4090": 0.35,
        "A100 80GB": 0.85,
        "H100 SXM5": 2.10
    }
}

def get_market_prices():
    now = time.time()
    # Cache for 10 minutes
    if now - MARKET_PRICES_CACHE["last_updated"] < 600:
        return MARKET_PRICES_CACHE["prices"]
        
    headers = {"Accept": "application/json"}
    gpus_to_query = {
        "RTX 3090": "3090",
        "RTX 4090": "4090",
        "A100 80GB": "A100",
        "H100 SXM5": "H100"
    }
    
    new_prices = {}
    for display_name, search_name in gpus_to_query.items():
        q = {
            "rentable": {"eq": True},
            "gpu_name": {"ilike": f"%{search_name}%"},
            "order": [["dph_total", "asc"]],
            "limit": 5
        }
        try:
            r = requests.get(
                "https://cloud.vast.ai/api/v0/bundles/",
                params={"q": json.dumps(q)},
                headers=headers,
                timeout=5
            )
            if r.status_code == 200:
                offers = r.json().get('offers', [])
                if offers:
                    min_price = min([float(o.get('dph_total', 99.0)) for o in offers])
                    new_prices[display_name] = round(min_price, 2)
        except Exception as e:
            print(f"Vast price fetch failed for {display_name}: {e}")
            
    for gpu, val in new_prices.items():
        MARKET_PRICES_CACHE["prices"][gpu] = val
    MARKET_PRICES_CACHE["last_updated"] = now
    return MARKET_PRICES_CACHE["prices"]

@app.route('/api/v1/update_status', methods=['POST'])
def update_status_api():
    data = request.get_json(silent=True) or request.form or {}
    license_key = data.get('license_key')
    
    if not license_key:
        return jsonify({"success": False, "message": "License key required"}), 400
        
    active_instances_count = data.get('active_instances_count', 0)
    total_failovers = data.get('total_failovers', 0)
    saved_dollars = data.get('saved_dollars', 0.0)
    saved_percentage = data.get('saved_percentage', 0)
    
    conn = get_db()
    cursor = conn.cursor()
    lic = cursor.execute("SELECT * FROM licenses WHERE license_key = ? AND status = 'Active'", (license_key,)).fetchone()
    
    if not lic:
        conn.close()
        if license_key == "DEVELOPMENT_TEST_KEY" or license_key.startswith("TRIAL_"):
            return jsonify({"success": True, "message": "Development bypass. Status recorded."})
        return jsonify({"success": False, "message": "License key not found or inactive."}), 401
        
    now_str = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    cursor.execute("""
        UPDATE licenses 
        SET active_instances_count = ?, 
            total_failovers = ?, 
            saved_dollars = ?, 
            saved_percentage = ?, 
            last_reported_at = ?
        WHERE license_key = ?
    """, (int(active_instances_count), int(total_failovers), float(saved_dollars), int(saved_percentage), now_str, license_key))
    conn.commit()
    conn.close()
    
    return jsonify({"success": True, "message": "Status updated successfully"})

@app.route('/api/v1/market_prices', methods=['GET'])
def market_prices_api():
    prices = get_market_prices()
    return jsonify({"success": True, "prices": prices})

@app.route('/dashboard/login', methods=['GET', 'POST'])
def dashboard_login():
    if request.method == 'POST':
        license_key = request.form.get('license_key', '').strip()
        if not license_key:
            return render_template('index.html', error="License key is required.")
            
        conn = get_db()
        cursor = conn.cursor()
        lic = cursor.execute("SELECT * FROM licenses WHERE license_key = ? AND status = 'Active'", (license_key,)).fetchone()
        conn.close()
        
        if lic or license_key == "DEVELOPMENT_TEST_KEY" or license_key.startswith("TRIAL_"):
            session['user_license_key'] = license_key
            return redirect('/dashboard')
        else:
            # Render index.html with inline error message
            return redirect('/?error=invalid_license')
            
    return redirect('/')

@app.route('/dashboard')
def dashboard():
    license_key = session.get('user_license_key')
    if not license_key:
        return redirect('/')
        
    conn = get_db()
    cursor = conn.cursor()
    lic = cursor.execute("SELECT * FROM licenses WHERE license_key = ?", (license_key,)).fetchone()
    conn.close()
    
    # Handle development keys or trial keys not in DB (mock defaults)
    if not lic:
        if license_key == "DEVELOPMENT_TEST_KEY" or license_key.startswith("TRIAL_"):
            lic = {
                "license_key": license_key,
                "email": "developer@company.ai" if license_key == "DEVELOPMENT_TEST_KEY" else f"{license_key.split('_')[1].lower()}@company.ai",
                "expire_date": "2026-12-31 23:59:59",
                "status": "Active",
                "active_instances_count": 1,
                "total_failovers": 2,
                "saved_dollars": 154.20,
                "saved_percentage": 70,
                "last_reported_at": datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            }
        else:
            session.pop('user_license_key', None)
            return redirect('/')
            
    prices = get_market_prices()
    return render_template('dashboard.html', license=lic, prices=prices)

@app.route('/dashboard/logout')
def dashboard_logout():
    session.pop('user_license_key', None)
    return redirect('/')

if __name__ == '__main__':
    init_db()
    # Port 8087 chosen to prevent conflicts with 8000 (Vity-Signal)
    app.run(host='0.0.0.0', port=8087, debug=True)
