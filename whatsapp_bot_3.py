import os
from dotenv import load_dotenv
#import fitz  # PyMuPDF
import sqlite3
import threading
from flask import Flask, request
from twilio.rest import Client
from twilio.twiml.messaging_response import MessagingResponse
from groq import Groq

load_dotenv()

TWILIO_SID = os.getenv("twilio_account_sid")
TWILIO_AUTH_TOKEN = os.getenv("twilio_auth_token")
TWILIO_WHATSAPP_NUMBER = os.getenv("twilio_whatsapp_number")
GROQ_API_KEY = os.getenv("model_groq_api_key")


# DIRETORIO_PDFS = "livros_financeiros"  # Nome da pasta onde os PDFs estão armazenados

MENSAGEM_BOAS_VINDAS = """🤖 Olá! Eu sou o Mezada 1.0 📊, seu assistente de planejamento financeiro.

💰 O que eu faço?
- Analiso sua situação financeira com inteligência artificial 🤖
- Dou recomendações para melhorar suas finanças 📈
- Te ajudo a tomar decisões inteligentes sobre dinheiro 💵

Digite uma mensagem contando sobre sua situação financeira e eu irei te ajudar!"""







# Configuração da API Groq para análise financeira

groq_client = Groq(api_key=GROQ_API_KEY)

app = Flask(__name__)

# Criar banco de dados para logs do WhatsApp (se não existir)
conn = sqlite3.connect("banco_de_dados.db")
cursor = conn.cursor()
cursor.execute("""
    CREATE TABLE IF NOT EXISTS logs_whatsapp (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        usuario TEXT NOT NULL,
        mensagem TEXT NOT NULL,
        resposta TEXT NOT NULL,
        data TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
""")
conn.commit()
conn.close()


# Função para salvar logs no banco de dados
def salvar_log(usuario, mensagem, resposta):
    conn = sqlite3.connect("banco_de_dados.db")
    cursor = conn.cursor()
    cursor.execute("INSERT INTO logs_whatsapp (usuario, mensagem, resposta) VALUES (?, ?, ?)",
                   (usuario, mensagem, resposta))
    conn.commit()
    conn.close()


# Função para dividir e enviar mensagens grandes via Twilio
def enviar_mensagem_whatsapp(numero, texto):
    """Divide a mensagem em partes de 1500 caracteres e envia via WhatsApp"""
    partes = [texto[i:i + 1500] for i in range(0, len(texto), 1500)]  # Divide o texto em partes

    client_twilio = Client(TWILIO_SID, TWILIO_AUTH_TOKEN)

    for i, parte in enumerate(partes):
        try:
            msg = client_twilio.messages.create(
                from_=TWILIO_WHATSAPP_NUMBER,
                to=numero,
                body=f"{parte} (Parte {i + 1}/{len(partes)})"
            )
            print(f"Mensagem parte {i + 1} enviada! SID: {msg.sid}")
        except Exception as e:
            print(f"Erro ao enviar parte {i + 1}: {e}")


# Função para gerar recomendação financeira com Groq (Llama 3)
def gerar_recomendacao(historia):
    """Gera uma recomendação financeira baseada na história do usuário"""
    prompt = f"""
    O usuário compartilhou a seguinte história financeira:
    {historia}

    Gere uma recomendação personalizada para ajudá-lo a melhorar sua vida financeira.
    """

    response = groq_client.chat.completions.create(
        model="llama-3.3-70b-versatile",
        messages=[{"role": "system", "content": prompt}]
    )

    return response.choices[0].message.content


# Função que processa e envia a resposta em segundo plano
def processar_e_enviar(numero_usuario, mensagem_usuario):
    print(">>> Thread iniciada para processar a mensagem:", mensagem_usuario)

    # Gerar recomendação financeira
    recomendacao = gerar_recomendacao(mensagem_usuario)
    print(">>> Recomendação gerada:", recomendacao)

    # Salvar log no banco de dados
    salvar_log(numero_usuario, mensagem_usuario, recomendacao)

    # Enviar a recomendação dividida em partes via WhatsApp
    enviar_mensagem_whatsapp(numero_usuario, f"📊 Análise Financeira\n\n{recomendacao}")


# Rota do webhook para processar mensagens do WhatsApp
@app.route("/webhook", methods=["POST"])
def webhook():
    """Recebe mensagens do WhatsApp e responde automaticamente"""
    data = request.form
    numero_usuario = data.get("From")  # Exemplo: "whatsapp:+5511912345678"
    mensagem_usuario = data.get("Body")

    # Conectar ao banco de dados para verificar se o usuário já interagiu antes
    conn = sqlite3.connect("banco_de_dados.db")
    cursor = conn.cursor()
    cursor.execute("SELECT COUNT(*) FROM logs_whatsapp WHERE usuario = ?", (numero_usuario,))
    ja_interagiu = cursor.fetchone()[0] > 0
    conn.close()

    # Se for a primeira interação, enviar mensagem de apresentação
    if not ja_interagiu:
        client_twilio = Client(TWILIO_SID, TWILIO_AUTH_TOKEN)
        client_twilio.messages.create(
            from_=TWILIO_WHATSAPP_NUMBER,
            to=numero_usuario,
            body=MENSAGEM_BOAS_VINDAS
        )
        print(">>> Enviando mensagem de boas-vindas para", numero_usuario)

    # Responder imediatamente para evitar timeout no Twilio
    resp = MessagingResponse()
    resp.message("✅ Recebemos sua mensagem! Estamos processando sua análise financeira. Aguarde um instante.")

    # Iniciar thread para processar a recomendação sem bloquear a resposta imediata
    if mensagem_usuario:
        thread = threading.Thread(target=processar_e_enviar, args=(numero_usuario, mensagem_usuario))
        thread.start()

    return str(resp)


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)



""" 
def extrair_texto_pdf(caminho_pdf):
    # Lê um PDF e retorna o texto extraído.
    texto_completo = ""
    try:
        with fitz.open(caminho_pdf) as pdf:
            for pagina in pdf:
                texto_completo += pagina.get_text("text") + "\n"
    except Exception as e:
        print(f"Erro ao ler o PDF: {e}")
    return texto_completo


def listar_pdfs():
    # Lista todos os arquivos PDF no diretório especificado.
    if not os.path.exists(DIRETORIO_PDFS):
        print("🚨 Diretório de PDFs não encontrado!")
        return []

    pdfs = [os.path.join(DIRETORIO_PDFS, f) for f in os.listdir(DIRETORIO_PDFS) if f.endswith(".pdf")]

    if not pdfs:
        print("🚨 Nenhum PDF encontrado no diretório!")
    else:
        print(f"📂 PDFs encontrados: {pdfs}")

    return pdfs


def buscar_insights_livros():
    # Lê todos os PDFs do diretório e retorna um resumo dos insights.
    insights = ""
    pdfs = listar_pdfs()

    if not pdfs:
        return "Nenhum livro foi encontrado no diretório."

    for pdf in pdfs:
        texto = extrair_texto_pdf(pdf)
        insights += f"\n📖 Insights do livro {os.path.basename(pdf)}:\n{texto[:1000]}...\n"

    return insights

"""
