"""
ComfyUI Gemini Direct — Direct Google Gemini image generation.
Bypasses ComfyUI's credit system. Uses your own Google AI API key.

Drop-in replacement for the built-in "Nano Banana Pro" node with:
  - 3 model tiers (Pro, Flash, 2.5 Flash)
  - Batched reference image input (visual context)
  - Real USD cost display instead of opaque credits
  - Auto-save to disk
  - Compatible with Hash Vault caching for $0 repeat generations
"""

import os
import io
import time
import numpy as np

import torch
from PIL import Image

try:
    import folder_paths
except ImportError:
    folder_paths = None

try:
    from google import genai
    from google.genai import types
    HAS_GENAI = True
except ImportError:
    HAS_GENAI = False

# ---------------------------------------------------------------------------
# CONSTANTS
# ---------------------------------------------------------------------------

MODELS = [
    "gemini-3-pro-image-preview",
    "gemini-3.1-flash-image-preview",
    "gemini-2.5-flash-image",
]

# Resolutions each model supports
MODEL_RESOLUTIONS = {
    "gemini-3-pro-image-preview": ["1K", "2K", "4K"],
    "gemini-3.1-flash-image-preview": ["512", "1K", "2K", "4K"],
    "gemini-2.5-flash-image": ["1K"],
}

# Estimated USD cost per image (based on output token counts × per-model rates)
COST_TABLE = {
    "gemini-3-pro-image-preview": {
        "1K": 0.134, "2K": 0.134, "4K": 0.240,
    },
    "gemini-3.1-flash-image-preview": {
        "512": 0.045, "1K": 0.067, "2K": 0.101, "4K": 0.151,
    },
    "gemini-2.5-flash-image": {
        "1K": 0.039,
    },
}

ALL_RESOLUTIONS = ["1K", "2K", "4K", "512"]

ASPECT_RATIOS = [
    "auto", "1:1", "2:3", "3:2", "3:4", "4:3",
    "4:5", "5:4", "9:16", "16:9", "21:9",
]

RESPONSE_MODALITIES_OPTIONS = ["IMAGE+TEXT", "IMAGE"]

DEFAULT_SYSTEM_PROMPT = (
    "You are an expert image-generation engine. You must ALWAYS produce an image.\n"
    "Interpret all user input\u2014regardless of format, intent, or abstraction\u2014as "
    "literal visual directives for image composition.\n"
    "If a prompt is conversational or lacks specific visual details, you must "
    "creatively invent a concrete visual scenario that depicts the concept.\n"
    "Prioritize generating the visual representation above any text, formatting, "
    "or conversational requests."
)

CATEGORY = "Gemini Direct"

# ---------------------------------------------------------------------------
# UTILITIES
# ---------------------------------------------------------------------------

def _resolve_api_key(api_key_input=""):
    """Resolve API key: direct input > env var > file."""
    if api_key_input and api_key_input.strip():
        return api_key_input.strip()

    env_key = os.environ.get("GEMINI_API_KEY", "").strip()
    if env_key:
        return env_key

    if folder_paths:
        root = os.path.dirname(folder_paths.get_output_directory())
    else:
        root = os.path.dirname(__file__)
    key_file = os.path.join(root, "gemini_api_key.txt")
    if os.path.exists(key_file):
        with open(key_file, "r") as f:
            file_key = f.read().strip()
        if file_key:
            return file_key

    raise ValueError(
        "[Gemini Direct] No API key found. Provide one via:\n"
        "  1. The api_key input on the node\n"
        "  2. GEMINI_API_KEY environment variable\n"
        "  3. A gemini_api_key.txt file in your ComfyUI root directory"
    )


def _get_client(api_key):
    if not HAS_GENAI:
        raise ImportError(
            "[Gemini Direct] google-genai package not installed.\n"
            "Run: pip install google-genai"
        )
    return genai.Client(api_key=api_key)


def _tensor_to_pil(tensor):
    """Convert single image tensor (H,W,C float32 0-1) to PIL."""
    arr = (tensor.cpu().numpy() * 255).clip(0, 255).astype(np.uint8)
    return Image.fromarray(arr, "RGB")


def _pil_to_tensor(pil_img):
    """Convert PIL to ComfyUI IMAGE tensor (1,H,W,C float32 0-1)."""
    arr = np.array(pil_img.convert("RGB")).astype(np.float32) / 255.0
    return torch.from_numpy(arr).unsqueeze(0)


def _pil_to_bytes(pil_img, fmt="PNG"):
    buf = io.BytesIO()
    pil_img.save(buf, format=fmt)
    return buf.getvalue()


def _extract_image_and_text(response):
    """Extract image bytes and text from Gemini response."""
    image_data = None
    text_parts = []
    if response.candidates:
        for part in response.candidates[0].content.parts:
            if part.inline_data and part.inline_data.data:
                image_data = part.inline_data.data
            if part.text:
                text_parts.append(part.text)
    return image_data, "\n".join(text_parts)


def _get_output_dir():
    if folder_paths:
        return folder_paths.get_output_directory()
    return os.path.join(os.path.dirname(__file__), "output")


def _save_image(image_bytes, prefix="gemini_direct"):
    """Save to ComfyUI output dir, return path."""
    out_dir = os.path.join(_get_output_dir(), "gemini_direct")
    os.makedirs(out_dir, exist_ok=True)
    timestamp = time.strftime("%Y%m%d_%H%M%S")
    filename = f"{prefix}_{timestamp}.png"
    filepath = os.path.join(out_dir, filename)
    pil = Image.open(io.BytesIO(image_bytes)).convert("RGB")
    pil.save(filepath, "PNG")
    return filepath


def _estimate_cost(model, resolution):
    return COST_TABLE.get(model, {}).get(resolution, 0.0)


def _resolve_resolution(model, requested):
    """Fallback to highest supported if model can't do the requested resolution."""
    supported = MODEL_RESOLUTIONS.get(model, ["1K"])
    if requested in supported:
        return requested
    fallback = supported[-1]
    print(f"[Gemini Direct] {model} doesn't support {requested}, falling back to {fallback}")
    return fallback


# ============================================================================
# NODE: GEMINI IMAGE GENERATE (Direct API)
# ============================================================================

class GeminiImageGenerate:
    """Direct Google Gemini image generation.
    Uses your own API key — no ComfyUI credits.
    Supports batched reference images as visual context."""

    @classmethod
    def INPUT_TYPES(s):
        return {
            "required": {
                "prompt": ("STRING", {
                    "multiline": True,
                    "default": "",
                    "tooltip": "Text prompt for image generation. Supports long, detailed prompts.",
                }),
                "model": (MODELS, {
                    "default": MODELS[0],
                    "tooltip": (
                        "Pro = best quality ($0.13-0.24) | "
                        "3.1 Flash = balanced ($0.05-0.15) | "
                        "2.5 Flash = cheapest ($0.04, 1K only)"
                    ),
                }),
                "seed": ("INT", {
                    "default": 0,
                    "min": 0,
                    "max": 0xFFFFFFFFFFFFFFFF,
                    "tooltip": "Seed for reproducibility",
                }),
                "aspect_ratio": (ASPECT_RATIOS, {
                    "default": "2:3",
                    "tooltip": "Output aspect ratio. 'auto' lets the model decide.",
                }),
                "resolution": (ALL_RESOLUTIONS, {
                    "default": "2K",
                    "tooltip": "Output resolution. Falls back if unsupported by chosen model.",
                }),
                "response_modalities": (RESPONSE_MODALITIES_OPTIONS, {
                    "default": "IMAGE+TEXT",
                    "tooltip": "IMAGE+TEXT returns image + description. IMAGE returns image only.",
                }),
            },
            "optional": {
                "images": ("IMAGE", {
                    "tooltip": (
                        "Reference images (batched) used as visual context. "
                        "Example: batch a background + character images, then prompt "
                        "'integrate these people into the background'."
                    ),
                }),
                "system_prompt": ("STRING", {
                    "multiline": True,
                    "default": DEFAULT_SYSTEM_PROMPT,
                    "tooltip": "System instruction. Default forces the model to always produce an image.",
                }),
                "api_key": ("STRING", {
                    "default": "",
                    "tooltip": (
                        "Google AI API key. Falls back to GEMINI_API_KEY env var "
                        "or gemini_api_key.txt in ComfyUI root."
                    ),
                }),
            },
        }

    RETURN_TYPES = ("IMAGE", "STRING", "STRING")
    RETURN_NAMES = ("images", "text", "cost_info")
    FUNCTION = "generate"
    CATEGORY = CATEGORY

    def generate(self, prompt, model, seed, aspect_ratio, resolution,
                 response_modalities, images=None, system_prompt="", api_key=""):

        resolved_key = _resolve_api_key(api_key)
        client = _get_client(resolved_key)

        # Resolve resolution for this model
        actual_resolution = _resolve_resolution(model, resolution)

        # Map modalities
        if response_modalities == "IMAGE+TEXT":
            modalities = ["IMAGE", "TEXT"]
        else:
            modalities = ["IMAGE"]

        # Build image config — omit aspect_ratio when set to "auto"
        image_config_kwargs = {"image_size": actual_resolution}
        if aspect_ratio != "auto":
            image_config_kwargs["aspect_ratio"] = aspect_ratio

        gen_config = types.GenerateContentConfig(
            response_modalities=modalities,
            image_config=types.ImageConfig(**image_config_kwargs),
            seed=seed,
        )

        if system_prompt and system_prompt.strip():
            gen_config.system_instruction = system_prompt.strip()

        # Build content parts: all reference images + prompt text
        contents = []

        if images is not None:
            batch_size = images.shape[0]
            for i in range(batch_size):
                pil_img = _tensor_to_pil(images[i])
                img_bytes = _pil_to_bytes(pil_img)
                contents.append(
                    types.Part.from_bytes(data=img_bytes, mime_type="image/png")
                )
            print(f"[Gemini Direct] {batch_size} reference image(s) attached")

        contents.append(prompt)

        # Estimate cost
        est_cost = _estimate_cost(model, actual_resolution)
        print(f"[Gemini Direct] Generating: {model} @ {actual_resolution} | Est. ${est_cost:.4f}")

        # Call API
        start_time = time.time()
        response = client.models.generate_content(
            model=model,
            contents=contents,
            config=gen_config,
        )
        elapsed = time.time() - start_time

        # Extract results
        image_bytes, response_text = _extract_image_and_text(response)

        if image_bytes is None:
            raise RuntimeError(
                f"[Gemini Direct] No image generated. Model said: {response_text}\n"
                "Try rephrasing your prompt or check content safety filters."
            )

        # Token usage info
        token_info = ""
        if hasattr(response, 'usage_metadata') and response.usage_metadata:
            meta = response.usage_metadata
            in_tok = getattr(meta, 'prompt_token_count', 0) or 0
            out_tok = getattr(meta, 'candidates_token_count', 0) or 0
            token_info = f" | Tokens: {in_tok} in / {out_tok} out"

        # Save to disk
        filepath = _save_image(image_bytes)

        # Build cost info string
        cost_info = (
            f"${est_cost:.4f} USD | {model} @ {actual_resolution} | "
            f"{elapsed:.1f}s{token_info} | {os.path.basename(filepath)}"
        )

        # Convert to tensor
        output_pil = Image.open(io.BytesIO(image_bytes)).convert("RGB")
        output_tensor = _pil_to_tensor(output_pil)

        print(
            f"[Gemini Direct] Done! {output_pil.size[0]}x{output_pil.size[1]} | "
            f"${est_cost:.4f} | {elapsed:.1f}s | {os.path.basename(filepath)}"
        )

        return (output_tensor, response_text, cost_info)


# ============================================================================
# MAPPINGS
# ============================================================================

NODE_CLASS_MAPPINGS = {
    "GeminiImageGenerate": GeminiImageGenerate,
}

NODE_DISPLAY_NAME_MAPPINGS = {
    "GeminiImageGenerate": "Gemini Image Generate (Direct API)",
}
