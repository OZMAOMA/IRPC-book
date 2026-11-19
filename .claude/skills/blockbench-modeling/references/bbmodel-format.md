# The `.bbmodel` file format

A `.bbmodel` is plain JSON (Blockbench writes it tab-indented). Blockbench opens
older `format_version`s and upgrades them, so writing `"4.10"` with groups
inline in the outliner is the safest choice: every Blockbench 4.x and 5.x
build opens it. (Blockbench 5 saves groups in a separate top-level `"groups"`
array and puts only uuids in the outliner. Read both forms; write the inline form.)
Groups that have a `name` inside the outliner load as "legacy groups" in every
version. This was checked against the Blockbench 5.2 source (`js/formats/bbmodel.js`).

> **Animation sign convention.** In files with `format_version` < 5.0, keyframe
> values are stored exactly like Bedrock `.animation.json` files. When
> Blockbench 5 loads such a file, it negates rotation X, rotation Y and
> position X for its internal convention. So: **write keyframes in Bedrock
> convention with `format_version: "4.10"`**. Don't write 5.0 unless you
> also negate those three components yourself.

Units: **1 block = 16 px**. All coordinates are in pixels. In Java/Bedrock
block formats, the block occupies `0..16` on each axis. In entity formats, the
model is centred on x/z = 0 with the feet at y = 0. **North = -Z** is the
"front" of entities.

## Top level

```jsonc
{
  "meta": { "format_version": "4.10", "model_format": "bedrock", "box_uv": true },
  "name": "robot",                      // project name
  "model_identifier": "robot",          // bedrock geometry id -> geometry.robot
  "visible_box": [1, 1, 0],             // bedrock culling box [width, height, y]
  "variable_placeholders": "",          // molang preview vars, e.g. "v.speed = 1"
  "variable_placeholder_buttons": [],
  "timeline_setups": [],
  "unhandled_root_fields": {},
  "resolution": { "width": 64, "height": 64 },   // UV space size
  "elements": [ ... ],                  // flat list of cubes/meshes/locators/...
  "outliner": [ ... ],                  // hierarchy: group objects + element uuids
  "textures": [ ... ],
  "animations": [ ... ],                // optional
  "animation_controllers": [ ... ],     // optional (bedrock)
  "display": { ... },                   // optional, Java item transforms
  "parent": "block/block",              // optional, Java Block only
  "ambientocclusion": true,             // optional, Java Block only
  "front_gui_light": false              // optional, Java Block only
}
```

`model_format` ids: `free` (Generic Model), `java_block`, `bedrock`,
`bedrock_block`, `bedrock_old`, `modded_entity`, `optifine_entity`,
`optifine_part`, `skin`. Plugins add more, for example GeckoLib's
`animated_entity_model`. If you don't know a plugin format's id, write the file as
`free` and have the user convert it with *File → Convert Project*.

## Elements

### Cube
```jsonc
{
  "type": "cube", "uuid": "…", "name": "torso",
  "from": [-4, 12, -2], "to": [4, 24, 2],     // min / max corner (px)
  "origin": [0, 12, 0],                        // pivot for rotation
  "rotation": [0, 0, 0],                       // degrees X, Y, Z
  "inflate": 0,                                // grows the cube without changing UV
  "box_uv": false,                             // true -> uv_offset drives all faces
  "uv_offset": [16, 16],                       // only meaningful with box_uv
  "mirror_uv": false,
  "shade": true,                               // Java: false = no directional shading
  "light_emission": 0,                         // Java 1.21.2+ per-element light 0-15
  "color": 0,                                  // outliner marker colour 0-7
  "autouv": 0,                                 // 0 off, 1 auto, 2 relative auto
  "faces": {
    "north": { "uv": [0, 0, 8, 12], "texture": 0, "rotation": 0,
               "cullface": "north", "tint": -1 },
    "east": {…}, "south": {…}, "west": {…}, "up": {…}, "down": {…}
  }
}
```
* `uv` is `[x1, y1, x2, y2]` in `resolution` space. If x2 < x1, the face is mirrored.
* `texture` is the index into `textures`, or `null` to leave the face blank (Java: hides the face).
* Face `rotation` is 0, 90, 180 or 270. `cullface` and `tint` only matter for Java.
* Omitting `rotation` means `[0, 0, 0]`.

### Box-UV layout (cube size w×h×d at `uv_offset` u,v)
```
            u+d      u+d+w    u+d+2w
   v     ┌────────┬────────┐
         │   up   │  down  │          (d tall)
 v+d ┌───┼────────┼────┬───┴────┐
     │ E │ north  │ W  │ south  │     (h tall)
     └───┴────────┴────┴────────┘
     u   u+d             u+2d+w
```
The strip takes `2(w+d)` × `(d+h)` px. Plan the texture atlas so the strips don't overlap.

### Mesh (Generic Model only)
```jsonc
{
  "type": "mesh", "uuid": "…", "name": "gem",
  "origin": [0, 0, 0], "rotation": [0, 0, 0],
  "vertices": { "a1": [0, 0, 0], "b2": [4, 0, 0], "c3": [2, 6, 0] },
  "faces": {
    "f1": { "vertices": ["a1", "b2", "c3"],
            "uv": { "a1": [0, 16], "b2": [16, 16], "c3": [8, 0] },
            "texture": 0 }
  }
}
```
Vertex positions are relative to `origin`. Faces have 3 or 4 vertices. Wind
them counter-clockwise as seen from outside so the normals point outward.

### Locator / Null object / Texture mesh
```jsonc
{ "type": "locator", "name": "right_hand", "position": [-6, 12, 0], "rotation": [0,0,0], "uuid": "…" }
{ "type": "null_object", "name": "leg_ik", "position": [2, 0, 0], "ik_target": "<group uuid>", "uuid": "…" }
{ "type": "texture_mesh", "name": "leaf", "texture_name": "leaf.png", "local_pivot": [0,0,0], "origin": [0,0,0], "rotation": [0,0,0], "scale": [1,1,1], "uuid": "…" }
```
In Bedrock you use locators for held items, particles and leashes. Null objects drive IK
chains in the animator.

## Outliner (hierarchy)

```jsonc
"outliner": [
  { "name": "body", "uuid": "…", "origin": [0, 12, 0], "rotation": [0, 0, 0],
    "color": 0, "export": true, "mirror_uv": false, "isOpen": true,
    "locked": false, "visibility": true, "autouv": 0,
    "bedrock_binding": "",                 // molang, e.g. attachable binding
    "children": [ "<cube uuid>", { …nested group… } ] },
  "<loose element uuid>"
]
```
Every element must be referenced exactly once. Groups are the **bones**:
their `origin` is the pivot that animations rotate around.

## Textures

```jsonc
{
  "name": "robot.png", "id": "0", "uuid": "…",
  "width": 64, "height": 64, "uv_width": 64, "uv_height": 64,
  "path": "", "folder": "block", "namespace": "",
  "particle": false,              // Java: particle texture
  "render_mode": "default",       // default | emissive | additive | layered
  "render_sides": "auto",         // auto | front | double
  "frame_time": 1, "frame_order_type": "loop", "frame_interpolate": false,
  "internal": true, "saved": false,
  "source": "data:image/png;base64,iVBOR…"     // embedded PNG
}
```
An animated texture is a vertical strip of frames (height = n × width).
`frame_time` is in game ticks.

## Animations

```jsonc
{
  "uuid": "…", "name": "animation.robot.walk",
  "loop": "loop",                 // once | hold | loop
  "override": false, "length": 1.0, "snapping": 24,
  "anim_time_update": "", "blend_weight": "", "start_delay": "", "loop_delay": "",
  "animators": {
    "<group uuid>": {
      "name": "left_leg", "type": "bone",
      "keyframes": [
        { "channel": "rotation", "time": 0, "interpolation": "linear",
          "data_points": [ { "x": 30, "y": 0, "z": 0 } ], "uuid": "…", "color": -1 },
        { "channel": "rotation", "time": 0.5, "interpolation": "catmullrom",
          "data_points": [ { "x": "math.sin(q.anim_time * 720) * 30", "y": 0, "z": 0 } ],
          "uuid": "…", "color": -1 }
      ]
    },
    "effects": { "name": "Effects", "type": "effect", "keyframes": [
      { "channel": "sound", "time": 0.25, "data_points": [ { "effect": "mob.zombie.step", "file": "" } ] },
      { "channel": "particle", "time": 0, "data_points": [ { "effect": "minecraft:basic_flame_particle", "locator": "head", "script": "" } ] },
      { "channel": "timeline", "time": 0, "data_points": [ { "script": "v.attack = 1;" } ] }
    ] }
  }
}
```
* Channels: `rotation` (degrees), `position` (px), `scale` (multiplier).
* `interpolation`: `linear`, `catmullrom` (smooth), `step`, `bezier`. Bezier
  also needs `bezier_linked`, `bezier_left_time`, `bezier_left_value`,
  `bezier_right_time` and `bezier_right_value`, each 3-arrays.
* A data point can be a number or a **Molang** string.
* `step` keyframes can carry two data points: pre and post.

## Display (Java Block/Item)

```jsonc
"display": {
  "thirdperson_righthand": { "rotation": [75, 45, 0], "translation": [0, 2.5, 0], "scale": [0.375, 0.375, 0.375] },
  "firstperson_righthand": { "rotation": [0, 45, 0], "translation": [0, 0, 0], "scale": [0.4, 0.4, 0.4] },
  "gui":    { "rotation": [30, 225, 0], "translation": [0, 0, 0], "scale": [0.625, 0.625, 0.625] },
  "ground": { "rotation": [0, 0, 0], "translation": [0, 3, 0], "scale": [0.25, 0.25, 0.25] },
  "fixed":  { "rotation": [0, 0, 0], "translation": [0, 0, 0], "scale": [0.5, 0.5, 0.5] },
  "head":   { "rotation": [0, 0, 0], "translation": [0, 0, 0], "scale": [1, 1, 1] }
}
```
The values above match vanilla `block/block`. The slots are `thirdperson_righthand/lefthand`,
`firstperson_righthand/lefthand`, `gui`, `head`, `ground` and `fixed` (item frame).
Translation is clamped to ±80 and scale to ≤4.
