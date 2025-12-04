from flask import Flask, render_template, jsonify, request, send_file, redirect, url_for, session
import os
from datetime import datetime, timezone
from io import BytesIO
import threading

app = Flask(__name__)

# ---------- Configuração segura ----------
app.secret_key = os.environ.get("SECRET_KEY", "prof_safe24_dev_secret")
ADMIN_PASSWORD = os.environ.get("ADMIN_PASSWORD", "ProfSafe24@VIP")

SCHOOL_NAME = os.environ.get("SCHOOL_NAME", "Escola Modelo SPYNET")
SCHOOL_ADDRESS = os.environ.get("SCHOOL_ADDRESS", "Av. Principal, 456 - Centro")
SCHOOL_CITY = os.environ.get("SCHOOL_CITY", "Brasília - DF")
SCHOOL_PHONE = os.environ.get("SCHOOL_PHONE", "(61) 99999-0000")
SCHOOL_DIRECTOR = os.environ.get("SCHOOL_DIRECTOR", "Maria Silva Oliveira")

# ---------- Estado em memória com lock ----------
alertas = []
sistema_status = {
    "sirene_ativa": False,
    "mutado": False,
    "ultima_atualizacao": None,
}
data_lock = threading.Lock()


def _now_str():
    """Retorna data/hora atual no formato brasileiro"""
    # Usa hora local do Brasil
    agora = datetime.now()
    return agora.strftime("%d/%m/%Y %H:%M:%S")


def _now_iso():
    """Retorna data/hora em formato ISO para JavaScript"""
    agora = datetime.now()
    return agora.isoformat()


def _now_for_report():
    """Formato mais legível para relatórios"""
    agora = datetime.now()
    dias_semana = ["Segunda", "Terça", "Quarta", "Quinta", "Sexta", "Sábado", "Domingo"]
    meses = ["Janeiro", "Fevereiro", "Março", "Abril", "Maio", "Junho", 
             "Julho", "Agosto", "Setembro", "Outubro", "Novembro", "Dezembro"]
    
    return {
        "dia_semana": dias_semana[agora.weekday()],
        "dia": agora.day,
        "mes": meses[agora.month - 1],
        "ano": agora.year,
        "hora": agora.strftime("%H:%M:%S")
    }


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
            session.permanent = False
            return redirect(url_for("central"))
        else:
            error = "Senha inválida. Tente novamente."

    return render_template("login_central.html", error=error, agora=_now_str())


@app.route("/logout_central")
def logout_central():
    session.pop("admin_logged", None)
    return redirect(url_for("login_central"))


@app.route("/central")
def central():
    if not session.get("admin_logged"):
        return redirect(url_for("login_central"))
    return render_template("central.html", agora=_now_str())


# ---------- APIs de alerta e status ----------

@app.route("/api/alert", methods=["POST"])
def api_alert():
    try:
        if request.is_json:
            data = request.get_json()
        else:
            data = request.form.to_dict()
            
        if not data:
            return jsonify({"ok": False, "error": "Dados inválidos"}), 400
            
        teacher = data.get("teacher", "Professor")
        room = data.get("room", "Sala não informada")
        description = data.get("description", "Sem descrição")

        alerta = {
            "teacher": teacher[:50],
            "room": room[:50],
            "description": description[:200],
            "ts": _now_str(),
            "timestamp_iso": _now_iso(),
            "resolved": False,
        }
        
        with data_lock:
            alertas.append(alerta)
            sistema_status["sirene_ativa"] = True
            sistema_status["ultima_atualizacao"] = _now_str()

        return jsonify({"ok": True, "alert": alerta})
        
    except Exception as e:
        app.logger.error(f"Erro em api_alert: {str(e)}")
        return jsonify({"ok": False, "error": "Erro interno do servidor"}), 500


@app.route("/api/status")
def api_status():
    try:
        with data_lock:
            active_alerts = [a for a in alertas if not a["resolved"]]
            return jsonify(
                {
                    "siren": sistema_status["sirene_ativa"],
                    "muted": sistema_status["mutado"],
                    "alerts": alertas[-50:],
                    "active_alerts": len(active_alerts),
                    "last_update": sistema_status["ultima_atualizacao"],
                    "server_time": _now_str(),
                    "server_time_iso": _now_iso(),
                }
            )
    except Exception as e:
        app.logger.error(f"Erro em api_status: {str(e)}")
        return jsonify({"ok": False, "error": "Erro interno do servidor"}), 500


@app.route("/api/siren", methods=["POST"])
def api_siren():
    try:
        if request.is_json:
            data = request.get_json()
        else:
            data = request.form.to_dict()
            
        if not data:
            return jsonify({"ok": False, "error": "Dados inválidos"}), 400
            
        action = data.get("action")
        
        with data_lock:
            if action == "on":
                sistema_status["sirene_ativa"] = True
                sistema_status["mutado"] = False
            elif action == "off":
                sistema_status["sirene_ativa"] = False
            elif action == "mute":
                sistema_status["mutado"] = True
            elif action == "unmute":
                sistema_status["mutado"] = False
            elif action == "clear":
                for a in alertas:
                    a["resolved"] = True
                sistema_status["sirene_ativa"] = False
            else:
                return jsonify({"ok": False, "error": "Ação inválida"}), 400

            sistema_status["ultima_atualizacao"] = _now_str()
            
        return jsonify(
            {
                "ok": True,
                "siren": sistema_status["sirene_ativa"],
                "muted": sistema_status["mutado"],
                "server_time": _now_str(),
            }
        )
        
    except Exception as e:
        app.logger.error(f"Erro em api_siren: {str(e)}")
        return jsonify({"ok": False, "error": "Erro interno do servidor"}), 500


@app.route("/api/resolve", methods=["POST"])
def api_resolve():
    try:
        with data_lock:
            # Marca o primeiro alerta não resolvido como resolvido
            resolved = False
            for a in alertas:
                if not a["resolved"]:
                    a["resolved"] = True
                    resolved = True
                    break
            
            # Se não houver mais alertas abertos, desliga a sirene
            if not any(not a["resolved"] for a in alertas):
                sistema_status["sirene_ativa"] = False
                
            sistema_status["ultima_atualizacao"] = _now_str()
            
        return jsonify({"ok": True, "resolved": resolved, "server_time": _now_str()})
        
    except Exception as e:
        app.logger.error(f"Erro em api_resolve: {str(e)}")
        return jsonify({"ok": False, "error": "Erro interno do servidor"}), 500


# ---------- Áudio da sirene ----------

@app.route("/tocar_sirene")
def tocar_sirene():
    try:
        siren_path = os.path.join(app.static_folder, "siren.mp3")
        if not os.path.exists(siren_path):
            return "Arquivo de áudio não encontrado", 404
        return send_file(siren_path, mimetype="audio/mpeg")
    except Exception as e:
        app.logger.error(f"Erro em tocar_sirene: {str(e)}")
        return "Erro interno do servidor", 500


# ---------- Relatório em PDF ----------

@app.route("/report.pdf")
def report_pdf():
    try:
        from reportlab.lib.pagesizes import A4
        from reportlab.pdfgen import canvas
        from reportlab.lib.utils import ImageReader
        import io
        
        buffer = BytesIO()
        c = canvas.Canvas(buffer, pagesize=A4)
        width, height = A4
        
        # Data formatada para o relatório
        report_date = _now_for_report()

        # Cabeçalho
        y = height - 50
        c.setFont("Helvetica-Bold", 18)
        c.drawString(50, y, "RELATÓRIO DE ALERTAS - PROF-SAFE24")
        y -= 25
        
        c.setFont("Helvetica", 10)
        c.drawString(50, y, f"Data de emissão: {report_date['dia_semana']}, {report_date['dia']} de {report_date['mes']} de {report_date['ano']} - {report_date['hora']}")
        y -= 25
        
        c.setFont("Helvetica-Bold", 12)
        c.drawString(50, y, "INFORMAÇÕES DA ESCOLA:")
        y -= 15
        
        c.setFont("Helvetica", 10)
        c.drawString(50, y, f"• Escola: {SCHOOL_NAME}")
        y -= 15
        c.drawString(50, y, f"• Endereço: {SCHOOL_ADDRESS}")
        y -= 15
        c.drawString(50, y, f"• Cidade: {SCHOOL_CITY}")
        y -= 15
        c.drawString(50, y, f"• Telefone: {SCHOOL_PHONE}")
        y -= 15
        c.drawString(50, y, f"• Diretor(a): {SCHOOL_DIRECTOR}")
        y -= 30
        
        # Estatísticas
        with data_lock:
            total_alertas = len(alertas)
            alertas_ativos = len([a for a in alertas if not a["resolved"]])
            alertas_resolvidos = total_alertas - alertas_ativos
        
        c.setFont("Helvetica-Bold", 12)
        c.drawString(50, y, "ESTATÍSTICAS:")
        y -= 15
        
        c.setFont("Helvetica", 10)
        c.drawString(50, y, f"• Total de alertas: {total_alertas}")
        y -= 15
        c.drawString(50, y, f"• Alertas ativos: {alertas_ativos}")
        y -= 15
        c.drawString(50, y, f"• Alertas resolvidos: {alertas_resolvidos}")
        y -= 30
        
        # Lista de alertas
        c.setFont("Helvetica-Bold", 12)
        c.drawString(50, y, "LISTA DE ALERTAS DETALHADA:")
        y -= 20
        
        c.setFont("Helvetica", 9)
        if not alertas:
            c.drawString(50, y, "Nenhum alerta registrado até o momento.")
            y -= 15
        else:
            # Cabeçalho da tabela
            c.setFont("Helvetica-Bold", 9)
            c.drawString(50, y, "Data/Hora")
            c.drawString(120, y, "Professor")
            c.drawString(200, y, "Sala")
            c.drawString(280, y, "Status")
            c.drawString(350, y, "Descrição")
            y -= 15
            
            c.setFont("Helvetica", 8)
            c.line(50, y, width-50, y)
            y -= 10
            
            with data_lock:
                for idx, a in enumerate(reversed(alertas), start=1):
                    if y < 80:
                        c.showPage()
                        y = height - 50
                        c.setFont("Helvetica", 8)
                    
                    status = "RESOLVIDO" if a.get("resolved") else "ATIVO"
                    status_color = "green" if a.get("resolved") else "red"
                    
                    # Data/Hora
                    c.drawString(50, y, a.get("ts", "N/A"))
                    # Professor
                    c.drawString(120, y, a.get("teacher", "N/A")[:15])
                    # Sala
                    c.drawString(200, y, a.get("room", "N/A")[:10])
                    # Status
                    c.setFillColor(status_color)
                    c.drawString(280, y, status)
                    c.setFillColor("black")
                    # Descrição
                    desc = a.get("description", "Sem descrição")[:30]
                    c.drawString(350, y, desc)
                    
                    y -= 15
                    
                    # Linha divisória
                    if idx < len(alertas):
                        c.line(50, y, width-50, y)
                        y -= 5

        # Rodapé
        c.showPage()
        y = height - 50
        c.setFont("Helvetica-Oblique", 8)
        c.drawString(50, y, "Este relatório foi gerado automaticamente pelo sistema PROF-SAFE24.")
        y -= 15
        c.drawString(50, y, "Sistema desenvolvido para segurança escolar - Todos os direitos reservados.")
        
        c.save()
        buffer.seek(0)
        
        return send_file(
            buffer,
            as_attachment=True,
            download_name=f"relatorio_alertas_{datetime.now().strftime('%Y%m%d_%H%M%S')}.pdf",
            mimetype="application/pdf",
        )
        
    except ImportError:
        return "Biblioteca reportlab não encontrada", 500
    except Exception as e:
        app.logger.error(f"Erro em report_pdf: {str(e)}")
        return f"Erro ao gerar relatório PDF: {str(e)}", 500


# ---------- API para obter hora do servidor ----------

@app.route("/api/server_time")
def api_server_time():
    """Retorna a hora atual do servidor"""
    return jsonify({
        "datetime": _now_str(),
        "datetime_iso": _now_iso(),
        "timestamp": datetime.now().timestamp(),
        "timezone": "America/Sao_Paulo",
    })


# ---------- Healthcheck ----------

@app.route("/health")
def health():
    try:
        with data_lock:
            status = {
                "status": "ok",
                "server_time": _now_str(),
                "alert_count": len(alertas),
                "active_alerts": len([a for a in alertas if not a["resolved"]]),
                "timestamp": datetime.now().isoformat()
            }
        return jsonify(status)
    except Exception as e:
        return jsonify({"status": "error", "message": str(e), "server_time": _now_str()}), 500


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    debug = os.environ.get("FLASK_DEBUG", "false").lower() == "true"
    
    if not debug:
        app.config.update(
            SESSION_COOKIE_SECURE=True,
            SESSION_COOKIE_HTTPONLY=True,
            SESSION_COOKIE_SAMESITE='Lax',
        )
    
    print(f"Servidor iniciado em: {_now_str()}")
    app.run(host="0.0.0.0", port=port, debug=debug, threaded=True)
