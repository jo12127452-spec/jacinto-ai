# 🤖 Jacinto AI

Assistente de IA **100% local**: roda no seu computador com o [Ollama](https://ollama.com), sem enviar suas conversas para nenhuma empresa. Interface de chat feita com Streamlit, pensada para rodar até em PC fraco, sem placa de vídeo.

## O que ele faz
- Conversa em português, com respostas em tempo real e botão **Parar**.
- **Modo programação** automático (Python, Lua, C++, C#, JavaScript…): quando você pede código, ele usa um prompt e um modelo próprios para isso e entrega só o script.
- Anexa arquivos de texto/código e imagens (imagens precisam de um modelo com visão).
- Várias conversas por usuário, salvas em arquivo.
- Login por email, com **código de confirmação** enviado ao email (opcional).
- Funciona no celular, pelo navegador, na mesma rede Wi-Fi.
- Botão opcional para **executar código Python** e pedir correção do erro.

## Requisitos
- Windows, Linux ou macOS
- [Python 3.10+](https://www.python.org/downloads/)
- [Ollama](https://ollama.com/download) instalado e aberto
- 8 GB de RAM recomendados (4 GB funcionam com modelos de 1B)

## Instalação
```bash
git clone https://github.com/SEU_USUARIO/jacinto-ai.git
cd jacinto-ai
pip install -r requirements.txt

ollama pull llama3.2:1b
ollama pull qwen2.5-coder:1.5b   # opcional, melhora o modo programação
```

Crie o modelo `jacinto` (opcional; se pular, escolha `llama3.2:1b` em ⚙️ Ajustes):
```bash
echo FROM llama3.2:1b > Modelfile
ollama create jacinto -f Modelfile
```

## Rodar
```bash
streamlit run app.py
```
No Windows, você também pode dar dois cliques em `iniciar_jacinto.bat`: ele liga o Ollama, baixa a prioridade dele para o PC não travar e mostra o endereço para abrir no celular.

## Configuração (opcional)
Copie `config_local.exemplo.json` para `config_local.json` e edite. Esse arquivo **não vai para o GitHub** (está no `.gitignore`). Nele você define:

| Campo | Para quê |
|---|---|
| `nome_usuario`, `seu_email` | O Jacinto te reconhece como dono |
| `sobre_criador` | O que ele diz quando perguntam quem o criou |
| `usuarios_conhecidos` | Recepção personalizada para pessoas específicas |
| `codigo_acesso` | Pede uma senha comum no login |
| `permitir_executar_codigo` | Liga o botão "Executar código" (veja o aviso abaixo) |
| `smtp_*` | Liga a confirmação do email por código |

### Confirmação do email por código
Sem SMTP, o login só confere se o email tem formato válido e se o domínio existe. **Qualquer pessoa pode digitar o email de outra.** Para confirmar de verdade, o app envia um código de 6 dígitos:

1. Use uma conta Gmail dedicada ao app e ative a verificação em duas etapas.
2. Crie uma **senha de app** em https://myaccount.google.com/apppasswords.
3. Coloque em `config_local.json`: `smtp_usuario` (o Gmail) e `smtp_senha` (a senha de app).

Nunca coloque essa senha no código nem suba o `config_local.json`.

## Usar no celular
Com o PC e o celular no mesmo Wi-Fi, abra `http://IP-DO-PC:8501` (veja o IP com `ipconfig` no Windows). Na primeira vez, libere o Python no Firewall em "redes privadas".

## ⚠️ Segurança
- Foi feito para uso **pessoal ou em rede doméstica**. Não abra a porta do roteador para a internet.
- O botão **Executar código** roda código gerado pela IA no seu computador, com bloqueios básicos que **não são à prova de falhas**. Fica desligado por padrão. Ligue só se só você usa o app.
- As conversas são salvas em texto simples na pasta `dados_jacinto/`.

## Dicas para PC fraco
- Prefira modelos de 1B a 1,5B (`llama3.2:1b`, `qwen2.5-coder:1.5b`, `gemma3:1b`).
- Evite modelos com modo de "raciocínio" e modelos de 3B ou mais sem placa de vídeo.
- Em ⚙️ Ajustes, use o **Modo leve** e ajuste as threads da CPU.

## Licença
Escolha uma licença para o repositório (por exemplo MIT) antes de divulgar.
