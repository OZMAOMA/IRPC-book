# Choosing a format and its rules

Choose the format before you model anything. Each format limits what you can
build. To change format later, use *File → Convert Project*, which can drop
features the new format lacks.

| Format (`model_format`) | Use for | UV | Bones animate? | Meshes | Key limits |
|---|---|---|---|---|---|
| **Java Block/Item** (`java_block`) | Vanilla resource-pack blocks & items | per-face | no (groups are folders only) | no | coords −16…32; rotation on **one axis**, angle ∈ {−45, −22.5, 0, 22.5, 45}; no group rotation; textures referenced as `#0`…; `display` transforms |
| **Bedrock Entity** (`bedrock`) | Bedrock add-on mobs, attachables | box (or per-face) | yes | no | every cube inside a bone; unique bone names; `model_identifier` → `geometry.<id>`; locators; Molang animations & controllers |
| **Bedrock Block** (`bedrock_block`) | Custom Bedrock blocks (`minecraft:geometry`) | per-face | — | no | must fit **30×30×30 px** around the block centre; unique bone names |
| **Bedrock Entity legacy** (`bedrock_old`) | Format 1.10 geometry | box | yes | no | old format; use only when the target needs it |
| **Modded Entity** (`modded_entity`) | Forge/Fabric Java code (MCP / Mojmaps / Yarn templates) | box | yes (export as code) | no | cubes inside bones; integer box UV; exports a `.java` class |
| **OptiFine Entity** (`optifine_entity`) | CEM replacements (`.jem`) | box | via `.jem` animations | no | bone names must match the vanilla part names (`head`, `body`, …) |
| **OptiFine Part** (`optifine_part`) | `.jpm` part files | box | — | no | one part per file |
| **Minecraft Skin** (`skin`) | Player skins (64×64) | box | pose only | no | fixed skeleton; you edit the texture, not the geometry |
| **Generic Model** (`free`) | Anything else: games, renders, Sketchfab, glTF/OBJ/FBX | per-face | yes | **yes** | no Minecraft limits; full mesh tools |
| Plugin formats (e.g. **GeckoLib Animated Model**) | Java mods using GeckoLib | box/per-face | yes | no | install the plugin from *File → Plugins*; export model, animation and display JSON separately |

## Java Block/Item checklist
* `parent`: `"block/block"` for full-block-ish models (it inherits display
  transforms), `"item/generated"` for flat items (that case needs no elements,
  just `layer0` textures), or nothing for a fully custom model.
* Hide a face by giving it `texture: null`. Faces flush with the block boundary
  should get a `cullface` so they don't render when a neighbour block covers them.
* `tint: 0` applies the biome colour (grass/leaves).
* Set the particle texture (`particle: true` on one texture).
* Transparency: the block's render type comes from the mod or game, not the model.
* For a rotation beyond 45°, split the part or rotate the whole model with blockstates
  (`x`/`y` in multiples of 90).
* Turn on `ambientocclusion: false` for small or detailed props to avoid dark edges.

## Bedrock Entity checklist
* Name the root bone `root` or `body` and pivot it at `[0, 0, 0]`.
* Use vanilla bone names (`head`, `body`, `leftArm`, `rightLeg`, …) when you
  want vanilla animations or render controllers to drive them.
* Put every pivot exactly where the joint is: the shoulder for arms, the neck for the head.
* `visible_box` must enclose the model or it will flicker out of view.
* Animations are exported to `animations/<name>.animation.json`. Names must
  start with `animation.`.
* Attachables and held items: add a `rightitem` locator, or use `bedrock_binding`.

## Texture-size rules of thumb
* Java block: 16×16 per face, so one 16×16 texture is common. Keep pixel density
  uniform: 1 texel = 1 model px.
* Bedrock mob: 64×64 or 128×128 atlas with box UV.
* Keep **texel density consistent** across parts. Scaled-up cubes with
  stretched UVs look wrong in Minecraft style.
