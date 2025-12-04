from flask import Flask, render_template, jsonify, request, send_file, redirect, url_for, session
import os
from datetime import datetime
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
            session.permanent = False  # Evita sessões muito longas
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
    try:
        # Tenta ler JSON, mas não força
        if request.is_json:
            data = request.get_json()
        else:
            # Se não for JSON, tenta ler como form data
            data = request.form.to_dict()
            
        if not data:
            return jsonify({"ok": False, "error": "Dados inválidos"}), 400
            
        teacher = data.get("teacher", "Professor")
        room = data.get("room", "Sala não informada")
        description = data.get("description", "Sem descrição")

        alerta = {
            "teacher": teacher[:50],  # Limita tamanho para segurança
            "room": room[:50],
            "description": description[:200],
            "ts": _now_str(),
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
                    "alerts": alertas[-50:],  # Retorna apenas últimos 50 alertas
                    "active_alerts": len(active_alerts),
                    "last_update": sistema_status["ultima_atualizacao"],
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
            
        return jsonify({"ok": True, "resolved": resolved})
        
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
        
        with data_lock:
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
        
    except ImportError:
        return "Biblioteca reportlab não encontrada", 500
    except Exception as e:
        app.logger.error(f"Erro em report_pdf: {str(e)}")
        return "Erro ao gerar relatório PDF", 500


# ---------- Healthcheck ----------

@app.route("/health")
def health():
    try:
        with data_lock:
            status = {
                "status": "ok",
                "alert_count": len(alertas),
                "active_alerts": len([a for a in alertas if not a["resolved"]]),
                "timestamp": _now_str()
            }
        return jsonify(status)
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500


# ---------- Limpeza periódica de alertas antigos (opcional) ----------
def limpar_alertas_antigos():
    """Limpa alertas com mais de 7 dias (executar em thread separada)"""
    import time
    while True:
        time.sleep(3600)  # Verifica a cada hora
        try:
            with data_lock:
                # Remove alertas com mais de 7 dias
                # (implementar se necessário armazenar datas como objetos datetime)
                pass
        except:
            pass


if __name__ == "__main__":
    # Inicia thread de limpeza (opcional)
    # cleaner_thread = threading.Thread(target=limpar_alertas_antigos, daemon=True)
    # cleaner_thread.start()
    
    port = int(os.environ.get("PORT", 5000))
    debug = os.environ.get("FLASK_DEBUG", "false").lower() == "true"
    
    # Configurações para produção
    if not debug:
        app.config.update(
            SESSION_COOKIE_SECURE=True,
            SESSION_COOKIE_HTTPONLY=True,
            SESSION_COOKIE_SAMESITE='Lax',
        )
    
    app.run(host="0.0.0.0", port=port, debug=debug, threaded=True)
