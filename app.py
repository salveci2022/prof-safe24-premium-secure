from flask import Flask, render_template, request, jsonify, send_file
from datetime import datetime
from io import BytesIO
from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas
import os
import json  # ✅ ADICIONADO

app = Flask(__name__)

# ================================
# "BANCO DE DADOS" EM MEMÓRIA
# ================================
alertas = []
siren_on = False
siren_muted = False
last_alert_time = None


# ================================
# ESCOLAS (schools.json) ✅ ADICIONADO
# ================================
def carregar_escola():
    """
    Lê schools.json com segurança e retorna os dados da escola.
    Uso: /central?school=colegio_spynet
    Se não existir, retorna um padrão (não quebra o sistema).
    """
    school_key = (request.args.get("school") or "").strip()

    # padrão seguro
    padrao = {
        "nome": "SPYNET SECURITY",
        "endereco": "—",
        "telefone": "—",
        "diretor": "—",
        "logo": ""
    }

    caminho = os.path.join(app.root_path, "schools.json")

    if not os.path.exists(caminho):
        return padrao

    try:
        with open(caminho, "r", encoding="utf-8") as f:
            schools = json.load(f)

        # se não passar ?school=, usa padrão
        if not school_key:
            return padrao

        # se a chave existir, usa, senão padrão
        return schools.get(school_key, padrao)

    except Exception:
        return padrao


# ================================
# PÁGINAS
# ================================
@app.route("/")
def home():
    # Tela premium de apresentação do sistema
    return render_template("home.html")


@app.route("/professor")
def professor():
    return render_template("professor.html")


@app.route("/central")
def central():
    # ✅ agora envia os dados da escola para o central.html
    school_data = carregar_escola()
    return render_template("central.html", school=school_data)


@app.route("/login_central", methods=["GET", "POST"])
def login_central():
    # Login simples (você pode depois colocar usuário/senha reais)
    if request.method == "POST":
        # Aqui poderia validar credenciais
        return render_template("central.html")
    return render_template("login_central.html")


@app.route("/painel_publico")
def painel_publico():
    # Painel público para TV / comunidade
    return render_template("painel_publico.html")


# ✅ NOVA ROTA (SEM MEXER EM NADA DO SISTEMA)
# Serve apenas para abrir o seu admin.html
@app.route("/admin")
def admin():
    return render_template("admin.html")


# ================================
# API – ENVIAR ALERTA (PAINEL DO PROFESSOR)
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
        "status": "Ativo",
    }

    # novo alerta sempre no topo
    alertas.insert(0, alerta)
    last_alert_time = alerta["time"]

    # liga sirene se não estiver mutada
    if not siren_muted:
        siren_on = True

    return jsonify({"ok": True, "alerta": alerta})


# ================================
# API – STATUS (Central + Painel Público)
# ================================
@app.route("/api/status")
def api_status():
    """
    Esta resposta foi pensada para funcionar AO MESMO TEMPO com:
      - central.html (usa: alertas, siren_on, last_alert_time)
      - painel_publico.html (usa: ok, alerts, siren, muted, active_alerts, total_alerts, last_update)
    """
    # contagens para os painéis
    total_alerts = len(alertas)
    active_alerts = sum(1 for a in alertas if a.get("status") == "Ativo")

    # formato mais "bonito" para o painel público
    alerts_public = [
        {
            "teacher": a.get("teacher"),
            "room": a.get("room"),
            "description": a.get("description"),
            "ts": a.get("time"),
            "resolved": a.get("status") != "Ativo",
        }
        for a in alertas
    ]

    return jsonify(
        {
            # formato antigo (Painel Central)
            "alertas": alertas,
            "siren_on": siren_on,
            "siren_muted": siren_muted,
            "last_alert_time": last_alert_time,
            # formato novo (Painel Público)
            "ok": True,
            "alerts": alerts_public,
            "siren": siren_on,
            "muted": siren_muted,
            "active_alerts": active_alerts,
            "total_alerts": total_alerts,
            "last_update": last_alert_time,
        }
    )


# ================================
# API – CONTROLE DA SIRENE (CENTRAL)
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
    pdf.drawString(
        50,
        altura - 70,
        f"Gerado em: {datetime.now().strftime('%d/%m/%Y %H:%M:%S')}",
    )
    pdf.line(50, altura - 75, largura - 50, altura - 75)

    y = altura - 100
    pdf.setFont("Helvetica-Bold", 12)
    pdf.drawString(50, y, "Histórico de Alertas")
    y -= 20
    pdf.setFont("Helvetica", 10)

    if not alertas:
        pdf.drawString(50, y, "Nenhum alerta registrado até o momento.")
    else:
        for alerta in alertas:
            if y < 80:
                pdf.showPage()
                y = altura - 50
                pdf.setFont("Helvetica", 10)

            linha = f"#{alerta['id']} - {alerta['time']} - {alerta['teacher']} - {alerta['room']}"
            status = alerta["status"]
            pdf.drawString(50, y, linha)
            y -= 14
            pdf.drawString(60, y, f"Status: {status} | Descrição: {alerta['description']}")
            y -= 18

    pdf.showPage()
    pdf.save()
    buffer.seek(0)

    return send_file(
        buffer,
        as_attachment=True,
        download_name="relatorio_alertas_spynet.pdf",
        mimetype="application/pdf",
    )


# ================================
# EXECUTAR LOCAL
# ================================
if __name__ == "__main__":
    # Para testes locais
    app.run(host="0.0.0.0", port=5000, debug=True)
