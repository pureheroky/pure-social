from google.cloud import storage
import uuid
from datetime import datetime, timezone
from core.config import get_settings

settings = get_settings()


class GCSManager:
    def __init__(self, bucket_name: str):
        self.client = storage.Client.from_service_account_json(
            settings.GCS_CREDENTIALS_PATH
        )
        self._bucket_name = bucket_name

    def bucket_name(self):
        return self._bucket_name

    def upload_file(
        self, file, file_extension: str, user_id: int, bucket_name: str | None = None
    ) -> str:
        current_bucket_name = bucket_name or self._bucket_name
        bucket = self.client.bucket(current_bucket_name)

        timestamp = datetime.now(timezone.utc).strftime("%Y%m%d%H%M%S")
        blob_name = (
            f"avatars/user_{user_id}_{timestamp}_{uuid.uuid4().hex}{file_extension}"
        )
        blob = bucket.blob(blob_name)

        blob.upload_from_file(file, content_type=f"image/{file_extension.lstrip(".")}")
        return blob.public_url

    def delete_file(self, blob_name: str, bucket_name: str | None = None):
        current_bucket_name = bucket_name or self._bucket_name
        bucket = self.client.bucket(current_bucket_name)
        blob = bucket.blob(blob_name)
        blob.delete()
