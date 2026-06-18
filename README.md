# 🎮 Steam Market Business Intelligence — Pipeline Agent IA & MCP

Projet réalisé par **Emeline GEHANNO** dans le cadre du cours *8INF896 - Séminaire thématique en Intelligence Artificielle* (Été 2026) à l'**Université du Québec à Chicoutimi (UQAC)**.

L'objectif de ce projet est de concevoir un pipeline de Business Intelligence *end-to-end* capable de répondre à des questions métier stratégiques sur l'industrie du jeu vidéo. La solution s'appuie sur une architecture multi-serveurs **MCP (Model Context Protocol)**, un agent décisionnel **ReAct (LangGraph)**, et une interface utilisateur analytique interactive développée avec **Streamlit** et **Plotly**.

---

## Architecture Générale du Système

Le projet interconnecte des bases de données relationnelles locales, des API Web en temps réel, un serveur d'inférence LLM local et une interface web réactive :

         ┌────────────────────────┐         ┌────────────────────────┐
         │ Base CSV (Top ~100)    │         │ API Web Live Steam     │
         └───────────┬────────────┘         └───────────┬────────────┘
                     │ (DuckDB SQL)                     │ (Requêtes HTTP)
                     ▼                                  ▼
         ┌───────────────────────────────────────────────────────────┐
         │             Serveur MCP (mcp_steam_server.py)             │
         └───────────────────────────┬───────────────────────────────┘
                                     │ (Transport stdio / JSON-RPC)
                                     ▼
         ┌───────────────────────────────────────────────────────────┐
         │             Agent Intelligent ReAct (LangGraph)           │
         │           Modèle : Llama 3.2 (Ollama Local)               │
         └───────────────────────────┬───────────────────────────────┘
                                     │
                                     ▼
         ┌───────────────────────────────────────────────────────────┐
         │          Interface Utilisateur Finale (app.py)            │
         │        Dashboard Multi-Charts Plotly + Chat BI            │
         └───────────────────────────────────────────────────────────┘


1. **Données et Stockage :** Un script d'extraction de masse télécharge initialement le Top 100 des jeux les plus joués de Steam pour concevoir `steam_games_clean.csv`.
2. **Serveur MCP (`mcp_steam_server.py`) :** Expose dynamiquement des outils à l'agent. Il utilise **DuckDB** pour exécuter des analyses SQL complexes sur la base locale et effectue des appels vers l'API Steam Charts/Store pour choper le nombre de joueurs en direct.
3. **Cache Adaptatif :** Si l'utilisateur pose une question sur un jeu absent du dataset local, le serveur MCP interroge automatiquement les API de Steam, extrait ses métadonnées, et met à jour dynamiquement le fichier CSV.
4. **Agent Cognitif :** Un agent ReAct compilé sous **LangGraph** orchestre la réflexion et sélectionne les outils en fonction du contexte.
5. **Interface Streamlit (`app.py`) :** Présente un tableau de bord analytique Plotly synchronisé. Une couche NLP supplémentaire intercepte les requêtes du chat pour ajuster automatiquement les filtres de la barre latérale en temps réel.

---

## Questions Métier Résolues

Le tableau de bord Plotly s'articule autour de 5 problématiques BI concrètes :

* **Q1. Parts de Marché :** Quels sont les genres dominants sur Steam en volume de jeux ? (*Diagramme Circulaire*)
* **Q2. Modèle Économique :** La gratuité (*Free-to-Play*) apporte-t-elle un meilleur taux de satisfaction qu'un jeu payant ? (*Box Plot d'approbation*)
* **Q3. Analyse Temporelle :** Comment a évolué le prix moyen des jeux lancés sur Steam au fil des années ? (*Courbe chronologique*)
* **Q4. Monopoles & Succès :** Quels sont les 5 éditeurs qui captent le plus grand volume d'évaluations positives ? (*Bar Chart horizontal*)
* **Q5. Cibles OS :** Est-ce que le fait de rendre un jeu compatible Mac augmente sa portée globale en volume d'avis ? (*Bar Chart groupé*)

---

## Installation et Démarrage

### Prérequis

* Python 3.10 ou supérieur
* Ollama installé localement avec le modèle `llama3.2` configuré

### 1. Cloner le dépôt et configurer l'environnement

```bash
# Clonage du projet
git clone [https://github.com/Emeline-sys/Steam_Business_Intelligence.git](https://github.com/Emeline-sys/Steam_Business_Intelligence.git)
cd Steam_Business_Intelligence

# Création et activation de l'environnement virtuel
python -m venv .venv
source .venv/bin/activate  # Sur Windows: .venv\Scripts\activate

# Installation des dépendances requises
pip install langchain langgraph langchain-openai langchain-mcp-adapters mcp duckdb streamlit pandas plotly requests
```

### 2. Configurer Ollama

Assure-toi que ton instance locale d'Ollama est active et héberge le bon modèle :

```bash
ollama serve
ollama run llama3.2
```

### 3. Exécution

Ouvre le notebook principal *Projet_Steam.ipynb* dans ton environnement Jupiter.
1. Spécifie ta clé API Steam dans la variable ```STEAM_API_KEY``` (Section 1).
2. Exécute le script d'extraction demasse (Section 5) pour générer le dataset initial.
3. Lance la dernière cellule pour instancier l'application Streamlit.
Pour démarrer manuellement l'interface Streamlit depuis le console :
```bash
streamlit run app.py
```
L'application s'ouvrira automatiquement à l'adresse suivante : ```http://localhost:8510```


## Technologies Mobilisées

- Moteur IA : Ollama, LangChain Core, LangGraph (Agent ReAct).
- Serveur MCP : FastMCP (Python Client/Server SDK).
- Gestion des données : DuckDB, Pandas.
- Visualisation et Interface : Streamlit, Plotly Express & Subplots.

---
