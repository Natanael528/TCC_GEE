import streamlit as st
import ee
import geemap.foliumap as geemap
from datetime import date
import plotly.express as px
import pandas as pd
import json
import tempfile
# --- Configurações Iniciais e Autenticação ---

# Cria arquivo temporário com as credenciais
service_account_info = dict(st.secrets["earthengine"])

with tempfile.NamedTemporaryFile(mode='w+', suffix='.json', delete=False) as f:
    json.dump(service_account_info, f)
    f.flush()
    credentials = ee.ServiceAccountCredentials(service_account_info["client_email"], f.name)
    ee.Initialize(credentials)


st.set_page_config(
    layout='wide',
    page_title='Análise de Precipitação | GEE',
    initial_sidebar_state='expanded',
    menu_items={
        'About': 'Aplicativo desenvolvido por Natanael Silva Oliveira para o TCC de Ciências Atmosféricas - UNIFEI.',
        'Report a bug': 'mailto:natanaeloliveira2387@gmail.com'
    },
    page_icon='☔️'
)

with open('style.css')as f:
    st.markdown(f"<style>{f.read()}</style>", unsafe_allow_html = True)

EE_COLLECTION = 'UCSB-CHG/CHIRPS/PENTAD'


# Coleções vetoriais do GEE
collection_estados = ee.FeatureCollection('FAO/GAUL/2015/level1') \
    .filter(ee.Filter.eq('ADM0_NAME', 'Brazil'))

collection_municipios = ee.FeatureCollection('FAO/GAUL/2015/level2') \
    .filter(ee.Filter.eq('ADM0_NAME', 'Brazil'))

def get_annual_precipitation_data(collection, roi, start_year, end_year):
    years = ee.List.sequence(start_year, end_year)

    def calculate_annual_mean(year):
        year = ee.Number(year)
        start_date = ee.Date.fromYMD(year, 1, 1)
        end_date = start_date.advance(1, 'year')
        
        # Filtra a coleção para o ano e soma todas as imagens (pentadas)
        total_precip_image = collection.filterDate(start_date, end_date).sum()

        mean_value = total_precip_image.reduceRegion(
            reducer=ee.Reducer.mean(),
            geometry=roi,
            scale=10000, 
            maxPixels=1e9
        ).get('precipitation')

        return ee.Feature(None, {'year': year, 'precip': mean_value})

    annual_means_fc = ee.FeatureCollection(years.map(calculate_annual_mean))
    data = annual_means_fc.getInfo()
    rows = [f['properties'] for f in data['features']]
    return pd.DataFrame(rows)

def get_monthly_climatology_data(collection, roi, start_year, end_year):
    months = ee.List.sequence(1, 12)
    
    # MODIFICADO: A climatologia deve ser calculada sobre a média de vários anos
    def calculate_monthly_mean(m):
        m = ee.Number(m)
        # Filtra a coleção para um mês específico ao longo de todos os anos selecionados
        monthly_collection = collection.filter(ee.Filter.calendarRange(m, m, 'month'))
        
        # Calcula a precipitação média mensal para o período
        # Soma das precipitações do mês e divide pelo número de anos
        total_precip = monthly_collection.sum()
        num_years = ee.Number(end_year).subtract(start_year).add(1)
        mean_monthly_precip = total_precip.divide(num_years)

        mean_value = mean_monthly_precip.reduceRegion(
            reducer=ee.Reducer.mean(),
            geometry=roi,
            scale=10000,
            maxPixels=1e9
        ).get('precipitation')

        return ee.Feature(None, {'month': m, 'precip': mean_value})

    monthly_means_fc = ee.FeatureCollection(months.map(calculate_monthly_mean))
    data = monthly_means_fc.getInfo()
    rows = [f['properties'] for f in data['features']]
    df = pd.DataFrame(rows)
    # Mapeia o número do mês para o nome para melhor visualização no gráfico
    df['month_name'] = df['month'].apply(lambda x: pd.to_datetime(f'2023-{x}-01').strftime('%b'))
    return df.sort_values(by='month').reset_index(drop=True)

# --- Interface do Usuário ---

st.title("☔️ Análise de Precipitação Acumulada (CHIRPS)")
st.markdown("Use a barra lateral para selecionar a região e o período de interesse.")

st.sidebar.header("1. Seleção da Região")

# NOVO: Seletor para escolher o tipo de análise (Estado ou Município)
tipo_analise = st.sidebar.radio(
    "Analisar por:",
    ('Município', 'Estado'),
    key='tipo_analise'
)

# Inicializa variáveis para evitar erros
estado_selecionado = None
municipio_selecionado = None
local_selecionado_nome = None # NOVO: Variável para guardar o nome do local para títulos

# Obtém a lista de estados (operação que pode ser lenta, ideal fazer uma vez)
try:
    estados = sorted(collection_estados.aggregate_array('ADM1_NAME').getInfo())
except Exception as e:
    st.sidebar.error("Não foi possível carregar a lista de estados do GEE.")
    st.stop()


# MODIFICADO: Lógica condicional para exibir os seletores
if tipo_analise == 'Município':
    estado_selecionado = st.sidebar.selectbox("Escolha o Estado", estados, index=estados.index('Minas Gerais'))
    
    if estado_selecionado:
        with st.spinner("Carregando municípios..."):
            municipios_filtrados = collection_municipios.filter(
                ee.Filter.eq('ADM1_NAME', estado_selecionado)
            )
            municipios = sorted(municipios_filtrados.aggregate_array('ADM2_NAME').getInfo())
        municipio_selecionado = st.sidebar.selectbox("Escolha o Município", municipios)
        if municipio_selecionado:
            local_selecionado_nome = f"{municipio_selecionado}, {estado_selecionado}"

elif tipo_analise == 'Estado':
    estado_selecionado = st.sidebar.selectbox("Escolha o Estado", estados, index=estados.index('Minas Gerais'))
    if estado_selecionado:
        local_selecionado_nome = estado_selecionado


st.sidebar.header("2. Seleção do Período")
# Limita o range de datas disponíveis para o CHIRPS
start_date = st.sidebar.date_input("🗓️ Data inicial", date(2015, 1, 1), min_value=date(1981, 1, 1), max_value=date.today())
end_date = st.sidebar.date_input("🗓️ Data final", date.today(), min_value=date(1981, 1, 1), max_value=date.today())

st.sidebar.header("3. Executar")
run_analysis = st.sidebar.button("Gerar Análise", type="primary")

if run_analysis:
    # MODIFICADO: Verifica se um local válido foi selecionado
    if not local_selecionado_nome:
        st.error("Por favor, selecione uma região válida (Estado ou Município).")
    elif start_date >= end_date:
        st.error("A data inicial deve ser anterior à data final.")
    else:
        roi = None
        # MODIFICADO: Define a ROI com base na escolha do usuário
        if tipo_analise == 'Município' and municipio_selecionado:
            roi_fc = collection_municipios.filter(
                ee.Filter.And(
                    ee.Filter.eq('ADM1_NAME', estado_selecionado),
                    ee.Filter.eq('ADM2_NAME', municipio_selecionado)
                )
            )
            roi = roi_fc.geometry()
        
        elif tipo_analise == 'Estado' and estado_selecionado:
            roi_fc = collection_estados.filter(
                ee.Filter.eq('ADM1_NAME', estado_selecionado)
            )
            roi = roi_fc.geometry()

        # Filtra a coleção de imagens com base na data e na ROI
        precip_collection = ee.ImageCollection(EE_COLLECTION) \
            .select('precipitation') \
            .filterDate(start_date.strftime("%Y-%m-%d"), end_date.strftime("%Y-%m-%d")) \
            .filterBounds(roi)

        st.header(f"🗺️ Mapa de Localização: {local_selecionado_nome}")
        m_roi = geemap.Map(height=400, center_lon=-49, center_lat=-15, zoom=4)
        m_roi.centerObject(roi, 8)
        m_roi.addLayer(roi, {'color': 'yellow', 'fillColor': 'yellow_50'}, 'Região de Interesse')
        m_roi.to_streamlit()

        st.header("📊 Análise Gráfica da Precipitação")
        col1, col2 = st.columns(2)

        with col1:
            with st.spinner("Gerando gráfico anual..."):
                df_annual = get_annual_precipitation_data(precip_collection, roi, start_date.year, end_date.year)
                if df_annual.empty or df_annual['precip'].isnull().all():
                    st.warning("Não há dados anuais para o período selecionado.")
                else:
                    fig_annual = px.bar(
                        df_annual, x="year", y="precip",
                        labels={"year": "Ano", "precip": "Precipitação Anual Acumulada (mm)"},
                        title=f"Precipitação Anual Total para<br><b>{local_selecionado_nome}</b>"
                    )
                    fig_annual.update_traces(marker_color="#0384fc")
                    st.plotly_chart(fig_annual, use_container_width=True)

        with col2:
            with st.spinner("Gerando gráfico de climatologia mensal..."):
                df_monthly = get_monthly_climatology_data(precip_collection, roi, start_date.year, end_date.year)
                if df_monthly.empty or df_monthly['precip'].isnull().all():
                    st.warning("Não há dados mensais para o período selecionado.")
                else:
                    fig_monthly = px.line(
                        df_monthly, x="month_name", y="precip",
                        labels={"month_name": "Mês", "precip": "Precipitação Média Mensal (mm)"},
                        title=f"Climatologia Mensal ({start_date.year}-{end_date.year})<br><b>{local_selecionado_nome}</b>",
                        markers=True
                    )
                    fig_monthly.update_xaxes(title_text='Mês')
                    st.plotly_chart(fig_monthly, use_container_width=True)
else:
    st.info("👈 Selecione as opções na barra lateral e clique em 'Gerar Análise' para começar.")