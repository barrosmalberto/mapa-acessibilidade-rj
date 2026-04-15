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
        return [255, 252, 190]      # Rustic Charm Pallete
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
# SECÇÃO DE ESTATÍSTICAS (NOVO)
# ==========================================
st.markdown("---")
st.subheader("📈 Análise Estatística Detalhada")

# Criar duas colunas lado a lado para os gráficos
col_grafico, col_tabela = st.columns(2)

with col_grafico:
    st.markdown("**Distribuição da Acessibilidade**")
    st.caption("Quantos hexágonos possuem X oportunidades?")
    
    # Removemos os zeros para não distorcer o gráfico (áreas vazias)
    dados_validos = gdf[gdf['valor_mapa'] > 0]['valor_mapa']
    
    if len(dados_validos) > 0:
        # Criamos um histograma rápido usando numpy e pandas
        contagem, divisorias = np.histogram(dados_validos, bins=20)
        # Formata os nomes das barras para ficarem legíveis
        rotulos = [f"{int(divisorias[i])} a {int(divisorias[i+1])}" for i in range(len(contagem))]
        
        import pandas as pd
        df_hist = pd.DataFrame({'Frequência (Nº de Áreas)': contagem}, index=rotulos)
        
        # O Streamlit desenha o gráfico de barras automaticamente!
        st.bar_chart(df_hist)
    else:
        st.info("Não há dados maiores que zero para este indicador.")

with col_tabela:
    st.markdown("**Top 10 Áreas com Maior Acesso**")
    st.caption("Hexágonos com os maiores índices selecionados.")
    
    # Ordena os dados do maior para o menor
    top10 = gdf.nlargest(10, 'valor_mapa')
    
    # Tenta encontrar a coluna de ID do hexágono ou nome do bairro (ajuste se o seu tiver outro nome)
    coluna_nome = 'hex_id' if 'hex_id' in gdf.columns else gdf.columns[0]
    
    df_top10 = top10[[coluna_nome, 'valor_mapa']].copy()
    df_top10.columns = ['ID da Área', 'Total de Oportunidades']
    df_top10['Total de Oportunidades'] = df_top10['Total de Oportunidades'].astype(int)
    
    # Mostra uma tabela interativa bonita
    st.dataframe(df_top10, use_container_width=True, hide_index=True)




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
    opacity=0.5,
    stroked=True,
    get_line_color=[77,77,77], # Linhas finas brancas entre hexágonos
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



