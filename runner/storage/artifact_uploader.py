"""MinIO / S3 artifact uploader — Task 29: upload video, screenshots, logs."""

import os
from pathlib import Path


def get_s3_client():
    """Return a boto3 S3 client configured for MinIO."""
    import boto3
    return boto3.client(
        "s3",
        endpoint_url=f"http://{os.getenv('MINIO_ENDPOINT', 'localhost:9000')}",
        aws_access_key_id=os.getenv("MINIO_ACCESS_KEY", "bug0minio"),
        aws_secret_access_key=os.getenv("MINIO_SECRET_KEY", "bug0miniopass"),
        region_name="us-east-1",
    )


def ensure_bucket(s3_client, bucket: str) -> None:
    """Create bucket if it doesn't exist."""
    try:
        s3_client.head_bucket(Bucket=bucket)
    except Exception:
        s3_client.create_bucket(Bucket=bucket)


def upload_file(
    local_path: str,
    s3_key: str,
    content_type: str = "application/octet-stream",
    bucket: str | None = None,
) -> str:
    """
    Upload a local file to MinIO.
    Returns the public URL (presigned if private bucket, or path-style URL).
    """
    bucket = bucket or os.getenv("MINIO_BUCKET", "bug0-artifacts")
    s3 = get_s3_client()
    ensure_bucket(s3, bucket)

    s3.upload_file(
        local_path,
        bucket,
        s3_key,
        ExtraArgs={"ContentType": content_type},
    )

    endpoint = os.getenv("MINIO_ENDPOINT", "localhost:9000")
    return f"http://{endpoint}/{bucket}/{s3_key}"


def upload_bytes(
    data: bytes,
    s3_key: str,
    content_type: str = "application/octet-stream",
    bucket: str | None = None,
) -> str:
    """Upload raw bytes to MinIO. Returns URL."""
    import io

    bucket = bucket or os.getenv("MINIO_BUCKET", "bug0-artifacts")
    s3 = get_s3_client()
    ensure_bucket(s3, bucket)

    s3.upload_fileobj(
        io.BytesIO(data),
        bucket,
        s3_key,
        ExtraArgs={"ContentType": content_type},
    )

    endpoint = os.getenv("MINIO_ENDPOINT", "localhost:9000")
    return f"http://{endpoint}/{bucket}/{s3_key}"


def upload_run_artifacts(
    run_id: str,
    result_id: str,
    video_path: str | None = None,
    screenshot_path: str | None = None,
    trace_path: str | None = None,
    console_logs: list[str] | None = None,
) -> dict[str, str | None]:
    """
    Upload all artifacts for a test result.
    Returns dict with video_url, screenshot_url, trace_url, log_url.
    """
    prefix = f"runs/{run_id}/{result_id}"
    urls: dict[str, str | None] = {
        "video_url": None,
        "screenshot_url": None,
        "trace_url": None,
        "log_url": None,
    }

    if video_path and Path(video_path).exists():
        urls["video_url"] = upload_file(
            video_path, f"{prefix}/video.webm", "video/webm"
        )

    if screenshot_path and Path(screenshot_path).exists():
        urls["screenshot_url"] = upload_file(
            screenshot_path, f"{prefix}/screenshot.png", "image/png"
        )

    if trace_path and Path(trace_path).exists():
        urls["trace_url"] = upload_file(
            trace_path, f"{prefix}/trace.zip", "application/zip"
        )

    if console_logs:
        log_text = "\n".join(console_logs)
        urls["log_url"] = upload_bytes(
            log_text.encode(), f"{prefix}/console.log", "text/plain"
        )

    return urls
