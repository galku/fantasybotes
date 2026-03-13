# gcs_utils.py
# JSON read/write backed by Google Cloud Storage when GCS_BUCKET is set,
# with automatic fallback to local files for development.
#
# On Cloud Run, no credentials config is needed — the service account is
# used automatically. Locally, run: gcloud auth application-default login

import os
import json

GCS_BUCKET = os.getenv("GCS_BUCKET")

_bucket = None


def _get_bucket():
    global _bucket
    if not GCS_BUCKET:
        return None
    if _bucket is None:
        from google.cloud import storage
        _bucket = storage.Client().bucket(GCS_BUCKET)
    return _bucket


def read_json(filename: str, default=None):
    if default is None:
        default = {}
    bucket = _get_bucket()
    if bucket:
        try:
            blob = bucket.blob(filename)
            if blob.exists():
                return json.loads(blob.download_as_text())
        except Exception as e:
            print(f"⚠️ GCS read feilet for '{filename}': {e}")
        return default
    # Local fallback
    if os.path.exists(filename):
        try:
            with open(filename, encoding="utf-8") as f:
                return json.load(f)
        except (json.JSONDecodeError, OSError):
            pass
    return default


def write_json(filename: str, data) -> None:
    bucket = _get_bucket()
    if bucket:
        try:
            blob = bucket.blob(filename)
            blob.upload_from_string(
                json.dumps(data, indent=2, ensure_ascii=False),
                content_type="application/json",
            )
            return
        except Exception as e:
            print(f"⚠️ GCS write feilet for '{filename}': {e}")
    # Local fallback
    try:
        with open(filename, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
    except OSError as e:
        print(f"⚠️ Lokal write feilet for '{filename}': {e}")
