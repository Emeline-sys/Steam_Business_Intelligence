import streamlit as st
import asyncio, os, sys, json, re, webbrowser
import pandas as pd, plotly.graph_objects as go
from plotly.subplots import make_subplots
import nest_asyncio; nest_asyncio.apply()

from langchain_core.tools import tool
os.chdir(os.path.dirname(os.path.abspath(__file__)))

from langchain_openai import ChatOpenAI
from langgraph.prebuilt import create_react_agent
from langchain_mcp_adapters.client import MultiServerMCPClient

st.set_page_config(page_title="Steam BI Intelligence", page_icon="🎮", layout="wide")
st.title("🎮 Steam Market BI Dashboard — Pipeline Agent & MCP")

llm = ChatOpenAI(model="llama3.2", base_url="http://localhost:11434/v1", api_key="ollama", temperature=0)

SYSTEM_PROMPT_STEAM = """Tu es un expert Business Intelligence de l'industrie du jeu vidéo.
Règles impératives :
1. Pour les analyses de marché globales ou requêtes SQL, utilise `query_steam_data`.
2. Pour l'activité temps réel ou ajouter un jeu absent, appelle TOUJOURS `get_live_players`.
3. Appuie-toi sur les graphiques du dashboard (Parts de marché, Free-to-play vs Payant, Évolution des prix, Top Éditeurs, Impact Mac) pour formuler des insights BI clairs et professionnels.
"""

@tool
def make_steam_dashboard(title: str = "Analyses") -> str:
    """Génère un dashboard."""
    return "✓ Affichage mis à jour."

def load_data():
    if not os.path.exists('steam_games_clean.csv'):
        return None
    df = pd.read_csv('steam_games_clean.csv')

    # Remplissage sécurisé des valeurs numériques
    df['price'] = pd.to_numeric(df['price']).fillna(0.0)
    df['positive_ratings'] = pd.to_numeric(df['positive_ratings']).fillna(0).astype(int)
    df['negative_ratings'] = pd.to_numeric(df['negative_ratings']).fillna(0).astype(int)

    df['satisfaction_rate'] = (df['positive_ratings'] / (df['positive_ratings'] + df['negative_ratings']).replace(0, 1)) * 100
    df['total_reviews'] = df['positive_ratings'] + df['negative_ratings']

    def extraire_annee(x):
        try:
            if '-' in str(x): return int(str(x)[:4])
            m = re.search(r'(\d{4})', str(x))
            return int(m.group(1)) if m else 2020
        except: return 2020

    df['release_year'] = df['release_date'].apply(extraire_annee).astype(int)
    return df

df = load_data()

# EXTRACTION DYNAMIQUE DES VALEURS POUR LES FILTRES
if df is not None:
    genres_actuels = sorted(list(set([g.strip() for sublist in df['genres'].dropna().str.split(',') for g in sublist])))
    MAX_PRICE = float(df['price'].max()) if df['price'].max() > 0 else 100.0

    # Extraction propre des listes uniques de développeurs et d'éditeurs (avec option "Tous")
    devs_uniques = ["Tous"] + sorted(list(df['developer'].dropna().unique()))
    pubs_uniques = ["Tous"] + sorted(list(df['publisher'].dropna().unique()))
    total_jeux_base = len(df)
else:
    genres_actuels, MAX_PRICE = [], 100.0
    devs_uniques, pubs_uniques = ["Tous"], ["Tous"]
    total_jeux_base = 0

# AFFICHAGE DU COMPTEUR DE JEUX EN HAUT (KPI)
st.markdown(f"""
<div style="background-color:#1b2838; padding:15px; border-radius:10px; margin-bottom:20px; border-left: 5px solid #66c0f4;">
    <h3 style="color:#ffffff; margin:0; font-family:Arial;">📊 Taille de la base de données locale</h3>
    <p style="color:#66c0f4; font-size:28px; font-weight:bold; margin:5px 0 0 0;">{total_jeux_base:,} jeux synchronisés</p>
</div>
""", unsafe_allow_html=True)

# Initialisation du session state global pour les filtres si absent
if "steam_filters" not in st.session_state:
    st.session_state["steam_filters"] = {
        "price_max": MAX_PRICE,
        "selected_genres": genres_actuels[:5] if genres_actuels else [],
        "mac_only": False,
        "min_rating": 0.0,
        "selected_developer": "Tous",
        "selected_publisher": "Tous"
    }

with st.sidebar:
    st.header("⚙️ Filtres de Recherche")
    if df is not None:
        price_max = st.slider("Prix Maximum ($)", 0.0, max(MAX_PRICE, 100.0), float(st.session_state["steam_filters"]["price_max"]))
        selected_genres = st.multiselect("Genres", options=genres_actuels, default=[g for g in st.session_state["steam_filters"]["selected_genres"] if g in genres_actuels])

        # NOUVEAUX FILTRES : Développeur et Éditeur
        selected_developer = st.selectbox("Développeur", options=devs_uniques, index=devs_uniques.index(st.session_state["steam_filters"]["selected_developer"]) if st.session_state["steam_filters"]["selected_developer"] in devs_uniques else 0)
        selected_publisher = st.selectbox("Éditeur / Publisher", options=pubs_uniques, index=pubs_uniques.index(st.session_state["steam_filters"]["selected_publisher"]) if st.session_state["steam_filters"]["selected_publisher"] in pubs_uniques else 0)

        mac_only = st.checkbox("Disponible sur Mac 🍎", value=st.session_state["steam_filters"]["mac_only"])
        min_rating = st.slider("Taux de satisfaction min (%)", 0.0, 100.0, float(st.session_state["steam_filters"]["min_rating"]))

        st.session_state["steam_filters"]["price_max"] = price_max
        st.session_state["steam_filters"]["selected_genres"] = selected_genres
        st.session_state["steam_filters"]["mac_only"] = mac_only
        st.session_state["steam_filters"]["min_rating"] = min_rating
        st.session_state["steam_filters"]["selected_developer"] = selected_developer
        st.session_state["steam_filters"]["selected_publisher"] = selected_publisher

def build_live_dashboard(filters):
    if df is None or not filters: return go.Figure()

    # Application séquentielle des filtres de la sidebar
    f_df = df[df['price'] <= filters['price_max']]
    f_df = f_df[f_df['satisfaction_rate'] >= filters['min_rating']]

    if filters['mac_only']:
        f_df = f_df[f_df['platforms'].str.contains('mac', case=False, na=False)]
    if filters['selected_genres'] and not f_df.empty:
        regex_genres = '|'.join(filters['selected_genres'])
        f_df = f_df[f_df['genres'].str.contains(regex_genres, case=False, na=False)]

    # Application des nouveaux filtres Dev et Pub
    if filters['selected_developer'] != "Tous":
        f_df = f_df[f_df['developer'] == filters['selected_developer']]
    if filters['selected_publisher'] != "Tous":
        f_df = f_df[f_df['publisher'] == filters['selected_publisher']]

    fig = make_subplots(
        rows=3, cols=2,
        specs=[[{"type": "pie"}, {"type": "box"}],
               [{"type": "scatter"}, {"type": "bar"}],
               [{"type": "bar", "colspan": 2}, None]],
        subplot_titles=(
            f"Q1. Répartition des parts de marché par Genre ({len(f_df)} filtrés)",
            "Q2. Satisfaction : Jeux Gratuits vs Payants",
            "Q3. Évolution du Prix Moyen par Année de Sortie",
            "Q4. Top 5 Éditeurs par Évaluations Positives",
            "Q5. Portée globale du marché : Compatibilité Mac vs Windows Seul"
        )
    )

    if not f_df.empty:
        genres_series = f_df['genres'].dropna().str.split(',').explode().str.strip()
        genres_counts = genres_series.value_counts()
        fig.add_trace(go.Pie(labels=genres_counts.index, values=genres_counts.values, hole=0.3), row=1, col=1)

        f_df['model_type'] = f_df['price'].apply(lambda x: 'Gratuit' if x == 0.0 else 'Payant')
        fig.add_trace(go.Box(x=f_df['model_type'], y=f_df['satisfaction_rate'], marker_color='#2ecc71', name='Satisfaction'), row=1, col=2)

        yearly_price = f_df.groupby('release_year')['price'].mean().reset_index()
        fig.add_trace(go.Scatter(x=yearly_price['release_year'], y=yearly_price['price'], mode='lines+markers', line=dict(color='#e74c3c', width=3)), row=2, col=1)

        pub_data = f_df.groupby('publisher')['positive_ratings'].sum().nlargest(5).reset_index()
        fig.add_trace(go.Bar(x=pub_data['positive_ratings'], y=pub_data['publisher'], orientation='h', marker_color='#34495e'), row=2, col=2)

        f_df['has_mac'] = f_df['platforms'].apply(lambda x: 'Compatible Mac 🍎' if 'mac' in str(x).lower() else 'Windows uniquement 🪟')
        mac_volume = f_df.groupby('has_mac')['total_reviews'].sum().reset_index()
        fig.add_trace(go.Bar(x=mac_volume['has_mac'], y=mac_volume['total_reviews'], marker_color=['#9b59b6', '#3498db']), row=3, col=1)

    fig.update_layout(height=1000, showlegend=False, template="plotly_white")
    return fig

if df is not None:
    st.plotly_chart(build_live_dashboard(st.session_state["steam_filters"]), use_container_width=True)

st.subheader("💬 Posez vos questions métier à l'assistant Business Intelligence")
if "steam_messages" not in st.session_state: st.session_state["steam_messages"] = []

for msg in st.session_state["steam_messages"]:
    with st.chat_message(msg["role"]): st.write(msg["content"])

async def run_steam_agent(question: str):
    client = MultiServerMCPClient({'steam_srv': {'command': sys.executable, 'args': [os.path.abspath('mcp_steam_server.py')], 'transport': 'stdio'}})
    mcp_tools = await client.get_tools()
    agent = create_react_agent(llm, list(mcp_tools) + [make_steam_dashboard], prompt=SYSTEM_PROMPT_STEAM)
    result = await agent.ainvoke({"messages": [("user", question)]})
    return result["messages"][-1].content

def extraire_filtres_steam(question: str) -> dict:
    prompt = (
        "Analyse la question suivante concernant le store Steam. Extrait les filtres demandés par l'utilisateur. "
        "Réponds STRICTEMENT sous forme d'un objet JSON valide, sans aucune phrase autour. "
        "Champs du JSON : "
        '{"price_max": null, "genre": null, "mac_only": false, "min_rating": null, "reset": false} '
        f"Question : {question}"
    )
    try:
        raw = llm.invoke(prompt).content.strip()
        m = re.search(r"\{.*\}", raw, re.DOTALL)
        if m: return json.loads(m.group())
    except: pass
    return {}

def appliquer_filtres_steam(nouveaux: dict):
    if not nouveaux: return
    if nouveaux.get("reset") is True:
        st.session_state["steam_filters"] = {"price_max": MAX_PRICE, "selected_genres": genres_actuels[:5] if genres_actuels else [], "mac_only": False, "min_rating": 0.0, "selected_developer": "Tous", "selected_publisher": "Tous"}
        return
    f = st.session_state["steam_filters"]
    if nouveaux.get("price_max") is not None:
        try: f["price_max"] = min(float(nouveaux["price_max"]), MAX_PRICE)
        except: pass
    if nouveaux.get("min_rating") is not None:
        try: f["min_rating"] = float(nouveaux["min_rating"])
        except: pass
    if nouveaux.get("mac_only") is not None: f["mac_only"] = bool(nouveaux["mac_only"])
    if nouveaux.get("genre") is not None:
        matches = [g for g in genres_actuels if str(nouveaux["genre"]).lower() in g.lower()]
        if matches: f["selected_genres"] = matches

question = st.chat_input("Posez votre question ici...")
if question:
    st.session_state["steam_messages"].append({"role": "user", "content": question})
    with st.chat_message("user"): st.write(question)

    with st.chat_message("assistant"):
        with st.spinner("Recherche et mise à jour de la base..."):
            answer = asyncio.run(run_steam_agent(question))
            st.write(answer)
            st.session_state["steam_messages"].append({"role": "assistant", "content": answer})
    st.rerun()
