from flask import Flask, request, jsonify, send_from_directory, render_template_string, send_file
import json
import os
from flask_cors import CORS
from datetime import datetime
import zipfile
import io

app = Flask(__name__, static_url_path='', static_folder='static')
CORS(app)

DATA_FILE_FREEFIRE = "static/registrations_freefire.json"
DATA_FILE_PUBG = "static/registrations_pubg.json"
SCREENSHOT_DIR = "static/screenshots"  # Screenshots saved here

# Ensure screenshot directory exists
if not os.path.exists(SCREENSHOT_DIR):
    os.makedirs(SCREENSHOT_DIR)

def load_data(data_file):
    if os.path.exists(data_file):
        with open(data_file, "r") as file:
            return json.load(file)
    return []

def save_data(data, data_file):
    with open(data_file, "w") as file:
        json.dump(data, file, indent=4)

def generate_unique_id(prefix):
    return f"{prefix}{datetime.now().strftime('%Y%m%d%H%M%S')}{os.urandom(2).hex().upper()}"

@app.route('/')
def serve_index():
    return send_from_directory('static', 'index.html')

@app.route('/get_id', methods=['POST'])
def get_id():
    data = request.json
    parameter = data.get("parameter")
    return jsonify({"reg_id": generate_unique_id(parameter)}), 200

@app.route('/register_', methods=['POST'])
def register_():
    data = request.json

    if data.get("gameType") == "freefire":
        DATA_FILE = DATA_FILE_FREEFIRE
    else:
        DATA_FILE = DATA_FILE_PUBG

    registrations = load_data(DATA_FILE)

    reg_id = data.get("regId")
    type_ = data.get("parameter")

    if type_ == "SINGLE":
        registrations.append({
            "reg_id": reg_id,
            "type": type_,
            "name": data.get("username"),
            "uid": data.get("uid"),
            "email": data.get("email"),
            "payment_status": "pending",
            "screenshot": None,
            "amount": 50,
            "timestamp": datetime.now().isoformat()
        })
        save_data(registrations, DATA_FILE)
        return jsonify({"message": "Single registration saved!", "reg_id": reg_id}), 200
    else:
        team_name = data.get("teamName")
        members = data.get("members")
        registrations.append({
            "reg_id": reg_id,
            "type": type_,
            "team_name": team_name,
            "members": members,
            "payment_status": "pending",
            "screenshot": None,
            "amount": 200,
            "timestamp": datetime.now().isoformat()
        })
        save_data(registrations, DATA_FILE)
        return jsonify({"message": "Team registration saved!", "reg_id": reg_id}), 200

@app.route('/upload-payment', methods=['POST'])
def upload_payment():
    reg_id = request.form.get("reg_id")
    screenshot = request.files.get("screenshot")
    game_type = request.form.get("game_type", "freefire")

    if not reg_id or not screenshot:
        return jsonify({"error": "Missing reg_id or screenshot"}), 400

    data_file = DATA_FILE_FREEFIRE if game_type == "freefire" else DATA_FILE_PUBG
    registrations = load_data(data_file)
    
    reg_found = False
    for reg in registrations:
        if reg["reg_id"] == reg_id:
            screenshot_filename = f"{reg_id}_{screenshot.filename}"
            screenshot_path = os.path.join(SCREENSHOT_DIR, screenshot_filename)
            screenshot.save(screenshot_path)
            reg["screenshot"] = f"screenshots/{screenshot_filename}"  # Store relative to static/
            reg_found = True
            break
    
    if not reg_found:
        return jsonify({"error": "Registration not found"}), 404

    save_data(registrations, data_file)
    return jsonify({"message": "Screenshot uploaded!", "reg_id": reg_id}), 200

@app.route('/pending-payments', methods=['GET'])
def get_pending_payments():
    game_type = request.args.get("game_type", "freefire")
    data_file = DATA_FILE_FREEFIRE if game_type == "freefire" else DATA_FILE_PUBG
    registrations = load_data(data_file)
    pending = [r for r in registrations if r["payment_status"] == "pending" and r.get("screenshot")]
    return jsonify(pending), 200

@app.route('/confirm-payment', methods=['POST'])
def confirm_payment():
    data = request.json
    reg_id = data.get("reg_id")
    game_type = data.get("game_type", "freefire")

    if not reg_id:
        return jsonify({"error": "Missing reg_id"}), 400

    data_file = DATA_FILE_FREEFIRE if game_type == "freefire" else DATA_FILE_PUBG
    registrations = load_data(data_file)
    
    reg_found = False
    for reg in registrations:
        if reg["reg_id"] == reg_id:
            reg["payment_status"] = "confirmed"
            reg_found = True
            break
    
    if not reg_found:
        return jsonify({"error": "Registration not found"}), 404

    save_data(registrations, data_file)
    return jsonify({"message": "Payment confirmed!", "reg_id": reg_id}), 200

@app.route('/admin-login', methods=['POST'])
def admin_login():
    data = request.json
    if data.get('username') == 'AUeSports' and data.get('password') == 'auesports@22233124':
        return jsonify({'message': 'Login successful', 'token': 'some-token'}), 200
    return jsonify({'error': 'Invalid credentials'}), 401

@app.route('/view/<game>')
def view_json(game):
    file_path = DATA_FILE_PUBG if game == 'pubg' else DATA_FILE_FREEFIRE
    try:
        with open(file_path, 'r') as f:
            data = json.load(f)
        html = f"<h2>Registrations for {game.upper()}</h2>"
        html += "<ul>"
        for item in data:
            html += "<li>"
            html += "<br>".join([f"<b>{k}:</b> {v}" for k, v in item.items() if k != "screenshot"])
            if item.get("screenshot"):
                screenshot_path = item["screenshot"]
                html += f'<br><img src="/{screenshot_path}" alt="Payment Screenshot" style="max-width: 300px;">'
            html += "</li><hr>"
        html += "</ul>"
        return render_template_string(html)
    except FileNotFoundError:
        return "No registrations found yet."

@app.route('/download/<game>')
def download_json(game):
    file_path = DATA_FILE_PUBG if game == 'pubg' else DATA_FILE_FREEFIRE
    try:
        with open(file_path, 'r') as f:
            data = json.load(f)
        zip_buffer = io.BytesIO()
        with zipfile.ZipFile(zip_buffer, 'w', zipfile.ZIP_DEFLATED) as zip_file:
            zip_file.write(file_path, os.path.basename(file_path))
            for item in data:
                if item.get("screenshot"):
                    screenshot_path = os.path.join(app.static_folder, item["screenshot"])
                    if os.path.exists(screenshot_path):
                        zip_file.write(screenshot_path, os.path.basename(screenshot_path))
        zip_buffer.seek(0)
        return send_file(
            zip_buffer,
            mimetype='application/zip',
            as_attachment=True,
            download_name=f"{game}_registrations_with_screenshots.zip"
        )
    except FileNotFoundError:
        return "File not found.", 404

@app.route('/all', methods=['GET'])
def get_all():
    game_type = request.args.get("game_type", "freefire")
    data_file = DATA_FILE_FREEFIRE if game_type == "freefire" else DATA_FILE_PUBG
    return jsonify(load_data(data_file)), 200

if __name__ == '__main__':
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=True)