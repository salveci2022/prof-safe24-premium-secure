"""
PROF-SAFE 24 — Sistema de Segurança Escolar
Versão PRO: Multi-escola, Multi-perfil, WhatsApp (Z-API), Email (Gmail)
"""
from flask import Flask, render_template, request, jsonify, send_file, session, redirect, url_for
from datetime import datetime
from io import BytesIO
from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas as pdf_canvas
from pathlib import Path
from functools import wraps
import json, os, urllib.request, urllib.parse, smtplib, ssl

app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", "profsafe24-estadual-goias-2026")

BASE_DIR     = Path(__file__).resolve().parent
USERS_FILE   = BASE_DIR / "users.json"
ESCOLAS_FILE = BASE_DIR / "escolas.json"
ALERTS_FILE  = BASE_DIR / "alertas.json"
STATE_FILE   = BASE_DIR / "state.json"

# ============================================================
# CONFIGURAÇÕES DE NOTIFICAÇÃO (variáveis de ambiente)
# ============================================================
# WHATSAPP (Z-API):
#   1. Acesse https://app.z-api.io e crie uma instância
#   2. Conecte seu WhatsApp escaneando o QR Code
#   3. Copie: Instance ID, Token e Client-Token
#   4. Configure no Render.com → Environment Variables
#
# GMAIL:
#   1. Ative verificação em 2 etapas na conta Google
#   2. Acesse: myaccount.google.com/apppasswords
#   3. Crie senha de app "PROF-SAFE 24"
#   4. Configure GMAIL_USER e GMAIL_APP_PASS no Render

ZAPI_INSTANCE   = os.environ.get("ZAPI_INSTANCE", "")
ZAPI_TOKEN      = os.environ.get("ZAPI_TOKEN", "")
ZAPI_CLIENT_TKN = os.environ.get("ZAPI_CLIENT_TOKEN", "")
GMAIL_USER      = os.environ.get("GMAIL_USER", "")
GMAIL_PASS      = os.environ.get("GMAIL_APP_PASS", "")

# Log de configuração ao iniciar
def _check_notif_config():
    ok_w = bool(ZAPI_INSTANCE and ZAPI_TOKEN)
    ok_e = bool(GMAIL_USER and GMAIL_PASS)
    print(f"📱 WhatsApp Z-API: {'✅ CONFIGURADO' if ok_w else '⚠️  NÃO CONFIGURADO'}")
    print(f"📧 Gmail:          {'✅ CONFIGURADO' if ok_e else '⚠️  NÃO CONFIGURADO'}")

# ============================================================
# PERFIS DO SISTEMA
# ============================================================
# admin        → cadastra escolas e usuários
# estadual     → vê tudo (Responsável Segurança Estadual)
# secretaria   → vê todas escolas da sua região
# diretor      → vê apenas sua escola
# coordenador  → vê apenas sua escola
# professor    → envia SOS (não precisa login)

# ============================================================
# PERSISTÊNCIA
# ============================================================
def _read(path, default):
    try:
        if path.exists():
            return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        pass
    return default

def _write(path, data):
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")

def load_users():    return _read(USERS_FILE,   {})
def load_escolas():  return _read(ESCOLAS_FILE, {})
def load_alertas():  return _read(ALERTS_FILE,  [])
def load_state():    return _read(STATE_FILE,   {"last_id": 0, "siren_on": False})

def save_users(d):   _write(USERS_FILE,   d)
def save_escolas(d): _write(ESCOLAS_FILE, d)
def save_alertas(d): _write(ALERTS_FILE,  d)
def save_state(d):   _write(STATE_FILE,   d)

# ============================================================
# DADOS DE DEMONSTRAÇÃO (cria na 1ª execução)
# ============================================================
def seed_demo_data():
    """Cria dados de demo para a apresentação."""
    escolas = load_escolas()
    if not escolas:
        escolas = {
            "escola_001": {
                "id": "escola_001", "nome": "Colégio Estadual Noroeste",
                "cidade": "São Miguel do Araguaia", "regiao": "Noroeste",
                "endereco": "Av. Brasil, 100 – São Miguel do Araguaia/GO",
                "telefone": "(62) 99999-0001", "diretor": "Prof. Carlos Souza",
                "ativo": True
            },
            "escola_002": {
                "id": "escola_002", "nome": "Colégio Estadual Centro-Oeste",
                "cidade": "Goiânia", "regiao": "Central",
                "endereco": "Rua das Flores, 200 – Goiânia/GO",
                "telefone": "(62) 99999-0002", "diretor": "Profa. Ana Lima",
                "ativo": True
            },
            "escola_003": {
                "id": "escola_003", "nome": "Colégio Estadual Sul Goiano",
                "cidade": "Itumbiara", "regiao": "Sul",
                "endereco": "Av. Goiás, 300 – Itumbiara/GO",
                "telefone": "(64) 99999-0003", "diretor": "Prof. João Alves",
                "ativo": True
            }
        }
        save_escolas(escolas)

    users = load_users()
    if not users:
        users = {
            "admin": {
                "nome": "Administrador", "senha": "admin2026",
                "perfil": "admin", "escola_id": None,
                "whatsapp": "", "email": ""
            },
            "estadual": {
                "nome": "Responsável Segurança Estadual",
                "senha": "estadual2026",
                "perfil": "estadual", "escola_id": None,
                "whatsapp": os.environ.get("WHATS_ESTADUAL", ""),
                "email":    os.environ.get("EMAIL_ESTADUAL", "")
            },
            "secretaria": {
                "nome": "Secretaria de Educação", "senha": "seceduc2026",
                "perfil": "secretaria", "escola_id": None,
                "whatsapp": os.environ.get("WHATS_SECEDUC", ""),
                "email":    os.environ.get("EMAIL_SECEDUC", "")
            },
            "diretor001": {
                "nome": "Prof. Carlos Souza", "senha": "diretor001",
                "perfil": "diretor", "escola_id": "escola_001",
                "whatsapp": os.environ.get("WHATS_DIRETOR1", ""),
                "email": ""
            },
            "coord001": {
                "nome": "Coordenadora Silva", "senha": "coord001",
                "perfil": "coordenador", "escola_id": "escola_001",
                "whatsapp": "", "email": ""
            }
        }
        save_users(users)

seed_demo_data()
_check_notif_config()
_check_notif_config()

# ============================================================
# AUTENTICAÇÃO
# ============================================================
def login_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if not session.get("logged_in"):
            return redirect("/login")
        return f(*args, **kwargs)
    return decorated

def role_required(*roles):
    def decorator(f):
        @wraps(f)
        def decorated(*args, **kwargs):
            if not session.get("logged_in"):
                return redirect("/login")
            if session.get("perfil") not in roles:
                return redirect("/acesso_negado")
            return f(*args, **kwargs)
        return decorated
    return decorator

# ============================================================
# NOTIFICAÇÕES
# ============================================================
def enviar_whatsapp(numero, mensagem):
    """Envia WhatsApp via Z-API. Ignora se não configurado."""
    if not ZAPI_INSTANCE or not ZAPI_TOKEN or not numero:
        print(f"[ZAPI] Ignorado — não configurado ou número vazio ({numero})")
        return False
    try:
        # Remove caracteres não numéricos do número
        numero_limpo = "".join(filter(str.isdigit, numero))
        url     = f"https://api.z-api.io/instances/{ZAPI_INSTANCE}/token/{ZAPI_TOKEN}/send-text"
        payload = json.dumps({"phone": numero_limpo, "message": mensagem}).encode("utf-8")
        headers = {
            "Content-Type":  "application/json",
            "Client-Token":  ZAPI_CLIENT_TKN,
        }
        print(f"[ZAPI] Enviando para {numero_limpo}...")
        print(f"[ZAPI] Instance: {ZAPI_INSTANCE[:8]}...")
        print(f"[ZAPI] Client-Token: {ZAPI_CLIENT_TKN[:8]}...")
        req  = urllib.request.Request(url, data=payload, headers=headers, method="POST")
        resp = urllib.request.urlopen(req, timeout=10)
        body = resp.read().decode("utf-8")
        print(f"[ZAPI] ✅ Resposta: {body}")
        return True
    except Exception as e:
        print(f"[ZAPI] ❌ Erro ao enviar para {numero}: {e}")
        return False

def enviar_email(destinatario, assunto, corpo):
    """Envia email via Gmail. Ignora se não configurado."""
    if not GMAIL_USER or not GMAIL_PASS or not destinatario:
        print(f"[Gmail] Ignorado — não configurado ou destinatário vazio")
        return False
    try:
        ctx = ssl.create_default_context()
        with smtplib.SMTP_SSL("smtp.gmail.com", 465, context=ctx) as server:
            server.login(GMAIL_USER, GMAIL_PASS)
            msg = (
                f"Subject: {assunto}\n"
                f"From: PROF-SAFE 24 <{GMAIL_USER}>\n"
                f"To: {destinatario}\n"
                f"Content-Type: text/plain; charset=utf-8\n\n"
                f"{corpo}"
            )
            server.sendmail(GMAIL_USER, destinatario, msg.encode("utf-8"))
        print(f"[Gmail] ✅ Email enviado para {destinatario}")
        return True
    except Exception as e:
        print(f"[Gmail] ❌ Erro ao enviar para {destinatario}: {e}")
        return False

def notificar_alerta(alerta, escola):
    """Notifica WhatsApp + Email para todos os responsáveis."""
    nome_escola = escola.get("nome", "Escola")
    cidade      = escola.get("cidade", "")
    regiao      = escola.get("regiao", "")
    professor   = alerta.get("teacher", "Professor(a)")
    sala        = alerta.get("room", "")
    desc        = alerta.get("description", "")
    hora        = alerta.get("time", "")

    msg = (
        f"🚨 *ALERTA PROF-SAFE 24*\n\n"
        f"🏫 Escola: {nome_escola}\n"
        f"📍 {cidade} — Região {regiao}\n"
        f"👤 Professor(a): {professor}\n"
        f"🚪 Sala/Local: {sala}\n"
        f"⚠️ Ocorrência: {desc}\n"
        f"⏰ Hora: {hora}\n\n"
        f"Acesse o painel: https://profsafe24.com.br/painel_estado"
    )

    assunto = f"🚨 ALERTA PROF-SAFE 24 — {nome_escola} — {desc[:40]}"

    users = load_users()
    for username, info in users.items():
        perfil = info.get("perfil", "")
        escola_id_user = info.get("escola_id")

        # Notifica: estadual (todos), secretaria (todos), diretor/coord da escola
        deve_notificar = (
            perfil in ("estadual", "secretaria") or
            (perfil in ("diretor", "coordenador") and escola_id_user == alerta.get("escola_id"))
        )
        if deve_notificar:
            whats = info.get("whatsapp", "")
            email = info.get("email", "")
            if whats:
                enviar_whatsapp(whats, msg)
            if email:
                enviar_email(email, assunto, msg.replace("*",""))

# ============================================================
# PÁGINAS PÚBLICAS
# ============================================================
@app.route("/")
def home():
    return render_template("home.html")

@app.route("/acesso_negado")
def acesso_negado():
    return render_template("acesso_negado.html"), 403

@app.route("/professor")
def professor():
    escola_id = request.args.get("escola", "escola_001")
    escolas   = load_escolas()
    escola    = escolas.get(escola_id, {})
    return render_template("professor.html", escola=escola, escola_id=escola_id,
                           escolas=list(escolas.values()))

@app.route("/painel_publico")
def painel_publico():
    escola_id = request.args.get("escola", "")
    escolas   = load_escolas()
    escola    = escolas.get(escola_id, {}) if escola_id else {}
    return render_template("painel_publico.html", escola=escola, escola_id=escola_id,
                           escolas=list(escolas.values()))

# ============================================================
# LOGIN / LOGOUT
# ============================================================
@app.route("/login", methods=["GET", "POST"])
def login():
    error = None
    if request.method == "POST":
        usuario = request.form.get("usuario", "").strip()
        senha   = request.form.get("senha", "")
        users   = load_users()
        user    = users.get(usuario)
        if user and user.get("senha") == senha:
            session.clear()
            session["logged_in"]  = True
            session["usuario"]    = usuario
            session["perfil"]     = user["perfil"]
            session["nome"]       = user.get("nome", usuario)
            session["escola_id"]  = user.get("escola_id")

            # Redireciona conforme perfil
            perfil = user["perfil"]
            # Redireciona para a página que tentou acessar (se houver)
            next_page = request.args.get("next", "")
            if next_page in ("painel_estado", "central", "admin", "painel_secretaria"):
                return redirect("/" + next_page)
            # Redireciona conforme perfil
            if perfil == "admin":
                return redirect("/admin")
            elif perfil == "estadual":
                return redirect("/painel_estado")
            elif perfil == "secretaria":
                return redirect("/painel_secretaria")
            elif perfil in ("diretor", "coordenador"):
                return redirect("/central")
            else:
                return redirect("/")
        else:
            error = "Usuário ou senha inválidos."
    return render_template("login.html", error=error)

@app.route("/logout")
def logout():
    session.clear()
    return redirect("/login")

# ============================================================
# PAINEL CENTRAL (Diretor / Coordenador)
# ============================================================
@app.route("/central")
@role_required("admin", "diretor", "coordenador")
def central():
    escola_id = session.get("escola_id") or request.args.get("escola", "")
    escolas   = load_escolas()
    escola    = escolas.get(escola_id, {})
    return render_template("central.html", escola=escola, escola_id=escola_id)

# ============================================================
# PAINEL ESTADUAL (Responsável Segurança Estadual)
# ============================================================
@app.route("/painel_estado")
def painel_estado():
    if not session.get("logged_in"):
        return redirect("/login?next=painel_estado")
    if session.get("perfil") not in ("admin", "estadual"):
        return redirect("/acesso_negado")
    escolas = load_escolas()
    return render_template("painel_estado.html", escolas=list(escolas.values()))

# ============================================================
# PAINEL SECRETARIA
# ============================================================
@app.route("/painel_secretaria")
@role_required("admin", "secretaria")
def painel_secretaria():
    escolas = load_escolas()
    return render_template("painel_secretaria.html", escolas=list(escolas.values()))

# ============================================================
# ADMIN
# ============================================================
@app.route("/admin")
@role_required("admin")
def admin():
    escolas = load_escolas()
    users   = load_users()
    return render_template("admin.html", escolas=escolas, users=users)

@app.route("/admin/escola/add", methods=["POST"])
@role_required("admin")
def admin_add_escola():
    escolas = load_escolas()
    escola_id = f"escola_{len(escolas)+1:03d}"
    escolas[escola_id] = {
        "id":       escola_id,
        "nome":     request.form.get("nome", "").strip(),
        "cidade":   request.form.get("cidade", "").strip(),
        "regiao":   request.form.get("regiao", "").strip(),
        "endereco": request.form.get("endereco", "").strip(),
        "telefone": request.form.get("telefone", "").strip(),
        "diretor":  request.form.get("diretor", "").strip(),
        "ativo":    True
    }
    save_escolas(escolas)
    return redirect("/admin?msg=Escola+cadastrada")

@app.route("/admin/usuario/add", methods=["POST"])
@role_required("admin")
def admin_add_usuario():
    users = load_users()
    username = request.form.get("username", "").strip()
    if username and username not in users:
        users[username] = {
            "nome":      request.form.get("nome", "").strip(),
            "senha":     request.form.get("senha", "").strip(),
            "perfil":    request.form.get("perfil", "diretor"),
            "escola_id": request.form.get("escola_id") or None,
            "whatsapp":  request.form.get("whatsapp", "").strip(),
            "email":     request.form.get("email", "").strip()
        }
        save_users(users)
    return redirect("/admin?msg=Usuário+cadastrado")

@app.route("/admin/usuario/delete/<username>", methods=["POST"])
@role_required("admin")
def admin_delete_usuario(username):
    users = load_users()
    if username in users and username != "admin":
        users.pop(username)
        save_users(users)
    return redirect("/admin?msg=Usuário+removido")

@app.route("/admin/escola/delete/<escola_id>", methods=["POST"])
@role_required("admin")
def admin_delete_escola(escola_id):
    escolas = load_escolas()
    if escola_id in escolas:
        escolas.pop(escola_id)
        save_escolas(escolas)
    return redirect("/admin?msg=Escola+removida")

# ============================================================
# API — ENVIAR ALERTA
# ============================================================
@app.route("/api/alert", methods=["POST"])
def api_alert():
    st      = load_state()
    alertas = load_alertas()
    escolas = load_escolas()
    data    = request.get_json() or {}

    escola_id = str(data.get("escola_id", "escola_001"))
    escola    = escolas.get(escola_id, {})

    st["last_id"] = int(st.get("last_id", 0)) + 1
    alerta = {
        "id":          st["last_id"],
        "teacher":     str(data.get("teacher", "Professor(a)"))[:100],
        "room":        str(data.get("room",    "Local não informado"))[:100],
        "description": str(data.get("description", "Alerta de pânico"))[:500],
        "escola_id":   escola_id,
        "escola_nome": escola.get("nome", escola_id),
        "escola_cidade": escola.get("cidade", ""),
        "escola_regiao": escola.get("regiao", ""),
        "time":        datetime.now().strftime("%d/%m/%Y %H:%M:%S"),
        "status":      "Ativo"
    }

    alertas.insert(0, alerta)
    alertas = alertas[:500]  # máximo 500 alertas

    st["siren_on"]        = True
    st["last_alert_time"] = alerta["time"]
    save_alertas(alertas)
    save_state(st)

    # Notifica WhatsApp e Email em background
    try:
        notificar_alerta(alerta, escola)
    except Exception as e:
        print(f"[Notificação] Erro: {e}")

    return jsonify({"ok": True, "alerta": alerta})

# ============================================================
# API — STATUS (filtrável por escola)
# ============================================================
@app.route("/api/status")
def api_status():
    st      = load_state()
    alertas = load_alertas()
    escola_id = request.args.get("escola", "")

    if escola_id:
        alertas_filtrados = [a for a in alertas if a.get("escola_id") == escola_id]
        siren = any(a.get("status") == "Ativo" for a in alertas_filtrados)
    else:
        alertas_filtrados = alertas
        siren = st.get("siren_on", False)

    return jsonify({
        "alertas":         alertas_filtrados,
        "siren_on":        siren,
        "last_alert_time": st.get("last_alert_time"),
        "total_escolas":   len(load_escolas()),
        "total_ativos":    sum(1 for a in alertas if a.get("status") == "Ativo")
    })

# ============================================================
# API — SIRENE
# ============================================================
@app.route("/api/siren", methods=["POST"])
def api_siren():
    st     = load_state()
    action = (request.get_json() or {}).get("action")
    if action == "on":   st["siren_on"] = True
    elif action == "off": st["siren_on"] = False
    save_state(st)
    return jsonify({"ok": True, "siren_on": st["siren_on"]})

# ============================================================
# API — RESOLVER / LIMPAR
# ============================================================
@app.route("/api/resolve", methods=["POST"])
def api_resolve():
    st      = load_state()
    alertas = load_alertas()
    escola_id = (request.get_json() or {}).get("escola_id", "")
    for a in alertas:
        if not escola_id or a.get("escola_id") == escola_id:
            a["status"] = "Resolvido"
    st["siren_on"] = False
    save_alertas(alertas)
    save_state(st)
    return jsonify({"ok": True})

@app.route("/api/clear", methods=["POST"])
def api_clear():
    st = load_state()
    escola_id = (request.get_json() or {}).get("escola_id", "")
    if escola_id:
        alertas = [a for a in load_alertas() if a.get("escola_id") != escola_id]
    else:
        alertas = []
    st["siren_on"] = False
    save_alertas(alertas)
    save_state(st)
    return jsonify({"ok": True})

# ============================================================
# API — LISTA DE ESCOLAS
# ============================================================
@app.route("/api/escolas")
def api_escolas():
    return jsonify(list(load_escolas().values()))

# ============================================================
# RELATÓRIO PDF
# ============================================================
@app.route("/report.pdf")
def gerar_relatorio():
    alertas   = load_alertas()
    escola_id = request.args.get("escola", "")
    if escola_id:
        alertas = [a for a in alertas if a.get("escola_id") == escola_id]

    buffer = BytesIO()
    pdf    = pdf_canvas.Canvas(buffer, pagesize=A4)
    larg, alt = A4

    pdf.setTitle("Relatório — PROF-SAFE 24")
    pdf.setFont("Helvetica-Bold", 18)
    pdf.drawString(50, alt - 50, "PROF-SAFE 24")
    pdf.setFont("Helvetica-Bold", 13)
    pdf.drawString(50, alt - 72, "Sistema Estadual de Segurança Escolar — Goiás")
    pdf.setFont("Helvetica", 10)
    pdf.drawString(50, alt - 90, f"Gerado em: {datetime.now().strftime('%d/%m/%Y %H:%M:%S')}")
    if escola_id:
        escola = load_escolas().get(escola_id, {})
        pdf.drawString(50, alt - 104, f"Escola: {escola.get('nome', escola_id)} — {escola.get('cidade', '')}")
    pdf.line(50, alt - 110, larg - 50, alt - 110)

    y = alt - 130
    pdf.setFont("Helvetica-Bold", 11)
    pdf.drawString(50, y, f"Total de alertas: {len(alertas)}")
    ativos = sum(1 for a in alertas if a.get("status") == "Ativo")
    pdf.drawString(250, y, f"Ativos: {ativos}")
    pdf.drawString(380, y, f"Resolvidos: {len(alertas) - ativos}")
    y -= 22
    pdf.setFont("Helvetica", 10)

    for alerta in alertas:
        if y < 80:
            pdf.showPage(); y = alt - 50; pdf.setFont("Helvetica", 10)
        linha = f"#{alerta['id']} | {alerta['time']} | {alerta.get('escola_nome','?')} | {alerta['teacher']} | {alerta['room']}"
        pdf.drawString(50, y, linha); y -= 14
        pdf.drawString(60, y, f"Desc: {alerta['description']} | Status: {alerta['status']}"); y -= 16

    pdf.showPage(); pdf.save(); buffer.seek(0)
    fname = f"profsafe24_{'escola_' + escola_id if escola_id else 'geral'}.pdf"
    return send_file(buffer, as_attachment=True, download_name=fname, mimetype="application/pdf")

# ============================================================
# ÁUDIO
# ============================================================
@app.route("/tocar_sirene")
def tocar_sirene():
    caminho = os.path.join("static", "siren.mp3")
    if os.path.exists(caminho):
        return send_file(caminho)
    return "Arquivo não encontrado", 404

# ============================================================
# RUN
# ============================================================
if __name__ == "__main__":
    print("=" * 62)
    print("🚨  PROF-SAFE 24 — Sistema Estadual de Segurança Escolar")
    print("    Estado de Goiás")
    print("=" * 62)
    print("🔐  Logins de demonstração:")
    print("    admin      / admin2026      → Administrador")
    print("    estadual   / estadual2026   → Responsável Estadual")
    print("    secretaria / seceduc2026    → Secretaria de Educação")
    print("    diretor001 / diretor001     → Diretor Escola Noroeste")
    print("=" * 62)
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)), debug=False)
