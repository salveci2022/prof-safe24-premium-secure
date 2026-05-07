# 🚨 PROF-SAFE 24 — Sistema de Segurança Escolar

<div align="center">

![Python](https://img.shields.io/badge/Python-3.10+-3776AB?style=for-the-badge&logo=python&logoColor=white)
![Flask](https://img.shields.io/badge/Flask-2.x-000000?style=for-the-badge&logo=flask&logoColor=white)
![Render](https://img.shields.io/badge/Deploy-Render.com-46E3B7?style=for-the-badge&logo=render&logoColor=white)
![WhatsApp](https://img.shields.io/badge/WhatsApp-Z--API-25D366?style=for-the-badge&logo=whatsapp&logoColor=white)
![License](https://img.shields.io/badge/Licença-Proprietária-red?style=for-the-badge)

**Sistema de botão de pânico silencioso para professores da rede estadual de ensino.**  
Alertas em tempo real · Notificação via WhatsApp e Email · Painel multi-escola · Relatório PDF

[🔴 Demo ao Vivo](https://prof-safe24-premium-secure-pd90.onrender.com) · [📋 Documentação](#documentação) · [🚀 Deploy](#deploy-no-rendercom)

</div>

---

## 📋 Índice

- [Sobre o Sistema](#sobre-o-sistema)
- [Funcionalidades](#funcionalidades)
- [Perfis de Acesso](#perfis-de-acesso)
- [Stack Tecnológica](#stack-tecnológica)
- [Estrutura do Projeto](#estrutura-do-projeto)
- [Instalação Local](#instalação-local)
- [Variáveis de Ambiente](#variáveis-de-ambiente)
- [Deploy no Render.com](#deploy-no-rendercom)
- [Testando via CMD](#testando-via-cmd)
- [Fluxo do Alerta](#fluxo-do-alerta)
- [Logins de Demonstração](#logins-de-demonstração)
- [Desenvolvido por](#desenvolvido-por)

---

## Sobre o Sistema

O **PROF-SAFE 24** é uma solução SaaS de segurança escolar desenvolvida para a rede estadual de ensino de Goiás. Permite que professores acionem um **botão de pânico silencioso** em situações de risco, notificando instantaneamente a equipe gestora da escola, a Secretaria de Educação e o Responsável Estadual de Segurança.

> 💡 **Único no Brasil** — Sistema multi-escola, multi-perfil, com notificação via WhatsApp, Email e painel centralizado em tempo real.

---

## Funcionalidades

### 🔴 Painel do Professor
- Botão SOS com acionamento em um clique
- Seleção rápida de tipo de ocorrência (8 categorias)
- Identificação por escola, sala e nome
- Sem necessidade de login — acesso imediato

### 🖥️ Painel Central (Diretor / Coordenador)
- Atualização em tempo real (polling a cada 1,5s)
- Esfera de status: **NORMAL** → **ALERTA**
- Tabela de alertas com histórico completo
- Controle manual da sirene
- Resolver e limpar alertas
- Download de relatório PDF

### 🗺️ Painel Estadual
- Visão de todas as escolas monitoradas
- Contadores por escola em tempo real
- Filtro por escola no feed de alertas
- Exclusão de escolas pelo painel

### 🏛️ Painel Secretaria
- Visão consolidada por escola
- Resolução e limpeza de alertas

### 📱 Notificações Automáticas
- WhatsApp via **Z-API** para diretores, coordenadores, secretaria e responsável estadual
- Email via **Gmail SMTP** para os mesmos perfis
- Mensagem formatada com escola, professor, sala, ocorrência e horário

### 📄 Relatório PDF
- Gerado com ReportLab
- Filtro por escola ou geral
- Download direto pelo painel

### 💜 Bem-Estar do Professor
- Chat de apoio emocional com IA (Claude Haiku)
- Exercício de respiração guiada
- Seletor de humor
- CVV integrado para situações críticas

### 🔐 Administração
- Cadastro e exclusão de escolas
- Cadastro e exclusão de usuários
- Atribuição de perfis e escolas

---

## Perfis de Acesso

| Perfil | Acesso | Descrição |
|---|---|---|
| `professor` | `/professor` | Envia SOS — sem login |
| `diretor` | `/central` | Painel da escola |
| `coordenador` | `/central` | Painel da escola |
| `secretaria` | `/painel_secretaria` | Visão regional |
| `estadual` | `/painel_estado` | Visão estadual completa |
| `admin` | `/admin` | Gestão total do sistema |

---

## Stack Tecnológica

| Camada | Tecnologia |
|---|---|
| Backend | Python 3.10+ / Flask 2.x |
| Frontend | HTML5 / CSS3 / JavaScript puro (sem frameworks) |
| Persistência | JSON file-based (alertas.json, users.json, escolas.json) |
| Notificações | Z-API (WhatsApp) / Gmail SMTP |
| PDF | ReportLab |
| IA | Anthropic Claude Haiku (bem-estar) |
| Deploy | Render.com (Web Service) |
| Proxy | Werkzeug ProxyFix |
| PWA | manifest.json + service worker |

---

## Estrutura do Projeto

```
prof-safe24/
├── app.py                  # Backend principal — Flask
├── requirements.txt        # Dependências Python
├── users.json              # Usuários (criado automaticamente)
├── escolas.json            # Escolas (criado automaticamente)
├── alertas.json            # Histórico de alertas
├── state.json              # Estado da sirene e último alerta
├── static/
│   ├── siren.mp3           # Áudio da sirene
│   ├── manifest.json       # PWA manifest
│   └── ...
└── templates/
    ├── home.html           # Página inicial
    ├── professor.html      # Painel do professor (SOS)
    ├── central.html        # Painel central (diretor/coord)
    ├── painel_estado.html  # Painel estadual
    ├── painel_secretaria.html
    ├── painel_publico.html
    ├── admin.html
    ├── login.html
    ├── bem_estar_prof.html
    └── acesso_negado.html
```

---

## Instalação Local

### Pré-requisitos
- Python 3.10+
- pip

### Passo a passo

```bash
# 1. Clonar o repositório
git clone https://github.com/salveci2022/prof-safe24-premium-secure.git
cd prof-safe24-premium-secure

# 2. Instalar dependências
pip install -r requirements.txt

# 3. Rodar o sistema
python app.py
```

Acesse: `http://localhost:5000`

---

## Variáveis de Ambiente

Configure no Render.com → **Environment Variables**:

| Variável | Descrição | Obrigatório |
|---|---|---|
| `SECRET_KEY` | Chave secreta Flask | ✅ |
| `ESTADO_NOME` | Nome do estado (ex: Goiás) | ✅ |
| `ESTADO_SIGLA` | Sigla do estado (ex: GO) | ✅ |
| `ESTADO_CIDADE` | Cidade sede (ex: Goiânia) | ✅ |
| `SISTEMA_TITULO` | Nome do sistema | ✅ |
| `ZAPI_INSTANCE` | ID da instância Z-API | WhatsApp |
| `ZAPI_TOKEN` | Token Z-API | WhatsApp |
| `ZAPI_CLIENT_TOKEN` | Client Token Z-API | WhatsApp |
| `GMAIL_USER` | Email Gmail remetente | Email |
| `GMAIL_APP_PASS` | Senha de app Gmail | Email |
| `WHATS_ESTADUAL` | WhatsApp do responsável estadual | Notif. |
| `WHATS_SECEDUC` | WhatsApp da secretaria | Notif. |
| `EMAIL_ESTADUAL` | Email do responsável estadual | Notif. |
| `EMAIL_SECEDUC` | Email da secretaria | Notif. |
| `ANTHROPIC_API_KEY` | Chave Anthropic (bem-estar IA) | IA |

---

## Deploy no Render.com

```bash
# 1. Commitar as alterações
git add .
git commit -m "deploy: prof-safe24 production"
git push origin main
```

O Render detecta o push e faz o deploy automaticamente.

**Configurações no Render:**
- **Environment:** Python
- **Build Command:** `pip install -r requirements.txt`
- **Start Command:** `python app.py`
- **Instance Type:** Free (ou superior para produção)

---

## Testando via CMD

### Verificar se está online:
```cmd
curl http://localhost:5000/api/status
```

### Disparar alerta de teste:
```cmd
curl -X POST http://localhost:5000/api/alert -H "Content-Type: application/json" -d "{\"teacher\":\"Prof. Teste\",\"room\":\"Sala 10\",\"description\":\"Teste CMD\",\"escola_id\":\"escola_001\"}"
```

### Limpar alertas após teste:
```cmd
curl -X POST http://localhost:5000/api/clear -H "Content-Type: application/json" -d "{\"escola_id\":\"escola_001\"}"
```

---

## Fluxo do Alerta

```
Professor clica SOS
        │
        ▼
POST /api/alert (sem login necessário)
        │
        ▼
Backend salva alerta + ativa sirene (siren_on: true)
        │
        ├──▶ WhatsApp Z-API → Diretor / Secretaria / Estadual
        └──▶ Gmail SMTP    → Diretor / Secretaria / Estadual
        │
        ▼
Painéis fazem polling GET /api/status (a cada 1,5~2s)
        │
        ▼
Painel Central / Estadual / Secretaria atualizam:
  • Esfera: NORMAL → ALERTA (vermelho)
  • Tabela: alerta aparece imediatamente
  • Sirene: toca automaticamente
  • Status: muda para ⚠️ ALERTA ATIVO
```

---

## Logins de Demonstração

| Usuário | Senha | Perfil | Acesso |
|---|---|---|---|
| `admin` | `admin2026` | Administrador | `/admin` |
| `estadual` | `estadual2026` | Responsável Estadual | `/painel_estado` |
| `secretaria` | `seceduc2026` | Secretaria de Educação | `/painel_secretaria` |
| `diretor001` | `diretor001` | Diretor — Escola 001 | `/central` |
| `coord001` | `coord001` | Coordenador — Escola 001 | `/central` |

> ⚠️ Altere as senhas antes de ir para produção.

---

## Desenvolvido por

<div align="center">

**SPYNET Security — Tecnologia Forense & Soluções Digitais**

[![WhatsApp](https://img.shields.io/badge/WhatsApp-Contato-25D366?style=for-the-badge&logo=whatsapp&logoColor=white)](https://wa.me/5561999999999)
[![GitHub](https://img.shields.io/badge/GitHub-salveci2022-181717?style=for-the-badge&logo=github&logoColor=white)](https://github.com/salveci2022)

**Salveci dos Santos**  
Fundador & CEO — SPYNET Tecnologia Forense & Soluções Digitais Ltda  
CNPJ: 64.000.808/0001-51 — Brasília/DF

---

*© 2025 SPYNET Security — Todos os direitos reservados.*  
*Sistema proprietário. Proibida reprodução sem autorização.*

</div>
