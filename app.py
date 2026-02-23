import streamlit as st
import google.generativeai as genai
import pandas as pd
from datetime import datetime
import gspread
from oauth2client.service_account import ServiceAccountCredentials
import PyPDF2
import docx
import io

# --- 1. CONFIGURATION DRIVE & API ---
scope = [
    "https://www.googleapis.com/auth/drive", 
    "https://www.googleapis.com/auth/spreadsheets"
]

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
except Exception as e:
    st.error(f"Erreur de configuration API : {str(e)}")

st.set_page_config(page_title="Simulateur Coaching UBM", layout="centered")

# --- 2. FONCTIONS DE GESTION & PEDAGOGIE ---
def verifier_email(email):
    try:
        df_auth = pd.read_csv("autorisations.csv", sep=None, engine='python', header=None)
        liste_valide = df_auth.iloc[:, 0].astype(str).str.strip().str.lower().tolist()
        return email.strip().lower() in liste_valide
    except Exception as e:
        print(f"Erreur de lecture CSV : {e}")
        return False

def extraire_texte_fichier(fichier):
    texte = ""
    try:
        if fichier.name.endswith('.pdf'):
            lecteur = PyPDF2.PdfReader(fichier)
            for page in lecteur.pages:
                if page.extract_text():
                    texte += page.extract_text() + "\n"
        elif fichier.name.endswith('.docx'):
            doc = docx.Document(fichier)
            for para in doc.paragraphs:
                texte += para.text + "\n"
        return texte
    except Exception as e:
        return f"Erreur d'extraction : {e}"

def charger_cours():
    try:
        with open("referentiel_coaching.txt", "r", encoding="utf-8") as f:
            return f.read()
    except Exception:
        return "Le professeur n'a pas encore chargé le référentiel de cours."

def generer_feedback(historique):
    cours = charger_cours()
    texte_conversation = "\n".join([f"{'Coach' if m['role']=='user' else 'Client'}: {m['content']}" for m in historique])
    
    prompt_evaluation = f"""
    Tu es un superviseur expert en coaching positif. 
    Voici les notes de cours et les compétences attendues pour l'étudiant : 
    {cours}
    
    Voici la transcription de la séance de coaching de l'étudiant :
    {texte_conversation}
    
    Rédige un feedback constructif et bienveillant adressé directement à l'étudiant. 
    Mets en évidence 2 points forts de sa pratique et 1 ou 2 axes d'amélioration précis en te basant STRICTEMENT sur les notes de cours. Sois concis.
    """
    try:
        reponse = model.generate_content(prompt_evaluation)
        return reponse.text
    except:
        return "Le feedback IA est indisponible pour le moment."

def exporter_vers_drive_silencieux(email, client_type, historique, feedback):
    try:
        client_drive = initialiser_drive()
        if client_drive:
            ID_FICHIER_MAITRE = "1SCfmcWKY5-PUbBu3qMZ-WRakhUDr0dpTvsldZFdgHgE"
            sh = client_drive.open_by_key(ID_FICHIER_MAITRE)
            worksheet = sh.get_worksheet(0) 
            
            texte_conversation = ""
            for msg in historique:
                role = "Coach" if msg["role"] == "user" else "Client"
                texte_conversation += f"{role}: {msg['content']}\n\n"
            
            date_session = datetime.now().strftime('%Y-%m-%d %H:%M')
            nouvelle_ligne = [date_session, email, client_type, texte_conversation, feedback]
            worksheet.append_row(nouvelle_ligne)
    except Exception:
        pass # Silence total

# --- 3. INTERFACE ENSEIGNANT ---
if st.sidebar.checkbox("Accès Enseignant (Admin)"):
    mdp = st.sidebar.text_input("Code d'accès", type="password")
    if mdp == "VOTRE_CODE_SECRET": 
        st.header("🛠 Espace Administration")
        
        st.subheader("1. Gestion des accès")
        st.file_uploader("Mettre à jour la liste des étudiants (autorisations.csv)", type=['csv'])
        
        st.divider()
        
        st.subheader("2. Référentiel Pédagogique")
        st.write("Uploadez votre support de cours. L'IA lira le texte pour évaluer les étudiants.")
        fichier_cours = st.file_uploader("Support de cours (PDF ou DOCX)", type=['pdf', 'docx'])
        
        if fichier_cours is not None:
            if st.button("Mettre à jour la base de connaissances IA"):
                with st.spinner("Extraction du texte en cours..."):
                    texte_extrait = extraire_texte_fichier(fichier_cours)
                    if not texte_extrait.startswith("Erreur"):
                        with open("referentiel_coaching.txt", "w", encoding="utf-8") as f:
                            f.write(texte_extrait)
                        st.success("✅ Le support de cours a été analysé et sauvegardé avec succès ! L'IA utilisera désormais ces critères.")
                    else:
                        st.error(texte_extrait)
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
                st.session_state.session_terminee = False
                st.rerun()
            else:
                st.error("Email non autorisé.")
    
    else:
        st.sidebar.info(f"Coach : {st.session_state.user_email}")
        if st.sidebar.button("Déconnexion"):
            st.session_state.auth = False
            if 'chat_history' in st.session_state:
                del st.session_state.chat_history
            if 'client_choice' in st.session_state:
                del st.session_state.client_choice
            st.rerun()

        if not st.session_state.get('session_terminee', False):
            client_choice = st.selectbox("Sélectionnez un profil de client :", [
                "Sélectionner...",
                "1. Étudiant en fin de cycle cherchant son premier stage (Kinshasa)",
                "2. Jeune diplômé bloqué par le favoritisme à l'embauche",
                "3. Étudiante voulant lancer une start-up agricole (Kivu)",
                "4. Jeune professionnel voulant quitter le secteur informel",
                "5. Diplômé dont la formation théorique ne correspond pas au marché",
                "6. Étudiante manquant de confiance pour les entretiens",
                "7. Jeune entrepreneur découragé par les tracasseries administratives",
                "8. Professionnel junior subissant une forte pression financière familiale",
                "9. Étudiant cherchant à concilier petits boulots de survie et études",
                "10. Jeune femme confrontée aux barrières de genre dans un milieu technique"
            ])

            if client_choice != "Sélectionner...":
                if "chat_history" not in st.session_state:
                    st.session_state.chat_history = []
                
                if len(st.session_state.chat_history) == 0:
                    with st.spinner("Le client s'installe..."):
                        init_prompt = f"""
                        Tu es un client de coaching avec ce profil : {client_choice}. Tu vis en République Démocratique du Congo.
                        C'est notre toute première rencontre.
                        1. Attribue-toi un nom et prénom congolais. Tire au hasard ton origine parmi toutes les provinces. Ne choisis pas toujours la même province.
                        2. Salue le coach poliment et donne un bref contexte sur ta situation pour créer une connexion humaine.
                        3. Pose le problème qui t'amène aujourd'hui.
                        Sois naturel.
                        """
                        try:
                            response = model.generate_content(init_prompt)
                            st.session_state.chat_history.append({"role": "assistant", "content": response.text})
                        except Exception as e:
                            st.error(f"Erreur technique : {str(e)}")

                for message in st.session_state.chat_history:
                    with st.chat_message(message["role"]):
                        st.markdown(message["content"])

                if prompt := st.chat_input("Votre réponse de coach..."):
                    st.session_state.chat_history.append({"role": "user", "content": prompt})
                    with st.chat_message("user"):
                        st.markdown(prompt)

                    with st.chat_message("assistant"):
                        try:
                            historique_texte = "\n".join([f"{'Coach' if m['role']=='user' else 'Client'}: {m['content']}" for m in st.session_state.chat_history])
                            
                            full_prompt = f"""
                            Tu es le client ({client_choice}). Reste strictement dans ton personnage. 
                            Voici notre conversation :
                            {historique_texte}
                            Réponds de manière naturelle et concise au Coach.
                            """
                            response = model.generate_content(full_prompt)
                            st.session_state.chat_history.append({"role": "assistant", "content": response.text})
                            st.markdown(response.text)
                        except Exception:
                            st.error("Erreur de communication avec le client.")

                st.divider()
                if st.button("Terminer la Session"):
                    st.session_state.client_choice = client_choice
                    st.session_state.session_terminee = True
                    st.rerun()

        # --- ECRAN DE FIN DE SESSION ET FEEDBACK BLINDÉ ---
        else:
            # Récupération 100% sécurisée des variables
            profil_sauvegarde = st.session_state.get("client_choice", "Profil non spécifié")
            historique_sauvegarde = st.session_state.get("chat_history", [])
            email_sauvegarde = st.session_state.get("user_email", "Email inconnu")

            st.success("La session est terminée. Merci pour votre écoute active.")
            
            with st.spinner("Le système analyse votre pratique..."):
                feedback = generer_feedback(historique_sauvegarde)
                exporter_vers_drive_silencieux(email_sauvegarde, profil_sauvegarde, historique_sauvegarde, feedback)
            
            st.markdown("### 📋 Retour Pédagogique")
            st.info(feedback)
            
            if st.button("Retour à l'accueil"):
                del st.session_state.chat_history
                if 'client_choice' in st.session_state:
                    del st.session_state.client_choice
                st.session_state.session_terminee = False
                st.rerun()
