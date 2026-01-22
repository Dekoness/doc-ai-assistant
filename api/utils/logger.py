"""
Logger personalizado compatible con Windows (sin emojis Unicode).
Proporciona logging estructurado para debugging.
"""


class Logger:
    """Logger simple compatible con consola Windows"""
    
    def __init__(self, name: str = "Agent"):
        self.name = name
    
    def _print(self, level: str, message: str):
        print(f"[{level}] {message}")
    
    def info(self, message: str):
        self._print("INFO", message)
    
    def warn(self, message: str):
        self._print("WARN", message)
    
    def error(self, message: str):
        self._print("ERROR", message)
    
    def debug(self, message: str):
        self._print("DEBUG", message)
    
    def success(self, message: str):
        self._print("OK", message)
    
    def section(self, title: str):
        """Imprime un separador de seccion"""
        print("\n" + "=" * 80)
        print(f"[{title}]")
        print("=" * 80)


# Logger global
logger = Logger()
