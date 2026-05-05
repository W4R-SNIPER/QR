from flask import Flask, render_template, request, send_file
import os, sqlite3, qrcode
from PIL import Image, ImageDraw
from qrcode.image.styledpil import StyledPilImage
from qrcode.image.styles.moduledrawers import CircleModuleDrawer, RoundedModuleDrawer, SquareModuleDrawer
from qrcode.image.styles.colormasks import SolidFillColorMask

app = Flask(__name__)

BASE_URL = "https://qr-am95.onrender.com"
QR_PATH = "static/qr.png"
LOGO_PATH = "static/logos/logo.png"

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
    if not h:
        return (0, 0, 0)
    h = h.lstrip("#")
    return tuple(int(h[i:i+2], 16) for i in (0, 2, 4))

def add_logo(path):
    if not os.path.exists(LOGO_PATH):
        return
    qr = Image.open(path).convert("RGBA")
    logo = Image.open(LOGO_PATH).convert("RGBA").resize((80, 80))
    pos = ((qr.size[0]-80)//2, (qr.size[1]-80)//2)
    qr.paste(logo, pos, logo)
    qr.save(path)

def recolor_qr(input_path, output_path, new_color, new_bg):
    """Recolor existing QR without regenerating"""
    try:
        img = Image.open(input_path).convert("RGB")
        pixels = img.load()
        width, height = img.size
        
        old_color = (0, 0, 0)
        old_bg = (255, 255, 255)
        new_color_rgb = hex_to_rgb(new_color)
        new_bg_rgb = hex_to_rgb(new_bg)
        
        for i in range(width):
            for j in range(height):
                r, g, b = pixels[i, j][:3]
                # Check if pixel is black (dark) or white (light)
                if (r + g + b) / 3 < 128:  # Dark = QR module
                    pixels[i, j] = new_color_rgb
                else:  # Light = Background
                    pixels[i, j] = new_bg_rgb
        
        img.save(output_path)
    except:
        pass

# -------- BUILD DATA --------
def build_qr_data(form):

    if 'ssid' in form:
        return f"WIFI:T:WPA;S:{form['ssid']};P:{form['password']};;"

    if 'phone' in form:
        return f"https://wa.me/{form['phone']}"

    if 'instagram' in form:
        return f"https://instagram.com/{form['instagram'].replace('@','')}"

    if 'facebook' in form:
        fb = form['facebook']
        return fb if fb.startswith("http") else f"https://facebook.com/{fb}"

    if 'snapchat' in form:
        return f"https://snapchat.com/add/{form['snapchat'].replace('@','')}"

    data = form.get("data", "")

    # smarter URL handling
    if data and "." in data and not data.startswith(("http://", "https://")):
        data = "https://" + data

    if not data:
        return "https://example.com"

    return data

# -------- GENERATE QR --------
def generate_qr(data, color, bg, style, frame, mode):

    color = color or "#000000"
    bg = bg or "#ffffff"

    conn = sqlite3.connect("database.db")
    c = conn.cursor()
    c.execute("INSERT INTO qr_codes (data) VALUES (?)", (data,))
    qr_id = c.lastrowid
    conn.commit()
    conn.close()

    qr_data = f"{BASE_URL}/qr/{qr_id}" if mode == "track" else data

    # 🎨 SELECT STYLE DRAWER
    if style == "dot":
        drawer = CircleModuleDrawer()
    elif style == "heart":
        drawer = RoundedModuleDrawer()
    elif style == "diamond":
        drawer = CircleModuleDrawer()  # Diamond effect with post-processing
    elif style == "pixel":
        drawer = SquareModuleDrawer()  # Pixel/square style
    else:
        drawer = SquareModuleDrawer()

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
    ).convert("RGB")

    # ❤️ HEART BACKGROUND PATTERN
    if style == "heart":
        bg_img = Image.new("RGB", img.size, hex_to_rgb(bg))
        draw_bg = ImageDraw.Draw(bg_img)

        for x in range(0, img.size[0], 40):
            for y in range(0, img.size[1], 40):
                draw_bg.text((x, y), "❤", fill=(255, 200, 200))

        bg_img.paste(img, (0, 0))
        img = bg_img

    # 💎 DIAMOND EFFECT (rotated with expand to prevent trimming)
    elif style == "diamond":
        img = img.rotate(45, expand=True, fillcolor=hex_to_rgb(bg))

    img.save(QR_PATH)
    add_logo(QR_PATH)

    # frame
    im = Image.open(QR_PATH)
    draw = ImageDraw.Draw(im)

    if frame == "black":
        draw.rectangle([0,0,im.size[0],im.size[1]], outline="black", width=10)
    elif frame == "rounded":
        draw.rounded_rectangle([0,0,im.size[0],im.size[1]], radius=40, outline="black", width=10)

    im.save(QR_PATH)

# -------- ROUTES --------
@app.route("/", methods=["GET","POST"])
def home():
    if request.method == "POST":
        # Check if this is a recolor request (has style but no data changes)
        has_data = any(key in request.form for key in ['data', 'phone', 'instagram', 'facebook', 'snapchat', 'ssid'])
        
        if has_data:
            # Full QR generation
            data = build_qr_data(request.form)
            generate_qr(
                data,
                request.form.get("qr-color", "#000000"),
                request.form.get("qr-bg", "#ffffff"),
                request.form.get("style", "square"),
                request.form.get("frame"),
                request.form.get("mode")
            )
        else:
            # Just recolor existing QR
            recolor_qr(
                QR_PATH,
                QR_PATH,
                request.form.get("qr-color", "#000000"),
                request.form.get("qr-bg", "#ffffff")
            )

    return render_template("index.html")

@app.route("/download")
def download():
    return send_file(QR_PATH, as_attachment=True)

if __name__ == "__main__":
    app.run(debug=True)