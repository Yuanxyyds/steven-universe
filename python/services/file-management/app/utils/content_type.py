"""
Content-Type detection utilities.
Auto-detect MIME types from file extensions.
"""

import mimetypes
from typing import Optional


def detect_content_type(filename: str, provided_type: Optional[str] = None) -> str:
    """
    Detect Content-Type from filename extension.

    Falls back to provided type if detection fails, or 'application/octet-stream' as last resort.

    Args:
        filename: Filename or path (e.g., "document.pdf", "path/to/file.tar.gz")
        provided_type: Optional explicitly provided Content-Type from client

    Returns:
        MIME type string (e.g., "application/pdf", "image/jpeg")

    Examples:
        >>> detect_content_type("document.pdf")
        'application/pdf'

        >>> detect_content_type("photo.jpg")
        'image/jpeg'

        >>> detect_content_type("model.tar.gz")
        'application/gzip'

        >>> detect_content_type("unknown.xyz")
        'application/octet-stream'

        >>> detect_content_type("file.txt", "text/custom")
        'text/custom'  # Respects provided type
    """
    # If client provided a specific type (not generic), use it
    if provided_type and provided_type != "application/octet-stream":
        return provided_type

    # Try to guess from file extension
    guessed_type, _ = mimetypes.guess_type(filename)

    # Priority: guessed > provided > fallback
    return guessed_type or provided_type or "application/octet-stream"


# Common MIME type mappings for reference
COMMON_MIME_TYPES = {
    # Documents
    ".pdf": "application/pdf",
    ".doc": "application/msword",
    ".docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    ".xls": "application/vnd.ms-excel",
    ".xlsx": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    ".ppt": "application/vnd.ms-powerpoint",
    ".pptx": "application/vnd.openxmlformats-officedocument.presentationml.presentation",

    # Images
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".png": "image/png",
    ".gif": "image/gif",
    ".webp": "image/webp",
    ".svg": "image/svg+xml",
    ".ico": "image/x-icon",

    # Video
    ".mp4": "video/mp4",
    ".webm": "video/webm",
    ".avi": "video/x-msvideo",
    ".mov": "video/quicktime",
    ".mkv": "video/x-matroska",

    # Audio
    ".mp3": "audio/mpeg",
    ".wav": "audio/wav",
    ".ogg": "audio/ogg",
    ".m4a": "audio/mp4",

    # Archives
    ".zip": "application/zip",
    ".tar": "application/x-tar",
    ".gz": "application/gzip",
    ".tar.gz": "application/gzip",
    ".tgz": "application/gzip",
    ".bz2": "application/x-bzip2",
    ".7z": "application/x-7z-compressed",
    ".rar": "application/x-rar-compressed",

    # Text
    ".txt": "text/plain",
    ".html": "text/html",
    ".css": "text/css",
    ".js": "application/javascript",
    ".json": "application/json",
    ".xml": "application/xml",
    ".csv": "text/csv",

    # Programming
    ".py": "text/x-python",
    ".java": "text/x-java-source",
    ".c": "text/x-c",
    ".cpp": "text/x-c++",
    ".h": "text/x-c",
    ".rs": "text/x-rust",
    ".go": "text/x-go",

    # Machine Learning Models
    ".safetensors": "application/octet-stream",  # SafeTensors model format
    ".ckpt": "application/octet-stream",  # PyTorch checkpoint
    ".pth": "application/octet-stream",  # PyTorch model
    ".pt": "application/octet-stream",  # PyTorch tensor
    ".onnx": "application/octet-stream",  # ONNX model format
    ".pb": "application/octet-stream",  # TensorFlow protobuf
    ".h5": "application/x-hdf",  # Keras/HDF5 model
    ".pkl": "application/octet-stream",  # Python pickle
    ".joblib": "application/octet-stream",  # Joblib serialized

    # Other
    ".bin": "application/octet-stream",
    ".exe": "application/x-msdownload",
    ".dmg": "application/x-apple-diskimage",
    ".iso": "application/x-iso9660-image",
}
