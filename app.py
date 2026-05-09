import streamlit as st
import osmnx as ox
import folium
from streamlit_folium import folium_static
import pandas as pd
import ollama
import sqlite3
from datetime import datetime

# --- CONFIGURATION DE LA PAGE ---
st.set_page_config(page_title="Geo-Market Insights", layout="wide")

# --- DATABASE (Data Engineering) ---
def init_db():
    conn = sqlite3.connect('data/history.db')
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS searches 
                 (date TEXT, city TEXT, business TEXT, count INTEGER, score REAL)''')
    conn.commit()
    conn.close()

def save_search(city, business, count, score):
    conn = sqlite3.connect('data/history.db')
    c = conn.cursor()
    c.execute("INSERT INTO searches VALUES (?, ?, ?, ?, ?)", 
              (datetime.now().strftime("%Y-%m-%d %H:%M"), city, business, count, score))
    conn.commit()
    conn.close()

init_db()

# --- INTERFACE UTILISATEUR ---
st.title("📍 Geo-Market Insights OpenSource")
st.markdown("---")

with st.sidebar:
    st.header("Paramètres d'analyse")
    city = st.text_input("Ville à analyser", "Pau")
    # Mapping des types de commerce vers des tags OpenStreetMap plus larges
    business_map = {
        "Salles de sport": {"amenity": ["gym"], "leisure": ["fitness_centre", "sports_centre"]},
        "Restaurants": {"amenity": ["restaurant", "fast_food", "food_court"]},
        "Boulangeries": {"shop": ["bakery"]},
        "Pharmacies": {"amenity": ["pharmacy"]}
    }
    business_label = st.selectbox("Type de commerce", list(business_map.keys()))
    run_analysis = st.button("Lancer l'analyse")

if run_analysis:
    try:
        with st.spinner(f"Extraction et traitement des données pour {city}..."):
            # 1. EXTRACTION ROBUSTE (Multi-tags)
            tags = business_map[business_label]
            # On tente d'abord par nom de lieu
            try:
                geometries = ox.features_from_place(city, tags=tags)
            except:
                # Fallback sur un rayon de 5km autour de la ville si le polygone échoue
                geometries = ox.features_from_address(f"{city}, France", tags=tags, dist=5000)

            if geometries.empty:
                st.error("Aucune donnée trouvée. Essayez une autre ville ou un autre type de commerce.")
            else:
                # 2. DATA CLEANING (Conversion des surfaces en points centraux)
                points = geometries.copy()
                points['geometry'] = points.geometry.centroid
                points['lon'] = points.geometry.x
                points['lat'] = points.geometry.y
                
                count = len(points)
                
                # 3. SCORE MATHÉMATIQUE (Logique Vice-Major)
                # Exemple de scoring : Plus il y a de densité, plus le score baisse
                # On peut raffiner ce modèle plus tard
                base_score = 100
                density_penalty = count * 2.5
                opportunity_score = max(0, min(100, base_score - density_penalty))

                save_search(city, business_label, count, opportunity_score)

                # --- AFFICHAGE DES RÉSULTATS ---
                col1, col2 = st.columns([2, 1])

                with col1:
                    st.subheader(f"Carte de la concurrence ({count} points)")
                    m = folium.Map(location=[points['lat'].mean(), points['lon'].mean()], zoom_start=13)
                    for _, row in points.iterrows():
                        name = row.get('name', 'Commerce sans nom')
                        folium.Marker([row['lat'], row['lon']], popup=name, icon=folium.Icon(color='red')).add_to(m)
                    folium_static(m)

                with col2:
                    st.metric("Score d'Opportunité", f"{opportunity_score}/100")
                    st.write(f"Analyse basée sur **{count}** concurrents identifiés.")
                    
                    # 4. RAPPORT IA (Prompt Engineering)
                    st.subheader("🤖 Analyse Stratégique")
                    prompt = (f"En tant qu'expert en géomarketing, analyse l'ouverture d'un projet '{business_label}' "
                              f"à {city}. Concurrence actuelle : {count} établissements. "
                              f"Score d'opportunité : {opportunity_score}/100. "
                              f"Donne 3 conseils brefs.")
                    
                    try:
                        response = ollama.chat(model='llama3', messages=[{'role': 'user', 'content': prompt}])
                        st.info(response['message']['content'])
                    except Exception as e:
                        st.warning("IA locale (Ollama) non détectée. Assurez-vous qu'Ollama est lancé.")

    except Exception as e:
        st.error(f"Une erreur est survenue : {e}")

# --- HISTORIQUE (Visualisation Data) ---
st.markdown("---")
st.subheader("Historique des analyses récentes")
try:
    conn = sqlite3.connect('data/history.db')
    df_hist = pd.read_sql_query("SELECT * FROM searches ORDER BY date DESC LIMIT 5", conn)
    st.dataframe(df_hist, use_container_width=True)
    conn.close()
except:
    st.write("L'historique s'affichera après votre première analyse.")