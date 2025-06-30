import streamlit as st
import ee
import geemap.foliumap as geemap  # Importa o backend correto para Streamlit
from datetime import date, timedelta

# --- CONFIGURAÇÃO DA PÁGINA STREAMLIT ---
# Define a configuração da página para um layout amplo e adiciona metadados.
st.set_page_config(
    layout='wide',
    page_title='Análise de Chuva GEE',
    initial_sidebar_state='expanded',
    menu_items={
        'About': 'Aplicativo desenvolvido por Natanael Silva Oliveira para o projeto de TCC do curso de Ciências Atmosféricas da Universidade Federal de Itajubá - UNIFEI.',
        'Report a bug': 'mailto:natanaeloliveira2387@gmail.com'
    },
    page_icon='🌧️'
)

# --- INICIALIZAÇÃO DO GOOGLE EARTH ENGINE ---
# É crucial inicializar o GEE no início do script.
# Em um ambiente de produção do Streamlit Cloud, as credenciais devem ser
# configuradas como segredos (secrets).
try:
    ee.Initialize()
except Exception as e:
    st.error("Falha ao inicializar o Google Earth Engine. Verifique suas credenciais.")
    st.stop()

# --- GERENCIAMENTO DE ESTADO DA SESSÃO ---
# Inicializa as variáveis no st.session_state se elas não existirem.
# Isso é essencial para manter os dados entre as execuções do script no Streamlit.
if 'drawn_geometry' not in st.session_state:
    st.session_state['drawn_geometry'] = None
if 'precipitation_result' not in st.session_state:
    st.session_state['precipitation_result'] = None


# --- CARREGAMENTO E PROCESSAMENTO DE DADOS GEE ---
# Define o intervalo de datas para buscar a imagem mais recente.
datain = date.today() - timedelta(days=1)
datafi = date.today()

with open('style.css')as f:
    st.markdown(f"<style>{f.read()}</style>", unsafe_allow_html = True)

# Carrega a coleção de imagens GPM, filtra por data e ordena para obter a mais recente.
dataset = ee.ImageCollection('NASA/GPM_L3/IMERG_V07') \
           .filterDate(datain.strftime('%Y-%m-%d'), datafi.strftime('%Y-%m-%d')) \
           .sort('system:time_start', False)

# Seleciona a imagem mais recente da coleção.
ultima_imagem = dataset.first()
# Seleciona a banda de interesse ('precipitation').
precipitation = ultima_imagem.select('precipitation')

# Obtém a data da imagem para exibição.
data_ultima_imagem = ee.Date(ultima_imagem.get('system:time_start')) \
                       .format('YYYY-MM-dd HH:mm').getInfo()

st.title("Análise de Precipitação Instantânea (GPM)")
st.write(f"Visualizando a última imagem disponível em **{data_ultima_imagem}** (UTC).")
st.markdown("---")

# --- LAYOUT DA APLICAÇÃO ---
# Divide a interface em duas colunas para melhor organização.
col1, col2 = st.columns()

with col1:
    # --- CRIAÇÃO E EXIBIÇÃO DO MAPA INTERATIVO ---
    # Instancia o mapa usando geemap.foliumap.
    Map = geemap.Map(center=[-15, -55], zoom=4, tiles='cartodbdark_matter')

    # Define os parâmetros de visualização para a camada de precipitação.
    precipitationVis = {
        'min': 1,
        'max': 30.0,
        'palette': ['1621a2', '03ffff', '13ff03', 'efff00', 'ffb103', 'ff2300']
    }

    # Adiciona a camada de precipitação ao mapa, com uma máscara para valores > 0.5 mm/h.
    Map.addLayer(precipitation.updateMask(precipitation.gt(0.5)),
                 precipitationVis, 'Precipitação Horária', opacity=1)

    # Adiciona a barra de cores ao mapa.
    Map.add_colorbar(precipitationVis, label='Precipitação [mm/h]')

    # Renderiza o mapa no Streamlit e captura as interações do usuário.
    # O dicionário 'output' contém o estado do mapa no cliente.
    output = Map.to_streamlit(height=700)

    # Atualiza o estado da sessão com a geometria desenhada mais recente.
    if output and output.get("last_active_drawing"):
        st.session_state['drawn_geometry'] = output["last_active_drawing"]
        # Limpa o resultado anterior quando um novo desenho é feito.
        st.session_state['precipitation_result'] = None

with col2:
    st.subheader("Controles de Análise")
    st.write("Use as ferramentas de desenho no mapa (canto superior esquerdo) para selecionar uma área e clique no botão abaixo.")

    # --- LÓGICA DO BOTÃO DE ANÁLISE ---
    if st.button('Analisar Área Selecionada'):
        # Verifica se uma geometria foi desenhada e está no estado da sessão.
        if st.session_state['drawn_geometry']:
            with st.spinner('Calculando a precipitação média...'):
                try:
                    # Converte o dicionário GeoJSON do frontend para um objeto ee.Geometry.
                    coords = st.session_state['drawn_geometry']['geometry']['coordinates']
                    roi_ee = ee.Geometry.Polygon(coords)

                    # Executa a análise zonal usando reduceRegion.
                    stats = precipitation.reduceRegion(
                        reducer=ee.Reducer.mean(),
                        geometry=roi_ee,
                        scale=10000,  # Resolução em metros, apropriada para GPM.
                        crs='EPSG:4326',
                        bestEffort=True # Garante que a análise funcione para áreas grandes.
                    ).getInfo()

                    # Extrai o resultado e armazena no estado da sessão.
                    precip_value = stats.get('precipitation')
                    st.session_state['precipitation_result'] = precip_value

                except Exception as e:
                    st.error(f"Ocorreu um erro durante a análise: {e}")
                    st.session_state['precipitation_result'] = "Erro"
        else:
            st.warning('Nenhuma área foi desenhada. Por favor, selecione uma região no mapa.')

    # --- EXIBIÇÃO DOS RESULTADOS ---
    st.markdown("---")
    st.subheader("Resultado")

    if st.session_state['precipitation_result'] is not None:
        if isinstance(st.session_state['precipitation_result'], (int, float)):
            st.metric(
                label="Precipitação Média na Área",
                value=f"{st.session_state['precipitation_result']:.2f} mm/h"
            )
            st.success("Cálculo concluído com sucesso!")
        elif st.session_state['precipitation_result'] == "Erro":
            st.error("Não foi possível calcular o valor.")
        else:
            # Caso em que o valor é None dentro da área (sem precipitação)
            st.metric(
                label="Precipitação Média na Área",
                value="0.00 mm/h"
            )
            st.info("Nenhuma precipitação significativa detectada na área selecionada.")
    else:
        st.info("Aguardando análise...")