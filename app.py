import streamlit as st
import pydeck as pdk
import geopandas as gpd
import zipfile
import os

st.set_page_config(page_title="Acessibilidade RJ", layout="wide")
st.title("🗺️ Mapa Interativo de Acessibilidade - Rio de Janeiro")

@st.cache_data
def load_data():
    # 1. Extrair o ficheiro ZIP
    if not os.path.exists("hexgrid_with_accessibility.geojson"):
        with zipfile.ZipFile("hexgrid_with_accessibility.zip", 'r') as zip_ref:
            zip_ref.extractall(".")
            
    # 2. Ler os dados
    gdf = gpd.read_file("hexgrid_with_accessibility.geojson")
    
    # 3. O PULO DO GATO: Forçar a conversão para Latitude/Longitude (EPSG:4326)
    if gdf.crs != "EPSG:4326":
        gdf = gdf.to_crs(epsg=4326)
        
    return gdf

dados = load_data()

camada_hex = pdk.Layer(
    "GeoJsonLayer",
    dados,
    opacity=0.8,
    stroked=False, 
    filled=True,
    extruded=True, 
    wireframe=True,
    get_elevation="properties.jobs_vinculos_30min_transit_p50 * 10",
    get_fill_color="[255, properties.jobs_vinculos_30min_transit_p50 * 2, 100]",
    pickable=True 
)

visao_inicial = pdk.ViewState(
    latitude=-22.9068,
    longitude=-43.1729,
    zoom=10,
    pitch=45, 
    bearing=0
)

# 4. Trocámos o map_style para "dark" (estilo CartoDB que é 100% gratuito e não exige chave)
st.pydeck_chart(pdk.Deck(
    map_style="dark", 
    initial_view_state=visao_inicial,
    layers=[camada_hex],
    tooltip={"text": "Empregos acessíveis (30min): {jobs_vinculos_30min_transit_p50}"}
))
