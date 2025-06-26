from typing import Optional
import os
import traceback
from .base import ImageGenerator, get_image_info_and_save, generate_image_id
from services.config_service import FILES_DIR
from ..midjourney import generate_image as mj_generate_image


class MidjourneyGenerator(ImageGenerator):
    """Midjourney image generator implementation"""

    async def generate(
        self,
        prompt: str,
        model: str = "",  # Midjourney does not require a model name
        aspect_ratio: str = "1:1",
        input_image: Optional[str] = None,
        **kwargs,
    ) -> tuple[str, int, int, str]:
        """Generate an image via Midjourney and save it locally.

        Args:
            prompt: Prompt text.
            model: Unused for Midjourney (kept for compatibility).
            aspect_ratio: Desired aspect ratio (e.g. "1:1").
            input_image: Unused for Midjourney currently.

        Returns:
            Tuple containing (mime_type, width, height, filename)
        """
        try:
            print(f"🦄 [MidjourneyGenerator] Starting generation for prompt: '{prompt}' | aspect_ratio: {aspect_ratio}")
            # Midjourney does not support input image editing in this wrapper yet
            if input_image:
                print("⚠️ Midjourney generator currently ignores `input_image` argument.")

            # Call the shared Midjourney helper to get CDN URLs
            urls = await mj_generate_image(prompt, aspect_ratio)
            print(f"🦄 [MidjourneyGenerator] Midjourney responded with {len(urls)} url(s): {urls}")
            if not urls or len(urls) == 0:
                raise RuntimeError("No image URLs received from Midjourney")

            # Use the first returned image URL
            output_url = urls[0]
            print(f"🦄 [MidjourneyGenerator] Using first URL: {output_url}")

            image_id = generate_image_id()
            print("🦄 Midjourney image generation image_id", image_id)

            # Download and save the image, and get metadata
            mime_type, width, height, extension = await get_image_info_and_save(
                output_url, os.path.join(FILES_DIR, f"{image_id}")
            )
            filename = f"{image_id}.{extension}"
            return mime_type, width, height, filename

        except Exception as e:
            print("Error generating image with Midjourney", e)
            traceback.print_exc()
            raise e 