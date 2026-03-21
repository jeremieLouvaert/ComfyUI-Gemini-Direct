"""
ComfyUI Prompt Studio — AI-powered prompt enhancement for image generation.
Uses Gemini text models to expand briefs or refine existing prompts.
"""

import os
import io
import time
import numpy as np

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

from PIL import Image

# ---------------------------------------------------------------------------
# CONSTANTS
# ---------------------------------------------------------------------------

TEXT_MODELS = [
    "gemini-3-flash-preview",
    "gemini-3-pro-image-preview",
    "gemini-2.5-flash-image",
]

MODES = ["Expand", "Refine"]

STYLE_PRESETS = [
    "Photography",
    "Cinematic",
    "Editorial / Fashion",
    "Fine Art",
    "Product / Commercial",
    "Custom",
]

CATEGORY = "Gemini Direct"

# ---------------------------------------------------------------------------
# SYSTEM PROMPTS
# ---------------------------------------------------------------------------

EXPAND_SYSTEM_PROMPT = """You are an expert image generation prompt engineer. Your job is to take a short creative brief and expand it into a comprehensive, structured image generation prompt.

OUTPUT FORMAT — always use this exact structure with these section headers:

**CRITICAL INSTRUCTION:** State the core visual transformation, dominant aesthetic, and any mandatory technical requirements (aspect ratio if mentioned, style era, mood).

**CAMERA RE-COMPOSITION:**
- Angle: (eye-level, low-angle, aerial, dutch angle, etc.)
- Lens Compression: (focal length aesthetic — 24mm wide, 35mm street, 50mm standard, 85mm portrait, 135mm telephoto)
- Framing: (rule of thirds, centered, symmetrical, negative space usage, leading lines)

**MANDATORY SUBJECT LOCK:**
- Identity: (who/what is the subject — be specific)
- Action: (what they're doing — pose, gesture, expression)
- Detail: (clothing, textures, materials, distinguishing features)

**TONAL REFINEMENT:**
- Color Science: (color palette, film stock emulation, color temperature)
- Lighting: (direction, quality, intensity, shadow behavior)
- Micro-contrast: (texture detail level, surface rendering)

**ENVIRONMENT:**
- Texture: (ground, walls, surfaces — specific materials)
- Architecture/Setting: (specific environment details)
- Atmosphere: (air quality, particles, weather, time of day)

**PHOTOGRAPHIC STYLE:**
- Gear: (camera body + lens combination)
- Settings: (aperture, focus behavior)
- Film Profile: (grain type, optical characteristics, output feel)

RULES:
- Be highly specific and technical — avoid vague terms like "beautiful" or "nice"
- Every section must have actionable visual directives
- Use real camera/lens/film references for authenticity
- The prompt must read like art direction from a creative director
- If reference images are provided, incorporate their visual qualities (colors, composition, textures, mood) into the prompt
- Do NOT include any preamble, explanation, or commentary — output ONLY the structured prompt"""

REFINE_SYSTEM_PROMPT = """You are an expert image generation prompt reviewer. Your job is to take an existing prompt and strengthen it while preserving the author's intent and structure.

YOUR TASKS:
1. Identify weak or vague sections and make them more specific and technically precise
2. Add missing technical detail (if camera specs are vague, specify exact gear; if lighting is mentioned loosely, define direction and quality)
3. Fix inconsistencies (e.g., conflicting lighting descriptions, impossible camera settings)
4. Strengthen visual language — replace generic terms with specific, actionable directives
5. If reference images are provided, incorporate relevant visual qualities you observe

RULES:
- PRESERVE the author's creative intent and overall vision — do not change the concept
- PRESERVE the existing structure and section headers if present
- If the prompt has no structure, add the standard sections (CRITICAL INSTRUCTION, CAMERA, SUBJECT, TONAL, ENVIRONMENT, PHOTOGRAPHIC STYLE) while keeping all original content
- Do NOT remove content the author wrote — only enhance and add
- Do NOT include any preamble, explanation, or commentary — output ONLY the refined prompt
- Be surgical — strengthen weak areas, leave strong areas untouched"""

CUSTOM_TEMPLATE_DEFAULT = """Define your own prompt structure here. Use section headers that match your workflow.

Example:
**SCENE:** [describe the scene]
**SUBJECT:** [describe the subject]
**STYLE:** [artistic style and references]
**TECHNICAL:** [camera, lens, film]
**MOOD:** [atmosphere, emotion, color]"""

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
        "[Prompt Studio] No API key found. Provide one via:\n"
        "  1. The api_key input on the node\n"
        "  2. GEMINI_API_KEY environment variable\n"
        "  3. A gemini_api_key.txt file in your ComfyUI root directory"
    )


def _get_client(api_key):
    if not HAS_GENAI:
        raise ImportError(
            "[Prompt Studio] google-genai package not installed.\n"
            "Run: pip install google-genai"
        )
    return genai.Client(api_key=api_key)


def _tensor_to_pil(tensor):
    if len(tensor.shape) == 4:
        tensor = tensor[0]
    arr = (tensor.cpu().numpy() * 255).clip(0, 255).astype(np.uint8)
    return Image.fromarray(arr, "RGB")


def _pil_to_bytes(pil_img, fmt="JPEG", quality=85):
    buf = io.BytesIO()
    pil_img.save(buf, format=fmt, quality=quality)
    return buf.getvalue()


# ============================================================================
# NODE: PROMPT STUDIO
# ============================================================================

class PromptStudio:
    """AI-powered prompt enhancement. Expand briefs or refine existing prompts
    using Gemini text models. Supports reference image analysis."""

    @classmethod
    def INPUT_TYPES(s):
        return {
            "required": {
                "brief": ("STRING", {
                    "multiline": True,
                    "default": "",
                    "tooltip": (
                        "Expand mode: short creative direction (e.g. 'street photographer, "
                        "1960s, Kodachrome, Saul Leiter style'). "
                        "Refine mode: your full prompt to review and strengthen."
                    ),
                }),
                "mode": (MODES, {
                    "default": "Expand",
                    "tooltip": (
                        "Expand: short brief → full structured prompt. "
                        "Refine: review and strengthen an existing prompt."
                    ),
                }),
                "style_preset": (STYLE_PRESETS, {
                    "default": "Photography",
                    "tooltip": "Guides the enhancement style. Use 'Custom' with custom_template for full control.",
                }),
                "model": (TEXT_MODELS, {
                    "default": TEXT_MODELS[0],
                    "tooltip": "Gemini 3 Flash is recommended — fast and near-free for text.",
                }),
            },
            "optional": {
                "images": ("IMAGE", {
                    "tooltip": "Reference images for visual context. The LLM will analyze and incorporate their qualities.",
                }),
                "custom_template": ("STRING", {
                    "multiline": True,
                    "default": "",
                    "tooltip": "Custom prompt structure template. Only used when style_preset is 'Custom'.",
                }),
                "additional_instructions": ("STRING", {
                    "multiline": True,
                    "default": "",
                    "tooltip": "Extra instructions for the enhancer (e.g. 'focus on dramatic lighting', 'keep it minimal').",
                }),
                "api_key": ("STRING", {
                    "default": "",
                }),
            },
        }

    RETURN_TYPES = ("STRING", "STRING")
    RETURN_NAMES = ("enhanced_prompt", "analysis")
    FUNCTION = "enhance"
    CATEGORY = CATEGORY

    def enhance(self, brief, mode, style_preset, model,
                images=None, custom_template="", additional_instructions="", api_key=""):

        if not brief.strip():
            raise ValueError("[Prompt Studio] Brief is empty. Write something to enhance.")

        resolved_key = _resolve_api_key(api_key)
        client = _get_client(resolved_key)

        # Select system prompt based on mode
        if mode == "Expand":
            system_prompt = EXPAND_SYSTEM_PROMPT
        else:
            system_prompt = REFINE_SYSTEM_PROMPT

        # Add style preset context
        style_context = ""
        if style_preset == "Custom" and custom_template and custom_template.strip():
            style_context = (
                f"\n\nCUSTOM TEMPLATE — use this structure instead of the default:\n"
                f"{custom_template.strip()}"
            )
        elif style_preset != "Custom":
            style_hints = {
                "Photography": "Focus on real-world camera gear, film stocks, and photographic technique. The output should read like a photographer's shot brief.",
                "Cinematic": "Focus on cinematic language — film references, color grading (LUTs), anamorphic lenses, aspect ratios, production design. The output should read like a director's shot list.",
                "Editorial / Fashion": "Focus on fashion photography — editorial lighting, model posing, wardrobe detail, makeup, set design. Reference real fashion photographers and magazines.",
                "Fine Art": "Focus on artistic composition, art historical references, painterly techniques, conceptual depth. Reference specific artists, movements, and mediums.",
                "Product / Commercial": "Focus on clean product photography — controlled studio lighting, material rendering, reflections, hero angles. Reference commercial photography techniques.",
            }
            style_context = f"\n\nSTYLE DIRECTION: {style_hints.get(style_preset, '')}"

        # Add additional instructions if provided
        extra = ""
        if additional_instructions and additional_instructions.strip():
            extra = f"\n\nADDITIONAL INSTRUCTIONS FROM USER: {additional_instructions.strip()}"

        full_system = system_prompt + style_context + extra

        # Build content parts
        contents = []

        # Add reference images if provided
        if images is not None:
            batch_size = images.shape[0]
            for i in range(batch_size):
                pil_img = _tensor_to_pil(images[i])
                # Resize for efficiency — we only need visual analysis, not full res
                max_dim = 1024
                if max(pil_img.size) > max_dim:
                    ratio = max_dim / max(pil_img.size)
                    new_size = (int(pil_img.size[0] * ratio), int(pil_img.size[1] * ratio))
                    pil_img = pil_img.resize(new_size, Image.LANCZOS)
                img_bytes = _pil_to_bytes(pil_img)
                contents.append(
                    types.Part.from_bytes(data=img_bytes, mime_type="image/jpeg")
                )
            print(f"[Prompt Studio] {batch_size} reference image(s) attached for analysis")

        # Add the brief
        if mode == "Expand":
            contents.append(f"Expand this creative brief into a full structured image generation prompt:\n\n{brief}")
        else:
            contents.append(f"Review and refine this image generation prompt — strengthen weak areas while preserving intent:\n\n{brief}")

        # Call Gemini text API
        print(f"[Prompt Studio] {mode} mode | {style_preset} | {model}")
        start_time = time.time()

        response = client.models.generate_content(
            model=model,
            contents=contents,
            config=types.GenerateContentConfig(
                system_instruction=full_system,
                response_modalities=["TEXT"],
            ),
        )
        elapsed = time.time() - start_time

        # Extract text
        enhanced = ""
        if response.candidates:
            for part in response.candidates[0].content.parts:
                if part.text:
                    enhanced += part.text

        if not enhanced.strip():
            raise RuntimeError("[Prompt Studio] No response from model. Try rephrasing your brief.")

        # Build analysis
        token_info = ""
        if hasattr(response, 'usage_metadata') and response.usage_metadata:
            meta = response.usage_metadata
            in_tok = getattr(meta, 'prompt_token_count', 0) or 0
            out_tok = getattr(meta, 'candidates_token_count', 0) or 0
            # Estimate cost (Gemini 3 Flash: ~$0.10/1M input, ~$0.40/1M output)
            est_cost = (in_tok * 0.10 + out_tok * 0.40) / 1_000_000
            token_info = f"Tokens: {in_tok} in / {out_tok} out | Est. ${est_cost:.6f}"

        analysis = (
            f"Mode: {mode} | Style: {style_preset} | Model: {model}\n"
            f"Time: {elapsed:.1f}s | {token_info}\n"
            f"Brief length: {len(brief)} chars | Enhanced: {len(enhanced)} chars"
        )

        print(f"[Prompt Studio] Done! {len(brief)} → {len(enhanced)} chars | {elapsed:.1f}s")

        return (enhanced, analysis)


# ============================================================================
# MAPPINGS
# ============================================================================

NODE_CLASS_MAPPINGS = {
    "PromptStudio": PromptStudio,
}

NODE_DISPLAY_NAME_MAPPINGS = {
    "PromptStudio": "Prompt Studio (AI Enhancer)",
}
