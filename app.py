import streamlit as st
import pydeck as pdk
import geopandas as gpd
import zipfile
import os
import json # <-- Importante para o novo método à prova de falhas

st.set_page_config(page_title="Acessibilidade RJ", layout="wide")
st.title("🗺️ Mapa Interativo de Acessibilidade - Rio de Janeiro")

@st.cache_data
def load_data():
    if not os.path.exists("hexgrid_with_accessibility.geojson"):
        with zipfile.ZipFile("hexgrid_with_accessibility.zip", 'r') as zip_ref:
            zip_ref.extractall(".")
            
    gdf = gpd.read_file("hexgrid_with_accessibility.geojson")
    
    if gdf.crs != "EPSG:4326":
        gdf = gdf.to_crs(epsg=4326)
        
    # --- PREPARAÇÃO À PROVA DE FALHAS ---
    
    # 1. Garantir que não há valores vazios (NaN) que tornam o mapa invisível
    coluna_dados = 'jobs_vinculos_30min_transit_p50'
    if coluna_dados in gdf.columns:
        gdf['valor_mapa'] = gdf[coluna_dados].fillna(0)
    else:
        # Se a coluna não existir com esse nome exato, usa outra genérica para não quebrar
        gdf['valor_mapa'] = 50 

    # 2. Calcular a altura e a cor no Python (muito mais seguro)
    gdf['altura'] = gdf['valor_mapa'] * 10

    def calcular_cor(valor):
        verde = int(min(valor * 2, 255))
        return [255, verde, 100] # Gera um degrade de vermelho para amarelo
        
    gdf['cor'] = gdf['valor_mapa'].apply(calcular_cor)

    # 3. Converter o GeoDataFrame para um dicionário JSON puro (O Pydeck adora este formato)
    return json.loads(gdf.to_json())

# Carrega os dados processados
dados = load_data()

camada_hex = pdk.Layer(
    "GeoJsonLayer",
    data=dados, # Passa o dicionário puro
    opacity=0.8,
    stroked=False, 
    filled=True,
    extruded=True, 
    wireframe=True,
    get_elevation="properties.altura", # Agora puxa a altura já calculada
    get_fill_color="properties.cor",   # Agora puxa a cor já calculada
    pickable=True 
)

visao_inicial = pdk.ViewState(
    latitude=-22.9068,
    longitude=-43.1729,
    zoom=10,
    pitch=45, 
    bearing=0
)

st.pydeck_chart(pdk.Deck(
    map_style="dark", 
    initial_view_state=visao_inicial,
    layers=[camada_hex],
    tooltip={"text": "Indicador de Acessibilidade: {valor_mapa}"}
))
