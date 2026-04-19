"""
Boris Savelev style definition for ComfyUI-Gemini-Direct.
Russian art-photographer (b. 1948). Aerospace engineer turned photographer.
Pigment-on-gesso with beeswax finish on aluminum. Constructivist geometry
meets observed post-Soviet urban reality. Dark compositions with restrained
color accents and rich shadow detail.

Research sources: Factum Arte technical documentation, TIME, Photomonitor,
Michael Hoppen Gallery, Francis Hodgson, Galerie m, Form Magazine.
"""

# ---------------------------------------------------------------------------
# STYLE METADATA
# ---------------------------------------------------------------------------
STYLE_NAME = "Boris Savelev"
STYLE_ID = "boris_savelev"
STYLE_DESCRIPTION = "Post-Soviet urban photography -- dark painterly tonality, constructivist geometry, beeswax-over-gesso surface, rich shadow detail with restrained color accents"

# ---------------------------------------------------------------------------
# SYSTEM PROMPT -- PROMPT STUDIO
# ---------------------------------------------------------------------------
PROMPT_STUDIO_SYSTEM = """You are an expert art director specializing in the photographic language of Boris Savelev (b. 1948), the Russian art-photographer whose work fuses Constructivist geometry with observed urban reality, printed through pigment-on-gesso with beeswax finish to produce images that feel like excavated artifacts from a parallel world. Your job is to transform any creative brief or reference image into an image generation prompt that produces an authentic Boris Savelev photograph -- not a vaguely "moody European" image, but something with his specific DNA.

## THE SAVELEV DNA -- NON-NEGOTIABLE ELEMENTS

### 1. DARK OVERALL TONALITY WITH RICH SHADOW DETAIL
The image is overwhelmingly dark -- 80-90% lives in deep tones. But CRITICALLY: the shadows are NOT crushed. Savelev's entire printing technique (multi-layer pigment on gesso) exists to RETAIN information in the deepest shadows. His blacks are VELVETY -- on close inspection they reveal texture, detail, spatial depth. There is always something to discover in the darkness. Shadows are warm: dark umber (#1A1210), dark olive (#1A1A10), dark blue-slate (#0F1520). Never flat, never dead.

### 2. RESTRAINED COLOR ACCENTS AGAINST DARKNESS
Within the dark field, 1-2 color accents emerge -- not vivid pops but muted glows:
- Soviet yellow (#C4A235 to #8B7722) -- sodium vapor, dirty-warm, filtered through grime
- Burnt orange/rusty red (#A0522D to #8B3A3A) -- aged painted surfaces, rusted metal
- Cadmium-adjacent red (#B22222) -- a coat, a sign, real-world saturated not neon
- Rare cool accent: steel blue or teal (#4A6670) -- wet surfaces, certain sky conditions
These accents glow FROM BENEATH the waxy surface, not sitting on top.

### 3. CONSTRUCTIVIST GEOMETRY IN OBSERVED REALITY
Inherited from Rodchenko -- strong geometric armature applied to FOUND scenes:
- Raking diagonal shadows cutting across facades
- Window grids creating Mondrian-like subdivisions
- Doorways and passages forming frames-within-frames
- Multiple depth planes visible through layered openings
The geometry is sharp and precise even in low light -- Savelev was an aerospace engineer.

### 4. PAINTERLY SURFACE QUALITY (BEESWAX/GESSO EFFECT)
The image must NOT look like a standard photograph -- it must look like a physical art object:
- Colors glow from BENEATH a translucent waxy membrane
- Surface has a matte, tactile quality like encaustic painting
- Multiple pigment layers create depth -- tones sit at different physical depths within the surface
- Edges are slightly softened by the medium, not by lens blur
- The overall effect: a hand-made print on gesso-coated aluminum, sealed with beeswax

### 5. POST-SOVIET URBAN TEXTURE
Surfaces showing decades of entropy: peeling paint revealing older colors, cracked plaster, aged wood grain, patinated metal. These surfaces become abstract paintings of accumulated time.

### 6. ANONYMOUS FIGURES IN ARCHITECTURAL SPACE
People appear small and incidental: silhouetted in doorways, crossing courtyards, framed by geometry. Architecture > geometry > light > figure.

### 7. EMOTIONAL REGISTER
Observational, not expressionist. Ghostly, contemplative, structurally precise. Nostalgia for the specific -- this particular crumbling wall, this exact shadow at this hour. The feeling of walking through a city that remembers more than its inhabitants do.

NEVER: bright, cheerful, dramatic, confrontational, documentary, journalistic, digitally clean, or expressionist/moody.

## PROMPT STRUCTURE

```
SCENE ARCHITECTURE: [Geometric and spatial setup -- frames within frames, depth planes, diagonal shadow lines]
LIGHT DIRECTION: [Raking low angle, shadow geometry, warm amber/ochre quality, time of day]
COLOR STRATEGY: [Dark muted base + 1-2 restrained accent colors, specific placement]
SURFACE TREATMENT: [Beeswax/gesso painterly quality -- encaustic depth, matte luminosity]
URBAN TEXTURE: [Weathering, decay, patina -- specific material surfaces]
SHADOW QUALITY: [Rich velvety shadows with retained detail -- NOT crushed blacks]
FIGURE PLACEMENT: [If present -- small, incidental, geometric relationship to architecture]
```

## RULES
- Map any reference to Savelev's visual language -- find geometric structure in any scene
- The image must feel like a physical artifact, not a digital file
- NO generic terms: "moody," "cinematic," "atmospheric" -- use SPECIFIC physical descriptors
- Shadows must contain visible detail and texture -- NEVER flat black
- Output ONLY the structured prompt. No preamble, no explanation.
"""

# ---------------------------------------------------------------------------
# SHARED BUILDING BLOCKS FOR TRANSFORM VARIANTS
# ---------------------------------------------------------------------------

_SHARED_HEADER = """You are transforming a photograph into the visual language of Boris Savelev (b. 1948), the Russian art-photographer who prints pigment-on-gesso with beeswax finish. You will receive an input image. Your task is to REBUILD the image as Savelev would have conceived it -- not apply a dark filter, but generate a new photograph that could exist in his body of work.

## CRITICAL ANTI-PATTERNS -- DO NOT DO THESE

- Do NOT crush the blacks to flat, dead black. This is the SINGLE BIGGEST ERROR. Savelev's entire technical practice -- multi-layer pigment printing on gesso -- exists specifically to RETAIN detail in the deepest shadows. His blacks are VELVETY and contain spatial information. If your shadows are flat black voids with zero detail, you have failed.
- Do NOT just darken an image and call it Savelev. The constructivist geometry, the surface quality, and the spatial layering are equally essential.
- Do NOT make a generic "Eastern European moody" photograph. Savelev is PRECISE and STRUCTURAL, not expressionist. He is closer to architectural photography than fine-art mood photography.
- Do NOT add obvious film grain or scratches. His prints are smooth, matte, and waxy -- not gritty.
- Do NOT over-saturate the color accents. They gain power from contrast with surrounding darkness, not from their own intensity.
- Do NOT use blue-black shadows. His shadows are ALWAYS warm-toned: dark umber, dark olive, warm slate.
- Do NOT make figures the hero. They are small geometric elements within architectural space.
- Do NOT make it look vintage or retro-filtered. His printing is technically state-of-the-art.
"""

_SHARED_GEOMETRY = """
### CONSTRUCTIVIST GEOMETRY (NON-NEGOTIABLE)
This is Savelev's structural DNA, inherited from Rodchenko:
- Find or create strong geometric armature in the scene using architectural lines, shadows, and edges
- Create frames-within-frames using doorways, windows, passages, arches
- Establish 2-3 visible depth planes (foreground structure -> midground space -> background wall/sky)
- Use raking diagonal shadow lines to create dynamic compositional tension
- The geometry must be PRECISE and SHARP even in low light -- engineered, not accidental
"""

_SHARED_SURFACE = """
### BEESWAX-OVER-GESSO SURFACE (THE SIGNATURE)
This separates Savelev from every other dark-palette photographer:
- Colors glow from BENEATH a translucent waxy membrane -- encaustic depth
- The surface reads as MATTE and TACTILE -- like touching gesso-primed aluminum
- Multiple pigment layers create a sense of looking INTO the image, not AT a flat surface
- Fine detail is slightly softened by the medium -- not blurred, but veiled
- No specular gloss, no digital sharpness, no crisp pixel edges
- The overall effect: a hand-made physical print, luminous and quiet
"""

_SHARED_SHADOW = """
### SHADOW QUALITY (CRITICAL -- GET THIS RIGHT)
Savelev's shadows are his most distinctive technical achievement:
- Shadows are WARM-TONED: dark umber (#1A1210), dark olive-brown (#1A1A10), warm slate (#0F1520)
- Shadows contain VISIBLE DETAIL -- textures, spatial depth, subtle color information
- On close inspection, the darkness reveals walls, surfaces, receding spaces
- Think "velvety darkness" not "black void" -- rich, soft, deep, but populated with information
- The relationship between shadow detail and color accents creates spatial depth impossible in flat-black images
- Dynamic range is compressed but NOT clipped -- deep darks and muted highlights, no extremes
"""

_SHARED_FIGURES = """
### FIGURES (IF PRESENT)
- Small relative to architectural space -- 10-20% of frame height
- Positioned within geometric structure: in a doorway, crossing a shadow line, framed by an arch
- Rendered as near-silhouettes or partially shadowed -- no facial detail, no expression
- They provide scale and human presence as geometric elements (dark vertical shapes)
- If the source has a close-up portrait, PULL BACK and place the person within architecture
"""

_SHARED_OUTPUT = """
## OUTPUT
Generate a new photograph that Savelev would have made in this scene. The subject/location from the original should be recognizable, but COMPOSITION, PALETTE, SURFACE QUALITY, and LIGHT should be entirely Savelev's. The result must look like a physical beeswax-over-gesso print -- matte, luminous, with rich shadow detail -- not a digital photograph with a dark filter.
"""

# ---------------------------------------------------------------------------
# VARIANT 1: SECRET CITY (Orwochrome period, 1980s)
# ---------------------------------------------------------------------------
TRANSFORM_SECRET_CITY = _SHARED_HEADER + """
## VARIANT: SECRET CITY -- The Soviet Color

This variant channels Savelev's 1980s work shot on Orwochrome 32, the only color film available in Soviet stores. The East German film stock produced a distinctive shifted color rendering -- a specific "Soviet yellow" that cannot be replicated by any other means. Published as "Secret City" (1988), the first book by an unofficial Soviet photographer published in the West.

### THE ORWOCHROME COLOR CAST
- Dominant hue: Soviet yellow (#C4A235 to #8B7722) -- NOT clean golden, but the specific dirty-warm yellow of sodium vapor streetlights filtered through urban grime and aged window glass
- Overall color rendering is shifted and imperfect -- the film's limited chemistry produces unexpected cross-channel behavior
- Midtone grays are warm concrete: #6B6356, #7A7062 -- the color of Soviet buildings, sidewalks, overcast sky in puddles
- Blacks retain warm brown undertone -- never neutral, never cool

### SUBJECTS: THE QUOTIDIAN SOVIET CITY
- Sidewalks, garage interiors, phone booths, park benches -- the quotidian, not the iconic
- NO onion domes, no obvious Russian landmarks, no snow cliches
- Crumbling infrastructure, graffiti, scratched surfaces, torn posters
- Figures are silhouettes: a woman on a streetcar, an old man at a phone box
- Scattered, seemingly accidental compositions that reveal geometric structure on closer inspection
""" + _SHARED_GEOMETRY + _SHARED_SHADOW + _SHARED_SURFACE + _SHARED_FIGURES + _SHARED_OUTPUT

# ---------------------------------------------------------------------------
# VARIANT 2: KODACHROME DARKNESS (mature color period, 1990s-2000s)
# ---------------------------------------------------------------------------
TRANSFORM_KODACHROME = _SHARED_HEADER + """
## VARIANT: KODACHROME DARKNESS -- The Mature Vision

After discovering Kodachrome, Savelev used it exclusively for all color work. Kodachrome gave him "what a real image should look like" -- deeper blacks with richer color separation, truer reds, more saturated accents. But he deployed this richer palette within his characteristically dark compositions: small bursts of saturated color against overwhelming darkness.

### KODACHROME COLOR RENDERING
- Richer, more saturated color than the Orwochrome period but still dark overall
- Color accents are real-world saturated: a painted wall (#B22222 red), a coat, an illuminated sign
- The accents gain power from CONTRAST with surrounding darkness, not from their own intensity
- Warm earth tones: burnt orange (#A0522D), rusty red (#8B3A3A), aged brick
- Rare cool accents: steel blue (#4A6670) from reflections or wet surfaces
- Kodachrome's grain is extremely fine -- the texture comes from the beeswax surface, not film grain

### LIGHT: RAKING AND GEOMETRIC
- Dawn or dusk light at extreme angles, casting long geometric hard-edged shadows
- Shadows are as important as what casts them -- abstract shapes overlaid on walls and pavements
- Light is warm (amber/ochre) arriving from the side or behind structures
- Creates silhouettes and edge-lit surfaces
- Overall illumination is LOW -- a dim, quiet, structurally precise world
""" + _SHARED_GEOMETRY + _SHARED_SHADOW + _SHARED_SURFACE + _SHARED_FIGURES + _SHARED_OUTPUT

# ---------------------------------------------------------------------------
# VARIANT 3: PIGMENT ON GESSO (contemporary large-format prints, 2006+)
# ---------------------------------------------------------------------------
TRANSFORM_GESSO = _SHARED_HEADER + """
## VARIANT: PIGMENT ON GESSO -- The Physical Print

This variant channels Savelev's definitive printing method developed with Factum Arte (2006-2007): multiple layers of pigment printed at varying opacity onto gesso-coated aluminum, then hand-finished and sealed with beeswax. This is where his obsession with shadow detail reaches its fullest expression -- an extended tonal range far beyond standard printing.

### THE MULTI-LAYER PIGMENT TECHNIQUE (simulate visually)
- Image built through multiple overprinting passes -- tones appear to sit at DIFFERENT PHYSICAL DEPTHS
- Velvety blacks that reveal a wealth of detail on close inspection -- the deepest shadows still contain spatial information
- Colorful saturation amplified by the aluminum substrate in ways paper cannot achieve
- The gesso absorbs pigment like canvas absorbs oil paint -- closer to painting than photography
- The beeswax finish creates subtle warmth and protective membrane quality -- images GLOW rather than reflect

### MAXIMUM TONAL DEPTH
- This is the fullest expression of Savelev's shadow-detail obsession
- Even the darkest 5% of the image should contain discernible texture and spatial cues
- The extended range means you can see INTO the shadows, discovering receding walls, doorways, surfaces
- Highlights are restrained: cream, pale ochre, warm ivory -- never bright white
- The overall impression: looking through a luminous membrane into a deep, warm, detailed darkness

### CONTEMPORARY SUBJECTS
- Incorporates both re-printed older negatives and new digital captures
- Includes work from Vigo, Spain (his home since 2022) alongside Russian material
- Large-format presentation (120 x 80 cm equivalent) -- monumental scale
""" + _SHARED_GEOMETRY + _SHARED_SHADOW + _SHARED_SURFACE + _SHARED_FIGURES + _SHARED_OUTPUT

# ---------------------------------------------------------------------------
# VARIANT 4: GEOMETRIC SHADOW (emphasis on constructivist composition)
# ---------------------------------------------------------------------------
TRANSFORM_GEOMETRIC = _SHARED_HEADER + """
## VARIANT: GEOMETRIC SHADOW -- The Engineer's Eye

This variant emphasizes Savelev's Constructivist inheritance and his background as an aerospace engineer. The geometric armature IS the subject -- shadows, lines, and architectural divisions create abstract compositions from observed reality. Less about color accents, more about the structural skeleton of the image.

### GEOMETRY AS SUBJECT
- Raking diagonal shadows cutting across facades are the PRIMARY compositional element
- Window grids, doorways, railings, and staircases create Mondrian-like subdivisions
- Multiple depth planes layered through openings: a doorway reveals a courtyard reveals a wall reveals sky
- The precision feels engineered -- every angle, every proportion deliberate
- The geometry is FOUND, not imposed -- Savelev notices the Rodchenko hiding in the architecture

### SHADOW AS COMPOSITIONAL FORCE
- Long geometric shadows from low-angle light create abstract overlays on architectural surfaces
- The shadow pattern subdivides walls and ground planes into geometric zones
- Hard-edged shadow lines create tension with the organic textures beneath (peeling paint, cracked plaster)
- Shadow shapes are as carefully composed as the lit elements -- they are positive compositional forces, not mere absence of light

### MINIMAL COLOR
- Color is severely restricted in this variant -- near-monochrome in warm earth tones
- At most ONE subtle color accent to punctuate the geometric composition
- The emphasis is on tonal structure: warm darks, muted midtones, restrained highlights
- The image reads almost as a warm-toned B&W with the faintest color presence
""" + _SHARED_SHADOW + _SHARED_SURFACE + _SHARED_FIGURES + _SHARED_OUTPUT

# ---------------------------------------------------------------------------
# VARIANT REGISTRY
# ---------------------------------------------------------------------------
TRANSFORM_VARIANTS = {
    "Secret City -- Soviet Orwochrome color": TRANSFORM_SECRET_CITY,
    "Kodachrome Darkness -- mature color": TRANSFORM_KODACHROME,
    "Pigment on Gesso -- physical print": TRANSFORM_GESSO,
    "Geometric Shadow -- constructivist": TRANSFORM_GEOMETRIC,
}
VARIANT_LIST = list(TRANSFORM_VARIANTS.keys())

# Legacy fallback
TRANSFORM_SYSTEM = TRANSFORM_KODACHROME

# ---------------------------------------------------------------------------
# INTENSITY MODIFIERS
# ---------------------------------------------------------------------------
INTENSITY_MODIFIERS = {
    "subtle": """Apply Savelev's visual language with restraint. Shift the palette toward dark warm earth tones. Add slight matte surface softening suggesting the beeswax membrane. Darken shadows but RETAIN their detail -- they should be rich and velvety, not flat. Keep 1-2 muted color accents. Enhance existing geometric structure without full recomposition. This is a whisper of Savelev -- the warmth, the shadow richness, and the surface quality shift without dramatic transformation.""",

    "moderate": """Apply Savelev's visual language clearly. Darken the overall tonality significantly toward his characteristic dark key. Shift fully to warm earth-tone palette. Apply noticeable beeswax/gesso surface quality -- matte luminosity, colors glowing from within. Shadows are warm and detailed, not crushed. Emphasize constructivist geometry in the composition. Reduce figures in prominence. The original scene is recognizable but clearly transformed into Savelev's visual world.""",

    "full": """Apply the complete Savelev visual language -- dark warm tonality with rich velvety shadow detail, strong constructivist geometry, raking light with geometric shadows, beeswax-over-gesso surface (matte, luminous, encaustic depth), restrained color accents glowing from beneath the waxy membrane. Figures small and incidental. Urban textures emphasized. Shadows must contain visible spatial information. This is the default and most authentic mode.""",

    "extreme": """Push into Savelev's most painterly territory. The image approaches pure physical artifact -- the beeswax surface is so present that the photograph borders on encaustic painting. Nearly all information lives in warm darkness with only traces of form and color emerging from the depths. Geometry becomes the ghost of architecture -- shadow lines and structural edges floating in rich, detailed darkness. Color accents are barely perceptible whispers. The image feels excavated from deep time -- more physical object than photograph. Even at this extreme, shadows retain subtle internal detail -- they are deep, not dead."""
}
