import os
import io
from datetime import datetime

from flask import (
    Flask,
    render_template,
    request,
    jsonify,
    send_file,
    redirect,
    url_for,
    session,
)

from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import A4

app = Flask(__name__)

# =====================================================
# SEGURANÇA BÁSICA
# =====================================================
app.secret_key = os.environ.get("SECRET_KEY", "prof_safe24_dev_secret")

ADMIN_PASSWORD = os.environ.get("ADMIN_PASSWORD", "ProfSafe24@VIP")

# Dados da escola (MUDE AQUI para cada cliente)
SCHOOL_DATA = {
    "nome": "Escola Modelo PROF-SAFE24",
    "cidade": "Cidade/UF",
    "telefone": "(00) 0000-0000",
}

# Banco simples em memória
alertas = []
siren_on = False
siren_muted = False
last_alert_time = None


# =====================================================
# ROTAS DE PÁGINAS
# =====================================================
@app.route("/")
def home():
    return render_template("home.html")


@app.route("/professor")
def professor():
    return render_template("professor.html")


@app.route("/central")
def central():
    # se quiser travar o acesso, descomente estas 3 linhas:
    # if not session.get("logado"):
    #     return redirect(url_for("login_central"))
    return render_template("central.html")


# LOGIN NO ESTILO SPYNET (GET + POST)
@app.route("/login_central", methods=["GET", "POST"])
def login_central():
    error = None
    if request.method == "POST":
        password = request.form.get("password", "")
        if password == ADMIN_PASSWORD:
            session["logado"] = True
            return redirect(url_for("central"))
        else:
            error = "Senha incorreta. Tente novamente."

    return render_template("login_central.html", error=error)


@app.route("/admin")
def admin():
    return render_template("admin.html")


@app.route("/publico")
def publico():
    return render_template("painel_publico.html")


# Alias para não dar 404 quando acessar /painel_publico
@app.route("/painel_publico")
def painel_publico_alias():
    return render_template("painel_publico.html")


# =====================================================
# API – ENVIAR ALERTA
# =====================================================
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


# =====================================================
# API – STATUS
# =====================================================
@app.route("/api/status")
def api_status():
    return jsonify(
        {
            "alertas": alertas,
            "siren_on": siren_on,
            "siren_muted": siren_muted,
            "last_alert_time": last_alert_time,
            "school": SCHOOL_DATA,
        }
    )


# =====================================================
# API – SIRENE
# =====================================================
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


# =====================================================
# API – LIMPAR ALERTAS
# =====================================================
@app.route("/api/clear", methods=["POST"])
def api_clear():
    global alertas, siren_on, last_alert_time
    alertas = []
    siren_on = False
    last_alert_time = None
    return jsonify({"ok": True})


# =====================================================
# SIRENE (MP3)
# =====================================================
@app.route("/play-alarm")
def play_alarm():
    caminho = os.path.join("static", "siren.mp3")
    if os.path.exists(caminho):
        return send_file(caminho)
    return "Arquivo de áudio não encontrado", 404


@app.route("/tocar_sirene")
def tocar_sirene():
    caminho = os.path.join("static", "siren.mp3")
    if os.path.exists(caminho):
        return send_file(caminho)
    return "Erro ao carregar sirene", 500


# =====================================================
# RELATÓRIO EM PDF – /report.pdf
# =====================================================
@app.route("/report.pdf")
def report_pdf():
    """
    Gera um relatório simples dos alertas em PDF.
    URL: /report.pdf
    """

    buffer = io.BytesIO()
    p = canvas.Canvas(buffer, pagesize=A4)
    width, height = A4

    # Cabeçalho
    p.setFont("Helvetica-Bold", 16)
    p.drawString(50, height - 50, "Relatório de Alertas – PROF-SAFE24")

    p.setFont("Helvetica", 11)
    p.drawString(50, height - 70, f"Escola: {SCHOOL_DATA['nome']}")
    p.drawString(50, height - 85, f"Cidade/UF: {SCHOOL_DATA['cidade']}")
    p.drawString(50, height - 100, f"Telefone: {SCHOOL_DATA['telefone']}")
    p.drawString(
        50,
        height - 120,
        "Gerado em: " + datetime.now().strftime("%d/%m/%Y %H:%M:%S"),
    )

    # Lista de alertas
    y = height - 150
    p.setFont("Helvetica-Bold", 12)
    p.drawString(50, y, "Alertas registradados:")
    y -= 20
    p.setFont("Helvetica", 10)

    if not alertas:
        p.drawString(50, y, "Nenhum alerta registrado até o momento.")
    else:
        for alerta in alertas:
            linha = (
                f"{alerta['time']} | Sala: {alerta['room']} | "
                f"Prof: {alerta['teacher']} | {alerta['description']}"
            )
            p.drawString(50, y, linha)
            y -= 15
            if y < 60:
                p.showPage()
                y = height - 50
                p.setFont("Helvetica", 10)

    p.showPage()
    p.save()
    buffer.seek(0)

    return send_file(
        buffer,
        as_attachment=True,
        download_name="report.pdf",
        mimetype="application/pdf",
    )


# =====================================================
# EXECUTAR LOCAL
# =====================================================
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)
