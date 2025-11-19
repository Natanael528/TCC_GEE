
import streamlit as st
import ee
import geemap.foliumap as geemap
import json
import tempfile

# --- Configuração da Página e Estilo ---
st.set_page_config(
    layout='wide',
    page_title='AquaGEE Analytics | Início',
    initial_sidebar_state='collapsed',
    menu_items={
        'About': 'Aplicativo desenvolvido por Natanael Silva Oliveira para o TCC de Ciências Atmosféricas - UNIFEI.',
        'Report a bug': 'mailto:natanaeloliveira2387@gmail.com'
    },
    page_icon='💧'
)

# Carrega o estilo CSS personalizado
with open('style.css') as f:
    st.markdown(f"<style>{f.read()}</style>", unsafe_allow_html=True)

# --- Inicialização Segura do Google Earth Engine ---
# Este bloco é executado apenas uma vez e fica em cache para otimizar o desempenho.
@st.cache_resource
def initialize_gee():
    try:
        service_account_info = dict(st.secrets["earthengine"])
        with tempfile.NamedTemporaryFile(mode='w+', suffix='.json', delete=False) as f:
            json.dump(service_account_info, f)
            f.flush()
            credentials = ee.ServiceAccountCredentials(service_account_info["client_email"], f.name)
            # Use o project_id das credenciais para inicializar
            ee.Initialize(credentials, project=credentials.project_id)
            print("GEE Inicializado com sucesso.")
    except Exception as e:
        st.error("Ocorreu um erro ao inicializar o Google Earth Engine. Verifique as credenciais em st.secrets.")
        st.error(f"Detalhes do erro: {e}")
        st.stop()

initialize_gee()

# --- Função em Cache para Gerar o Mapa de Exemplo ---
# O cache de dados evita que o GEE processe a mesma informação repetidamente.
@st.cache_data
def create_brazil_annual_map():
    """
    Cria e retorna um mapa geemap com a precipitação anual de um ano de referência para o Brasil.
    """
    try:
        # Carrega a coleção de limites do Brasil
        countries = ee.FeatureCollection('USDOS/LSIB_SIMPLE/2017')
        brazil = countries.filter(ee.Filter.eq('country_na', 'Brazil'))

        # Carrega a coleção CHIRPS para um ano recente (ex: 2023)
        precip_collection = ee.ImageCollection('UCSB-CHG/CHIRPS/PENTAD') \
            .filter(ee.Filter.date('2023-01-01', '2023-12-31')) \
            .select('precipitation')

        # Soma todas as imagens para obter o acumulado anual e recorta para o Brasil
        annual_precipitation = precip_collection.sum().clip(brazil)

        # Parâmetros de visualização
        palette = ['#1621a2', '#03ffff', '#13ff03', '#efff00', '#ffb103', '#ff2300']
        vis_params = {'min': 200.0, 'max': 3000.0, 'palette': palette}

        # Cria o mapa com um tema escuro
        m = geemap.Map(center=[-15, -55], zoom=3, tiles=None)
        m.add_basemap('CartoDB.DarkMatter')
        m.addLayer(
            annual_precipitation,
            vis_params,
            'Precipitação Anual (2023)'
        )
        
        return m
    except ee.ee_exception.EEException as e:
        st.warning(f"Não foi possível gerar o mapa de exemplo. Erro no GEE: {e}")
        return None

# --- ESTRUTURA DA PÁGINA INICIAL ---

# --- 1. Seção de Apresentação (Hero Section) ---
st.title("💧 AquaGEE Analytics")
st.markdown("##### Sua plataforma para análise de dados de precipitação com o poder do Google Earth Engine.")
st.write("---")

col1, col2 = st.columns([0.6, 0.4])

with col1:
    st.markdown("""
    O **AquaGEE Analytics** oferece ferramentas intuitivas para explorar, visualizar e analisar padrões de chuva em todo o território brasileiro.
    Utilizando dados de satélite processados em nuvem, você pode gerar mapas, séries temporais e comparações de forma rápida e eficiente.

    Navegue pelas nossas ferramentas para:

    - **🗺️ Mapas Interativos:** Visualize a distribuição espacial da chuva em diferentes escalas de tempo.
    - **📈 Séries Temporais:** Extraia dados quantitativos para análises detalhadas por estado, município ou área de interesse.
    - **📊 Comparações:** Analise diferentes fontes de dados lado a lado para entender suas características e diferenças.
    """)
    st.info("👈 **Para começar, expanda o menu na barra lateral à esquerda e escolha uma das ferramentas de análise.**", icon="💡")

with col2:
    with st.spinner("Carregando mapa de exemplo..."):
        mapa_exemplo = create_brazil_annual_map()
        if mapa_exemplo:
            mapa_exemplo.to_streamlit(height=400)

st.write("---")

# --- 2. Seção de Funcionalidades ---
st.header("Nossas Ferramentas de Análise")
st.write("")

c1, c2, c3 = st.columns(3)

with c1:
    with st.container(border=True):
        st.markdown("#### 🗺️ Mapas Interativos")
        st.write("""
        Visualize a distribuição espacial da precipitação. Ideal para entender a cobertura e intensidade de eventos de chuva em todo o Brasil.
        - **Escalas:** Última imagem, Diária, Mensal e Anual.
        - **Fontes:** IMERG, GSMaP e CHIRPS.
        - **Recursos:** Mapa interativo com zoom, legenda e seleção de período.
        """)

with c2:
    with st.container(border=True):
        st.markdown("#### 📈 Séries Temporais por Região")
        st.write("""
        Extraia dados quantitativos para uma localidade específica e analise o comportamento da chuva ao longo do tempo.
        - **Seleção:** Por Estado, Município, Ponto (Lat/Lon) ou desenhando no mapa.
        - **Gráficos:** Séries diárias, mensais, climatologia e totais anuais.
        - **Objetivo:** Identificar tendências, sazonalidade e anomalias.
        """)

with c3:
    with st.container(border=True):
        st.markdown("#### 📊 Comparações")
        st.write("""
        Compare visualmente os resultados das principais fontes de dados de precipitação, lado a lado, para o mesmo período.
        - **Análise:** Compare as estimativas de chuva para o mesmo dia, mês ou ano.
        - **Fontes:** GSMaP vs. IMERG vs. CHIRPS.
        - **Utilidade:** Entender as diferenças e a sensibilidade de cada produto.
        """)

st.write("---")

# --- 3. Seção sobre as Fontes de Dados ---
st.header("Fontes de Dados")
st.write("Utilizamos produtos de precipitação globalmente reconhecidos e validados, processados pelo Google Earth Engine.")

d1, d2, d3 = st.columns(3)

with d1:
    with st.container(border=True):
        st.subheader("CHIRPS")
        st.write("""
        O *Climate Hazards Group InfraRed Precipitation with Station data* (CHIRPS) é um conjunto de dados de precipitação com mais de *40 anos* de registros contínuos. Ele combina observações de satélite com medições em milhares de estações pluviométricas espalhadas pelo globo, oferecendo informações consistentes para análises climatológicas e estudos de longo prazo. Sua resolução espacial é de aproximadamente 5,5 km, e a série histórica cobre o período de 1981 até o presente.

        Um detalhe importante: o CHIRPS disponibiliza dados apenas sobre os continentes, e não sobre os oceanos. Isso acontece porque a principal utilidade do banco é monitorar impactos da chuva em áreas habitadas, agricultura e recursos hídricos, que estão no continente. Além disso, a integração com estações meteorológicas em solo — um dos diferenciais do CHIRPS — só é possível em terra firme, já que não existem redes equivalentes em mar aberto. Para precipitação sobre oceanos, outros produtos satelitais, como o GPM (Global Precipitation Measurement), são mais indicados.
        - **Resolução Espacial:** 5566 metros
        - **Disponibilidade:** 1981-Presente
        - **Referência:** [CHIRPS](https://developers.google.com/earth-engine/datasets/catalog/UCSB-CHG_CHIRPS_DAILY?hl=pt-br#citations)
        - **Mais informações:** [CHG](https://www.chc.ucsb.edu/data/chirps)
        """)

with d2:
    with st.container(border=True):
        st.subheader("IMERG")
        st.write("""
        O *Integrated Multi-satellitE Retrievals for GPM* (IMERG), desenvolvido pela NASA dentro da missão Global Precipitation Measurement (GPM), é um dos principais produtos globais de precipitação por satélite. Ele oferece estimativas de chuva com alta resolução temporal, atualizadas a cada *30 minutos*, o que o torna ideal para o acompanhamento de eventos de curta duração, como tempestades intensas, enchentes repentinas e monitoramento quase em tempo real. Sua resolução espacial é de cerca de *10 km*, cobrindo praticamente todo o globo.

        Ao contrário do CHIRPS, que se concentra nos continentes, o IMERG fornece dados tanto sobre terra quanto sobre os oceanos, já que se baseia em uma constelação de satélites de micro-ondas e infravermelho capazes de observar a atmosfera globalmente. Isso o torna especialmente útil para o estudo de sistemas meteorológicos de grande escala, como ciclones tropicais, frentes frias e zonas de convergência.
        - **Resolução Espacial:** 11132 metros
        - **Disponibilidade:** 2000-Presente
        - **Referência:** [IMERG](https://developers.google.com/earth-engine/datasets/catalog/NASA_GPM_L3_IMERG_V07?hl=pt-br#citations)
        - **Mais informações:** [GPM](https://gpm.nasa.gov/)
        """)

with d3:
    with st.container(border=True):
        st.subheader("GSMaP")
        st.write("""
        O *Global Satellite Mapping of Precipitation* (GSMaP), desenvolvido pela JAXA em parceria com o projeto GPM, fornece estimativas de precipitação com resolução horária e aproximadamente 10 km de detalhamento espacial. Um de seus grandes diferenciais é a rapidez na disponibilização dos dados, o que o torna muito útil para o acompanhamento de sistemas convectivos, como tempestades tropicais e eventos intensos de curta duração.

        Assim como o IMERG, o GSMaP oferece cobertura global, incluindo tanto continentes quanto oceanos, graças à constelação de satélites de micro-ondas e infravermelho que alimentam o sistema. Essa abrangência é essencial para aplicações em regiões remotas e em áreas oceânicas, permitindo o monitoramento de ciclones, zonas de convergência e sistemas de grande escala. Além disso, sua agilidade na atualização torna o GSMaP uma referência em contextos de monitoramento operacional.
        - **Resolução Espacial:** 11132 metros
        - **Disponibilidade:** 2000-Presente
        - **Referência:** [GSMaP](https://developers.google.com/earth-engine/datasets/catalog/JAXA_GPM_L3_GSMaP_v8_operational?hl=pt-br#citations)
        - **Mais informações:** [JAXA](https://sharaku.eorc.jaxa.jp/GSMaP_NOW/index_j.htm)
        """)

# --- 4. Seção de Instruções ---
with st.expander("🤔 Como usar o aplicativo? (Clique para expandir)"):
    st.markdown("""
        1.  **Navegue na barra lateral:** Clique no ícone `>` no canto superior esquerdo para abrir o menu e escolha entre `Mapas Interativos`, `Séries Temporais` ou `Comparações`.
        2.  **Configure os filtros:** Em cada página, um menu lateral permitirá que você defina a fonte de dados, o período (data, mês, ano) e/ou a localidade de interesse.
        3.  **Execute a Análise:** Clique no botão principal (ex: "Gerar Mapas" ou "Gerar Análise") para que os dados sejam processados no Google Earth Engine.
        4.  **Interaja com os resultados:** Use o zoom nos mapas, passe o mouse sobre os gráficos para ver valores detalhados e explore os dados gerados.
    """)

# --- 5. Rodapé ---
st.markdown("---")
st.markdown(
    """
    <div style="text-align: center; color: grey;">
        Desenvolvido por Natanael Silva Oliveira | TCC Ciências Atmosféricas - UNIFEI 2025
    </div>
    """,
    unsafe_allow_html=True
)
