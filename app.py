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
    except Exception:
        return None

# --- CONFIGURATION IA (FORCE LE MODÈLE STABLE) ---
try:
    genai.configure(api_key=st.secrets["GEMINI_API_KEY"])
    # Utilisation de la version 'latest' qui est la plus compatible
    model = genai.GenerativeModel('gemini-1.5-flash-latest')
except Exception as e:
    st.error(f"Erreur configuration API : {str(e)}")

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
            st.success(f"✅ Rapport exporté sur Google Drive")
        except Exception as e:
            st.error(f"Échec exportation : {e}")

# --- 3. INTERFACE ENSEIGNANT ---
if st.sidebar.checkbox("Accès Enseignant (Admin)"):
    mdp = st.sidebar.text_input("Code d'accès", type="password")
    if mdp == "VOTRE_CODE_SECRET": 
        st.header("🛠 Espace Administration")
        st.write("Diagnostic des modèles disponibles...")
        try:
            models = [m.name for m in genai.list_models() if 'generateContent' in m.supported_generation_methods]
            st.write(models)
        except Exception as e:
            st.write(f"Erreur diagnostic : {e}")
    else:
        if mdp: st.error("Code erroné")

# --- 4. INTERFACE ÉTUDIANT ---
else:
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
            if "chat_history" not in st.session_state:
                st.session_state.chat_history = []
            
            # --- INITIALISATION ---
            if len(st.session_state.chat_history) == 0:
                with st.spinner("Le client entre..."):
                    try:
                        # Appel simplifié sans paramètres complexes
                        response = model.generate_content(f"Tu es un client de coaching : {client_choice}. Présente ton problème brièvement en une phrase.")
                        st.session_state.chat_history.append({"role": "assistant", "content": response.text})
                    except Exception as e:
                        st.error(f"Erreur technique (IA) : {str(e)}")

            for message in st.session_state.chat_history:
                with st.chat_message(message["role"]):
                    st.markdown(message["content"])

            if prompt := st.chat_input("Répondez au client..."):
                st.session_state.chat_history.append({"role": "user", "content": prompt})
                with st.chat_message("user"):
                    st.markdown(prompt)

                with st.chat_message("assistant"):
                    try:
                        # Utilisation de l'historique simplifié
                        full_prompt = f"Tu es le client {client_choice}. Le coach dit : '{prompt}'. Réponds brièvement."
                        response = model.generate_content(full_prompt)
                        st.session_state.chat_history.append({"role": "assistant", "content": response.text})
                        st.markdown(response.text)
                    except Exception as e:
                        st.error(f"Erreur de réponse : {str(e)}")

            st.divider()
            if st.button("Terminer la session"):
                exporter_vers_drive(st.session_state.user_email, client_choice, st.session_state.chat_history)
                del st.session_state.chat_history
                st.rerun()
