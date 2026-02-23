import streamlit as st
import google.generativeai as genai
import pandas as pd
from datetime import datetime
import gspread
from oauth2client.service_account import ServiceAccountCredentials

# --- 1. CONFIGURATION DRIVE & API ---
scope = ["https://www.googleapis.com/auth/drive", "https://www.googleapis.com/auth/drive.file"]

def initialiser_drive():
    try:
        creds_dict = st.secrets["gcp_service_account"]
        creds = ServiceAccountCredentials.from_json_keyfile_dict(creds_dict, scope)
        return gspread.authorize(creds)
    except Exception as e:
        return None

# Initialisation de l'IA Gemini
try:
    genai.configure(api_key=st.secrets["GEMINI_API_KEY"])
    model = genai.GenerativeModel('gemini-1.5-pro')
except Exception as e:
    st.error("Erreur de configuration de la clé API Gemini. Vérifiez vos Secrets Streamlit.")

st.set_page_config(page_title="Simulateur Coaching UBM", layout="centered")

# --- 2. FONCTIONS DE GESTION ---
def verifier_email(email):
    try:
        df_auth = pd.read_csv("autorisations.csv")
        liste_valide = df_auth.iloc[:, 0].str.strip().str.lower().tolist()
        return email.strip().lower() in liste_valide
    except:
        return False

def exporter_vers_drive(email, client_type, historique):
    client_drive = initialiser_drive()
    if client_drive:
        try:
            nom_fichier = f"Session_{email}_{datetime.now().strftime('%Y%m%d_%H%M')}"
            client_drive.create(nom_fichier)
            st.success(f"✅ Rapport exporté sur Google Drive : {nom_fichier}")
        except Exception as e:
            st.error(f"Échec de l'exportation Drive : {e}")

# --- 3. INTERFACE ENSEIGNANT ---
if st.sidebar.checkbox("Accès Enseignant (Admin)"):
    mdp = st.sidebar.text_input("Code d'accès", type="password")
    if mdp == "VOTRE_CODE_SECRET": 
        st.header("🛠 Espace Administration")
        st.file_uploader("Mettre à jour la liste des étudiants (CSV)", type=['csv'])
    else:
        if mdp: st.error("Code erroné")

# --- 4. INTERFACE ÉTUDIANT ---
else:
    # En-tête officiel UBM
    col1, col2 = st.columns([1, 4])
    with col1:
        try:
            st.image("logo-ubm.png", width=120)
        except:
            st.write("LOGO UBM")
    with col2:
        st.markdown("#### RÉPUBLIQUE DÉMOCRATIQUE DU CONGO\n**UNIVERSITÉ BERNADETTE MULEKA - UBM**\n*Département du Coaching Positif*")

    st.divider()

    if 'auth' not in st.session_state:
        st.session_state.auth = False

    if not st.session_state.auth:
        st.subheader("Authentification Étudiant")
        email_input = st.text_input("Email académique :")
        if st.button("Se connecter"):
            if verifier_email(email_input):
                st.session_state.auth = True
                st.session_state.user_email = email_input.lower()
                st.rerun()
            else:
                st.error("Email non autorisé.")
    
    else:
        st.sidebar.info(f"Coach : {st.session_state.user_email}")
        if st.sidebar.button("Déconnexion"):
            st.session_state.auth = False
            st.rerun()

        client_choice = st.selectbox("Sélectionnez un client :", [
            "Sélectionner...",
            "Fonctionnaire de l'État (Kinshasa)",
            "Entrepreneur local (Lubumbashi)",
            "Couple de la diaspora (Bruxelles)",
            "Étudiant en recherche de stage",
            "Professionnel en burnout"
        ])

        if client_choice != "Sélectionner...":
            # Initialisation de l'historique pour ce client précis
            if "chat_history" not in st.session_state:
                st.session_state.chat_history = []
            
            # --- ACTION : Le client parle en premier ---
            if len(st.session_state.chat_history) == 0:
                with st.spinner("Le client entre et s'installe..."):
                    init_prompt = f"Tu es un client de coaching : {client_choice}. Tu es en RDC ou issu de cette culture. Salue ton coach et présente brièvement ton problème pour lancer la séance. Sois court et authentique."
                    try:
                        # On utilise directement generate_content avec une chaîne simple pour l'init
                        response = model.generate_content(init_prompt)
                        st.session_state.chat_history.append({"role": "assistant", "content": response.text})
                    except Exception as e:
                        st.error(f"Erreur d'initialisation : {str(e)}")

            # Affichage des messages
            for message in st.session_state.chat_history:
                with st.chat_message(message["role"]):
                    st.markdown(message["content"])

            # Entrée du texte par le coach
            if prompt := st.chat_input("Répondez au client..."):
                st.session_state.chat_history.append({"role": "user", "content": prompt})
                with st.chat_message("user"):
                    st.markdown(prompt)

                with st.chat_message("assistant"):
                    with st.spinner("Le client répond..."):
                        try:
                            # Construction du contexte pour la réponse
                            instruction = f"Tu es le client {client_choice}. Réponds naturellement au coach."
                            # On envoie l'instruction + le dernier message pour plus de fluidité
                            response = model.generate_content([instruction, prompt])
                            
                            st.session_state.chat_history.append({"role": "assistant", "content": response.text})
                            st.markdown(response.text)
                        except Exception as e:
                            st.error(f"Erreur de réponse : {str(e)}")

            # Fin de séance
            st.divider()
            if st.button("Terminer la session (Sauvegarder et quitter)"):
                exporter_vers_drive(st.session_state.user_email, client_choice, st.session_state.chat_history)
                # On vide l'historique pour permettre de changer de client
                del st.session_state.chat_history
                st.rerun()
