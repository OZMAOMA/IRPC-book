---
name: blockbench-modeling
description: Build, edit, texture and animate 3D models for Blockbench - writes ready-to-open .bbmodel files (cubes, groups/bones, meshes, locators, IK null objects, embedded PNG textures, keyframe and Molang animations, Java display transforms) for every Blockbench format (Java Block/Item, Bedrock Entity/Block, Modded Entity, OptiFine, Skin, Generic/glTF), plus Blockbench JavaScript plugins/console scripts and click-by-click guidance for any Blockbench tool. Use whenever the user mentions Blockbench, .bbmodel, Minecraft models/mobs/items/blocks, low-poly or voxel-style models, GeckoLib, or asks to ปั้นโมเดล / สร้างโมเดล / ทำแอนิเมชัน in Blockbench.
---

# Blockbench Modeling

You make models the user can open directly in Blockbench (desktop app or
web.blockbench.net). You can't click inside Blockbench from here, so you have three
ways to deliver:

1. **Generate a `.bbmodel`** with `scripts/bbmodel.py`. This is the main path for new models.
2. **Write a Blockbench script or plugin** (JS) for edits to a model already
   open in Blockbench, or for things that need Blockbench itself (its exporters,
   UV packing, batch edits). See `references/scripting-api.md`.
3. **Tell the user which tool to use** when a hands-on tool fits better
   (painting details, sculpting meshes, Display tweaking). See
   `references/blockbench-features.md`.

Most good answers combine them: a generated file plus short steps for finishing touches.

## Workflow

### 1. Pin down the target (ask only if unclear)
* **Format.** Where will it be used? Pick from `references/formats.md`.
  Defaults: Minecraft Java resource pack → `java_block`; Bedrock add-on mob →
  `bedrock`; a mod with animations → `bedrock`-style bones (or the GeckoLib plugin
  format); anything else, a game engine, or a render → `free`.
* **Scale & style.** 16 px = 1 block. A Minecraft-style mob is about 32 px tall
  (zombie) or 16 px (pig). Note the texture resolution (16×16, 64×64 …).
* **Parts that move.** These become bones (groups) with pivots at the joints.

### 2. Plan before writing code
Write a short part list: for each part give name, parent bone, `from`/`to` (px), pivot,
and UV offset. Sketch the silhouette in your head from the front (−Z) and side.
Rules that make models look right:
* Use whole pixels. Use half pixels only for tiny details. Avoid odd scales.
* Put pivots on the joints: shoulders, hips, neck. The root bone pivots at `[0,0,0]`.
* Model one side, then use `Model.mirror()` for the other.
* Get round shapes in a Minecraft style by stacking stepped cubes. Use real meshes
  only in `free`.
* Use `inflate` for outer layers (hair, armour, clothing) instead of
  overlapping cubes of the same size, which cause z-fighting.
* Respect the format limits (Java: one rotation axis, ±22.5/45°, −16…32 range).
* Keep texel density uniform. Plan box-UV strips so they don't overlap
  (each takes `2(w+d) × (d+h)`).

### 3. Build with the helper
```python
import sys; sys.path.insert(0, ".claude/skills/blockbench-modeling/scripts")
from bbmodel import Model, Texture, Mesh

m = Model("penguin", fmt="bedrock", texture_size=(64, 64))
tex = m.add_texture(Texture.blank("penguin", 64, 64))
tex.noise_rect(0, 0, 64, 64, "#222831", amount=10)     # base colour with pixel noise
tex.fill_rect(0, 16, 32, 16, "#eeeeee")                   # belly area on the atlas

root = m.group("root", origin=(0, 0, 0))
body = m.group("body", origin=(0, 2, 0), parent=root)
m.cube("body", (-4, 2, -3), (4, 12, 3), parent=body, uv_offset=(0, 16))
head = m.group("head", origin=(0, 12, 0), parent=body)
m.cube("head", (-3, 12, -3), (3, 17, 3), parent=head, uv_offset=(0, 0))
m.cube("beak", (-1, 13, -5), (1, 14, -3), parent=head, uv_offset=(24, 0))
m.locator("head_locator", (0, 17, 0), parent=head)
leg_l = m.group("leg_left", origin=(2, 2, 0), parent=root)
m.cube("leg_left", (1, 0, -2), (3, 2, 1), parent=leg_l, uv_offset=(28, 16))
m.mirror(leg_l, axis="x")                                  # creates leg_right

walk = m.animation("animation.penguin.walk", length=1, loop="loop")
for t, a in [(0, 15), (0.5, -15), (1, 15)]:
    walk.keyframe(leg_l, "rotation", t, (a, 0, 0), interpolation="catmullrom")
walk.keyframe(body, "rotation", 0, (0, 0, "math.sin(q.anim_time*360)*5"))

print(m.save("penguin.bbmodel"))     # validates; raises on errors, returns warnings
```
Full API: read `scripts/bbmodel.py`. It supports `Cube` (box or per-face UV,
`faces=` overrides with `texture`/`uv`/`rotation`/`cullface`/`tint`), `Mesh`
(vertices/faces, `Mesh.cylinder`), `Locator`, `NullObject`, nested groups,
multiple textures (`Texture.blank`, `Texture.from_png`, pixel painting),
`Animation.keyframe` (numbers or Molang, linear/catmullrom/step/bezier),
`Animation.effect` (sound/particle/timeline), `Model.set_display` and
`Model.extra` for format fields such as `parent` or `ambientocclusion`.

Keyframe values use the **Bedrock `.animation.json` convention** (the same
numbers you'd write in an `.animation.json`). Files are saved as format 4.10,
which Blockbench 4 and 5 both open; Blockbench 5's UI shows rotation X/Y and
position X with flipped signs. That's expected.

If you need a field the helper doesn't expose, edit `m.to_json()` output or
build the dict by hand following `references/bbmodel-format.md`.

### 4. Validate and inspect
```bash
python3 .claude/skills/blockbench-modeling/scripts/bbmodel.py validate out.bbmodel
python3 .claude/skills/blockbench-modeling/scripts/bbmodel.py info out.bbmodel
python3 .claude/skills/blockbench-modeling/scripts/bbmodel.py extract-textures out.bbmodel tex/
python3 .claude/skills/blockbench-modeling/scripts/bbmodel.py preview out.bbmodel preview.png
```
Fix every `ERROR`. Read the `WARN`s and fix them unless they're intentional. Then
**look at `preview.png`** (Read it: front | side | top silhouettes, one colour
per element) and fix proportions, floating parts or gaps before you hand the file over.

### 5. Deliver
* Put the `.bbmodel` (and PNGs if separate) where the user can open them, and
  send the file.
* Tell them how to open it: **File → Open Model** (or drag into Blockbench), and
  how to export it for the target. For example:
  Java: *File → Export → Export Block/Item Model* into
  `assets/<ns>/models/block/`. Bedrock: *Export Bedrock Geometry* into
  `models/entity/` plus *Animation → Export Animations* into `animations/`.
  Engines: *Export glTF/OBJ/FBX*.
* List the finishing touches that are better done by hand, naming the tools (Paint mode
  brush, *Create Texture → Template*, Display presets, Graph editor).

## Editing an existing model
1. Run `bbmodel.py info file.bbmodel` to see the tree, then read the JSON.
2. Change the JSON with Python: load it, modify elements or outliner, keep uuids
   stable, and add new uuids for new things. Then run `validate`.
3. If the user is working live in Blockbench, give a console script instead
   (wrapped in `Undo.initEdit/finishEdit`) so they can paste it and undo it.

## Reference files
* `references/bbmodel-format.md`: every JSON field (elements, outliner,
  textures, animations, display, box-UV layout).
* `references/formats.md`: format comparison and per-format rules and checklists.
* `references/blockbench-features.md`: every Blockbench mode, tool and menu,
  and which ones to use for which request.
* `references/scripting-api.md`: the JS API for console scripts and plugins.
