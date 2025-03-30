from azure.storage.blob import BlobServiceClient
from urllib.parse import urlparse
import os

AZURE_CONNECTION_STRING = os.getenv("AZURE_STORAGE_CONNECTION_STRING")
CONTAINER_NAME = "message-attachments"

def delete_blob_by_url(blob_url: str):
    blob_service = BlobServiceClient.from_connection_string(AZURE_CONNECTION_STRING)
    parsed_url = urlparse(blob_url)
    blob_name = parsed_url.path.lstrip(f"/{CONTAINER_NAME}/")
    blob_client = blob_service.get_blob_client(container=CONTAINER_NAME, blob=blob_name)
    blob_client.delete_blob()