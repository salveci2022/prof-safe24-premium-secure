from flask import Flask, render_template, jsonify, request, send_file, redirect, url_for, session
import os
from datetime import datetime, timedelta
from io import BytesIO
import threading
import time
import json

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

# Cache para o arquivo de áudio
siren_audio_cache = None

def _now_str():
    """Retorna data/hora atual no formato brasileiro CORRETO"""
    agora = datetime.now()
    return agora.strftime("%d/%m/%Y %H:%M:%S")

def _now_iso():
    """Retorna data/hora em formato ISO para JavaScript"""
    return datetime.now().isoformat()

def _now_for_display():
    """Formato para exibição no frontend"""
    agora = datetime.now()
    dias_semana = ["Dom", "Seg", "Ter", "Qua", "Qui", "Sex", "Sáb"]
    meses = ["Jan", "Fev", "Mar", "Abr", "Mai", "Jun", 
             "Jul", "Ago", "Set", "Out", "Nov", "Dez"]
    
    return {
        "data_completa": agora.strftime("%d/%m/%Y %H:%M:%S"),
        "data_curta": agora.strftime("%d/%m/%Y"),
        "hora": agora.strftime("%H:%M:%S"),
        "dia_semana": dias_semana[agora.weekday()],
        "dia": agora.day,
        "mes": meses[agora.month - 1],
        "ano": agora.year,
        "timestamp": agora.timestamp()
    }

# ---------- Funções auxiliares ----------

def carregar_arquivo_sirene():
    """Carrega o arquivo de sirene em memória"""
    global siren_audio_cache
    
    if siren_audio_cache is not None:
        return siren_audio_cache
    
    # Procurar arquivo de sirene
    audio_files = [
        ("siren.mp3", "audio/mpeg"),
        ("siren.wav", "audio/wav"),
        ("alarm.mp3", "audio/mpeg"),
        ("alarm.wav", "audio/wav"),
        ("emergency.mp3", "audio/mpeg"),
    ]
    
    for filename, mimetype in audio_files:
        filepath = os.path.join(app.static_folder, filename)
        if os.path.exists(filepath):
            try:
                with open(filepath, 'rb') as f:
                    siren_audio_cache = (f.read(), mimetype, filename)
                print(f"Arquivo de sirene carregado: {filename}")
                return siren_audio_cache
            except Exception as e:
                print(f"Erro ao carregar {filename}: {e}")
    
    # Criar sirene artificial se não encontrar arquivo
    print("Criando sirene artificial...")
    siren_audio_cache = criar_sirene_artificial()
    return siren_audio_cache

def criar_sirene_artificial():
    """Cria uma sirene artificial (bip alternado)"""
    import numpy as np
    from scipy.io import wavfile
    from io import BytesIO
    
    # Parâmetros do áudio
    sample_rate = 44100
    duration = 10.0  # 10 segundos
    
    # Criar array de tempo
    t = np.linspace(0, duration, int(sample_rate * duration), False)
    
    # Criar sirene alternada (800Hz e 600Hz)
    siren_wave = np.zeros_like(t)
    for i in range(len(t)):
        # Alterna a cada 0.5 segundos
        if int(t[i] * 2) % 2 == 0:
            # Tom alto
            siren_wave[i] = 0.5 * np.sin(2 * np.pi * 800 * t[i])
        else:
            # Tom baixo
            siren_wave[i] = 0.5 * np.sin(2 * np.pi * 600 * t[i])
    
    # Converter para 16-bit
    audio_data = np.int16(siren_wave * 32767)
    
    # Salvar em buffer WAV
    buffer = BytesIO()
    wavfile.write(buffer, sample_rate, audio_data)
    buffer.seek(0)
    
    return (buffer.getvalue(), 'audio/wav', 'siren_artificial.wav')

# ---------- Rotas de páginas ----------

@app.route("/")
def home():
    return render_template("home.html")

@app.route("/professor")
def professor():
    return render_template("professor.html")

@app.route("/painel_publico")
def painel_publico():
    agora = _now_for_display()
    return render_template("painel_publico.html", agora=agora)

@app.route("/admin")
def admin():
    return render_template("admin.html")

# ----------- Login da Central -----------

@app.route("/login_central", methods=["GET", "POST"])
def login_central():
    error = None
    if request.method == "POST":
        password = request.form.get("password") or request.form.get("senha")

        if password == ADMIN_PASSWORD:
            session["admin_logged"] = True
            session.permanent = False
            return redirect(url_for("central"))
        else:
            error = "Senha inválida. Tente novamente."

    agora = _now_for_display()
    return render_template("login_central.html", error=error, agora=agora)

@app.route("/logout_central")
def logout_central():
    session.pop("admin_logged", None)
    return redirect(url_for("login_central"))

@app.route("/central")
def central():
    if not session.get("admin_logged"):
        return redirect(url_for("login_central"))
    
    agora = _now_for_display()
    return render_template("central.html", agora=agora)

# ---------- APIs de alerta e status ----------

@app.route("/api/alert", methods=["POST"])
def api_alert():
    try:
        data = request.get_json() if request.is_json else request.form.to_dict()
        
        if not data:
            return jsonify({"ok": False, "error": "Dados inválidos"}), 400
        
        teacher = data.get("teacher", "Professor")[:50]
        room = data.get("room", "Sala não informada")[:50]
        description = data.get("description", "Sem descrição")[:200]
        
        timestamp = _now_str()
        
        alerta = {
            "id": len(alertas) + 1,
            "teacher": teacher,
            "room": room,
            "description": description,
            "ts": timestamp,
            "timestamp": datetime.now().timestamp(),
            "resolved": False,
        }
        
        with data_lock:
            alertas.append(alerta)
            sistema_status["sirene_ativa"] = True
            sistema_status["ultima_atualizacao"] = timestamp
        
        print(f"✅ NOVO ALERTA: {teacher} - {room} - {timestamp}")
        print(f"   Sirene ativada: {sistema_status['sirene_ativa']}")
        
        return jsonify({
            "ok": True, 
            "alert": alerta,
            "siren_activated": True,
            "timestamp": timestamp
        })
        
    except Exception as e:
        print(f"❌ Erro em api_alert: {str(e)}")
        return jsonify({"ok": False, "error": "Erro interno do servidor"}), 500

@app.route("/api/status")
def api_status():
    try:
        with data_lock:
            active_alerts = [a for a in alertas if not a["resolved"]]
            now_info = _now_for_display()
            
            status_data = {
                "ok": True,
                "siren": sistema_status["sirene_ativa"],
                "muted": sistema_status["mutado"],
                "alerts": alertas[-20:],  # Últimos 20 alertas
                "active_alerts": len(active_alerts),
                "total_alerts": len(alertas),
                "last_update": sistema_status["ultima_atualizacao"],
                "server_time": now_info["data_completa"],
                "server_timestamp": now_info["timestamp"],
            }
        
        return jsonify(status_data)
        
    except Exception as e:
        print(f"❌ Erro em api_status: {str(e)}")
        return jsonify({"ok": False, "error": str(e)}), 500

@app.route("/api/siren", methods=["POST"])
def api_siren():
    try:
        data = request.get_json() if request.is_json else request.form.to_dict()
        action = data.get("action", "").lower()
        
        with data_lock:
            if action == "on":
                sistema_status["sirene_ativa"] = True
                sistema_status["mutado"] = False
                print("🔊 Sirene LIGADA via API")
                
            elif action == "off":
                sistema_status["sirene_ativa"] = False
                print("🔇 Sirene DESLIGADA via API")
                
            elif action == "mute":
                sistema_status["mutado"] = True
                print("🔈 Sirene SILENCIADA via API")
                
            elif action == "unmute":
                sistema_status["mutado"] = False
                print("🔊 Sirene ATIVADA (unmute) via API")
                
            elif action == "clear":
                for a in alertas:
                    a["resolved"] = True
                sistema_status["sirene_ativa"] = False
                print("🧹 Alertas LIMPOS e sirene desligada")
                
            elif action == "test":
                sistema_status["sirene_ativa"] = True
                sistema_status["mutado"] = False
                print("🔊 Sirene de TESTE ativada")
                
            else:
                return jsonify({"ok": False, "error": "Ação inválida"}), 400

            sistema_status["ultima_atualizacao"] = _now_str()
            
        return jsonify({
            "ok": True,
            "siren": sistema_status["sirene_ativa"],
            "muted": sistema_status["mutado"],
            "message": f"Ação '{action}' realizada com sucesso",
            "timestamp": _now_str()
        })
        
    except Exception as e:
        print(f"❌ Erro em api_siren: {str(e)}")
        return jsonify({"ok": False, "error": str(e)}), 500

@app.route("/api/resolve/<int:alert_id>", methods=["POST"])
def api_resolve_specific(alert_id):
    try:
        with data_lock:
            for alerta in alertas:
                if alerta["id"] == alert_id:
                    alerta["resolved"] = True
                    print(f"✅ Alerta {alert_id} resolvido")
                    break
            
            # Verificar se ainda há alertas ativos
            if not any(not a["resolved"] for a in alertas):
                sistema_status["sirene_ativa"] = False
                print("🔇 Sirene desligada (todos os alertas resolvidos)")
                
            sistema_status["ultima_atualizacao"] = _now_str()
            
        return jsonify({"ok": True, "alert_id": alert_id})
        
    except Exception as e:
        print(f"❌ Erro em api_resolve: {str(e)}")
        return jsonify({"ok": False, "error": str(e)}), 500

# ---------- Áudio da sirene ----------

@app.route("/tocar_sirene")
def tocar_sirene():
    """Endpoint para reproduzir a sirene"""
    try:
        # Verificar se a sirene deve tocar
        with data_lock:
            if not sistema_status["sirene_ativa"] or sistema_status["mutado"]:
                return jsonify({"error": "Sirene não autorizada"}), 403
        
        # Carregar áudio
        audio_data, mimetype, filename = carregar_arquivo_sirene()
        
        # Criar resposta
        response = send_file(
            BytesIO(audio_data),
            mimetype=mimetype,
            as_attachment=False,
            download_name=filename
        )
        
        # Headers para evitar cache
        response.headers['Cache-Control'] = 'no-cache, no-store, must-revalidate'
        response.headers['Pragma'] = 'no-cache'
        response.headers['Expires'] = '0'
        response.headers['X-Siren-Status'] = 'playing'
        
        print(f"🔊 Sirene tocando: {filename}")
        return response
        
    except Exception as e:
        print(f"❌ Erro em tocar_sirene: {str(e)}")
        return jsonify({"error": f"Erro ao reproduzir sirene: {str(e)}"}), 500

@app.route("/siren/stream")
def siren_stream():
    """Stream contínuo da sirene (para loop no frontend)"""
    try:
        with data_lock:
            if not sistema_status["sirene_ativa"] or sistema_status["mutado"]:
                return "", 204  # No Content
        
        audio_data, mimetype, filename = carregar_arquivo_sirene()
        
        def generate():
            # Enviar áudio em chunks
            chunk_size = 1024 * 10  # 10KB chunks
            for i in range(0, len(audio_data), chunk_size):
                yield audio_data[i:i + chunk_size]
                # Pequena pausa entre chunks
                time.sleep(0.01)
        
        return app.response_class(
            generate(),
            mimetype=mimetype,
            headers={
                'Cache-Control': 'no-cache',
                'X-Accel-Buffering': 'no',  # Para streaming
            }
        )
        
    except Exception as e:
        print(f"Erro no stream da sirene: {e}")
        return "", 500

# ---------- Relatório em PDF ----------

@app.route("/report.pdf")
def report_pdf():
    try:
        from reportlab.lib.pagesizes import A4
        from reportlab.pdfgen import canvas
        from reportlab.lib.utils import ImageReader
        
        buffer = BytesIO()
        c = canvas.Canvas(buffer, pagesize=A4)
        width, height = A4
        
        # Data ATUALIZADA
        agora = datetime.now()
        data_formatada = agora.strftime("%d/%m/%Y %H:%M:%S")
        
        # Cabeçalho
        y = height - 50
        c.setFont("Helvetica-Bold", 18)
        c.drawString(50, y, "RELATÓRIO DE ALERTAS - PROF-SAFE24")
        y -= 25
        
        c.setFont("Helvetica", 10)
        c.drawString(50, y, f"Data de emissão: {data_formatada}")
        y -= 25
        
        # Informações da escola
        c.setFont("Helvetica-Bold", 12)
        c.drawString(50, y, "INFORMAÇÕES DA ESCOLA:")
        y -= 15
        
        c.setFont("Helvetica", 10)
        c.drawString(50, y, f"Escola: {SCHOOL_NAME}")
        y -= 15
        c.drawString(50, y, f"Endereço: {SCHOOL_ADDRESS}")
        y -= 15
        c.drawString(50, y, f"Cidade: {SCHOOL_CITY}")
        y -= 15
        c.drawString(50, y, f"Telefone: {SCHOOL_PHONE}")
        y -= 15
        c.drawString(50, y, f"Diretor(a): {SCHOOL_DIRECTOR}")
        y -= 30
        
        # Estatísticas ATUALIZADAS
        with data_lock:
            total = len(alertas)
            ativos = len([a for a in alertas if not a["resolved"]])
            resolvidos = total - ativos
        
        c.setFont("Helvetica-Bold", 12)
        c.drawString(50, y, "ESTATÍSTICAS:")
        y -= 15
        
        c.setFont("Helvetica", 10)
        c.drawString(50, y, f"Total de alertas: {total}")
        y -= 15
        c.drawString(50, y, f"Alertas ativos: {ativos}")
        y -= 15
        c.drawString(50, y, f"Alertas resolvidos: {resolvidos}")
        y -= 30
        
        # Lista de alertas
        if alertas:
            c.setFont("Helvetica-Bold", 12)
            c.drawString(50, y, "ALERTAS REGISTRADOS:")
            y -= 20
            
            c.setFont("Helvetica", 9)
            for idx, alerta in enumerate(reversed(alertas[-50:]), 1):
                if y < 100:  # Nova página se necessário
                    c.showPage()
                    y = height - 50
                    c.setFont("Helvetica", 9)
                
                status = "✅ RESOLVIDO" if alerta.get("resolved") else "⚠️ ATIVO"
                cor = (0, 1, 0) if alerta.get("resolved") else (1, 0, 0)
                
                c.setFillColorRGB(*cor)
                c.drawString(50, y, f"{idx}. {alerta.get('ts', 'N/A')} - {status}")
                y -= 12
                
                c.setFillColorRGB(0, 0, 0)
                c.drawString(70, y, f"Professor: {alerta.get('teacher', 'N/A')}")
                c.drawString(200, y, f"Sala: {alerta.get('room', 'N/A')}")
                y -= 12
                
                desc = alerta.get('description', 'Sem descrição')
                if len(desc) > 60:
                    desc = desc[:57] + "..."
                c.drawString(70, y, f"Descrição: {desc}")
                y -= 20
                
                # Linha divisória
                c.line(50, y, width-50, y)
                y -= 15
        
        c.save()
        buffer.seek(0)
        
        return send_file(
            buffer,
            as_attachment=True,
            download_name=f"relatorio_{agora.strftime('%Y%m%d_%H%M%S')}.pdf",
            mimetype="application/pdf"
        )
        
    except ImportError:
        return "Biblioteca reportlab não encontrada", 500
    except Exception as e:
        print(f"❌ Erro no relatório PDF: {e}")
        return f"Erro ao gerar relatório: {str(e)}", 500

# ---------- API para hora do servidor ----------

@app.route("/api/server_time")
def api_server_time():
    """Retorna a hora EXATA do servidor"""
    agora = datetime.now()
    return jsonify({
        "datetime": agora.strftime("%d/%m/%Y %H:%M:%S"),
        "date": agora.strftime("%d/%m/%Y"),
        "time": agora.strftime("%H:%M:%S"),
        "iso": agora.isoformat(),
        "timestamp": agora.timestamp(),
        "timezone": "America/Sao_Paulo",
    })

# ---------- Healthcheck com debug ----------

@app.route("/health")
def health():
    try:
        with data_lock:
            status = {
                "status": "ok",
                "server_time": _now_str(),
                "alert_count": len(alertas),
                "active_alerts": len([a for a in alertas if not a["resolved"]]),
                "siren_status": {
                    "active": sistema_status["sirene_ativa"],
                    "muted": sistema_status["mutado"],
                    "last_update": sistema_status["ultima_atualizacao"],
                },
                "endpoints": {
                    "siren_audio": "/tocar_sirene",
                    "siren_stream": "/siren/stream",
                    "siren_control": "/api/siren",
                    "status": "/api/status",
                    "server_time": "/api/server_time",
                }
            }
        return jsonify(status)
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500

# ---------- Debug ----------

@app.route("/debug")
def debug():
    """Página de debug"""
    with data_lock:
        debug_info = {
            "server_time": _now_str(),
            "alertas": alertas,
            "sistema_status": sistema_status,
            "session": dict(session) if session else None,
        }
    
    return jsonify(debug_info)

# ---------- Inicialização ----------

if __name__ == "__main__":
    # Carregar sirene na inicialização
    carregar_arquivo_sirene()
    
    port = int(os.environ.get("PORT", 5000))
    debug = os.environ.get("FLASK_DEBUG", "true").lower() == "true"
    
    print("=" * 60)
    print("🚀 SISTEMA PROF-SAFE24 INICIADO")
    print(f"📅 Data/Hora: {_now_str()}")
    print(f"🌐 Porta: {port}")
    print(f"🐛 Debug: {debug}")
    print(f"🏫 Escola: {SCHOOL_NAME}")
    print("=" * 60)
    
    app.run(host="0.0.0.0", port=port, debug=debug, threaded=True)
