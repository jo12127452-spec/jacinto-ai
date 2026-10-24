import os
import time
import uuid
import datetime
import re
import secrets
import json
import hashlib
import hmac
import sys
import subprocess
import tempfile

import streamlit as st
import ollama

# ───────────────────────── 1. Configuração ─────────────────────────
st.set_page_config(page_title="Jacinto AI", page_icon="🤖", layout="centered",
                   initial_sidebar_state="expanded")

def _carregar_config_local():
    """Dados pessoais ficam em config_local.json (que NÃO vai para o GitHub)."""
    pasta = os.path.dirname(os.path.abspath(__file__))
    try:
        with open(os.path.join(pasta, "config_local.json"), encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}

CFG = _carregar_config_local()
NOME_USUARIO = CFG.get("nome_usuario", "")
MODELO_PADRAO = "jacinto"
TIPOS_IMAGEM = ["png", "jpg", "jpeg", "webp"]
TIPOS_TEXTO = ["txt", "md", "py", "lua", "js", "json", "csv", "html", "css"]
LIMITE_ARQUIVO_TEXTO = 4000     # caracteres por arquivo (menos = mais rápido)
MAX_MSGS_NA_TELA = 20           # só desenha as últimas N mensagens
MAX_CHATS_NA_LATERAL = 10
THREADS_PADRAO = os.cpu_count() or 2   # Pentium G2030 = 2 threads: usar os dois

SYSTEM_PADRAO = (
    "Você é o Jacinto, um assistente amigável e direto. Responda em português do "
    "Brasil, em texto natural e curto. Não escreva código a menos que o usuário peça."
)

# Textos extras: só entram no prompt quando a pergunta pede (deixa tudo mais rápido)
CRIADOR_TEXTO = CFG.get("sobre_criador") or (
    "SOBRE VOCÊ: você é o Jacinto, um assistente de IA de código aberto que roda "
    "localmente, no computador de quem te instalou, usando o Ollama e o modelo Llama 3.2. "
    "Se perguntarem quem te criou, diga que é um projeto open source feito por um "
    "desenvolvedor brasileiro iniciante, e que qualquer pessoa pode instalar e modificar."
)

CODIGO_PROMPT = (
    "MODO PROGRAMAÇÃO: entregue só o script. Regras: "
    "1) responda com o código COMPLETO e funcional em um único bloco, com a linguagem indicada; "
    "2) no máximo uma frase curta antes do código e nenhuma explicação longa depois; "
    "3) comentários curtos dentro do código; "
    "4) nunca invente bibliotecas, funções ou parâmetros que não existem; "
    "5) se faltar informação (linguagem, versão), assuma a opção mais comum, sem perguntar; "
    "6) para corrigir erro: uma frase com a causa e o código corrigido completo."
)

RE_CRIADOR = re.compile(
    r"quem (te |o |a )?(criou|fez|desenvolveu|programou|inventou)|"
    r"(seu|teu) (criador|dono|autor|desenvolvedor)|foi criad[oa]|te criou|"
    r"criad[oa] por|de onde (voc[êe]|vc) veio", re.I)

RE_CODIGO = re.compile(
    r"c[óo]digo|script|program(a|ar|ação|acao)\b|fun[çc][ãa]o|\bpython\b|\blua\b|"
    r"roblox|javascript|\bhtml\b|\bcss\b|\bsql\b|\bbug\b|\berro\b|algoritmo|"
    r"\bclasse\b|c\+\+|c#|csharp|\bunity\b|godot|\bluau\b|\bphp\b|\brust\b|kotlin|typescript|"
    r"powershell|\bbash\b|\bjava\b|\bapi\b|\bloop\b|\barray\b|compil|debug|traceback", re.I)

EXT_CODIGO = (".py", ".lua", ".js", ".html", ".css", ".json")

# ── Usuários e permissões (vêm do config_local.json) ──
SEU_EMAIL = CFG.get("seu_email", "")
CODIGO_ACESSO = CFG.get("codigo_acesso", "")
USUARIOS_CONHECIDOS = {k.strip().lower(): v for k, v in CFG.get("usuarios_conhecidos", {}).items()}
PERMITIR_EXECUTAR = bool(CFG.get("permitir_executar_codigo", False))  # botão "Executar código"

# ── Verificação de email por código (opcional) ──
SMTP_USUARIO = os.environ.get("JACINTO_SMTP_USUARIO") or CFG.get("smtp_usuario", "")
SMTP_SENHA = os.environ.get("JACINTO_SMTP_SENHA") or CFG.get("smtp_senha", "")
SMTP_HOST = CFG.get("smtp_host", "smtp.gmail.com")
SMTP_PORTA = int(CFG.get("smtp_porta", 465))
VERIFICAR_POR_CODIGO = bool(SMTP_USUARIO and SMTP_SENHA)

# CSS enxuto (sem seletores pesados)
st.markdown("""
<style>
    body, .stApp { background:#0d0d0d !important; color:#ececec !important; }
    #MainMenu, footer, .stDeployButton, [data-testid="stMainMenu"],
    [data-testid="stToolbarActions"], [data-testid="stDecoration"] { display:none !important; }
    [data-testid="stExpandSidebarButton"], [data-testid="collapsedControl"],
    [data-testid="stSidebarCollapseButton"] { display:flex !important; visibility:visible !important; }
    [data-testid="stExpandSidebarButton"] *, [data-testid="collapsedControl"] *,
    [data-testid="stSidebarCollapseButton"] * { color:#ececec !important; }
    .stMain .stButton > button { background:#1a1a1a !important; color:#dddddd !important;
        border:1px solid #2c2c2c !important; border-radius:14px !important; }
    .stMain .stButton > button:hover { border-color:#555 !important; color:#fff !important; }
    header[data-testid="stHeader"] { background:transparent !important; }
    .block-container { max-width:760px !important; padding-top:2rem !important; padding-bottom:6rem !important; }
    section[data-testid="stSidebar"] { background:#111 !important; border-right:1px solid #1f1f1f !important; }
    [data-testid^="stChatMessageAvatar"] { display:none !important; }
    .stChatMessage { background:transparent !important; padding:.5rem 0 !important; }
    [data-testid="stChatInput"] { background:#ffffff !important; border:1px solid #cfcfcf !important; border-radius:24px !important; }
    [data-testid="stChatInput"] > div, [data-testid="stChatInput"] div[data-baseweb] { background:#ffffff !important; }
    [data-testid="stChatInput"] textarea, [data-testid="stChatInputTextArea"] {
        color:#000000 !important; -webkit-text-fill-color:#000000 !important;
        caret-color:#000000 !important; background:transparent !important; }
    [data-testid="stChatInput"] textarea::placeholder { color:#6b6b6b !important; -webkit-text-fill-color:#6b6b6b !important; }
    [data-testid="stChatInput"] button { color:#222222 !important; }
    [data-testid="stBottom"] > div { background:#0d0d0d !important; }
    @media (max-width: 640px) { .block-container { padding-left:.8rem !important; padding-right:.8rem !important; padding-top:1rem !important; } }
</style>
""", unsafe_allow_html=True)

# ───────────────────────── Login ─────────────────────────

def fazer_login(email, nome_digitado):
    email = email.strip().lower()
    st.session_state.email = email
    if email in USUARIOS_CONHECIDOS:
        u = USUARIOS_CONHECIDOS[email]
        st.session_state.nome = u.get("nome", "visitante")
        st.session_state.contexto_usuario = "\n\n" + u.get("contexto", "")
        st.session_state.extra_criador = "\n" + u.get("extra", "")
    elif SEU_EMAIL and email == SEU_EMAIL.strip().lower():
        nome = NOME_USUARIO or "criador"
        st.session_state.nome = nome
        st.session_state.contexto_usuario = f"\n\nVocê está falando com {nome}, seu criador."
        st.session_state.extra_criador = ""
    else:
        nome = nome_digitado.strip().title() or "visitante"
        st.session_state.nome = nome
        st.session_state.contexto_usuario = f"\n\nVocê está falando com {nome}."
        st.session_state.extra_criador = ""

# ── Verificação do email ──
RE_EMAIL = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")

@st.cache_resource
def _codigos():
    return {}   # email -> {"hash", "expira", "tentativas", "envios": [timestamps]}

def dominio_existe(email):
    """Confere se o domínio do email existe e recebe emails (precisa do pacote dnspython)."""
    dominio = email.rsplit("@", 1)[-1]
    try:
        import dns.resolver
    except ImportError:
        return True  # sem dnspython, não dá para checar: não bloqueia
    try:
        dns.resolver.resolve(dominio, "MX", lifetime=4)
        return True
    except dns.resolver.NXDOMAIN:
        return False
    except dns.resolver.NoAnswer:
        try:
            dns.resolver.resolve(dominio, "A", lifetime=4)
            return True
        except Exception:
            return False
    except Exception:
        return True  # sem internet / timeout: não bloqueia

def enviar_email_codigo(email, codigo):
    import smtplib
    from email.message import EmailMessage
    msg = EmailMessage()
    msg["Subject"] = f"{codigo} é o seu código do Jacinto AI"
    msg["From"] = SMTP_USUARIO
    msg["To"] = email
    msg.set_content(f"Seu código de acesso ao Jacinto AI é: {codigo}\n\n"
                    "Ele vale por 10 minutos. Se não foi você que pediu, ignore este email.")
    if SMTP_PORTA == 587:
        with smtplib.SMTP(SMTP_HOST, SMTP_PORTA, timeout=15) as srv:
            srv.starttls()
            srv.login(SMTP_USUARIO, SMTP_SENHA)
            srv.send_message(msg)
    else:
        with smtplib.SMTP_SSL(SMTP_HOST, SMTP_PORTA, timeout=15) as srv:
            srv.login(SMTP_USUARIO, SMTP_SENHA)
            srv.send_message(msg)

def gerar_e_enviar_codigo(email):
    """Devolve None se enviou, ou um texto de erro."""
    reg = _codigos()
    agora = time.time()
    d = reg.setdefault(email, {"hash": "", "expira": 0, "tentativas": 0, "envios": []})
    d["envios"] = [t for t in d["envios"] if agora - t < 3600]
    if d["envios"] and agora - d["envios"][-1] < 45:
        return "Espere uns segundos antes de pedir outro código."
    if len(d["envios"]) >= 5:
        return "Muitos códigos pedidos. Tente de novo daqui a uma hora."
    codigo = f"{secrets.randbelow(10**6):06d}"
    try:
        enviar_email_codigo(email, codigo)
    except Exception:
        return "Não consegui enviar o email agora. Confira o endereço e tente de novo."
    d["hash"] = hashlib.sha256((codigo + email).encode()).hexdigest()
    d["expira"] = agora + 600
    d["tentativas"] = 0
    d["envios"].append(agora)
    return None

def conferir_codigo(email, digitado):
    d = _codigos().get(email)
    if not d or not d["hash"] or time.time() > d["expira"]:
        return "Esse código expirou. Peça um novo."
    if d["tentativas"] >= 5:
        return "Muitas tentativas erradas. Peça um novo código."
    d["tentativas"] += 1
    h = hashlib.sha256((digitado.strip() + email).encode()).hexdigest()
    if not hmac.compare_digest(h, d["hash"]):
        return "Código incorreto."
    d["hash"] = ""   # código só vale uma vez
    return None

# Sessões lembradas (sobrevivem ao F5 enquanto o app estiver aberto no PC)
@st.cache_resource
def _sessoes():
    return {}

def sair():
    try:
        _sessoes().pop(st.query_params.get("t"), None)
        st.query_params.clear()
    except Exception:
        pass
    for k in ("email", "nome", "contexto_usuario", "extra_criador", "exec_result", "chats", "current", "pending",
              "login_email", "login_nome", "login_manter"):
        st.session_state.pop(k, None)

# Volta sozinho para a conta se a página foi atualizada
if "email" not in st.session_state:
    try:
        _t = st.query_params.get("t")
    except Exception:
        _t = None
    if _t and _t in _sessoes():
        fazer_login(_sessoes()[_t]["email"], _sessoes()[_t]["nome"])

if "email" not in st.session_state:
    st.markdown("""
    <style>
        section[data-testid="stSidebar"], [data-testid="stExpandSidebarButton"],
        [data-testid="collapsedControl"] { display:none !important; }
        [data-testid="stForm"] { border:1px solid #2a2a2a !important; border-radius:18px !important;
            background:#141414 !important; padding:1.4rem !important; }
        [data-testid="stForm"] label p { color:#bbbbbb !important; font-size:.9rem; }
        [data-testid="stForm"] [data-baseweb="input"], [data-testid="stForm"] [data-baseweb="base-input"] {
            background:#1f1f1f !important; border-radius:12px !important; border-color:#2f2f2f !important; }
        [data-testid="stForm"] input { background:#1f1f1f !important; color:#ffffff !important;
            -webkit-text-fill-color:#ffffff !important; caret-color:#ffffff !important; }
        [data-testid="stForm"] input::placeholder { color:#777777 !important; -webkit-text-fill-color:#777777 !important; }
        [data-testid="stFormSubmitButton"] button { background:#ffffff !important; color:#000000 !important;
            border:none !important; border-radius:12px !important; font-weight:600 !important; padding:.55rem 0 !important; }
        [data-testid="stFormSubmitButton"] button:hover { background:#e6e6e6 !important; }
    </style>
    <div style="text-align:center;margin-top:7vh;margin-bottom:1.6rem;">
        <div style="font-size:3.4rem;line-height:1;">🤖</div>
        <h1 style="font-weight:600;font-size:2.2rem;margin:.6rem 0 .3rem;">Jacinto AI</h1>
        <p style="color:#888;margin:0;">Entre com seu email para conversar</p>
    </div>
    """, unsafe_allow_html=True)
    def _entrar(email, nome, manter):
        fazer_login(email, nome)
        if manter:
            try:
                reg = _sessoes()
                if len(reg) > 50:
                    reg.pop(next(iter(reg)))
                token = secrets.token_urlsafe(16)
                reg[token] = {"email": email.strip().lower(), "nome": nome}
                st.query_params["t"] = token
            except Exception:
                pass
        for k in ("login_email", "login_nome", "login_manter"):
            st.session_state.pop(k, None)
        st.rerun()

    pendente = st.session_state.get("login_email")

    if not pendente:
        # ── Etapa 1: email ──
        with st.form("login"):
            email_in = st.text_input("Email", placeholder="seuemail@gmail.com")
            nome_in = st.text_input("Como quer ser chamado? (opcional)")
            codigo_in = st.text_input("Código de acesso", type="password") if CODIGO_ACESSO else ""
            manter = st.checkbox("Manter conectado neste aparelho", value=True)
            enviar = st.form_submit_button("Continuar" if VERIFICAR_POR_CODIGO else "Entrar",
                                           use_container_width=True)
        if enviar:
            email_ok = email_in.strip().lower()
            if not RE_EMAIL.match(email_ok):
                st.error("Digite um email válido.")
            elif CODIGO_ACESSO and codigo_in != CODIGO_ACESSO:
                st.error("Código de acesso incorreto.")
            elif not dominio_existe(email_ok):
                st.error("Esse endereço de email não parece existir. Confira se digitou certo.")
            elif VERIFICAR_POR_CODIGO:
                with st.spinner("Enviando o código para o seu email…"):
                    erro = gerar_e_enviar_codigo(email_ok)
                if erro:
                    st.error(erro)
                else:
                    st.session_state.login_email = email_ok
                    st.session_state.login_nome = nome_in
                    st.session_state.login_manter = manter
                    st.rerun()
            else:
                _entrar(email_ok, nome_in, manter)
        rodape = ("🔒 Seu email é confirmado por um código. Nada é enviado para empresas de IA."
                  if VERIFICAR_POR_CODIGO else
                  "🔒 Tudo roda no computador de quem hospeda o app. Nada é enviado para empresas de IA.")
        st.markdown(f"<p style='text-align:center;color:#666;font-size:.8rem;margin-top:1rem;'>{rodape}</p>",
                    unsafe_allow_html=True)
    else:
        # ── Etapa 2: código recebido por email ──
        st.markdown(f"<p style='text-align:center;color:#aaa;'>Enviamos um código de 6 dígitos para "
                    f"<b>{pendente}</b>.<br>Ele vale por 10 minutos. Veja também a caixa de spam.</p>",
                    unsafe_allow_html=True)
        with st.form("verificar"):
            cod = st.text_input("Código de 6 dígitos", max_chars=6, placeholder="123456")
            ok = st.form_submit_button("Entrar", use_container_width=True)
        if ok:
            erro = conferir_codigo(pendente, cod)
            if erro:
                st.error(erro)
            else:
                _entrar(pendente, st.session_state.get("login_nome", ""),
                        st.session_state.get("login_manter", True))
        c1, c2 = st.columns(2)
        if c1.button("Reenviar código", use_container_width=True):
            erro = gerar_e_enviar_codigo(pendente)
            st.error(erro) if erro else st.success("Código reenviado.")
        if c2.button("Usar outro email", use_container_width=True):
            for k in ("login_email", "login_nome", "login_manter"):
                st.session_state.pop(k, None)
            st.rerun()
    st.stop()

# ───────────────────────── 2. Estado ─────────────────────────
def novo_chat():
    atual = st.session_state.chats.get(st.session_state.current)
    if atual and not atual["messages"]:
        return  # já está numa conversa vazia
    cid = uuid.uuid4().hex[:8]
    st.session_state.chats[cid] = {"title": "Nova conversa", "messages": []}
    st.session_state.current = cid
    st.session_state.pending = False

def abrir_chat(cid):
    st.session_state.current = cid
    st.session_state.pending = False

def apagar_chat(cid):
    st.session_state.chats.pop(cid, None)
    if st.session_state.current == cid:
        if st.session_state.chats:
            st.session_state.current = next(iter(st.session_state.chats))
        else:
            novo_chat()
    st.session_state.pending = False

def regenerar():
    msgs = st.session_state.chats[st.session_state.current]["messages"]
    if msgs and msgs[-1]["role"] == "assistant":
        msgs.pop()
        st.session_state.pending = True

# ───────────────────────── Salvar / carregar conversas ─────────────────────────
PASTA_DADOS = os.path.join(os.path.dirname(os.path.abspath(__file__)), "dados_jacinto")

def _arquivo_usuario():
    h = hashlib.sha256(st.session_state.email.encode("utf-8")).hexdigest()[:16]
    return os.path.join(PASTA_DADOS, f"chats_{h}.json")

def salvar_chats():
    """Grava as conversas do usuário em arquivo (imagens não são salvas)."""
    try:
        limpo = {}
        for cid, c in st.session_state.chats.items():
            msgs = []
            for m in c["messages"]:
                mm = {k: v for k, v in m.items() if k != "images"}
                mm["images"] = []
                if m.get("images"):
                    mm["n_imgs"] = len(m["images"])
                msgs.append(mm)
            limpo[cid] = {"title": c["title"], "messages": msgs}
        texto = json.dumps({"current": st.session_state.current, "chats": limpo}, ensure_ascii=False)
        if st.session_state.get("_ultimo_save") == texto:
            return  # nada mudou
        os.makedirs(PASTA_DADOS, exist_ok=True)
        arq = _arquivo_usuario()
        with open(arq + ".tmp", "w", encoding="utf-8") as f:
            f.write(texto)
        os.replace(arq + ".tmp", arq)
        st.session_state["_ultimo_save"] = texto
    except Exception:
        pass

def carregar_chats():
    try:
        with open(_arquivo_usuario(), encoding="utf-8") as f:
            d = json.load(f)
        chats = d.get("chats") or {}
        if chats:
            cur = d.get("current")
            return chats, (cur if cur in chats else list(chats)[-1])
    except Exception:
        pass
    return None, None

if "chats" not in st.session_state:
    st.session_state.pending = False
    _salvos, _cur = carregar_chats()
    if _salvos:
        st.session_state.chats, st.session_state.current = _salvos, _cur
    else:
        st.session_state.chats = {}
        st.session_state.current = None
        novo_chat()

@st.cache_data(ttl=10, show_spinner=False)
def estado_ollama():
    """(ligado?, lista de modelos). Cache curto: não consulta o Ollama a cada clique."""
    try:
        nomes = []
        for m in ollama.list()["models"]:
            try:
                nomes.append(m["model"])
            except (KeyError, TypeError):
                nomes.append(m["name"])
        return True, (nomes or [MODELO_PADRAO])
    except Exception:
        return False, [MODELO_PADRAO]

def listar_modelos():
    return estado_ollama()[1]

def _motivo_fim(chunk):
    try:
        return chunk["done_reason"]
    except Exception:
        return getattr(chunk, "done_reason", None)

def explicar_erro(e, modelo):
    msg = str(e).lower()
    if any(k in msg for k in ("connect", "refused", "10061", "winerror", "unreachable", "timed out")):
        return ("🔌 Não consegui falar com o Ollama. Ele deve estar desligado: abra o Ollama "
                "pelo menu Iniciar, espere alguns segundos e tente de novo.")
    if "not found" in msg or getattr(e, "status_code", None) == 404:
        return f"📦 O modelo '{modelo}' não foi encontrado. Baixe com: ollama pull {modelo}"
    if "memory" in msg:
        return "🧠 Faltou memória para carregar esse modelo. Feche outros programas ou use um modelo menor."
    return f"Erro ao comunicar com o modelo local: {e}"

# ───────────────────────── Executar código (Python) ─────────────────────────
RE_BLOCO_PY = re.compile(r"```(?:python|py)[ \t]*\n(.*?)```", re.S | re.I)
PROIBIDO = ["os.remove", "os.unlink", "os.rmdir", "os.removedirs", "shutil", "os.system",
            "os.popen", "subprocess", "socket", "ctypes", "winreg", "__import__",
            "eval(", "exec(", "urllib", "requests", "pip install"]
RE_ESCRITA = re.compile(r"open\([^)]*['\"][^'\"]*[wax+][^'\"]*['\"]")

def rodar_python(codigo):
    """Roda o código numa pasta temporária, com limite de 10 s. Bloqueia o que é perigoso."""
    for b in PROIBIDO:
        if b in codigo:
            return {"ok": False, "saida": "", "erro": f"Bloqueado por segurança: o código usa '{b}'."}
    if RE_ESCRITA.search(codigo):
        return {"ok": False, "saida": "", "erro": "Bloqueado por segurança: o código tenta gravar arquivos."}
    with tempfile.TemporaryDirectory() as d:
        arq = os.path.join(d, "codigo.py")
        with open(arq, "w", encoding="utf-8") as f:
            f.write(codigo)
        try:
            r = subprocess.run([sys.executable, arq], cwd=d, capture_output=True, text=True,
                               timeout=10, stdin=subprocess.DEVNULL, encoding="utf-8",
                               errors="replace", env={**os.environ, "PYTHONIOENCODING": "utf-8"})
            return {"ok": r.returncode == 0, "saida": r.stdout[-2000:], "erro": r.stderr[-1500:]}
        except subprocess.TimeoutExpired:
            return {"ok": False, "saida": "", "erro": "O código passou de 10 segundos e foi interrompido."}

def executar(i, codigo):
    st.session_state.exec_result = {"cid": st.session_state.current, "i": i, **rodar_python(codigo)}

def pedir_correcao(erro):
    texto = f"O código deu este erro. Corrija e mostre o código completo:\n```\n{erro}\n```"
    st.session_state.chats[st.session_state.current]["messages"].append(
        {"role": "user", "content": texto, "model_content": texto, "images": [], "files": []})
    st.session_state.exec_result = None
    st.session_state.pending = True

def painel_codigo(i, texto):
    if not PERMITIR_EXECUTAR:
        return
    blocos = RE_BLOCO_PY.findall(texto)
    if not blocos:
        return
    codigo = max(blocos, key=len)
    st.button("▶️ Executar código", key=f"x_{i}", on_click=executar, args=(i, codigo))
    r = st.session_state.get("exec_result")
    if r and r["cid"] == st.session_state.current and r["i"] == i:
        if r["saida"]:
            st.code(r["saida"], language=None)
        if r["ok"]:
            st.success("Rodou sem erros ✅")
        else:
            st.error("Deu erro ❌")
            st.code(r["erro"], language=None)
            st.button("🛠 Pedir correção ao Jacinto", key=f"c_{i}", on_click=pedir_correcao, args=(r["erro"],))

SUGESTOES = [
    ("💡 Explicar um assunto", "Me explique de um jeito simples como funciona a inteligência artificial."),
    ("💻 Criar um código", "Faça um código em Python que mostre a tabuada do 7."),
    ("✍️ Escrever um texto", "Me ajude a escrever uma mensagem simpática para um amigo."),
    ("🎲 Curiosidade", "Me conte uma curiosidade interessante."),
]

def usar_sugestao(texto):
    chat = st.session_state.chats[st.session_state.current]
    chat["messages"].append({"role": "user", "content": texto, "model_content": texto,
                             "images": [], "files": []})
    chat["title"] = texto[:40]
    st.session_state.pending = True

# ───────────────────────── 3. Barra lateral ─────────────────────────
with st.sidebar:
    st.markdown("### 🤖 Jacinto AI")
    st.button("➕  Nova conversa", on_click=novo_chat, use_container_width=True)
    _ativo, _ = estado_ollama()
    st.caption("🟢 Ollama ligado" if _ativo else "🔴 Ollama desligado: abra o Ollama")
    st.caption("Conversas")
    for cid, chat in list(reversed(list(st.session_state.chats.items())))[:MAX_CHATS_NA_LATERAL]:
        c1, c2 = st.columns([0.82, 0.18])
        marc = "● " if cid == st.session_state.current else ""
        c1.button(f"{marc}{chat['title'][:24]}", key=f"o_{cid}", on_click=abrir_chat,
                  args=(cid,), use_container_width=True)
        c2.button("🗑", key=f"d_{cid}", on_click=apagar_chat, args=(cid,))

    st.markdown("---")
    with st.expander("⚙️ Ajustes"):
        modelos = listar_modelos()
        idx = modelos.index(MODELO_PADRAO) if MODELO_PADRAO in modelos else 0
        modelo = st.selectbox("Modelo", modelos, index=idx)
        modelo_visao = st.selectbox("Modelo para imagens", ["(nenhum)"] + modelos)
        _cod = [m for m in modelos if "coder" in m.lower()]
        _op = ["(nenhum)"] + modelos
        modelo_codigo = st.selectbox("Modelo para programação", _op,
                                     index=_op.index(_cod[0]) if _cod else 0,
                                     help="Usado automaticamente quando você pede código. Sugestão: qwen2.5-coder:1.5b")
        modo_leve = st.toggle("Modo leve (atualiza a tela 1 vez por segundo)", value=True)
        temperatura = st.slider("Criatividade", 0.1, 1.0, 0.3, 0.1)
        limite_tokens = st.number_input("Limite de resposta", 64, 4096, 384, 64)
        contexto = st.select_slider("Memória (contexto)", [512, 1024, 2048, 4096], value=1024)
        n_historico = st.slider("Mensagens lembradas", 2, 20, 4, 2)
        threads = st.slider("Threads da CPU", 1, os.cpu_count() or 8, THREADS_PADRAO)
        system_prompt = st.text_area("Personalidade", SYSTEM_PADRAO, height=120)

    chat_atual = st.session_state.chats[st.session_state.current]
    if chat_atual["messages"]:
        md = "\n\n".join(f"**{'Você' if m['role']=='user' else 'Jacinto'}:** {m['content']}"
                         for m in chat_atual["messages"])
        st.download_button("⬇️ Exportar conversa", md, file_name="conversa.md", use_container_width=True)
    st.caption(f"👤 **{st.session_state.nome}**")
    st.button("Sair", on_click=sair, use_container_width=True)

# ───────────────────────── 4. Entrada ─────────────────────────
try:
    entrada = st.chat_input("Pergunte qualquer coisa…", accept_file="multiple",
                            file_type=TIPOS_IMAGEM + TIPOS_TEXTO)
except TypeError:
    entrada = st.chat_input("Pergunte qualquer coisa…")

if entrada is None:
    texto, arquivos = "", []
elif isinstance(entrada, str):
    texto, arquivos = entrada, []
else:
    texto, arquivos = entrada["text"] or "", entrada["files"] or []

mensagens = chat_atual["messages"]

if texto.strip() or arquivos:
    imagens, nomes, blocos = [], [], []
    for f in arquivos:
        ext = f.name.rsplit(".", 1)[-1].lower()
        nomes.append(f.name)
        if ext in TIPOS_IMAGEM:
            imagens.append(f.getvalue())
        else:
            conteudo = f.getvalue().decode("utf-8", errors="replace")[:LIMITE_ARQUIVO_TEXTO]
            blocos.append(f"[Arquivo: {f.name}]\n{conteudo}")
    conteudo_modelo = texto.strip()
    if blocos:
        conteudo_modelo = "\n\n".join(blocos) + "\n\n" + conteudo_modelo
    mensagens.append({"role": "user", "content": texto.strip() or "(anexo)",
                      "model_content": conteudo_modelo or "Analise o anexo.",
                      "images": imagens, "files": nomes})
    if chat_atual["title"] == "Nova conversa":
        chat_atual["title"] = (texto.strip() or nomes[0])[:40]
    st.session_state.pending = True

# ───────────────────────── 5. Tela ─────────────────────────
if not mensagens:
    h = datetime.datetime.now().hour
    saud = "Bom dia" if h < 12 else "Boa tarde" if h < 18 else "Boa noite"
    st.markdown("<br><br><br>", unsafe_allow_html=True)
    st.markdown(f"<h1 style='text-align:center;font-weight:500;font-size:2.4rem;'>{saud}, {st.session_state.nome}</h1>"
                "<p style='text-align:center;color:#777;font-size:1.05rem;'>Como posso ajudar você hoje?</p>",
                unsafe_allow_html=True)

if not mensagens:
    _c1, _c2 = st.columns(2)
    for _n, (_rot, _txt) in enumerate(SUGESTOES):
        (_c1 if _n % 2 == 0 else _c2).button(_rot, key=f"s_{_n}", on_click=usar_sugestao,
                                             args=(_txt,), use_container_width=True)

if len(mensagens) > MAX_MSGS_NA_TELA:
    st.caption(f"… {len(mensagens) - MAX_MSGS_NA_TELA} mensagens antigas ocultas para manter leve")

inicio_vis = max(0, len(mensagens) - MAX_MSGS_NA_TELA)
for i in range(inicio_vis, len(mensagens)):
    m = mensagens[i]
    with st.chat_message(m["role"]):
        for img in m.get("images", []):
            st.image(img, width=240)
        if m.get("n_imgs") and not m.get("images"):
            st.caption(f"🖼 {m['n_imgs']} imagem(ns) anexada(s) (não ficam salvas)")
        if m.get("files"):
            st.caption("📎 " + ", ".join(m["files"]))
        st.markdown(m["content"])
        if m.get("aviso"):
            st.caption(m["aviso"])
        if m["role"] == "assistant" and m.get("tempo"):
            st.caption(f"⚡ {m['tempo']}s")
            if i == len(mensagens) - 1 and not st.session_state.pending:
                st.button("🔄 Regenerar", key=f"r_{i}", on_click=regenerar)
        if m["role"] == "assistant" and i == len(mensagens) - 1 and not st.session_state.pending:
            painel_codigo(i, m["content"])

_erro_anterior = st.session_state.pop("erro_msg", None)
if _erro_anterior:
    st.error(_erro_anterior)

# ───────────────────────── 6. Resposta ─────────────────────────
if st.session_state.pending and mensagens and mensagens[-1]["role"] == "user":
    ultima = mensagens[-1]
    modelo_uso = modelo

    # Prompt dinâmico: só inclui o que a pergunta realmente precisa
    sistema = system_prompt + st.session_state.contexto_usuario
    if RE_CRIADOR.search(ultima["content"]):
        sistema += "\n\n" + CRIADOR_TEXTO + st.session_state.get("extra_criador", "")
    modo_codigo = bool(RE_CODIGO.search(ultima["content"])) or any(
        n.lower().endswith(EXT_CODIGO) for n in ultima.get("files", []))
    temp_uso, tokens_uso, ctx_uso = temperatura, int(limite_tokens), int(contexto)
    if modo_codigo:
        sistema += "\n\n" + CODIGO_PROMPT
        temp_uso = min(temperatura, 0.2)          # código pede precisão, não criatividade
        tokens_uso = max(tokens_uso, 768)
        ctx_uso = max(ctx_uso, 2048)
        if modelo_codigo != "(nenhum)":
            modelo_uso = modelo_codigo

    historico = [{"role": "system", "content": sistema}]
    for m in mensagens[-n_historico:]:
        item = {"role": m["role"], "content": m.get("model_content", m["content"])}
        if m is ultima and m.get("images"):
            if modelo_visao != "(nenhum)":
                item["images"] = m["images"]
                modelo_uso = modelo_visao
            else:
                st.warning("Imagem ignorada: escolha um modelo de visão em ⚙️ Ajustes.")
        historico.append(item)

    intervalo = 1.0 if modo_leve else 0.25   # segundos entre atualizações da tela

    salvar_chats()   # a pergunta já fica salva antes de gerar
    with st.chat_message("assistant"):
        espaco = st.empty()
        slot_parar = st.empty()
        texto_completo, ultimo_update = "", 0.0
        inicio = time.time()
        stream = None
        concluido = False
        motivo = None
        ultimo_chunk = None
        try:
            espaco.markdown("▌")
            slot_parar.button("⏹ Parar", key="parar_ger")
            stream = ollama.chat(
                model=modelo_uso, messages=historico, stream=True, keep_alive="30m",
                options={"temperature": temp_uso, "num_predict": tokens_uso,
                         "num_ctx": ctx_uso, "num_thread": int(threads), "num_batch": 128},
            )
            for chunk in stream:
                ultimo_chunk = chunk
                texto_completo += chunk["message"]["content"]
                agora = time.time()
                if agora - ultimo_update >= intervalo:
                    espaco.markdown(texto_completo + "▌")
                    ultimo_update = agora
            espaco.markdown(texto_completo)
            slot_parar.empty()
            tempo = round(time.time() - inicio, 1)
            st.caption(f"⚡ {tempo}s")
            msg_final = {"role": "assistant", "content": texto_completo, "tempo": tempo}
            if _motivo_fim(ultimo_chunk) == "length":
                msg_final["aviso"] = ("⚠️ Resposta cortada pelo limite de tamanho. "
                                      "Aumente o \"Limite de resposta\" em ⚙️ Ajustes.")
                st.caption(msg_final["aviso"])
            mensagens.append(msg_final)
            concluido = True
            st.button("🔄 Regenerar", key=f"r_{len(mensagens)-1}", on_click=regenerar)
            painel_codigo(len(mensagens) - 1, texto_completo)
        except Exception as e:
            slot_parar.empty()
            espaco.empty()
            motivo = explicar_erro(e, modelo_uso)
            st.session_state.erro_msg = motivo
            st.error(motivo)
        finally:
            # Se o botão Parar foi clicado, a execução é interrompida aqui: guarda o que já saiu
            if stream is not None:
                try:
                    stream.close()
                except Exception:
                    pass
            if not concluido and texto_completo.strip():
                mensagens.append({"role": "assistant", "content": texto_completo,
                                  "tempo": round(time.time() - inicio, 1),
                                  "aviso": ("⚠️ " + motivo) if motivo else
                                           "⚠️ Resposta interrompida (botão Parar, página recarregada ou conexão perdida)."})
            st.session_state.pending = False
            salvar_chats()

# Salva no fim de cada execução (cobre trocar/apagar conversa, regenerar etc.)
salvar_chats()
