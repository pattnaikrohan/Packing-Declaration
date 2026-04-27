import logging
import uuid
from azure.storage.blob import BlobServiceClient
from app.config import settings
from pathlib import Path

logger = logging.getLogger(__name__)

async def upload_to_blob_storage(file_bytes: bytes, filename: str) -> str:
    """
    Uploads a file to Azure Blob Storage if configured.
    Returns the URL of the uploaded blob, or None if upload was skipped or failed.
    """
    if not settings.AZURE_STORAGE_CONNECTION_STRING:
        logger.info("Azure Storage connection string not configured. Skipping upload.")
        return None

    try:
        blob_service_client = BlobServiceClient.from_connection_string(settings.AZURE_STORAGE_CONNECTION_STRING)
        container_client = blob_service_client.get_container_client(settings.AZURE_CONTAINER_NAME)
        
        # Create container if it doesn't exist
        if not container_client.exists():
            container_client.create_container()
            
        # Use the exact filename without any UUID
        blob_name = filename
        if hasattr(settings, 'AZURE_FOLDER_NAME') and settings.AZURE_FOLDER_NAME:
            # Ensure folder name doesn't end with a slash and combine
            folder = settings.AZURE_FOLDER_NAME.strip('/')
            blob_name = f"{folder}/{filename}"
            
        blob_client = blob_service_client.get_blob_client(container=settings.AZURE_CONTAINER_NAME, blob=blob_name)
        
        logger.info(f"Uploading {filename} to Azure Blob Storage as {blob_name}...")
        blob_client.upload_blob(file_bytes, overwrite=True)
        logger.info(f"Successfully uploaded {filename} to Azure Blob Storage.")
        
        return blob_client.url
        
    except Exception as e:
        logger.error(f"Failed to upload to Azure Blob Storage: {e}")
        return None

async def clear_blob_storage():
    """
    Deletes all blobs in the configured container/folder.
    """
    if not settings.AZURE_STORAGE_CONNECTION_STRING:
        return
        
    try:
        blob_service_client = BlobServiceClient.from_connection_string(settings.AZURE_STORAGE_CONNECTION_STRING)
        container_client = blob_service_client.get_container_client(settings.AZURE_CONTAINER_NAME)
        
        if not container_client.exists():
            return
            
        folder_prefix = ""
        if hasattr(settings, 'AZURE_FOLDER_NAME') and settings.AZURE_FOLDER_NAME:
            folder_prefix = settings.AZURE_FOLDER_NAME.strip('/') + "/"
            
        blob_list = container_client.list_blobs(name_starts_with=folder_prefix)
        for blob in blob_list:
            container_client.delete_blob(blob.name)
            logger.info(f"Deleted previous blob: {blob.name}")
            
    except Exception as e:
        logger.error(f"Failed to clear Azure Blob Storage: {e}")
