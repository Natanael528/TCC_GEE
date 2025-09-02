import streamlit as st
import folium
from folium.plugins import Draw
from streamlit_folium import st_folium
import ee
import geemap.foliumap as geemap
from datetime import date, datetime
import plotly.express as px
import plotly.graph_objects as go
import pandas as pd
import json
import tempfile

# --- Configurações Iniciais e Autenticação do GEE ---
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


# --- Constantes e Dicionário de Datasets ---
# Unificando a configuração dos datasets em um único lugar
DATASETS = {
    'CHIRPS Daily': {
        'id': 'UCSB-CHG/CHIRPS/DAILY',
        'band': 'precipitation',
        'multiplier': 1,
        'start_year': 1981,
        'scale': 5566,
        'name': 'UCSB-CHG CHIRPS Daily',
    },
    'IMERG Daily': {
        'id': 'NASA/GPM_L3/IMERG_V07',
        'band': 'precipitation',
        'multiplier': 0.5, # Multiplicador para converter para 24h
        'start_year': 2000,
        'scale': 11132,
        'name': 'NASA GPM IMERG Daily (GPM L3)',
    },
    'GSMAP Standard': {
        'id': 'JAXA/GPM_L3/GSMaP/v8/operational',
        'band': 'hourlyPrecipRate',
        'multiplier': 1, # Já está em mm/hr, a soma diária funciona
        'start_year': 2000,
        'scale': 11132,
        'name': 'JAXA GPM GSMaP Standard',
    }
}
SCALE = 5566 # Escala padrão, pode ser sobrescrita pelo dataset

# --- Funções de Cache para Coleções de Features ---
@st.cache_data
def get_feature_collection(name):
    """Busca e armazena em cache coleções de features (limites políticos)."""
    if name == 'estados':
        return ee.FeatureCollection('FAO/GAUL/2015/level1').filter(ee.Filter.eq('ADM0_NAME', 'Brazil'))
    elif name == 'municipios':
        return ee.FeatureCollection('FAO/GAUL/2015/level2').filter(ee.Filter.eq('ADM0_NAME', 'Brazil'))
    return None

collection_estados = get_feature_collection('estados')
collection_municipios = get_feature_collection('municipios')


# --- Funções de Processamento de Dados (Otimizadas e com Cache) ---
# As funções agora recebem 'info' do dataset para serem genéricas
# O ROI é convertido para JSON para ser 'hasheável' pelo cache do Streamlit

@st.cache_data
def get_annual_precipitation(_info, roi_json, start_year, end_year):
    """Calcula a precipitação anual média para um dado dataset, ROI e período."""
    roi = ee.Geometry(roi_json)
    collection = ee.ImageCollection(_info['id']).select(_info['band'])
    scale = _info.get('scale', SCALE)
    years = ee.List.sequence(start_year, end_year)

    def calculate_annual(year):
        start_date = ee.Date.fromYMD(year, 1, 1)
        end_date = start_date.advance(1, 'year')
        
        total_precip_image = collection.filterDate(start_date, end_date) \
                                     .map(lambda img: img.multiply(_info['multiplier'])) \
                                     .sum()
                                     
        mean_value = total_precip_image.reduceRegion(
            reducer=ee.Reducer.sum(),
            geometry=roi,
            scale=scale,
            maxPixels=1e12
        ).get(_info['band'])
        return ee.Feature(None, {'year': year, 'precip': mean_value})

    annual_means_fc = ee.FeatureCollection(years.map(calculate_annual))
    data = annual_means_fc.getInfo()['features']
    rows = [f['properties'] for f in data]
    return pd.DataFrame(rows)

@st.cache_data
def get_monthly_climatology(_info, roi_json, start_year, end_year):
    """Calcula a climatologia mensal para um dado dataset, ROI e período."""
    roi = ee.Geometry(roi_json)
    collection = ee.ImageCollection(_info['id']).select(_info['band'])
    scale = _info.get('scale', SCALE)
    months = ee.List.sequence(1, 12)
    num_years = end_year - start_year + 1

    def calculate_monthly(m):
        monthly_collection = collection.filter(ee.Filter.calendarRange(start_year, end_year, 'year')) \
                                       .filter(ee.Filter.calendarRange(m, m, 'month'))
        
        total_precip = monthly_collection.map(lambda img: img.multiply(_info['multiplier'])).sum()
        mean_monthly_precip = total_precip.divide(num_years)
        
        mean_value = mean_monthly_precip.reduceRegion(
            reducer=ee.Reducer.mean(),
            geometry=roi,
            scale=scale,
            maxPixels=1e12
        ).get(_info['band'])
        return ee.Feature(None, {'month': m, 'precip': mean_value})

    monthly_means_fc = ee.FeatureCollection(months.map(calculate_monthly))
    data = monthly_means_fc.getInfo()['features']
    rows = [f['properties'] for f in data]
    df = pd.DataFrame(rows)
    df['month_name'] = df['month'].apply(lambda x: datetime(2023, x, 1).strftime('%b'))
    return df.sort_values(by='month').reset_index(drop=True)

@st.cache_data
def get_daily_precip(_info, roi_json, start_year, end_year):
    """Calcula a precipitação diária para um dado dataset, ROI e período."""
    roi = ee.Geometry(roi_json)
    scale = _info.get('scale', SCALE)
    
    start_date = ee.Date(f"{start_year}-01-01")
    end_date = ee.Date(f"{end_year}-12-31")

    daily_collection = ee.ImageCollection(_info['id']) \
                        .select(_info['band']) \
                        .filterDate(start_date, end_date) \
                        .filterBounds(roi)

    def daily_sum(img):
        # A soma total diária já considera o multiplicador
        total = img.multiply(_info['multiplier']).reduceRegion(
            reducer=ee.Reducer.sum(),
            geometry=roi,
            scale=scale,
            maxPixels=1e12
        ).get(_info['band'])
        
        date_str = img.date().format('YYYY-MM-dd')
        return ee.Feature(None, {'date': date_str, 'precip': total})

    fc = ee.FeatureCollection(daily_collection.map(daily_sum))
    data = fc.getInfo()['features']
    rows = [f['properties'] for f in data]
    
    df = pd.DataFrame(rows)
    df['date'] = pd.to_datetime(df['date'])
    df['precip'] = pd.to_numeric(df['precip'], errors='coerce')
    df = df.dropna(subset=['precip']).sort_values('date').reset_index(drop=True)
    return df

# --- Interface do Usuário (Sidebar) ---
st.sidebar.title("Configurações da Análise")

st.sidebar.header("1. Selecione o Dataset")
dataset_key = st.sidebar.selectbox(
    'Fonte de Dados de Precipitação:',
    list(DATASETS.keys()),
    index=0 # CHIRPS como padrão
)
info = DATASETS[dataset_key]
st.sidebar.write(f"**Fonte:** [{info['name']}]({info.get('url', '#')})")
st.sidebar.write(f"**Disponível desde:** {info['start_year']}")

st.sidebar.header("2. Selecione a Região")
tipo_analise = st.sidebar.radio(
    "Como deseja selecionar a área?",
    ('Por Divisão Política', 'Por Ponto (Lat/Lon)', 'Desenhar no Mapa'),
    key='tipo_analise'
)

roi = None
local_selecionado_nome = "Área de Interesse"

# Lógica para seleção de ROI (mantida do script original, com pequenas melhorias)
if tipo_analise == 'Por Divisão Política':
    tipo_divisao = st.sidebar.radio("Analisar por:", ('Município', 'Estado'))
    try:
        estados_info = collection_estados.aggregate_array('ADM1_NAME').getInfo()
        estados = sorted([estado for estado in estados_info if estado and estado != 'Name Unknown'])
        default_index = estados.index('Minas Gerais') if 'Minas Gerais' in estados else 0
        estado_selecionado = st.sidebar.selectbox("Escolha o Estado", estados, index=default_index)

        if tipo_divisao == 'Município':
            if estado_selecionado:
                with st.spinner("Carregando municípios..."):
                    municipios_filtrados = collection_municipios.filter(ee.Filter.eq('ADM1_NAME', estado_selecionado))
                    municipios = sorted(municipios_filtrados.aggregate_array('ADM2_NAME').getInfo())
                municipio_selecionado = st.sidebar.selectbox("Escolha o Município", municipios, index=0)
                if municipio_selecionado:
                    local_selecionado_nome = f"{municipio_selecionado}, {estado_selecionado}"
                    roi_fc = collection_municipios.filter(ee.Filter.And(
                        ee.Filter.eq('ADM1_NAME', estado_selecionado),
                        ee.Filter.eq('ADM2_NAME', municipio_selecionado)
                    ))
                    roi = roi_fc.geometry()
        else:
            local_selecionado_nome = estado_selecionado
            roi_fc = collection_estados.filter(ee.Filter.eq('ADM1_NAME', estado_selecionado))
            roi = roi_fc.geometry()

    except Exception as e:
        st.sidebar.error("Não foi possível carregar a lista de estados/municípios.")
        st.stop()

elif tipo_analise == 'Por Ponto (Lat/Lon)':
    lat = st.sidebar.number_input("Latitude", -90.0, 90.0, -19.92, format="%.4f")
    lon = st.sidebar.number_input("Longitude", -180.0, 180.0, -43.94, format="%.4f")
    buffer_radius = st.sidebar.number_input("Raio (em metros)", 100, 50000, 10000, step=1000)
    local_selecionado_nome = f"Ponto ({lat:.2f}, {lon:.2f}) com raio de {buffer_radius/1000:.1f} km"
    point = ee.Geometry.Point([lon, lat])
    roi = point.buffer(buffer_radius)

elif tipo_analise == 'Desenhar no Mapa':
    local_selecionado_nome = "Área Desenhada no Mapa"
    if 'drawn_geometry' in st.session_state and st.session_state.drawn_geometry:
        roi = ee.Geometry(st.session_state.drawn_geometry)

st.sidebar.header("3. Selecione o Período")
current_year = date.today().year
# O ano inicial agora depende do dataset selecionado
start_year = st.sidebar.slider("Ano Inicial", info['start_year'], current_year, info['start_year'])
end_year = st.sidebar.slider("Ano Final", info['start_year'], current_year, current_year - 1)

run_analysis = st.sidebar.button("📊 Gerar Análise", type="primary", use_container_width=True)

# --- LÓGICA DE EXIBIÇÃO PRINCIPAL ---
if not run_analysis:
    st.title(f"☔️ Análise de Precipitação - {dataset_key}")
    if tipo_analise == 'Desenhar no Mapa':
        st.info('ℹ️ Use as ferramentas no canto esquerdo do mapa para desenhar. Após desenhar, clique em "Gerar Análise".')
        m_draw = folium.Map(location=[-15, -55], zoom_start=4, tiles='cartodbdark_matter')
        Draw(export=False, position='topleft').add_to(m_draw)
        output = st_folium(m_draw, width='100%', height=600, returned_objects=['last_active_drawing'])
        
        if output and output.get("last_active_drawing"):
            geom = output["last_active_drawing"]["geometry"]
            if st.session_state.get('drawn_geometry') != geom:
                st.session_state.drawn_geometry = geom
                st.sidebar.success("✅ Área desenhada capturada!")
                st.rerun() # Atualiza para mostrar que a geometria foi capturada
    else:
        st.info("👈 Configure as opções na barra lateral e clique em 'Gerar Análise' para começar.")
    st.stop()

# --- SEÇÃO DE ANÁLISE E RESULTADOS (APÓS CLICAR NO BOTÃO) ---
if roi is None:
    st.error("❌ A região de interesse (ROI) não foi definida. Por favor, selecione uma opção válida.")
    st.stop()
if start_year >= end_year:
    st.error("❌ O ano inicial deve ser anterior ao ano final.")
    st.stop()

with st.spinner(f"Processando dados de '{dataset_key}' para '{local_selecionado_nome}'... Isso pode levar alguns minutos."):
    # Converte o ROI para JSON para que possa ser usado no cache
    roi_json = roi.getInfo() 
    df_annual = get_annual_precipitation(info, roi_json, start_year, end_year)
    df_monthly = get_monthly_climatology(info, roi_json, start_year, end_year)
    df_daily = get_daily_precip(info, roi_json, start_year, end_year)

st.header(f"📍 Resultados para: {local_selecionado_nome}")
st.subheader(f"Fonte de Dados: {info['name']}")

# Métricas principais
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

# Abas com os gráficos
tab1, tab2, tab3, tab4 = st.tabs(["🗺️ Mapa da Seleção", "📊 Série Anual", "📈 Climatologia Mensal", "📈 Série Diária"])

with tab1:
    st.subheader("Mapa da Região de Interesse")
    m_roi = geemap.Map()
    m_roi.centerObject(roi, 10)
    m_roi.addLayer(roi, {'color': '#007BFF', 'fillColor': '#007BFF50'}, 'Região de Interesse')
    m_roi.to_streamlit()

with tab2:
    st.subheader(f"Precipitação Anual Total ({start_year}-{end_year})")
    if not df_annual.empty and not df_annual['precip'].isnull().all():
        media_historica = df_annual['precip'].mean()
        df_annual['anomalia'] = df_annual['precip'] - media_historica
        df_annual['cor'] = df_annual['anomalia'].apply(lambda x: '#007BFF' if x >= 0 else '#FF4B4B')
        
        fig_annual = go.Figure()
        fig_annual.add_trace(go.Bar(x=df_annual['year'], y=df_annual['precip'], marker_color=df_annual['cor'], name='Precipitação Anual'))
        fig_annual.add_trace(go.Scatter(x=df_annual['year'], y=[media_historica] * len(df_annual), mode='lines', line=dict(color='yellow', dash='dash'), name=f'Média Histórica ({media_historica:.1f} mm)'))
        fig_annual.update_layout(title=f"Precipitação Anual e Anomalia em Relação à Média<br><b>{local_selecionado_nome}</b>", xaxis_title="Ano", yaxis_title="Precipitação Anual (mm)", template="plotly_dark")
        st.plotly_chart(fig_annual, use_container_width=True)
    else:
        st.warning("Não há dados anuais para o período selecionado.")

with tab3:
    st.subheader(f"Climatologia Mensal ({start_year}-{end_year})")
    if not df_monthly.empty and not df_monthly['precip'].isnull().all():
        fig_monthly = px.bar(df_monthly, x="month_name", y="precip", labels={"month_name": "Mês", "precip": "Precipitação Média (mm)"}, title=f"Precipitação Média Mensal (Climatologia)<br><b>{local_selecionado_nome}</b>")
        fig_monthly.update_traces(marker_color="#0384fc")
        fig_monthly.update_layout(template="plotly_dark", xaxis_title='Mês')
        st.plotly_chart(fig_monthly, use_container_width=True)
    else:
        st.warning("Não há dados mensais para o período selecionado.")

with tab4:
    st.subheader(f"Precipitação Diária ({start_year}-{end_year})")
    if not df_daily.empty and not df_daily['precip'].isnull().all():
        fig_daily = px.bar(df_daily, x="date", y="precip", labels={"date": "Data", "precip": "Precipitação (mm)"}, title=f"Precipitação Diária<br><b>{local_selecionado_nome}</b>", color_discrete_sequence=["#ffffff"])
        fig_daily.update_layout(template="plotly_dark", xaxis_title='Data', yaxis_title='Precipitação (mm)')
        st.plotly_chart(fig_daily, use_container_width=True)
    else:
        st.warning("Não há dados diários para o período selecionado.")
