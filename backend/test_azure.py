import asyncio
import os
from dotenv import load_dotenv
from app.config import settings
from app.azure_storage import upload_to_blob_storage

load_dotenv()

async def main():
    print(f"Connection String: {settings.AZURE_STORAGE_CONNECTION_STRING[:30]}...")
    print(f"Container: {settings.AZURE_CONTAINER_NAME}")
    print(f"Folder: {settings.AZURE_FOLDER_NAME}")
    
    file_bytes = b"Hello, World!"
    filename = "test_upload.txt"
    
    url = await upload_to_blob_storage(file_bytes, filename)
    print(f"Result URL: {url}")

if __name__ == "__main__":
    asyncio.run(main())
