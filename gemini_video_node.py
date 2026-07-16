"""
ComfyUI Gemini Video Omni — video generation + conversational video editing
using Google's Gemini Omni model (Interactions API).

Text/images/video in -> 3-10s 720p/24fps video WITH audio out. Uses the
stateful Interactions API (client.interactions.create()), where wiring the
returned interaction_id back into a second instance of this node lets you
refine the previous video server-side ("generate -> swap character ->
golden hour" as chained nodes) instead of re-describing the whole scene.

Direct API / BYOK: no ComfyUI credits, real USD cost display.
"""

import os
import io
import time
import base64
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

try:
    from comfy_api.latest import InputImpl, Types
    HAS_COMFY_VIDEO = True
except ImportError:
    HAS_COMFY_VIDEO = False

# ---------------------------------------------------------------------------
# CONSTANTS
# ---------------------------------------------------------------------------

VIDEO_MODELS = ["gemini-omni-flash-preview"]

VIDEO_ASPECTS = ["16:9", "9:16"]

MAX_REF_IMAGES = 14

# $ per million tokens
INPUT_PER_MTOK = 1.50
VIDEO_OUT_PER_MTOK = 17.50

CATEGORY = "Gemini Direct"

# ---------------------------------------------------------------------------
# UTILITIES (duplicated per house pattern -- see style_transfer_node.py /
# gemini_direct_nodes.py, no shared utils module in this pack)
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


def _get_client(api_key, timeout_sec=480):
    if not HAS_GENAI:
        raise ImportError(
            "[Gemini Direct] google-genai package not installed.\n"
            "Run: pip install google-genai"
        )
    http_options = types.HttpOptions(timeout=int(timeout_sec) * 1000)
    return genai.Client(api_key=api_key, http_options=http_options)


def _tensor_to_pil(tensor):
    """Convert an IMAGE tensor to PIL. Guards against a leftover batch dim
    (single-image slices from a batch already drop it, but be defensive)."""
    if len(tensor.shape) == 4:
        tensor = tensor[0]
    arr = (tensor.cpu().numpy() * 255).clip(0, 255).astype(np.uint8)
    return Image.fromarray(arr, "RGB")


def _pil_to_bytes(pil_img, fmt="PNG"):
    buf = io.BytesIO()
    pil_img.save(buf, format=fmt)
    return buf.getvalue()


def _get_output_dir():
    if folder_paths:
        return folder_paths.get_output_directory()
    return os.path.join(os.path.dirname(__file__), "output")


def _save_video(video_bytes, prefix="video_omni"):
    """Save raw mp4 bytes to ComfyUI output dir, return path. No re-encode --
    the bytes came straight off the wire from Gemini (or the Files API)."""
    out_dir = os.path.join(_get_output_dir(), "gemini_direct")
    os.makedirs(out_dir, exist_ok=True)
    timestamp = time.strftime("%Y%m%d_%H%M%S")
    filename = f"{prefix}_{timestamp}.mp4"
    filepath = os.path.join(out_dir, filename)
    with open(filepath, "wb") as f:
        f.write(video_bytes)
    return filepath


def _fetch_video_bytes(client, uri, api_key):
    """Resolve a video output URI to raw bytes.

    Model-generated outputs live under the Files API (files/...): poll until
    ACTIVE, then use the SDK's authenticated download. If the URI isn't a
    files/ resource (or files.get otherwise chokes on it), fall back to a
    raw authenticated GET against the URI itself.
    """
    try:
        f = client.files.get(name=uri)
        poll_start = time.time()
        while f.state == "PROCESSING":
            if time.time() - poll_start > 120:
                raise RuntimeError(
                    f"[Gemini Direct] Generated video did not reach ACTIVE within "
                    f"120s (state={f.state})."
                )
            time.sleep(2)
            f = client.files.get(name=uri)
        if f.state != "ACTIVE":
            raise RuntimeError(
                f"[Gemini Direct] Generated video file is not usable (state={f.state})."
            )
        return client.files.download(file=f)
    except RuntimeError:
        raise
    except Exception as e:
        print(f"[Gemini Direct] files.get on '{uri}' failed ({e}), falling back to raw GET")
        import httpx
        resp = httpx.get(uri, headers={"x-goog-api-key": api_key}, timeout=120.0)
        resp.raise_for_status()
        return resp.content


# ============================================================================
# NODE: GEMINI VIDEO OMNI (Direct API)
# ============================================================================

class GeminiVideoOmni:
    """Video generation + conversational video editing via Gemini Omni.
    Text/images/video in -> 3-10s 720p/24fps video with audio out. Wire
    interaction_id from one instance into another to chain edits server-side
    (only the edit is billed, not a full re-generation)."""

    @classmethod
    def INPUT_TYPES(s):
        return {
            "required": {
                "prompt": ("STRING", {
                    "multiline": True,
                    "default": "",
                    "tooltip": (
                        "Describe the scene, dialogue and sound. State the desired "
                        "DURATION explicitly (3-10s) -- there is no duration widget. "
                        "Output is fixed at 720p/24fps with audio."
                    ),
                }),
                "model": (VIDEO_MODELS, {
                    "default": VIDEO_MODELS[0],
                    "tooltip": "Gemini Omni video model.",
                }),
                "aspect_ratio": (VIDEO_ASPECTS, {
                    "default": "16:9",
                    "tooltip": "Output aspect ratio.",
                }),
                "seed": ("INT", {
                    "default": 0,
                    "min": 0,
                    "max": 0xFFFFFFFFFFFFFFFF,
                    "tooltip": (
                        "Re-run trigger only -- NOT sent to the API. Gemini Omni "
                        "video is non-deterministic regardless of seed; change this "
                        "to force ComfyUI to re-execute the node."
                    ),
                }),
            },
            "optional": {
                "images": ("IMAGE", {
                    "tooltip": f"Reference images (batched), up to {MAX_REF_IMAGES}.",
                }),
                "video": ("VIDEO", {
                    "tooltip": (
                        "Reference video to edit (<=10s, >=3s recommended). "
                        "EEA/CH/UK: editing an UPLOADED video is region-blocked. "
                        "Wire interaction_id instead to edit a GENERATED video."
                    ),
                }),
                "interaction_id": ("STRING", {
                    "default": "",
                    "tooltip": (
                        "Interaction ID of a previous turn to continue/edit "
                        "server-side. Wire from another Gemini Video Omni node's "
                        "interaction_id output, or paste one to resume across "
                        "sessions (expires ~55 days; requires store=True)."
                    ),
                }),
                "store": ("BOOLEAN", {
                    "default": True,
                    "tooltip": (
                        "Retain this interaction server-side so it can be continued "
                        "via interaction_id. Required for chaining. Set False for "
                        "privacy -- breaks chaining on this turn."
                    ),
                }),
                "api_key": ("STRING", {
                    "default": "",
                    "tooltip": (
                        "Google AI API key. Falls back to GEMINI_API_KEY env var "
                        "or gemini_api_key.txt in ComfyUI root."
                    ),
                }),
                "timeout_sec": ("INT", {
                    "default": 480,
                    "min": 10,
                    "max": 1800,
                    "tooltip": "HTTP timeout (seconds) for the Gemini API call. Default 480s.",
                }),
            },
        }

    RETURN_TYPES = ("VIDEO", "STRING", "STRING", "STRING", "STRING")
    RETURN_NAMES = ("video", "text", "interaction_id", "cost_info", "cache_key")
    FUNCTION = "generate"
    CATEGORY = CATEGORY

    def generate(self, prompt, model, aspect_ratio, seed, images=None, video=None,
                 interaction_id="", store=True, api_key="", timeout_sec=480):

        if not HAS_COMFY_VIDEO:
            raise ImportError(
                "[Gemini Direct] comfy_api.latest (InputImpl/Types) not available. "
                "VIDEO input/output requires a ComfyUI core with the modern Video "
                "API (0.28+). Update ComfyUI to use Gemini Video Omni."
            )

        interaction_id = (interaction_id or "").strip()

        # 1. Validate ------------------------------------------------------
        if not (prompt and prompt.strip()) and not interaction_id:
            raise ValueError(
                "[Gemini Direct] Provide a prompt, or an interaction_id to "
                "continue a previous turn."
            )

        n_images = 0
        if images is not None:
            n_images = images.shape[0]
            if n_images > MAX_REF_IMAGES:
                raise ValueError(
                    f"[Gemini Direct] {n_images} reference images given, max is {MAX_REF_IMAGES}."
                )

        if video is not None:
            try:
                ref_duration = video.get_duration()
            except Exception:
                ref_duration = None  # exotic VIDEO impls may not know; let the API judge
            if ref_duration and ref_duration > 10:
                raise ValueError(
                    f"[Gemini Direct] Reference video is {ref_duration:.1f}s, max is 10s."
                )
            if ref_duration and ref_duration < 3:
                print(
                    f"[Gemini Direct] WARNING: reference video is {ref_duration:.1f}s "
                    "(<3s) -- Gemini Omni may silently misprocess very short clips."
                )

        resolved_key = _resolve_api_key(api_key)
        client = _get_client(resolved_key, timeout_sec=timeout_sec)

        # Build deterministic cache key from all generation parameters
        cache_key = (
            f"video_omni|{model}|{seed}|{aspect_ratio}|{int(store)}|{interaction_id}|"
            f"{n_images}img|{'vid' if video is not None else 'novid'}|{prompt}"
        )

        # 2. Build parts -----------------------------------------------------
        parts = []

        if images is not None:
            for i in range(n_images):
                pil_img = _tensor_to_pil(images[i])
                img_bytes = _pil_to_bytes(pil_img)
                b64_data = base64.b64encode(img_bytes).decode("utf-8")
                parts.append({"type": "image", "data": b64_data, "mime_type": "image/png"})
            print(f"[Gemini Direct] {n_images} reference image(s) attached")

        if video is not None:
            buf = io.BytesIO()
            video.save_to(buf, format=Types.VideoContainer.MP4, codec=Types.VideoCodec.H264)
            video_bytes = buf.getvalue()

            print(f"[Gemini Direct] Uploading reference video ({len(video_bytes)} bytes)...")
            uploaded = client.files.upload(
                file=io.BytesIO(video_bytes),
                config={"mime_type": "video/mp4"},
            )
            poll_start = time.time()
            while uploaded.state == "PROCESSING":
                if time.time() - poll_start > 300:
                    raise RuntimeError(
                        "[Gemini Direct] Reference video upload did not reach "
                        f"ACTIVE within 300s (state={uploaded.state})."
                    )
                time.sleep(2)
                uploaded = client.files.get(name=uploaded.name)
            if uploaded.state != "ACTIVE":
                raise RuntimeError(
                    f"[Gemini Direct] Reference video upload failed (state={uploaded.state})."
                )

            # SDK >= 2.0 types "document" as PDF/CSV only; uploaded video goes
            # in as a "video" content part (the legacy docs said "document").
            parts.append({"type": "video", "uri": uploaded.uri, "mime_type": "video/mp4"})
            print(f"[Gemini Direct] Reference video ACTIVE: {uploaded.uri}")

        parts.append({"type": "text", "text": prompt})

        # 3. Call the Interactions API ---------------------------------------
        create_kwargs = {
            "model": model,
            "input": parts,
            "response_format": {"type": "video", "aspect_ratio": aspect_ratio, "delivery": "uri"},
            "background": False,
            "stream": False,
            "store": store,
            "timeout": float(timeout_sec),
        }
        if interaction_id:
            create_kwargs["previous_interaction_id"] = interaction_id

        print(
            f"[Gemini Direct] Generating video: {model} @ {aspect_ratio} | store={store}"
            + (f" | continuing {interaction_id}" if interaction_id else "")
        )

        start_time = time.time()
        try:
            interaction = client.interactions.create(**create_kwargs)
        except Exception as e:
            # SDK exception classes live on a private path -- don't import them,
            # inspect the response shape instead.
            status_code = getattr(e, "status_code", None)
            message = str(e)
            if any(k in message.lower() for k in
                   ("region", "location is not supported", "failed_precondition")):
                raise RuntimeError(
                    "[Gemini Direct] Region restriction: Gemini Omni video editing "
                    "on an UPLOADED video is blocked in EEA/CH/UK. Editing a "
                    "GENERATED video via interaction_id is still expected to work "
                    "-- wire this node's interaction_id output into a second "
                    "Gemini Video Omni node instead of uploading raw footage.\n"
                    f"Raw error: {message}"
                ) from e
            if status_code == 404 and interaction_id:
                raise RuntimeError(
                    f"[Gemini Direct] interaction_id '{interaction_id}' not found "
                    "(404). It may have expired (~55 days) or was created with "
                    "store=False (not retained server-side). Re-run the "
                    "originating node with store=True.\n"
                    f"Raw error: {message}"
                ) from e
            raise RuntimeError(f"[Gemini Direct] interactions.create failed: {message}") from e
        elapsed = time.time() - start_time

        # 4. Extract outputs (SDK >= 2.0 schema: steps timeline + output_*
        # convenience fields; the 1.x flat `outputs` list no longer exists) ----
        text_out = getattr(interaction, "output_text", None) or ""
        video_content = getattr(interaction, "output_video", None)
        if video_content is None or not text_out:
            for step in (getattr(interaction, "steps", None) or []):
                for c in (getattr(step, "content", None) or []):
                    c_type = getattr(c, "type", "")
                    if c_type == "text" and not getattr(interaction, "output_text", None):
                        text_out += getattr(c, "text", "") or ""
                    elif c_type == "video" and video_content is None:
                        video_content = c

        if interaction.status != "completed":
            raise RuntimeError(
                f"[Gemini Direct] Interaction did not complete (status="
                f"{interaction.status}). Model said: {text_out}"
            )

        if video_content is None:
            raise RuntimeError(
                f"[Gemini Direct] No video in response. Model said: {text_out}\n"
                "Try stating an explicit 3-10s duration and describing the "
                "scene/dialogue/sound in the prompt."
            )

        if getattr(video_content, "data", None):
            video_bytes_out = base64.b64decode(video_content.data)
        else:
            uri = getattr(video_content, "uri", None)
            if not uri:
                raise RuntimeError(
                    "[Gemini Direct] Video output has neither inline data nor a URI."
                )
            video_bytes_out = _fetch_video_bytes(client, uri, resolved_key)

        # 5. Save + wrap ---------------------------------------------------
        filepath = _save_video(video_bytes_out)
        video_obj = InputImpl.VideoFromFile(filepath)

        out_duration = None
        try:
            out_duration = video_obj.get_duration()
        except Exception:
            pass

        # 6. Cost ------------------------------------------------------------
        usage = interaction.usage
        if usage:
            total_in = usage.total_input_tokens or 0
            billable_out = None
            for e in (usage.output_tokens_by_modality or []):
                if str(e.modality).lower() == "video":
                    billable_out = e.tokens or 0
                    break
            if billable_out is None:
                billable_out = usage.total_output_tokens or 0
            cost = (total_in * INPUT_PER_MTOK / 1_000_000) + (billable_out * VIDEO_OUT_PER_MTOK / 1_000_000)
            cost_str = f"${cost:.4f}"
            token_info = f" | Tokens: {total_in} in / {billable_out} out"
        else:
            est_duration = out_duration if out_duration else 5.0
            cost = 0.10 * est_duration
            cost_str = f"~${cost:.4f}"
            token_info = ""

        duration_info = f" | {out_duration:.1f}s video" if out_duration else ""
        cost_info = (
            f"{cost_str} USD | {model} @ {aspect_ratio} | {elapsed:.1f}s{token_info}"
            f"{duration_info} | {os.path.basename(filepath)}"
        )

        print(
            f"[Gemini Direct] Done! {cost_str} | {elapsed:.1f}s | "
            f"{os.path.basename(filepath)} | interaction_id={interaction.id}"
        )

        return (video_obj, text_out, interaction.id or "", cost_info, cache_key)


# ============================================================================
# MAPPINGS
# ============================================================================

NODE_CLASS_MAPPINGS = {
    "GeminiVideoOmniDirect": GeminiVideoOmni,
}

NODE_DISPLAY_NAME_MAPPINGS = {
    "GeminiVideoOmniDirect": "Gemini Video Omni (Direct API)",
}
