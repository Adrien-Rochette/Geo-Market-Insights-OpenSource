import streamlit as st
import osmnx as ox
import folium
from streamlit_folium import folium_static
import pandas as pd
import ollama
import sqlite3
import os
from datetime import datetime
from shapely.ops import nearest_points

# --- CONFIGURATION ---
st.set_page_config(page_title="Geo-Market Insights | Pro", layout="wide")

# Création du dossier data s'il n'existe pas
if not os.path.exists('data'):
    os.makedirs('data')

# --- LOGIQUE DATA ENGINEER (Persistence & SQL) ---
def init_db():
    conn = sqlite3.connect('data/history.db')
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS searches 
                 (date TEXT, city TEXT, business TEXT, count INTEGER, score REAL, file_path TEXT)''')
    conn.commit()
    conn.close()

def save_to_data_lake(df, city, business):
    """Sauvegarde les données brutes pour de futures analyses ML"""
    filename = f"data/{city}_{business}_{datetime.now().strftime('%Y%m%d_%H%M')}.csv"
    df.to_csv(filename, index=False)
    return filename

def save_search(city, business, count, score, file_path):
    conn = sqlite3.connect('data/history.db')
    c = conn.cursor()
    c.execute("INSERT INTO searches VALUES (?, ?, ?, ?, ?, ?)", 
              (datetime.now().strftime("%Y-%m-%d %H:%M"), city, business, count, score, file_path))
    conn.commit()
    conn.close()

init_db()

# --- INTERFACE ---
st.title("📍 Geo-Market Insights OpenSource")
st.caption("Outil d'ingénierie décisionnelle basé sur OpenStreetMap et l'IA Locale")
st.markdown("---")

with st.sidebar:
    st.header("⚙️ Paramètres d'analyse")
    city = st.text_input("Ville cible", "Pau")
    
    business_map = {
        "🏋️ Salles de sport": {"amenity": ["gym"], "leisure": ["fitness_centre"]},
        "🍴 Restauration": {"amenity": ["restaurant", "fast_food", "cafe"]},
        "🥖 Boulangeries": {"shop": ["bakery"]},
        "💊 Santé": {"amenity": ["pharmacy", "clinic"]},
        "🚗 Bornes Électriques": {"amenity": ["charging_station"]},
        "🏫 Éducation": {"amenity": ["school", "university"]},
        "💻 Coworking": {"amenity": ["coworking_space"]}
    }
    
    business_label = st.selectbox("Secteur d'activité", list(business_map.keys()))
    radius = st.slider("Rayon d'influence (mètres)", 500, 10000, 2000)
    run_analysis = st.button("🚀 Lancer l'analyse experte")

if run_analysis:
    try:
        with st.spinner(f"Extraction des flux de données pour {city}..."):
            # 1. Extraction Multi-Tags
            tags = business_map[business_label]
            # Utilisation de features_from_address pour plus de précision sur le rayon
            geometries = ox.features_from_address(f"{city}, France", tags=tags, dist=radius)

            if geometries.empty:
                st.error("Aucune donnée trouvée. Essayez d'augmenter le rayon.")
            else:
                # 2. Data Cleaning & Projection (EPSG:3857 pour calculs en mètres)
                points = geometries.copy()
                points = points[points.geom_type.isin(['Point', 'Polygon'])]
                # Centroid avec projection correcte
                points['geometry'] = points.geometry.to_crs(epsg=3857).centroid.to_crs(epsg=4326)
                points['lon'] = points.geometry.x
                points['lat'] = points.geometry.y
                
                # Nettoyage des colonnes pour le CSV
                df_clean = pd.DataFrame(points.drop(columns='geometry'))
                file_saved = save_to_data_lake(df_clean, city, business_label)

                # 3. Calculs Statistiques (Profil Major Math)
                count = len(points)
                # Score de saturation : basé sur la densité par km²
                area_km2 = (3.14 * (radius**2)) / 1000000
                density = count / area_km2
                opportunity_score = max(0, min(100, 100 - (density * 5)))

                save_search(city, business_label, count, round(opportunity_score, 1), file_saved)

                # --- DASHBOARD ---
                tab1, tab2, tab3 = st.tabs(["🗺️ Carte Interactive", "📊 Statistiques Avancées", "🤖 Rapport IA"])

                with tab1:
                    m = folium.Map(location=[points['lat'].mean(), points['lon'].mean()], zoom_start=14)
                    for _, row in points.iterrows():
                        name = row.get('name', 'Établissement')
                        folium.Marker([row['lat'], row['lon']], 
                                     popup=f"<b>{name}</b>", 
                                     icon=folium.Icon(color='red', icon='briefcase', prefix='fa')).add_to(m)
                    folium_static(m)

                with tab2:
                    c1, c2, c3 = st.columns(3)
                    c1.metric("Concurrents", count)
                    c2.metric("Densité (u/km²)", round(density, 2))
                    c3.metric("Score Opportunité", f"{round(opportunity_score, 1)}/100")
                    
                    st.subheader("Fichiers stockés dans /data")
                    st.info(f"Données brutes sauvegardées sous : `{file_saved}`")
                    st.download_button("📥 Télécharger le dataset (CSV)", df_clean.to_csv(), "data_export.csv")

                with tab3:
                    st.subheader("Analyse Stratégique via Ollama")
                    try:
                        prompt = (f"Analyse de marché pour {business_label} à {city} (Rayon {radius}m). "
                                  f"Concurrents: {count}. Densité: {round(density, 2)} au km2. "
                                  f"Donne 3 préconisations d'implantation.")
                        response = ollama.chat(model='llama3', messages=[{'role': 'user', 'content': prompt}])
                        st.success(response['message']['content'])
                    except:
                        st.warning("⚠️ Serveur Ollama hors ligne. Lancez 'ollama serve' dans votre terminal.")

    except Exception as e:
        st.error(f"Erreur technique : {e}")

# --- HISTORIQUE DATA ENGINEER ---
st.markdown("---")
st.subheader("📊 Historique du Data Lake local")
try:
    conn = sqlite3.connect('data/history.db')
    df_hist = pd.read_sql_query("SELECT date, city, business, count, score FROM searches ORDER BY date DESC LIMIT 10", conn)
    st.table(df_hist)
    conn.close()
except:
    st.write("Le stockage local est prêt.")