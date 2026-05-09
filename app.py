import streamlit as st
import osmnx as ox
import folium
from streamlit_folium import folium_static
import pandas as pd
import ollama

# Configuration de la page
st.set_page_config(page_title="Geo-Market Insights", layout="wide")

st.title("📍 Geo-Market Insights OpenSource")
st.markdown("---")

# Sidebar pour les paramètres (User Experience)
with st.sidebar:
    st.header("Paramètres d'analyse")
    city = st.text_input("Ville à analyser", "Bordeaux")
    business_type = st.selectbox("Type de commerce", ["restaurant", "bakery", "gym", "pharmacy"])
    radius = st.slider("Rayon d'analyse (mètres)", 500, 5000, 1500)
    run_analysis = st.button("Lancer l'analyse")

if run_analysis:
    with st.spinner(f"Extraction des données pour {city}..."):
        try:
            # 1. Extraction via OpenStreetMap (OSMnx)
            # Utilise tes compétences en traitement de flux de données [cite: 28]
            geometries = ox.features_from_place(city, tags={"amenity": business_type})
            
            # Nettoyage rapide (Data Cleaning)
            points = geometries[geometries.geom_type == 'Point'].copy()
            points['lon'] = points.geometry.x
            points['lat'] = points.geometry.y
            
            # 2. Affichage de la Carte Interactive
            st.subheader(f"Carte de la concurrence : {business_type} à {city}")
            m = folium.Map(location=[points['lat'].mean(), points['lon'].mean()], zoom_start=14)
            
            for _, row in points.iterrows():
                folium.Marker(
                    location=[row['lat'], row['lon']],
                    popup=row.get('name', 'Commerce sans nom'),
                    icon=folium.Icon(color="red", icon="info-sign")
                ).add_to(m)
            
            folium_static(m)

            # 3. Statistiques et IA (Ollama)
            st.markdown("---")
            col1, col2 = st.columns(2)
            
            with col1:
                st.metric("Nombre de concurrents trouvés", len(points))
                st.dataframe(points[['name', 'addr:street']].dropna().head(10))

            with col2:
                st.subheader("🤖 Analyse Stratégique (IA Locale)")
                prompt = f"En tant qu'expert en géomarketing, analyse cette situation : {len(points)} {business_type} identifiés à {city}. Est-ce une zone saturée ou une opportunité ? Réponds en 3 points courts."
                
                # Appel à ton modèle local Ollama
                response = ollama.chat(model='llama3', messages=[{'role': 'user', 'content': prompt}])
                st.write(response['message']['content'])

        except Exception as e:
            st.error(f"Erreur lors de la récupération des données : {e}")