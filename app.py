import streamlit as st
import pydeck as pdk
import geopandas as gpd
import zipfile
import os
import json
import numpy as np

# 1. CONFIGURAÇÃO DA PÁGINA
st.set_page_config(page_title="DataViz Acessibilidade RJ", layout="wide")

@st.cache_data
def load_data():
    if not os.path.exists("hexgrid_with_accessibility.geojson"):
        with zipfile.ZipFile("hexgrid_with_accessibility.zip", 'r') as zip_ref:
            zip_ref.extractall(".")
            
    gdf = gpd.read_file("hexgrid_with_accessibility.geojson")
    if gdf.crs != "EPSG:4326":
        gdf = gdf.to_crs(epsg=4326)
    return gdf

gdf = load_data()

# ==========================================
# BARRA LATERAL (DASHBOARD CONTROLS)
# ==========================================
st.sidebar.title("🎮 Painel de Visualização")

colunas_acessibilidade = [col for col in gdf.columns if 'transit' in col or 'walk' in col]
indicador = st.sidebar.selectbox("Selecione o Indicador:", colunas_acessibilidade)

# Slider para o usuário controlar a altura máxima (evita o efeito "grotesco")
altura_max = st.sidebar.slider("Visualização vertical:", 500, 5000, 2000)

# ==========================================
# LÓGICA DE CORES PROFISSIONAL (MAGMA)
# ==========================================
gdf['valor_mapa'] = gdf[indicador].fillna(0)
max_val = gdf['valor_mapa'].max()

def get_color_magma(val):
    if max_val <= 0: return [40, 40, 40, 50]
    # Normalizamos o valor de 0 a 1
    frac = val / max_val
    
    # Rustic Charm Pallete
    if frac == 0:
        return [255, 252, 242]      # Rustic Charm Pallete
    elif frac < 0.25:
        return [204, 197, 185]      # Rustic Charm Pallete
    elif frac < 0.5:
        return [64, 61, 57]    # Rustic Charm Pallete
    elif frac < 0.75:
        return [37, 36, 34]   # Rustic Charm Pallete
    else:
        return [235, 94, 40]   # Rustic Charm Pallete

gdf['cor'] = gdf['valor_mapa'].apply(get_color_magma)
gdf['altura'] = (gdf['valor_mapa'] / max_val) * altura_max if max_val > 0 else 0

dados_json = json.loads(gdf.to_json())

# ==========================================
# DASHBOARD: MÉTRICAS E MAPA
# ==========================================
st.title("🏙️ Mapa Interativo de Acessibilidade - Rio de Janeiro")
st.subheader(f"Analisando: {indicador.replace('_', ' ').title()}")

m1, m2, m3 = st.columns(3)
m1.metric("Total de Células", f"{len(gdf):,}")
m2.metric("Valor Máximo", f"{int(max_val):,}")
m3.metric("Média Geral", f"{int(gdf['valor_mapa'].mean()):,}")

# Camada do Mapa
layer = pdk.Layer(
    "GeoJsonLayer",
    data=dados_json,
    opacity=0.9,
    stroked=True,
    get_line_color=[255, 255, 255, 30], # Linhas finas brancas entre hexágonos
    line_width_min_pixels=0.5,
    filled=True,
    extruded=True,
    get_elevation="properties.altura",
    get_fill_color="properties.cor",
    pickable=True,
    auto_highlight=True
)

view = pdk.ViewState(latitude=-22.9068, longitude=-43.1729, zoom=10, pitch=45)

st.pydeck_chart(pdk.Deck(
    map_style="mapbox://styles/mapbox/navigation-guidance-night-v4", # Estilo focado em dados
    initial_view_state=view,
    layers=[layer],
    tooltip={"text": "Oportunidades: {valor_mapa}"}
))
