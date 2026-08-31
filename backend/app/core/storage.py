import io
import logging
import os
import re
import uuid
from typing import Any, Dict, List, Optional, Tuple, Union
from fastapi import UploadFile

from app.config import settings
from app.core.exceptions import BadRequestException, NotFoundException

logger = logging.getLogger("app.core.storage")

# In-memory storage mock registry for offline testing / development fallback
_local_mock_storage: Dict[str, bytes] = {}


def sanitize_filename(filename: Optional[str]) -> str:
    """
    Sanitizes client-supplied filename to prevent path traversal,
    injection of special directory characters, control codes, and unsafe extensions.
    """
    if not filename or not filename.strip():
        return f"document_{uuid.uuid4().hex[:8]}.pdf"

    # Strip directory components if any are included in client filename
    base_name = os.path.basename(filename.strip().replace("\\", "/"))

    # Remove null bytes and control characters
    base_name = re.sub(r"[\x00-\x1f\x7f]", "", base_name)

    # Replace unsafe characters with underscore, keeping alphanumeric, dots, underscores, and hyphens
    clean_name = re.sub(r"[^a-zA-Z0-9_.\-]", "_", base_name)

    # Remove leading dots to prevent hidden files or relative path confusion
    clean_name = clean_name.lstrip(".")

    # Prevent multiple consecutive dots to avoid extension confusion
    clean_name = re.sub(r"\.{2,}", ".", clean_name)

    # Limit filename length to 255 characters
    if len(clean_name) > 255:
        ext = os.path.splitext(clean_name)[1]
        clean_name = clean_name[: 255 - len(ext)] + ext

    if not clean_name:
        clean_name = f"document_{uuid.uuid4().hex[:8]}.pdf"

    return clean_name


def sanitize_path_segment(segment: str) -> str:
    """Sanitizes an individual directory segment (e.g. tender_id, bidder_id, doc_type)."""
    clean_segment = re.sub(r"[^a-zA-Z0-9_-]", "_", str(segment).strip())
    clean_segment = re.sub(r"_+", "_", clean_segment)
    return clean_segment.strip("_") or "default"



def validate_storage_path(storage_path: str) -> str:
    """
    Validates that a storage path does not contain traversal sequences
    or illegal characters. Raises BadRequestException if invalid.
    """
    if not storage_path or not storage_path.strip():
        raise BadRequestException(message="Storage path cannot be empty.")

    normalized = storage_path.strip().replace("\\", "/")

    # Reject path traversal patterns
    if (
        ".." in normalized
        or normalized.startswith("/")
        or normalized.startswith("./")
        or "\x00" in normalized
        or ":" in normalized
    ):
        raise BadRequestException(message="Invalid or unsafe storage path detected.")

    return normalized


def generate_tender_storage_path(
    tender_id: Union[uuid.UUID, str],
    filename: str,
    unique_prefix: bool = True,
) -> str:
    """
    Generates canonical server-side storage path for tender documents.
    Hierarchy: tenders/{tender_id}/{filename}
    """
    clean_id = sanitize_path_segment(str(tender_id))
    clean_name = sanitize_filename(filename)
    if unique_prefix:
        file_id = uuid.uuid4().hex[:8]
        final_filename = f"{file_id}_{clean_name}"
    else:
        final_filename = clean_name
    return validate_storage_path(f"tenders/{clean_id}/{final_filename}")


def generate_bidder_storage_path(
    bidder_id: Union[uuid.UUID, str],
    document_type: Any,
    filename: str,
    unique_prefix: bool = True,
) -> str:
    """
    Generates canonical server-side storage path for bidder compliance documents.
    Hierarchy: bidders/{bidder_id}/{document_type}/{filename}
    """
    clean_id = sanitize_path_segment(str(bidder_id))
    type_str = document_type.value if hasattr(document_type, "value") else str(document_type)
    clean_type = sanitize_path_segment(type_str.upper())
    clean_name = sanitize_filename(filename)
    if unique_prefix:
        file_id = uuid.uuid4().hex[:8]
        final_filename = f"{file_id}_{clean_name}"
    else:
        final_filename = clean_name
    return validate_storage_path(f"bidders/{clean_id}/{clean_type}/{final_filename}")


class SupabaseStorageService:
    """
    Dedicated Service abstraction for Supabase Storage.
    Encapsulates all Supabase SDK calls, credentials management,
    path sanitization, file validation, and mock fallback for tests.
    """

    def __init__(
        self,
        bucket: Optional[str] = None,
        supabase_url: Optional[str] = None,
        service_role_key: Optional[str] = None,
    ):
        self.bucket = bucket or settings.SUPABASE_STORAGE_BUCKET
        self.supabase_url = supabase_url or settings.SUPABASE_URL
        self.service_role_key = service_role_key or settings.SUPABASE_SERVICE_ROLE_KEY
        self._client = None

    def _get_client(self):
        """Initializes and caches the Supabase client when credentials are present."""
        if self._client is not None:
            return self._client

        if self.supabase_url and self.service_role_key:
            try:
                from supabase import create_client
                self._client = create_client(self.supabase_url, self.service_role_key)
                return self._client
            except Exception as e:
                logger.warning(
                    f"Could not initialize real Supabase client: {e}. Falling back to mock storage."
                )
                return None
        return None

    @property
    def is_connected(self) -> bool:
        """Returns True if the service has an active Supabase client instance."""
        return self._get_client() is not None

    async def validate_upload_file(
        self,
        file: UploadFile,
        allowed_mime_types: Optional[List[str]] = None,
        max_size_mb: Optional[int] = None,
    ) -> Tuple[bytes, str, int]:
        """
        Validates the incoming UploadFile for size, MIME type, and magic bytes.
        Returns the byte content, verified MIME type, and content length.
        """
        from app.core.validation import validate_single_upload_file

        val_file = await validate_single_upload_file(
            file=file,
            allowed_mime_types=allowed_mime_types,
            max_size_mb=max_size_mb,
        )
        return val_file.content, val_file.mime_type, val_file.file_size


    def upload(
        self,
        storage_path: str,
        file_content: bytes,
        mime_type: str = "application/pdf",
        upsert: bool = True,
    ) -> str:
        """
        Uploads binary content to Supabase Storage bucket and returns the storage path.
        Falls back to local mock store when running in disconnected test mode.
        """
        valid_path = validate_storage_path(storage_path)
        client = self._get_client()

        if client is not None:
            try:
                storage = client.storage.from_(self.bucket)
                storage.upload(
                    path=valid_path,
                    file=file_content,
                    file_options={
                        "content-type": mime_type,
                        "upsert": "true" if upsert else "false",
                    },
                )
                logger.info(f"Uploaded file to Supabase Storage: bucket={self.bucket}, path={valid_path}")
                return valid_path
            except Exception as e:
                logger.error(f"Failed to upload file to Supabase Storage: {e}")
                raise BadRequestException(message="Failed to persist file in cloud storage.")
        else:
            # Local/Test mock persistence
            _local_mock_storage[valid_path] = file_content
            logger.info(f"Saved file to mock storage: {valid_path}")
            return valid_path

    def download(self, storage_path: str) -> bytes:
        """
        Downloads and returns the raw file bytes from Supabase Storage or mock storage.
        """
        valid_path = validate_storage_path(storage_path)
        client = self._get_client()

        if client is not None:
            try:
                storage = client.storage.from_(self.bucket)
                data = storage.download(valid_path)
                return data
            except Exception as e:
                logger.error(f"Failed to download file from Supabase Storage: {e}")
                raise NotFoundException(message=f"File not found at storage path: {valid_path}")
        else:
            if valid_path in _local_mock_storage:
                return _local_mock_storage[valid_path]
            raise NotFoundException(message=f"File not found at storage path: {valid_path}")

    def delete(self, storage_path: str) -> bool:
        """Removes a file from Supabase Storage or mock storage."""
        try:
            valid_path = validate_storage_path(storage_path)
        except BadRequestException:
            return False

        client = self._get_client()
        if client is not None:
            try:
                storage = client.storage.from_(self.bucket)
                storage.remove([valid_path])
                logger.info(f"Removed file from Supabase Storage: bucket={self.bucket}, path={valid_path}")
                return True
            except Exception as e:
                logger.error(f"Failed to delete file from Supabase Storage: {e}")
                return False
        else:
            if valid_path in _local_mock_storage:
                del _local_mock_storage[valid_path]
            return True

    def delete_batch(self, storage_paths: List[str]) -> bool:
        """Batch removes multiple files from Supabase Storage or mock storage."""
        if not storage_paths:
            return True

        valid_paths = []
        for p in storage_paths:
            try:
                valid_paths.append(validate_storage_path(p))
            except BadRequestException:
                continue

        if not valid_paths:
            return False

        client = self._get_client()
        if client is not None:
            try:
                storage = client.storage.from_(self.bucket)
                storage.remove(valid_paths)
                logger.info(f"Batch removed {len(valid_paths)} files from Supabase Storage")
                return True
            except Exception as e:
                logger.error(f"Failed to batch delete files from Supabase Storage: {e}")
                return False
        else:
            for p in valid_paths:
                if p in _local_mock_storage:
                    del _local_mock_storage[p]
            return True

    def exists(self, storage_path: str) -> bool:
        """Checks if a file exists at the given storage path."""
        try:
            valid_path = validate_storage_path(storage_path)
        except BadRequestException:
            return False

        client = self._get_client()
        if client is not None:
            try:
                parent_dir = os.path.dirname(valid_path)
                file_name = os.path.basename(valid_path)
                storage = client.storage.from_(self.bucket)
                file_list = storage.list(parent_dir)
                return any(item.get("name") == file_name for item in file_list)
            except Exception as e:
                logger.error(f"Error checking file existence in Supabase Storage: {e}")
                return False
        else:
            return valid_path in _local_mock_storage

    def get_signed_url(self, storage_path: str, expires_in: int = 3600) -> Optional[str]:
        """Generates a secure, temporary pre-signed URL for document retrieval."""
        try:
            valid_path = validate_storage_path(storage_path)
        except BadRequestException:
            return None

        client = self._get_client()
        if client is not None:
            try:
                storage = client.storage.from_(self.bucket)
                res = storage.create_signed_url(valid_path, expires_in=expires_in)
                if isinstance(res, dict) and "signedURL" in res:
                    return res["signedURL"]
                elif isinstance(res, dict) and "signedUrl" in res:
                    return res["signedUrl"]
                return str(res)
            except Exception as e:
                logger.error(f"Failed to generate signed URL: {e}")
                return None
        else:
            return f"https://mock-storage.local/{self.bucket}/{valid_path}?token=mock_signed_token"

    def get_public_url(self, storage_path: str) -> str:
        """Generates a public URL for the storage path."""
        valid_path = validate_storage_path(storage_path)
        client = self._get_client()
        if client is not None:
            try:
                storage = client.storage.from_(self.bucket)
                return storage.get_public_url(valid_path)
            except Exception as e:
                logger.error(f"Failed to generate public URL: {e}")
                return f"{self.supabase_url}/storage/v1/object/public/{self.bucket}/{valid_path}"
        return f"https://mock-storage.local/{self.bucket}/{valid_path}"


# Singleton instance configured from application settings
storage_service = SupabaseStorageService()
