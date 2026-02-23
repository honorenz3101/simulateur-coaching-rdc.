import streamlit as st
import google.generativeai as genai
import pandas as pd
from datetime import datetime
import gspread
from oauth2client.service_account import ServiceAccountCredentials

# Configuration de la connexion
scope = ["https://www.googleapis.com/auth/drive", "https://www.googleapis.com/auth/drive.file"]

# On récupère les accès depuis les "Secrets" de Streamlit
creds_dict = st.secrets["gcp_service_account"]
creds = ServiceAccountCredentials.from_json_keyfile_dict(creds_dict, scope)
client = gspread.authorize(creds)

def sauvegarder_sur_drive(email_etudiant, contenu):
    # Cette fonction va créer un fichier texte directement dans votre dossier partagé
    # (Il faudra ajouter l'ID de votre dossier Drive ici)
    pass

# --- CONFIGURATION ---
genai.configure(api_key="VOTRE_CLE_API_GEMINI")
model = genai.GenerativeModel('gemini-1.5-pro')

st.set_page_config(page_title="Simulateur de Coaching - Dr Nzambu", layout="centered")

# --- FONCTIONS DE GESTION ---
def verifier_email(email, liste_autorisee):
    return email in liste_autorisee

def sauvegarder_conversation(email, client, historique):
    # Logique pour créer un fichier texte ou envoyer vers Google Drive
    nom_fichier = f"Session_{email}_{datetime.now().strftime('%Y%m%d_%H%M')}.txt"
    contenu = f"Étudiant: {email}\nClient: {client}\n\n{historique}"
    # Ici, on simule l'export (peut être lié à l'API Google Drive)
    st.info(f"La conversation a été archivée sous : {nom_fichier}")

# --- INTERFACE ENSEIGNANT (ADMIN) ---
if st.sidebar.checkbox("Accès Enseignant (Admin)"):
    mdp = st.sidebar.text_input("Code d'accès", type="password")
    if mdp == "VOTRE_CODE_SECRET":
        st.header("🛠 Tableau de Bord Enseignant")
        
        # Gestion des étudiants
        uploaded_file = st.file_uploader("Mettre à jour la liste des emails (CSV)", type=['csv'])
        if uploaded_file:
            df_emails = pd.read_csv(uploaded_file)
            st.success("Liste mise à jour !")
        
        # Support de cours
        support_cours = st.file_uploader("Télécharger le support de cours (PDF/DOCX)", type=['pdf', 'docx'])
        if support_cours:
            st.success("Base de connaissances actualisée.")
    else:
        st.error("Accès refusé.")

# --- INTERFACE ÉTUDIANT ---
else:
    # --- EN-TÊTE OFFICIEL UBM ---
    col1, col2 = st.columns([1, 4])

    with col1:
    # Remplacez l'URL ci-dessous par le lien direct vers l'image de votre logo
    st.image("logo_ubm.png", width=120)

    with col2:
    st.markdown("""
    ### RÉPUBLIQUE DÉMOCRATIQUE DU CONGO
    **UNIVERSITÉ BERNADETTE MULEKA - UBM** *Département du Coaching Positif*
    """)

st.divider() # Ajoute une ligne de séparation élégante
st.title("🎓 Simulateur de Conversations de Coaching")
    
    if 'auth' not in st.session_state:
        st.session_state.auth = False

    if not st.session_state.auth:
        email_input = st.text_input("Entrez votre adresse email académique :")
        if st.button("Se connecter"):
            # Simulation d'une liste (à remplacer par votre fichier CSV)
            liste_valide = ["etudiant1@ubm.cd", "nzambu.honore@example.com"] 
            if verifier_email(email_input, liste_valide):
                st.session_state.auth = True
                st.session_state.user_email = email_input
                st.rerun()
            else:
                st.error("Email non autorisé. Veuillez contacter le Dr Nzambu.")
    
    else:
        # Une fois connecté
        st.write(f"Bonjour, **{st.session_state.user_email}**.")
        st.warning("⚠️ Rappel : Ne partagez aucune information personnelle réelle durant la simulation.")
        
        client_type = st.selectbox("Choisissez votre client pour cette session :", [
            "Sélectionner...",
            "Fonctionnaire de l'État (Kinshasa) - Stress administratif",
            "Entrepreneur (Goma) - Conflit d'associés",
            "Couple de la diaspora (Belgique) - Éducation des enfants",
            "Professionnel en reconversion (Diaspora USA)",
            "Chômeur (Lubumbashi) - Perte de motivation"
        ])

        if client_type != "Sélectionner...":
            if "chat_history" not in st.session_state:
                st.session_state.chat_history = []

            # Affichage du chat
            for message in st.session_state.chat_history:
                with st.chat_message(message["role"]):
                    st.markdown(message["content"])

            if prompt := st.chat_input("Votre réponse de coach..."):
                st.session_state.chat_history.append({"role": "user", "content": prompt})
                with st.chat_message("user"):
                    st.markdown(prompt)

                # Appel à Gemini avec le contexte spécifique
                response = model.generate_content(f"Agis comme un client de type {client_type} en RDC. Réponds brièvement à : {prompt}")
                
                with st.chat_message("assistant"):
                    st.markdown(response.text)
                st.session_state.chat_history.append({"role": "assistant", "content": response.text})

            if st.button("Terminer la session"):
                sauvegarder_conversation(st.session_state.user_email, client_type, st.session_state.chat_history)
                st.session_state.chat_history = []
                st.write("Session terminée. Merci !")
