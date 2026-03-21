"""
ComfyUI Prompt Studio — AI-powered prompt enhancement for image generation.
Uses Gemini text models to expand briefs, refine, or iteratively edit prompts.

Domain-adaptive: detects the creative domain from your brief and generates
appropriate section structures. Anti-AI-look realism mandate is always enforced.
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

MODES = ["Expand", "Refine", "Edit"]

CATEGORY = "Gemini Direct"

# ---------------------------------------------------------------------------
# REALISM MANDATE — always injected into every prompt, every domain
# ---------------------------------------------------------------------------

REALISM_MANDATE = """
ABSOLUTE REALISM MANDATE (apply to EVERY prompt you generate, regardless of domain):

You must engineer prompts that produce images indistinguishable from real photography.
Eliminate all hallmarks of AI-generated imagery:
- NO plastic/waxy skin or fabric — specify pores, weave, thread count, material wear
- NO uniform lighting glow — specify hard shadow edges, falloff zones, bounce light physics
- NO perfect symmetry — introduce organic asymmetry in composition, posture, architecture
- NO AI "sheen" on surfaces — specify matte/gloss/satin finishes with dust, fingerprints, patina, weathering
- NO impossibly clean environments — add realistic entropy (scuffs, stains, wear patterns, aging)
- NO generic depth of field — specify exact aperture behavior, bokeh character (busy/smooth/swirly), focus plane placement

ALWAYS include:
- Real camera body + lens combination (e.g., "Leica M6 + 35mm Summicron f/2", "Hasselblad 500C/M + 80mm Planar")
- Film stock OR sensor characteristics (e.g., "Kodachrome 64", "Portra 400 pushed +1", "Phase One IQ4 150MP sensor")
- Optical imperfections: chromatic aberration at edges, subtle lens distortion, vignetting, halation on highlights
- Physical grain structure: silver halide grain (film) or controlled sensor noise (digital) — never smooth/clean
- Micro-texture on ALL surfaces: concrete pores, fabric weave, skin texture, wood grain, metal brushing
"""

# ---------------------------------------------------------------------------
# SYSTEM PROMPTS
# ---------------------------------------------------------------------------

EXPAND_SYSTEM_PROMPT = """You are an elite image generation prompt engineer. Your job is to take a short creative brief and expand it into a comprehensive, structured prompt that will produce photorealistic results indistinguishable from real photography or professional editorial work.

DOMAIN-ADAPTIVE STRUCTURE:
Analyze the brief to detect the creative domain, then use the most appropriate section structure. Examples:

For PORTRAIT / STREET / DOCUMENTARY photography:
- CRITICAL INSTRUCTION (core vision + era + aesthetic mandate)
- CAMERA RE-COMPOSITION (angle, lens, framing, focus plane)
- SUBJECT LOCK (identity, action, expression, wardrobe detail)
- TONAL REFINEMENT (color science, lighting, shadow behavior, micro-contrast)
- ENVIRONMENT (textures, setting, atmosphere)
- PHOTOGRAPHIC STYLE (gear, settings, film profile, optical characteristics)

For ARCHITECTURAL / INTERIOR photography:
- CRITICAL INSTRUCTION (core vision + publication reference + aesthetic)
- SPATIAL COMPOSITION (viewpoint, perspective, leading lines, scale)
- MATERIAL & TEXTURE (concrete, glass, steel, wood — specific finishes and aging)
- LIGHT STUDY (natural/artificial, direction, quality, caustics, shadow geometry)
- ARCHITECTURAL CONTEXT (style movement, era, architect references, surrounding landscape)
- EDITORIAL STYLE (publication reference, photographer reference, gear, format)

For FASHION / EDITORIAL:
- CRITICAL INSTRUCTION (concept, mood, publication tier)
- MODEL DIRECTION (pose, expression, body language, attitude)
- WARDROBE & STYLING (garments, fabrics, accessories, hair, makeup — specific references)
- LIGHTING DESIGN (key/fill/rim setup, modifier types, light quality)
- SET DESIGN & ENVIRONMENT (backdrop, props, spatial context)
- EDITORIAL TECHNIQUE (photographer reference, camera + lens, color grade, publication style)

For PRODUCT / COMMERCIAL:
- CRITICAL INSTRUCTION (product, brand positioning, hero angle)
- PRODUCT DETAIL (materials, finish, scale, key features to highlight)
- LIGHTING SETUP (studio configuration, reflections, caustics, material rendering)
- SURFACE & BACKGROUND (surface material, backdrop, negative space)
- COMMERCIAL STYLE (brand references, photographer, camera, post-production feel)

For FINE ART / CONCEPTUAL:
- CRITICAL INSTRUCTION (concept, art historical references, emotional intent)
- COMPOSITION & FORM (visual structure, symbolism, spatial relationships)
- PALETTE & TONALITY (color theory, contrast, mood)
- MEDIUM REFERENCE (painting technique, print process, or photographic process referenced)
- TECHNICAL EXECUTION (camera/lens if photographic, or rendering characteristics)

You may create hybrid structures when the brief spans multiple domains.
Always end with a TECHNICAL FOUNDATION section covering camera, lens, and film/sensor.

""" + REALISM_MANDATE + """

RULES:
- Be highly specific and technical — every directive must be actionable
- Use real-world references: actual cameras, lenses, film stocks, photographers, publications, architects, designers
- The prompt must read like art direction from a senior creative director
- If reference images are provided, analyze and incorporate their visual qualities
- Do NOT include any preamble, explanation, or commentary — output ONLY the structured prompt
- Do NOT use generic terms: "beautiful", "stunning", "high quality", "professional" — these are meaningless
"""

REFINE_SYSTEM_PROMPT = """You are an elite image generation prompt reviewer. Take an existing prompt and surgically strengthen it while preserving the author's creative intent.

""" + REALISM_MANDATE + """

YOUR TASKS:
1. Detect weak or vague language and replace with specific, actionable directives
2. Add missing technical detail — exact camera gear, lens specs, film stocks, lighting physics
3. Fix inconsistencies — conflicting lighting, impossible camera settings, contradictory descriptions
4. Strengthen material/texture descriptions — replace generic surfaces with specific physical properties
5. Enforce the Realism Mandate — add anti-AI directives if missing (optical imperfections, micro-texture, organic asymmetry)
6. If reference images are provided, incorporate relevant visual qualities

RULES:
- PRESERVE the author's creative intent, vision, and concept — do not change what they're going for
- PRESERVE the existing structure and section headers
- If no structure exists, add domain-appropriate sections while keeping all original content
- Do NOT remove author's content — only enhance, specify, and add
- Be surgical — strengthen weak areas, leave strong areas untouched
- Output ONLY the refined prompt — no preamble, no commentary, no explanations
"""

EDIT_SYSTEM_PROMPT = """You are an elite image generation prompt editor. You will receive a previously enhanced prompt and the user's feedback about what to change. Apply their edits precisely.

""" + REALISM_MANDATE + """

YOUR TASKS:
1. Read the existing prompt carefully
2. Apply the user's requested changes — and ONLY those changes
3. Maintain the overall structure, quality level, and all unchanged sections
4. If the user asks to change something vague, interpret it in the most specific way possible
5. Ensure the edited prompt still adheres to the Realism Mandate

RULES:
- ONLY change what the user explicitly asks to change
- Do NOT "improve" or alter sections the user didn't mention
- Maintain the same section structure and level of detail
- If the user asks to add something new, integrate it naturally into the existing structure
- Output ONLY the edited prompt — no preamble, no commentary, no "here's what I changed"
"""

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
    """AI-powered prompt enhancement with domain-adaptive structure.
    Three modes: Expand (brief to full prompt), Refine (strengthen existing),
    Edit (iterative adjustment with feedback). Anti-AI realism always enforced."""

    @classmethod
    def INPUT_TYPES(s):
        return {
            "required": {
                "brief": ("STRING", {
                    "multiline": True,
                    "default": "",
                    "tooltip": (
                        "Expand: short creative direction. "
                        "Refine: full prompt to strengthen. "
                        "Edit: leave empty and use previous_prompt + feedback instead."
                    ),
                }),
                "mode": (MODES, {
                    "default": "Expand",
                    "tooltip": (
                        "Expand: brief to full structured prompt. "
                        "Refine: strengthen existing prompt. "
                        "Edit: adjust previous output with feedback."
                    ),
                }),
                "model": (TEXT_MODELS, {
                    "default": TEXT_MODELS[0],
                    "tooltip": "Gemini 3 Flash recommended — fast and near-free for text.",
                }),
            },
            "optional": {
                "images": ("IMAGE", {
                    "tooltip": "Reference images for visual context analysis.",
                }),
                "previous_prompt": ("STRING", {
                    "forceInput": True,
                    "tooltip": "For Edit mode: wire the enhanced_prompt output back here.",
                }),
                "feedback": ("STRING", {
                    "multiline": True,
                    "default": "",
                    "tooltip": (
                        "For Edit mode: what to change (e.g. 'make lighting more dramatic', "
                        "'change lens to 24mm wide angle', 'swap film stock to Portra 400')."
                    ),
                }),
                "custom_instructions": ("STRING", {
                    "multiline": True,
                    "default": "",
                    "tooltip": (
                        "Extra directives for any mode. Examples: "
                        "'use only Hasselblad medium format references', "
                        "'target Architectural Digest editorial style', "
                        "'keep prompt under 500 words'."
                    ),
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

    def enhance(self, brief, mode, model,
                images=None, previous_prompt=None, feedback="",
                custom_instructions="", api_key=""):

        # Validate inputs based on mode
        if mode == "Edit":
            if not previous_prompt or not previous_prompt.strip():
                raise ValueError(
                    "[Prompt Studio] Edit mode requires previous_prompt. "
                    "Wire the enhanced_prompt output from a previous run back into previous_prompt."
                )
            if not feedback or not feedback.strip():
                raise ValueError(
                    "[Prompt Studio] Edit mode requires feedback. "
                    "Describe what to change in the feedback field."
                )
        elif not brief.strip():
            raise ValueError("[Prompt Studio] Brief is empty. Write something to enhance.")

        resolved_key = _resolve_api_key(api_key)
        client = _get_client(resolved_key)

        # Select system prompt based on mode
        if mode == "Expand":
            system_prompt = EXPAND_SYSTEM_PROMPT
        elif mode == "Refine":
            system_prompt = REFINE_SYSTEM_PROMPT
        else:
            system_prompt = EDIT_SYSTEM_PROMPT

        # Add custom instructions if provided
        if custom_instructions and custom_instructions.strip():
            system_prompt += f"\n\nADDITIONAL USER DIRECTIVES: {custom_instructions.strip()}"

        # Build content parts
        contents = []

        # Add reference images if provided
        if images is not None:
            batch_size = images.shape[0]
            for i in range(batch_size):
                pil_img = _tensor_to_pil(images[i])
                # Resize for efficiency — visual analysis doesn't need full res
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

        # Build the user message based on mode
        if mode == "Expand":
            contents.append(
                f"Expand this creative brief into a full structured image generation prompt:\n\n{brief}"
            )
        elif mode == "Refine":
            contents.append(
                f"Review and refine this image generation prompt — "
                f"strengthen weak areas while preserving intent:\n\n{brief}"
            )
        else:  # Edit
            contents.append(
                f"Here is the current prompt:\n\n{previous_prompt}\n\n"
                f"Apply these changes:\n\n{feedback}"
            )

        # Call Gemini text API
        print(f"[Prompt Studio] {mode} mode | {model}")
        start_time = time.time()

        response = client.models.generate_content(
            model=model,
            contents=contents,
            config=types.GenerateContentConfig(
                system_instruction=system_prompt,
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
            est_cost = (in_tok * 0.10 + out_tok * 0.40) / 1_000_000
            token_info = f"Tokens: {in_tok} in / {out_tok} out | Est. ${est_cost:.6f}"

        input_len = len(previous_prompt) if mode == "Edit" else len(brief)
        analysis = (
            f"Mode: {mode} | Model: {model}\n"
            f"Time: {elapsed:.1f}s | {token_info}\n"
            f"Input: {input_len} chars | Output: {len(enhanced)} chars"
        )

        print(f"[Prompt Studio] Done! {input_len} -> {len(enhanced)} chars | {elapsed:.1f}s")

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
