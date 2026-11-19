# Blockbench feature map

This file covers everything Blockbench can do and how to reach each feature. For
each feature it says whether to produce it in the `.bbmodel` or tell the user
which tool to click. Menu names follow Blockbench 4.x/5.x and may move slightly
between versions.

## Modes (top-right tabs)
| Mode | What happens there |
|---|---|
| **Edit** | Geometry: cubes, meshes, groups, pivots, UV |
| **Paint** | Texture painting directly on the model or the 2D UV editor |
| **Display** | Java item transforms (hand, GUI, ground, head, frame); reference player/armor stand |
| **Animate** | Keyframe animation, graph editor, Molang, effects, IK |

## Edit mode tools
* **Add:** Cube (Ctrl+N), Group (Ctrl+G), Mesh primitives (cube, cylinder,
  sphere, torus, cone, tube, pyramid, plane, circle), Locator, Null Object,
  Texture Mesh, Bounding Box (Java 1.21+ collision helper in some versions).
* **Transform:** Move (V), Resize (S), Rotate (R), Pivot tool (P), Vertex Snap
  (X). Hold Shift/Ctrl for fine or 1/4 steps. The *Transform* panel takes exact numbers.
* **Mirror modeling** (toolbar toggle): edits on one side are mirrored across X=0.
  In the JSON build this is `Model.mirror()`.
* **Inflate:** grows a cube without changing its UV. Use it for outer layers like
  hats, jackets and overlays (`inflate: 0.25 / 0.5`).
* **Mesh tools:** Extrude (E), Inset, Loop Cut, Knife, Merge Vertices, Split,
  Bevel, Subdivide, Invert Faces, Solidify, Dissolve edges, Create face from
  selected vertices (F), Proportional editing, Seam / Auto UV by seams.
* **Edit → Convert to Mesh**, **Center Model**, **Flip** on X/Y/Z,
  **Scale** (with pivot / overflow handling), **Rotate model** 90°.
* **Outliner:** drag to re-parent, lock, hide, toggle export, set colour marker,
  rename (F2), **Sort**, **Auto-name** duplicates, select children.
* **Views:** Numpad views, Quad view, Wireframe, **Reference images**
  (*View → Reference Images*, which lets you load concept art per view),
  Shading toggle, Painting grid, **Onion skin** in Animate.

## UV editing
* Per-face UV editor: drag, scale, rotate 90°, mirror X/Y, **Auto UV**
  (fit to face size), **Maximize**, **Snap to pixel grid**.
* Box UV: set `uv_offset`. *Edit → Optimize UV / Pack UV* lays the strips out
  automatically.
* **Create Texture** (*Textures panel → Create Texture*) with *Template*
  enabled generates an atlas plus a UV layout for every element. This is the fastest
  way to texture a finished model. It has options for resolution, box/per-face,
  "Compress", "Power of 2", and fill colour or "Template" outlines.
* **Face properties:** texture slot, `cullface`, `tint`, rotation, enabled.

## Paint mode
* Tools: Brush (B), Eraser (E), Fill (bucket with face/element/connected modes),
  Color Picker (C), Line, Shape (rect/ellipse), Gradient, Copy brush/Clone
  stamp, Selection (M), Move layer.
* Brush options: size, softness, opacity, **shape** (square/circle), **blend
  modes**, **noise / dithering**, pixel perfect lines, **mirror painting**
  (X), **lock alpha**, paint on 3D model vs 2D editor.
* **Layers** on textures (enable *Layers*), adjustments: Brightness/Contrast,
  Hue/Saturation, Invert, Grayscale, Adjust Curves, **Color palette**
  (load/save `.gpl`, generate from image), **Resize/Crop texture**, Animated
  textures (frames, `frame_time`), Emissive/additive/layered render modes.
* Edit textures in external editors (*Open in default editor*). Changes reload live.

## Display mode (Java)
* Slots: Third-person R/L, First-person R/L, Head, GUI, Ground, Item Frame.
* Presets (block, item, tool, handheld rod), copy slot to the opposite hand,
  reference models (player, zombie, armor stand, baby). In JSON this is `Model.set_display()`.

## Animate mode
* Animations panel: create, rename, loop mode (once/hold/loop), length,
  override, snapping (fps), **anim_time_update**, **blend_weight**, start/loop
  delay (Molang).
* Timeline: keyframes per bone channel (rotation/position/scale), copy/paste,
  **mirror keyframes**, **bake** (resample), **flip animation**, reverse,
  interpolation (linear/catmullrom/step/bezier), **Graph editor** with bezier
  handles.
* **Molang** in any data point (`math.sin(q.anim_time*360)*10`) plus a variable
  placeholder panel to preview variables.
* **Effects track:** sounds, particles on locators, timeline Molang scripts.
* **Animation controllers** (Bedrock): states, transitions, blend.
* **Inverse Kinematics:** null object with `ik_target` drives a bone chain.
* Animate **textures** (UV/flipbook) and **Onion skin**.
* Export: Bedrock `.animation.json`, GeckoLib (plugin), glTF/FBX with animations,
  **Render GIF/PNG sequence/Video** (*Animation → Export as GIF*), **Screenshot**
  (Ctrl+P), 360° turntable recording.

## File menu essentials
* **New** (choose format), **Open**, **Save project** (`.bbmodel`), **Import**
  (Java JSON, Bedrock geometry, OBJ, glTF on newer versions, image → *Extrude
  Image* to make a 3D item from a sprite), **Export** (per format: Java JSON,
  Bedrock geometry, OptiFine JEM/JPM, Modded Entity `.java`, OBJ + MTL, glTF /
  GLB, FBX, Collada (DAE), STL (plugin), Image/Spritesheet), **Convert
  Project**, **Plugins** (install from store: e.g. Asset Browser, GeckoLib,
  Mod Utils, Shape Generator, Mesh Tools, Voxel Shape generator, Animation
  utilities), **Preferences / Settings** (snapping, grid size, units), **Sketchfab
  upload**, **Share** (blockbench.net temporary link).

## Translating requests to tools
| User wants… | Do in JSON | Or tell them |
|---|---|---|
| Symmetric creature | `Model.mirror()` | Toggle Mirror Modeling |
| Round shapes in a Minecraft style | stack stepped cubes (a "staircase circle") | `free` → Mesh cylinder |
| Hat / overlay layer | duplicate the cube with `inflate=0.5`, box UV shifted | Inflate slider |
| Texture from a finished model | write per-face UVs and a procedural PNG | Create Texture → Template |
| 3D item from a sprite | — | File → Import → Extrude Image |
| Walk cycle | `Animation.keyframe` on legs/arms, half-length phase offset | Animate mode |
| Glowing parts | separate emissive texture (`render_mode: emissive`) | Texture → Render Mode |
| Put model in Minecraft | `java_block` / `bedrock` + export steps | File → Export |
