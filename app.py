from flask import Flask, render_template, jsonify, request, send_file, redirect, url_for, session
import os
from datetime import datetime
from io import BytesIO

app = Flask(__name__)

# ---------- Configuração segura ----------
app.secret_key = os.environ.get("SECRET_KEY", "prof_safe24_dev_secret")
ADMIN_PASSWORD = os.environ.get("ADMIN_PASSWORD", "ProfSafe24@VIP")

SCHOOL_NAME = os.environ.get("SCHOOL_NAME", "Escola Modelo SPYNET")
SCHOOL_ADDRESS = os.environ.get("SCHOOL_ADDRESS", "Av. Principal, 456 - Centro")
SCHOOL_CITY = os.environ.get("SCHOOL_CITY", "Brasília - DF")
SCHOOL_PHONE = os.environ.get("SCHOOL_PHONE", "(61) 99999-0000")
SCHOOL_DIRECTOR = os.environ.get("SCHOOL_DIRECTOR", "Maria Silva Oliveira")

# ---------- Estado em memória ----------
alertas = []
sistema_status = {
    "sirene_ativa": False,
    "mutado": False,
    "ultima_atualizacao": None,
}


def _now_str():
    return datetime.now().strftime("%d/%m/%Y %H:%M:%S")


# ---------- Rotas de páginas ----------

@app.route("/")
def home():
    return render_template("home.html")


@app.route("/professor")
def professor():
    return render_template("professor.html")


@app.route("/painel_publico")
def painel_publico():
    return render_template("painel_publico.html")


@app.route("/admin")
def admin():
    return render_template("admin.html")


# ----------- Login da Central -----------

@app.route("/login_central", methods=["GET", "POST"])
def login_central():
    error = None
    if request.method == "POST":
        # pega do form (HTML) ou de JSON
        password = None
        if request.is_json:
            data = request.get_json(silent=True) or {}
            password = data.get("password") or data.get("senha")
        else:
            password = request.form.get("password") or request.form.get("senha")

        if password == ADMIN_PASSWORD:
            session["admin_logged"] = True
            return redirect(url_for("central"))
        else:
            error = "Senha inválida. Tente novamente."

    return render_template("login_central.html", error=error)


@app.route("/logout_central")
def logout_central():
    session.pop("admin_logged", None)
    return redirect(url_for("login_central"))


@app.route("/central")
def central():
    if not session.get("admin_logged"):
        return redirect(url_for("login_central"))
    return render_template("central.html")


# ---------- APIs de alerta e status ----------

@app.route("/api/alert", methods=["POST"])
def api_alert():
    data = request.get_json(force=True, silent=True) or {}
    teacher = data.get("teacher") or "Professor"
    room = data.get("room") or "Sala não informada"
    description = data.get("description") or "Sem descrição"

    alerta = {
        "teacher": teacher,
        "room": room,
        "description": description,
        "ts": _now_str(),
        "resolved": False,
    }
    alertas.append(alerta)

    sistema_status["sirene_ativa"] = True
    sistema_status["ultima_atualizacao"] = _now_str()

    return jsonify({"ok": True, "alert": alerta})


@app.route("/api/status")
def api_status():
    active_alerts = [a for a in alertas if not a["resolved"]]
    return jsonify(
        {
            "siren": sistema_status["sirene_ativa"],
            "muted": sistema_status["mutado"],
            "alerts": alertas,
            "active_alerts": len(active_alerts),
            "last_update": sistema_status["ultima_atualizacao"],
        }
    )


@app.route("/api/siren", methods=["POST"])
def api_siren():
    data = request.get_json(force=True, silent=True) or {}
    action = data.get("action")

    if action == "on":
        sistema_status["sirene_ativa"] = True
    elif action == "off":
        sistema_status["sirene_ativa"] = False
    elif action == "mute":
        sistema_status["mutado"] = True
    elif action == "unmute":
        sistema_status["mutado"] = False
    elif action == "clear":
        for a in alertas:
            a["resolved"] = True
    else:
        return jsonify({"ok": False, "error": "Ação inválida"}), 400

    sistema_status["ultima_atualizacao"] = _now_str()
    return jsonify(
        {
            "ok": True,
            "siren": sistema_status["sirene_ativa"],
            "muted": sistema_status["mutado"],
        }
    )


@app.route("/api/resolve", methods=["POST"])
def api_resolve():
    # Marca o primeiro alerta não resolvido como resolvido
    for a in alertas:
        if not a["resolved"]:
            a["resolved"] = True
            sistema_status["ultima_atualizacao"] = _now_str()
            break
    # Se não houver mais alertas abertos, desliga a sirene
    if not any(not a["resolved"] for a in alertas):
        sistema_status["sirene_ativa"] = False
    return jsonify({"ok": True})


# ---------- Áudio da sirene ----------

@app.route("/tocar_sirene")
def tocar_sirene():
    siren_path = os.path.join(app.static_folder, "siren.mp3")
    if not os.path.exists(siren_path):
        return "Arquivo de áudio não encontrado", 404
    return send_file(siren_path, mimetype="audio/mpeg")


# ---------- Relatório em PDF ----------

@app.route("/report.pdf")
def report_pdf():
    try:
        from reportlab.lib.pagesizes import A4
        from reportlab.pdfgen import canvas
    except Exception as e:
        return f"Biblioteca reportlab não encontrada: {e}", 500

    buffer = BytesIO()
    c = canvas.Canvas(buffer, pagesize=A4)
    width, height = A4

    y = height - 50
    c.setFont("Helvetica-Bold", 16)
    c.drawString(50, y, "Relatório de Alertas - PROF-SAFE24")
    y -= 30

    c.setFont("Helvetica", 11)
    c.drawString(50, y, f"Escola: {SCHOOL_NAME}")
    y -= 15
    c.drawString(50, y, f"Endereço: {SCHOOL_ADDRESS} - {SCHOOL_CITY}")
    y -= 15
    c.drawString(50, y, f"Telefone: {SCHOOL_PHONE}")
    y -= 15
    c.drawString(50, y, f"Diretor(a): {SCHOOL_DIRECTOR}")
    y -= 25

    c.drawString(50, y, f"Data de emissão: {_now_str()}")
    y -= 25

    c.setFont("Helvetica-Bold", 12)
    c.drawString(50, y, "Alertas registrados:")
    y -= 20

    c.setFont("Helvetica", 10)
    if not alertas:
        c.drawString(50, y, "Nenhum alerta registrado até o momento.")
    else:
        for idx, a in enumerate(alertas, start=1):
            if y < 80:
                c.showPage()
                y = height - 50
                c.setFont("Helvetica", 10)
            status = "Resolvido" if a.get("resolved") else "Pendente"
            linha = f"{idx}. {a.get('ts')} | Prof: {a.get('teacher')} | Sala: {a.get('room')} | {status}"
            c.drawString(50, y, linha)
            y -= 15

    c.showPage()
    c.save()
    buffer.seek(0)
    return send_file(
        buffer,
        as_attachment=True,
        download_name="relatorio_prof_safe24.pdf",
        mimetype="application/pdf",
    )


# ---------- Healthcheck ----------

@app.route("/health")
def health():
    return jsonify({"status": "ok"})


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
