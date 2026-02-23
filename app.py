import streamlit as st
import google.generativeai as genai
import pandas as pd
from datetime import datetime
import gspread
from oauth2client.service_account import ServiceAccountCredentials

# --- 1. CONFIGURATION DRIVE & API ---
scope = ["https://www.googleapis.com/auth/drive", "https://www.googleapis.com/auth/spreadsheets"]

def initialiser_drive():
    try:
        creds_dict = st.secrets["gcp_service_account"]
        creds = ServiceAccountCredentials.from_json_keyfile_dict(creds_dict, scope)
        return gspread.authorize(creds)
    except Exception:
        return None

# --- CONFIGURATION IA ---
try:
    genai.configure(api_key=st.secrets["GEMINI_API_KEY"])
    
    modele_autorise = None
    for m in genai.list_models():
        if 'generateContent' in m.supported_generation_methods:
            modele_autorise = m.name
            if 'flash' in m.name: 
                break
                
    if modele_autorise:
        model = genai.GenerativeModel(modele_autorise)
    else:
        st.error("Aucun modèle IA autorisé trouvé.")
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
            # ⚠️ L'ID DE VOTRE FICHIER GOOGLE SHEETS CENTRAL
            ID_FICHIER_MAITRE = "1SCfmcWKY5-PUbBu3qMZ-WRakhUDr0dpTvsldZFdgHgE"
            
            # 1. On rassemble toute la conversation en un seul bloc de texte
            texte_conversation = ""
            for msg in historique:
                role = "Coach" if msg["role"] == "user" else "Client"
                texte_conversation += f"{role}: {msg['content']}\n\n"
            
            # 2. On ouvre votre fichier existant
            sh = client_drive.open_by_key(ID_FICHIER_MAITRE)
            worksheet = sh.sheet1 # Sélectionne le premier onglet du tableau
            
            # 3. On prépare la nouvelle ligne de données
            date_session = datetime.now().strftime('%Y-%m-%d %H:%M')
            nouvelle_ligne = [date_session, email, client_type, texte_conversation]
            
            # 4. On ajoute la ligne tout en bas du tableau
            worksheet.append_row(nouvelle_ligne)
            
            st.success("✅ Rapport sauvegardé avec succès dans le registre central !")
        except Exception as e:
            st.error(f"Échec de l'exportation Drive : {e}")

# --- 3. INTERFACE ENSEIGNANT ---
if st.sidebar.checkbox("Accès Enseignant (Admin)"):
    mdp = st.sidebar.text_input("Code d'accès", type="password")
    if mdp == "VOTRE_CODE_SECRET": 
        st.header("🛠 Espace Administration")
        st.success(f"Modèle IA actuellement connecté : {modele_autorise}")
        st.file_uploader("Mettre à jour la liste des étudiants (CSV)", type=['csv'])
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

        client_choice = st.selectbox("Sélectionnez un profil de client :", [
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
            
            # --- INITIALISATION : Connexion et Présentation ---
            if len(st.session_state.chat_history) == 0:
                with st.spinner("Le client s'installe dans votre bureau virtuel..."):
                    try:
                        init_prompt = f"""
                        Tu es un client de coaching avec ce profil : {client_choice}. Tu vis en RDC ou tu es issu de la diaspora africaine.
                        C'est notre toute première rencontre.
                        1. Attribue-toi un nom réaliste (ex: Monsieur, Madame, ou Mademoiselle suivi d'un nom de famille).
                        2. Salue le coach et donne un bref contexte sur ta vie ou ton travail pour créer une connexion humaine.
                        3. Termine en posant le problème qui t'amène aujourd'hui.
                        Sois naturel, chaleureux mais préoccupé par ton problème. Pas de phrases robotiques.
                        """
                        response = model.generate_content(init_prompt)
                        st.session_state.chat_history.append({"role": "assistant", "content": response.text})
                    except Exception as e:
                        st.error(f"Erreur technique (IA) : {str(e)}")

            # Affichage de l'historique de la conversation
            for message in st.session_state.chat_history:
                with st.chat_message(message["role"]):
                    st.markdown(message["content"])

            # Entrée du texte par le coach (Étudiant)
            if prompt := st.chat_input("Votre réponse de coach..."):
                st.session_state.chat_history.append({"role": "user", "content": prompt})
                with st.chat_message("user"):
                    st.markdown(prompt)

                with st.chat_message("assistant"):
                    try:
                        # Reconstitution de l'historique pour garder la mémoire du nom et de l'histoire
                        historique_texte = "\n".join([f"{'Coach' if m['role']=='user' else 'Client'}: {m['content']}" for m in st.session_state.chat_history])
                        
                        full_prompt = f"""
                        Tu es le client ({client_choice}). Reste strictement dans ton personnage (garde le même nom et la même histoire qu'au début de la conversation). 
                        Voici notre conversation en cours :
                        {historique_texte}
                        
                        Réponds de manière naturelle et concise au dernier message du Coach.
                        """
                        response = model.generate_content(full_prompt)
                        st.session_state.chat_history.append({"role": "assistant", "content": response.text})
                        st.markdown(response.text)
                    except Exception as e:
                        st.error(f"Erreur de réponse : {str(e)}")

            # --- BOUTON DE FIN DE SESSION ET SAUVEGARDE ---
            st.divider()
            if st.button("Terminer la session et sauvegarder le rapport"):
                exporter_vers_drive(st.session_state.user_email, client_choice, st.session_state.chat_history)
                # Réinitialisation de l'historique pour la prochaine session
                del st.session_state.chat_history
                st.rerun()
