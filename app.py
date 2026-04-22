import streamlit as st
import pydeck as pdk
import geopandas as gpd
import zipfile
import os
import json
import numpy as np
import pandas as pd
import scipy.stats as stats  # <-- IMPORT ATUALIZADO
import matplotlib
import plotly.express as px
import plotly.graph_objects as go

# ==========================================
# 1. CONFIGURAÇÃO DA PÁGINA
# ==========================================
st.set_page_config(page_title="Dashboard de Acessibilidade RJ", layout="wide")

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

    # ==========================================
    # CRUZAMENTO ESPACIAL: DADOS SOCIOECONÔMICOS
    # ==========================================
    nome_arquivo_socio = "territorios_poly_expansao.geojson"
    if os.path.exists(nome_arquivo_socio):
        try:
            socio_gdf = gpd.read_file(nome_arquivo_socio)
            if socio_gdf.crs != "EPSG:4326":
                socio_gdf = socio_gdf.to_crs(epsg=4326)
            
            # Garante que criamos o centroide apenas se não existir
            if 'gdf_centroides' not in locals():
                gdf_centroides = gdf.copy()
                gdf_centroides['geometry'] = gdf_centroides.geometry.centroid
                
            vars_socio = ['IPM', 'Rnd_p_capi', 'Tx_desocup']
            cols_to_keep = ['geometry'] + [c for c in vars_socio if c in socio_gdf.columns]
            
            cruzamento_socio = gpd.sjoin(gdf_centroides, socio_gdf[cols_to_keep], how='left', predicate='within')
            
            # Removemos duplicações caso haja sobreposição minúscula de polígonos
            cruzamento_socio = cruzamento_socio[~cruzamento_socio.index.duplicated(keep='first')]
            
            for var in vars_socio:
                if var in cruzamento_socio.columns:
                    gdf[var] = pd.to_numeric(cruzamento_socio[var], errors='coerce')
        except Exception as e:
            print(f"Aviso ao carregar dados socioeconômicos: {e}")

    return gdf

gdf = load_data()

# ==========================================
# FUNÇÃO DE FORMATAÇÃO (TRADUTOR DE VARIÁVEIS)
# ==========================================
def formatar_indicador(nome_tecnico):
    nome = nome_tecnico
    nome = nome.replace('jobs_vinculos', 'Empregos')
    nome = nome.replace('schools_creche', 'Creches')
    nome = nome.replace('schools_pre', 'Pré-escolas')
    nome = nome.replace('schools_fundamental', 'Ensino Fundamental')
    nome = nome.replace('saude_primaria', 'Saúde Primária')
    nome = nome.replace('saude_emergencia', 'Saúde de Emergência')
    nome = nome.replace('_15min_', ' em 15 min ')
    nome = nome.replace('_30min_', ' em 30 min ')
    nome = nome.replace('_60min_', ' em 60 min ')
    nome = nome.replace('transit', 'via Transp. Público')
    nome = nome.replace('walk', 'a pé')
    nome = nome.replace('_p50', '')
    nome = nome.replace('_p5', ' (Otimista)')
    nome = nome.replace('_p95', ' (Pessimista)')
    
    # Formatação das variáveis socioeconômicas
    nome = nome.replace('IPM', 'Índ. Pobreza Multidimensional (IPM)')
    nome = nome.replace('Rnd_p_capi', 'Renda per capita')
    nome = nome.replace('Tx_desocup', 'Taxa de Desocupação')
    
    return nome.strip()

# ==========================================
# BARRA LATERAL (CONTROLOS)
# ==========================================
st.sidebar.title("🎛️ Painel de Controle")

colunas_acessibilidade = [col for col in gdf.columns if 'transit' in col or 'walk' in col]

indicador = st.sidebar.selectbox(
    "Selecione o Indicador:", 
    colunas_acessibilidade,
    format_func=formatar_indicador
)

# --- FILTRO DE ÁREA PROGRAMÁTICA ---
ap_selecionada = "Rio de Janeiro (Cidade Toda)" 

if 'Area_Programatica' in gdf.columns and gdf['Area_Programatica'].nunique() > 1:
    lista_aps = ["Rio de Janeiro (Cidade Toda)"] + sorted(list(gdf['Area_Programatica'].dropna().unique()))
    ap_selecionada = st.sidebar.selectbox("🗺️ Filtrar por Área Programática:", lista_aps)

altura_max = st.sidebar.slider("Exagero vertical (Altura):", 500, 5000, 2000)

# ==========================================
# LÓGICA DE CORES E DADOS
# ==========================================
gdf['valor_mapa'] = gdf[indicador].fillna(0)
gdf_completo = gdf.copy()

if ap_selecionada != "Rio de Janeiro (Cidade Toda)":
    gdf = gdf[gdf['Area_Programatica'] == ap_selecionada]

max_val = gdf['valor_mapa'].max()

def calcular_gini(valores):
    valores = np.sort(np.array(valores, dtype=np.float64))
    valores = valores[valores > 0] 
    if len(valores) < 2:
        return 0.0
    n = len(valores)
    index = np.arange(1, n + 1)
    gini = (np.sum((2 * index - n  - 1) * valores)) / (n * np.sum(valores))
    return gini

def get_color_sunset(val):
    if max_val <= 0: return [40, 40, 40, 50]
    frac = val / max_val
    if frac == 0:
        return [255, 255, 255, 10] 
    elif frac < 0.05: 
        return [158, 1, 66, 200]
    elif frac < 0.20: 
        return [244, 109, 67, 220]
    elif frac < 0.50: 
        return [253, 174, 97, 240]
    else:             
        return [230, 245, 152, 255]

gdf['cor'] = gdf['valor_mapa'].apply(get_color_sunset)
gdf['altura'] = (gdf['valor_mapa'] / max_val) * altura_max if max_val > 0 else 0

# ==========================================
# FRONTEIRA DO MUNICÍPIO/AP
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
st.title("🏙️ Painel de Acessibilidade Urbana - RJ")
st.subheader(f"Análise Atual: {formatar_indicador(indicador)}")

m1, m2, m3 = st.columns(3)
m1.metric("Áreas Analisadas", f"{len(gdf):,}".replace(",", "."))
m2.metric("Máximo de Acessos", f"{int(max_val):,}".replace(",", "."))
m3.metric("Média da Cidade", f"{int(gdf['valor_mapa'].mean()):,}".replace(",", "."))

# ==========================================
# ORGANIZAÇÃO EM ABAS
# ==========================================
aba_mapa, aba_stats, aba_correlacoes, aba_chat = st.tabs([
    "🗺️ Mapa Interativo", 
    "📈 Distribuição", 
    "🔗 Correlações e Testes",
    "💬 Assistente Virtual"
])

with aba_mapa:
    # --- CAMADA 1: HEXÁGONOS 3D (As "Torres") ---
    # Camada de Calor (Heatmap) foi removida a pedido para um visual mais limpo
    layer_hex = pdk.Layer(
        "GeoJsonLayer",
        data=dados_json,
        opacity=0.8, # Opacidade aumentada já que não há calor embaixo
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

    # --- CAMADA 2: FRONTEIRAS (A "Cerca" Branca) ---
    layer_limites = pdk.Layer(
        "GeoJsonLayer",
        data=dados_limite,
        stroked=True,
        filled=False, 
        get_line_color=[255, 255, 255, 200], 
        get_line_width=3,
        line_width_min_pixels=3,
    )

    centro_lat = gdf.geometry.centroid.y.mean()
    centro_lon = gdf.geometry.centroid.x.mean()
    
    view = pdk.ViewState(latitude=centro_lat, longitude=centro_lon, zoom=10, pitch=45)

    st.pydeck_chart(pdk.Deck(
        map_style="dark", 
        initial_view_state=view,
        layers=[layer_hex, layer_limites], # Apenas Hexágonos e Limites
        tooltip={"text": "Oportunidades: {valor_mapa}"}
    ))

with aba_stats:
    st.markdown("### 📊 Decomposição e Desigualdade dos Dados")
    
    gini_val = calcular_gini(gdf['valor_mapa'])
    
    fig_gini = go.Figure(go.Indicator(
        mode = "gauge+number",
        value = gini_val,
        title = {'text': "Índice de Gini (Desigualdade Espacial)", 'font': {'size': 18}},
        gauge = {
            'axis': {'range': [0, 1]},
            'bar': {'color': "white"},
            'steps': [
                {'range': [0.0, 0.3], 'color': "#2ca02c"},
                {'range': [0.3, 0.5], 'color': "#f5b111"},
                {'range': [0.5, 0.7], 'color': "#ff7f0e"},
                {'range': [0.7, 1.0], 'color': "#d62728"} 
            ],
        }
    ))
    fig_gini.update_layout(height=280, margin=dict(l=10, r=10, t=40, b=10), template="plotly_dark")
    
    st.plotly_chart(fig_gini, use_container_width=True)
    st.markdown("---")

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
    # --- TABELA 1: ACESSIBILIDADE X ACESSIBILIDADE ---
    st.markdown("### 🔗 Matriz: Acessibilidade X Acessibilidade")
    
    tempo_selecionado = st.radio(
        "Focar a análise em um tempo de deslocamento específico:",
        ["Matriz Completa", "Apenas 15 minutos", "Apenas 30 minutos", "Apenas 60 minutos"],
        horizontal=True
    )
    
    colunas_matriz = [col for col in gdf.columns if 'transit' in col or 'walk' in col]
    
    if tempo_selecionado == "Apenas 15 minutos":
        colunas_matriz = [col for col in colunas_matriz if '_15min_' in col]
    elif tempo_selecionado == "Apenas 30 minutos":
        colunas_matriz = [col for col in colunas_matriz if '_30min_' in col]
    elif tempo_selecionado == "Apenas 60 minutos":
        colunas_matriz = [col for col in colunas_matriz if '_60min_' in col]
    
    if len(colunas_matriz) > 1:
        df_matriz = gdf[colunas_matriz].corr(method='spearman')
        nomes_limpos = {col: formatar_indicador(col) for col in colunas_matriz}
        df_matriz = df_matriz.rename(columns=nomes_limpos, index=nomes_limpos)
        matriz_estilizada = df_matriz.style.background_gradient(cmap='RdBu', vmin=-1, vmax=1).format("{:.2f}")
        st.dataframe(matriz_estilizada, use_container_width=True)
    else:
        st.warning("É necessário ter pelo menos dois indicadores no tempo selecionado para calcular correlações.")

    # ==========================================
    # TABELA 2: SOCIOECONÔMICA
    # ==========================================
    st.markdown("---")
    st.markdown("#### 📉 Matriz: Acessibilidade X Vulnerabilidade Social")
    st.caption("**Tons de Vermelho (-)** apresentam a falta de infraestrutura")

    cols_socio = [c for c in ['IPM', 'Rnd_p_capi', 'Tx_desocup'] if c in gdf.columns]
    
    if len(cols_socio) > 0 and len(colunas_matriz) > 0:
        df_matriz_socio = gdf[colunas_matriz + cols_socio].corr(method='spearman')
        
        df_matriz_socio = df_matriz_socio.loc[colunas_matriz, cols_socio]
        
        nomes_limpos_acc = {col: formatar_indicador(col) for col in colunas_matriz}
        nomes_limpos_socio = {col: formatar_indicador(col) for col in cols_socio}
        df_matriz_socio = df_matriz_socio.rename(index=nomes_limpos_acc, columns=nomes_limpos_socio)
        
        matriz_socio_estilizada = df_matriz_socio.style.background_gradient(cmap='RdBu', vmin=-1, vmax=1).format("{:.2f}")
        st.dataframe(matriz_socio_estilizada, use_container_width=True)
        
        # ==========================================
        # GRÁFICOS DE DISPERSÃO (COM P-VALOR LIMPO)
        # ==========================================
        st.markdown("---")
        st.markdown(f"#### 📍 Visão de Dispersão: **{formatar_indicador(indicador)}** X Dados Sociais")
        st.caption("Cada ponto é uma área do mapa. A linha mostra a tendência. Foram removidas áreas com zero acessos.")
        
        cols_graficos = st.columns(len(cols_socio))
        
        try:
            tema_escuro = st.get_option("theme.base") == "dark"
        except:
            tema_escuro = False

        cor_solida = "white" if tema_escuro else "black"
        
        for i, var_socio in enumerate(cols_socio):
            with cols_graficos[i]:
                df_plot = gdf[[indicador, var_socio]].replace([np.inf, -np.inf], np.nan).dropna()
                df_plot = df_plot[(df_plot[indicador] > 0) & (df_plot[var_socio] > 0)]
                
                if len(df_plot) > 1: 
                    # Calcula o Spearman apenas para extrair o P-valor
                    corr, pval = stats.spearmanr(df_plot[indicador], df_plot[var_socio])
                    p_text = "< 0.001" if pval < 0.001 else f"{pval:.4f}"
                    
                    # Cria o título com estilo minimalista contendo APENAS o P-valor
                    titulo_grafico = f"{formatar_indicador(var_socio)}<br><span style='font-size:12px; font-weight:normal;'>P-valor: {p_text}</span>"
                    
                    if len(df_plot) > 3000:
                        df_plot = df_plot.sample(3000, random_state=42)
                    
                    fig_disp = px.scatter(
                        df_plot,
                        x=indicador,
                        y=var_socio,
                        opacity=1.0,
                        color_discrete_sequence=[cor_solida],
                        labels={indicador: "Oportunidades", var_socio: formatar_indicador(var_socio)}
                        # O título foi removido daqui para ser passado no update_layout e evitar sobreposições
                    )
                    
                    fig_disp.update_traces(marker_size=2, selector=dict(mode='markers'))
                    
                    try:
                        z = np.polyfit(df_plot[indicador], df_plot[var_socio], 1)
                        p = np.poly1d(z)
                        
                        fig_disp.add_scatter(
                            x=df_plot[indicador], 
                            y=p(df_plot[indicador]), 
                            mode='lines', 
                            name='Tendência', 
                            line=dict(color=cor_solida, width=3),
                            showlegend=False
                        )
                    except:
                        pass
                    
                    # Margem superior (t=85) aumentada consideravelmente para não esmagar os números do eixo Y
                    fig_disp.update_layout(
                        title=dict(text=titulo_grafico, font=dict(size=14)),
                        margin=dict(l=10, r=10, t=85, b=10), 
                        height=300
                    )
                    
                    st.plotly_chart(fig_disp, use_container_width=True, theme="streamlit")
                else:
                    st.info("📍 Poucos ou nenhum acesso nesta região para gerar gráfico.")

# ==========================================
# LÓGICA DO CHAT (FUNÇÃO FRAGMENTADA)
# ==========================================
@st.fragment
def renderizar_chat():
    if "mensagens" not in st.session_state:
        st.session_state.mensagens = []

    for msg in st.session_state.mensagens:
        with st.chat_message(msg["role"]):
            st.markdown(msg["content"])

    if pergunta := st.chat_input("Ex: O que é o Índice de Gini?"):
        with st.chat_message("user"):
            st.markdown(pergunta)
            
        st.session_state.mensagens.append({"role": "user", "content": pergunta})
        
        try:
            import google.generativeai as genai
            genai.configure(api_key=st.secrets["GEMINI_API_KEY"])
            
            modelos_disponiveis = [m.name for m in genai.list_models() if 'generateContent' in m.supported_generation_methods]
            
            modelo_escolhido = "gemini-2.5-flash-lite" 
            preferencias = [
                'models/gemini-2.5-flash-lite', 
                'models/gemini-2.0-flash-lite', 
                'models/gemini-flash-lite-latest',
                'models/gemini-2.0-flash'
            ]
            
            for pref in preferencias:
                if pref in modelos_disponiveis:
                    modelo_escolhido = pref.replace('models/', '')
                    break
            
            model = genai.GenerativeModel(modelo_escolhido)
            
            instrucao = "Você é um Analista de Dados Sênior e especialista em planejamento urbano. O seu objetivo é ajudar usuários interessados sobre a gestão urbana do município do Rio de Janeiro a interpretar um dashboard de Acessibilidade Urbana. Explique conceitos, resultados estatísticos e métricas de transporte de forma clara e executiva."
            
            gemini_history = [
                {"role": "user", "parts": [instrucao]},
                {"role": "model", "parts": ["Entendido! Estou pronto para analisar os dados urbanos do Rio de Janeiro."]}
            ]
            
            historico_recente = st.session_state.mensagens[-5:-1] if len(st.session_state.mensagens) > 4 else st.session_state.mensagens[:-1]
            
            for msg in historico_recente: 
                role = "user" if msg["role"] == "user" else "model"
                gemini_history.append({"role": role, "parts": [msg["content"]]})
                
            chat = model.start_chat(history=gemini_history)
            
            with st.spinner(f"A analisar dados (via {modelo_escolhido})..."):
                resposta_api = chat.send_message(pergunta)
                resposta = resposta_api.text
            
        except Exception as e:
            resposta = f"**Aguarde um momento.** O limite de processamento rápido foi atingido. Por favor, aguarde 30 segundos e faça a pergunta novamente.\n\n*(Detalhe técnico: {e})*"
        
        with st.chat_message("assistant"):
            st.markdown(resposta)
        st.session_state.mensagens.append({"role": "assistant", "content": resposta})

with aba_chat:
    st.markdown("### 💬 Assistente Virtual de Acessibilidade")
    st.caption("Tire suas dúvidas sobre os dados, o Índice de Gini ou peça ajuda para interpretar o mapa.")
    renderizar_chat()
