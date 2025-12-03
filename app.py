from flask import Flask, render_template, send_file, jsonify, request, redirect, url_for
import os
import datetime
from io import BytesIO

# PDF
try:
    from reportlab.lib.pagesizes import A4
    from reportlab.pdfgen import canvas
    HAS_REPORTLAB = True
except Exception:
    # Permite rodar mesmo sem reportlab instalado (ex.: primeiro teste local)
    HAS_REPORTLAB = False

app = Flask(__name__)

# ===== Configurações básicas =====
app.config['JSONIFY_PRETTYPRINT_REGULAR'] = False

# Segurança: usa variáveis de ambiente, com valores padrão de backup
app.secret_key = os.environ.get("SECRET_KEY", "spynet_PROFSAFE24_default_secret")
ADMIN_PASSWORD = os.environ.get("ADMIN_PASSWORD", "ProfSafe24@2025")

# ========= DADOS DA ESCOLA =========
# É AQUI QUE VOCÊ COLOCA OS DADOS DA ESCOLA PARA VENDER 👇
school_data = {
    "name": os.environ.get("SCHOOL_NAME", "Colégio Estadual SpyNet"),
    "phone": os.environ.get("SCHOOL_PHONE", "(11) 99999-9999"),
    "address": os.environ.get("SCHOOL_ADDRESS", "Av. Principal, 456 - Centro"),
    "director": os.environ.get("SCHOOL_DIRECTOR", "Diretora Maria Silva")
}

# Armazenamento em memória
alertas = []
sistema_status = {
    "sirene_ativa": False,
    "mutado": False,
    "ultima_atualizacao": None,
}

# ===== Rotas principais =====
@app.route("/")
def home():
    return render_template("home.html")

@app.route("/professor")
def professor():
    return render_template("professor.html")

@app.route("/central")
def central():
    # envia dados da escola para preencher o painel
    return render_template("central.html", school=school_data)

@app.route("/painel_publico")
def painel_publico():
    return render_template("painel_publico.html")

@app.route("/admin", methods=["GET", "POST"])
def admin():
    global school_data
    message = None
    if request.method == "POST":
        school_data["name"] = request.form.get("school_name", school_data["name"])
        school_data["phone"] = request.form.get("school_phone", school_data["phone"])
        school_data["address"] = request.form.get("school_address", school_data["address"])
        school_data["director"] = request.form.get("school_director", school_data["director"])
        message = "Dados da escola atualizados com sucesso."
    return render_template("admin.html", school=school_data, message=message)

@app.route("/login_central", methods=["GET", "POST"])
def login_central():
    error = None
    if request.method == "POST":
        # usa o campo "senha" do formulário (você já tem esse input no login_central.html)
        senha = request.form.get("senha", "")
        if senha == ADMIN_PASSWORD:
            return redirect(url_for("central"))
        else:
            error = "Senha incorreta. Tente novamente."
    return render_template("login_central.html", error=error)

# ===== Áudio da sirene =====
@app.route("/play-alarm")
def play_alarm():
    # usado pelo painel para testar a sirene
    try:
        return send_file("static/siren.mp3")
    except FileNotFoundError:
        return "Arquivo de áudio não encontrado", 404

@app.route("/tocar_sirene")
def tocar_sirene():
    # usado quando alerta é disparado
    try:
        return send_file("static/siren.mp3")
    except Exception as e:
        return f"Erro ao carregar sirene: {e}", 500

# ===== API de alertas =====
@app.route("/api/alert", methods=["POST"])
def receber_alerta():
    try:
        data = request.get_json() or {}
        novo_alerta = {
            "id": len(alertas) + 1,
            "teacher": data.get("teacher", "Professor"),
            "room": data.get("room", "Sala não informada"),
            "description": data.get("description", "Sem descrição"),
            "timestamp": datetime.datetime.now().strftime("%d/%m/%Y %H:%M:%S"),
            "resolved": False,
            "ts": datetime.datetime.now().strftime("%H:%M:%S"),
        }
        alertas.append(novo_alerta)
        sistema_status["sirene_ativa"] = True
        sistema_status["ultima_atualizacao"] = datetime.datetime.now().isoformat()
        return jsonify({"ok": True, "message": "Alerta recebido com sucesso"})
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 500

@app.route("/api/status", methods=["GET"])
def status_sistema():
    try:
        alertas_ativos = [a for a in alertas if not a["resolved"]]
        return jsonify({
            "ok": True,
            "siren": sistema_status["sirene_ativa"],
            "muted": sistema_status["mutado"],
            "alerts": alertas,
            "active_alerts": len(alertas_ativos),
            "last_update": sistema_status["ultima_atualizacao"],
            "school": school_data,
        })
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 500

@app.route("/api/siren", methods=["POST"])
def controlar_sirene():
    try:
        data = request.get_json() or {}
        action = data.get("action")
        if action == "on":
            sistema_status["sirene_ativa"] = True
            sistema_status["mutado"] = False
        elif action == "off":
            sistema_status["sirene_ativa"] = False
            sistema_status["mutado"] = False
        elif action == "mute":
            sistema_status["mutado"] = True
        sistema_status["ultima_atualizacao"] = datetime.datetime.now().isoformat()
        return jsonify({"ok": True, "siren": sistema_status["sirene_ativa"], "muted": sistema_status["mutado"]})
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 500

@app.route("/api/resolve", methods=["POST"])
def resolver_alerta():
    try:
        for alerta in alertas:
            if not alerta["resolved"]:
                alerta["resolved"] = True
                break
        alertas_ativos = [a for a in alertas if not a["resolved"]]
        if not alertas_ativos:
            sistema_status["sirene_ativa"] = False
        sistema_status["ultima_atualizacao"] = datetime.datetime.now().isoformat()
        return jsonify({"ok": True})
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 500

@app.route("/api/clear", methods=["POST"])
def limpar_alertas():
    try:
        alertas.clear()
        sistema_status["sirene_ativa"] = False
        sistema_status["ultima_atualizacao"] = datetime.datetime.now().isoformat()
        return jsonify({"ok": True})
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 500

@app.route("/acionar_alerta", methods=["POST"])
def acionar_alerta():
    try:
        novo_alerta = {
            "id": len(alertas) + 1,
            "teacher": "Professor",
            "room": "Local não informado",
            "description": "Alerta de pânico acionado",
            "timestamp": datetime.datetime.now().strftime("%d/%m/%Y %H:%M:%S"),
            "resolved": False,
            "ts": datetime.datetime.now().strftime("%H:%M:%S"),
        }
        alertas.append(novo_alerta)
        sistema_status["sirene_ativa"] = True
        sistema_status["ultima_atualizacao"] = datetime.datetime.now().isoformat()
        return jsonify({
            "success": True,
            "message": "Alerta de pânico acionado! Sirene ativada.",
            "alerta": novo_alerta,
        })
    except Exception as e:
        return jsonify({
            "success": False,
            "message": f"Erro: {e}",
        }), 500

# ===== Relatório em PDF =====
@app.route("/report.pdf")
def gerar_relatorio_pdf():
    if not HAS_REPORTLAB:
        return "Biblioteca reportlab não está instalada no servidor.", 500

    buffer = BytesIO()
    pdf = canvas.Canvas(buffer, pagesize=A4)
    width, height = A4

    y = height - 50
    pdf.setFont("Helvetica-Bold", 16)
    pdf.drawString(50, y, "Relatório de Ocorrências - PROF-SAFE24")
    y -= 30

    pdf.setFont("Helvetica", 11)
    pdf.drawString(50, y, f"Escola: {school_data.get('name', '')}")
    y -= 15
    pdf.drawString(50, y, f"Telefone: {school_data.get('phone', '')}")
    y -= 15
    pdf.drawString(50, y, f"Endereço: {school_data.get('address', '')}")
    y -= 15
    pdf.drawString(50, y, f"Diretor(a): {school_data.get('director', '')}")
    y -= 25

    pdf.setFont("Helvetica-Bold", 12)
    pdf.drawString(50, y, "Ocorrências registradas:")
    y -= 20

    pdf.setFont("Helvetica", 10)
    if not alertas:
        pdf.drawString(50, y, "Nenhum alerta registrado até o momento.")
    else:
        for alerta in alertas:
            linha = f"[{alerta.get('timestamp','')}] Sala {alerta.get('room','')} - {alerta.get('teacher','')} - {alerta.get('description','')}"
            if y < 80:
                pdf.showPage()
                y = height - 50
                pdf.setFont("Helvetica", 10)
            pdf.drawString(50, y, linha)
            y -= 14

    pdf.showPage()
    pdf.save()
    buffer.seek(0)
    return send_file(
        buffer,
        as_attachment=True,
        download_name="relatorio_prof_safe24.pdf",
        mimetype="application/pdf",
    )

# Health check
@app.route("/health")
def health_check():
    return jsonify({"status": "healthy"})

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    # debug=True apenas para desenvolvimento local
    app.run(host="0.0.0.0", port=port, debug=True)
