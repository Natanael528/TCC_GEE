import streamlit as st
import ee
import geemap.foliumap as geemap 
import folium
from datetime import date, timedelta, datetime
import json
import tempfile
import pandas as pd
import altair as alt


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
    page_title='AquaGEE Analytics | Início',
    initial_sidebar_state='expanded',
    menu_items={
        'About': 'Aplicativo desenvolvido por Natanael Silva Oliveira para o TCC de Ciências Atmosféricas - UNIFEI.',
        'Report a bug': 'mailto:natanaeloliveira2387@gmail.com'
    },
    page_icon='💧'
)

with open('style.css')as f:
    st.markdown(f"<style>{f.read()}</style>", unsafe_allow_html = True)


# --- CONFIGURAÇÕES DOS DADOS ---
PALETA_PRECIPITACAO = ['1621a2', '03ffff', '13ff03', 'efff00', 'ffb103', 'ff2300']

# Dicionário com informações detalhadas de cada fonte de dados
DATASETS = {
    'CHIRPS': {
        'id': 'UCSB-CHG/CHIRPS/DAILY',
        'id2': 'UCSB-CHG/CHIRPS/PENTAD',
        'band': 'precipitation',
        'band2': 'precipitation',
        'multiplier': 1,      # já vem em mm/dia
        'multiplier2': 1,     # já vem em mm/pentad
        'temp': False,
        'start_year': 1981,
        'scale': 5566,
        'name': 'CHIRPS',
        'type': 'daily',      # etiqueta para ajudar a função
    },
    'IMERG': {
        'id': 'NASA/GPM_L3/IMERG_V07',            # 30 min
        'id2': 'NASA/GPM_L3/IMERG_MONTHLY_V07',   # mensal
        'band': 'precipitation',
        'band2': 'precipitation',
        'multiplier': 0.5,    # 30 min → mm/24h (48 steps * 0.5 = 24h)
        'multiplier2': 1,     # 
        'temp': True,
        'start_year': 2000,
        'scale': 11132,
        'name': 'IMERG',
        'type': 'subdaily',
    },
    'GSMAP': {
        'id': 'JAXA/GPM_L3/GSMaP/v8/operational', # horário
        'id2': 'JAXA/GPM_L3/GSMaP/v8/operational',
        'band': 'hourlyPrecipRate',
        'band2': 'hourlyPrecipRate',
        'multiplier': 1,       # já em mm/h
        'multiplier2': 1,
        'temp': False,
        'start_year': 2000,
        'scale': 11132,
        'name': 'GSMaP',
        'type': 'hourly',
    },

}

# Ordem fixa para exibição dos mapas
DATASETS_PARA_COMPARAR = ['GSMAP', 'IMERG', 'CHIRPS']

# --- FUNÇÕES AUXILIARES ---

def desenhar_mapa_em_coluna(coluna, image, vis_params, titulo, legenda):
    """Renderiza um mapa geemap dentro de uma coluna específica do Streamlit."""
    with coluna:
        st.subheader(titulo)
        mapa = geemap.Map(center=[-19, -60], zoom=3, tiles='cartodbdark_matter')
        
        # Adiciona uma verificação para garantir que a imagem não está vazia
        try:
            # Pega o nome da banda do dicionário de visualização se possível, senão da imagem
            band_name = vis_params.get('bands', image.bandNames().get(0).getInfo())
            masked_image = image.select(band_name).updateMask(image.select(band_name).gt(vis_params['min']))
            mapa.addLayer(masked_image, vis_params, titulo)
            mapa.add_colorbar(vis_params, label=legenda, background_color='white')
        except Exception as e:
            st.warning(f"Pode não haver dados para o período selecionado.")
            
        mapa.to_streamlit(height=600)

def obter_soma_periodo(info, inicio, fim):
    colecao = ee.ImageCollection(info['id']).filterDate(inicio, fim).select(info['band'])

    # Casos especiais com coleção mensal/pentadal
    if 'id2' in info and (info['id2'] != info['id']) and (info['type'] in ['monthly', 'pentad']):
        colecao = ee.ImageCollection(info['id2']).filterDate(inicio, fim).select(info['band2'])
        return colecao.sum().multiply(info['multiplier2'])

    # IMERG: mm/h → mm/30min → mm/dia
    if info['name'] == "IMERG":
        colecao = colecao.map(lambda img: img.multiply(0.5))
        return colecao.sum()

    # GSMaP: já em mm/h → precisa multiplicar por 1h
    if info['name'] == "GSMaP":
        colecao = colecao.map(lambda img: img.multiply(1))
        return colecao.sum()

    # CHIRPS diário: já vem pronto em mm/dia
    if info['name'] == "CHIRPS":
        return colecao.sum()

    # fallback
    return colecao.sum().multiply(info['multiplier'])

def obter_series_temporais(info, escala, inicio_python, fim_python, geometry):
    """Retorna lista de dicts {'date':..., 'dataset':..., 'value':...} para o periodo e escala."""
    resultados = []
    try:
        if escala == "Diário":
            cur = inicio_python
            while cur <= fim_python:
                inicio = ee.Date(cur.strftime("%Y-%m-%d"))
                fim = inicio.advance(1, 'day')
                img = obter_soma_periodo(info, inicio, fim)
                rr = img.reduceRegion(ee.Reducer.mean(), geometry, info['scale']).getInfo()
                val = None
                if rr:
                    # pega o primeiro valor retornado
                    val = list(rr.values())[0]
                resultados.append({'date': cur.strftime("%Y-%m-%d"), 'dataset': info['name'], 'value': val or 0.0})
                cur += timedelta(days=1)

        elif escala == "Mensal":
            # inicio_python and fim_python are date objects representing first day of month (user provided)
            cur_year = inicio_python.year
            cur_month = inicio_python.month
            end_year = fim_python.year
            end_month = fim_python.month
            while (cur_year, cur_month) <= (end_year, end_month):
                inicio = ee.Date.fromYMD(cur_year, cur_month, 1)
                fim = inicio.advance(1, 'month')
                img = obter_soma_periodo(info, inicio, fim)
                rr = img.reduceRegion(ee.Reducer.mean(), geometry, info['scale']).getInfo()
                val = None
                if rr:
                    val = list(rr.values())[0]
                label = f"{cur_year}-{cur_month:02d}"
                resultados.append({'date': label, 'dataset': info['name'], 'value': val or 0.0})
                # advance month
                if cur_month == 12:
                    cur_month = 1
                    cur_year += 1
                else:
                    cur_month += 1

        elif escala == "Anual":
            for ano in range(inicio_python, fim_python + 1):
                inicio = ee.Date.fromYMD(ano, 1, 1)
                fim = inicio.advance(1, 'year')
                img = obter_soma_periodo(info, inicio, fim)
                rr = img.reduceRegion(ee.Reducer.mean(), geometry, info['scale']).getInfo()
                val = None
                if rr:
                    val = list(rr.values())[0]
                resultados.append({'date': str(ano), 'dataset': info['name'], 'value': val or 0.0})
    except Exception as e:
        # devolve resultados parciais e loga no streamlit
        st.warning(f"Erro ao gerar séries para {info['name']}: {e}")
    return resultados

# --- MODOS DE ANÁLISE (LÓGICA PRINCIPAL) ---

def processar_comparacao(modo, **kwargs):
    """Função central que busca os dados para os 3 datasets e os exibe em colunas."""
    st.header(f"Comparação de Precipitação - {modo}")

    col1, col2, col3 = st.columns(3)
    colunas = [col1, col2, col3]

    for i, nome_dataset in enumerate(DATASETS_PARA_COMPARAR):
        info = DATASETS[nome_dataset]
        
        try:
            if modo == "Diário":
                data_sel = kwargs['data_sel']

                inicio = ee.Date(data_sel.strftime("%Y-%m-%d"))
                fim = inicio.advance(1, 'day')
                img = obter_soma_periodo(info, inicio, fim)
                vis = {'min': 1, 'max': 50, 'palette': PALETA_PRECIPITACAO}
                legenda = "Precipitação [mm/dia]"

            elif modo == "Mensal":
                ano, mes_idx, meses = kwargs['ano'], kwargs['mes_idx'], kwargs['meses']

                inicio = ee.Date.fromYMD(ano, mes_idx, 1)
                fim = inicio.advance(1, 'month')
                img = obter_soma_periodo(info, inicio, fim)
                vis = {'min': 50, 'max': 600, 'palette': PALETA_PRECIPITACAO}
                legenda = "Precipitação [mm/mês]"

            elif modo == "Anual":
                ano = kwargs['ano']
                
                inicio = f"{ano}-01-01"
                fim = f"{ano}-12-31"
                img = obter_soma_periodo(info, inicio, fim)
                vis = {'min': 200, 'max': 3000, 'palette': PALETA_PRECIPITACAO}
                legenda = "Precipitação [mm/ano]"

            else:
                st.error("Modo de análise desconhecido.")
                return

            desenhar_mapa_em_coluna(colunas[i], img, vis, info['name'], legenda)
        
        except Exception as e:
            with colunas[i]:
                st.subheader(info['name'])
                st.error(f"Ocorreu um erro ao processar os dados para {info['name']}: {e}")

# --- INTERFACE DO USUÁRIO (SIDEBAR) ---
st.sidebar.title('Menu de Comparação')
st.sidebar.info("Selecione a escala temporal e o período. Os mapas das bases de dados GSMAP, CHIRPS e IMERG serão exibidos lado a lado.")

# nova opção: escolha entre Mapas e Gráfico
visualizacao = st.sidebar.radio("Visualização:", ["Mapas", "Gráfico"])

modos = {'Diário': 'Diário', 'Mensal': 'Mensal', 'Anual': 'Anual'}

# modo_selecionado = st.sidebar.radio(
#     "Escolha a Escala Temporal:",
#     list(modos.keys())
# )

st.sidebar.header("Filtros de Período")

# O ano mínimo deve ser o da base mais antiga (CHIRPS: 1981)
ANO_INICIAL_GLOBAL = min(d['start_year'] for d in DATASETS.values())
ANO_ATUAL = date.today().year

# # inputs de localização para o gráfico (ponto + raio)
# st.sidebar.markdown("### Local para séries (para gráfico)")
# lat = st.sidebar.number_input("Latitude", value=-19.0, format="%.6f")
# lon = st.sidebar.number_input("Longitude", value=-60.0, format="%.6f")
# raio_km = st.sidebar.number_input("Raio (km)", value=10, min_value=1)

# botão unificado
if visualizacao == "Mapas":
    modo_selecionado = st.sidebar.radio(
    "Escolha a Escala Temporal:",
    list(modos.keys())
)
    if modo_selecionado == "Diário":
        data_selecionada = st.sidebar.date_input(
            "Data",
            max_value=date.today() - timedelta(days=1),
            value=date.today() - timedelta(days=2)
        )
        if st.sidebar.button("Gerar Mapas", use_container_width=True):
            processar_comparacao("Diário", data_sel=data_selecionada)

    elif modo_selecionado == "Mensal":
        mes_passado = date.today().replace(day=1) - timedelta(days=1)
        
        ano_selecionado = st.sidebar.selectbox("Ano", range(ANO_INICIAL_GLOBAL, ANO_ATUAL + 1), index=range(ANO_INICIAL_GLOBAL, ANO_ATUAL + 1).index(mes_passado.year))
        
        meses_nomes = ["Janeiro","Fevereiro","Março","Abril","Maio","Junho",
                       "Julho","Agosto","Setembro","Outubro","Novembro","Dezembro"]
        mes_selecionado_idx = st.sidebar.selectbox("Mês", range(1,13), format_func=lambda m: meses_nomes[m-1], index=mes_passado.month-1)
        
        if st.sidebar.button("Gerar Mapas", use_container_width=True):
            processar_comparacao("Mensal", ano=ano_selecionado, mes_idx=mes_selecionado_idx, meses=meses_nomes)

    elif modo_selecionado == "Anual":
        ultimo_ano_completo = ANO_ATUAL - 1
        ano_selecionado = st.sidebar.selectbox("Ano", range(ANO_INICIAL_GLOBAL, ultimo_ano_completo + 1), index=range(ANO_INICIAL_GLOBAL, ultimo_ano_completo + 1).index(ultimo_ano_completo))
        if st.sidebar.button("Gerar Mapas", use_container_width=True):
            processar_comparacao("Anual", ano=ano_selecionado)
            st.sidebar.warning('Atenção: alguns plots podem demorar um pouco para carregar devido ao volume de dados anual.')

else:  # Gráfico
    modo_selecionado = st.sidebar.radio( "Escolha a Escala Temporal:",('Diário', 'Mensal'))

    # inputs de período para gerar séries temporais
    
    # inputs de localização para o gráfico (ponto + raio)
    st.sidebar.markdown("### Local para séries (para gráfico)")
    lat = st.sidebar.number_input("Latitude", value=-22.424808, format="%.6f")
    lon = st.sidebar.number_input("Longitude", value=-45.462025, format="%.6f")
    raio_km = st.sidebar.number_input("Raio (km)", value=10, min_value=1)
    

    
    if modo_selecionado == "Diário":
        start_date = st.sidebar.date_input("Data inicial", value=date.today() - timedelta(days=2), max_value=date.today() - timedelta(days=1))
        end_date = st.sidebar.date_input("Data final", value=date.today() - timedelta(days=1), min_value=start_date, max_value=date.today() - timedelta(days=1))
    elif modo_selecionado == "Mensal":
        meses_nomes = ["Janeiro","Fevereiro","Março","Abril","Maio","Junho",
                       "Julho","Agosto","Setembro","Outubro","Novembro","Dezembro"]
        start_year = st.sidebar.selectbox("Ano início", range(ANO_INICIAL_GLOBAL, ANO_ATUAL + 1), index=0)
        start_month = st.sidebar.selectbox("Mês início", range(1,13), format_func=lambda m: meses_nomes[m-1], index=0)
        end_year = st.sidebar.selectbox("Ano fim", range(ANO_INICIAL_GLOBAL, ANO_ATUAL + 1), index=min(5, ANO_ATUAL-ANO_INICIAL_GLOBAL))
        end_month = st.sidebar.selectbox("Mês fim", range(1,13), format_func=lambda m: meses_nomes[m-1], index=11)
        # constrói datas Python representando primeiro dia dos meses
        start_date = date(start_year, start_month, 1)
        end_date = date(end_year, end_month, 1)
        
    else:  # Anual
        start_year = st.sidebar.selectbox("Ano início", range(ANO_INICIAL_GLOBAL, ANO_ATUAL), index=0)
        end_year = st.sidebar.selectbox("Ano fim", range(ANO_INICIAL_GLOBAL, ANO_ATUAL), index=min(5, ANO_ATUAL-ANO_INICIAL_GLOBAL-1))
        start_date = start_year
        end_date = end_year

    if st.sidebar.button("Gerar Gráfico", use_container_width=True):
        # constrói geometry
        geom = ee.Geometry.Point([float(lon), float(lat)]).buffer(int(raio_km) * 1000)
        todas_series = []
        with st.spinner("Gerando séries... isso pode demorar conforme o tamanho do período"):
            for nome_dataset in DATASETS_PARA_COMPARAR:
                info = DATASETS[nome_dataset]
                series = obter_series_temporais(info, modo_selecionado, start_date, end_date, geom)
                todas_series.extend(series)

        if not todas_series:
            st.error("Nenhum dado retornado para o período/posição selecionados.")
        else:
            df = pd.DataFrame(todas_series)
            # converter coluna date para datetime conforme escala
            if modo_selecionado == "Diário":
                df['date'] = pd.to_datetime(df['date'])
            elif modo_selecionado == "Mensal":
                df['date'] = pd.to_datetime(df['date'] + "-01")
            else:
                # anual: usa primeiro dia do ano
                df['date'] = pd.to_datetime(df['date'] + "-01-01")


            titulo_grafico = f"Série Temporal de Precipitação ({modo_selecionado})"
            selecao_legenda = alt.selection_point(fields=['dataset'], bind='legend')

            chart = alt.Chart(df).mark_line(
                strokeWidth=2, # Linha mais grossa
                point={'filled': False, 'fill': 'white', 'size': 40}
            ).encode(
                # Eixo X (Data)
                x=alt.X('date:T', title='Período', axis=alt.Axis(format='%d/%m/%Y')),
                
                # Eixo Y (Precipitação)
                y=alt.Y('value:Q', title='Precipitação (mm)', axis=alt.Axis(format='.1f')),
                
                # Cor baseada na fonte de dados (traduzido)
                color=alt.Color('dataset:N', title='Fonte de Dados'),
                
                # Opacidade ligada à seleção da legenda
                opacity=alt.condition(selecao_legenda, alt.value(1.0), alt.value(0.2)),
                
                # Tooltip (caixa de informação) traduzido e formatado
                tooltip=[
                    alt.Tooltip('dataset:N', title='Fonte'),
                    alt.Tooltip('date:T', title='Data', format='%d/%m/%Y'),
                    alt.Tooltip('value:Q', title='Precip. (mm)', format='.2f')
                ]
            ).add_selection(
                selecao_legenda
            ).properties(
                title=titulo_grafico,
                height=500
            ).configure_title(
                fontSize=20,
                anchor='start'
            ).configure_legend(
                orient='bottom', # Move a legenda para baixo
                titleFontSize=14,
                labelFontSize=12
            ).interactive() # Habilita zoom e pan

            # --- Exibição no Streamlit ---
            st.header(f"Comparação Gráfica - {modo_selecionado}")
            st.altair_chart(chart, use_container_width=True)
