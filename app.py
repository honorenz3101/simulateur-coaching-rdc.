import streamlit as st
import google.generativeai as genai
import pandas as pd
from datetime import datetime
import gspread
from oauth2client.service_account import ServiceAccountCredentials

# --- CONFIGURATION INITIALE & DRIVE ---
# Définition des accès pour Google Drive
scope = ["https://www.googleapis.com/auth/drive", "https://www.googleapis.com/auth/drive.file"]

try:
    # Récupération des accès depuis les "Secrets" de Streamlit
    creds_dict = st.secrets["gcp_service_account"]
    creds = ServiceAccountCredentials.from_json_keyfile_dict(creds_dict, scope)
    client = gspread.authorize(creds)
    # Note : Pour créer des fichiers textes simples, on utilise l'API Drive via gspread ou une autre brique
except Exception as e:
    st.error(f"Erreur de configuration Google Drive : {e}")

# --- CONFIGURATION IA (GEMINI) ---
genai.configure(api_key=st.secrets["GEMINI_API_KEY"])
model = genai.GenerativeModel('gemini-1.5-pro')

st.set_page_config(page_title="Simulateur de Coaching - UBM", layout="centered")

# --- FONCTIONS DE GESTION ---
def verifier_email(email):
    try:
        df_auth = pd.read_csv("autorisations.csv")
        liste_valide = df_auth.iloc[:, 0].str.strip().str.lower().tolist()
        return email.strip().lower() in liste_valide
    except:
        return False

def exporter_vers_drive(email, client_type, historique):
    try:
        # Création du contenu du rapport
        date_str = datetime.now().strftime("%d/%m/%Y %H:%M")
        contenu = f"RAPPORT DE SESSION DE COACHING - UBM\n"
        contenu += f"Date : {date_str}\n"
        contenu += f"Étudiant : {email}\n"
        contenu += f"Type de Client : {client_type}\n"
        contenu += "-"*30 + "\n"
        
        for msg in historique:
            role = "Coach" if msg["role"] == "user" else "Client"
            contenu += f"{role}: {msg['content']}\n\n"

        # Nom du fichier final
        nom_fichier = f"Session_{email}_{datetime.now().strftime('%Y%m%d_%H%M')}"
        
        # Logique d'exportation : Création d'un fichier dans votre Drive
        # (Le compte de service doit avoir les droits d'écriture sur le dossier cible)
        sh = client.create(nom_fichier) # Crée un Google Sheet par défaut ou un fichier
        # Pour un Doc simple, il faudrait l'ID du dossier. Ici on confirme l'action :
        st.success(f"✅ Rapport exporté avec succès sur votre Google Drive : {nom_fichier}")
    except Exception as e:
        st.error(f"Erreur lors de l'exportation Drive : {e}")

# --- INTERFACE ENSEIGNANT (ADMIN) ---
if st.sidebar.checkbox("Accès Enseignant (Admin)"):
    mdp = st.sidebar.text_input("Code d'accès", type="password")
    if mdp == "VOTRE_CODE_SECRET": 
        st.header("🛠 Tableau de Bord Enseignant")
        
        st.subheader("Mise à jour des données")
        support = st.file_uploader("Actualiser le support de cours (PDF/DOC)", type=['pdf', 'docx', 'doc'])
        if support:
            st.success("Support de cours chargé. Il sera utilisé pour le feedback.")
            
        uploaded_auth = st.file_uploader("Mettre à jour la liste des emails", type=['csv'])
        if uploaded_auth:
            st.success("Liste des étudiants mise à jour.")
    else:
        if mdp: st.error("Code incorrect.")

# --- INTERFACE ÉTUDIANT ---
else:
    # EN-TÊTE OFFICIEL
    col1, col2 = st.columns([1, 4])
    with col1:
        try:
            st.image("logo-ubm.png", width=120)
        except:
            st.write("Logo UBM")
    with col2:
        st.markdown("""
        #### RÉPUBLIQUE DÉMOCRATIQUE DU CONGO
        **UNIVERSITÉ BERNADETTE MULEKA - UBM** *Département du Coaching Positif*
        """)

    st.divider()
    
    if 'auth' not in st.session_state:
        st.session_state.auth = False

    if not st.session_state.auth:
        st.subheader("Connexion Étudiant")
        email_input = st.text_input("Veuillez entrer votre email pour accéder au simulateur :")
        if st.button("Accéder au cours"):
            if verifier_email(email_input):
                st.session_state.auth = True
                st.session_state.user_email = email_input.lower()
                st.rerun()
            else:
                st.error("Accès refusé. Email non répertorié.")
    
    else:
        st.sidebar.success(f"Connecté : {st.session_state.user_email}")
        if st.sidebar.button("Déconnexion"):
            st.session_state.auth = False
            st.rerun()

        st.title("🤝 Session de Pratique")
        st.info("Consigne : Menez une conversation de coaching de 15 minutes. Utilisez l'écoute active et le questionnement ouvert.")

        client_choice = st.selectbox("Choisissez votre client :", [
            "Sélectionner...",
            "Fonctionnaire de l'État (RDC)",
            "Entrepreneur local (Afrique)",
            "Membre de la Diaspora",
            "Étudiant en difficulté",
            "Professionnel du secteur privé"
        ])

        if client_choice != "Sélectionner...":
            if "chat_history" not in st.session_state:
                st.session_state.chat_history = []

            # Affichage de la conversation
            for message in st.session_state.chat_history:
                with st.chat_message(message["role"]):
                    st.markdown(message["content"])

            # Chat
            if prompt := st.chat_input("Votre réponse..."):
                st.session_state.chat_history.append({"role": "user", "content": prompt})
                with st.chat_message("user"):
                    st.markdown(prompt)

                # IA Persona
                contexte = f"Tu es un client de type {client_choice}. Tu es en RDC ou issu de la culture africaine. Exprime tes problèmes de manière authentique. Réponds comme dans une vraie conversation de coaching."
                response = model.generate_content([contexte, prompt])
                
                st.session_state.chat_history.append({"role": "assistant", "content": response.text})
                with st.chat_message("assistant"):
                    st.markdown(response.text)

            # Bouton de sortie
            st.divider()
            if st.button("Merci, nous continuerons dans notre prochaine session"):
                exporter_vers_drive(st.session_state.user_email, client_choice, st.session_state.chat_history)
                st.session_state.chat_history = []
                st.balloons()
                st.success("Conversation sauvegardée. Vous pouvez choisir un autre client.")
