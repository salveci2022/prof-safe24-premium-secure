
print("Instruções criadas from flask import Flask, render_template, jsonify, request, send_file, redirect, url_for, session
import os
from datetime import datetime
from io import BytesIO
import threading
import time

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
    "sirene_playing": False,  # Novo: controle de reprodução
}
data_lock = threading.Lock()

# Thread para controlar sirene
siren_thread = None
siren_stop_event = threading.Event()

def _now_str():
    """Retorna data/hora atual no formato brasileiro"""
    agora = datetime.now()
    return agora.strftime("%d/%m/%Y %H:%M:%S")


def sirene_control():
    """Thread para controlar a reprodução da sirene"""
    print("Thread da sirene iniciada")
    
    while not siren_stop_event.is_set():
        with data_lock:
            should_play = (sistema_status["sirene_ativa"] and 
                          not sistema_status["mutado"] and
                          not sistema_status["sirene_playing"])
            
            if should_play:
                sistema_status["sirene_playing"] = True
                print("Sirene: INICIANDO reprodução")
        
        if siren_stop_event.is_set():
            break
            
        time.sleep(0.1)
    
    print("Thread da sirene finalizada")


# ---------- Iniciar thread da sirene ----------
def iniciar_thread_sirene():
    global siren_thread, siren_stop_event
    
    if siren_thread is None or not siren_thread.is_alive():
        siren_stop_event.clear()
        siren_thread = threading.Thread(target=sirene_control, daemon=True)
        siren_thread.start()
        print("Thread da sirene iniciada")


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
    
    # Iniciar thread da sirene se necessário
    iniciar_thread_sirene()
    
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
            "resolved": False,
        }
        
        with data_lock:
            alertas.append(alerta)
            sistema_status["sirene_ativa"] = True
            sistema_status["ultima_atualizacao"] = _now_str()
            
            # Log para debug
            print(f"Novo alerta: {teacher} na sala {room}")
            print(f"Sirene ativada: {sistema_status['sirene_ativa']}")
            print(f"Sistema mutado: {sistema_status['mutado']}")

        return jsonify({"ok": True, "alert": alerta})
        
    except Exception as e:
        app.logger.error(f"Erro em api_alert: {str(e)}")
        return jsonify({"ok": False, "error": "Erro interno do servidor"}), 500


@app.route("/api/status")
def api_status():
    try:
        with data_lock:
            active_alerts = [a for a in alertas if not a["resolved"]]
            status_data = {
                "siren": sistema_status["sirene_ativa"],
                "muted": sistema_status["mutado"],
                "alerts": alertas[-50:],
                "active_alerts": len(active_alerts),
                "last_update": sistema_status["ultima_atualizacao"],
                "server_time": _now_str(),
                "siren_playing": sistema_status["sirene_playing"],  # Para debug
            }
            
            print(f"Status consultado - Sirene: {sistema_status['sirene_ativa']}, Muted: {sistema_status['mutado']}")
            
        return jsonify(status_data)
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
                sistema_status["sirene_playing"] = False
                print("Sirene LIGADA via API")
                
            elif action == "off":
                sistema_status["sirene_ativa"] = False
                sistema_status["sirene_playing"] = False
                print("Sirene DESLIGADA via API")
                
            elif action == "mute":
                sistema_status["mutado"] = True
                sistema_status["sirene_playing"] = False
                print("Sirene SILENCIADA via API")
                
            elif action == "unmute":
                sistema_status["mutado"] = False
                print("Sirene ATIVADA (unmute) via API")
                
            elif action == "clear":
                for a in alertas:
                    a["resolved"] = True
                sistema_status["sirene_ativa"] = False
                sistema_status["sirene_playing"] = False
                print("Alertas LIMPOS e sirene desligada")
                
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
                sistema_status["sirene_playing"] = False
                
            sistema_status["ultima_atualizacao"] = _now_str()
            
        return jsonify({"ok": True, "resolved": resolved, "server_time": _now_str()})
        
    except Exception as e:
        app.logger.error(f"Erro em api_resolve: {str(e)}")
        return jsonify({"ok": False, "error": "Erro interno do servidor"}), 500


# ---------- Áudio da sirene ----------

@app.route("/tocar_sirene")
def tocar_sirene():
    """Endpoint para tocar a sirene (usado pelo frontend)"""
    try:
        # Verifica se a sirene deve tocar
        with data_lock:
            should_play = (sistema_status["sirene_ativa"] and 
                          not sistema_status["mutado"])
            
            if not should_play:
                print("Sirene bloqueada: ativa={}, mutado={}".format(
                    sistema_status["sirene_ativa"], 
                    sistema_status["mutado"]
                ))
                return jsonify({"error": "Sirene não autorizada"}), 403
        
        # Tenta diferentes formatos de áudio
        audio_files = [
            os.path.join(app.static_folder, "siren.mp3"),
            os.path.join(app.static_folder, "siren.wav"),
            os.path.join(app.static_folder, "alarm.mp3"),
            os.path.join(app.static_folder, "alarm.wav"),
        ]
        
        audio_file = None
        mime_type = None
        
        for file_path in audio_files:
            if os.path.exists(file_path):
                audio_file = file_path
                if file_path.endswith('.mp3'):
                    mime_type = 'audio/mpeg'
                elif file_path.endswith('.wav'):
                    mime_type = 'audio/wav'
                break
        
        if not audio_file:
            # Se não encontrar arquivo, retorna um áudio gerado dinamicamente
            print("Arquivo de sirene não encontrado, usando fallback")
            return criar_audio_fallback()
        
        print(f"Reproduzindo sirene: {audio_file}")
        
        # Marcar que está reproduzindo
        with data_lock:
            sistema_status["sirene_playing"] = True
        
        # Enviar arquivo
        response = send_file(audio_file, mimetype=mime_type)
        
        # Adicionar headers para evitar cache
        response.headers['Cache-Control'] = 'no-cache, no-store, must-revalidate'
        response.headers['Pragma'] = 'no-cache'
        response.headers['Expires'] = '0'
        
        return response
        
    except Exception as e:
        app.logger.error(f"Erro em tocar_sirene: {str(e)}")
        return jsonify({"error": f"Erro ao reproduzir sirene: {str(e)}"}), 500


def criar_audio_fallback():
    """Cria um áudio de sirene simples como fallback"""
    import numpy as np
    from io import BytesIO
    
    # Criar um tom simples
    sample_rate = 44100
    duration = 3.0
    t = np.linspace(0, duration, int(sample_rate * duration), False)
    
    # Tom de sirene (alternando frequências)
    tone = np.zeros_like(t)
    for i in range(len(t)):
        if int(t[i] * 2) % 2 == 0:  # Alterna a cada 0.5 segundos
            tone[i] = 0.3 * np.sin(2 * np.pi * 800 * t[i])  # 800 Hz
        else:
            tone[i] = 0.3 * np.sin(2 * np.pi * 600 * t[i])  # 600 Hz
    
    # Converter para áudio
    audio_data = np.int16(tone * 32767)
    
    # Salvar em buffer WAV
    import wave
    buffer = BytesIO()
    
    with wave.open(buffer, 'wb') as wav_file:
        wav_file.setnchannels(1)  # Mono
        wav_file.setsampwidth(2)  # 2 bytes = 16 bits
        wav_file.setframerate(sample_rate)
        wav_file.writeframes(audio_data.tobytes())
    
    buffer.seek(0)
    
    return send_file(
        buffer,
        mimetype='audio/wav',
        as_attachment=False,
        download_name='sirene_fallback.wav'
    )


@app.route("/api/siren/test")
def test_siren():
    """Endpoint para testar a sirene"""
    with data_lock:
        sistema_status["sirene_ativa"] = True
        sistema_status["mutado"] = False
        sistema_status["sirene_playing"] = False
    
    return jsonify({
        "ok": True,
        "message": "Sirene de teste ativada",
        "siren_url": "/tocar_sirene"
    })


# ---------- Relatório em PDF ----------
# (Mantém o código do relatório que já funciona)


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
                "siren_status": {
                    "active": sistema_status["sirene_ativa"],
                    "muted": sistema_status["mutado"],
                    "playing": sistema_status["sirene_playing"],
                },
                "static_files": {
                    "siren_mp3": os.path.exists(os.path.join(app.static_folder, "siren.mp3")),
                    "siren_wav": os.path.exists(os.path.join(app.static_folder, "siren.wav")),
                }
            }
        return jsonify(status)
    except Exception as e:
        return jsonify({"status": "error", "message": str(e), "server_time": _now_str()}), 500


# ---------- Rotas de debug ----------

@app.route("/debug/siren")
def debug_siren():
    """Página de debug para a sirene"""
    with data_lock:
        status = {
            "sirene_ativa": sistema_status["sirene_ativa"],
            "mutado": sistema_status["mutado"],
            "sirene_playing": sistema_status["sirene_playing"],
            "ultima_atualizacao": sistema_status["ultima_atualizacao"],
            "alertas_ativos": len([a for a in alertas if not a["resolved"]]),
            "arquivos_audio": []
        }
    
    # Verificar arquivos de áudio
    static_dir = app.static_folder
    if os.path.exists(static_dir):
        for file in os.listdir(static_dir):
            if file.endswith(('.mp3', '.wav', '.ogg')):
                status["arquivos_audio"].append(file)
    
    return jsonify(status)


if __name__ == "__main__":
    # Iniciar thread da sirene
    iniciar_thread_sirene()
    
    port = int(os.environ.get("PORT", 5000))
    debug = os.environ.get("FLASK_DEBUG", "true").lower() == "true"
    
    print("=" * 50)
    print(f"SISTEMA PROF-SAFE24 INICIANDO")
    print(f"Hora do servidor: {_now_str()}")
    print(f"Porta: {port}")
    print(f"Debug: {debug}")
    print("=" * 50)
    
    # Verificar arquivos estáticos
    static_dir = app.static_folder
    print(f"Pasta static: {static_dir}")
    
    if os.path.exists(static_dir):
        print("Arquivos na pasta static:")
        for file in os.listdir(static_dir):
            print(f"  - {file}")
    else:
        print("AVISO: Pasta static não encontrada!")
        os.makedirs(static_dir, exist_ok=True)
    
    app.run(host="0.0.0.0", port=port, debug=debug, threaded=True)em static/siren_info.txt")
