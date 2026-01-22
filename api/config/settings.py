"""
Configuracion centralizada de la aplicacion.
Carga variables de entorno y proporciona acceso tipado.
"""
import os
from dataclasses import dataclass
from typing import Optional


@dataclass
class VisionConfig:
    """Configuracion de Azure Computer Vision"""
    key: Optional[str]
    endpoint: Optional[str]
    
    @property
    def is_configured(self) -> bool:
        return bool(self.key and self.endpoint)


@dataclass
class OpenAIConfig:
    """Configuracion de Azure OpenAI"""
    key: Optional[str]
    endpoint: Optional[str]
    deployment_name: str = "gpt-4.1-mini"
    api_version: str = "2024-08-01-preview"
    
    @property
    def is_configured(self) -> bool:
        return bool(self.key and self.endpoint)
    
    @property
    def chat_url(self) -> str:
        """Construye la URL completa para chat completions"""
        if 'deployments' in self.endpoint:
            return self.endpoint
        base = self.endpoint.rstrip('/')
        return f"{base}/openai/deployments/{self.deployment_name}/chat/completions?api-version={self.api_version}"


@dataclass
class SearchConfig:
    """Configuracion de Azure AI Search"""
    endpoint: Optional[str]
    key: Optional[str]
    index_name: str = "certificado-federico"
    
    @property
    def is_configured(self) -> bool:
        return bool(self.endpoint and self.key)


class Settings:
    """Configuracion global de la aplicacion"""
    
    def __init__(self):
        self.vision = VisionConfig(
            key=os.environ.get("VISION_KEY"),
            endpoint=os.environ.get("VISION_ENDPOINT")
        )
        
        self.openai = OpenAIConfig(
            key=os.environ.get("OPENAI_KEY"),
            endpoint=os.environ.get("OPENAI_ENDPOINT")
        )
        
        self.search = SearchConfig(
            endpoint=os.environ.get("SEARCH_ENDPOINT"),
            key=os.environ.get("SEARCH_ADMIN_KEY"),
            index_name=os.environ.get("SEARCH_INDEX_NAME", "certificado-federico")
        )
    
    def validate_required(self) -> tuple[bool, list[str]]:
        """Valida que las configuraciones requeridas esten presentes"""
        missing = []
        
        if not self.vision.key:
            missing.append("VISION_KEY")
        if not self.vision.endpoint:
            missing.append("VISION_ENDPOINT")
        if not self.openai.key:
            missing.append("OPENAI_KEY")
        if not self.openai.endpoint:
            missing.append("OPENAI_ENDPOINT")
        
        return len(missing) == 0, missing
    
    def print_status(self, logger):
        """Imprime el estado de la configuracion"""
        logger.info("Variables de entorno cargadas:")
        logger.info(f"  VISION_KEY: {'[OK]' if self.vision.key else '[X] MISSING'}")
        logger.info(f"  VISION_ENDPOINT: {self.vision.endpoint or '[X] MISSING'}")
        logger.info(f"  OPENAI_KEY: {'[OK]' if self.openai.key else '[X] MISSING'}")
        logger.info(f"  OPENAI_ENDPOINT: {self.openai.endpoint or '[X] MISSING'}")
        logger.info(f"  SEARCH_ENDPOINT: {self.search.endpoint or '[X] MISSING'}")
        logger.info(f"  SEARCH_KEY: {'[OK]' if self.search.key else '[X] MISSING'}")
        logger.info(f"  SEARCH_INDEX: {self.search.index_name}")


# Singleton de configuracion
settings = Settings()
