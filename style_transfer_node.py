"""
ComfyUI Gemini Style Transfer — Transform any image into a master photographer's
visual language using Gemini's image generation capabilities.

Option B: Direct one-step transformation. Image in → styled image out.
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
# DYNAMIC STYLE LOADING — auto-discover all styles from data/styles/
# ---------------------------------------------------------------------------
import importlib
import pathlib

STYLE_REGISTRY = {}  # {display_name: {transform, variants, intensity, name}}

def _load_styles():
    """Discover and load all style modules from data/styles/."""
    styles_dir = pathlib.Path(__file__).parent / "data" / "styles"
    if not styles_dir.exists():
        return

    for py_file in sorted(styles_dir.glob("*.py")):
        if py_file.name.startswith("_"):
            continue
        module_name = py_file.stem
        try:
            mod = importlib.import_module(f".data.styles.{module_name}", package=__package__)

            style_name = getattr(mod, "STYLE_NAME", module_name)
            entry = {
                "name": style_name,
                "id": getattr(mod, "STYLE_ID", module_name),
                "description": getattr(mod, "STYLE_DESCRIPTION", ""),
                "intensity": getattr(mod, "INTENSITY_MODIFIERS", {}),
            }

            # Support both variant-based (Leiter) and single-prompt styles
            if hasattr(mod, "TRANSFORM_VARIANTS"):
                entry["variants"] = mod.TRANSFORM_VARIANTS
                entry["variant_list"] = getattr(mod, "VARIANT_LIST", list(mod.TRANSFORM_VARIANTS.keys()))
            elif hasattr(mod, "TRANSFORM_SYSTEM"):
                # Single prompt style — wrap in a variants dict
                entry["variants"] = {"Default": mod.TRANSFORM_SYSTEM}
                entry["variant_list"] = ["Default"]
            else:
                continue  # Skip if no transform prompt at all

            STYLE_REGISTRY[style_name] = entry
            print(f"[Style Transfer] Loaded style: {style_name} ({len(entry['variant_list'])} variant(s))")

        except Exception as e:
            print(f"[Style Transfer] Failed to load style {module_name}: {e}")

_load_styles()

# ---------------------------------------------------------------------------
# CONSTANTS
# ---------------------------------------------------------------------------

MODELS = [
    "gemini-3-pro-image-preview",
    "gemini-3.1-flash-image-preview",
    "gemini-2.5-flash-image",
]

MODEL_RESOLUTIONS = {
    "gemini-3-pro-image-preview": ["1K", "2K", "4K"],
    "gemini-3.1-flash-image-preview": ["512", "1K", "2K", "4K"],
    "gemini-2.5-flash-image": ["1K"],
}

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

# Build combined style/variant dropdown — one entry per variant, no orphan choices
# Format: "Photographer / Variant" for multi-variant, "Photographer" for single-variant
STYLE_CHOICES = []       # dropdown list for UI
STYLE_LOOKUP = {}        # {dropdown_value: (style_name, variant_key)}

for style_name in sorted(STYLE_REGISTRY.keys()):
    entry = STYLE_REGISTRY[style_name]
    variants = entry["variant_list"]
    if len(variants) == 1 and variants[0] == "Default":
        # Single-variant: just the photographer name
        STYLE_CHOICES.append(style_name)
        STYLE_LOOKUP[style_name] = (style_name, "Default")
    else:
        # Multi-variant: "Photographer / Variant label"
        for v in variants:
            # Strip the long "-- description" for the dropdown, keep it for lookup
            short_label = v.split(" -- ")[0].strip() if " -- " in v else v
            combo = f"{style_name} / {short_label}"
            STYLE_CHOICES.append(combo)
            STYLE_LOOKUP[combo] = (style_name, v)

if not STYLE_CHOICES:
    STYLE_CHOICES = ["(no styles loaded)"]

INTENSITIES = ["subtle", "moderate", "full", "extreme"]

CATEGORY = "Gemini Direct"

# ---------------------------------------------------------------------------
# UTILITIES
# ---------------------------------------------------------------------------

def _resolve_api_key(api_key_input=""):
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
        "[Style Transfer] No API key found. Provide one via:\n"
        "  1. The api_key input on the node\n"
        "  2. GEMINI_API_KEY environment variable\n"
        "  3. A gemini_api_key.txt file in your ComfyUI root directory"
    )


def _get_client(api_key):
    if not HAS_GENAI:
        raise ImportError(
            "[Style Transfer] google-genai package not installed.\n"
            "Run: pip install google-genai"
        )
    return genai.Client(api_key=api_key)


def _tensor_to_pil(tensor):
    if len(tensor.shape) == 4:
        tensor = tensor[0]
    arr = (tensor.cpu().numpy() * 255).clip(0, 255).astype(np.uint8)
    return Image.fromarray(arr, "RGB")


def _pil_to_tensor(pil_img):
    arr = np.array(pil_img.convert("RGB")).astype(np.float32) / 255.0
    return torch.from_numpy(arr).unsqueeze(0)


def _pil_to_bytes(pil_img, fmt="PNG"):
    buf = io.BytesIO()
    pil_img.save(buf, format=fmt)
    return buf.getvalue()


def _get_output_dir():
    if folder_paths:
        return folder_paths.get_output_directory()
    return os.path.join(os.path.dirname(__file__), "output")


def _save_image(image_bytes, prefix="style_transfer"):
    out_dir = os.path.join(_get_output_dir(), "gemini_direct")
    os.makedirs(out_dir, exist_ok=True)
    timestamp = time.strftime("%Y%m%d_%H%M%S")
    filename = f"{prefix}_{timestamp}.png"
    filepath = os.path.join(out_dir, filename)
    pil = Image.open(io.BytesIO(image_bytes)).convert("RGB")
    pil.save(filepath, "PNG")
    return filepath


def _resolve_resolution(model, requested):
    supported = MODEL_RESOLUTIONS.get(model, ["1K"])
    if requested in supported:
        return requested
    fallback = supported[-1]
    print(f"[Style Transfer] {model} doesn't support {requested}, falling back to {fallback}")
    return fallback


# ============================================================================
# NODE: GEMINI STYLE TRANSFER
# ============================================================================

class GeminiStyleTransfer:
    """Transform any image into a master photographer's visual language.
    One-step: image in → styled image out. Uses Gemini's image generation
    with a deep style-specific system prompt."""

    @classmethod
    def INPUT_TYPES(s):
        return {
            "required": {
                "image": ("IMAGE", {
                    "tooltip": "Source image to transform into the selected style.",
                }),
                "style": (STYLE_CHOICES, {
                    "default": STYLE_CHOICES[0],
                    "tooltip": (
                        "Master photographer style and variant. "
                        "Multi-variant styles show as 'Photographer / Variant'."
                    ),
                }),
                "intensity": (INTENSITIES, {
                    "default": "full",
                    "tooltip": (
                        "How aggressively to apply the style. "
                        "subtle = whisper of style, moderate = clear but gentle, "
                        "full = authentic transformation, extreme = abstract/painterly."
                    ),
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
                    "default": "auto",
                    "tooltip": "Output aspect ratio. 'auto' preserves source proportions.",
                }),
                "resolution": (ALL_RESOLUTIONS, {
                    "default": "2K",
                    "tooltip": "Output resolution.",
                }),
            },
            "optional": {
                "direction": ("STRING", {
                    "multiline": True,
                    "default": "",
                    "tooltip": (
                        "Optional creative direction to guide the transformation. "
                        "Examples: 'focus on the red umbrella as the accent', "
                        "'make it a snowy scene', 'emphasize the reflection in the window'. "
                        "Leave empty for pure style interpretation."
                    ),
                }),
                "api_key": ("STRING", {
                    "default": "",
                }),
            },
        }

    RETURN_TYPES = ("IMAGE", "STRING", "STRING")
    RETURN_NAMES = ("image", "cost_info", "cache_key")
    FUNCTION = "transform"
    CATEGORY = CATEGORY

    def transform(self, image, style, intensity, model, seed, aspect_ratio,
                  resolution, direction="", api_key=""):

        resolved_key = _resolve_api_key(api_key)
        client = _get_client(resolved_key)

        # Resolve style + variant from combined dropdown
        if style not in STYLE_LOOKUP:
            raise ValueError(f"[Style Transfer] Unknown style: {style}. Available: {', '.join(STYLE_CHOICES)}")

        style_name, variant_key = STYLE_LOOKUP[style]
        style_entry = STYLE_REGISTRY[style_name]

        # Build cache key
        cache_key = f"style_transfer|{style}|{intensity}|{model}|{seed}|{aspect_ratio}|{resolution}|{direction}"

        # Get the system prompt for this variant
        system_prompt = style_entry["variants"].get(variant_key)
        if not system_prompt:
            system_prompt = list(style_entry["variants"].values())[0]

        # Append intensity modifier
        intensity_mod = style_entry["intensity"].get(intensity, "")
        if intensity_mod:
            system_prompt += f"\n\nINTENSITY LEVEL -- {intensity.upper()}:\n{intensity_mod}"

        # Resolve resolution
        actual_resolution = _resolve_resolution(model, resolution)

        # Build image config
        image_config_kwargs = {"image_size": actual_resolution}
        if aspect_ratio != "auto":
            image_config_kwargs["aspect_ratio"] = aspect_ratio

        gen_config = types.GenerateContentConfig(
            response_modalities=["IMAGE"],
            image_config=types.ImageConfig(**image_config_kwargs),
            system_instruction=system_prompt,
            seed=seed,
        )

        # Build content: source image + transformation instruction
        pil_img = _tensor_to_pil(image)
        img_bytes = _pil_to_bytes(pil_img)

        contents = [
            types.Part.from_bytes(data=img_bytes, mime_type="image/png"),
        ]

        # Build the user message
        user_msg = (
            f"Rebuild this scene as {style_name} would have photographed it. "
            f"Same location and subject, but reimagine the composition, "
            f"framing, color, and visual treatment entirely through "
            f"{style_name}'s eyes. Do not overlay effects on this photo -- "
            f"generate a new photograph in their visual language."
        )
        if direction and direction.strip():
            user_msg += f"\n\nCreative direction: {direction.strip()}"

        contents.append(user_msg)

        # Estimate cost
        est_cost = COST_TABLE.get(model, {}).get(actual_resolution, 0.0)
        print(f"[Style Transfer] {style} ({intensity}) | {model} @ {actual_resolution} | Est. ${est_cost:.4f}")

        # Call API
        start_time = time.time()
        response = client.models.generate_content(
            model=model,
            contents=contents,
            config=gen_config,
        )
        elapsed = time.time() - start_time

        # Extract image
        image_data = None
        if response.candidates:
            for part in response.candidates[0].content.parts:
                if part.inline_data and part.inline_data.data:
                    image_data = part.inline_data.data
                    break

        if image_data is None:
            # Extract any text for error reporting
            error_text = ""
            if response.candidates:
                for part in response.candidates[0].content.parts:
                    if part.text:
                        error_text += part.text
            raise RuntimeError(
                f"[Style Transfer] No image generated. Model said: {error_text}\n"
                "Try a different seed or adjust creative direction."
            )

        # Token usage
        token_info = ""
        if hasattr(response, 'usage_metadata') and response.usage_metadata:
            meta = response.usage_metadata
            in_tok = getattr(meta, 'prompt_token_count', 0) or 0
            out_tok = getattr(meta, 'candidates_token_count', 0) or 0
            token_info = f" | Tokens: {in_tok} in / {out_tok} out"

        # Save to disk
        style_prefix = style_entry["id"]
        filepath = _save_image(image_data, prefix=f"{style_prefix}_{intensity}")

        # Cost info
        cost_info = (
            f"${est_cost:.4f} USD | {style} ({intensity}) | {model} @ {actual_resolution} | "
            f"{elapsed:.1f}s{token_info}"
        )

        # Convert to tensor
        output_pil = Image.open(io.BytesIO(image_data)).convert("RGB")
        output_tensor = _pil_to_tensor(output_pil)

        print(
            f"[Style Transfer] Done! {output_pil.size[0]}x{output_pil.size[1]} | "
            f"${est_cost:.4f} | {elapsed:.1f}s | {os.path.basename(filepath)}"
        )

        return (output_tensor, cost_info, cache_key)


# ============================================================================
# NODE: GEMINI STYLE TRANSFER SETTINGS
# ============================================================================

class GeminiStyleTransferSettings:
    """Companion node that owns the style and intensity dropdowns.

    Emits (style, intensity) as STRING outputs without calling the API.
    Wire each output to the matching Style Transfer input (convert those
    widgets to inputs) AND to a Hash Vault any_input_N slot. This keeps
    the dropdown UX while giving Hash Vault a stable, validated string
    to hash on. Single source of truth -- no typo-silent cache corruption.
    """

    @classmethod
    def INPUT_TYPES(s):
        return {
            "required": {
                "style": (STYLE_CHOICES, {
                    "default": STYLE_CHOICES[0],
                    "tooltip": (
                        "Master photographer style and variant. "
                        "Multi-variant styles show as 'Photographer / Variant'."
                    ),
                }),
                "intensity": (INTENSITIES, {
                    "default": "full",
                    "tooltip": (
                        "How aggressively to apply the style. "
                        "subtle = whisper of style, moderate = clear but gentle, "
                        "full = authentic transformation, extreme = abstract/painterly."
                    ),
                }),
            },
        }

    RETURN_TYPES = ("STRING", "STRING")
    RETURN_NAMES = ("style", "intensity")
    FUNCTION = "emit"
    CATEGORY = CATEGORY

    def emit(self, style, intensity):
        return (style, intensity)


# ============================================================================
# MAPPINGS
# ============================================================================

NODE_CLASS_MAPPINGS = {
    "GeminiStyleTransfer": GeminiStyleTransfer,
    "GeminiStyleTransferSettings": GeminiStyleTransferSettings,
}

NODE_DISPLAY_NAME_MAPPINGS = {
    "GeminiStyleTransfer": "Gemini Style Transfer",
    "GeminiStyleTransferSettings": "Gemini Style Transfer Settings",
}
