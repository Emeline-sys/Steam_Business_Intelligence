from mcp.server.fastmcp import FastMCP
import duckdb
import os
import requests
import pandas as pd
from datetime import datetime

mcp = FastMCP('SteamProjectServer')
CSV_PATH = os.path.join(os.path.dirname(__file__), 'steam_games_clean.csv')

def get_conn():
    conn = duckdb.connect()
    if os.path.exists(CSV_PATH):
        conn.execute(f"CREATE TABLE IF NOT EXISTS games AS SELECT * FROM read_csv_auto('{CSV_PATH}', all_varchar=False)")
    return conn

def enrichir_csv_si_absent(nom_ou_id) -> int:
    """Recherche un jeu sur le Store Steam, récupère ses infos réelles et l'ajoute au CSV."""
    appid = None
    try:
        appid = int(nom_ou_id)
    except ValueError:
        search_url = f"https://store.steampowered.com/api/storesearch/?term={nom_ou_id}&l=french&cc=fr"
        try:
            req = requests.get(search_url, timeout=10)
            if req.status_code == 200:
                results = req.json().get('items', [])
                if results:
                    appid = results[0]['id']
        except Exception:
            return None

    if not appid:
        return None

    if os.path.exists(CSV_PATH):
        try:
            df_existing = pd.read_csv(CSV_PATH)
            if 'appid' in df_existing.columns and appid in df_existing['appid'].values:
                return appid
        except Exception:
            df_existing = pd.DataFrame()
    else:
        df_existing = pd.DataFrame()

    store_url = f"https://store.steampowered.com/api/appdetails?appids={appid}&cc=fr&l=french"
    reviews_url = f"https://store.steampowered.com/appreviews/{appid}?json=1&language=all&purchase_type=all"

    positives, negatives = 0, 0
    try:
        rev_resp = requests.get(reviews_url, timeout=10)
        if rev_resp.status_code == 200:
            query_summary = rev_resp.json().get('query_summary', {})
            # On récupère les vraies valeurs fournies par Steam !
            positives = query_summary.get('total_positive', 0)
            negatives = query_summary.get('total_negative', 0)
    except Exception as e:
        print(f"Impossible de choper les vrais ratings : {e}")

    try:
        resp = requests.get(store_url, timeout=10)
        if resp.status_code == 200 and resp.json()[str(appid)]['success']:
            info = resp.json()[str(appid)]['data']

            genres = ", ".join([g['description'] for g in info.get('genres', [])])
            platforms_list = [os_name for os_name, disp in info.get('platforms', {}).items() if disp]
            platforms = ";".join(platforms_list)

            if info.get('is_free'):
                price = 0.0
            else:
                price = info.get('price_overview', {}).get('final', 0) / 100.0

            nouvel_enregistrement = {
                'appid': int(appid),
                'name': str(info.get('name', 'Inconnu')),
                'developer': str(", ".join(info.get('developers', ['Inconnu']))),
                'publisher': str(", ".join(info.get('publishers', ['Inconnu']))),
                'genres': genres if genres else 'Indéterminé',
                'price': float(price),
                'positive_ratings': int(positives), 
                'negative_ratings': int(negatives), 
                'platforms': platforms if platforms else 'windows',
                'release_date': str(info.get('release_date', {}).get('date', datetime.today().strftime('%Y-%m-%d')))
            }

            df_new = pd.DataFrame([nouvel_enregistrement])
            if not df_existing.empty:
                df_combined = pd.concat([df_existing, df_new], ignore_index=True)
            else:
                df_combined = df_new

            df_combined.to_csv(CSV_PATH, index=False)
            return appid
    except Exception as e:
        print(f"Erreur lors de l'écriture CSV : {e}")
    return appid

@mcp.tool()
def get_live_players(nom_ou_id: str) -> str:
    """Ajoute ou synchronise un jeu dans la base locale, récupère son genre, ses détails généraux et le nombre de joueurs en direct."""
    appid = enrichir_csv_si_absent(nom_ou_id)
    if not appid:
        return f"Désolé, je n'ai pas trouvé de correspondance sur Steam pour '{nom_ou_id}'."

    url = "https://api.steampowered.com/ISteamUserStats/GetNumberOfCurrentPlayers/v1/"
    params = {"appid": appid}
    try:
        resp = requests.get(url, params=params, timeout=10)
        if resp.status_code == 200:
            data = resp.json()
            if data["response"].get("result") == 1:
                count = data["response"]["player_count"]
                return f"Il y a actuellement {count:,} joueurs en ligne sur l'AppID {appid}."
        return f"Jeu synchronisé, mais impossible de récupérer les joueurs en direct pour l'AppID {appid}."
    except Exception as e:
        return f"Erreur Live API : {str(e)}"

@mcp.tool()
def query_steam_data(sql: str) -> str:
    """Exécute une requête SQL DuckDB sur la table 'games'."""
    conn = get_conn()
    try:
        result = conn.execute(sql).fetchall()
        columns = [desc[0] for desc in conn.description]
        output = ' | '.join(columns) + '\n' + '-' * len(columns)*5 + '\n'
        for row in result:
            output += ' | '.join(str(x) for x in row) + '\n'
        return output.strip()
    except Exception as e:
        return f"Erreur SQL : {e}"
    finally:
        conn.close()

@mcp.tool()
def check_mac_impact() -> str:
    """Calcule le ratio d'évaluation positive moyen pour Mac vs Windows."""
    conn = get_conn()
    try:
        query = """
            SELECT 
                CASE WHEN platforms LIKE '%mac%' THEN 'Disponible sur Mac' ELSE 'Windows uniquement' END as support_mac,
                COUNT(*) as nb_jeux,
                ROUND(AVG(positive_ratings * 100.0 / NULLIF(positive_ratings + negative_ratings, 0)), 2) as approbation
            FROM games
            GROUP BY support_mac
        """
        res = conn.execute(query).fetchall()
        return "\n".join([f"- {row[0]} : {row[1]} jeux, {row[2]}% d'approbation" for row in res])
    finally:
        conn.close()

if __name__ == '__main__':
    mcp.run()
