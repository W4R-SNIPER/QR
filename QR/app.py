
from flask import Flask, render_template, request, send_file, redirect, jsonify
import os
import sqlite3
from PIL import Image, ImageDraw
import qrcode
from qrcode.image.styledpil import StyledPilImage
from qrcode.image.styles.moduledrawers import CircleModuleDrawer, RoundedModuleDrawer
from qrcode.image.styles.colormasks import SolidFillColorMask

# -------- CONFIG --------
app = Flask(__name__, static_folder="static")

BASE_URL = os.getenv("BASE_URL", "http://127.0.0.1:5000")
QR_FOLDER = "static/qr_codes"
MAIN_QR = "static/qr.png"   # 👈 IMPORTANT for UI
LOGO_PATH = "static/logos/logo.png"

os.makedirs(QR_FOLDER, exist_ok=True)
os.makedirs("static", exist_ok=True)

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
        if not os.path.exists(LOGO_PATH):
            return
        qr = Image.open(qr_path).convert("RGBA")
        logo = Image.open(LOGO_PATH).convert("RGBA")
        logo = logo.resize((80, 80))

        pos = ((qr.size[0] - logo.size[0]) // 2,
               (qr.size[1] - logo.size[1]) // 2)

        qr.paste(logo, pos, logo)
        qr.save(qr_path)
    except Exception as e:
        print("Logo error:", e)

# -------- GENERATE QR --------
def generate_qr(data):
    conn = sqlite3.connect("database.db")
    c = conn.cursor()
    c.execute("INSERT INTO qr_codes (data) VALUES (?)", (data,))
    qr_id = c.lastrowid
    conn.commit()
    conn.close()

    dynamic_url = f"{BASE_URL}/qr/{qr_id}"

    # STYLE (simple default)
    drawer = RoundedModuleDrawer()

    qr = qrcode.QRCode(error_correction=qrcode.constants.ERROR_CORRECT_H)
    qr.add_data(dynamic_url)
    qr.make(fit=True)

    img = qr.make_image(
        image_factory=StyledPilImage,
        module_drawer=drawer,
        color_mask=SolidFillColorMask(
            front_color=(0, 0, 0),
            back_color=(255, 255, 255)
        )
    )

    # Save main QR for UI
    img.save(MAIN_QR)

    # Save unique QR (optional)
    file_path = f"{QR_FOLDER}/{qr_id}.png"
    img.save(file_path)

    add_logo(MAIN_QR)

    # Update DB
    conn = sqlite3.connect("database.db")
    c = conn.cursor()
    c.execute("UPDATE qr_codes SET file_path=? WHERE id=?", (file_path, qr_id))
    conn.commit()
    conn.close()

    return MAIN_QR

# -------- HOME --------
@app.route("/", methods=["GET", "POST"])
def home():
    if request.method == "POST":
        data = request.form.get("data")

        if data:
            generate_qr(data)

    return render_template("index.html")

# -------- DOWNLOAD --------
@app.route("/download")
def download():
    return send_file(MAIN_QR, as_attachment=True)

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

        if not data.startswith(("http://", "https://", "mailto:", "tel:", "WIFI:")):
            return "Invalid URL"

        return redirect(data)

    return "QR not found"

# -------- RUN --------
if __name__ == "__main__":
    app.run(debug=True)
