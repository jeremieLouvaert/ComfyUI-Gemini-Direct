# ComfyUI Gemini Direct

Direct Google Gemini image generation and AI prompt enhancement for ComfyUI — bypass the credit system and use your own API key.

A drop-in replacement for ComfyUI's built-in "Nano Banana Pro (Google Gemini Image)" node, plus an AI-powered prompt engineering tool. Instead of paying through ComfyUI's opaque credit system, this pack calls the Google Gemini API directly with your own key and shows you the real USD cost per generation.

## Nodes

### 1. Gemini Image Generate (Direct API)

Direct image generation with 3 model tiers and real cost transparency.

| Input | Type | Description |
|-------|------|-------------|
| `prompt` | STRING | Text prompt for image generation |
| `model` | COMBO | Model tier selection (Pro, 3.1 Flash, 2.5 Flash) |
| `seed` | INT | Seed for reproducibility |
| `aspect_ratio` | COMBO | auto, 1:1, 2:3, 3:2, 3:4, 4:3, 4:5, 5:4, 9:16, 16:9, 21:9 |
| `resolution` | COMBO | 512, 1K, 2K, or 4K (falls back if unsupported by model) |
| `response_modalities` | COMBO | IMAGE+TEXT or IMAGE only |
| `images` | IMAGE (optional) | Batched reference images as visual context |
| `system_prompt` | STRING (optional) | System instruction (default forces image output) |
| `api_key` | STRING (optional) | Google AI API key |

**Outputs:** `images` (IMAGE), `text` (STRING), `cost_info` (STRING), `cache_key` (STRING)

#### Cost per Image

| Model | Resolution | Cost per Image | Best For |
|-------|-----------|---------------|----------|
| Gemini 3 Pro | 1K-2K | ~$0.13 | Best quality |
| Gemini 3 Pro | 4K | ~$0.24 | High-res best quality |
| Gemini 3.1 Flash | 512-1K | $0.05-0.07 | Balanced quality/cost |
| Gemini 3.1 Flash | 2K-4K | $0.10-0.15 | Balanced, higher res |
| Gemini 2.5 Flash | 1K | ~$0.04 | Cheapest option |

ComfyUI's built-in Gemini node charges credits: **211 credits = $1 USD**, with no visibility into what each generation actually costs.

#### Reference Images

Batch multiple reference images and feed them as visual context. For example, batch a background image with character photos, then prompt "integrate these people into the background scene."

#### Cache Key Output

The `cache_key` output encodes all generation parameters (model, seed, aspect ratio, resolution, prompt) into a deterministic string. Wire it to the [ComfyUI API Optimizer](https://github.com/jeremieLouvaert/ComfyUI-API-Optimizer)'s Hash Vault so any parameter change triggers a fresh generation, while identical runs hit cache at $0.

---

### 2. Prompt Studio (AI Enhancer)

AI-powered prompt engineering using Gemini text models. Domain-adaptive with a built-in anti-AI realism mandate.

| Input | Type | Description |
|-------|------|-------------|
| `brief` | STRING | Creative direction (short brief or full prompt) |
| `mode` | COMBO | Expand, Refine, or Edit |
| `model` | COMBO | Gemini 3 Flash recommended (~$0.001/call) |
| `images` | IMAGE (optional) | Reference images for visual context analysis |
| `previous_prompt` | STRING (optional) | For Edit mode: wire enhanced_prompt back here |
| `feedback` | STRING (optional) | For Edit mode: what to change |
| `custom_instructions` | STRING (optional) | Extra directives for any mode |
| `api_key` | STRING (optional) | Google AI API key |

**Outputs:** `enhanced_prompt` (STRING), `analysis` (STRING)

#### Three Modes

**Expand** — Short brief to full structured prompt. The LLM detects the creative domain (architecture, fashion, portrait, product, fine art) and generates appropriate section structures automatically.

```
"brutalist concrete interior, Tadao Ando, morning light, ArchDigest editorial"
  --> Full structured prompt with Spatial Composition, Material & Texture,
      Light Study, Architectural Context, Editorial Style sections
```

**Refine** — Takes your existing full prompt and surgically strengthens weak areas, adds missing technical detail, and enforces the realism mandate. Preserves your intent and structure.

**Edit** — Iterative adjustment loop. Wire the previous `enhanced_prompt` back into `previous_prompt`, write your feedback, and only the sections you mention get changed.

```
Prompt Studio (Expand) --> enhanced_prompt --> Preview
                                  |
                 Not happy?       |  Wire it back:
                                  v
                Prompt Studio (Edit) <-- previous_prompt
                     feedback: "change lens to 24mm, make it golden hour"
                          |
                          v
                    edited_prompt --> Gemini Direct
```

#### Anti-AI Realism Mandate

Every prompt — regardless of domain — is engineered to avoid AI-generated aesthetics:

- Real camera body + lens combinations (Leica M6, Hasselblad 500C/M, etc.)
- Specific film stocks or sensor characteristics (Kodachrome 64, Portra 400)
- Optical imperfections: chromatic aberration, vignetting, halation
- Physical grain structure (silver halide, sensor noise)
- Micro-texture on all surfaces: pores, weave, wood grain, concrete
- No plastic skin, no AI sheen, no impossibly clean environments

#### Domain-Adaptive Structure

The LLM automatically detects the creative domain from your brief and generates the most appropriate section structure:

- **Portrait/Street** — Camera, Subject Lock, Tonal Refinement, Environment, Photographic Style
- **Architecture/Interior** — Spatial Composition, Material & Texture, Light Study, Architectural Context
- **Fashion/Editorial** — Model Direction, Wardrobe & Styling, Lighting Design, Set Design
- **Product/Commercial** — Product Detail, Lighting Setup, Surface & Background
- **Fine Art** — Composition & Form, Palette & Tonality, Medium Reference

---

## API Key Setup

Provide your Google AI API key via one of these methods (checked in order):

1. **Key file** — create a `gemini_api_key.txt` file in your ComfyUI root directory (recommended)
2. **Environment variable** — set `GEMINI_API_KEY` in your system environment
3. **Direct input** — paste into the `api_key` field on the node (not recommended — visible in workflow JSON)

Get an API key at [Google AI Studio](https://aistudio.google.com/apikey). Billing must be enabled for image generation.

## Installation

Clone this repository into your `ComfyUI/custom_nodes/` directory:

```bash
cd ComfyUI/custom_nodes/
git clone https://github.com/jeremieLouvaert/ComfyUI-Gemini-Direct.git
pip install -r ComfyUI-Gemini-Direct/requirements.txt
```

Restart ComfyUI. Nodes appear under the **Gemini Direct** category.

### Dependencies

- **google-genai** >= 1.0.0 — Google's Gen AI Python SDK
- **Pillow** — image conversion
- **PyTorch** — already present in any ComfyUI installation

## License

MIT
