from flask import Flask, render_template, request, jsonify, send_file, session, redirect, url_for
from datetime import datetime
from io import BytesIO
from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas
import os
import json
import time
from functools import wraps

app = Flask(__name__)

# ================================
# CONFIG / SEGURANÇA BÁSICA
# ================================
# Render já está com SECRET_KEY no painel (Environment). Se não estiver, gere uma.
app.secret_key = os.getenv("SECRET_KEY", "dev-insecure-change-me")

# Cookies de sessão mais seguros (não quebra o sistema)
app.config.update(
    SESSION_COOKIE_HTTPONLY=True,
    SESSION_COOKIE_SAMESITE="Lax",
)

# Em produção (HTTPS), marque cookies como Secure
if os.getenv("RENDER") or os.getenv("FLASK_ENV") == "production":
    app.config["SESSION_COOKIE_SECURE"] = True


def _env_first(*keys: str) -> str:
    """Lê variáveis de ambiente na ordem e retorna string limpa."""
    for k in keys:
        v = os.getenv(k)
        if v is not None and str(v).strip() != "":
            return str(v).strip()
    return ""


def _admin_password() -> str:
    # Padrão recomendado: ADMIN_PASSWORD (mantém compatibilidade com ADMIN_PASS)
    return _env_first("ADMIN_PASSWORD", "ADMIN_PASS")


def _central_password() -> str:
    return _env_first("CENTRAL_PASSWORD", "CENTRAL_PASS")

# ================================
# "BANCO DE DADOS" EM MEMÓRIA (por escola)
# - Mantém compatibilidade com o uso atual (1 escola)
# - Permite vender para várias escolas sem misturar alertas
# ================================
alertas_by_school = {"default": []}
siren_by_school = {"default": {"on": False, "muted": False, "last": None}}

# ================================
# CADASTRO DE ESCOLAS (Admin)
# - Guarda dados básicos e gera links por escola (igual CONDO)
# - Persistência simples em schools.json (não quebra o sistema)
# ================================
SCHOOLS_FILE = os.path.join(os.path.dirname(__file__), "schools.json")


def _sanitize_school_id(sid: str) -> str:
    sid = (sid or "").strip().lower()
    sid = "".join(ch for ch in sid if ch.isalnum() or ch in ("-", "_"))[:64]
    return sid or "default"


def _load_schools() -> dict:
    try:
        if os.path.exists(SCHOOLS_FILE):
            with open(SCHOOLS_FILE, "r", encoding="utf-8") as f:
                data = json.load(f) or {}
                # normaliza chaves
                fixed = {}
                for k, v in data.items():
                    fixed[_sanitize_school_id(k)] = v if isinstance(v, dict) else {"nome": str(v)}
                return fixed
    except Exception:
        pass
    return {}


def _save_schools(data: dict) -> None:
    """Salva de forma mais segura (evita arquivo corrompido em escrita parcial)."""
    try:
        tmp = SCHOOLS_FILE + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        os.replace(tmp, SCHOOLS_FILE)
    except Exception:
        # Se não conseguir salvar (ex.: filesystem restrito), não derruba o app
        try:
            if os.path.exists(SCHOOLS_FILE + ".tmp"):
                os.remove(SCHOOLS_FILE + ".tmp")
        except Exception:
            pass


schools_db = _load_schools()

# Rate-limit simples (anti-spam) para /api/alert
_rate = {}  # ip -> [timestamps]


def _get_school_id():
    """Resolve o school_id sem quebrar URLs antigas."""
    # prioridade: JSON, querystring, header
    sid = None
    try:
        if request.is_json:
            sid = (request.get_json(silent=True) or {}).get("school")
    except Exception:
        sid = None

    sid = sid or request.args.get("school") or request.headers.get("X-School")
    sid = _sanitize_school_id(sid or "default")
    if sid not in alertas_by_school:
        alertas_by_school[sid] = []
        siren_by_school[sid] = {"on": False, "muted": False, "last": None}
    return sid


def _base_url() -> str:
    # host_url já vem com barra final
    return (request.host_url or "").rstrip("/")


def _client_ip():
    # Render passa X-Forwarded-For
    xff = request.headers.get("X-Forwarded-For", "")
    if xff:
        return xff.split(",")[0].strip()
    return request.remote_addr or "unknown"


def rate_limit_alerts(max_per_minute: int = 25):
    """Limite simples por IP para reduzir ataques/abusos."""

    def deco(fn):
        @wraps(fn)
        def wrapper(*args, **kwargs):
            ip = _client_ip()
            now = time.time()
            window = 60
            stamps = _rate.get(ip, [])
            stamps = [t for t in stamps if now - t < window]
            if len(stamps) >= max_per_minute:
                return jsonify({"ok": False, "error": "Muitas tentativas. Aguarde 1 minuto."}), 429
            stamps.append(now)
            _rate[ip] = stamps
            return fn(*args, **kwargs)

        return wrapper

    return deco


def require_login(role: str | None = None):
    """Protege rotas sensíveis (central/admin) sem alterar o painel do professor."""

    def deco(fn):
        @wraps(fn)
        def wrapper(*args, **kwargs):
            # Compatibilidade: mantém auth/role e adiciona flags explícitas
            is_admin = bool(session.get("admin_logged") or session.get("role") == "admin")
            is_central = bool(session.get("central_logged") or session.get("role") == "central")
            if not (session.get("auth") or is_admin or is_central):
                return redirect(url_for("login_central"))

            if role == "central":
                if not (is_central or is_admin):
                    return render_template("forbidden.html"), 403
            elif role == "admin":
                if not is_admin:
                    return render_template("forbidden.html"), 403
            return fn(*args, **kwargs)

        return wrapper

    return deco


@app.after_request
def security_headers(resp):
    # Cabeçalhos básicos (não interfere no front)
    resp.headers.setdefault("X-Content-Type-Options", "nosniff")
    resp.headers.setdefault("X-Frame-Options", "SAMEORIGIN")
    resp.headers.setdefault("Referrer-Policy", "strict-origin-when-cross-origin")
    # HTTPS only (Render)
    if request.headers.get("X-Forwarded-Proto", "http") == "https":
        resp.headers.setdefault("Strict-Transport-Security", "max-age=15552000; includeSubDomains")
    return resp


# ================================
# PÁGINAS
# ================================
@app.route("/")
def home():
    # Tela premium de apresentação do sistema
    return render_template("home.html")


# Health check para Render (evita reinícios por healthcheck incorreto)
@app.route("/healthz")
def healthz():
    return "ok", 200


@app.route("/professor")
def professor():
    return render_template("sos.html")

@app.route("/sos")
def sos():
    return render_template("sos.html")



@app.route("/central")
@require_login(role="central")
def central():
    return render_template("central.html")


# Alias compatível com links antigos/novos usados em venda
@app.route("/panel")
@require_login(role="central")
def panel():
    return render_template("central.html")


@app.route("/login_central", methods=["GET", "POST"])
@app.route("/panel/login", methods=["GET", "POST"])
def login_central():
    """Login Central/Admin.
    - CENTRAL_PASSWORD: acesso ao painel central (direção/coordenação)
    - ADMIN_PASSWORD ou ADMIN_PASS: acesso admin (se você ativar rotas admin)
    """
    if request.method == "POST":
        usuario = (request.form.get("usuario") or "").strip()[:80]
        senha = (request.form.get("senha") or "").strip()

        central_pass = _central_password()
        admin_pass = _admin_password()

        # Regras: senha central ou senha admin
        if central_pass and senha == central_pass:
            session["auth"] = True
            session["role"] = "central"
            session["central_logged"] = True
            session["admin_logged"] = False
            session["user"] = usuario or "central"
            return redirect(url_for("central"))
        if admin_pass and senha == admin_pass:
            session["auth"] = True
            session["role"] = "admin"
            session["admin_logged"] = True
            session["central_logged"] = False
            session["user"] = usuario or "admin"
            return redirect(url_for("central"))

        return render_template("login_central.html", error="Usuário ou senha inválidos.")

    return render_template("login_central.html")


@app.route("/panel/logout")
def logout():
    session.clear()
    return redirect(url_for("home"))




@app.route("/admin/login", methods=["GET", "POST"])
def login_admin():
    """Login exclusivo do ADMIN."""
    if request.method == "POST":
        usuario = (request.form.get("usuario") or "").strip()[:80]
        senha = (request.form.get("senha") or "").strip()

        admin_pass = _admin_password()
        if admin_pass and senha == admin_pass:
            session["auth"] = True
            session["role"] = "admin"
            session["admin_logged"] = True
            session["central_logged"] = False
            session["user"] = usuario or "admin"
            return redirect(url_for("admin"))
        return render_template("login_admin.html", error="Usuário ou senha inválidos.")

    return render_template("login_admin.html")


@app.route("/admin")
def admin():
    if not (session.get("auth") or session.get("admin_logged")):
        return redirect(url_for("login_admin"))
    if not (session.get("role") == "admin" or session.get("admin_logged")):
        return render_template("forbidden.html"), 403
    return render_template("admin.html")


# ================================
# ADMIN – CADASTRO DE ESCOLAS / LINKS
# (igual CONDO-SAFE24, sem mexer no painel do professor)
# ================================


def _require_admin():
    return bool((session.get("auth") or session.get("admin_logged")) and (session.get("role") == "admin" or session.get("admin_logged")))


@app.route("/admin/api/schools", methods=["GET"])
def admin_api_schools_get():
    if not _require_admin():
        return jsonify({"ok": False, "error": "Sem permissão"}), 403
    return jsonify({"ok": True, "schools": schools_db})


@app.route("/admin/api/schools", methods=["POST"])
def admin_api_schools_upsert():
    if not _require_admin():
        return jsonify({"ok": False, "error": "Sem permissão"}), 403

    data = request.get_json(silent=True) or {}
    sid = _sanitize_school_id(data.get("school_id") or data.get("id") or "")
    if not sid:
        return jsonify({"ok": False, "error": "ID da escola inválido"}), 400

    payload = {
        "nome": (data.get("nome") or "").strip()[:120] or sid,
        "endereco": (data.get("endereco") or "").strip()[:160],
        "telefone": (data.get("telefone") or "").strip()[:60],
        "diretor": (data.get("diretor") or "").strip()[:120],
        "logo": (data.get("logo") or "").strip()[:200],
        "updated_at": datetime.now().strftime("%d/%m/%Y %H:%M:%S"),
    }
    # preserva created_at se já existir
    if sid in schools_db and isinstance(schools_db[sid], dict) and schools_db[sid].get("created_at"):
        payload["created_at"] = schools_db[sid]["created_at"]
    else:
        payload["created_at"] = payload["updated_at"]

    schools_db[sid] = payload
    _save_schools(schools_db)

    # garante estruturas de runtime
    if sid not in alertas_by_school:
        alertas_by_school[sid] = []
        siren_by_school[sid] = {"on": False, "muted": False, "last": None}

    return jsonify({"ok": True, "school_id": sid, "school": payload})


@app.route("/admin/api/schools/<sid>", methods=["DELETE"])
def admin_api_schools_delete(sid):
    if not _require_admin():
        return jsonify({"ok": False, "error": "Sem permissão"}), 403
    sid = _sanitize_school_id(sid)
    if sid in schools_db:
        del schools_db[sid]
        _save_schools(schools_db)
    return jsonify({"ok": True})


@app.route("/admin/api/links/<sid>", methods=["GET"])
def admin_api_links(sid):
    if not _require_admin():
        return jsonify({"ok": False, "error": "Sem permissão"}), 403
    sid = _sanitize_school_id(sid)
    base = _base_url()
    links = {
        "professor": f"{base}/professor?school={sid}",
        "central_login": f"{base}/panel/login?school={sid}",
        "central": f"{base}/panel?school={sid}",
        "painel_publico": f"{base}/painel_publico?school={sid}",
        "relatorio": f"{base}/report.pdf?school={sid}",
    }
    return jsonify({"ok": True, "school": sid, "links": links})


@app.route("/forbidden")
def forbidden():
    return render_template("forbidden.html"), 403


@app.route("/acesso_restrito")
def acesso_restrito():
    return render_template("acesso_restrito.html"), 403
@app.route("/painel_publico")
def painel_publico():
    # Painel público para TV / comunidade
    return render_template("painel_publico.html")


# ================================
# API – ENVIAR ALERTA (PAINEL DO PROFESSOR)
# ================================
@app.route("/api/alert", methods=["POST"])
@rate_limit_alerts(max_per_minute=35)
def api_alert():
    """Recebe alerta do professor.

    Compatível com o sistema atual.
    Para multi-escolas, envie "school" no JSON, por ex.: {"school":"colegio_x"}.
    """
    sid = _get_school_id()
    data = request.get_json(silent=True) or {}

    # Compatibilidade de chaves (caso algum front envie nomes diferentes)
    teacher_raw = (data.get("teacher") or data.get("professor") or "Professor(a)")
    room_raw = (data.get("room") or data.get("sala") or "Sala / Local não informado")

    # Ocorrências podem vir como lista (problems/problemas) — queremos mostrar na Central
    problems = data.get("problems") or data.get("problemas") or []
    if isinstance(problems, str):
        problems = [problems]
    if not isinstance(problems, list):
        problems = []
    problems = [str(p).strip() for p in problems if str(p).strip()]

    # Descrição pode vir por description/descricao
    desc_in = (data.get("description") or data.get("descricao") or "").strip()

    # Monta descrição final: prioriza ocorrências selecionadas
    if problems:
        desc_final = " | ".join(problems)
        if desc_in and desc_in not in desc_final:
            desc_final = f"{desc_final} | {desc_in}"
    else:
        desc_final = desc_in or "Alerta de pânico acionado"

    teacher = str(teacher_raw)[:80]
    room = str(room_raw)[:80]
    desc = str(desc_final)[:220]

    alertas = alertas_by_school[sid]
    alerta = {
        "id": len(alertas) + 1,
        "teacher": teacher,
        "room": room,
        "description": desc,
        "time": datetime.now().strftime("%d/%m/%Y %H:%M:%S"),
        "status": "Ativo",
        "school": sid,
    }

    alertas.insert(0, alerta)
    siren_by_school[sid]["last"] = alerta["time"]
    if not siren_by_school[sid]["muted"]:
        siren_by_school[sid]["on"] = True

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
    sid = _get_school_id()
    alertas = alertas_by_school.get(sid, [])

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
            "school": sid,
            # formato antigo (Painel Central)
            "alertas": alertas,
            "siren_on": siren_by_school[sid]["on"],
            "siren_muted": siren_by_school[sid]["muted"],
            "last_alert_time": siren_by_school[sid]["last"],
            # formato novo (Painel Público)
            "ok": True,
            "alerts": alerts_public,
            "siren": siren_by_school[sid]["on"],
            "muted": siren_by_school[sid]["muted"],
            "active_alerts": active_alerts,
            "total_alerts": total_alerts,
            "last_update": siren_by_school[sid]["last"],
        }
    )


# ================================
# API – CONTROLE DA SIRENE (CENTRAL)
# ================================
@app.route("/api/siren", methods=["POST"])
@require_login(role="central")
def api_siren():
    sid = _get_school_id()
    data = request.get_json(silent=True) or {}
    action = data.get("action")

    if action == "on":
        if not siren_by_school[sid]["muted"]:
            siren_by_school[sid]["on"] = True
    elif action == "off":
        siren_by_school[sid]["on"] = False
    elif action == "mute":
        siren_by_school[sid]["muted"] = True
        siren_by_school[sid]["on"] = False
    elif action == "unmute":
        siren_by_school[sid]["muted"] = False
    else:
        return jsonify({"ok": False, "error": "Ação inválida"}), 400

    return jsonify(
        {
            "ok": True,
            "school": sid,
            "siren_on": siren_by_school[sid]["on"],
            "siren_muted": siren_by_school[sid]["muted"],
        }
    )


# ================================
# API – RESOLVER / LIMPAR ALERTAS
# ================================
@app.route("/api/resolve", methods=["POST"])
@require_login(role="central")
def api_resolve():
    sid = _get_school_id()
    for a in alertas_by_school.get(sid, []):
        a["status"] = "Resolvido"
    siren_by_school[sid]["on"] = False
    return jsonify({"ok": True, "school": sid})


@app.route("/api/clear", methods=["POST"])
@require_login(role="central")
def api_clear():
    sid = _get_school_id()
    alertas_by_school[sid] = []
    siren_by_school[sid] = {"on": False, "muted": False, "last": None}
    return jsonify({"ok": True, "school": sid})


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
@require_login(role="central")
def gerar_relatorio():
    sid = _get_school_id()
    alertas = alertas_by_school.get(sid, [])
    buffer = BytesIO()
    pdf = canvas.Canvas(buffer, pagesize=A4)
    largura, altura = A4

    pdf.setTitle("Relatório de Alertas - PROF-SAFE24 PREMIUM")

    pdf.setFont("Helvetica-Bold", 16)
    pdf.drawString(50, altura - 50, "PROF-SAFE24 PREMIUM - Relatório de Alertas")
    pdf.setFont("Helvetica", 10)
    pdf.drawString(50, altura - 62, f"Escola/Unidade: {sid}")
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
        download_name="relatorio_alertas_prof-safe24-premium.pdf",
        mimetype="application/pdf",
    )


# ================================
# EXECUTAR LOCAL
# ================================
if __name__ == "__main__":
    # Para testes locais
    app.run(host="0.0.0.0", port=5000, debug=os.getenv("FLASK_DEBUG") == "1")
