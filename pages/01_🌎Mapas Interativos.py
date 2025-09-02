import streamlit as st
import ee
import geemap.foliumap as geemap 
import folium
from datetime import date, timedelta, datetime
import json
import tempfile

# Cria arquivo temporário com as credenciais
service_account_info = dict(st.secrets["earthengine"])

with tempfile.NamedTemporaryFile(mode='w+', suffix='.json', delete=False) as f:
    json.dump(service_account_info, f)
    f.flush()
    credentials = ee.ServiceAccountCredentials(service_account_info["client_email"], f.name)
    ee.Initialize(credentials)
    
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

# st.sidebar.title('Menu')

# dado = st.sidebar.selectbox('Escolha uma opção:', ['IMERG', 'CHIRPS','GSMAP'])
# Imerg = 'NASA/GPM_L3/IMERG_V07'
# Chirps = 'UCSB-CHG/CHIRPS/PENTAD'
# Gsmap = 'JAXA/GSMap/GSMAP'
# dados = {
#     'IMERG': Imerg,
#     'CHIRPS': Chirps,
#     'GSMAP': Gsmap
# }


# genre = st.sidebar.radio(
#     "Escolha a opção de precipitação:",
#     ["***Instantâneo***","***Diário***", "***Mensal***", "***Anual***"],
#     captions=[
#         "Imagens disponiveis.",
#         "Acumulado diário.",
#         "Acumulado mensal.",
#         "Acumulado anual.",
#     ],
# )

# if genre == "***Diário***":
#     # --- Barra Lateral ---
#     st.sidebar.header("Filtros")

#     data = st.sidebar.date_input("Data", max_value= date.today() -  timedelta(days=1))

#     data = data.strftime('%Y-%m-%d')

#     # dados de um dia específico
#     range = ee.Date(data).getRange('day')
    
    
#     # carregando os dados
#     imerge_30min = ee.ImageCollection(dados[dado]) \
#                     .filter(ee.Filter.date(range)) \
#                     .select('precipitation')

#     imerge_mes = imerge_30min.map(lambda img: img.multiply(0.5).copyProperties(img, img.propertyNames()))
#     # seleciona o máximo de precipitação
#     precipitation = imerge_mes.sum()

#     # mascara valores abaixo de 0.5 mm/h
#     mask = precipitation.gt(0.5)
#     precipitation = precipitation.updateMask(mask)

    
#     st.sidebar.write("Os dados de precipitação dessa opção são provenientes do Global Integrated Multi-satellite Retrievals for GPM (IMERG) e estão disponíveis a partir de 2000.")

#     # Configura a visualização
#     precipitationVis = {
#         'min': 1,
#         'max': 50.0,
#         'palette': ['1621a2','03ffff', '13ff03', 'efff00', 'ffb103', 'ff2300']}

#     st.write(f"Você selecionou o acumulado diário para a data **{data}**")
    
#     # Cria o mapa
#     Map = geemap.Map(center=[-19, -60], zoom=4, tiles='cartodbdark_matter')
#     Map.addLayer(precipitation, precipitationVis, 'Precipitação Horária', opacity=1)

#     Map.add_colorbar(precipitationVis, background_color='white', step= 20, label='Precipitação [mm/dia]')
#     Map.to_streamlit(width=1820, height=900)



# elif genre == "***Mensal***":
#     # --- Barra Lateral ---
#     st.sidebar.header("Filtros")
    
#     anos_disponiveis = list(range(2000, date.today().year + 1))

#     # 2. Crie o selectbox
#     ano = st.sidebar.selectbox(
#         "Selecione o ano:",
#         options=anos_disponiveis,
#         # Define o ano atual como padrão, encontrando seu índice na lista
#         index=anos_disponiveis.index(date.today().year) 
#     )

#     mes_nome = st.sidebar.selectbox("Selecione o mês:",
#         ["Janeiro", "Fevereiro", "Março", "Abril", "Maio", "Junho", 
#         "Julho", "Agosto", "Setembro", "Outubro", "Novembro", "Dezembro"],
#         index=date.today().month - 1 # Começa no mês atual
#     )

#     # --- Lógica Principal ---
#     # Converte o nome do mês para número (1 a 12)
#     mes_num = ["Janeiro", "Fevereiro", "Março", "Abril", "Maio", "Junho", 
#             "Julho", "Agosto", "Setembro", "Outubro", "Novembro", "Dezembro"].index(mes_nome) + 1
    
#     st.write("Você selecionou o acumulado mensal.  **{}** de **{}**".format(mes_nome, ano))


#     # Usa a abordagem robusta do GEE para definir o período
#     start_date = ee.Date.fromYMD(ano, mes_num, 1)
#     end_date = start_date.advance(1, 'month')

#     # Carrega a coleção de imagens GPM e filtra pelo intervalo de datas correto
#     dataset = ee.ImageCollection(dados[dado]) \
#         .filterDate(start_date, end_date) \
#         .select('precipitation')
        
    
#     st.sidebar.write("Os dados de precipitação dessa opção são provenientes do Global Integrated Multi-satellite Retrievals for GPM (IMERG) e estão disponíveis a partir de 2000.")


#     # transforma de mm/h para mm/0.5h
#     imerge_mes = dataset.map(lambda img: img.multiply(0.5).copyProperties(img, img.propertyNames()))
    
#     # soma a chuva do mês, ficando a unidade em mm/mês
#     imerge_mes = imerge_mes.sum()
    
#     # Ajusta a escala para um acumulado mensal em mm
#     precipitationVis = {
#         'min': 50.0,
#         'max': 600.0, # Um valor máximo realista para chuvas mensais
#         'palette': ['1621a2','03ffff', '13ff03', 'efff00', 'ffb103', 'ff2300']
#     }

#     # Cria o mapa, com um zoom mais afastado para a visualização global
#     Map = geemap.Map(center=[-19, -60], zoom=4, tiles='cartodbdark_matter')

#     # Adiciona a camada de precipitação mensal
#     Map.addLayer(
#         imerge_mes.updateMask(imerge_mes.gt(50)),  # Máscara para mostrar apenas áreas com mais de 50mm
#         precipitationVis, 
#         f'Precipitação {mes_nome}/{ano}'
#     )

#     # Adiciona a legenda com o rótulo e unidade corretos
#     Map.add_colorbar(
#         precipitationVis, 
#         label='Precipitação Acumulada [mm/mês]', 
#         orientation='vertical', 
#         layer_name=f'Precipitação {mes_nome}/{ano}',
#         background_color='white'
#     )
#     Map.to_streamlit(width=1820, height=900)


# elif genre == "***Anual***":

    

#     anos_disponiveis = list(range(1981, date.today().year + 1))

#     # 2. Crie o selectbox
#     ano = st.sidebar.selectbox(
#         "Selecione o ano:",
#         options=anos_disponiveis,
#         # Define o ano atual como padrão, encontrando seu índice na lista
#         index=anos_disponiveis.index(date.today().year) 
#     )

#     st.sidebar.markdown('Os dados de precipitação dessa opção são provenientes do Climate Hazards Center InfraRed Precipitation with Station data (CHIRPS) e estão disponíveis a partir de 1981.')

#     # --- Lógica Principal ---
#     # Define o período de interesse para o ano inteiro
#     datain = date(ano, 1, 1)
#     datafi = date(ano, 12, 31)

#     # Converte as datas para strings no formato 'YYYY-MM-DD' para o filtro do GEE
#     datain_str = datain.strftime('%Y-%m-%d')
#     datafi_str = datafi.strftime('%Y-%m-%d')

#     st.write("Você selecionou o acumulado anual, focado no Brasil para o ano de **{}**".format(ano))

#     # countries = ee.FeatureCollection('USDOS/LSIB_SIMPLE/2017')
#     # brazil = countries.filter(ee.Filter.eq('country_na', 'Brazil'))

#     # Carrega a coleção de imagens GPM e filtra por data
#     imerge_30min = ee.ImageCollection(dados[dado]) \
#         .filter(ee.Filter.date(datain_str, datafi_str))\

#     # Seleciona a banda de precipitação
#     precipitation_collection = imerge_30min.select('precipitation')

#     # Soma todas as imagens da coleção para obter o acumulado anual
#     annual_precipitation = precipitation_collection.sum()

#     # # **NOVA ETAPA:** Recorta a imagem de precipitação usando o limite do Brasil
#     brazil_precipitation = annual_precipitation#.clip(brazil)

#     # Ajusta os parâmetros de visualização para um acumulado anual (mm)
#     precipitationVis = {
#         'min': 0.0,
#         'max': 2500.0,
#         'palette': ['1621a2', '03ffff', '13ff03', 'efff00', 'ffb103', 'ff2300']
#     }

#     # Cria o mapa, centralizado no Brasil
#     Map = geemap.Map(center=[-15, -55], zoom=4, tiles='cartodbdark_matter')

#     # Adiciona a camada de precipitação anual recortada para o Brasil
#     # Usamos uma máscara para mostrar apenas áreas com mais de 200mm de chuva anual
#     Map.addLayer(
#         brazil_precipitation.updateMask(brazil_precipitation.gt(0)), 
#         precipitationVis, 
#         f'Precipitação Acumulada {ano} - Brasil'
#     )

#     # Adiciona a legenda com o rótulo e unidade corretos
#     Map.add_colorbar(
#         precipitationVis, 
#         label='Precipitação Acumulada [mm/ano]', 
#         orientation='vertical', 
#         layer_name=f'Precipitação Acumulada {ano} - Brasil',
#         background_color='white'
#     )
#     Map.to_streamlit(width=1820, height=900)
    
# else:

#     # Data inicial (3 dias atrás) e data final (hoje)
#     datain_padrao = date.today() - timedelta(days=3)
#     datafi_padrao = date.today() - timedelta(days=1)

#     # Entrada de data específica no sidebar
#     data_especifica = st.sidebar.date_input(
#         "Escolha uma data específica:",
#         value=datafi_padrao,
#         min_value=date(2000, 6, 1),
#         max_value=datafi_padrao
#     )

#     # Define intervalo: se escolher a data específica, busca apenas esse dia
#     if data_especifica:
#         datain = data_especifica
#         datafi = data_especifica + timedelta(days=1)
#     else:
#         datain = datain_padrao
#         datafi = datafi_padrao


#     ime_collection = ee.ImageCollection(dados[dado]) \
#         .filterDate(datain.strftime('%Y-%m-%d'), datafi.strftime('%Y-%m-%d') )

#     # Converte mm/h para mm/0.5h
#     dataset = ime_collection.map(lambda img: img.multiply(0.5).copyProperties(img, img.propertyNames()))

#     dataset_size = dataset.size().getInfo()

#     if dataset_size > 0:
#         # Ordena do mais recente para o mais antigo
#         dataset_sorted = dataset.sort('system:time_start', False)

#         # Lista de horários disponíveis
#         horarios = dataset_sorted.aggregate_array('system:time_start').getInfo()
#         horarios_formatados = [ee.Date(h).format('YYYY-MM-dd HH:mm').getInfo() for h in horarios]

#         # Mostra a última imagem disponível
#         ultima_imagem = dataset_sorted.first()
#         ultima_data = ee.Date(ultima_imagem.get('system:time_start')).format('YYYY-MM-dd HH:mm').getInfo()

#         st.write(f"Imagem disponível para: **{ultima_data} UTC**")

#         # Escolha de horário específico
#         horario_escolhido = st.sidebar.selectbox(
#             "Selecione um horário disponível:",
#             options=horarios_formatados,
#             index=0
#         )

#         # Filtra a imagem pelo horário escolhido
#         imagem_selecionada = dataset_sorted.filter(
#             ee.Filter.eq('system:time_start', horarios[horarios_formatados.index(horario_escolhido)])
#         ).first()

#         precipitation = imagem_selecionada.select('precipitation')

#         # Configura visualização
#         precipitationVis = {
#             'min': 1,
#             'max': 30.0,
#             'palette': ['1621a2', '03ffff', '13ff03', 'efff00', 'ffb103', 'ff2300']
#         }

#         st.sidebar.text("Dados: NASA GPM IMERG (0.1°, 30 min) desde 2000.")

#         # Cria mapa
#         Map = geemap.Map(center=[-19, -60], zoom=4, tiles='cartodbdark_matter')
#         Map.addLayer(precipitation.updateMask(precipitation.gt(0.5)),
#                     precipitationVis, 'Precipitação Horária', opacity=1)
#         Map.add_colorbar(precipitationVis, background_color='white', label='Precipitação [mm/h]')
#         Map.to_streamlit(width=1820, height=900)

#     else:
#         # Informa ao usuário que não foram encontrados dados
#         st.warning(f"Nenhum dado de precipitação encontrado no período de {datain.strftime('%d/%m/%Y')} a {datafi.strftime('%d/%m/%Y')}. Tente novamente mais tarde.")




# --- CONFIGURAÇÕES ---
PALETA_PRECIPITACAO = ['1621a2', '03ffff', '13ff03', 'efff00', 'ffb103', 'ff2300']

DATASETS = {
    'IMERG': {
        'id': 'NASA/GPM_L3/IMERG_V07',
        'band': 'precipitation',
        'multiplier': 0.5,
        'start_year': 2000,
        'name': 'NASA GPM IMERG',
    },
    'GSMAP': {
        'id': 'JAXA/GPM_L3/GSMaP/v8/operational',
        'band': 'hourlyPrecipRate',
        'multiplier': 1,
        'start_year': 2000,
        'name': 'JAXA GPM GSMaP',
    },
    'CHIRPS': {
        'id': 'UCSB-CHG/CHIRPS/DAILY',
        'band': 'precipitation',
        'multiplier': 1,
        'start_year': 1981,
        'name': 'UCSB-CHG CHIRPS',
    }
}

# --- FUNÇÕES AUXILIARES ---
def desenhar_mapa(image, vis_params, titulo, legenda):
    st.write(f"**Exibindo:** {titulo}")
    mapa = geemap.Map(center=[-19, -60], zoom=4, tiles='cartodbdark_matter')
    mapa.addLayer(image, vis_params, titulo)
    mapa.add_colorbar(vis_params, label=legenda,background_color='white')
    mapa.to_streamlit(width=1920, height=800)

def soma_periodo(info, inicio, fim):
    colecao = ee.ImageCollection(info['id']) \
        .filterDate(inicio, fim) \
        .select(info['band']) \
        .map(lambda img: img.multiply(info['multiplier']))
    return colecao.sum()

# --- MODOS DE ANÁLISE ---
def ultima_imagem(info):
    hoje = date.today()
    inicio = hoje - timedelta(days=30)  # buscar só nos últimos 30 dias
    colecao = ee.ImageCollection(info['id']) \
        .filterDate(str(inicio), str(hoje + timedelta(days=1))) \
        .sort('system:time_start', False)

    if colecao.size().getInfo() == 0:
        st.warning("Nenhuma imagem encontrada nos últimos 30 dias.")
        return

    img = colecao.first()
    data_img = ee.Date(img.get('system:time_start')).format('dd/MM/YYYY').getInfo()
    vis = {'min': 0, 'max': 50, 'palette': PALETA_PRECIPITACAO}

    desenhar_mapa(img.select(info['band']).updateMask(img.select(info['band']).gt(1)),
                  vis, f"Última Imagem - {data_img}", "Precipitação [mm]")

def acumulado_diario(info):
    st.sidebar.header("Filtros")

    hoje = date.today()
    inicio = hoje - timedelta(days=30)

    # Busca a última data com dados disponíveis nos últimos 30 dias
    colecao = ee.ImageCollection(info['id']) \
        .filterDate(str(inicio), str(hoje + timedelta(days=1))) \
        .sort('system:time_start', False)

    if colecao.size().getInfo() == 0:
        st.warning("Nenhum dado disponível nos últimos 30 dias.")
        return

    ultima_img = colecao.first()
    ultima_data = ee.Date(ultima_img.get('system:time_start')).format('YYYY-MM-dd').getInfo()
    ultima_data = date.fromisoformat(ultima_data)

    # Campo de seleção com a última data como padrão
    data_sel = st.sidebar.date_input(
        "Data",
        max_value=ultima_data,
        value=ultima_data
    )

    # Filtra novamente para o dia selecionado
    colecao_dia = ee.ImageCollection(info['id']) \
        .filterDate(str(data_sel), str(data_sel + timedelta(days=1))) \
        .select(info['band']) \
        .map(lambda img: img.multiply(info['multiplier']))

    if colecao_dia.size().getInfo() == 0:
        st.warning(f"Nenhum dado encontrado para {data_sel.strftime('%d/%m/%Y')}.")
        return

    img = colecao_dia.sum()
    vis = {'min': 1, 'max': 50, 'palette': PALETA_PRECIPITACAO}
    desenhar_mapa(
        img.updateMask(img.gt(0.5)),
        vis,
        f"Acumulado Diário - {data_sel.strftime('%d/%m/%Y')}",
        "Precipitação [mm/dia]"
    )

def acumulado_mensal(info):
    st.sidebar.header("Filtros")
    hoje = date.today()
    mes_passado = hoje.replace(day=1) - timedelta(days=1)

    ano = st.sidebar.selectbox("Ano", range(info['start_year'], hoje.year+1), index=mes_passado.year - info['start_year'])
    meses = ["Janeiro","Fevereiro","Março","Abril","Maio","Junho",
             "Julho","Agosto","Setembro","Outubro","Novembro","Dezembro"]
    mes_idx = st.sidebar.selectbox("Mês", range(1,13), format_func=lambda m: meses[m-1], index=mes_passado.month-1)

    inicio = ee.Date.fromYMD(ano, mes_idx, 1)
    fim = inicio.advance(1, 'month')
    img = soma_periodo(info, inicio, fim)
    vis = {'min': 50, 'max': 600, 'palette': PALETA_PRECIPITACAO}
    desenhar_mapa(img.updateMask(img.gt(50)),
                  vis, f"Acumulado Mensal - {meses[mes_idx-1]} {ano}", "Precipitação [mm/mês]")

def acumulado_anual(info):
    st.sidebar.header("Filtros")
    ultimo_ano = date.today().year - 1
    ano = st.sidebar.selectbox("Ano", range(info['start_year'], ultimo_ano+1), index=ultimo_ano - info['start_year'])
    img = soma_periodo(info, f"{ano}-01-01", f"{ano}-12-31")
    vis = {'min': 200, 'max': 2500, 'palette': PALETA_PRECIPITACAO}
    desenhar_mapa(img.updateMask(img.gt(200)),
                  vis, f"Acumulado Anual - {ano}", "Precipitação [mm/ano]")

# --- APP ---
st.sidebar.title('Menu')
dataset = st.sidebar.selectbox('Escolha o conjunto de dados:', list(DATASETS.keys()), index=2)
info = DATASETS[dataset]

modos = {
    "Última Imagem": ultima_imagem,
    "Acumulado Diário": acumulado_diario,
    "Acumulado Mensal": acumulado_mensal,
    "Acumulado Anual": acumulado_anual
}

modo_sel = st.sidebar.radio("Escala Temporal:", list(modos.keys()))
st.sidebar.write(f"**Fonte:** {info['name']} (desde {info['start_year']})")
modos[modo_sel](info)