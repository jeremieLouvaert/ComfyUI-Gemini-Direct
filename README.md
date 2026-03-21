# ComfyUI Gemini Direct

Direct Google Gemini image generation for ComfyUI — bypass the credit system and use your own API key.

A drop-in replacement for ComfyUI's built-in "Nano Banana Pro (Google Gemini Image)" node. Instead of paying through ComfyUI's opaque credit system, this node calls the Google Gemini API directly with your own key and shows you the real USD cost per generation.

## Why Direct API?

ComfyUI's built-in Gemini node charges credits: **211 credits = $1 USD**, with no visibility into what each generation actually costs.

With Gemini Direct, you pay Google's API rates directly and see the exact cost:

| Model | Resolution | Cost per Image | Best For |
|-------|-----------|---------------|----------|
| Gemini 3 Pro | 1K–2K | ~$0.13 | Best quality |
| Gemini 3 Pro | 4K | ~$0.24 | High-res best quality |
| Gemini 3.1 Flash | 512–1K | $0.05–0.07 | Balanced quality/cost |
| Gemini 3.1 Flash | 2K–4K | $0.10–0.15 | Balanced, higher res |
| Gemini 2.5 Flash | 1K | ~$0.04 | Cheapest option |

## Node: Gemini Image Generate (Direct API)

| Input | Type | Description |
|-------|------|-------------|
| `prompt` | STRING | Text prompt for image generation |
| `model` | COMBO | Model tier selection (Pro, 3.1 Flash, 2.5 Flash) |
| `seed` | INT | Seed for reproducibility |
| `aspect_ratio` | COMBO | 1:1, 2:3, 3:2, 3:4, 4:3, 4:5, 5:4, 9:16, 16:9, 21:9, or auto |
| `resolution` | COMBO | 512, 1K, 2K, or 4K (falls back if unsupported by model) |
| `response_modalities` | COMBO | IMAGE+TEXT or IMAGE only |
| `images` | IMAGE (optional) | Batched reference images as visual context |
| `system_prompt` | STRING (optional) | System instruction (default forces image output) |
| `api_key` | STRING (optional) | Google AI API key |

**Outputs:** `images` (IMAGE), `text` (STRING), `cost_info` (STRING)

### Reference Images

Like the built-in node's multi-image support, you can batch multiple reference images and feed them as visual context. For example, batch a background image with character photos, then prompt "integrate these people into the background scene."

### Cost Info Output

The `cost_info` output shows the real cost of each generation:

```
$0.1340 USD | gemini-3-pro-image-preview @ 2K | 3.2s | Tokens: 142 in / 1584 out | gemini_direct_20260321_143022.png
```

### Hash Vault Compatibility

Pair this node with the [ComfyUI API Optimizer](https://github.com/jeremieLouvaert/ComfyUI-API-Optimizer)'s Hash Vault caching. On cache hits, the API node never executes — repeat generations cost $0.

## API Key Setup

Provide your Google AI API key via one of these methods (checked in order):

1. **Direct input** — paste into the `api_key` field on the node
2. **Environment variable** — set `GEMINI_API_KEY` in your system environment
3. **Key file** — create a `gemini_api_key.txt` file in your ComfyUI root directory

Get a free API key at [Google AI Studio](https://aistudio.google.com/apikey).

## Output Files

Generated images are auto-saved to your ComfyUI output directory:

| Path | Description |
|------|-------------|
| `output/gemini_direct/gemini_direct_YYYYMMDD_HHMMSS.png` | Auto-saved generation output |

## Installation

Clone this repository into your `ComfyUI/custom_nodes/` directory:

```bash
cd ComfyUI/custom_nodes/
git clone https://github.com/jeremieLouvaert/ComfyUI-Gemini-Direct.git
pip install -r ComfyUI-Gemini-Direct/requirements.txt
```

Restart ComfyUI.

### Dependencies

- **google-genai** >= 1.0.0 — Google's Gen AI Python SDK
- **Pillow** — image conversion
- **PyTorch** — already present in any ComfyUI installation

## License

MIT
