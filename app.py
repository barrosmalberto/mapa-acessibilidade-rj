import streamlit as st
import pydeck as pdk
import geopandas as gpd
import zipfile
import os
import json
import numpy as np
import pandas as pd

# 1. CONFIGURAÇÃO DA PÁGINA
st.set_page_config(page_title="DataViz Acessibilidade RJ", layout="wide")

@st.cache_data
def load_data():
    if not os.path.exists("hexgrid_with_accessibility.geojson"):
        # Verifica o nome exato do seu ZIP no GitHub
        nome_zip = "hexgrid_with_accessibility.zip" 
        if os.path.exists(nome_zip):
            with zipfile.ZipFile(nome_zip, 'r') as zip_ref:
                zip_ref.extractall(".")
    
    gdf = gpd.read_file("hexgrid_with_accessibility.geojson")
    if gdf.crs != "EPSG:4326":
        gdf = gdf.to_crs(epsg=4326)
    return gdf

gdf = load_data()

# ==========================================
# BARRA LATERAL (CONTROLES)
# ==========================================
st.sidebar.title("🎮 Painel de Visualização")

colunas_acessibilidade = [col for col in gdf.columns if 'transit' in col or 'walk' in col]
indicador = st.sidebar.selectbox("Selecione o Indicador:", colunas_acessibilidade)
altura_max = st.sidebar.slider("Exagero vertical (Altura):", 500, 5000, 2000)

# ==========================================
# LÓGICA DE CORES E ALTURA
# ==========================================
gdf['valor_mapa'] = gdf[indicador].fillna(0)
max_val = gdf['valor_mapa'].max()

def get_color_rustic(val):
    if max_val <= 0: return [40, 40, 40, 50]
    frac = val / max_val
    # Sua paleta Rustic Charm corrigida (RGBA)
    if frac == 0:     return [255, 252, 190, 140]
    elif frac < 0.25: return [204, 197, 185, 180]
    elif frac < 0.5:  return [64, 61, 57, 200]
    elif frac < 0.75: return [37, 36, 34, 230]
    else:             return [235, 94, 40, 255]

gdf['cor'] = gdf['valor_mapa'].apply(get_color_rustic)
gdf['altura'] = (gdf['valor_mapa'] / max_val) * altura_max if max_val > 0 else 0

dados_json = json.loads(gdf.to_json())

# ==========================================
# CABEÇALHO E MÉTRICAS
# ==========================================
st.title("🏙️ Dashboard de Acessibilidade Urbana - RJ")
st.subheader(f"Análise: {indicador.replace('_', ' ').title()}")

m1, m2, m3 = st.columns(3)
m1.metric("Total de Células", f"{len(gdf):,}".replace(",", "."))
m2.metric("Valor Máximo", f"{int(max_val):,}".replace(",", "."))
m3.metric("Média Geral", f"{int(gdf['valor_mapa'].mean()):,}".replace(",", "."))

# ==========================================
# ORGANIZAÇÃO EM ABAS (MAPA VS ESTATÍSTICAS)
# ==========================================
aba_mapa, aba_stats = st.tabs(["🗺️ Mapa Interativo", "📈 Estatísticas Detalhadas"])

with aba_mapa:
    # Camada do Mapa
    layer = pdk.Layer(
        "GeoJsonLayer",
        data=dados_json,
        opacity=0.5,
        stroked=True,
        get_line_color=[77, 77, 77, 100], 
        line_width_min_pixels=0.5,
        filled=True,
        extruded=True,
        get_elevation="properties.altura",
        get_fill_color="properties.cor",
        pickable=True,
        auto_highlight=True
    )

    view = pdk.ViewState(latitude=-22.9068, longitude=-43.1729, zoom=10, pitch=45)

    # USANDO ESTILO "DARK" SIMPLES (Não exige Token da Mapbox)
    st.pydeck_chart(pdk.Deck(
        map_style="dark", 
        initial_view_state=view,
        layers=[layer],
        tooltip={"text": "Localidade: {hex_id}\nOportunidades: {valor_mapa}"}
    ))

with aba_stats:
    st.markdown("### Análise de Distribuição")
    
    col_graf, col_tab = st.columns([2, 1])
    
    with col_graf:
        dados_validos = gdf[gdf['valor_mapa'] > 0]['valor_mapa']
        if len(dados_validos) > 0:
            contagem, divisorias = np.histogram(dados_validos, bins=20)
            rotulos = [f"{int(divisorias[i])}-{int(divisorias[i+1])}" for i in range(len(contagem))]
            df_hist = pd.DataFrame({'Frequência': contagem}, index=rotulos)
            st.bar_chart(df_hist)
        else:
            st.info("Sem dados para exibir o gráfico.")

    with col_tab:
        st.markdown("**Top 10 Áreas**")
        # Ajuste o nome da coluna de identificação aqui se necessário
        col_id = 'nome_bairro' if 'nome_bairro' in gdf.columns else (
                 'hex_id' if 'hex_id' in gdf.columns else gdf.columns[0])
        
        top10 = gdf.nlargest(10, 'valor_mapa')[[col_id, 'valor_mapa']]
        top10.columns = ['Localidade', 'Valor']
        st.dataframe(top10, hide_index=True, use_container_width=True)
