from flask import (
    Flask, render_template, request,
    jsonify, send_file, redirect, url_for, session
)
from datetime import datetime
import os
import io
from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas

app = Flask(__name__)

# ========= SEGURANÇA / CONFIG =========
app.secret_key = os.getenv("SECRET_KEY", "chave_dev_insegura")

ADMIN_USER = os.getenv("ADMIN_USER", "diretor")
ADMIN_PASSWORD = os.getenv("ADMIN_PASSWORD", "ProfSafe24@VIP")

# Dados da escola (pode mudar no Render depois)
SCHOOL_NAME = os.getenv("SCHOOL_NAME", "Escola Modelo PROF-SAFE24")
SCHOOL_CITY = os.getenv("SCHOOL_CITY", "Cidade / UF")
SCHOOL_CONTACT = os.getenv("SCHOOL_CONTACT", "Telefone / WhatsApp da escola")

# ========= MEMÓRIA SIMPLES =========
alertas = []
siren_on = False
siren_muted = False
last_alert_time = None


# ========= DECORATOR LOGIN =========
from functools import wraps

def login_required(view_func):
    @wraps(view_func)
    def wrapper(*args, **kwargs):
        if not session.get("logged_in"):
            return redirect(url_for("login_central"))
        return view_func(*args, **kwargs)
    return wrapper


# ========= PÁGINAS =========
@app.route("/")
def home():
    return render_template("home.html")

@app.route("/professor")
def professor():
    return render_template("professor.html")

@app.route("/login_central", methods=["GET", "POST"])
def login_central():
    erro = None
    if request.method == "POST":
        user = request.form.get("username", "").strip()
        password = request.form.get("password", "").strip()

        if user == ADMIN_USER and password == ADMIN_PASSWORD:
            session["logged_in"] = True
            session["admin_user"] = user
            return redirect(url_for("central"))
        else:
            erro = "Usuário ou senha inválidos."

    return render_template("login_central.html", error=erro)

@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("login_central"))

@app.route("/central")
@login_required
def central():
    return render_template(
        "central.html",
        alertas=alertas,
        school_name=SCHOOL_NAME,
        school_city=SCHOOL_CITY,
        school_contact=SCHOOL_CONTACT,
        last_alert_time=last_alert_time,
        siren_on=siren_on
    )


# ========= API – ALERTAS / SIRENE =========
@app.route("/api/alert", methods=["POST"])
def api_alert():
    global siren_on, last_alert_time, siren_muted

    data = request.get_json()
    teacher = data.get("teacher", "Professor")
    room = data.get("room", "Sala")
    desc = data.get("description", "")

    if not room or not desc:
        return jsonify({"ok": False, "error": "Dados incompletos"}), 400

    alerta = {
        "teacher": teacher,
        "room": room,
        "description": desc,
        "time": datetime.now().strftime("%H:%M:%S")
    }

    alertas.insert(0, alerta)
    last_alert_time = datetime.now().strftime("%d/%m/%Y %H:%M:%S")

    if not siren_muted:
        siren_on = True

    return jsonify({"ok": True, "alerta": alerta})


@app.route("/api/status")
@login_required
def api_status():
    return jsonify({
        "alertas": alertas,
        "siren_on": siren_on,
        "siren_muted": siren_muted,
        "last_alert_time": last_alert_time
    })


@app.route("/api/siren", methods=["POST"])
@login_required
def api_siren():
    global siren_on, siren_muted

    data = request.get_json()
    action = data.get("action")

    if action == "on":
        if not siren_muted:
            siren_on = True
    elif action == "off":
        siren_on = False
    elif action == "mute":
        siren_muted = True
        siren_on = False
    elif action == "unmute":
        siren_muted = False
    else:
        return jsonify({"ok": False, "error": "Ação inválida"}), 400

    return jsonify({"ok": True, "siren_on": siren_on, "siren_muted": siren_muted})


@app.route("/api/clear", methods=["POST"])
@login_required
def api_clear():
    global alertas, siren_on, last_alert_time
    alertas = []
    siren_on = False
    last_alert_time = None
    return jsonify({"ok": True})


# ========= SIRENE (ÁUDIO) =========
@app.route("/tocar_sirene")
def tocar_sirene():
    caminho = os.path.join("static", "siren.mp3")
    if os.path.exists(caminho):
        return send_file(caminho)
    return "Arquivo de áudio não encontrado", 404


# ========= RELATÓRIO PDF =========
@app.route("/report.pdf")
@login_required
def report_pdf():
    """
    Gera relatório simples com:
    - Dados da escola
    - Últimos alertas
    """
    buffer = io.BytesIO()
    p = canvas.Canvas(buffer, pagesize=A4)

    largura, altura = A4
    y = altura - 50

    p.setFont("Helvetica-Bold", 16)
    p.drawString(50, y, "PROF-SAFE24 – Relatório de Ocorrências")
    y -= 30

    p.setFont("Helvetica", 12)
    p.drawString(50, y, f"Escola: {SCHOOL_NAME}")
    y -= 18
    p.drawString(50, y, f"Cidade/UF: {SCHOOL_CITY}")
    y -= 18
    p.drawString(50, y, f"Contato: {SCHOOL_CONTACT}")
    y -= 18
    p.drawString(50, y, f"Gerado em: {datetime.now().strftime('%d/%m/%Y %H:%M:%S')}")
    y -= 30

    p.setFont("Helvetica-Bold", 12)
    p.drawString(50, y, "Ocorrências registradas:")
    y -= 20

    p.setFont("Helvetica", 11)

    if not alertas:
        p.drawString(50, y, "Nenhum alerta registrado até o momento.")
    else:
        for alerta in alertas:
            if y < 80:
                p.showPage()
                y = altura - 50
                p.setFont("Helvetica", 11)

            linha = f"[{alerta['time']}] Prof.: {alerta['teacher']} | Sala: {alerta['room']} | Detalhes: {alerta['description']}"
            p.drawString(50, y, linha)
            y -= 15

    p.showPage()
    p.save()

    buffer.seek(0)
    return send_file(
        buffer,
        as_attachment=False,
        download_name="relatorio_prof_safe24.pdf",
        mimetype="application/pdf",
    )


# ========= RUN LOCAL =========
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)
