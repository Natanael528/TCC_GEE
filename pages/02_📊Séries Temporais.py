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

# # --- Constantes e Coleções do GEE ---
# EE_COLLECTION = 'UCSB-CHG/CHIRPS/PENTAD'
# SCALE = 5566

# @st.cache_data
# def get_feature_collection(name):
#     if name == 'estados':
#         return ee.FeatureCollection('FAO/GAUL/2015/level1').filter(ee.Filter.eq('ADM0_NAME', 'Brazil'))
#     elif name == 'municipios':
#         return ee.FeatureCollection('FAO/GAUL/2015/level2').filter(ee.Filter.eq('ADM0_NAME', 'Brazil'))
#     return None

# collection_estados = get_feature_collection('estados')
# collection_municipios = get_feature_collection('municipios')

# # --- Funções de Processamento de Dados (Otimizadas) ---
# def get_annual_precipitation(collection, roi, start_year, end_year):
#     years = ee.List.sequence(start_year, end_year)
#     def calculate_annual(year):
#         start_date = ee.Date.fromYMD(year, 1, 1)
#         end_date = start_date.advance(1, 'year')
#         total_precip_image = collection.filterDate(start_date, end_date).sum()
#         mean_value = total_precip_image.reduceRegion(
#             reducer=ee.Reducer.mean(), geometry=roi, scale=SCALE, maxPixels=1e12
#         ).get('precipitation')
#         return ee.Feature(None, {'year': year, 'precip': mean_value})
#     annual_means_fc = ee.FeatureCollection(years.map(calculate_annual))
#     data = annual_means_fc.getInfo()['features']
#     rows = [f['properties'] for f in data]
#     return pd.DataFrame(rows)

# def get_monthly_climatology(collection, roi, start_year, end_year):
#     months = ee.List.sequence(1, 12)
#     num_years = end_year - start_year + 1
#     def calculate_monthly(m):
#         monthly_collection = collection.filter(ee.Filter.calendarRange(m, m, 'month'))
#         total_precip = monthly_collection.sum()
#         mean_monthly_precip = total_precip.divide(num_years)
#         mean_value = mean_monthly_precip.reduceRegion(
#             reducer=ee.Reducer.mean(), geometry=roi, scale=SCALE, maxPixels=1e12
#         ).get('precipitation')
#         return ee.Feature(None, {'month': m, 'precip': mean_value})
#     monthly_means_fc = ee.FeatureCollection(months.map(calculate_monthly))
#     data = monthly_means_fc.getInfo()['features']
#     rows = [f['properties'] for f in data]
#     df = pd.DataFrame(rows)
#     df['month_name'] = df['month'].apply(lambda x: datetime(2023, x, 1).strftime('%b'))
#     return df.sort_values(by='month').reset_index(drop=True)

# def get_daily_precip(collection, roi, start_year, end_year):
#     # Define intervalo de datas
#     start_date = ee.Date(f"{start_year}-01-01")
#     end_date = ee.Date(f"{end_year}-12-31")
    
#     # Filtra coleção
#     daily_collection = collection.filterDate(start_date, end_date).filterBounds(roi)
    
#     # Reduz região para cada imagem
#     def daily_sum(img):
#         total = img.reduceRegion(
#             reducer=ee.Reducer.sum(),
#             geometry=roi,
#             scale=SCALE,
#             maxPixels=1e12
#         ).get('precipitation')
#         date = img.date().format('YYYY-MM-dd')
#         return ee.Feature(None, {'date': date, 'precip': total})
    
#     # Aplica função e converte para lista
#     fc = ee.FeatureCollection(daily_collection.map(daily_sum))
#     data = fc.getInfo()['features']
#     rows = [f['properties'] for f in data]

#     # Converte para DataFrame
#     df = pd.DataFrame(rows)
#     df['date'] = pd.to_datetime(df['date'])
#     df['precip'] = pd.to_numeric(df['precip'], errors='coerce')
#     df = df.dropna(subset=['precip']).sort_values('date').reset_index(drop=True)
#     return df




# # --- Interface do Usuário (Sidebar) ---
# st.sidebar.header("1. Selecione a Região")
# tipo_analise = st.sidebar.radio("Como deseja selecionar a área?", ('Por Divisão Política', 'Por Ponto (Lat/Lon)', 'Desenhar no Mapa'), key='tipo_analise')

# roi = None
# local_selecionado_nome = "Área de Interesse"

# if tipo_analise == 'Por Divisão Política':
#     tipo_divisao = st.sidebar.radio("Analisar por:", ('Município', 'Estado'))
#     try:
#         estados_info = collection_estados.aggregate_array('ADM1_NAME').getInfo()
#         estados = sorted([estado for estado in estados_info if estado and estado != 'Name Unknown'])
#         default_index = estados.index('Minas Gerais') if 'Minas Gerais' in estados else 0
#         estado_selecionado = st.sidebar.selectbox("Escolha o Estado", estados, index=default_index)

#         if tipo_divisao == 'Município':
#             if estado_selecionado:
#                 with st.spinner("Carregando municípios..."):
#                     municipios_filtrados = collection_municipios.filter(ee.Filter.eq('ADM1_NAME', estado_selecionado))
#                     municipios = sorted(municipios_filtrados.aggregate_array('ADM2_NAME').getInfo())
#                 municipio_selecionado = st.sidebar.selectbox("Escolha o Município", municipios, index=0)
#                 if municipio_selecionado:
#                     local_selecionado_nome = f"{municipio_selecionado}, {estado_selecionado}"
#                     roi_fc = collection_municipios.filter(ee.Filter.And(ee.Filter.eq('ADM1_NAME', estado_selecionado), ee.Filter.eq('ADM2_NAME', municipio_selecionado)))
#                     roi = roi_fc.geometry()
#         else:
#             local_selecionado_nome = estado_selecionado
#             roi_fc = collection_estados.filter(ee.Filter.eq('ADM1_NAME', estado_selecionado))
#             roi = roi_fc.geometry()

#     except Exception as e:
#         st.sidebar.error("Não foi possível carregar a lista de estados/municípios.")
#         st.stop()

# elif tipo_analise == 'Por Ponto (Lat/Lon)':
#     st.sidebar.markdown("Digite as coordenadas e o raio.")
#     lat = st.sidebar.number_input("Latitude", -90.0, 90.0, -19.92, format="%.4f")
#     lon = st.sidebar.number_input("Longitude", -180.0, 180.0, -43.94, format="%.4f")
#     buffer_radius = st.sidebar.number_input("Raio (em metros)", 100, 50000, 10000, step=1000)
#     local_selecionado_nome = f"Ponto ({lat:.2f}, {lon:.2f}) com raio de {buffer_radius/1000:.1f} km"
#     point = ee.Geometry.Point([lon, lat])
#     roi = point.buffer(buffer_radius)

# if 'drawn_geometry' not in st.session_state:
#     st.session_state.drawn_geometry = None

# if tipo_analise == 'Desenhar no Mapa':
#     local_selecionado_nome = "Área Desenhada no Mapa"
#     if st.session_state.drawn_geometry:
#         roi = ee.Geometry(st.session_state.drawn_geometry)

# st.sidebar.divider()
# st.sidebar.header("2. Selecione o Período")
# current_year = date.today().year
# start_year = st.sidebar.slider("Ano Inicial", 1981, current_year, 1981)
# end_year = st.sidebar.slider("Ano Final", 1981, current_year, current_year - 1)

# run_analysis = st.sidebar.button("📊 Gerar Análise", type="primary", use_container_width=True)

# if run_analysis and tipo_analise == 'Desenhar no Mapa':
#     if st.sidebar.button("✏️ Desenhar Nova Área"):
#         st.session_state.drawn_geometry = None # Limpa a geometria anterior
#         st.rerun() # Reinicia o script para voltar à tela de desenho

# # --- LÓGICA DE EXIBIÇÃO PRINCIPAL ---

# if not run_analysis:
#     st.title("☔️ Análise de Precipitação Acumulada (CHIRPS)")
#     if tipo_analise == 'Desenhar no Mapa':
#         st.info('ℹ️ Use as ferramentas no canto superior esquerdo do mapa para desenhar um polígono, retângulo ou marcar um ponto. A última forma desenhada será utilizada. Após desenhar, clique em "Gerar Análise" na barra lateral.')
#         m_draw = folium.Map(location=[-15, -55], zoom_start=4, tiles='openstreetmap')
#         Draw(export=False, position='topleft').add_to(m_draw)
#         output = st_folium(m_draw, width='100%', height=600, returned_objects=['last_active_drawing'])
#         if output and output.get("last_active_drawing"):
#             if st.session_state.drawn_geometry != output["last_active_drawing"]["geometry"]:
#                  st.session_state.drawn_geometry = output["last_active_drawing"]["geometry"]
#                  st.sidebar.success("✅ Área desenhada capturada!")
#     else:
#         st.info("👈 Configure as opções na barra lateral e clique em 'Gerar Análise' para começar.")
#     st.stop()

# # --- SEÇÃO DE ANÁLISE E RESULTADOS ---

# if roi is None:
#     st.error("❌ A região de interesse (ROI) não foi definida. Por favor, selecione uma opção válida ou desenhe uma área no mapa.")
#     st.stop()
# if start_year >= end_year:
#     st.error("❌ O ano inicial deve ser anterior ao ano final.")
#     st.stop()

# with st.spinner(f"Processando dados para '{local_selecionado_nome}'... Isso pode levar alguns minutos."):
    
#     precip_collection = ee.ImageCollection(EE_COLLECTION).select('precipitation').filterDate(f"{start_year}-01-01", f"{end_year}-12-31").filterBounds(roi)
#     precip_day = (ee.ImageCollection("UCSB-CHG/CHIRPS/DAILY").select('precipitation').filterDate(f"{start_year}-01-01", f"{end_year}-12-31").filterBounds(roi))
    
#     df_annual = get_annual_precipitation(precip_collection, roi, start_year, end_year)
#     df_monthly = get_monthly_climatology(precip_collection, roi, start_year, end_year)
#     df_daily = get_daily_precip(precip_day, roi, start_year, end_year)


# st.header(f"📍 Resultados para: {local_selecionado_nome}")

# if not df_annual.empty and 'precip' in df_annual.columns:
#     media_anual = df_annual['precip'].mean()
#     ano_mais_chuvoso = df_annual.loc[df_annual['precip'].idxmax()]
#     ano_menos_chuvoso = df_annual.loc[df_annual['precip'].idxmin()]
#     col1, col2, col3 = st.columns(3)
#     col1.metric("Precipitação Média Anual", f"{media_anual:.1f} mm")
#     col2.metric("Ano Mais Chuvoso", f"{int(ano_mais_chuvoso['year'])} ({ano_mais_chuvoso['precip']:.1f} mm)")
#     col3.metric("Ano Menos Chuvoso", f"{int(ano_menos_chuvoso['year'])} ({ano_menos_chuvoso['precip']:.1f} mm)")
# else:
#     st.warning("Não foi possível calcular as métricas anuais.")

# tab1, tab2, tab3, tab4 = st.tabs(["🗺️ Mapa da Seleção", "📈 Climatologia Diária", "📈 Climatologia Mensal", "📊 Série Anual"])

# with tab1:
#     st.subheader("Mapa da Região de Interesse")
#     m_roi = geemap.Map(center=[-15, -55], zoom=4)
#     m_roi.centerObject(roi, 10)
#     m_roi.addLayer(roi, {'color': '#007BFF', 'fillColor': '#007BFF50'}, 'Região de Interesse')
#     m_roi.to_streamlit()

# with tab4:
#     st.subheader(f"Precipitação Anual Total ({start_year}-{end_year})")
#     if not df_annual.empty and not df_annual['precip'].isnull().all():
#         media_historica = df_annual['precip'].mean()
#         df_annual['anomalia'] = df_annual['precip'] - media_historica
#         df_annual['cor'] = df_annual['anomalia'].apply(lambda x: '#007BFF' if x > 0 else '#FF4B4B')
#         fig_annual = go.Figure()
#         fig_annual.add_trace(go.Bar(x=df_annual['year'], y=df_annual['precip'], marker_color=df_annual['cor'], name='Precipitação Anual'))
#         fig_annual.add_trace(go.Scatter(x=df_annual['year'], y=[media_historica] * len(df_annual), mode='lines', line=dict(color='yellow', dash='dash'), name=f'Média Histórica ({media_historica:.1f} mm)'))
#         fig_annual.update_layout(title=f"Precipitação Anual e Anomalia em Relação à Média<br><b>{local_selecionado_nome}</b>", xaxis_title="Ano", yaxis_title="Precipitação Anual Acumulada (mm)", template="plotly_white")
#         st.plotly_chart(fig_annual, use_container_width=True)
#     else:
#         st.warning("Não há dados anuais para o período selecionado.")

# with tab3:
#     st.subheader(f"Climatologia Mensal ({start_year}-{end_year})")
#     if not df_monthly.empty and not df_monthly['precip'].isnull().all():
#         fig_monthly = px.bar(df_monthly, x="month_name", y="precip", labels={"month_name": "Mês", "precip": "Precipitação Média Mensal (mm)"}, title=f"Precipitação Média Mensal (Climatologia)<br><b>{local_selecionado_nome}</b>")
#         fig_monthly.update_traces(marker_color="#0384fc")
#         fig_monthly.update_layout(template="plotly_white", xaxis_title='Mês')
#         st.plotly_chart(fig_monthly, use_container_width=True)
#     else:
#         st.warning("Não há dados mensais para o período selecionado.")

# with tab2:
#     st.subheader(f"Precipitação Diária ({start_year}-{end_year})")
    
#     if not df_daily.empty and not df_daily['precip'].isnull().all():
#         # Cria o gráfico diário
#         fig_daily = px.bar(
#             df_daily,
#             x="date",
#             y="precip",
#             labels={"date": "Data", "precip": "Precipitação Diária (mm)"},
#             title=f"Precipitação Diária ({start_year}-{end_year})<br><b>{local_selecionado_nome}</b>",
#             color_discrete_sequence=["#0384fc"]
#         )

#         # Atualiza layout
#         fig_daily.update_layout(
#             template="plotly_white",
#             xaxis_title='Data',
#             yaxis_title='Precipitação (mm)',
#             xaxis=dict(
#                 tickformat="%d-%b-%Y",
#                 tickangle=-45
#             )
#         )

#         st.plotly_chart(fig_daily, use_container_width=True)
#     else:
#         st.warning("Não há dados diários para o período selecionado.")


        
# --- Constantes e Coleções do GEE ---
EE_COLLECTION = 'UCSB-CHG/CHIRPS/PENTAD'
SCALE = 5566

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
            reducer=ee.Reducer.mean(), geometry=roi, scale=SCALE, maxPixels=1e12 ##########################
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
            reducer=ee.Reducer.mean(), geometry=roi, scale=SCALE, maxPixels=1e12 #################
        ).get('precipitation')
        return ee.Feature(None, {'month': m, 'precip': mean_value})
    monthly_means_fc = ee.FeatureCollection(months.map(calculate_monthly))
    data = monthly_means_fc.getInfo()['features']
    rows = [f['properties'] for f in data]
    df = pd.DataFrame(rows)
    df['month_name'] = df['month'].apply(lambda x: datetime(2023, x, 1).strftime('%b'))
    return df.sort_values(by='month').reset_index(drop=True)


def get_monthly_total_series(collection, roi, start_year, end_year):
    """Calcula a precipitação total para cada mês no período selecionado."""
    years = ee.List.sequence(start_year, end_year)
    months = ee.List.sequence(1, 12)

    def map_months_over_years(year):
        def map_years_over_months(month):
            start_date = ee.Date.fromYMD(year, month, 1)
            end_date = start_date.advance(1, 'month')
            total_precip_image = collection.filterDate(start_date, end_date).sum()
            mean_value = total_precip_image.reduceRegion(
                reducer=ee.Reducer.mean(), geometry=roi, scale=SCALE, maxPixels=1e12 #############
            ).get('precipitation')
            return ee.Feature(None, {'date': start_date.format('YYYY-MM'), 'precip': mean_value})
        return months.map(map_years_over_months)

    monthly_fc = ee.FeatureCollection(years.map(map_months_over_years).flatten())
    data = monthly_fc.getInfo()['features']
    rows = [f['properties'] for f in data]
    df = pd.DataFrame(rows)
    
    if not df.empty:
        df['date'] = pd.to_datetime(df['date'])
        df = df.dropna(subset=['precip']).sort_values('date').reset_index(drop=True)
        # Garante que os dados estão dentro do período selecionado
        start_date_pd = pd.to_datetime(f"{start_year}-01-01")
        end_date_pd = pd.to_datetime(f"{end_year}-12-31")
        df = df[(df['date'] >= start_date_pd) & (df['date'] <= end_date_pd)]
    return df


def get_daily_precip(collection, roi, start_year, end_year):
    start_date = ee.Date(f"{start_year}-01-01")
    end_date = ee.Date(f"{end_year}-12-31")

    daily_collection = collection.filterDate(start_date, end_date).filterBounds(roi)

    # Usando getRegion em vez de map+getInfo
    data = daily_collection.getRegion(roi, SCALE).getInfo()

    # A tabela vem com metadados, precisamos filtrar
    header = data[0]
    rows = data[1:]
    df = pd.DataFrame(rows, columns=header)

    # Pega apenas data e precipitação
    df = df[['time', 'precipitation']].dropna()
    df['date'] = pd.to_datetime(df['time'], unit='ms')
    df.rename(columns={'precipitation': 'precip'}, inplace=True)
    df['precip'] = pd.to_numeric(df['precip'], errors='coerce')
    df = df.dropna(subset=['precip']).sort_values('date').reset_index(drop=True)

    return df




# --- Interface do Usuário (Sidebar) ---
st.sidebar.header("1. Selecione a Região")
tipo_analise = st.sidebar.radio("Como deseja selecionar a área?", ('Por Divisão Política', 'Por Ponto (Lat/Lon)', 'Desenhar no Mapa'), key='tipo_analise')

roi = None
local_selecionado_nome = "Área de Interesse"

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
                    roi_fc = collection_municipios.filter(ee.Filter.And(ee.Filter.eq('ADM1_NAME', estado_selecionado), ee.Filter.eq('ADM2_NAME', municipio_selecionado)))
                    roi = roi_fc.geometry()
        else:
            local_selecionado_nome = estado_selecionado
            roi_fc = collection_estados.filter(ee.Filter.eq('ADM1_NAME', estado_selecionado))
            roi = roi_fc.geometry()

    except Exception as e:
        st.sidebar.error("Não foi possível carregar a lista de estados/municípios.")
        st.stop()

elif tipo_analise == 'Por Ponto (Lat/Lon)':
    st.sidebar.markdown("Digite as coordenadas e o raio.")
    lat = st.sidebar.number_input("Latitude", -90.0, 90.0, -19.92, format="%.4f")
    lon = st.sidebar.number_input("Longitude", -180.0, 180.0, -43.94, format="%.4f")
    buffer_radius = st.sidebar.number_input("Raio (em metros)", 100, 50000, 10000, step=1000)
    local_selecionado_nome = f"Ponto ({lat:.2f}, {lon:.2f}) com raio de {buffer_radius/1000:.1f} km"
    point = ee.Geometry.Point([lon, lat])
    roi = point.buffer(buffer_radius)

if 'drawn_geometry' not in st.session_state:
    st.session_state.drawn_geometry = None

if tipo_analise == 'Desenhar no Mapa':
    local_selecionado_nome = "Área Desenhada no Mapa"
    if st.session_state.drawn_geometry:
        roi = ee.Geometry(st.session_state.drawn_geometry)

st.sidebar.divider()
st.sidebar.header("2. Selecione o Período")
current_year = date.today().year
start_year = st.sidebar.slider("Ano Inicial", 1981, current_year, 1981)
end_year = st.sidebar.slider("Ano Final", 1981, current_year, current_year - 1)

run_analysis = st.sidebar.button("📊 Gerar Análise", type="primary", use_container_width=True)

if run_analysis and tipo_analise == 'Desenhar no Mapa':
    if st.sidebar.button("✏️ Desenhar Nova Área"):
        st.session_state.drawn_geometry = None # Limpa a geometria anterior
        st.rerun() # Reinicia o script para voltar à tela de desenho

# --- LÓGICA DE EXIBIÇÃO PRINCIPAL ---

if not run_analysis:
    st.title("☔️ Análise de Precipitação Acumulada (CHIRPS)")
    if tipo_analise == 'Desenhar no Mapa':
        st.info('ℹ️ Use as ferramentas no canto superior esquerdo do mapa para desenhar um polígono, retângulo ou marcar um ponto. A última forma desenhada será utilizada. Após desenhar, clique em "Gerar Análise" na barra lateral.')
        m_draw = folium.Map(location=[-15, -55], zoom_start=4, tiles='openstreetmap')
        Draw(export=False, position='topleft').add_to(m_draw)
        output = st_folium(m_draw, width='100%', height=600, returned_objects=['last_active_drawing'])
        if output and output.get("last_active_drawing"):
            if st.session_state.drawn_geometry != output["last_active_drawing"]["geometry"]:
                   st.session_state.drawn_geometry = output["last_active_drawing"]["geometry"]
                   st.sidebar.success("✅ Área desenhada capturada!")
    else:
        st.info("👈 Configure as opções na barra lateral e clique em 'Gerar Análise' para começar.")
    st.stop()

# --- SEÇÃO DE ANÁLISE E RESULTADOS ---

if roi is None:
    st.error("❌ A região de interesse (ROI) não foi definida. Por favor, selecione uma opção válida ou desenhe uma área no mapa.")
    st.stop()
if start_year >= end_year:
    st.error("❌ O ano inicial deve ser anterior ao ano final.")
    st.stop()

with st.spinner(f"Processando dados para '{local_selecionado_nome}'... Isso pode levar alguns minutos."):
    
    precip_collection = ee.ImageCollection(EE_COLLECTION).select('precipitation').filterDate(f"{start_year}-01-01", f"{end_year}-12-31").filterBounds(roi)
    precip_day = (ee.ImageCollection("UCSB-CHG/CHIRPS/DAILY").select('precipitation').filterDate(f"{start_year}-01-01", f"{end_year}-12-31").filterBounds(roi))
    
    df_annual = get_annual_precipitation(precip_collection, roi, start_year, end_year)
    df_monthly_climatology = get_monthly_climatology(precip_collection, roi, start_year, end_year)
    # <<< NOVA CHAMADA DE FUNÇÃO >>>
    df_monthly_series = get_monthly_total_series(precip_collection, roi, start_year, end_year)
    df_daily = get_daily_precip(precip_day, roi, start_year, end_year)


st.header(f"📍 Resultados para: {local_selecionado_nome}")

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

# <<< NOVA ABA ADICIONADA AQUI >>>
tab1, tab2, tab3, tab4, tab5 = st.tabs(["🗺️ Mapa da Seleção", "📈 Série Diária", "📈 Série Mensal", "📉 Climatologia Mensal", "📊 Série Anual"])

with tab1:
    st.subheader("Mapa da Região de Interesse")
    m_roi = geemap.Map(center=[-15, -55], zoom=4)
    m_roi.centerObject(roi, 10)
    m_roi.addLayer(roi, {'color': '#007BFF', 'fillColor': '#007BFF50'}, 'Região de Interesse')
    m_roi.to_streamlit()

with tab2:
    st.subheader(f"Precipitação Diária ({start_year}-{end_year})")
    if not df_daily.empty and not df_daily['precip'].isnull().all():
        fig_daily = px.bar(
            df_daily, x="date", y="precip",
            labels={"date": "Data", "precip": "Precipitação Diária (mm)"},
            title=f"Precipitação Diária ({start_year}-{end_year})<br><b>{local_selecionado_nome}</b>",
            color_discrete_sequence=["#0384fc"]
        )
        fig_daily.update_layout(
            template="plotly_white", xaxis_title='Data', yaxis_title='Precipitação (mm)',
            xaxis=dict(tickformat="%d-%b-%Y", tickangle=-45)
        )
        st.plotly_chart(fig_daily, use_container_width=True)
    else:
        st.warning("Não há dados diários para o período selecionado.")

# <<< NOVA SEÇÃO DE PLOTAGEM PARA A SÉRIE MENSAL >>>
with tab3:
    st.subheader(f"Precipitação Mensal Total ({start_year}-{end_year})")
    if not df_monthly_series.empty and not df_monthly_series['precip'].isnull().all():
        fig_monthly_series = px.bar(
            df_monthly_series, x='date', y='precip',
            labels={'date': 'Mês', 'precip': 'Precipitação Mensal Total (mm)'},
            title=f"Série Temporal de Precipitação Mensal<br><b>{local_selecionado_nome}</b>"
        )
        # # Adiciona uma linha de média móvel para visualizar tendências
        # df_monthly_series['rolling_avg'] = df_monthly_series['precip'].rolling(window=12, center=True, min_periods=1).mean()
        # fig_monthly_series.add_trace(go.Scatter(
        #     x=df_monthly_series['date'], y=df_monthly_series['rolling_avg'], 
        #     mode='lines', line=dict(color='red', dash='dash'), 
        #     name='Média Móvel (12m)'
        # ))
        fig_monthly_series.update_layout(
            template="plotly_white", xaxis_title='Data', yaxis_title='Precipitação (mm)',
            xaxis_tickformat='%b %Y' # Formato do eixo X: 'Jan 2023'
        )
        st.plotly_chart(fig_monthly_series, use_container_width=True)
    else:
        st.warning("Não há dados para a série mensal no período selecionado.")

with tab4:
    st.subheader(f"Climatologia Mensal ({start_year}-{end_year})")
    if not df_monthly_climatology.empty and not df_monthly_climatology['precip'].isnull().all():
        fig_monthly = px.bar(df_monthly_climatology, x="month_name", y="precip", labels={"month_name": "Mês", "precip": "Precipitação Média Mensal (mm)"}, title=f"Precipitação Média Mensal (Climatologia)<br><b>{local_selecionado_nome}</b>")
        fig_monthly.update_traces(marker_color="#0384fc")
        fig_monthly.update_layout(template="plotly_white", xaxis_title='Mês')
        st.plotly_chart(fig_monthly, use_container_width=True)
    else:
        st.warning("Não há dados mensais para o período selecionado.")

with tab5:
    st.subheader(f"Precipitação Anual Total ({start_year}-{end_year})")
    if not df_annual.empty and not df_annual['precip'].isnull().all():
        media_historica = df_annual['precip'].mean()
        df_annual['anomalia'] = df_annual['precip'] - media_historica
        df_annual['cor'] = df_annual['anomalia'].apply(lambda x: '#007BFF' if x > 0 else '#FF4B4B')
        fig_annual = go.Figure()
        fig_annual.add_trace(go.Bar(x=df_annual['year'], y=df_annual['precip'], marker_color=df_annual['cor'], name='Precipitação Anual'))
        fig_annual.add_trace(go.Scatter(x=df_annual['year'], y=[media_historica] * len(df_annual), mode='lines', line=dict(color='yellow', dash='dash'), name=f'Média Histórica ({media_historica:.1f} mm)'))
        fig_annual.update_layout(title=f"Precipitação Anual e Anomalia em Relação à Média<br><b>{local_selecionado_nome}</b>", xaxis_title="Ano", yaxis_title="Precipitação Anual Acumulada (mm)", template="plotly_white")
        st.plotly_chart(fig_annual, use_container_width=True)
    else:
        st.warning("Não há dados anuais para o período selecionado.")