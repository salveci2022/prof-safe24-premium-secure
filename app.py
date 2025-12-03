import os
from datetime import datetime
from flask import (
    Flask, render_template, request, jsonify,
    send_file, redirect, url_for, session
)

app = Flask(__name__)

# ===========================
# SEGURANÇA – VARIÁVEIS .ENV
# ===========================
# Em Render: Environment → SECRET_KEY / ADMIN_PASSWORD
app.secret_key = os.environ.get("SECRET_KEY", "dev-key-change-me")
ADMIN_PASSWORD = os.environ.get("ADMIN_PASSWORD", "ProfSafe24@2025")

# Banco simples em memória
alertas = []
siren_on = False
siren_muted = False
last_alert_time = None


# ================================
# ROTAS DE PÁGINAS
# ================================
@app.route("/")
def home():
    return render_template("home.html")


@app.route("/professor")
def professor():
    return render_template("professor.html")


@app.route("/central")
def central():
    # Protege o painel central com login
    if not session.get("logged_in"):
        return redirect(url_for("login_central"))
    return render_template("central.html")


@app.route("/login_central", methods=["GET", "POST"])
def login_central():
    erro = None
    if request.method == "POST":
        senha = request.form.get("password", "")
        if senha == ADMIN_PASSWORD:
            session["logged_in"] = True
            return redirect(url_for("central"))
        else:
            erro = "Senha incorreta. Tente novamente."
    return render_template("login_central.html", error=erro)


@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("login_central"))


@app.route("/admin")
def admin():
    # se quiser, depois protege isso também com login
    return render_template("admin.html")


@app.route("/publico")
def publico():
    return render_template("painel_publico.html")


# ================================
# API – ENVIAR ALERTA
# ================================
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
    last_alert_time = datetime.now().strftime("%H:%M:%S")

    # Liga a sirene sempre que chega alerta (se não estiver mutada)
    if not siren_muted:
        siren_on = True

    return jsonify({"ok": True, "alerta": alerta})


# ================================
# API – STATUS
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
# API – LIGAR/DESLIGAR SIRENE
# ================================
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

    else:
        return jsonify({"ok": False, "error": "Ação inválida"}), 400


# ================================
# API – LIMPAR ALERTAS (RESET)
# ================================
@app.route("/api/clear", methods=["POST"])
def api_clear():
    global alertas, siren_on, last_alert_time
    alertas = []
    siren_on = False
    last_alert_time = None
    return jsonify({"ok": True})


# ========================================================
# TOCAR SIRENE USANDO SIREN.MP3
# ========================================================
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


# ================================
# EXECUTAR LOCALMENTE
# ================================
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)
