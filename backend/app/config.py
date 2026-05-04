from pydantic_settings import BaseSettings
from typing import List


class Settings(BaseSettings):
    POWER_AUTOMATE_URL: str = ""

    ALLOWED_ORIGINS: str = "http://localhost:5173,http://localhost:3000,https://delightful-ocean-0ea4d0b00.7.azurestaticapps.net,https://pkd-declaration.azurewebsites.net"

    AZURE_STORAGE_CONNECTION_STRING: str = ""
    AZURE_CONTAINER_NAME: str = "dev-aaw"
    AZURE_FOLDER_NAME: str = "test"

    # ── Azure Document Intelligence (best OCR for structured forms) ──
    AZURE_DOC_INTEL_ENDPOINT: str = ""
    AZURE_DOC_INTEL_KEY: str = ""

    @property
    def use_azure_doc_intel(self) -> bool:
        return bool(self.AZURE_DOC_INTEL_ENDPOINT and self.AZURE_DOC_INTEL_KEY)

    @property
    def allowed_origins_list(self) -> List[str]:
        return [o.strip() for o in self.ALLOWED_ORIGINS.split(",") if o.strip()]

    model_config = {"env_file": ".env", "extra": "ignore"}


settings = Settings()

