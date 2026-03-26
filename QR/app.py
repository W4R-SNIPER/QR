from flask import Flask, render_template, request, redirect

from flask import jsonify

@app.route("/generate", methods=["POST"])
def generate_live():
    data_type = request.form.get("type")
    value = request.form.get("value")
    ssid = request.form.get("ssid")
    password = request.form.get("password")

    # HANDLE TYPES
    if data_type == "whatsapp":
        data = f"https://wa.me/{value}"
    elif data_type == "instagram":
        data = f"https://instagram.com/{value}"
    elif data_type == "email":
        data = f"mailto:{value}"
    elif data_type == "phone":
        data = f"tel:{value}"
    elif data_type == "wifi":
        data = f"WIFI:T:WPA;S:{ssid};P:{password};;"
    else:
        data = value

    # CREATE QR
    import qrcode
    img = qrcode.make(data)

    path = "static/qr_codes/live.png"
    img.save(path)

    return jsonify({"qr": "/" + path})

import os

BASE_URL = os.getenv("BASE_URL", "http://127.0.0.1:5000")

if mode == "track":
    dynamic_url = f"{BASE_URL}/qr/{qr_id}"
else:
    dynamic_url = data
    
import sqlite3
from PIL import Image, ImageDraw

import qrcode
from qrcode.image.styledpil import StyledPilImage
from qrcode.image.styles.moduledrawers import CircleModuleDrawer, RoundedModuleDrawer
from qrcode.image.styles.colormasks import SolidFillColorMask

app = Flask(__name__, static_folder="static")

QR_FOLDER = "static/qr_codes"
LOGO_PATH = "static/logos/logo.png"

os.makedirs(QR_FOLDER, exist_ok=True)

# -------- DATABASE --------
def init_db():
    conn = sqlite3.connect("database.db")
    c = conn.cursor()

    c.execute("""
    CREATE TABLE IF NOT EXISTS qr_codes (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        data TEXT,
        file_path TEXT,
        scans INTEGER DEFAULT 0
    )
    """)

    conn.commit()
    conn.close()

init_db()

# -------- HEX TO RGB --------
def hex_to_rgb(hex_color):
    if not hex_color:
        return (0, 0, 0)
    hex_color = hex_color.lstrip("#")
    return tuple(int(hex_color[i:i+2], 16) for i in (0, 2, 4))

# -------- ADD LOGO --------
def add_logo(qr_path):
    try:
        qr = Image.open(qr_path).convert("RGBA")
        logo = Image.open(LOGO_PATH).convert("RGBA")

        logo = logo.resize((80, 80))

        pos = (
            (qr.size[0] - logo.size[0]) // 2,
            (qr.size[1] - logo.size[1]) // 2
        )

        qr.paste(logo, pos, logo)
        qr.save(qr_path)
    except:
        pass

# -------- GENERATE QR --------
def generate_qr(data, color, bgcolor, frame, style, mode):
    conn = sqlite3.connect("database.db")
    c = conn.cursor()

    c.execute("INSERT INTO qr_codes (data) VALUES (?)", (data,))
    qr_id = c.lastrowid
    conn.commit()
    conn.close()

    # MODE
    if mode == "track":
        dynamic_url = f"https://qr-am95.onrender.com/qr/{qr_id}" # change after deploy
    else:
        dynamic_url = data

    file_path = f"{QR_FOLDER}/{qr_id}.png"

    # STYLE
    if style == "dots":
        drawer = CircleModuleDrawer()
    elif style == "rounded":
        drawer = RoundedModuleDrawer()
    else:
        drawer = None

    qr = qrcode.QRCode(error_correction=qrcode.constants.ERROR_CORRECT_H)
    qr.add_data(dynamic_url)
    qr.make(fit=True)

    img = qr.make_image(
        image_factory=StyledPilImage,
        module_drawer=drawer,
        color_mask=SolidFillColorMask(
            front_color=hex_to_rgb(color),
            back_color=hex_to_rgb(bgcolor)
        )
    )

    img.save(file_path)

    add_logo(file_path)

    img = Image.open(file_path)
    draw = ImageDraw.Draw(img)

    if frame == "black":
        draw.rectangle([0, 0, img.size[0], img.size[1]], outline="black", width=10)

    elif frame == "rounded":
        draw.rounded_rectangle([0, 0, img.size[0], img.size[1]], radius=40, outline="black", width=10)

    img.save(file_path)

    conn = sqlite3.connect("database.db")
    c = conn.cursor()
    c.execute("UPDATE qr_codes SET file_path=? WHERE id=?", (file_path, qr_id))
    conn.commit()
    conn.close()

    return file_path

# -------- HOME --------
@app.route("/", methods=["GET", "POST"])
def index():
    qr_path = None

    if request.method == "POST":
        qr_type = request.form.get("type")
        mode = request.form.get("mode")
        value = request.form.get("value")

        if qr_type == "whatsapp":
            data = f"https://wa.me/{value}"
        elif qr_type == "instagram":
            data = f"https://instagram.com/{value}"
        elif qr_type == "email":
            data = f"mailto:{value}"
        elif qr_type == "phone":
            data = f"tel:{value}"
        elif qr_type == "wifi":
            ssid = request.form.get("ssid")
            password = request.form.get("password")
            data = f"WIFI:T:WPA;S:{ssid};P:{password};;"
        else:
            data = value

        color = request.form.get("color")
        bgcolor = request.form.get("bgcolor")
        frame = request.form.get("frame")
        style = request.form.get("style")

        qr_path = generate_qr(data, color, bgcolor, frame, style, mode)

    return render_template("index.html", qr_path=qr_path)

# -------- TRACK --------
@app.route("/qr/<int:qr_id>")
def track_qr(qr_id):
    conn = sqlite3.connect("database.db")
    c = conn.cursor()

    c.execute("SELECT data, scans FROM qr_codes WHERE id=?", (qr_id,))
    result = c.fetchone()

    if result:
        data, scans = result
        scans += 1

        c.execute("UPDATE qr_codes SET scans=? WHERE id=?", (scans, qr_id))
        conn.commit()
        conn.close()

        return redirect(data)

    return "QR not found"

# -------- DASHBOARD --------
@app.route("/dashboard")
def dashboard():
    conn = sqlite3.connect("database.db")
    c = conn.cursor()

    c.execute("SELECT * FROM qr_codes")
    data = c.fetchall()

    conn.close()

    return render_template("dashboard.html", data=data)

# -------- RUN --------
if __name__ == "__main__":
    app.run(debug=True)
