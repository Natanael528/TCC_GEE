# ...existing code...
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
try:
    service_account_info = dict(st.secrets["earthengine"])
    with tempfile.NamedTemporaryFile(mode='w+', suffix='.json', delete=False) as f:
        json.dump(service_account_info, f)
        f.flush()
        credentials = ee.ServiceAccountCredentials(service_account_info["client_email"], f.name)
        ee.Initialize(credentials)
except Exception as e:
    st.error("Ocorreu um erro na autenticação com o Google Earth Engine. Verifique suas credenciais.")
    st.error(f"Detalhes do erro: {e}")
    st.stop()

# --- Configuração da Página do Streamlit ---
st.set_page_config(
    layout='wide',
    page_title='AquaGEE Analytics | Início',
    initial_sidebar_state='expanded',
    menu_items={
        'About': 'Aplicativo desenvolvido por Natanael Silva Oliveira para o TCC de Ciências Atmosféricas - UNIFEI.',
        'Report a bug': 'mailto:natanaeloliveira2387@gmail.com'
    },
    page_icon='💧'
)

# Estilo CSS (opcional)
try:
    with open('style.css') as f:
        st.markdown(f"<style>{f.read()}</style>", unsafe_allow_html=True)
except FileNotFoundError:
    pass

# --- Dicionário de Datasets e Constantes ---
PALETA_PRECIPITACAO = ['#FFFFFF', '#00FFFF', '#0000FF', '#00FF00', '#FFFF00', '#FF0000', '#800000']

DATASETS = {
    'CHIRPS': {
        'id': 'UCSB-CHG/CHIRPS/DAILY',
        'id2': 'UCSB-CHG/CHIRPS/PENTAD',
        'band': 'precipitation',
        'multiplier': 1, # Unidade já é mm/dia
        'scale': 5566,
        'start_year': 1981,
        'name': 'CHIRPS',
    },
    'IMERG': {
        'id': 'NASA/GPM_L3/IMERG_V07',
        'id2': 'NASA/GPM_L3/IMERG_V07',
        'band': 'precipitation',
        'multiplier': 0.5,
        'scale': 11132,
        'start_year': 2000,
        'name': 'IMERG',
    },
    'GSMaP': {
        'id': 'JAXA/GPM_L3/GSMaP/v8/operational',
        'id2': 'JAXA/GPM_L3/GSMaP/v8/operational',
        'band': 'hourlyPrecipRate',
        'multiplier': 1,
        'scale': 11132,
        'start_year': 2000,
        'name': 'GSMaP',
    },
}

# --- Coleções de Features (Divisões Políticas) ---
@st.cache_data
def get_feature_collection(name):
    if name == 'estados':
        return ee.FeatureCollection('FAO/GAUL/2015/level1').filter(ee.Filter.eq('ADM0_NAME', 'Brazil'))
    elif name == 'municipios':
        return ee.FeatureCollection('FAO/GAUL/2015/level2').filter(ee.Filter.eq('ADM0_NAME', 'Brazil'))
    return None

collection_estados = get_feature_collection('estados')
collection_municipios = get_feature_collection('municipios')

# ---------- Helpers robustos ----------
def _fc_to_df(fc):
    """Converte um ee.FeatureCollection (já calculado) em pandas.DataFrame de forma defensiva."""
    info = fc.getInfo()
    features = info.get('features', []) if isinstance(info, dict) else []
    rows = [f.get('properties', {}) for f in features if f.get('properties') is not None]
    return pd.DataFrame(rows)

def _ensure_date_and_precip(df, band_name=None, multiplier=1):
    """Garante colunas 'date' (datetime) e 'precip' (float). Retorna df com essas colunas."""
    if df is None or df.empty:
        return pd.DataFrame(columns=['date', 'precip'])
    if 'date' in df.columns:
        df['date'] = pd.to_datetime(df['date'], errors='coerce')
    elif 'time' in df.columns:
        df['date'] = pd.to_datetime(df['time'], unit='ms', errors='coerce')
    elif 'year' in df.columns and 'month' in df.columns:
        df['date'] = pd.to_datetime(df['year'].astype(str) + '-' + df['month'].astype(str).str.zfill(2) + '-01', errors='coerce')
    else:
        df['date'] = pd.NaT

    if 'precip' in df.columns:
        df['precip'] = pd.to_numeric(df['precip'], errors='coerce')
    elif band_name and band_name in df.columns:
        df['precip'] = pd.to_numeric(df[band_name], errors='coerce') * multiplier
    else:
        numeric_cols = df.select_dtypes(include=['number']).columns.tolist()
        if numeric_cols:
            df['precip'] = pd.to_numeric(df[numeric_cols[0]], errors='coerce') * multiplier
        else:
            df['precip'] = pd.Series([pd.NA] * len(df), dtype='float64')

    df = df.dropna(subset=['precip']).sort_values('date').reset_index(drop=True)
    return df[['date', 'precip']]

# ---------- Função diária (robusta e sem getRegion) ----------
def get_daily_precip(collection, roi, start_year, end_year, band_name, scale, multiplier):
    """
    Calcula série diária reduzindo cada imagem sobre a ROI.
    Faz verificação do número de imagens e aborta (lança RuntimeError)
    se a coleção exceder o limite seguro de getInfo (5000).
    """
    start = ee.Date.fromYMD(start_year, 1, 1)
    end = ee.Date.fromYMD(end_year, 12, 31).advance(1, 'day')
    daily_coll = collection.filterDate(start, end).filterBounds(roi)

    # Verifica tamanho da coleção para evitar getInfo massivo
    n_images = daily_coll.size().getInfo()
    if n_images > 5000:
        raise RuntimeError(f"too_many_images: coleção diária tem {n_images} imagens (>5000)")

    def _per_image(img):
        img_band = img.select([band_name]).multiply(multiplier)
        date_str = ee.Date(img.get('system:time_start')).format('YYYY-MM-dd')
        val = img_band.reduceRegion(
            reducer=ee.Reducer.mean(),
            geometry=roi,
            scale=scale,
            maxPixels=1e13
        ).get(band_name)
        return ee.Feature(None, {'date': date_str, 'precip': val})

    daily_fc = daily_coll.map(_per_image)
    df = _fc_to_df(daily_fc)
    df = _ensure_date_and_precip(df, band_name=band_name, multiplier=multiplier)
    return df

# ---------- Série mensal (YYYY-MM) ----------
def get_monthly_total_series(collection, roi, start_year, end_year, band_name, scale, multiplier):
    years = list(range(start_year, end_year + 1))
    features = []
    for y in years:
        for m in range(1, 13):
            start = ee.Date.fromYMD(y, m, 1)
            end = start.advance(1, 'month')
            img_sum = collection.filterDate(start, end).sum().multiply(multiplier)
            mean_val = img_sum.reduceRegion(
                reducer=ee.Reducer.mean(), geometry=roi, scale=scale, maxPixels=1e13
            ).get(band_name)
            features.append(ee.Feature(None, {'date': start.format('YYYY-MM'), 'precip': mean_val}))
    monthly_fc = ee.FeatureCollection(features)
    df = _fc_to_df(monthly_fc)
    if 'date' in df.columns:
        df['date'] = pd.to_datetime(df['date'].astype(str) + '-01', errors='coerce')
    df = _ensure_date_and_precip(df, band_name=band_name, multiplier=multiplier)
    if not df.empty:
        start_pd = pd.to_datetime(f"{start_year}-01-01")
        end_pd = pd.to_datetime(f"{end_year}-12-31")
        df = df[(df['date'] >= start_pd) & (df['date'] <= end_pd)].reset_index(drop=True)
    return df

# ---------- Climatologia mensal (média do mês ao longo dos anos) ----------
def get_monthly_climatology(collection, roi, start_year, end_year, band_name, scale, multiplier):
    months = range(1, 13)
    features = []

    for m in months:
        # filtra só o mês m em todos os anos
        monthly_coll = collection.filter(ee.Filter.calendarRange(m, m, 'month'))

        # acumula precipitação dentro de cada mês/ano
        def month_sum(img):
            year = img.date().get('year')
            month_coll = collection.filterDate(
                ee.Date.fromYMD(year, m, 1),
                ee.Date.fromYMD(year, m, 1).advance(1, 'month')
            )
            return month_coll.sum().multiply(multiplier).set({'year': year, 'month': m})

        monthly_totals = monthly_coll.map(month_sum)

        # média interanual
        month_mean = monthly_totals.mean()

        mean_val = month_mean.reduceRegion(
            reducer=ee.Reducer.mean(),
            geometry=roi,
            scale=scale,
            maxPixels=1e13
        ).get(band_name)

        features.append(ee.Feature(None, {'month': m, 'precip': mean_val}))

    monthly_fc = ee.FeatureCollection(features)
    df = _fc_to_df(monthly_fc)
    if 'month' in df.columns:
        df['month'] = pd.to_numeric(df['month'], errors='coerce').astype('Int64')
        df['month_name'] = df['month'].apply(lambda x: datetime(2023, int(x), 1).strftime('%b') if pd.notna(x) else '')
    df['precip'] = pd.to_numeric(df.get('precip', pd.Series([], dtype=float)), errors='coerce')
    return df.sort_values('month').reset_index(drop=True)

# ---------- Precipitação anual ----------
def get_annual_precipitation(collection, roi, start_year, end_year, band_name, scale, multiplier):
    features = []
    for y in range(start_year, end_year + 1):
        start = ee.Date.fromYMD(y, 1, 1)
        end = start.advance(1, 'year')
        total = collection.filterDate(start, end).sum().multiply(multiplier)
        mean_val = total.reduceRegion(reducer=ee.Reducer.mean(), geometry=roi, scale=scale, maxPixels=1e13).get(band_name)
        features.append(ee.Feature(None, {'year': y, 'precip': mean_val}))
    annual_fc = ee.FeatureCollection(features)
    df = _fc_to_df(annual_fc)
    if 'year' in df.columns:
        df['year'] = pd.to_numeric(df['year'], errors='coerce').astype('Int64')
    df['precip'] = pd.to_numeric(df.get('precip', pd.Series([], dtype=float)), errors='coerce')
    return df.sort_values('year').reset_index(drop=True)

# --- Interface do Usuário (Sidebar) ---
st.sidebar.header("1. Selecione a Fonte de Dados")
dataset_name = st.sidebar.selectbox(
    "Escolha o dataset de precipitação",
    options=list(DATASETS.keys())
)
selected_dataset = DATASETS[dataset_name]

ee_collection_id_daily = selected_dataset['id']
ee_collection_id_agg = selected_dataset['id2']
band_name = selected_dataset['band']
dataset_scale = selected_dataset['scale']
dataset_start_year = selected_dataset['start_year']
dataset_multiplier = selected_dataset['multiplier']

st.sidebar.divider()

st.sidebar.header("2. Selecione a Região")
tipo_analise = st.sidebar.radio("Como deseja selecionar a área?", ('Por Divisão Política', 'Por Quadrado (Lat/Lon)', 'Por Ponto (Lat/Lon)', 'Desenhar no Mapa'), key='tipo_analise')

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
        st.sidebar.error(f"Não foi possível carregar a lista de estados/municípios. Erro: {e}")
        st.stop()

elif tipo_analise == 'Por Quadrado (Lat/Lon)':
    st.sidebar.markdown("Informe as coordenadas dos limites do quadrado/retângulo.")
    lat_min = st.sidebar.number_input("Latitude mínima (Sul)", -90.0, 90.0, -22.5, format="%.4f")
    lat_max = st.sidebar.number_input("Latitude máxima (Norte)", -90.0, 90.0, -22.35, format="%.4f")
    lon_min = st.sidebar.number_input("Longitude mínima (Oeste)", -180.0, 180.0, -45.55, format="%.4f")
    lon_max = st.sidebar.number_input("Longitude máxima (Leste)", -180.0, 180.0, -45.35, format="%.4f")

    # Cria retângulo no GEE
    roi = ee.Geometry.Rectangle([lon_min, lat_min, lon_max, lat_max])
    local_selecionado_nome = f"Quadrado: [{lat_min}, {lon_min}] até [{lat_max}, {lon_max}]"
        
        
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
    st.sidebar.markdown("ATENÇÃO: Áreas grandes podem demorar para processar.")
    local_selecionado_nome = "Área Desenhada no Mapa"
    if st.session_state.drawn_geometry:
        roi = ee.Geometry(st.session_state.drawn_geometry)

st.sidebar.divider()

st.sidebar.header("3. Selecione o Período")
current_year = date.today().year
start_year = st.sidebar.slider("Ano Inicial", dataset_start_year, current_year, dataset_start_year)
end_year = st.sidebar.slider("Ano Final", dataset_start_year, current_year, current_year - 1)
st.sidebar.markdown("CUIDADO: períodos muito longos podem levar a tempos de processamento elevados.")

run_analysis = st.sidebar.button("📊 Gerar Análise", type="primary", use_container_width=True)



# --- LÓGICA DE EXIBIÇÃO PRINCIPAL ---
st.title(f"☔️ Análise de Precipitação Acumulada ({selected_dataset['name']})")

if not run_analysis:
    if tipo_analise == 'Desenhar no Mapa':
        st.info('ℹ️ Use as ferramentas no canto superior esquerdo do mapa para desenhar sua área de interesse. A última forma desenhada será utilizada. Após desenhar, clique em "Gerar Análise" na barra lateral.')
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

with st.spinner(f"Processando dados de '{selected_dataset['name']}' para '{local_selecionado_nome}'... Isso pode levar alguns minutos."):
    try:
        date_filter = ee.Filter.date(f"{start_year}-01-01", f"{end_year}-12-31")
        
        precip_collection_agg = ee.ImageCollection(ee_collection_id_agg).select(band_name).filter(date_filter).filterBounds(roi)
        precip_collection_daily = ee.ImageCollection(ee_collection_id_daily).select(band_name).filter(date_filter).filterBounds(roi)
        
        df_annual = get_annual_precipitation(precip_collection_agg, roi, start_year, end_year, band_name, dataset_scale, dataset_multiplier)
        df_monthly_climatology = get_monthly_climatology(precip_collection_agg, roi, start_year, end_year, band_name, dataset_scale, dataset_multiplier)
        df_monthly_series = get_monthly_total_series(precip_collection_agg, roi, start_year, end_year, band_name, dataset_scale, dataset_multiplier)

        # --- Verifica tamanho da coleção diária antes de tentar processar ---
        daily_disabled = False
        df_daily = pd.DataFrame(columns=['date', 'precip'])
        try:
            n_images = precip_collection_daily.size().getInfo()
        except Exception as e:
            # Se não for possível obter tamanho, desativa diária por segurança
            n_images = None
            daily_disabled = True

        if n_images is not None and n_images > 5000:
            daily_disabled = True
            # st.warning(f"A coleção diária tem {n_images} imagens (>5000). Série diária desativada para evitar erro. Use a série mensal.")
        elif not daily_disabled:
            # coleção segura para série diária
            try:
                df_daily = get_daily_precip(precip_collection_daily, roi, start_year, end_year, band_name, dataset_scale, dataset_multiplier)
            except RuntimeError as e:
                # fallback: se a função detectar coleção grande internamente
                msg = str(e)
                if 'too_many_images' in msg or 'coleção diária' in msg:
                    daily_disabled = True
                    st.warning(f"Série diária desativada: {msg}. Usando série mensal como alternativa.")
                    df_daily = get_monthly_total_series(precip_collection_daily, roi, start_year, end_year, band_name, dataset_scale, dataset_multiplier)
                else:
                    raise
    except Exception as e:
        st.error("Ocorreu um erro ao processar os dados do Earth Engine. Verifique se a região de interesse é válida e tente novamente.")
        st.error(f"Detalhe do erro: {e}")
        st.stop()

st.header(f"📍 Resultados para: {local_selecionado_nome} | Fonte: {selected_dataset['name']}")

if not df_annual.empty and 'precip' in df_annual.columns and not df_annual['precip'].isnull().all():
    media_anual = df_annual['precip'].mean()
    ano_mais_chuvoso = df_annual.loc[df_annual['precip'].idxmax()]
    ano_menos_chuvoso = df_annual.loc[df_annual['precip'].idxmin()]
    col1, col2, col3 = st.columns(3)
    col1.metric("Precipitação Média Anual", f"{media_anual:.1f} mm")
    col2.metric("Ano Mais Chuvoso", f"{int(ano_mais_chuvoso['year'])} ({ano_mais_chuvoso['precip']:.1f} mm)")
    col3.metric("Ano Menos Chuvoso", f"{int(ano_menos_chuvoso['year'])} ({ano_menos_chuvoso['precip']:.1f} mm)")
else:
    st.warning("Não foi possível calcular as métricas anuais. Pode não haver dados para o período selecionado.")

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
        st.warning(f"A coleção diária tem {n_images} imagens (>5000). Série diária desativada para evitar erro. Use a série mensal.")

with tab3:
    st.subheader(f"Precipitação Mensal Total ({start_year}-{end_year})")
    if not df_monthly_series.empty and not df_monthly_series['precip'].isnull().all():
        fig_monthly_series = px.bar(
            df_monthly_series, x='date', y='precip',
            labels={'date': 'Mês', 'precip': 'Precipitação Mensal Total (mm)'},
            title=f"Série Temporal de Precipitação Mensal<br><b>{local_selecionado_nome}</b>"
        )
        fig_monthly_series.update_layout(
            template="plotly_white", xaxis_title='Data', yaxis_title='Precipitação (mm)',
            xaxis_tickformat='%b %Y'
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
        tab10, tab20, tab30, tab40 = st.columns(4)
        tab40.markdown("**Nota:** Barras azuis indicam anos com precipitação acima da média histórica, enquanto barras vermelhas indicam anos abaixo da média, a linha amarela representa a média histórica calculada pela média em relação ao período selecionado.")
    else:
        st.warning("Não há dados anuais para o período selecionado.")