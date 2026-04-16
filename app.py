import streamlit as st
import pydeck as pdk
import geopandas as gpd
import zipfile
import os
import json
import numpy as np
import pandas as pd

# 1. CONFIGURAÇÃO DA PÁGINA
st.set_page_config(page_title="Dashboard Acessibilidade RJ", layout="wide")

@st.cache_data
def load_data():
    nome_geojson = "hexgrid_with_accessibility.geojson"
    nome_zip = "hexgrid_with_accessibility.zip"
    
    if not os.path.exists(nome_geojson):
        if os.path.exists(nome_zip):
            with zipfile.ZipFile(nome_zip, 'r') as zip_ref:
                zip_ref.extractall(".")
    
    gdf = gpd.read_file(nome_geojson)
    if gdf.crs != "EPSG:4326":
        gdf = gdf.to_crs(epsg=4326)
    return gdf

gdf = load_data()


# ==========================================
# FUNÇÃO DE FORMATAÇÃO (TRADUTOR DE VARIÁVEIS)
# ==========================================
def formatar_indicador(nome_tecnico):
    nome = nome_tecnico
    
    # 1. Traduzir o Tema (Oportunidades)
    nome = nome.replace('jobs_vinculos', 'Empregos')
    nome = nome.replace('schools_creche', 'Creches')
    nome = nome.replace('schools_pre', 'Pré-escolas')
    nome = nome.replace('schools_fundamental', 'Ensino Fundamental')
    nome = nome.replace('saude_primaria', 'Saúde Primária')
    nome = nome.replace('saude_emergencia', 'Saúde de Emergência')
    
    # 2. Traduzir o Tempo e o Modo
    nome = nome.replace('_15min_', ' em 15 min ')
    nome = nome.replace('_30min_', ' em 30 min ')
    nome = nome.replace('_60min_', ' em 60 min ')
    nome = nome.replace('transit', 'via Transp. Público')
    nome = nome.replace('walk', 'a pé')
    
    # 3. Limpar o Percentil (Ocultar o p50 que é o padrão, ou dar nome aos outros)
    # nome = nome.replace('_p50', '_p50')
    # nome = nome.replace('_p5', '_p5')
    # nome = nome.replace('_p95', '_p95')
    
    return nome.strip()





# ==========================================
# 3. BARRA LATERAL (CONTROLOS)
# ==========================================
st.sidebar.title("Painel de Controle")

colunas_acessibilidade = [col for col in gdf.columns if 'transit' in col or 'walk' in col]

# Aqui o "format_func" chama a função que acabamos de criar acima!
indicador = st.sidebar.selectbox(
    "Selecione o Indicador:", 
    colunas_acessibilidade,
    format_func=formatar_indicador
)

altura_max = st.sidebar.slider("Exagero vertical (Altura):", 500, 5000, 2000)

# ==========================================
# LÓGICA DE CORES E DADOS
# ==========================================
gdf['valor_mapa'] = gdf[indicador].fillna(0)
max_val = gdf['valor_mapa'].max()

def get_color_rustic(val):
    if max_val <= 0: return [40, 40, 40, 50]
    frac = val / max_val
    # Paleta Rustic Charm (RGBA)
    if frac == 0:     return [255, 252, 190, 140]
    elif frac < 0.25: return [204, 197, 185, 180]
    elif frac < 0.5:  return [64, 61, 57, 200]
    elif frac < 0.75: return [37, 36, 34, 230]
    else:             return [235, 94, 40, 255]

gdf['cor'] = gdf['valor_mapa'].apply(get_color_rustic)
gdf['altura'] = (gdf['valor_mapa'] / max_val) * altura_max if max_val > 0 else 0

dados_json = json.loads(gdf.to_json())

# ==========================================
# CABEÇALHO E MÉTRICAS (ESTATÍSTICAS RÁPIDAS)
# ==========================================
st.title("🏙️ Dashboard de Acessibilidade Urbana - RJ")
st.subheader(f"Análise Atual: {formatar_indicador(indicador)}")

m1, m2, m3 = st.columns(3)
m1.metric("Áreas Analisadas", f"{len(gdf):,}".replace(",", "."))
m2.metric("Máximo de Acessos", f"{int(max_val):,}".replace(",", "."))
m3.metric("Média da Cidade", f"{int(gdf['valor_mapa'].mean()):,}".replace(",", "."))

# ==========================================
# ORGANIZAÇÃO EM ABAS (O SEGREDO DO LAYOUT)
# ==========================================
aba_mapa, aba_stats = st.tabs(["🗺️ Mapa Interativo", "📈 Estatísticas Detalhadas"])

with aba_mapa:
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

    st.pydeck_chart(pdk.Deck(
        map_style="dark", 
        initial_view_state=view,
        layers=[layer],
        tooltip={"text": "Oportunidades: {valor_mapa}"}
    ))

with aba_stats:
    st.markdown("### 📊 Decomposição dos Dados")
    
    col_graf, col_tab = st.columns([2, 1])
    
    with col_graf:
        st.markdown("**Distribuição de Oportunidades**")
        dados_validos = gdf[gdf['valor_mapa'] > 0]['valor_mapa']
        if len(dados_validos) > 0:
            contagem, divisorias = np.histogram(dados_validos, bins=20)
            rotulos = [f"{int(divisorias[i])}-{int(divisorias[i+1])}" for i in range(len(contagem))]
            df_hist = pd.DataFrame({'Nº de Áreas': contagem}, index=rotulos)
            st.bar_chart(df_hist)
        else:
            st.info("Aguardando dados para gerar o gráfico...")

    with col_tab:
        st.markdown("**Top 10 Melhores Localidades**")
        # Procura por colunas de nome. Se não houver, usa o ID.
        colunas_nome = ['nome_bairro', 'NM_BAIRRO', 'bairro', 'hex_id']
        col_id = next((c for c in colunas_nome if c in gdf.columns), gdf.columns[0])
        
        top10 = gdf.nlargest(10, 'valor_mapa')[[col_id, 'valor_mapa']]
        top10.columns = ['Localidade', 'Qtd Oportunidades']
        st.dataframe(top10, hide_index=True, use_container_width=True)
