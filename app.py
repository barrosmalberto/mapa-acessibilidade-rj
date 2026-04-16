import streamlit as st
import pydeck as pdk
import geopandas as gpd
import zipfile
import os
import json
import numpy as np
import pandas as pd
import scipy
import matplotlib
import plotly.express as px

# ==========================================
# 1. CONFIGURAÇÃO DA PÁGINA
# ==========================================
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

    # ==========================================
    # CRUZAMENTO ESPACIAL: ÁREAS PROGRAMÁTICAS
    # ==========================================
    nome_arquivo_ap = "areas_saude.geojson" 
    
    if os.path.exists(nome_arquivo_ap):
        ap_gdf = gpd.read_file(nome_arquivo_ap)
        if ap_gdf.crs != "EPSG:4326":
            ap_gdf = ap_gdf.to_crs(epsg=4326)
            
        gdf_centroides = gdf.copy()
        gdf_centroides['geometry'] = gdf_centroides.geometry.centroid
        
        cruzamento = gpd.sjoin(gdf_centroides, ap_gdf, how='left', predicate='within')
        
        coluna_nome_ap = 'COD_AP_SMS' 
        
        if coluna_nome_ap in cruzamento.columns:
            gdf['Area_Programatica'] = cruzamento[coluna_nome_ap]
        else:
            gdf['Area_Programatica'] = "AP Desconhecida"
    else:
        gdf['Area_Programatica'] = "Base de APs não encontrada"

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
    
    # 3. Limpar o Percentil
    nome = nome.replace('_p50', '')
    nome = nome.replace('_p5', ' (Otimista)')
    nome = nome.replace('_p95', ' (Pessimista)')
    
    return nome.strip()

# ==========================================
# BARRA LATERAL (CONTROLOS)
# ==========================================
st.sidebar.title("🎮 Painel de Controle")

colunas_acessibilidade = [col for col in gdf.columns if 'transit' in col or 'walk' in col]

indicador = st.sidebar.selectbox(
    "Selecione o Indicador:", 
    colunas_acessibilidade,
    format_func=formatar_indicador
)

# --- FILTRO DE ÁREA PROGRAMÁTICA ---
# 1. Definimos um valor padrão seguro
ap_selecionada = "Rio de Janeiro (Cidade Toda)" 

if 'Area_Programatica' in gdf.columns and gdf['Area_Programatica'].nunique() > 1:
    lista_aps = ["Rio de Janeiro (Cidade Toda)"] + sorted(list(gdf['Area_Programatica'].dropna().unique()))
    ap_selecionada = st.sidebar.selectbox("🗺️ Filtrar por Área Programática:", lista_aps)

altura_max = st.sidebar.slider("Exagero vertical (Altura):", 500, 5000, 2000)

# ==========================================
# LÓGICA DE CORES E DADOS (COM BACKUP DO DATASET)
# ==========================================
# Calcula o valor ANTES de aplicar o filtro para o Boxplot
gdf['valor_mapa'] = gdf[indicador].fillna(0)

# Guarda o mapa completo da cidade
gdf_completo = gdf.copy()

# Aplica o filtro de AP (se o usuário não quiser a cidade toda)
if ap_selecionada != "Rio de Janeiro (Cidade Toda)":
    gdf = gdf[gdf['Area_Programatica'] == ap_selecionada]

max_val = gdf['valor_mapa'].max()

def get_color_rustic(val):
    if max_val <= 0: return [40, 40, 40, 50]
    frac = val / max_val
    
    if frac == 0:
        return [255, 252, 190, 50]
    elif frac < 0.05: 
        return [204, 197, 185, 200]
    elif frac < 0.20: 
        return [64, 61, 57, 220]
    elif frac < 0.50: 
        return [37, 36, 34, 240]
    else:             
        return [235, 94, 40, 255]

gdf['cor'] = gdf['valor_mapa'].apply(get_color_rustic)
gdf['altura'] = (gdf['valor_mapa'] / max_val) * altura_max if max_val > 0 else 0

# ==========================================
# NOVA FUNÇÃO: FRONTEIRA DO MUNICÍPIO/AP
# ==========================================
@st.cache_data
def get_limites(_gdf_alvo, nome_da_area):
    limite = _gdf_alvo[['geometry']].dissolve()
    return json.loads(limite.to_json())

dados_limite = get_limites(gdf, ap_selecionada)
dados_json = json.loads(gdf.to_json())

# ==========================================
# CABEÇALHO E MÉTRICAS
# ==========================================
st.title("🏙️ Dashboard de Acessibilidade Urbana - RJ")
st.subheader(f"Análise Atual: {formatar_indicador(indicador)}")

m1, m2, m3 = st.columns(3)
m1.metric("Áreas Analisadas", f"{len(gdf):,}".replace(",", "."))
m2.metric("Máximo de Acessos", f"{int(max_val):,}".replace(",", "."))
m3.metric("Média da Cidade", f"{int(gdf['valor_mapa'].mean()):,}".replace(",", "."))

# ==========================================
# ORGANIZAÇÃO EM ABAS
# ==========================================
aba_mapa, aba_stats, aba_correlacoes = st.tabs(["🗺️ Mapa Interativo", "📈 Distribuição", "🔗 Correlações e Testes"])

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

    layer_limites = pdk.Layer(
        "GeoJsonLayer",
        data=dados_limite,
        stroked=True,
        filled=False, 
        get_line_color=[0, 0, 0, 255], 
        get_line_width=2,
        line_width_min_pixels=2,
    )

    centro_lat = gdf.geometry.centroid.y.mean()
    centro_lon = gdf.geometry.centroid.x.mean()
    view = pdk.ViewState(latitude=centro_lat, longitude=centro_lon, zoom=10, pitch=45)

    st.pydeck_chart(pdk.Deck(
        map_style="light", 
        initial_view_state=view,
        layers=[layer, layer_limites], 
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
        colunas_nome = ['nome_bairro', 'NM_BAIRRO', 'bairro', 'hex_id']
        col_id = next((c for c in colunas_nome if c in gdf.columns), gdf.columns[0])
        
        top10 = gdf.nlargest(10, 'valor_mapa')[[col_id, 'valor_mapa']]
        top10.columns = ['Localidade', 'Qtd Oportunidades']
        st.dataframe(top10, hide_index=True, use_container_width=True)

    # ==========================================
    # CLUSTERIZAÇÃO POR AP (BOXPLOT COMPARTIVO)
    # ==========================================
    st.markdown("---")
    st.markdown("**Clusterização de Oportunidades por Área Programática**")
    st.caption("Compare a desigualdade entre as regiões. Os 'pontos' fora das caixas indicam hexágonos excepcionais (ilhas de oportunidades).")
    
    df_plot = gdf_completo[gdf_completo['valor_mapa'] > 0]
    
    if not df_plot.empty and 'Area_Programatica' in df_plot.columns:
        fig = px.box(
            df_plot, 
            x='Area_Programatica', 
            y='valor_mapa', 
            color='Area_Programatica',
            labels={'Area_Programatica': 'Área Programática', 'valor_mapa': 'Oportunidades'},
            template="plotly_dark"
        )
        fig.update_layout(showlegend=False, margin=dict(t=10, b=10, l=10, r=10))
        st.plotly_chart(fig, use_container_width=True)
    else:
        st.info("Não há dados de Área Programática suficientes para gerar o gráfico comparativo.")

with aba_correlacoes:
    st.markdown("### 🔗 Matriz de Correlação de Spearman")
    st.caption("Mede a força e a direção da relação monotônica entre os indicadores de acessibilidade. Valores próximos a 1 (Azul) indicam forte correlação positiva.")
    
    colunas_matriz = [col for col in gdf.columns if 'transit' in col or 'walk' in col]
    
    if len(colunas_matriz) > 1:
        df_matriz = gdf[colunas_matriz].corr(method='spearman')
        
        nomes_limpos = {col: formatar_indicador(col) for col in colunas_matriz}
        df_matriz = df_matriz.rename(columns=nomes_limpos, index=nomes_limpos)
        
        matriz_estilizada = df_matriz.style.background_gradient(cmap='RdBu', vmin=-1, vmax=1).format("{:.2f}")
        st.dataframe(matriz_estilizada, use_container_width=True)
    else:
        st.warning("É necessário ter pelo menos dois indicadores de acessibilidade para calcular correlações.")
