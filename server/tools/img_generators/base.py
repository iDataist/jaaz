from abc import ABC, abstractmethod
from typing import Optional, Tuple
import base64
from PIL import Image
from io import BytesIO
import aiofiles
from nanoid import generate
from utils.http_client import HttpClient


class ImageGenerator(ABC):
    """Abstract base class for image generators"""

    @abstractmethod
    async def generate(
        self,
        prompt: str,
        model: str,
        aspect_ratio: str = "1:1",
        input_image: Optional[str] = None,
        **kwargs
    ) -> Tuple[str, int, int, str]:
        """
        Generate an image and return metadata

        Args:
            prompt: Text prompt for image generation
            model: Model name/identifier
            aspect_ratio: Image aspect ratio (e.g., "1:1", "16:9")
            input_image: Optional input image (base64 or file path)
            **kwargs: Additional provider-specific parameters

        Returns:
            Tuple of (mime_type, width, height, filename)
        """
        pass


async def get_image_info_and_save(url, file_path_without_extension, is_b64=False):
    """Shared utility function to download/decode and save image"""
    if is_b64:
        image_content = base64.b64decode(url)
    else:
        # Fetch the image asynchronously
        async with HttpClient.create() as client:
            response = await client.get(url, headers={
                "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
            })
            print(f"📥 [download] GET {url} -> status {response.status_code} content-type {response.headers.get('content-type')}")
            if response.status_code != 200:
                print("⚠️ httpx download failed, trying curl_cffi…")
                try:
                    from curl_cffi import requests as curl_requests
                    curl_res = curl_requests.get(url, impersonate="chrome")
                    print(f"📥 [curl_cffi] status {curl_res.status_code}")
                    image_content = curl_res.content
                except Exception as e:
                    print("❌ curl_cffi fallback failed", e)
                    raise
            else:
                # Read the image content as bytes
                image_content = response.content
    # Open the image
    try:
        image = Image.open(BytesIO(image_content))
    except Exception as e:
        print("❌ [PIL] Failed to open image: ", e)
        # Save raw bytes to debug file
        debug_path = f"{file_path_without_extension}_raw.bin"
        async with aiofiles.open(debug_path, 'wb') as dbg:
            await dbg.write(image_content)

        # Fallback: assume WebP (Midjourney) 1024x1024
        mime_type = "image/webp"
        width = 1024
        height = 1024
        extension = "webp"
        file_path = f"{file_path_without_extension}.{extension}"
        async with aiofiles.open(file_path, 'wb') as out_file:
            await out_file.write(image_content)
        print(f"🔧 [fallback] Saved raw image bytes to {file_path}")
        return mime_type, width, height, extension

    # Get MIME type
    mime_type = Image.MIME.get(image.format if image.format else 'PNG')

    # Get dimensions
    width, height = image.size

    # Determine the file extension
    extension = image.format.lower() if image.format else 'png'
    file_path = f"{file_path_without_extension}.{extension}"

    # Save the image to a local file with the correct extension asynchronously
    async with aiofiles.open(file_path, 'wb') as out_file:
        await out_file.write(image_content)
    print('🦄image saved to file_path', file_path)

    return mime_type, width, height, extension


def generate_image_id():
    """Generate unique image ID"""
    return 'im_' + generate(size=8)
