import os
from io import BytesIO
from datetime import datetime

from flask import (
    Flask,
    render_template,
    request,
    jsonify,
    send_file,
    redirect,
    url_for,
)

from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas

app = Flask(__name__)

# =========================
# CONFIGURAÇÕES DE SEGURANÇA
# =========================

app.secret_key = os.environ.get("SECRET_KEY", "dev_inseguro_ProfSafe24")
ADMIN_PASSWORD = os.environ.get("ADMIN_PASSWORD", "ProfSafe24@2025")

# =========================
# DADOS DA ESCOLA
# >>> EDITE ESTES 3 CAMPOS PARA CADA CLIENTE
# =========================
SCHOOL_NAME = "Escola Municipal Modelo PROF-SAFE24"
SCHOOL_ADDRESS = "Rua Exemplo, 123 – Bairro, Cidade/UF"
SCHOOL_RESPONSAVEL = "Diretor(a): Nome do Responsável"


# =========================
# BANCO SIMPLES EM MEMÓRIA
# =========================
alertas = []
siren_on = False
siren_muted = False
last_alert_time = None


# =========================
# ROTAS DE PÁGINAS
# =========================
@app.route("/")
def home():
    return render_template("home.html")


@app.route("/professor")
def professor():
    return render_template("professor.html")


@app.route("/central")
def central():
    return render_template("central.html")


# LOGIN – usa senha do ADMIN_PASSWORD (Render)
@app.route("/login_central", methods=["GET", "POST"])
def login_central():
    error = None
    if request.method == "POST":
        senha_digitada = request.form.get("password", "")
        if senha_digitada == ADMIN_PASSWORD:
            return redirect(url_for("central"))
        else:
            error = "Senha incorreta. Tente novamente."
    return render_template("login_central.html", error=error)


@app.route("/admin")
def admin():
    return render_template("admin.html")


@app.route("/painel_publico")
def painel_publico():
    return render_template("painel_publico.html")


# =========================
# API – ENVIAR ALERTA
# =========================
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
        "time": datetime.now().strftime("%H:%M:%S"),
    }

    alertas.insert(0, alerta)
    last_alert_time = datetime.now().strftime("%H:%M:%S")

    if not siren_muted:
        siren_on = True

    return jsonify({"ok": True, "alerta": alerta})


# =========================
# API – STATUS
# =========================
@app.route("/api/status")
def api_status():
    return jsonify(
        {
            "alertas": alertas,
            "siren_on": siren_on,
            "siren_muted": siren_muted,
            "last_alert_time": last_alert_time,
        }
    )


# =========================
# API – CONTROLE DA SIRENE
# =========================
@app.route("/api/siren", methods=["POST"])
def api_siren():
    global siren_on, siren_muted

    data = request.get_json()
    action = data.get("action")

    if action == "on":
        if not siren_muted:
            siren_on = True
        return jsonify({"ok": True, "siren_on": siren_on})

    elif action == "off":
        siren_on = False
        return jsonify({"ok": True, "siren_on": siren_on})

    elif action == "mute":
        siren_muted = True
        siren_on = False
        return jsonify({"ok": True, "siren_muted": siren_muted})

    elif action == "unmute":
        siren_muted = False
        return jsonify({"ok": True, "siren_muted": siren_muted})

    return jsonify({"ok": False, "error": "Ação inválida"}), 400


# =========================
# API – LIMPAR ALERTAS
# =========================
@app.route("/api/clear", methods=["POST"])
def api_clear():
    global alertas, siren_on, last_alert_time
    alertas = []
    siren_on = False
    last_alert_time = None
    return jsonify({"ok": True})


# =========================
# SIRENE (ÁUDIO MP3)
# =========================
@app.route("/tocar_sirene")
def tocar_sirene():
    caminho = os.path.join("static", "siren.mp3")
    if os.path.exists(caminho):
        return send_file(caminho)
    return "Erro ao carregar sirene", 500


# =========================
# RELATÓRIO PDF EM /report.pdf
# =========================
@app.route("/report.pdf")
def gerar_relatorio_pdf():
    """
    Gera um PDF simples com:
    - Dados da escola
    - Lista de alertas
    """
    buffer = BytesIO()
    p = canvas.Canvas(buffer, pagesize=A4)
    largura, altura = A4
    y = altura - 50

    # Cabeçalho
    p.setFont("Helvetica-Bold", 16)
    p.drawString(50, y, f"Relatório de Alertas – {SCHOOL_NAME}")
    y -= 30

    p.setFont("Helvetica", 11)
    p.drawString(50, y, f"Escola: {SCHOOL_NAME}")
    y -= 15
    p.drawString(50, y, f"Endereço: {SCHOOL_ADDRESS}")
    y -= 15
    p.drawString(50, y, f"{SCHOOL_RESPONSAVEL}")
    y -= 25

    p.setFont("Helvetica-Bold", 13)
    p.drawString(50, y, "Alertas Registrados")
    y -= 20
    p.setFont("Helvetica", 11)

    if not alertas:
        p.drawString(50, y, "Nenhum alerta registrado até o momento.")
    else:
        for alerta in alertas:
            if y < 80:
                p.showPage()
                y = altura - 50
                p.setFont("Helvetica-Bold", 13)
                p.drawString(50, y, "Alertas (continuação)")
                y -= 20
                p.setFont("Helvetica", 11)

            linha1 = f"Hora: {alerta['time']}  |  Sala: {alerta['room']}  |  Professor: {alerta['teacher']}"
            p.drawString(50, y, linha1)
            y -= 15

            linha2 = f"Descrição: {alerta['description']}"
            p.drawString(50, y, linha2)
            y -= 25

    p.showPage()
    p.save()
    buffer.seek(0)

    return send_file(
        buffer,
        as_attachment=True,
        download_name="relatorio_prof_safe24.pdf",
        mimetype="application/pdf",
    )


# =========================
# MAIN
# =========================
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)
