import anthropic
import os
import imaplib
import smtplib
import email
import requests
from email.header import decode_header
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from datetime import datetime

client = anthropic.Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"])
GMAIL = os.environ["GMAIL_ADDRESS"]
PASSWORD = os.environ["GMAIL_PASSWORD"]
TELEGRAM_TOKEN = os.environ["TELEGRAM_TOKEN"]
TELEGRAM_CHAT_ID = os.environ["TELEGRAM_CHAT_ID"]

# Outil 1 : lire les emails
def lire_emails():
    mail = imaplib.IMAP4_SSL("imap.gmail.com")
    mail.login(GMAIL, PASSWORD)
    mail.select("inbox")
    today = datetime.now().strftime("%d-%b-%Y")
    _, messages = mail.search(None, f'(SINCE "{today}")')
    emails = []
    for num in messages[0].split()[:20]:
        _, msg_data = mail.fetch(num, "(RFC822)")
        msg = email.message_from_bytes(msg_data[0][1])
        sujet = decode_header(msg["Subject"])[0][0]
        if isinstance(sujet, bytes):
            sujet = sujet.decode()
        expediteur = msg["From"]
        corps = ""
        if msg.is_multipart():
            for part in msg.walk():
                if part.get_content_type() == "text/plain":
                    corps = part.get_payload(decode=True).decode(errors="ignore")[:500]
                    break
        else:
            corps = msg.get_payload(decode=True).decode(errors="ignore")[:500]
        emails.append(f"De: {expediteur}\nSujet: {sujet}\nContenu: {corps}\n---")
    mail.close()
    mail.logout()
    if not emails:
        return "Aucun email reçu aujourd'hui."
    return "\n".join(emails)

# Outil 2 : envoyer le rapport par email
def envoyer_email(contenu):
    msg = MIMEMultipart()
    msg["From"] = GMAIL
    msg["To"] = GMAIL
    msg["Subject"] = f"📬 Rapport Email du {datetime.now().strftime('%d/%m/%Y')}"
    msg.attach(MIMEText(contenu, "plain"))
    with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
        server.login(GMAIL, PASSWORD)
        server.send_message(msg)
    return "Rapport envoyé par email ✅"

# Outil 3 : envoyer un résumé sur Telegram
def envoyer_telegram(message):
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    requests.post(url, data={"chat_id": TELEGRAM_CHAT_ID, "text": message, "parse_mode": "Markdown"})
    return "Message Telegram envoyé ✅"

# Outil 4 : sauvegarder le rapport
def sauvegarder_rapport(contenu):
    date = datetime.now().strftime("%Y-%m-%d")
    nom = f"rapport_emails_{date}.txt"
    with open(nom, "w") as f:
        f.write(contenu)
    return f"Rapport sauvegardé : {nom}"

outils = [
    {
        "name": "lire_emails",
        "description": "Lit les emails reçus aujourd'hui dans Gmail.",
        "input_schema": {"type": "object", "properties": {}}
    },
    {
        "name": "envoyer_email",
        "description": "Envoie le rapport complet par email.",
        "input_schema": {
            "type": "object",
            "properties": {
                "contenu": {"type": "string", "description": "Le rapport complet"}
            },
            "required": ["contenu"]
        }
    },
    {
        "name": "envoyer_telegram",
        "description": "Envoie un résumé court sur Telegram.",
        "input_schema": {
            "type": "object",
            "properties": {
                "message": {"type": "string", "description": "Le résumé court pour Telegram"}
            },
            "required": ["message"]
        }
    },
    {
        "name": "sauvegarder_rapport",
        "description": "Sauvegarde le rapport dans un fichier.",
        "input_schema": {
            "type": "object",
            "properties": {
                "contenu": {"type": "string", "description": "Le rapport à sauvegarder"}
            },
            "required": ["contenu"]
        }
    }
]

messages = [
    {"role": "user", "content": """Tu es mon assistant email personnel. Voici ta mission :
1. Lis mes emails du jour avec lire_emails
2. Catégorise chaque email : URGENT / ACTION REQUISE / INFO / SPAM
3. Sauvegarde le rapport détaillé avec sauvegarder_rapport
4. Envoie le rapport complet par email avec envoyer_email
5. Envoie un résumé court et clair sur Telegram avec envoyer_telegram (max 10 lignes, emojis, points clés seulement)
Commence maintenant."""}
]

print("--- Agent Email Final démarré ---\n")

while True:
    reponse = client.messages.create(
        model="claude-opus-4-5",
        max_tokens=4096,
        tools=outils,
        messages=messages
    )

    if reponse.stop_reason == "end_turn":
        print("\n✅ Agent terminé avec succès !")
        break

    if reponse.stop_reason == "tool_use":
        messages.append({"role": "assistant", "content": reponse.content})
        resultats_outils = []
        for bloc in reponse.content:
            if bloc.type == "tool_use":
                print(f"→ Claude utilise : {bloc.name}")
                if bloc.name == "lire_emails":
                    resultat = lire_emails()
                elif bloc.name == "envoyer_email":
                    resultat = envoyer_email(bloc.input["contenu"])
                elif bloc.name == "envoyer_telegram":
                    resultat = envoyer_telegram(bloc.input["message"])
                elif bloc.name == "sauvegarder_rapport":
                    resultat = sauvegarder_rapport(bloc.input["contenu"])
                print(f"  ✓ {resultat[:80]}\n")
                resultats_outils.append({
                    "type": "tool_result",
                    "tool_use_id": bloc.id,
                    "content": resultat
                })
        messages.append({"role": "user", "content": resultats_outils})
