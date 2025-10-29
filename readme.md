
# 🚛 Sistema de Análise Fiscal com IA e Rotas

#### Este repositório reúne o projeto desenvolvido para o curso Agentes Autônomos com IA Generativa, oferecido pelas empresas I2A2, Meta e MetadataH.

Sistema inteligente para análise automatizada de documentos fiscais (NF-e, CT-e, MDF-e) com cálculo de rotas otimizadas, geocodificação automática e análise detalhada de custos logísticos.

![Python](https://img.shields.io/badge/python-3.8+-blue.svg)
![Streamlit](https://img.shields.io/badge/streamlit-1.28+-red.svg)
![License](https://img.shields.io/badge/license-MIT-green.svg)

## 📋 Índice

- [Visão Geral](#-visão-geral)
- [Funcionalidades](#-funcionalidades)
- [Tecnologias Utilizadas](#️-tecnologias-utilizadas)
- [Instalação](#-instalação)
- [Configuração](#️-configuração)
- [Uso](#-uso)
- [Estrutura do Projeto](#-estrutura-do-projeto)
- [APIs Utilizadas](#-apis-utilizadas)
- [Exemplos de Uso](#-exemplos-de-uso)
- [Contribuindo](#-contribuindo)
- [Licença](#-licença)

## 🎯 Visão Geral

Este sistema foi desenvolvido para automatizar e otimizar o processo de análise de documentos fiscais e planejamento logístico. Ele combina inteligência artificial com APIs de geolocalização e roteamento para fornecer:

- **Extração automática** de dados de XMLs fiscais brasileiros
- **Geocodificação inteligente** de endereços de entrega
- **Cálculo de rotas otimizadas** com distâncias e tempos
- **Estimativa precisa de custos** operacionais completos
- **Visualização interativa** em mapas dinâmicos
- **Relatórios exportáveis** para análise e tomada de decisão

## ✨ Funcionalidades

### 📄 Processamento de Documentos Fiscais

- ✅ **NF-e (Nota Fiscal Eletrônica)**: Extração completa de dados de produtos, valores e destinatários
- ✅ **CT-e (Conhecimento de Transporte Eletrônico)**: Parse de informações de carga e transporte
- ✅ **MDF-e (Manifesto de Documento Fiscal Eletrônico)**: Processamento de manifestos de carga
- ✅ **Validação automática** de XMLs com tratamento de namespaces
- ✅ **Extração inteligente** de endereços, CEPs e coordenadas

### 🗺️ Geocodificação e Rotas

- ✅ **Geocodificação automática** usando OpenStreetMap/Nominatim (gratuito)
- ✅ **Fallback inteligente** para endereços incompletos (tenta cidade/estado)
- ✅ **Cálculo de rotas** com OpenRouteService API quando disponível
- ✅ **Estimativa de distâncias** usando fórmula de Haversine como alternativa
- ✅ **Otimização de sequência** de entregas para minimizar distância
- ✅ **Cálculo de tempo estimado** de viagem com base em velocidades médias

### 💰 Análise de Custos Completa

- ✅ **Combustível**: Cálculo baseado em consumo médio e preço por litro
- ✅ **Pedágios**: Estimativa por distância e número de praças
- ✅ **Mão de obra**: Custo do motorista por hora trabalhada
- ✅ **Desgaste do veículo**: Depreciação por quilômetro rodado
- ✅ **Seguro e taxas**: Custos fixos diários e por entrega
- ✅ **Alimentação e pernoite**: Estimativas para viagens longas
- ✅ **Análise de viabilidade**: Percentual do custo sobre valor da carga
- ✅ **Recomendações inteligentes**: Sugestões automáticas de otimização

### 📊 Visualização e Relatórios

- ✅ **Mapa interativo** com Folium e marcadores coloridos
- ✅ **Linhas de rota** com informações detalhadas em popups
- ✅ **Dashboard completo** com métricas principais
- ✅ **Tabelas dinâmicas** com análise de custos por categoria
- ✅ **Gráficos de viabilidade** econômica da operação
- ✅ **Exportação em JSON** com todos os dados calculados
- ✅ **Exportação em CSV** de documentos processados
- ✅ **Interface responsiva** e intuitiva com Streamlit

## 🛠️ Tecnologias Utilizadas

### Core

- **Python 3.8+**: Linguagem principal do projeto
- **Streamlit 1.28+**: Framework para interface web interativa
- **OpenAI GPT** (opcional): Processamento de linguagem natural

### Processamento de Dados

- **xml.etree.ElementTree**: Parse nativo de XMLs fiscais
- **Pandas**: Manipulação, análise e visualização de dados tabulares
- **dataclasses**: Estruturas de dados tipadas e imutáveis
- **typing**: Type hints para código mais robusto

### Geolocalização e Mapas

- **Nominatim (OpenStreetMap)**: Geocodificação gratuita e sem API key
- **OpenRouteService**: Cálculo de rotas otimizadas (opcional)
- **Folium**: Criação de mapas interativos com Leaflet.js
- **streamlit-folium**: Integração perfeita entre Folium e Streamlit

### Utilitários

- **requests**: Requisições HTTP para APIs externas
- **python-dotenv**: Gerenciamento seguro de variáveis de ambiente
- **json**: Serialização e exportação de dados
- **datetime**: Manipulação de datas e timestamps
- **math**: Cálculos geográficos (Haversine, trigonometria)

## 📦 Instalação

### Pré-requisitos

- Python 3.8 ou superior instalado
- pip (gerenciador de pacotes Python)
- Conta OpenAI (opcional, apenas para recursos avançados)

### Passo a Passo

1. **Clone o repositório**

```bash
git clone https://github.com/AlvesVitor/RouteWise.git
cd RouteWise
```

2. **Crie um ambiente virtual (recomendado)**

```bash
python -m venv venv

# Linux/Mac
source venv/bin/activate

# Windows
venv\Scripts\activate
```

3. **Instale as dependências**

```bash
pip install -r requirements.txt
```

4. **Crie o arquivo requirements.txt** (se necessário)

```txt
streamlit>=1.28.0
openai>=1.0.0
pandas>=2.0.0
folium>=0.14.0
streamlit-folium>=0.15.0
requests>=2.31.0
python-dotenv>=1.0.0
```

## ⚙️ Configuração

### 1. Variáveis de Ambiente

Crie um arquivo `.env` na raiz do projeto:

```env
# Obrigatório para recursos avançados (pode funcionar sem)
OPENAI_API_KEY=sua_chave_openai_aqui
OPENAI_MODEL=gpt-4

# Opcional - Melhora precisão das rotas (gratuito até 2000 req/dia)
OPENROUTESERVICE_API_KEY=sua_chave_openroute_aqui

# Opcional - Pedágios precisos (pago)
TOLLGURU_API_KEY=sua_chave_tollguru_aqui
```

### 2. Obtenha as Chaves de API

#### OpenAI (Opcional)

- Acesse: https://platform.openai.com/api-keys
- Crie uma nova chave de API
- Cole no arquivo `.env`

#### OpenRouteService (Recomendado)

- Acesse: https://openrouteservice.org/dev/#/signup
- Cadastro gratuito (até 2000 requisições/dia)
- Cole a chave no arquivo `.env`

#### TollGuru (Opcional)

- Acesse: https://tollguru.com/
- Planos pagos para pedágios precisos
- Sistema funciona bem com estimativa interna

> **💡 Dica**: O sistema funciona sem as APIs opcionais, usando cálculos estimados e geocodificação gratuita do OpenStreetMap.

### 3. Arquivo .env.example

Crie um arquivo `.env.example` para referência:

```env
OPENAI_API_KEY=your_openai_key_here
OPENAI_MODEL=gpt-4
OPENROUTESERVICE_API_KEY=your_openroute_key_here
TOLLGURU_API_KEY=your_tollguru_key_here
```

## 🚀 Uso

### Iniciar o Sistema

```bash
streamlit run app.py
```

O sistema abrirá automaticamente no navegador em `http://localhost:8501`

### Fluxo de Trabalho Completo

#### 1️⃣ Upload de Documentos

- Clique no botão de upload ou arraste os arquivos XML
- Formatos aceitos: `.xml` (NF-e, CT-e, MDF-e)
- Suporta múltiplos arquivos simultaneamente
- O sistema identifica automaticamente o tipo de documento

#### 2️⃣ Processamento Automático

O sistema extrai automaticamente:

- ✅ Dados completos do destinatário
- ✅ Endereços formatados (rua, número, cidade, UF, CEP)
- ✅ Valores totais das mercadorias
- ✅ Pesos das cargas
- ✅ Lista detalhada de produtos
- ✅ Coordenadas geográficas (latitude/longitude)

#### 3️⃣ Configuração da Rota

**Origem:**

- Digite o endereço completo de onde a carga sairá
- Exemplo: "Av. Paulista, 1000 - São Paulo, SP"

**Parâmetros do Veículo:**

- **Consumo médio**: km por litro (ex: 3.5 km/l)
- **Preço do combustível**: valor atual por litro (ex: R$ 6,20)
- **Valor/hora motorista**: custo por hora (ex: R$ 15,00)

#### 4️⃣ Cálculo e Análise

Clique em **"Calcular Rota e Custos"** e aguarde:

- 🗺️ Geocodificação da origem (2-5 segundos)
- 📍 Cálculo de rotas otimizadas (5-10 segundos)
- 💰 Análise completa de custos (2-3 segundos)
- 🗺️ Geração do mapa interativo (3-5 segundos)

#### 5️⃣ Explorar Resultados

Navegue pelas abas:

**📋 Resumo Geral**

- Métricas principais (distância, tempo, custos)
- Informações da carga
- Consumo de combustível
- Recomendações inteligentes

**🗺️ Mapa da Rota**

- Visualização interativa com marcadores
- Popups com detalhes de cada parada
- Linhas coloridas indicando sequência
- Zoom e navegação livre

**🛣️ Roteirização**

- Tabela com sequência otimizada
- Detalhes de cada trecho (distância, tempo, pedágios)
- Informações de entregas por parada

**💰 Análise de Custos**

- Decomposição por categoria
- Percentuais sobre o total
- Análise de viabilidade econômica
- Top 3 maiores custos

**📈 Dados Detalhados**

- Lista completa de documentos processados
- Estatísticas por tipo e estado
- Exportação em JSON e CSV

#### 6️⃣ Exportação de Relatórios

**Relatório Completo (JSON):**

- Todos os dados calculados
- Documentos processados
- Rotas detalhadas
- Custos discriminados
- Parâmetros utilizados
- Timestamp da análise

**Documentos (CSV):**

- Tabela simples para Excel
- Todos os campos dos XMLs
- Status de geocodificação
- Coordenadas calculadas

## 📝 Licença

Este projeto está sob a licença MIT. Veja o arquivo [LICENSE](LICENSE) para mais detalhes.

```
MIT License

Copyright (c) 2025 Vitor Alves

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:
...
```

### Políticas de Dados

- ✅ **Processamento local**: XMLs processados apenas na sua máquina
- ✅ **Sem armazenamento**: Nenhum dado é enviado para servidores externos
- ✅ **APIs externas**: Apenas coordenadas são enviadas (sem dados sensíveis)
- ✅ **Código aberto**: Audite você mesmo o código

</div>
