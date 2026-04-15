import streamlit as st
import pydeck as pdk
import geopandas as gpd
import zipfile
import os
import json

# 1. CONFIGURAÇÃO DA PÁGINA (Layout Largo)
st.set_page_config(page_title="Dashboard de Acessibilidade RJ", layout="wide")

# ==========================================
# BARRA LATERAL (MENU DO DASHBOARD)
# ==========================================
st.sidebar.title("📊 Painel de Controlo")
st.sidebar.markdown("Explore a acessibilidade do Rio de Janeiro.")

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
# LÓGICA DO DASHBOARD E ESCALA PROPORCIONAL
# ==========================================

# Encontra todas as colunas de resultados (geralmente começam com o nome do indicador)
colunas_acessibilidade = [col for col in gdf.columns if 'transit' in col or 'walk' in col]

if len(colunas_acessibilidade) > 0:
    # O utilizador escolhe o que quer ver no mapa!
    indicador_selecionado = st.sidebar.selectbox("Selecione o Indicador:", colunas_acessibilidade)
else:
    indicador_selecionado = 'jobs_vinculos_30min_transit_p50' # fallback caso não encontre

gdf['valor_mapa'] = gdf[indicador_selecionado].fillna(0)
valor_maximo = gdf['valor_mapa'].max()

# --- A CORREÇÃO DA ALTURA GROTESCA ---
# Em vez de multiplicar por 10, fazemos uma proporção. 
# O hexágono com maior valor terá sempre a altura máxima de 3000 metros visuais.
if valor_maximo > 0:
    gdf['altura'] = (gdf['valor_mapa'] / valor_maximo) * 1000
else:
    gdf['altura'] = 0

# Calcula cores: do Amarelo (baixo) ao Laranja/Vermelho (Alto)
def calcular_cor(valor):
    if valor_maximo == 0: return [255, 255, 150]
    intensidade = int((valor / valor_maximo) * 100)
    return [255, 255 - intensidade, 50]

gdf['cor'] = gdf['valor_mapa'].apply(calcular_cor)
dados_json = json.loads(gdf.to_json())

# ==========================================
# CORPO PRINCIPAL DO DASHBOARD
# ==========================================
st.title("🗺️ Mapa Interativo de Acessibilidade - Rio de Janeiro")

# Cartões de Métricas (Métricas Rápidas)
col1, col2, col3 = st.columns(3)
col1.metric("Hexágonos Mapeados", f"{len(gdf):,}".replace(",", "."))
col2.metric("Oportunidades (Máximo)", f"{int(valor_maximo):,}".replace(",", "."))
col3.metric("Média de Acessos", f"{int(gdf['valor_mapa'].mean()):,}".replace(",", "."))

st.markdown("---") # Linha divisória

# ==========================================
# MAPA 3D
# ==========================================
camada_hex = pdk.Layer(
    "GeoJsonLayer",
    data=dados_json,
    opacity=0.8,
    stroked=False, 
    filled=True,
    extruded=True, 
    wireframe=True,
    get_elevation="properties.altura", 
    get_fill_color="properties.cor",   
    pickable=True 
)

visao_inicial = pdk.ViewState(
    latitude=-22.9068,
    longitude=-43.1729,
    zoom=10,
    pitch=25, 
    bearing=0
)

st.pydeck_chart(pdk.Deck(
    map_style="satellite", 
    initial_view_state=visao_inicial,
    layers=[camada_hex],
    tooltip={"text": f"Oportunidades nesta zona: {{valor_mapa}}"}
))
