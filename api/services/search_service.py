"""
Servicio de busqueda usando Azure AI Search.
Implementa RAG (Retrieval Augmented Generation) para buscar en la base de conocimiento.
"""
from typing import Optional, List
from azure.core.credentials import AzureKeyCredential
from azure.search.documents import SearchClient

from ..config import settings
from ..utils import logger


class SearchService:
    """Servicio de busqueda en Azure AI Search"""
    
    # Keywords que indican consultas genericas
    GENERIC_KEYWORDS = [
        'que certificados', 'cuales certificados', 'todos', 'certificaciones',
        'titulos', 'formacion', 'estudios', 'tiene federico', 'tiene zoppi',
        'lista', 'mostrar', 'ver todos'
    ]
    
    # Campos de busqueda para consultas especificas
    SEARCH_FIELDS = ['chunk', 'title', 'keyPhrases', 'persons', 'organizations']
    
    def __init__(self):
        self.config = settings.search
        self._client: Optional[SearchClient] = None
    
    @property
    def client(self) -> Optional[SearchClient]:
        """Cliente de Azure Search (lazy initialization)"""
        if self._client is None and self.config.is_configured:
            try:
                credential = AzureKeyCredential(self.config.key)
                self._client = SearchClient(
                    endpoint=self.config.endpoint,
                    index_name=self.config.index_name,
                    credential=credential
                )
                logger.success("Cliente de busqueda creado")
            except Exception as e:
                logger.error(f"Error creando cliente de busqueda: {str(e)}")
        
        return self._client
    
    def _is_generic_query(self, query: str) -> bool:
        """Determina si la consulta es generica (debe traer todos los docs)"""
        query_lower = query.lower()
        return any(kw in query_lower for kw in self.GENERIC_KEYWORDS)
    
    def _build_search_params(self, query: str, is_generic: bool) -> dict:
        """Construye los parametros de busqueda"""
        if is_generic:
            return {
                'search_text': '*',
                'top': 10,
                'include_total_count': True
            }
        
        return {
            'search_text': query,
            'search_mode': 'any',
            'search_fields': self.SEARCH_FIELDS,
            'top': 5,
            'include_total_count': True
        }
    
    def _format_document(self, result: dict, index: int) -> Optional[str]:
        """Formatea un documento para incluir en el contexto"""
        content = result.get('chunk', '')
        
        if not content or len(content) <= 20:
            return None
        
        title = result.get('title', f'doc_{index}')
        persons = result.get('persons', [])
        organizations = result.get('organizations', [])
        locations = result.get('locations', [])
        key_phrases = result.get('keyPhrases', [])
        
        # Construir documento enriquecido
        formatted = f"[DOC: {title}]\n\n"
        
        if persons:
            formatted += f"Personas: {', '.join(persons)}\n"
        if organizations:
            formatted += f"Organizaciones: {', '.join(organizations)}\n"
        if locations:
            formatted += f"Ubicaciones: {', '.join(locations)}\n"
        if key_phrases:
            formatted += f"Palabras clave: {', '.join(key_phrases[:7])}\n"
        
        formatted += f"\n{content[:1200]}"
        
        return formatted
    
    def _log_document(self, result: dict, index: int):
        """Loguea informacion de un documento"""
        logger.info(f"--- DOCUMENTO {index} ---")
        logger.debug(f"   Keys: {list(result.keys())}")
        logger.info(f"   Titulo: {result.get('title', 'N/A')}")
        logger.info(f"   Score: {result.get('@search.score', 0)}")
        logger.info(f"   Contenido: {len(result.get('chunk', ''))} chars")
    
    def search(self, query: str) -> str:
        """
        Busca en la base de conocimiento y retorna contexto relevante.
        
        Args:
            query: Consulta del usuario
            
        Returns:
            Contexto formateado para RAG o string vacio si no hay resultados
        """
        if not self.config.is_configured:
            logger.warn("Search Service no configurado - RAG deshabilitado")
            return ""
        
        if not self.client:
            logger.error("No se pudo crear cliente de busqueda")
            return ""
        
        try:
            logger.section("BUSQUEDA EN BASE DE CONOCIMIENTO")
            logger.info(f"Endpoint: {self.config.endpoint}")
            logger.info(f"Indice: {self.config.index_name}")
            logger.info(f"Query: '{query[:200]}...'")
            
            # Determinar tipo de busqueda
            is_generic = self._is_generic_query(query)
            logger.info(f"Tipo: {'GENERICA' if is_generic else 'ESPECIFICA'}")
            
            # Ejecutar busqueda
            search_params = self._build_search_params(query, is_generic)
            results = self.client.search(**search_params)
            
            # Procesar resultados
            context_parts: List[str] = []
            result_count = 0
            
            for result in results:
                result_count += 1
                self._log_document(result, result_count)
                
                formatted = self._format_document(result, result_count)
                if formatted:
                    context_parts.append(formatted)
                    logger.success(f"   Documento {result_count} agregado al contexto")
                else:
                    logger.warn(f"   Documento {result_count} descartado (contenido insuficiente)")
            
            # Resumen
            logger.info(f"\nRESUMEN: {result_count} docs procesados, {len(context_parts)} incluidos")
            
            if context_parts:
                final_context = "\n\n" + "=" * 60 + "\n\n".join(context_parts)
                logger.success(f"Contexto final: {len(final_context)} caracteres")
                return final_context
            
            logger.warn("Sin contexto para devolver")
            return ""
            
        except Exception as e:
            logger.error(f"Error en busqueda: {str(e)}")
            import traceback
            traceback.print_exc()
            return ""


# Instancia singleton del servicio
search_service = SearchService()
