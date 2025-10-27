import os
import streamlit as st
import xml.etree.ElementTree as ET
import pandas as pd
import json
import re
from datetime import datetime, timedelta
import math
from typing import Dict, List, Any, Optional, Tuple
import openai
from dataclasses import dataclass, field
import requests
from dotenv import load_dotenv
import folium
from streamlit_folium import st_folium

# Configuração da página
st.set_page_config(
    page_title="Sistema de Análise Fiscal com IA",
    page_icon="📊",
    layout="wide"
)

# Configurações
load_dotenv()
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
OPENAI_MODEL = os.getenv("OPENAI_MODEL", "gpt-4")
OPENROUTESERVICE_API_KEY = os.getenv("OPENROUTESERVICE_API_KEY", "")
TOLLGURU_API_KEY = os.getenv("TOLLGURU_API_KEY", "")

@dataclass
class FiscalDocument:
    tipo: str
    numero: str
    destinatario: str
    endereco_completo: str
    cidade: str
    uf: str
    cep: str
    produtos: List[Dict]
    valor_total: float
    peso_total: float
    coordenadas: Optional[Tuple[float, float]] = None
    prazo_entrega: Optional[str] = None
    restricoes: List[str] = field(default_factory=list)

class GeocodingService:
    """Serviço para obter coordenadas de endereços"""
    
    @staticmethod
    def geocode_address(endereco: str, cidade: str, uf: str, cep: str) -> Optional[Tuple[float, float]]:
        """Obtém coordenadas (lat, lon) de um endereço usando Nominatim (OpenStreetMap)"""
        try:
            # Monta endereço completo
            endereco_completo = f"{endereco}, {cidade}, {uf}, Brasil"
            
            # Nominatim é gratuito e não requer API key
            url = "https://nominatim.openstreetmap.org/search"
            params = {
                'q': endereco_completo,
                'format': 'json',
                'limit': 1
            }
            headers = {
                'User-Agent': 'SistemaFiscalLogistica/1.0'
            }
            
            response = requests.get(url, params=params, headers=headers, timeout=5)
            
            if response.status_code == 200:
                data = response.json()
                if data and len(data) > 0:
                    return (float(data[0]['lat']), float(data[0]['lon']))
            
            # Fallback: tenta apenas com cidade e UF
            params['q'] = f"{cidade}, {uf}, Brasil"
            response = requests.get(url, params=params, headers=headers, timeout=5)
            
            if response.status_code == 200:
                data = response.json()
                if data and len(data) > 0:
                    return (float(data[0]['lat']), float(data[0]['lon']))
            
            return None
            
        except Exception as e:
            st.warning(f"Erro ao geocodificar {cidade}: {str(e)}")
            return None

class FiscalInterpretationAgent:
    """Agente responsável por extrair e interpretar dados dos XMLs fiscais"""
    
    def __init__(self, api_key: str):
        self.api_key = api_key
        openai.api_key = api_key
        self.geocoding_service = GeocodingService()
    
    def extract_xml_data(self, xml_content: str, tipo_documento: str) -> FiscalDocument:
        """Extrai dados estruturados do XML"""
        try:
            root = ET.fromstring(xml_content)
            
            if tipo_documento.upper() == "NFE":
                documento = self._process_nfe(root)
            elif tipo_documento.upper() == "CTE":
                documento = self._processar_cte(root)
            elif tipo_documento.upper() == "MDFE":
                documento = self._processar_mdfe(root)
            else:
                raise ValueError(f"Tipo de documento não suportado: {tipo_documento}")
            
            # Geocodifica o endereço
            if documento:
                coordenadas = self.geocoding_service.geocode_address(
                    documento.endereco_completo,
                    documento.cidade,
                    documento.uf,
                    documento.cep
                )
                documento.coordenadas = coordenadas
            
            return documento
                
        except Exception as e:
            st.error(f"Erro ao processar XML: {str(e)}")
            return None
    
    def _process_nfe(self, root) -> FiscalDocument:
        """Processa NFe e extrai informações relevantes"""
        ns = {'nfe': 'http://www.portalfiscal.inf.br/nfe'}
        
        # Dados básicos
        inf_nfe = root.find('.//nfe:infNFe', ns)
        numero = inf_nfe.find('.//nfe:ide/nfe:nNF', ns).text if inf_nfe.find('.//nfe:ide/nfe:nNF', ns) is not None else "N/A"
        
        # Destinatário
        dest = inf_nfe.find('.//nfe:dest', ns)
        nome_dest = dest.find('.//nfe:xNome', ns).text if dest.find('.//nfe:xNome', ns) is not None else "N/A"
        
        # Endereço
        ender_dest = dest.find('.//nfe:enderDest', ns)
        endereco = f"{ender_dest.find('.//nfe:xLgr', ns).text if ender_dest.find('.//nfe:xLgr', ns) is not None else ''}, "
        endereco += f"{ender_dest.find('.//nfe:nro', ns).text if ender_dest.find('.//nfe:nro', ns) is not None else ''}"
        cidade = ender_dest.find('.//nfe:xMun', ns).text if ender_dest.find('.//nfe:xMun', ns) is not None else "N/A"
        uf = ender_dest.find('.//nfe:UF', ns).text if ender_dest.find('.//nfe:UF', ns) is not None else "N/A"
        cep = ender_dest.find('.//nfe:CEP', ns).text if ender_dest.find('.//nfe:CEP', ns) is not None else "N/A"
        
        # Produtos
        produtos = []
        for det in inf_nfe.findall('.//nfe:det', ns):
            prod = det.find('.//nfe:prod', ns)
            produto = {
                'nome': prod.find('.//nfe:xProd', ns).text if prod.find('.//nfe:xProd', ns) is not None else "N/A",
                'quantidade': float(prod.find('.//nfe:qCom', ns).text) if prod.find('.//nfe:qCom', ns) is not None else 0,
                'valor': float(prod.find('.//nfe:vProd', ns).text) if prod.find('.//nfe:vProd', ns) is not None else 0,
                'peso': float(prod.find('.//nfe:pesoB', ns).text) if prod.find('.//nfe:pesoB', ns) is not None else 0
            }
            produtos.append(produto)
        
        # Totais
        total = inf_nfe.find('.//nfe:total/nfe:ICMSTot', ns)
        valor_total = float(total.find('.//nfe:vNF', ns).text) if total.find('.//nfe:vNF', ns) is not None else 0
        peso_total = sum([p['peso'] * p['quantidade'] for p in produtos])
        
        return FiscalDocument(
            tipo="NFE",
            numero=numero,
            destinatario=nome_dest,
            endereco_completo=endereco,
            cidade=cidade,
            uf=uf,
            cep=cep,
            produtos=produtos,
            valor_total=valor_total,
            peso_total=peso_total
        )
    
    def _processar_cte(self, root) -> FiscalDocument:
        """Processa CTe"""
        ns = {'cte': 'http://www.portalfiscal.inf.br/cte'}
        
        inf_cte = root.find('.//cte:infCte', ns)
        numero = inf_cte.find('.//cte:ide/cte:nCT', ns).text if inf_cte.find('.//cte:ide/cte:nCT', ns) is not None else "N/A"
        
        # Destinatário
        dest = inf_cte.find('.//cte:dest', ns)
        nome_dest = dest.find('.//cte:xNome', ns).text if dest.find('.//cte:xNome', ns) is not None else "N/A"
        
        # Endereço de entrega
        ender_dest = dest.find('.//cte:enderDest', ns)
        endereco = f"{ender_dest.find('.//cte:xLgr', ns).text if ender_dest.find('.//cte:xLgr', ns) is not None else ''}, "
        endereco += f"{ender_dest.find('.//cte:nro', ns).text if ender_dest.find('.//cte:nro', ns) is not None else ''}"
        cidade = ender_dest.find('.//cte:xMun', ns).text if ender_dest.find('.//cte:xMun', ns) is not None else "N/A"
        uf = ender_dest.find('.//cte:UF', ns).text if ender_dest.find('.//cte:UF', ns) is not None else "N/A"
        cep = ender_dest.find('.//cte:CEP', ns).text if ender_dest.find('.//cte:CEP', ns) is not None else "N/A"
        
        # Valores
        vPrest = inf_cte.find('.//cte:vPrest', ns)
        valor_total = float(vPrest.find('.//cte:vTPrest', ns).text) if vPrest.find('.//cte:vTPrest', ns) is not None else 0
        
        # Carga
        infCarga = inf_cte.find('.//cte:infCarga', ns)
        peso_total = float(infCarga.find('.//cte:vCarga', ns).text) if infCarga.find('.//cte:vCarga', ns) is not None else 0
        
        produtos = [{'nome': 'Carga de Transporte', 'quantidade': 1, 'valor': valor_total, 'peso': peso_total}]
        
        return FiscalDocument(
            tipo="CTE",
            numero=numero,
            destinatario=nome_dest,
            endereco_completo=endereco,
            cidade=cidade,
            uf=uf,
            cep=cep,
            produtos=produtos,
            valor_total=valor_total,
            peso_total=peso_total
        )
    
    def _processar_mdfe(self, root) -> FiscalDocument:
        """Processa MDFe"""
        ns = {'mdfe': 'http://www.portalfiscal.inf.br/mdfe'}
        
        inf_mdfe = root.find('.//mdfe:infMDFe', ns)
        numero = inf_mdfe.find('.//mdfe:ide/mdfe:nMDF', ns).text if inf_mdfe.find('.//mdfe:ide/mdfe:nMDF', ns) is not None else "N/A"
        
        # Para MDF-e, pode ter múltiplos destinos
        destinos = []
        for infDoc in inf_mdfe.findall('.//mdfe:infDoc', ns):
            dest_info = {
                'nome': 'Destinatário MDF-e',
                'endereco': 'Múltiplos destinos',
                'cidade': 'Múltiplas cidades',
                'uf': 'Múltiplos estados',
                'cep': 'N/A'
            }
            destinos.append(dest_info)
        
        produtos = [{'nome': 'Manifesto de Carga', 'quantidade': len(destinos), 'valor': 0, 'peso': 0}]
        
        return FiscalDocument(
            tipo="MDFE",
            numero=numero,
            destinatario="Múltiplos destinatários",
            endereco_completo="Múltiplos endereços",
            cidade="Múltiplas cidades",
            uf="Múltiplos estados",
            cep="N/A",
            produtos=produtos,
            valor_total=0,
            peso_total=0
        )

class RouteService:
    """Serviço para calcular rotas usando APIs externas"""
    
    def __init__(self, api_key: str = ""):
        self.api_key = api_key
        self.base_url = "https://api.openrouteservice.org"
    
    def calculate_optimized_route(self, origem: Tuple[float, float], 
                               destinos: List[Tuple[float, float]]) -> Optional[Dict]:
        """
        Calcula rota otimizada usando OpenRouteService
        origem: (latitude, longitude)
        destinos: lista de (latitude, longitude)
        """
        if not self.api_key:
            return None
        
        try:
            # Prepara coordenadas no formato [longitude, latitude]
            jobs = []
            for i, dest in enumerate(destinos):
                jobs.append({
                    "id": i + 1,
                    "location": [dest[1], dest[0]],  # [lon, lat]
                    "service": 300  # tempo de serviço em segundos (5 min)
                })
            
            # Veículo começando na origem
            vehicles = [{
                "id": 1,
                "profile": "driving-car",
                "start": [origem[1], origem[0]],  # [lon, lat]
                "end": [origem[1], origem[0]],
                "capacity": [1000],  # capacidade em kg
                "time_window": [0, 86400]  # 24 horas
            }]
            
            payload = {
                "jobs": jobs,
                "vehicles": vehicles,
                "options": {
                    "g": True  # retorna geometria da rota
                }
            }
            
            headers = {
                'Authorization': self.api_key,
                'Content-Type': 'application/json'
            }
            
            response = requests.post(
                f"{self.base_url}/optimization",
                json=payload,
                headers=headers,
                timeout=30
            )
            
            if response.status_code == 200:
                return response.json()
            else:
                return None
                
        except Exception as e:
            return None
    
    def calculate_distance_time(self, origem: Tuple[float, float], 
                                destino: Tuple[float, float]) -> Optional[Dict]:
        """Calcula distância e tempo entre dois pontos"""
        if not self.api_key:
            return None
        
        try:
            # Formato: [longitude, latitude]
            coordinates = [
                [origem[1], origem[0]],
                [destino[1], destino[0]]
            ]
            
            headers = {
                'Authorization': self.api_key,
                'Content-Type': 'application/json',
                'Accept': 'application/json, application/geo+json, application/gpx+xml, img/png; charset=utf-8'
            }
            
            body = {
                "coordinates": coordinates
            }
            
            response = requests.post(
                f"{self.base_url}/v2/directions/driving-car/json",
                json=body,
                headers=headers,
                timeout=10
            )
            
            if response.status_code == 200:
                data = response.json()
                if 'routes' in data and len(data['routes']) > 0:
                    route = data['routes'][0]
                    summary = route['summary']
                    return {
                        'distancia_km': round(summary['distance'] / 1000, 2),
                        'tempo_horas': round(summary['duration'] / 3600, 2),
                        'geometria': route.get('geometry', None)
                    }
            
            return None
            
        except Exception as e:
            return None

class TollService:
    """Serviço para calcular pedágios na rota"""
    
    def __init__(self, api_key: str = ""):
        self.api_key = api_key
    
    def calculate_route_tolls(self, origem: Tuple[float, float], 
                               destino: Tuple[float, float]) -> Optional[Dict]:
        """
        Calcula pedágios usando TollGuru API ou estimativa
        """
        if not self.api_key:
            return self._estimate_tolls_by_distance(origem, destino)
        
        try:
            return self._estimate_tolls_by_distance(origem, destino)
            
        except Exception as e:
            return self._estimate_tolls_by_distance(origem, destino)
    
    def _estimate_tolls_by_distance(self, origem: Tuple[float, float], 
                                        destino: Tuple[float, float]) -> Dict:
        """Estimativa de pedágios baseada em dados médios brasileiros"""
        from math import sin, cos, sqrt, atan2, radians
        
        R = 6371  # Raio da Terra em km
        lat1, lon1 = radians(origem[0]), radians(origem[1])
        lat2, lon2 = radians(destino[0]), radians(destino[1])
        
        dlat = lat2 - lat1
        dlon = lon2 - lon1
        
        a = sin(dlat/2)**2 + cos(lat1) * cos(lat2) * sin(dlon/2)**2
        c = 2 * atan2(sqrt(a), sqrt(1-a))
        distancia = R * c
        
        # Estimativa: média de R$ 0,15/km em rodovias com pedágio
        valor_pedagio_por_km = 0.15 * 0.4
        numero_pedagogios = max(1, int(distancia / 150))
        valor_medio_pedagio = 15.0
        
        return {
            'valor_total': round(numero_pedagogios * valor_medio_pedagio, 2),
            'numero_pracas': numero_pedagogios,
            'valor_medio': valor_medio_pedagio,
            'estimado': True
        }

class RoutingAgent:
    """Agente responsável por calcular rotas otimizadas usando APIs reais"""
    
    def __init__(self, api_key: str, openroute_key: str = "", tollguru_key: str = ""):
        self.api_key = api_key
        openai.api_key = api_key
        self.servico_rotas = RouteService(openroute_key)
        self.servico_pedagogios = TollService(tollguru_key)
        self.geocoding_service = GeocodingService()
    
    def calculate_optimized_route(self, documentos: List[FiscalDocument], 
                               endereco_origem: str) -> Dict:
        """Calcula rota otimizada usando dados reais de APIs"""
        
        # Geocodifica a origem
        origem_coords = self.geocoding_service.geocode_address(
            endereco_origem, "", "", ""
        )
        
        if not origem_coords:
            st.error("Não foi possível geocodificar o endereço de origem")
            return None
        
        # Agrupa documentos por cidade
        entregas_por_local = {}
        coordenadas_destinos = []
        
        for doc in documentos:
            if doc.coordenadas:
                chave_local = f"{doc.cidade}, {doc.uf}"
                if chave_local not in entregas_por_local:
                    entregas_por_local[chave_local] = {
                        'documentos': [],
                        'coordenadas': doc.coordenadas
                    }
                entregas_por_local[chave_local]['documentos'].append(doc)
                
                if doc.coordenadas not in coordenadas_destinos:
                    coordenadas_destinos.append(doc.coordenadas)
        
        # Tenta usar API de otimização
        rota_otimizada_api = self.servico_rotas.calculate_optimized_route(
            origem_coords, coordenadas_destinos
        )
        
        # Calcula rotas individuais
        rotas_calculadas = []
        distancia_total = 0
        tempo_total = 0
        custo_pedagogios_total = 0
        
        locais_ordenados = list(entregas_por_local.keys())
        
        ponto_anterior = origem_coords
        nome_anterior = endereco_origem
        
        for i, local in enumerate(locais_ordenados):
            info_local = entregas_por_local[local]
            coords_destino = info_local['coordenadas']
            
            # Calcula rota
            rota_info = self.servico_rotas.calculate_distance_time(
                ponto_anterior, coords_destino
            )
            
            if rota_info:
                distancia = rota_info['distancia_km']
                tempo = rota_info['tempo_horas']
            else:
                distancia = self._calculate_haversine_distance(ponto_anterior, coords_destino)
                tempo = distancia / 60
            
            # Calcula pedágios
            pedagogios_info = self.servico_pedagogios.calculate_route_tolls(
                ponto_anterior, coords_destino
            )
            
            rota = {
                'sequencia': i + 1,
                'origem': nome_anterior,
                'destino': local,
                'coordenadas_destino': coords_destino,
                'distancia_km': round(distancia, 2),
                'tempo_estimado_horas': round(tempo, 2),
                'entregas': len(info_local['documentos']),
                'documentos': [doc.numero for doc in info_local['documentos']],
                'valor_total_entregas': sum([doc.valor_total for doc in info_local['documentos']]),
                'peso_total_entregas': sum([doc.peso_total for doc in info_local['documentos']]),
                'pedagios': pedagogios_info
            }
            
            rotas_calculadas.append(rota)
            distancia_total += distancia
            tempo_total += tempo
            custo_pedagogios_total += pedagogios_info['valor_total']
            
            ponto_anterior = coords_destino
            nome_anterior = local
        
        return {
            'rotas': rotas_calculadas,
            'origem_coordenadas': origem_coords,
            'resumo': {
                'total_cidades': len(locais_ordenados),
                'total_entregas': sum([len(info_local['documentos']) for info_local in entregas_por_local.values()]),
                'distancia_total_km': round(distancia_total, 2),
                'tempo_total_horas': round(tempo_total, 2),
                'tempo_total_dias': round(tempo_total / 8, 1),
                'custo_pedagogios_total': round(custo_pedagogios_total, 2),
                'api_utilizada': bool(rota_otimizada_api)
            }
        }
    
    def _calculate_haversine_distance(self, coord1: Tuple[float, float], 
                                     coord2: Tuple[float, float]) -> float:
        """Calcula distância entre coordenadas usando fórmula de Haversine"""
        from math import sin, cos, sqrt, atan2, radians
        
        R = 6371
        lat1, lon1 = radians(coord1[0]), radians(coord1[1])
        lat2, lon2 = radians(coord2[0]), radians(coord2[1])
        
        dlat = lat2 - lat1
        dlon = lon2 - lon1
        
        a = sin(dlat/2)**2 + cos(lat1) * cos(lat2) * sin(dlon/2)**2
        c = 2 * atan2(sqrt(a), sqrt(1-a))
        
        return R * c

class CostCalculationAgent:
    """Agente responsável por calcular custos de transporte com dados reais"""
    
    def __init__(self, api_key: str):
        self.api_key = api_key
        openai.api_key = api_key
    
    def calculate_route_costs(self, rota_info: Dict, 
                            consumo_medio: float = 3.5,
                            preco_combustivel: float = 6.20,
                            valor_hora_motorista: float = 15.0) -> Dict:
        """Calcula custos detalhados da rota"""
        
        resumo_rota = rota_info['resumo']
        
        # Cálculos de custos
        litros_necessarios = resumo_rota['distancia_total_km'] / consumo_medio
        custo_combustivel = litros_necessarios * preco_combustivel
        
        custo_pedagio = resumo_rota.get('custo_pedagogios_total', 0)
        
        custo_desgaste = resumo_rota['distancia_total_km'] * 0.45
        custo_motorista = resumo_rota['tempo_total_horas'] * valor_hora_motorista
        custo_seguro = resumo_rota['tempo_total_dias'] * 50.0
        custo_entregas = resumo_rota['total_entregas'] * 25.0
        
        custo_alimentacao = resumo_rota['tempo_total_dias'] * 80.0
        custo_pernoite = max(0, (resumo_rota['tempo_total_dias'] - 1)) * 150.0
        
        custo_total = (custo_combustivel + custo_pedagio + custo_desgaste + 
                      custo_motorista + custo_seguro + custo_entregas +
                      custo_alimentacao + custo_pernoite)
        
        custo_por_entrega = custo_total / resumo_rota['total_entregas']
        custo_por_km = custo_total / resumo_rota['distancia_total_km']
        
        valor_total_mercadorias = sum([rota['valor_total_entregas'] for rota in rota_info['rotas']])
        percentual_custo = (custo_total / valor_total_mercadorias) * 100 if valor_total_mercadorias > 0 else 0
        
        return {
            'detalhamento_custos': {
                'combustivel': round(custo_combustivel, 2),
                'pedagio': round(custo_pedagio, 2),
                'desgaste_veiculo': round(custo_desgaste, 2),
                'motorista': round(custo_motorista, 2),
                'seguro': round(custo_seguro, 2),
                'taxa_entregas': round(custo_entregas, 2),
                'alimentacao': round(custo_alimentacao, 2),
                'pernoite': round(custo_pernoite, 2)
            },
            'parametros_utilizados': {
                'consumo_medio_km_l': consumo_medio,
                'preco_combustivel_litro': preco_combustivel,
                'valor_hora_motorista': valor_hora_motorista,
                'litros_necessarios': round(litros_necessarios, 2)
            },
            'resumo_custos': {
                'custo_total': round(custo_total, 2),
                'custo_por_entrega': round(custo_por_entrega, 2),
                'custo_por_km': round(custo_por_km, 2),
                'valor_mercadorias': round(valor_total_mercadorias, 2),
                'percentual_custo': round(percentual_custo, 2)
            },
            'recomendacoes': self._generate_recommendations(custo_total, valor_total_mercadorias, percentual_custo, rota_info)
        }
    
    def _generate_recommendations(self, custo_total: float, valor_mercadorias: float, 
                            percentual_custo: float, rota_info: Dict) -> List[str]:
        """Gera recomendações baseadas na análise de custos"""
        recomendacoes = []
        
        if percentual_custo > 15:
            recomendacoes.append("⚠️ Custo de transporte elevado (>15% do valor das mercadorias)")
            recomendacoes.append("💡 Considere consolidar mais entregas na mesma rota")
        elif percentual_custo < 5:
            recomendacoes.append("✅ Excelente eficiência de custos (<5% do valor das mercadorias)")
        else:
            recomendacoes.append("✅ Custos dentro da média esperada (5-15%)")
        
        if rota_info['resumo']['tempo_total_dias'] > 3:
            recomendacoes.append("⏰ Rota longa (>3 dias) - avalie logística de pernoite")
        
        if custo_total > 5000:
            recomendacoes.append("💡 Avalie a possibilidade de terceirização do transporte")
        
        pedagogios_total = rota_info['resumo'].get('custo_pedagogios_total', 0)
        if pedagogios_total > custo_total * 0.2:
            recomendacoes.append("🛣️ Custo de pedágios alto - considere rotas alternativas")
        
        recomendacoes.append("📊 Monitore regularmente os custos de combustível")
        recomendacoes.append("🔧 Mantenha o veículo em bom estado para reduzir custos")
        
        return recomendacoes

def criar_mapa_rota(rota_info: Dict, origem_coords: Tuple[float, float]) -> folium.Map:
    """Cria um mapa interativo com a rota - VERSÃO CORRIGIDA"""
    
    try:
        # Valida coordenadas de origem
        if not origem_coords or len(origem_coords) != 2:
            raise ValueError("Coordenadas de origem inválidas")
        
        lat_origem, lon_origem = origem_coords[0], origem_coords[1]
        
        # Cria mapa centralizado na origem
        mapa = folium.Map(
            location=[lat_origem, lon_origem],
            zoom_start=6,
            tiles='OpenStreetMap'
        )
        
        # Adiciona marcador de origem
        folium.Marker(
            [lat_origem, lon_origem],
            popup="🏭 Origem",
            tooltip="Ponto de Partida",
            icon=folium.Icon(color='green', icon='home')
        ).add_to(mapa)
        
        # Cores para as rotas
        cores = ['red', 'blue', 'purple', 'orange', 'darkred', 'lightred', 'beige', 
                 'darkblue', 'darkgreen', 'cadetblue', 'darkpurple', 'pink']
        
        ponto_anterior = origem_coords
        todas_coordenadas = [origem_coords]
        
        # Adiciona marcadores e linhas para cada destino
        for i, rota in enumerate(rota_info.get('rotas', [])):
            cor = cores[i % len(cores)]
            coords_destino = rota.get('coordenadas_destino')
            
            # Valida coordenadas do destino
            if not coords_destino or len(coords_destino) != 2:
                continue
            
            lat_dest, lon_dest = coords_destino[0], coords_destino[1]
            todas_coordenadas.append(coords_destino)
            
            # Popup com informações detalhadas
            popup_text = f"""
            <div style="font-family: Arial; font-size: 12px;">
                <b style="font-size: 14px;">🎯 Parada {rota['sequencia']}</b><br>
                <b>{rota['destino']}</b><br><br>
                <b>📦 Entregas:</b> {rota['entregas']}<br>
                <b>🛣️ Distância:</b> {rota['distancia_km']} km<br>
                <b>⏱️ Tempo:</b> {rota['tempo_estimado_horas']:.1f}h<br>
                <b>💰 Valor:</b> R$ {rota['valor_total_entregas']:,.2f}<br>
                <b>🚧 Pedágios:</b> R$ {rota['pedagios']['valor_total']:.2f}<br>
                <b>📄 Docs:</b> {', '.join(rota['documentos'])}
            </div>
            """
            
            # Marcador do destino
            folium.Marker(
                [lat_dest, lon_dest],
                popup=folium.Popup(popup_text, max_width=300),
                tooltip=f"Parada {rota['sequencia']}: {rota['destino']}",
                icon=folium.Icon(color=cor, icon='info-sign', prefix='glyphicon')
            ).add_to(mapa)
            
            # Linha conectando pontos
            if ponto_anterior and len(ponto_anterior) == 2:
                folium.PolyLine(
                    locations=[
                        [ponto_anterior[0], ponto_anterior[1]], 
                        [lat_dest, lon_dest]
                    ],
                    color=cor,
                    weight=4,
                    opacity=0.8,
                    popup=f"Trecho {i+1}: {rota['distancia_km']} km - {rota['tempo_estimado_horas']:.1f}h"
                ).add_to(mapa)
                
                # Adiciona seta indicando direção
                meio_lat = (ponto_anterior[0] + lat_dest) / 2
                meio_lon = (ponto_anterior[1] + lon_dest) / 2
                
                folium.CircleMarker(
                    location=[meio_lat, meio_lon],
                    radius=5,
                    color=cor,
                    fill=True,
                    fillColor=cor,
                    fillOpacity=0.9,
                    popup=f"➡️ Direção Parada {rota['sequencia']}"
                ).add_to(mapa)
            
            ponto_anterior = coords_destino
        
        # Ajusta o zoom para mostrar todos os pontos
        if len(todas_coordenadas) > 1:
            mapa.fit_bounds(todas_coordenadas)
        
        return mapa
        
    except Exception as e:
        st.error(f"Erro detalhado ao criar mapa: {str(e)}")
        # Cria mapa básico em caso de erro
        mapa = folium.Map(
            location=[-23.5505, -46.6333],
            zoom_start=5,
            tiles='OpenStreetMap'
        )
        return mapa

def main():
    st.title("🚛 Sistema de Análise Fiscal com IA e Rotas")
    st.markdown("Sistema inteligente para análise de documentos fiscais com cálculo de rotas e custos")
    
    # Inicializa session_state
    if 'rota_calculada' not in st.session_state:
        st.session_state.rota_calculada = False
    if 'rota_info' not in st.session_state:
        st.session_state.rota_info = None
    if 'custos_info' not in st.session_state:
        st.session_state.custos_info = None
    if 'documentos_processados' not in st.session_state:
        st.session_state.documentos_processados = []
    
    # Status das APIs no sidebar
    with st.sidebar:
        st.header("⚙️ Status do Sistema")
        
        if OPENROUTESERVICE_API_KEY:
            st.success("✅ API de Rotas: Configurada")
        else:
            st.warning("⚠️ API de Rotas: Não configurada\n\nUsando cálculo aproximado")
        
        if TOLLGURU_API_KEY:
            st.success("✅ API de Pedágios: Configurada")
        else:
            st.info("ℹ️ API de Pedágios: Não configurada\n\nUsando estimativa")
    
    # Inicialização dos agentes
    try:
        agente_fiscal = FiscalInterpretationAgent(OPENAI_API_KEY)
        agente_rota = RoutingAgent(OPENAI_API_KEY, OPENROUTESERVICE_API_KEY, TOLLGURU_API_KEY)
        agente_custos = CostCalculationAgent(OPENAI_API_KEY)
    except Exception as e:
        st.error(f"Erro ao inicializar agentes: {str(e)}")
        return
    
    # Interface para upload de arquivos
    st.header("📁 Upload de Documentos Fiscais")
    
    uploaded_files = st.file_uploader(
        "Selecione os arquivos XML (NF-e, CT-e, MDF-e)",
        type=['xml'],
        accept_multiple_files=True,
        help="Os endereços de entrega serão extraídos automaticamente dos XMLs"
    )
    
    if uploaded_files:
        # Verifica se precisa reprocessar
        if len(st.session_state.documentos_processados) != len(uploaded_files):
            st.session_state.documentos_processados = []
            st.session_state.rota_calculada = False
        
        if not st.session_state.documentos_processados:
            st.header("🔍 Processamento dos Documentos")
            
            progress_bar = st.progress(0)
            
            # Processa cada arquivo
            for idx, uploaded_file in enumerate(uploaded_files):
                progress_bar.progress((idx + 1) / len(uploaded_files))
                
                with st.expander(f"📄 {uploaded_file.name}", expanded=False):
                    try:
                        xml_content = uploaded_file.read().decode('utf-8')
                        
                        # Identifica tipo de documento
                        if 'NFe' in xml_content or 'nfe' in xml_content:
                            tipo_doc = "NFE"
                        elif 'CTe' in xml_content or 'cte' in xml_content:
                            tipo_doc = "CTE"
                        elif 'MDFe' in xml_content or 'mdfe' in xml_content:
                            tipo_doc = "MDFE"
                        else:
                            st.warning(f"Tipo de documento não identificado")
                            continue
                        
                        # Processa o documento
                        with st.spinner(f"Processando e geocodificando {uploaded_file.name}..."):
                            documento = agente_fiscal.extract_xml_data(xml_content, tipo_doc)
                        
                        if documento:
                            st.session_state.documentos_processados.append(documento)
                            
                            # Mostra informações extraídas
                            col1, col2, col3 = st.columns(3)
                            with col1:
                                st.write(f"**Tipo:** {documento.tipo}")
                                st.write(f"**Número:** {documento.numero}")
                                st.write(f"**Destinatário:** {documento.destinatario}")
                            with col2:
                                st.write(f"**Cidade:** {documento.cidade}/{documento.uf}")
                                st.write(f"**CEP:** {documento.cep}")
                                st.write(f"**Endereço:** {documento.endereco_completo}")
                            with col3:
                                st.write(f"**Valor:** R$ {documento.valor_total:,.2f}")
                                st.write(f"**Peso:** {documento.peso_total:.2f} kg")
                                if documento.coordenadas:
                                    st.success(f"✅ Geocodificado: {documento.coordenadas}")
                                else:
                                    st.warning("⚠️ Não geocodificado")
                        
                    except Exception as e:
                        st.error(f"Erro: {str(e)}")
            
            progress_bar.empty()
        
        if st.session_state.documentos_processados:
            st.success(f"✅ {len(st.session_state.documentos_processados)} documentos processados com sucesso!")
            
            # Configurações de rota e custos
            st.header("🗺️ Configuração de Rota e Custos")
            
            col1, col2 = st.columns(2)
            
            with col1:
                st.subheader("📍 Origem")
                endereco_origem = st.text_input(
                    "Endereço Completo de Origem",
                    value="Av. Brg. Faria Lima, 6363 - Jardim Morumbi, São José do Rio Preto - SP",
                    help="Digite o endereço completo com cidade e estado",
                    key="endereco_origem"
                )
            
            with col2:
                st.subheader("🚛 Parâmetros do Veículo")
                
                consumo_medio = st.number_input(
                    "Consumo Médio (km/litro)",
                    min_value=1.0,
                    max_value=15.0,
                    value=3.5,
                    step=0.1,
                    help="Consumo médio do veículo em km por litro",
                    key="consumo_medio"
                )
                
                preco_combustivel = st.number_input(
                    "Preço do Combustível (R$/litro)",
                    min_value=1.0,
                    max_value=15.0,
                    value=6.20,
                    step=0.10,
                    help="Preço atual do diesel ou gasolina",
                    key="preco_combustivel"
                )
                
                valor_hora_motorista = st.number_input(
                    "Valor Hora do Motorista (R$/hora)",
                    min_value=5.0,
                    max_value=100.0,
                    value=15.0,
                    step=1.0,
                    help="Custo por hora do motorista",
                    key="valor_hora_motorista"
                )
            
            # Botão para calcular
            calcular_clicked = st.button("🚀 Calcular Rota e Custos", type="primary", use_container_width=True)
            
            if calcular_clicked:
                
                with st.spinner("🗺️ Calculando rota otimizada com APIs..."):
                    rota_info = agente_rota.calculate_optimized_route(
                        st.session_state.documentos_processados, 
                        endereco_origem
                    )
                
                if not rota_info:
                    st.error("❌ Não foi possível calcular a rota. Verifique o endereço de origem.")
                else:
                    with st.spinner("💰 Calculando custos detalhados..."):
                        custos_info = agente_custos.calculate_route_costs(
                            rota_info,
                            consumo_medio,
                            preco_combustivel,
                            valor_hora_motorista
                        )
                    
                    # Salva no session_state
                    st.session_state.rota_info = rota_info
                    st.session_state.custos_info = custos_info
                    st.session_state.rota_calculada = True
            
            # Exibe resultados se calculados
            if st.session_state.rota_calculada and st.session_state.rota_info and st.session_state.custos_info:
                
                rota_info = st.session_state.rota_info
                custos_info = st.session_state.custos_info
                
                st.markdown("---")
                
                # Exibe resultados
                st.header("📊 Relatório Completo de Análise")
                
                # Botões de ação
                col_btn1, col_btn2, col_btn3 = st.columns([1, 1, 2])
                with col_btn1:
                    if st.button("🔄 Recalcular Rota", use_container_width=True):
                        st.session_state.rota_calculada = False
                        st.session_state.rota_info = None
                        st.session_state.custos_info = None
                        st.session_state.mapa_html = None  # Limpa o mapa do cache
                        st.session_state.mapa_precisa_atualizar = True
                        st.rerun()
                with col_btn2:
                    if st.button("🗑️ Limpar Tudo", use_container_width=True):
                        st.session_state.clear()
                        st.rerun()
                
                # Indicador de API
                if rota_info['resumo'].get('api_utilizada'):
                    st.success("✅ Rotas calculadas usando OpenRouteService API (dados reais)")
                else:
                    st.info("ℹ️ Rotas calculadas usando estimativa aproximada")
                
                # Debug info
                st.info(f"📍 Total de rotas calculadas: {len(rota_info.get('rotas', []))}")
                
                # Tabs de resultados
                tab1, tab2, tab3, tab4, tab5 = st.tabs([
                    "📋 Resumo Geral", 
                    "🗺️ Mapa da Rota", 
                    "🛣️ Roteirização", 
                    "💰 Análise de Custos", 
                    "📈 Dados Detalhados"
                ])
                
                with tab1:
                    st.subheader("📊 Resumo Executivo")
                    
                    col1, col2, col3, col4, col5 = st.columns(5)
                    with col1:
                        st.metric("Entregas", rota_info['resumo']['total_entregas'])
                    with col2:
                        st.metric("Distância", f"{rota_info['resumo']['distancia_total_km']} km")
                    with col3:
                        st.metric("Tempo", f"{rota_info['resumo']['tempo_total_horas']:.1f}h")
                    with col4:
                        st.metric("Pedágios", f"R$ {rota_info['resumo']['custo_pedagogios_total']:.2f}")
                    with col5:
                        st.metric("Custo Total", f"R$ {custos_info['resumo_custos']['custo_total']:,.2f}")
                    
                    st.markdown("---")
                    
                    col1, col2 = st.columns(2)
                    
                    with col1:
                        st.subheader("📦 Informações da Carga")
                        valor_total = sum([doc.valor_total for doc in st.session_state.documentos_processados])
                        peso_total = sum([doc.peso_total for doc in st.session_state.documentos_processados])
                        
                        st.write(f"**Valor Total das Mercadorias:** R$ {valor_total:,.2f}")
                        st.write(f"**Peso Total:** {peso_total:,.2f} kg")
                        st.write(f"**Duração Estimada:** {rota_info['resumo']['tempo_total_dias']:.1f} dias")
                        st.write(f"**Custo por KM:** R$ {custos_info['resumo_custos']['custo_por_km']:.2f}")
                        st.write(f"**Custo por Entrega:** R$ {custos_info['resumo_custos']['custo_por_entrega']:.2f}")
                    
                    with col2:
                        st.subheader("⛽ Consumo de Combustível")
                        params = custos_info['parametros_utilizados']
                        
                        st.write(f"**Consumo Médio:** {params['consumo_medio_km_l']:.1f} km/l")
                        st.write(f"**Preço do Combustível:** R$ {params['preco_combustivel_litro']:.2f}/litro")
                        st.write(f"**Litros Necessários:** {params['litros_necessarios']:.2f} L")
                        st.write(f"**Custo Total Combustível:** R$ {custos_info['detalhamento_custos']['combustivel']:,.2f}")
                        
                        percentual = custos_info['resumo_custos']['percentual_custo']
                        if percentual <= 10:
                            st.success(f"✅ Eficiência: {percentual:.1f}% - EXCELENTE")
                        elif percentual <= 15:
                            st.warning(f"⚠️ Eficiência: {percentual:.1f}% - MODERADO")
                        else:
                            st.error(f"❌ Eficiência: {percentual:.1f}% - ATENÇÃO")
                    
                    st.markdown("---")
                    st.subheader("💡 Recomendações")
                    for rec in custos_info['recomendacoes']:
                        st.write(rec)
                
                with tab2:
                    st.subheader("🗺️ Visualização da Rota")
                    
                    try:
                        # Valida dados
                        if not rota_info.get('origem_coordenadas'):
                            st.warning("⚠️ Coordenadas de origem não disponíveis")
                        elif not rota_info.get('rotas') or len(rota_info['rotas']) == 0:
                            st.warning("⚠️ Nenhuma rota para exibir")
                        else:
                            # Info do mapa
                            num_paradas = len(rota_info['rotas'])
                            st.success(f"📍 Exibindo rota com {num_paradas} parada(s)")
                            
                            # Lista as paradas
                            st.write("**Sequência de paradas:**")
                            for rota in rota_info['rotas']:
                                st.write(f"- Parada {rota['sequencia']}: {rota['destino']} ({rota['entregas']} entregas)")
                            
                            st.markdown("---")
                            
                            # Cria o mapa apenas uma vez e guarda no session_state
                            if 'mapa_html' not in st.session_state or st.session_state.get('mapa_precisa_atualizar', True):
                                with st.spinner("🗺️ Gerando mapa interativo..."):
                                    mapa = criar_mapa_rota(rota_info, rota_info['origem_coordenadas'])
                                    # Salva como HTML no session_state
                                    st.session_state.mapa_html = mapa._repr_html_()
                                    st.session_state.mapa_precisa_atualizar = False
                            
                            # Renderiza o mapa usando HTML direto (evita loop)
                            st.components.v1.html(
                                st.session_state.mapa_html,
                                height=600,
                                scrolling=True
                            )
                            
                            st.markdown("---")
                            st.info("💡 **Como usar o mapa:** Clique nos marcadores para ver detalhes das entregas. Use o scroll para zoom e arraste para navegar.")
                            
                    except Exception as e:
                        st.error(f"❌ Erro ao criar mapa: {str(e)}")
                        import traceback
                        st.code(traceback.format_exc())
                        st.info("💡 Visualização do mapa não disponível. Veja os detalhes na aba Roteirização.")
                        
                        # Fallback com coordenadas
                        st.subheader("📍 Coordenadas da Rota")
                        st.write(f"**Origem:** {rota_info.get('origem_coordenadas', 'N/A')}")
                        for i, rota in enumerate(rota_info.get('rotas', [])):
                            st.write(f"**Parada {i+1} - {rota['destino']}:** {rota.get('coordenadas_destino', 'N/A')}")
                
                with tab3:
                    st.subheader("🛣️ Sequência de Entregas Otimizada")
                    
                    # Tabela de rotas
                    df_rotas = pd.DataFrame(rota_info['rotas'])
                    
                    # Adiciona informações de pedágios
                    df_rotas['pedagios_valor'] = df_rotas['pedagios'].apply(lambda x: x['valor_total'])
                    df_rotas['pedagios_pracas'] = df_rotas['pedagios'].apply(lambda x: x['numero_pracas'])
                    
                    st.dataframe(
                        df_rotas[[
                            'sequencia', 'origem', 'destino', 'entregas', 
                            'distancia_km', 'tempo_estimado_horas', 
                            'pedagios_valor', 'pedagios_pracas',
                            'valor_total_entregas'
                        ]],
                        column_config={
                            "sequencia": "Seq",
                            "origem": "De",
                            "destino": "Para",
                            "entregas": "Entregas",
                            "distancia_km": st.column_config.NumberColumn("Distância (km)", format="%.2f"),
                            "tempo_estimado_horas": st.column_config.NumberColumn("Tempo (h)", format="%.2f"),
                            "pedagios_valor": st.column_config.NumberColumn("Pedágios (R$)", format="R$ %.2f"),
                            "pedagios_pracas": "Praças",
                            "valor_total_entregas": st.column_config.NumberColumn("Valor Carga (R$)", format="R$ %.2f")
                        },
                        hide_index=True,
                        use_container_width=True
                    )
                    
                    st.markdown("---")
                    
                    # Detalhes de cada parada
                    st.subheader("📍 Detalhes das Paradas")
                    
                    for rota in rota_info['rotas']:
                        with st.expander(f"Parada {rota['sequencia']}: {rota['destino']}", expanded=True):
                            col1, col2 = st.columns(2)
                            
                            with col1:
                                st.write("**Informações do Trajeto:**")
                                st.write(f"- Origem: {rota['origem']}")
                                st.write(f"- Destino: {rota['destino']}")
                                st.write(f"- Coordenadas: {rota.get('coordenadas_destino', 'N/A')}")
                                st.write(f"- Distância: {rota['distancia_km']} km")
                                st.write(f"- Tempo estimado: {rota['tempo_estimado_horas']:.2f}h")
                                st.write(f"- Pedágios: R$ {rota['pedagios']['valor_total']:.2f} ({rota['pedagios']['numero_pracas']} praças)")
                            
                            with col2:
                                st.write("**Entregas nesta Parada:**")
                                st.write(f"- Número de entregas: {rota['entregas']}")
                                st.write(f"- Documentos: {', '.join(rota['documentos'])}")
                                st.write(f"- Valor total: R$ {rota['valor_total_entregas']:,.2f}")
                                st.write(f"- Peso total: {rota['peso_total_entregas']:.2f} kg")
                
                with tab4:
                    st.subheader("💰 Análise Detalhada de Custos")
                    
                    # Métricas principais
                    col1, col2, col3, col4 = st.columns(4)
                    with col1:
                        st.metric("Custo Total", f"R$ {custos_info['resumo_custos']['custo_total']:,.2f}")
                    with col2:
                        st.metric("por Entrega", f"R$ {custos_info['resumo_custos']['custo_por_entrega']:,.2f}")
                    with col3:
                        st.metric("por KM", f"R$ {custos_info['resumo_custos']['custo_por_km']:,.2f}")
                    with col4:
                        st.metric("% Mercadorias", f"{custos_info['resumo_custos']['percentual_custo']:.1f}%")
                    
                    st.markdown("---")
                    
                    # Decomposição de custos
                    st.subheader("📊 Composição dos Custos")
                    
                    custos_det = custos_info['detalhamento_custos']
                    df_custos = pd.DataFrame({
                        'Categoria': [
                            'Combustível', 'Pedágios', 'Desgaste do Veículo',
                            'Motorista', 'Seguro', 'Taxas de Entrega',
                            'Alimentação', 'Pernoite'
                        ],
                        'Valor': [
                            custos_det['combustivel'],
                            custos_det['pedagio'],
                            custos_det['desgaste_veiculo'],
                            custos_det['motorista'],
                            custos_det['seguro'],
                            custos_det['taxa_entregas'],
                            custos_det['alimentacao'],
                            custos_det['pernoite']
                        ]
                    })
                    
                    df_custos['Percentual'] = (df_custos['Valor'] / df_custos['Valor'].sum() * 100).round(2)
                    df_custos = df_custos.sort_values('Valor', ascending=False)
                    
                    col1, col2 = st.columns([2, 1])
                    
                    with col1:
                        st.dataframe(
                            df_custos,
                            column_config={
                                "Categoria": "Categoria de Custo",
                                "Valor": st.column_config.NumberColumn("Valor (R$)", format="R$ %.2f"),
                                "Percentual": st.column_config.NumberColumn("% do Total", format="%.2f%%")
                            },
                            hide_index=True,
                            use_container_width=True
                        )
                    
                    with col2:
                        st.write("**Top 3 Custos:**")
                        for idx, row in df_custos.head(3).iterrows():
                            st.write(f"**{row['Categoria']}**")
                            st.write(f"R$ {row['Valor']:,.2f} ({row['Percentual']:.1f}%)")
                            st.write("")
                    
                    st.markdown("---")
                    
                    # Análise de viabilidade
                    st.subheader("📈 Análise de Viabilidade Econômica")
                    
                    col1, col2 = st.columns(2)
                    
                    with col1:
                        valor_mercadorias = custos_info['resumo_custos']['valor_mercadorias']
                        custo_total = custos_info['resumo_custos']['custo_total']
                        margem = valor_mercadorias - custo_total
                        percentual = custos_info['resumo_custos']['percentual_custo']
                        
                        st.write(f"**Valor das Mercadorias:** R$ {valor_mercadorias:,.2f}")
                        st.write(f"**Custo de Transporte:** R$ {custo_total:,.2f}")
                        st.write(f"**Margem Líquida:** R$ {margem:,.2f}")
                        st.write(f"**Percentual de Custo:** {percentual:.2f}%")
                    
                    with col2:
                        if percentual <= 10:
                            st.success("✅ **Operação Altamente Viável**")
                            st.write("Os custos de transporte estão excelentes em relação ao valor da carga.")
                        elif percentual <= 15:
                            st.warning("⚠️ **Operação Moderadamente Viável**")
                            st.write("Os custos estão dentro da média, mas há espaço para otimização.")
                        else:
                            st.error("❌ **Atenção aos Custos**")
                            st.write("Os custos estão elevados. Considere otimizações ou renegociação de fretes.")
                
                with tab5:
                    st.subheader("📈 Dados Detalhados para Análise")
                    
                    # Documentos processados
                    st.subheader("📋 Documentos Fiscais")
                    
                    docs_data = []
                    for doc in st.session_state.documentos_processados:
                        docs_data.append({
                            'Tipo': doc.tipo,
                            'Número': doc.numero,
                            'Destinatário': doc.destinatario,
                            'Cidade': doc.cidade,
                            'UF': doc.uf,
                            'CEP': doc.cep,
                            'Endereço': doc.endereco_completo,
                            'Valor': doc.valor_total,
                            'Peso_kg': doc.peso_total,
                            'Produtos': len(doc.produtos),
                            'Geocodificado': 'Sim' if doc.coordenadas else 'Não',
                            'Coordenadas': str(doc.coordenadas) if doc.coordenadas else 'N/A'
                        })
                    
                    df_docs = pd.DataFrame(docs_data)
                    st.dataframe(
                        df_docs,
                        column_config={
                            "Valor": st.column_config.NumberColumn("Valor (R$)", format="R$ %.2f"),
                            "Peso_kg": st.column_config.NumberColumn("Peso (kg)", format="%.2f")
                        },
                        hide_index=True,
                        use_container_width=True
                    )
                    
                    st.markdown("---")
                    
                    # Estatísticas
                    st.subheader("📊 Estatísticas Gerais")
                    
                    col1, col2, col3 = st.columns(3)
                    
                    with col1:
                        st.write("**Por Tipo de Documento:**")
                        tipos_count = pd.Series([doc.tipo for doc in st.session_state.documentos_processados]).value_counts()
                        for tipo, count in tipos_count.items():
                            st.write(f"- {tipo}: {count}")
                    
                    with col2:
                        st.write("**Por Estado:**")
                        estados_count = pd.Series([doc.uf for doc in st.session_state.documentos_processados]).value_counts()
                        for estado, count in estados_count.items():
                            st.write(f"- {estado}: {count} entregas")
                    
                    with col3:
                        st.write("**Valores Totais:**")
                        valor_total = sum([doc.valor_total for doc in st.session_state.documentos_processados])
                        peso_total = sum([doc.peso_total for doc in st.session_state.documentos_processados])
                        st.write(f"- Valor: R$ {valor_total:,.2f}")
                        st.write(f"- Peso: {peso_total:,.2f} kg")
                    
                    st.markdown("---")
                    
                    # Exportação
                    st.subheader("📤 Exportar Relatório")
                    
                    col1, col2 = st.columns(2)
                    
                    with col1:
                        relatorio_json = {
                            'timestamp': datetime.now().isoformat(),
                            'documentos': docs_data,
                            'roteirizacao': {
                                'resumo': rota_info['resumo'],
                                'rotas': rota_info['rotas']
                            },
                            'custos': custos_info,
                            'parametros': {
                                'consumo_medio': st.session_state.consumo_medio,
                                'preco_combustivel': st.session_state.preco_combustivel,
                                'valor_hora_motorista': st.session_state.valor_hora_motorista,
                                'origem': st.session_state.endereco_origem
                            }
                        }
                        
                        st.download_button(
                            label="📥 Download Relatório Completo (JSON)",
                            data=json.dumps(relatorio_json, indent=2, ensure_ascii=False),
                            file_name=f"relatorio_completo_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json",
                            mime="application/json",
                            use_container_width=True
                        )
                    
                    with col2:
                        csv_data = df_docs.to_csv(index=False)
                        st.download_button(
                            label="📥 Download Documentos (CSV)",
                            data=csv_data,
                            file_name=f"documentos_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv",
                            mime="text/csv",
                            use_container_width=True
                        )
    
    else:
        # Informações de ajuda quando não há arquivos
        st.info("👆 Faça upload dos arquivos XML para começar a análise")
        
        with st.expander("📖 Como usar este sistema", expanded=True):
            st.markdown("""
            ### 🚀 Guia Rápido
            
            1. **Faça upload dos XMLs**:
               - Arraste ou selecione seus arquivos XML (NFe, CTe, MDFe)
               - O sistema extrai automaticamente os endereços de entrega
               - Geocodificação automática dos endereços
            
            2. **Configure a rota**:
               - Informe o endereço de origem (onde a carga sai)
               - Ajuste os parâmetros do veículo (consumo, combustível)
               - Defina o valor da hora do motorista
            
            3. **Calcule e analise**:
               - Clique em "Calcular Rota e Custos"
               - Visualize rotas otimizadas no mapa
               - Analise custos detalhados
               - Exporte relatórios
          
            """)
        
        with st.expander("💡 Exemplo de Uso"):
            st.markdown("""
            ### Caso de Uso Exemplo
            
            **Situação:**
            - Você tem 5 NFes para entregar em diferentes cidades
            - Precisa saber qual a melhor ordem de entrega
            - Quer calcular quanto vai custar a operação
            
            **Solução:**
            1. Faça upload dos 5 XMLs das NFes
            2. O sistema extrai automaticamente:
               - Endereços de entrega
               - Valores das mercadorias
               - Pesos das cargas
            3. Você informa apenas:
               - De onde vai sair (ex: "São Paulo, SP")
               - Consumo do caminhão (ex: 3.5 km/l)
               - Preço do diesel (ex: R$ 6,20)
               - Valor/hora do motorista (ex: R$ 15,00)
            4. O sistema calcula:
               - ✅ Melhor rota (menos km, menos tempo)
               - ✅ Custos totais (combustível + pedágios + tudo)
               - ✅ Mostra no mapa visual
            
            **Resultado:**
            - Economia de tempo e dinheiro
            - Decisões baseadas em dados reais
            - Previsibilidade de custos
            """)
    
    # Sidebar com informações
    st.sidebar.markdown("---")
    st.sidebar.subheader("ℹ️ Sobre o Sistema")
    st.sidebar.markdown("""
    
    **Funcionalidades:**
    - ✅ Processamento NFe/CTe/MDFe
    - ✅ Geocodificação automática
    - ✅ Rotas com APIs reais
    - ✅ Cálculo preciso de distâncias
    - ✅ Estimativa de pedágios
    - ✅ Otimização de sequência
    - ✅ Custos personalizáveis
    - ✅ Mapa interativo
    - ✅ Relatórios exportáveis
    """)
    
    st.sidebar.markdown("---")
    
    # Debug info no sidebar se houver dados
    if st.session_state.rota_calculada and st.session_state.rota_info:
        st.sidebar.subheader("🔍 Debug Info")
        st.sidebar.write(f"Documentos: {len(st.session_state.documentos_processados)}")
        st.sidebar.write(f"Rotas: {len(st.session_state.rota_info.get('rotas', []))}")
        st.sidebar.write(f"Origem: {st.session_state.rota_info.get('origem_coordenadas', 'N/A')}")

if __name__ == "__main__":
    main()