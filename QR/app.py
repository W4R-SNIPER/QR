from flask import Flask, render_template, request, send_file, redirect, jsonify
import os, sqlite3, qrcode
from PIL import Image, ImageDraw
from qrcode.image.styledpil import StyledPilImage
from qrcode.image.styles.moduledrawers import CircleModuleDrawer, RoundedModuleDrawer
from qrcode.image.styles.colormasks import SolidFillColorMask

app = Flask(__name__)

BASE_URL = "https://qr-am95.onrender.com"
QR_PATH = "static/qr.png"
QR_FOLDER = "static/qr_codes"
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
        scans INTEGER DEFAULT 0
    )
    """)
    conn.commit()
    conn.close()

init_db()

# -------- HELPERS --------
def hex_to_rgb(h):
    h = (h or "#000000").lstrip("#")
    return tuple(int(h[i:i+2], 16) for i in (0, 2, 4))

def add_logo(path):
    if not os.path.exists(LOGO_PATH): return
    qr = Image.open(path).convert("RGBA")
    logo = Image.open(LOGO_PATH).convert("RGBA").resize((80,80))
    pos = ((qr.size[0]-80)//2, (qr.size[1]-80)//2)
    qr.paste(logo, pos, logo)
    qr.save(path)

# -------- GENERATE --------
def generate_qr(data, color, bg, style, frame, mode):
    conn = sqlite3.connect("database.db")
    c = conn.cursor()
    c.execute("INSERT INTO qr_codes (data) VALUES (?)", (data,))
    qr_id = c.lastrowid
    conn.commit()
    conn.close()

    if mode == "track":
        qr_data = f"{BASE_URL}/qr/{qr_id}"
    else:
        qr_data = data

    drawer = CircleModuleDrawer() if style=="dots" else RoundedModuleDrawer()

    qr = qrcode.QRCode(error_correction=qrcode.constants.ERROR_CORRECT_H)
    qr.add_data(qr_data)
    qr.make(fit=True)

    img = qr.make_image(
        image_factory=StyledPilImage,
        module_drawer=drawer,
        color_mask=SolidFillColorMask(
            front_color=hex_to_rgb(color),
            back_color=hex_to_rgb(bg)
        )
    )

    img.save(QR_PATH)
    add_logo(QR_PATH)

    # frame
    im = Image.open(QR_PATH)
    d = ImageDraw.Draw(im)
    if frame=="black":
        d.rectangle([0,0,im.size[0],im.size[1]], outline="black", width=10)
    elif frame=="rounded":
        d.rounded_rectangle([0,0,im.size[0],im.size[1]], radius=40, outline="black", width=10)
    im.save(QR_PATH)

    return QR_PATH

# -------- ROUTES --------
@app.route("/", methods=["GET","POST"])
def home():
    if request.method=="POST":
        data = request.form.get("data")
        color = request.form.get("color")
        bg = request.form.get("bg")
        style = request.form.get("style")
        frame = request.form.get("frame")
        mode = request.form.get("mode")

        if not data.startswith("http"):
            data = "https://" + data

        generate_qr(data, color, bg, style, frame, mode)

    return render_template("index.html")

@app.route("/generate", methods=["POST"])
def live():
    data = request.form.get("data")
    img = qrcode.make(data)
    path = "static/qr_codes/live.png"
    img.save(path)
    return jsonify({"qr": "/" + path})

@app.route("/download")
def download():
    return send_file(QR_PATH, as_attachment=True)

@app.route("/qr/<int:id>")
def track(id):
    conn = sqlite3.connect("database.db")
    c = conn.cursor()
    c.execute("SELECT data, scans FROM qr_codes WHERE id=?", (id,))
    r = c.fetchone()
    if r:
        data, scans = r
        c.execute("UPDATE qr_codes SET scans=? WHERE id=?", (scans+1,id))
        conn.commit()
        conn.close()
        return redirect(data)
    return "Not found"

@app.route("/dashboard")
def dash():
    conn = sqlite3.connect("database.db")
    c = conn.cursor()
    c.execute("SELECT * FROM qr_codes")
    data = c.fetchall()
    conn.close()
    return render_template("dashboard.html", data=data)

if __name__=="__main__":
    app.run(debug=True)
