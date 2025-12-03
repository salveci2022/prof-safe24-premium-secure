from flask import Flask, render_template, request, jsonify, send_file
from datetime import datetime
from io import BytesIO
from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas
import os

app = Flask(__name__)

# Banco simples em memória
alertas = []
siren_on = False
siren_muted = False
last_alert_time = None

# ================================
# PÁGINAS
# ================================
@app.route("/")
def home():
    # se tiver home.html, usa; se não, manda direto p/ central
    try:
        return render_template("home.html")
    except Exception:
        return render_template("central.html")


@app.route("/professor")
def professor():
    return render_template("professor.html")


@app.route("/central")
def central():
    return render_template("central.html")


@app.route("/login_central", methods=["GET", "POST"])
def login_central():
    # login simples: qualquer POST entra
    if request.method == "POST":
        return render_template("central.html")
    return render_template("login_central.html")


# ================================
# API – ENVIAR ALERTA
# ================================
@app.route("/api/alert", methods=["POST"])
def api_alert():
    global siren_on, last_alert_time, siren_muted

    data = request.get_json() or {}
    teacher = data.get("teacher", "Professor(a)")
    room = data.get("room", "Sala / Local não informado")
    desc = data.get("description", "Alerta de pânico acionado")

    alerta = {
        "id": len(alertas) + 1,
        "teacher": teacher,
        "room": room,
        "description": desc,
        "time": datetime.now().strftime("%d/%m/%Y %H:%M:%S"),
        "status": "Ativo"
    }

    # alerta novo sempre no topo
    alertas.insert(0, alerta)
    last_alert_time = datetime.now().strftime("%d/%m/%Y %H:%M:%S")

    # liga sirene (se não estiver mutada)
    if not siren_muted:
        siren_on = True

    return jsonify({"ok": True, "alerta": alerta})


# ================================
# API – STATUS (Central fica lendo)
# ================================
@app.route("/api/status")
def api_status():
    return jsonify({
        "alertas": alertas,
        "siren_on": siren_on,
        "siren_muted": siren_muted,
        "last_alert_time": last_alert_time
    })


# ================================
# API – CONTROLE DA SIRENE
# ================================
@app.route("/api/siren", methods=["POST"])
def api_siren():
    global siren_on, siren_muted
    data = request.get_json() or {}
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


# ================================
# API – RESOLVER / LIMPAR ALERTAS
# ================================
@app.route("/api/resolve", methods=["POST"])
def api_resolve():
    global alertas, siren_on
    # marca todos como resolvidos
    for a in alertas:
        a["status"] = "Resolvido"
    siren_on = False
    return jsonify({"ok": True})


@app.route("/api/clear", methods=["POST"])
def api_clear():
    global alertas, siren_on, last_alert_time
    alertas = []
    siren_on = False
    last_alert_time = None
    return jsonify({"ok": True})


# ================================
# SIRENE (MP3 NA PASTA STATIC)
# ================================
@app.route("/tocar_sirene")
def tocar_sirene():
    caminho = os.path.join("static", "siren.mp3")
    if os.path.exists(caminho):
        return send_file(caminho)
    return "Arquivo de áudio não encontrado", 404


# ================================
# RELATÓRIO PDF
# ================================
@app.route("/report.pdf")
def gerar_relatorio():
    buffer = BytesIO()
    pdf = canvas.Canvas(buffer, pagesize=A4)
    largura, altura = A4

    pdf.setTitle("Relatório de Alertas - SpyNet Security")

    pdf.setFont("Helvetica-Bold", 16)
    pdf.drawString(50, altura - 50, "SPYNET SECURITY - Relatório de Alertas")
    pdf.setFont("Helvetica", 10)
    pdf.drawString(50, altura - 70,
                   f"Gerado em: {datetime.now().strftime('%d/%m/%Y %H:%M:%S')}")
    pdf.line(50, altura - 75, largura - 50, altura - 75)

    y = altura - 100
    pdf.setFont("Helvetica-Bold", 12)
    pdf.drawString(50, y, "Histórico")
    y -= 20
    pdf.setFont("Helvetica", 10)

    if not alertas:
        pdf.drawString(50, y, "Nenhum alerta registrado.")
    else:
        for alerta in alertas:
            linha = f"#{alerta['id']} - {alerta['time']} - {alerta['teacher']} - {alerta['room']}"
            status = alerta["status"]
            if y < 80:
                pdf.showPage()
                y = altura - 50
                pdf.setFont("Helvetica", 10)
            pdf.drawString(50, y, linha)
            y -= 14
            if y < 80:
                pdf.showPage()
                y = altura - 50
                pdf.setFont("Helvetica", 10)
            pdf.drawString(60, y, f"Descrição: {alerta['description']} | Status: {status}")
            y -= 16

    pdf.showPage()
    pdf.save()
    buffer.seek(0)

    return send_file(
        buffer,
        as_attachment=True,
        download_name="relatorio_alertas_spynet.pdf",
        mimetype="application/pdf"
    )


# ================================
# EXECUTAR LOCAL
# ================================
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)
