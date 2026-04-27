from pydantic_settings import BaseSettings
from typing import List


class Settings(BaseSettings):
    POWER_AUTOMATE_URL: str = ""

    TESSERACT_CMD: str = "tesseract"

    ALLOWED_ORIGINS: str = "http://localhost:5173,http://localhost:3000"

    AZURE_STORAGE_CONNECTION_STRING: str = ""
    AZURE_CONTAINER_NAME: str = "dev-aaw"
    AZURE_FOLDER_NAME: str = "test"

    @property
    def allowed_origins_list(self) -> List[str]:
        return [o.strip() for o in self.ALLOWED_ORIGINS.split(",") if o.strip()]

    model_config = {"env_file": ".env", "extra": "ignore"}


settings = Settings()
