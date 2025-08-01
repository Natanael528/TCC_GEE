import streamlit as st
import ee
import geemap.foliumap as geemap
from datetime import date, datetime
import plotly.express as px
import plotly.graph_objects as go
import pandas as pd
import json
import tempfile

# --- Configurações Iniciais e Autenticação do GEE ---

# Função para inicializar o Earth Engine (evita reinicializar)
# Cria arquivo temporário com as credenciais
service_account_info = dict(st.secrets["earthengine"])

with tempfile.NamedTemporaryFile(mode='w+', suffix='.json', delete=False) as f:
    json.dump(service_account_info, f)
    f.flush()
    credentials = ee.ServiceAccountCredentials(service_account_info["client_email"], f.name)
    ee.Initialize(credentials)




# --- Configuração da Página do Streamlit ---

st.set_page_config(
    layout='wide',
    page_title='HydroGEE Analytics | Início',
    initial_sidebar_state='expanded',
    menu_items={
        'About': 'Aplicativo desenvolvido por Natanael Silva Oliveira para o TCC de Ciências Atmosféricas - UNIFEI.',
        'Report a bug': 'mailto:natanaeloliveira2387@gmail.com'
    },
    page_icon='💧'
)

with open('style.css')as f:
    st.markdown(f"<style>{f.read()}</style>", unsafe_allow_html = True)




# --- Constantes e Coleções do GEE ---

EE_COLLECTION = 'UCSB-CHG/CHIRPS/PENTAD'
SCALE = 5566 # Escala nativa do CHIRPS em metros

# Usar @st.cache_data para acelerar o carregamento de dados que não mudam
@st.cache_data
def get_feature_collection(name):
    if name == 'estados':
        return ee.FeatureCollection('FAO/GAUL/2015/level1').filter(ee.Filter.eq('ADM0_NAME', 'Brazil'))
    elif name == 'municipios':
        return ee.FeatureCollection('FAO/GAUL/2015/level2').filter(ee.Filter.eq('ADM0_NAME', 'Brazil'))
    return None

collection_estados = get_feature_collection('estados')
collection_municipios = get_feature_collection('municipios')


# --- Funções de Processamento de Dados (Otimizadas) ---

def get_annual_precipitation(collection, roi, start_year, end_year):
    years = ee.List.sequence(start_year, end_year)

    def calculate_annual(year):
        start_date = ee.Date.fromYMD(year, 1, 1)
        end_date = start_date.advance(1, 'year')
        total_precip_image = collection.filterDate(start_date, end_date).sum()
        mean_value = total_precip_image.reduceRegion(
            reducer=ee.Reducer.mean(), geometry=roi, scale=SCALE, maxPixels=1e12
        ).get('precipitation')
        return ee.Feature(None, {'year': year, 'precip': mean_value})

    annual_means_fc = ee.FeatureCollection(years.map(calculate_annual))
    data = annual_means_fc.getInfo()['features']
    rows = [f['properties'] for f in data]
    return pd.DataFrame(rows)

def get_monthly_climatology(collection, roi, start_year, end_year):
    months = ee.List.sequence(1, 12)
    num_years = end_year - start_year + 1

    def calculate_monthly(m):
        monthly_collection = collection.filter(ee.Filter.calendarRange(m, m, 'month'))
        total_precip = monthly_collection.sum()
        mean_monthly_precip = total_precip.divide(num_years)
        mean_value = mean_monthly_precip.reduceRegion(
            reducer=ee.Reducer.mean(), geometry=roi, scale=SCALE, maxPixels=1e12
        ).get('precipitation')
        return ee.Feature(None, {'month': m, 'precip': mean_value})

    monthly_means_fc = ee.FeatureCollection(months.map(calculate_monthly))
    data = monthly_means_fc.getInfo()['features']
    rows = [f['properties'] for f in data]
    df = pd.DataFrame(rows)
    df['month_name'] = df['month'].apply(lambda x: datetime(2023, x, 1).strftime('%b'))
    return df.sort_values(by='month').reset_index(drop=True)


# --- Interface do Usuário (Sidebar) ---

st.sidebar.header("1. Selecione a Região")
tipo_analise = st.sidebar.radio(
    "Como deseja selecionar a área?",
    ('Por Divisão Política', 'Por Ponto (Lat/Lon)', 'Desenhar no Mapa'),
    key='tipo_analise'
)

roi = None
local_selecionado_nome = "Área de Interesse"

if tipo_analise == 'Por Divisão Política':
    tipo_divisao = st.sidebar.radio("Analisar por:", ('Município', 'Estado'))
    try:
        estados = sorted(collection_estados.aggregate_array('ADM1_NAME').getInfo())
    except Exception as e:
        st.sidebar.error("Não foi possível carregar a lista de estados.")
        st.stop()
    
    estado_selecionado = st.sidebar.selectbox("Escolha o Estado", estados, index=estados.index('Minas Gerais'))
    
    if tipo_divisao == 'Município':
        if estado_selecionado:
            with st.spinner("Carregando municípios..."):
                municipios_filtrados = collection_municipios.filter(ee.Filter.eq('ADM1_NAME', estado_selecionado))
                municipios = sorted(municipios_filtrados.aggregate_array('ADM2_NAME').getInfo())
            municipio_selecionado = st.sidebar.selectbox("Escolha o Município", municipios, index=0)
            if municipio_selecionado:
                local_selecionado_nome = f"{municipio_selecionado}, {estado_selecionado}"
                roi_fc = collection_municipios.filter(
                    ee.Filter.And(
                        ee.Filter.eq('ADM1_NAME', estado_selecionado),
                        ee.Filter.eq('ADM2_NAME', municipio_selecionado)
                    )
                )
                roi = roi_fc.geometry()
    else: # Estado
        local_selecionado_nome = estado_selecionado
        roi_fc = collection_estados.filter(ee.Filter.eq('ADM1_NAME', estado_selecionado))
        roi = roi_fc.geometry()

# --- Trecho Corrigido ---

elif tipo_analise == 'Por Ponto (Lat/Lon)':
    st.sidebar.markdown("Digite as coordenadas e o raio do buffer.")
    
    # CORRIGIDO: Usando argumentos nomeados para clareza e correção
    lat = st.sidebar.number_input(
        label="Latitude",
        min_value=-90.0,
        max_value=90.0,
        value=-19.92,  # Valor padrão (ex: Belo Horizonte)
        format="%.4f"
    )
    
    # CORRIGIDO: Usando argumentos nomeados para clareza e correção
    lon = st.sidebar.number_input(
        label="Longitude",
        min_value=-180.0,
        max_value=180.0,
        value=-43.94, # Valor padrão (ex: Belo Horizonte)
        format="%.4f"
    )
    
    buffer_radius = st.sidebar.number_input("Raio (em metros)", 100, 50000, 10000, step=1000)
    
    local_selecionado_nome = f"Ponto ({lat:.2f}, {lon:.2f}) com raio de {buffer_radius/1000:.1f} km"
    point = ee.Geometry.Point([lon, lat])
    roi = point.buffer(buffer_radius)

# A seleção por "Desenhar no Mapa" é tratada na seção principal

st.sidebar.header("2. Selecione o Período")
# Limita o range de datas disponíveis para o CHIRPS
current_year = date.today().year
start_year = st.sidebar.slider("Ano Inicial", 1981, current_year, 1991)
end_year = st.sidebar.slider("Ano Final", 1981, current_year, current_year - 1)


# --- Lógica Principal e Exibição ---
st.title("☔️ Análise de Precipitação Acumulada (CHIRPS)")

if tipo_analise == 'Desenhar no Mapa':
    st.info("Utilize as ferramentas no canto esquerdo do mapa para desenhar um polígono ou retângulo. Depois de desenhar, clique em 'Gerar Análise'.")
    m_draw = geemap.Map(center=[-19, -60], zoom=4)
    m_draw.add_basemap("HYBRID")
    m_draw.to_streamlit()
    
    if m_draw.draw_last_feature:
        drawn_feature = m_draw.draw_last_feature
        roi = ee.Geometry(drawn_feature.geometry)
        local_selecionado_nome = "Área Desenhada no Mapa"

# Botão de análise centralizado
run_analysis = st.sidebar.button("📊 Gerar Análise", type="primary", use_container_width=True)

if not run_analysis:
    st.info("👈 Configure as opções na barra lateral e clique em 'Gerar Análise' para começar.")
    st.stop()

# --- Validações ---
if roi is None:
    st.error("❌ A região de interesse (ROI) não foi definida. Por favor, selecione uma opção válida ou desenhe no mapa.")
    st.stop()
if start_year >= end_year:
    st.error("❌ O ano inicial deve ser anterior ao ano final.")
    st.stop()

# --- Execução da Análise ---
with st.spinner(f"Processando dados para '{local_selecionado_nome}'... Isso pode levar alguns minutos."):
    precip_collection = ee.ImageCollection(EE_COLLECTION) \
        .select('precipitation') \
        .filterDate(f"{start_year}-01-01", f"{end_year}-12-31") \
        .filterBounds(roi)
    
    # Executa as duas coletas de dados em paralelo (conceitualmente)
    df_annual = get_annual_precipitation(precip_collection, roi, start_year, end_year)
    df_monthly = get_monthly_climatology(precip_collection, roi, start_year, end_year)

# --- Exibição dos Resultados ---
st.header(f"📍 Resultados para: {local_selecionado_nome}")

# Métricas Principais
if not df_annual.empty and 'precip' in df_annual.columns:
    media_anual = df_annual['precip'].mean()
    ano_mais_chuvoso = df_annual.loc[df_annual['precip'].idxmax()]
    ano_menos_chuvoso = df_annual.loc[df_annual['precip'].idxmin()]
    
    col1, col2, col3 = st.columns(3)
    col1.metric("Precipitação Média Anual", f"{media_anual:.1f} mm")
    col2.metric("Ano Mais Chuvoso", f"{int(ano_mais_chuvoso['year'])} ({ano_mais_chuvoso['precip']:.1f} mm)")
    col3.metric("Ano Menos Chuvoso", f"{int(ano_menos_chuvoso['year'])} ({ano_menos_chuvoso['precip']:.1f} mm)")
else:
    st.warning("Não foi possível calcular as métricas anuais.")

# Abas para organizar os gráficos
tab1, tab2, tab3, tab4 = st.tabs(["🗺️ Mapa", "📊 Série Anual", "📈 Climatologia Mensal", "🗓️ Heatmap Anual"])

with tab1:
    st.subheader("Mapa da Região de Interesse")
    m_roi = geemap.Map(height=450)
    m_roi.centerObject(roi, 10)
    m_roi.addLayer(roi, {'color': '#007BFF', 'fillColor': '#007BFF50'}, 'Região de Interesse')
    
    # # Adiciona a camada de precipitação média para contexto
    # precip_media_total = precip_collection.mean()
    # vis_params = {
    #     'min': 0, 'max': 2500,
    #     'palette': ['#ffffcc', '#a1dab4', '#41b6c4', '#2c7fb8', '#253494']
    # }
    # m_roi.addLayer(precip_media_total, vis_params, 'Precipitação Média (mm/ano)')
    # m_roi.add_colorbar(vis_params, label="Precipitação Média Anual (mm)", layer_name='Precipitação Média (mm/ano)')
    
    m_roi.to_streamlit()

with tab2:
    st.subheader(f"Precipitação Anual Total ({start_year}-{end_year})")
    if not df_annual.empty and not df_annual['precip'].isnull().all():

        media_historica = df_annual['precip'].mean() ############### media histórica
        df_annual['anomalia'] = df_annual['precip'] - media_historica
        df_annual['cor'] = df_annual['anomalia'].apply(lambda x: '#007BFF' if x > 0 else '#FF4B4B')

        fig_annual = go.Figure()
        fig_annual.add_trace(go.Bar(
            x=df_annual['year'],
            y=df_annual['precip'],
            marker_color=df_annual['cor'],
            name='Precipitação Anual'
        ))
        fig_annual.add_trace(go.Scatter(
            x=df_annual['year'],
            y=[media_historica] * len(df_annual),
            mode='lines',
            line=dict(color='yellow', dash='dash'),
            name=f'Média Histórica ({media_historica:.1f} mm)'
        ))
        fig_annual.update_layout(
            title=f"Precipitação Anual e Anomalia em Relação à Média<br><b>{local_selecionado_nome}</b>",
            xaxis_title="Ano",
            yaxis_title="Precipitação Anual Acumulada (mm)",
            template="plotly_white"
        )
        st.plotly_chart(fig_annual, use_container_width=True)
    else:
        st.warning("Não há dados anuais para o período selecionado.")

with tab3:
    st.subheader(f"Climatologia Mensal ({start_year}-{end_year})")
    if not df_monthly.empty and not df_monthly['precip'].isnull().all():
        fig_monthly = px.bar(
            df_monthly, x="month_name", y="precip",
            labels={"month_name": "Mês", "precip": "Precipitação Média Mensal (mm)"},
            title=f"Precipitação Média Mensal (Climatologia)<br><b>{local_selecionado_nome}</b>",
        )
        fig_monthly.update_traces(marker_color="#0384fc")
        fig_monthly.update_layout(template="plotly_white", xaxis_title='Mês')
        st.plotly_chart(fig_monthly, use_container_width=True)
    else:
        st.warning("Não há dados mensais para o período selecionado.")

# with tab4:
    # st.subheader(f"Heatmap de Precipitação Mensal por Ano ({start_year}-{end_year})")
    # with st.spinner("Gerando heatmap... esta é uma análise mais intensiva."):
    #     # NOVO: Gráfico de Heatmap
    #     # Precisamos de uma função mais detalhada para isso
    #     def get_monthly_data_per_year(collection, roi, start_year, end_year):
    #         all_data = []
    #         for year in range(start_year, end_year + 1):
    #             for month in range(1, 13):
    #                 start_date = ee.Date.fromYMD(year, month, 1)
    #                 end_date = start_date.advance(1, 'month')
    #                 monthly_image = collection.filterDate(start_date, end_date).sum()
    #                 value = monthly_image.reduceRegion(
    #                     reducer=ee.Reducer.mean(), geometry=roi, scale=SCALE, maxPixels=1e12
    #                 ).get('precipitation')
    #                 all_data.append({'year': year, 'month': month, 'precip': value})
            
    #         # getInfo() em um loop pode ser lento. Para produção, é melhor reestruturar no lado do servidor com map().
    #         # Para este exemplo, faremos o getInfo da forma mais simples possível.
    #         ee_list = ee.List(all_data)
            
    #         # Uma forma mais eficiente, mas mais complexa de escrever:
    #         years = ee.List.sequence(start_year, end_year)
    #         months = ee.List.sequence(1, 12)
            
    #         def by_year(y):
    #             def by_month(m):
    #                 img = collection.filter(ee.Filter.calendarRange(y, y, 'year')) \
    #                                 .filter(ee.Filter.calendarRange(m, m, 'month')) \
    #                                 .sum()
    #                 val = img.reduceRegion(ee.Reducer.mean(), roi, SCALE, maxPixels=1e12).get('precipitation')
    #                 return ee.Feature(None, {'year': y, 'month': m, 'precip': val})
    #             return months.map(by_month)

    #         ee_fc = ee.FeatureCollection(years.map(by_year).flatten())
            
    #         try:
    #             data = ee_fc.getInfo()['features']
    #             rows = [f['properties'] for f in data]
    #             df = pd.DataFrame(rows)
    #             df.dropna(subset=['precip'], inplace=True)
                
    #             heatmap_pivot = df.pivot(index='year', columns='month', values='precip')
    #             heatmap_pivot.columns = [datetime(2023, m, 1).strftime('%b') for m in heatmap_pivot.columns]
                
    #             fig_heatmap = px.imshow(
    #                 heatmap_pivot,
    #                 labels=dict(x="Mês", y="Ano", color="Precipitação (mm)"),
    #                 title=f"Heatmap de Precipitação Mensal<br><b>{local_selecionado_nome}</b>",
    #                 color_continuous_scale=px.colors.sequential.YlGnBu
    #             )
    #             st.plotly_chart(fig_heatmap, use_container_width=True)

    #         except Exception as e:
    #             st.error("Não foi possível gerar o heatmap. A consulta pode ser muito complexa para a área/período selecionado.")
    #             st.write(e)