# C:\Users\myh03\project_weavemo\weavemo-backend-mock\services\post_image.py

from io import BytesIO
import warnings

from fastapi import HTTPException
from PIL import Image, ImageOps, UnidentifiedImageError


MAX_UPLOAD_BYTES = 5 * 1024 * 1024
MAX_IMAGE_PIXELS = 20_000_000
MAX_IMAGE_EDGE = 1600

ALLOWED_FORMATS = {"JPEG", "PNG", "WEBP"}


def prepare_post_image(data: bytes) -> bytes:
    """이미지를 검증하고 메타데이터 없는 WebP로 변환한다."""
    if not data:
        raise HTTPException(
            status_code=400,
            detail="Empty image",
        )

    if len(data) > MAX_UPLOAD_BYTES:
        raise HTTPException(
            status_code=413,
            detail="Image must be 5 MB or smaller",
        )

    try:
        with warnings.catch_warnings():
            warnings.simplefilter(
                "error",
                Image.DecompressionBombWarning,
            )

            # 확장자 대신 실제 파일 형식과 구조를 검사한다.
            with Image.open(BytesIO(data)) as probe:
                if probe.format not in ALLOWED_FORMATS:
                    raise HTTPException(
                        status_code=400,
                        detail="Only JPEG, PNG and WebP are supported",
                    )

                if probe.width * probe.height > MAX_IMAGE_PIXELS:
                    raise HTTPException(
                        status_code=400,
                        detail="Image resolution is too large",
                    )

                if getattr(probe, "is_animated", False):
                    raise HTTPException(
                        status_code=400,
                        detail="Animated images are not supported",
                    )

                probe.verify()

            # 검증 후 다시 열어 회전 보정과 크기 조정을 수행한다.
            with Image.open(BytesIO(data)) as source:
                image = ImageOps.exif_transpose(source)

                try:
                    image.thumbnail(
                        (MAX_IMAGE_EDGE, MAX_IMAGE_EDGE),
                        Image.Resampling.LANCZOS,
                    )

                    # 새 이미지에 픽셀만 복사해 EXIF·GPS 등을 제외한다.
                    mode = (
                        "RGBA"
                        if image.mode in {"RGBA", "LA"}
                        or "transparency" in image.info
                        else "RGB"
                    )

                    converted = image.convert(mode)

                    try:
                        with Image.new(mode, converted.size) as clean:
                            clean.paste(converted)

                            output = BytesIO()
                            clean.save(
                                output,
                                format="WEBP",
                                quality=85,
                                method=4,
                            )
                            result = output.getvalue()
                    finally:
                        converted.close()
                finally:
                    if image is not source:
                        image.close()

    except HTTPException:
        raise
    except (
        Image.DecompressionBombError,
        Image.DecompressionBombWarning,
    ) as exc:
        raise HTTPException(
            status_code=400,
            detail="Image resolution is too large",
        ) from exc
    except (
        UnidentifiedImageError,
        OSError,
        ValueError,
        SyntaxError,
        EOFError,
    ) as exc:
        raise HTTPException(
            status_code=400,
            detail="Invalid or damaged image",
        ) from exc

    if len(result) > MAX_UPLOAD_BYTES:
        raise HTTPException(
            status_code=413,
            detail="Processed image is too large",
        )

    return result
