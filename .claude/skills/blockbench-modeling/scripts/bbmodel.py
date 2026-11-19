#!/usr/bin/env python3
"""
bbmodel.py - build, validate and inspect Blockbench .bbmodel files with no
third-party dependencies (Python 3.8+ standard library only).

Use as a library:

    import sys; sys.path.insert(0, ".claude/skills/blockbench-modeling/scripts")
    from bbmodel import Model, Texture

    m = Model("robot", fmt="bedrock", texture_size=(64, 64))
    tex = m.add_texture(Texture.blank("robot", 64, 64))
    tex.fill_rect(0, 0, 64, 64, "#8a8f99")
    body = m.group("body", origin=(0, 12, 0))
    m.cube("torso", (-4, 12, -2), (4, 24, 2), parent=body, uv_offset=(16, 16))
    anim = m.animation("animation.robot.idle", length=2, loop="loop")
    anim.keyframe(body, "rotation", 0, (0, 0, 0))
    anim.keyframe(body, "rotation", 1, (0, 5, 0), interpolation="catmullrom")
    anim.keyframe(body, "rotation", 2, (0, 0, 0))
    m.save("robot.bbmodel")      # validates first, raises on errors

Or from the command line:

    python3 bbmodel.py validate model.bbmodel [--format java_block]
    python3 bbmodel.py info model.bbmodel
    python3 bbmodel.py extract-textures model.bbmodel outdir/
    python3 bbmodel.py preview model.bbmodel preview.png   # front/side/top silhouettes

Files are written as format_version 4.10 (opens in Blockbench 4.x and 5.x).
Keyframe values therefore use the Bedrock .animation.json convention;
Blockbench 5 converts on load (its UI shows rotation X/Y and position X with
the opposite sign).
"""
from __future__ import annotations

import base64
import json
import math
import os
import struct
import sys
import uuid as _uuid
import zlib
from typing import Dict, Iterable, List, Optional, Sequence, Tuple, Union

FORMAT_VERSION = "4.10"
FACES = ("north", "east", "south", "west", "up", "down")

# model_format ids used inside meta.model_format
FORMATS = {
    "free": "Generic Model",
    "java_block": "Java Block/Item",
    "bedrock": "Bedrock Entity",
    "bedrock_block": "Bedrock Block",
    "bedrock_old": "Bedrock Entity (legacy 1.10)",
    "modded_entity": "Modded Entity (Java code export)",
    "optifine_entity": "OptiFine Entity (.jem)",
    "optifine_part": "OptiFine Part (.jpm)",
    "skin": "Minecraft Skin",
}
BOX_UV_DEFAULT = {"bedrock", "bedrock_old", "modded_entity", "optifine_entity",
                  "optifine_part", "skin"}
MESH_FORMATS = {"free"}
JAVA_ANGLES = (-45, -22.5, 0, 22.5, 45)
JAVA_DISPLAY_SLOTS = ("thirdperson_righthand", "thirdperson_lefthand",
                      "firstperson_righthand", "firstperson_lefthand",
                      "ground", "gui", "head", "fixed")

Vec3 = Tuple[float, float, float]


def new_uuid() -> str:
    return str(_uuid.uuid4())


def _num(v):
    """Keep JSON tidy: 2.0 -> 2, round float noise."""
    if isinstance(v, float):
        v = round(v, 6)
        if v.is_integer():
            return int(v)
    return v


def _vec(v) -> list:
    return [_num(float(x)) for x in v]


# --------------------------------------------------------------------------
# PNG texture (pure python)
# --------------------------------------------------------------------------
def _parse_color(c) -> Tuple[int, int, int, int]:
    if isinstance(c, (tuple, list)):
        r, g, b = c[:3]
        a = c[3] if len(c) > 3 else 255
        return int(r), int(g), int(b), int(a)
    s = c.lstrip("#")
    if len(s) in (3, 4):
        s = "".join(ch * 2 for ch in s)
    if len(s) == 6:
        s += "ff"
    if len(s) != 8:
        raise ValueError(f"bad colour {c!r}")
    return tuple(int(s[i:i + 2], 16) for i in (0, 2, 4, 6))  # type: ignore


class Texture:
    """An RGBA texture that is embedded into the .bbmodel as a data URL."""

    def __init__(self, name: str, width: int, height: int,
                 pixels: Optional[List[List[Tuple[int, int, int, int]]]] = None,
                 png_bytes: Optional[bytes] = None):
        self.name = name if name.endswith(".png") else name + ".png"
        self.width, self.height = width, height
        self.pixels = pixels
        self.png_bytes = png_bytes
        self.uuid = new_uuid()
        self.particle = False
        self.render_mode = "default"   # default | emissive | additive | layered
        self.frame_time = 1            # for animated (flipbook) textures
        self.index = -1

    # constructors ---------------------------------------------------------
    @classmethod
    def blank(cls, name: str, width: int = 16, height: int = 16,
              color="#00000000") -> "Texture":
        px = [[_parse_color(color)] * width for _ in range(height)]
        return cls(name, width, height, pixels=[row[:] for row in px])

    @classmethod
    def from_png(cls, path: str, name: Optional[str] = None) -> "Texture":
        data = open(path, "rb").read()
        if data[:8] != b"\x89PNG\r\n\x1a\n":
            raise ValueError(f"{path} is not a PNG")
        w, h = struct.unpack(">II", data[16:24])
        return cls(name or os.path.basename(path), w, h, png_bytes=data)

    # painting -------------------------------------------------------------
    def _need_pixels(self):
        if self.pixels is None:
            raise RuntimeError("texture loaded from PNG bytes cannot be painted; "
                               "use Texture.blank() for procedural textures")

    def set_pixel(self, x: int, y: int, color):
        self._need_pixels()
        if 0 <= x < self.width and 0 <= y < self.height:
            self.pixels[y][x] = _parse_color(color)

    def fill_rect(self, x: int, y: int, w: int, h: int, color):
        c = _parse_color(color)
        self._need_pixels()
        for yy in range(max(0, y), min(self.height, y + h)):
            row = self.pixels[yy]
            for xx in range(max(0, x), min(self.width, x + w)):
                row[xx] = c

    def noise_rect(self, x: int, y: int, w: int, h: int, color,
                   amount: int = 18, seed: int = 1):
        """Fill with per-pixel brightness jitter - the classic pixel-art look."""
        import random
        rnd = random.Random(seed)
        r, g, b, a = _parse_color(color)
        self._need_pixels()
        for yy in range(max(0, y), min(self.height, y + h)):
            for xx in range(max(0, x), min(self.width, x + w)):
                d = rnd.randint(-amount, amount)
                self.pixels[yy][xx] = (max(0, min(255, r + d)),
                                       max(0, min(255, g + d)),
                                       max(0, min(255, b + d)), a)

    def outline_rect(self, x: int, y: int, w: int, h: int, color):
        self.fill_rect(x, y, w, 1, color)
        self.fill_rect(x, y + h - 1, w, 1, color)
        self.fill_rect(x, y, 1, h, color)
        self.fill_rect(x + w - 1, y, 1, h, color)

    # encoding -------------------------------------------------------------
    def to_png(self) -> bytes:
        if self.png_bytes is not None:
            return self.png_bytes
        raw = b"".join(b"\x00" + bytes(v for px in row for v in px)
                       for row in self.pixels)

        def chunk(tag, data):
            return (struct.pack(">I", len(data)) + tag + data +
                    struct.pack(">I", zlib.crc32(tag + data) & 0xFFFFFFFF))
        return (b"\x89PNG\r\n\x1a\n" +
                chunk(b"IHDR", struct.pack(">IIBBBBB", self.width, self.height,
                                           8, 6, 0, 0, 0)) +
                chunk(b"IDAT", zlib.compress(raw, 9)) + chunk(b"IEND", b""))

    def save_png(self, path: str):
        with open(path, "wb") as f:
            f.write(self.to_png())

    def to_json(self, uv_size: Tuple[int, int]) -> dict:
        src = "data:image/png;base64," + base64.b64encode(self.to_png()).decode()
        return {
            "path": "", "name": self.name, "folder": "block", "namespace": "",
            "id": str(self.index), "width": self.width, "height": self.height,
            "uv_width": uv_size[0], "uv_height": uv_size[1],
            "particle": self.particle, "use_as_default": False,
            "layers_enabled": False, "sync_to_project": "",
            "render_mode": self.render_mode, "render_sides": "auto",
            "frame_time": self.frame_time, "frame_order_type": "loop",
            "frame_order": "", "frame_interpolate": False,
            "visible": True, "internal": True, "saved": False,
            "uuid": self.uuid, "relative_path": "", "source": src,
        }


# --------------------------------------------------------------------------
# Outliner nodes
# --------------------------------------------------------------------------
class Group:
    """A bone/folder. In Bedrock/entity formats this is an animatable bone."""

    def __init__(self, name: str, origin: Vec3 = (0, 0, 0),
                 rotation: Vec3 = (0, 0, 0), color: int = 0):
        self.name, self.origin, self.rotation, self.color = name, origin, rotation, color
        self.uuid = new_uuid()
        self.children: List[Union["Group", "Element"]] = []
        self.mirror_uv = False
        self.export = True
        self.visibility = True
        self.extra: Dict = {}   # e.g. {"bedrock_binding": "q.item_slot_to_bone_name(...)"}

    def to_outliner(self) -> dict:
        d = {"name": self.name, "origin": _vec(self.origin), "color": self.color,
             "uuid": self.uuid, "export": self.export, "mirror_uv": self.mirror_uv,
             "isOpen": True, "locked": False, "visibility": self.visibility,
             "autouv": 0,
             "children": [c.uuid if isinstance(c, Element) else c.to_outliner()
                          for c in self.children]}
        if any(self.rotation):
            d["rotation"] = _vec(self.rotation)
        d.update(self.extra)
        return d


class Element:
    type = "element"

    def __init__(self, name: str):
        self.name = name
        self.uuid = new_uuid()
        self.visibility = True
        self.export = True
        self.locked = False


class Cube(Element):
    type = "cube"

    def __init__(self, name, frm: Vec3, to: Vec3, origin: Optional[Vec3] = None,
                 rotation: Vec3 = (0, 0, 0), inflate: float = 0,
                 box_uv: bool = False, uv_offset: Tuple[int, int] = (0, 0),
                 mirror_uv: bool = False, texture: Optional[int] = 0,
                 faces: Optional[Dict[str, dict]] = None, color: int = 0,
                 shade: bool = True):
        super().__init__(name)
        self.frm, self.to = tuple(frm), tuple(to)
        if origin is None:
            origin = tuple((a + b) / 2 for a, b in zip(frm, to))
        self.origin, self.rotation = tuple(origin), tuple(rotation)
        self.inflate, self.box_uv, self.uv_offset = inflate, box_uv, tuple(uv_offset)
        self.mirror_uv, self.texture, self.color, self.shade = mirror_uv, texture, color, shade
        self.faces_override = faces or {}

    @property
    def size(self) -> Vec3:
        return tuple(b - a for a, b in zip(self.frm, self.to))

    def box_uv_faces(self) -> Dict[str, List[float]]:
        """Standard Minecraft box-UV layout at uv_offset (u, v)."""
        w, h, d = (abs(x) for x in self.size)
        u, v = self.uv_offset
        f = {
            "east":  [u,             v + d, u + d,             v + d + h],
            "north": [u + d,         v + d, u + d + w,         v + d + h],
            "west":  [u + d + w,     v + d, u + d + w + d,     v + d + h],
            "south": [u + 2 * d + w, v + d, u + 2 * d + 2 * w, v + d + h],
            "up":    [u + d + w,     v + d, u + d,             v],
            "down":  [u + d + 2 * w, v,     u + d + w,         v + d],
        }
        if self.mirror_uv:
            f["east"], f["west"] = f["west"], f["east"]
            for k in f:
                x1, y1, x2, y2 = f[k]
                f[k] = [x2, y1, x1, y2]
        return f

    def auto_faces(self) -> Dict[str, List[float]]:
        """Per-face UV: project each face onto its own size (like 'Auto UV')."""
        w, h, d = (abs(x) for x in self.size)
        return {"north": [0, 0, w, h], "south": [0, 0, w, h],
                "east": [0, 0, d, h], "west": [0, 0, d, h],
                "up": [0, 0, w, d], "down": [0, 0, w, d]}

    def to_json(self) -> dict:
        base = self.box_uv_faces() if self.box_uv else self.auto_faces()
        faces = {}
        for name in FACES:
            fd = {"uv": _vec(base[name]), "texture": self.texture}
            fd.update(self.faces_override.get(name, {}))
            if "uv" in fd:
                fd["uv"] = _vec(fd["uv"])
            faces[name] = fd
        d = {"name": self.name, "box_uv": self.box_uv, "rescale": False,
             "locked": self.locked, "light_emission": 0, "render_order": "default",
             "allow_mirror_modeling": True, "from": _vec(self.frm), "to": _vec(self.to),
             "autouv": 0, "color": self.color, "origin": _vec(self.origin),
             "faces": faces, "type": "cube", "uuid": self.uuid}
        if any(self.rotation):
            d["rotation"] = _vec(self.rotation)
        if self.inflate:
            d["inflate"] = _num(float(self.inflate))
        if self.box_uv:
            d["uv_offset"] = list(self.uv_offset)
            if self.mirror_uv:
                d["mirror_uv"] = True
        if not self.shade:
            d["shade"] = False
        if not self.visibility:
            d["visibility"] = False
        if not self.export:
            d["export"] = False
        return d


class Mesh(Element):
    """Free-form polygon mesh (Generic Model format only)."""
    type = "mesh"

    def __init__(self, name, origin: Vec3 = (0, 0, 0), rotation: Vec3 = (0, 0, 0),
                 color: int = 0):
        super().__init__(name)
        self.origin, self.rotation, self.color = origin, rotation, color
        self.vertices: Dict[str, Vec3] = {}
        self.faces: Dict[str, dict] = {}
        self._vi = 0
        self._fi = 0

    def add_vertex(self, pos: Vec3) -> str:
        self._vi += 1
        key = f"v{self._vi:03d}"
        self.vertices[key] = tuple(pos)
        return key

    def add_face(self, vkeys: Sequence[str], texture: Optional[int] = 0,
                 uv: Optional[Dict[str, Tuple[float, float]]] = None) -> str:
        """vkeys: 3 or 4 vertex keys, counter-clockwise when seen from outside."""
        if len(vkeys) not in (3, 4):
            raise ValueError("mesh faces need 3 or 4 vertices")
        self._fi += 1
        key = f"f{self._fi:03d}"
        if uv is None:   # simple default square mapping
            corners = [(0, 0), (16, 0), (16, 16), (0, 16)]
            uv = {k: corners[i] for i, k in enumerate(vkeys)}
        self.faces[key] = {"uv": {k: _vec(v) for k, v in uv.items()},
                           "vertices": list(vkeys), "texture": texture}
        return key

    # primitives -----------------------------------------------------------
    @classmethod
    def cylinder(cls, name, center: Vec3, radius: float, height: float,
                 sides: int = 12, texture: int = 0) -> "Mesh":
        m = cls(name, origin=center)
        cx, cy, cz = center
        bot, top = [], []
        for i in range(sides):
            a = 2 * math.pi * i / sides
            x, z = cx + radius * math.cos(a), cz + radius * math.sin(a)
            bot.append(m.add_vertex((x, cy, z)))
            top.append(m.add_vertex((x, cy + height, z)))
        for i in range(sides):
            j = (i + 1) % sides
            m.add_face([bot[i], top[i], top[j], bot[j]], texture)
        cb, ct = m.add_vertex((cx, cy, cz)), m.add_vertex((cx, cy + height, cz))
        for i in range(sides):
            j = (i + 1) % sides
            m.add_face([cb, bot[i], bot[j]], texture)
            m.add_face([ct, top[j], top[i]], texture)
        return m

    def to_json(self) -> dict:
        d = {"name": self.name, "color": self.color, "origin": _vec(self.origin),
             "rotation": _vec(self.rotation), "export": self.export,
             "visibility": self.visibility, "locked": self.locked,
             "render_order": "default", "allow_mirror_modeling": True,
             "vertices": {k: _vec(v) for k, v in self.vertices.items()},
             "faces": self.faces, "type": "mesh", "uuid": self.uuid}
        return d


class Locator(Element):
    """Attachment point (Bedrock: held items, particles, leash)."""
    type = "locator"

    def __init__(self, name, position: Vec3 = (0, 0, 0), rotation: Vec3 = (0, 0, 0)):
        super().__init__(name)
        self.position, self.rotation = position, rotation

    def to_json(self) -> dict:
        return {"name": self.name, "position": _vec(self.position),
                "rotation": _vec(self.rotation), "ignore_inherited_scale": False,
                "visibility": True, "locked": False, "type": "locator",
                "uuid": self.uuid}


class NullObject(Element):
    """IK target / helper used by the animator."""
    type = "null_object"

    def __init__(self, name, position: Vec3 = (0, 0, 0), ik_target: str = ""):
        super().__init__(name)
        self.position, self.ik_target = position, ik_target

    def to_json(self) -> dict:
        return {"name": self.name, "position": _vec(self.position),
                "ik_target": self.ik_target, "lock_ik_target_rotation": False,
                "visibility": True, "locked": False, "type": "null_object",
                "uuid": self.uuid}


# --------------------------------------------------------------------------
# Animation
# --------------------------------------------------------------------------
class Animation:
    def __init__(self, name: str, length: float = 1.0, loop: str = "loop",
                 snapping: int = 24, override: bool = False):
        if loop not in ("once", "hold", "loop"):
            raise ValueError("loop must be once | hold | loop")
        self.name, self.length, self.loop = name, length, loop
        self.snapping, self.override = snapping, override
        self.uuid = new_uuid()
        self.animators: Dict[str, dict] = {}
        self.extra: Dict = {}  # anim_time_update, blend_weight, start_delay, loop_delay

    def keyframe(self, group: Group, channel: str, time: float,
                 value: Union[Vec3, Sequence[Union[str, float]]],
                 interpolation: str = "linear",
                 bezier: Optional[dict] = None):
        """channel: rotation | position | scale.  Values may be numbers or Molang
        strings, e.g. ("math.sin(q.anim_time*360)*10", 0, 0).
        interpolation: linear | catmullrom | step | bezier."""
        if channel not in ("rotation", "position", "scale"):
            raise ValueError("bone channels are rotation, position, scale")
        an = self.animators.setdefault(group.uuid, {"name": group.name, "type": "bone",
                                                    "keyframes": []})
        x, y, z = (_num(v) if not isinstance(v, str) else v for v in value)
        kf = {"channel": channel, "data_points": [{"x": x, "y": y, "z": z}],
              "uuid": new_uuid(), "time": _num(float(time)), "color": -1,
              "interpolation": interpolation}
        if interpolation == "bezier":
            kf.update(bezier or {"bezier_linked": True,
                                 "bezier_left_time": [-0.1, -0.1, -0.1],
                                 "bezier_left_value": [0, 0, 0],
                                 "bezier_right_time": [0.1, 0.1, 0.1],
                                 "bezier_right_value": [0, 0, 0]})
        an["keyframes"].append(kf)
        return kf

    def effect(self, channel: str, time: float, **data):
        """Effects track: channel 'sound' (effect='mob.cow.say'), 'particle'
        (effect='minecraft:basic_flame_particle', locator='head'), 'timeline'
        (script='v.x = 1;')."""
        an = self.animators.setdefault("effects", {"name": "Effects", "type": "effect",
                                                   "keyframes": []})
        an["keyframes"].append({"channel": channel, "data_points": [data],
                                "uuid": new_uuid(), "time": _num(float(time)),
                                "color": -1, "interpolation": "linear"})

    def to_json(self) -> dict:
        d = {"uuid": self.uuid, "name": self.name, "loop": self.loop,
             "override": self.override, "length": _num(float(self.length)),
             "snapping": self.snapping, "selected": False,
             "anim_time_update": "", "blend_weight": "", "start_delay": "",
             "loop_delay": "", "animators": self.animators}
        d.update(self.extra)
        return d


# --------------------------------------------------------------------------
# Model
# --------------------------------------------------------------------------
class Model:
    def __init__(self, name: str, fmt: str = "free",
                 texture_size: Tuple[int, int] = (16, 16),
                 box_uv: Optional[bool] = None, identifier: str = ""):
        if fmt not in FORMATS:
            raise ValueError(f"unknown format {fmt!r}; choose from {list(FORMATS)}")
        self.name, self.fmt = name, fmt
        self.texture_size = tuple(texture_size)
        self.box_uv = (fmt in BOX_UV_DEFAULT) if box_uv is None else box_uv
        self.identifier = identifier or name
        self.root: List[Union[Group, Element]] = []
        self.elements: List[Element] = []
        self.textures: List[Texture] = []
        self.animations: List[Animation] = []
        self.display: Dict[str, dict] = {}
        self.visible_box = [1, 1, 0]
        self.extra: Dict = {}       # e.g. {"parent": "block/block", "ambientocclusion": False}

    # building -------------------------------------------------------------
    def _attach(self, node, parent: Optional[Group]):
        (parent.children if parent else self.root).append(node)
        node.parent = parent
        if isinstance(node, Element):
            self.elements.append(node)
        return node

    def group(self, name, origin: Vec3 = (0, 0, 0), rotation: Vec3 = (0, 0, 0),
              parent: Optional[Group] = None, **extra) -> Group:
        g = Group(name, origin, rotation)
        g.extra.update(extra)
        return self._attach(g, parent)

    def cube(self, name, frm: Vec3, to: Vec3, parent: Optional[Group] = None,
             **kw) -> Cube:
        kw.setdefault("box_uv", self.box_uv)
        return self._attach(Cube(name, frm, to, **kw), parent)

    def mesh(self, mesh: Mesh, parent: Optional[Group] = None) -> Mesh:
        return self._attach(mesh, parent)

    def locator(self, name, position: Vec3, parent: Optional[Group] = None,
                rotation: Vec3 = (0, 0, 0)) -> Locator:
        return self._attach(Locator(name, position, rotation), parent)

    def null_object(self, name, position: Vec3, parent: Optional[Group] = None,
                    ik_target: str = "") -> NullObject:
        return self._attach(NullObject(name, position, ik_target), parent)

    def add_texture(self, tex: Texture) -> Texture:
        tex.index = len(self.textures)
        self.textures.append(tex)
        return tex

    def animation(self, name, **kw) -> Animation:
        a = Animation(name, **kw)
        self.animations.append(a)
        return a

    def set_display(self, slot: str, rotation: Vec3 = (0, 0, 0),
                    translation: Vec3 = (0, 0, 0), scale: Vec3 = (1, 1, 1)):
        """Java Block/Item hand/GUI/ground transforms."""
        self.display[slot] = {"rotation": _vec(rotation),
                              "translation": _vec(translation), "scale": _vec(scale)}

    def mirror(self, src: Union[Group, Cube], axis: str = "x",
               rename: Tuple[str, str] = ("left", "right"),
               parent: Optional[Group] = "same"):
        """Duplicate a cube or group mirrored across the 0-plane of an axis
        (Blockbench's 'Mirror Modeling'). Names swap rename[0] <-> rename[1].
        The copy goes under the same parent as src unless parent is given."""
        if parent == "same":
            parent = getattr(src, "parent", None)
        i = "xyz".index(axis)

        def swap(n):
            a, b = rename
            if a in n:
                return n.replace(a, b)
            if b in n:
                return n.replace(b, a)
            return n + "_mirror"

        def flip(v):
            v = list(v)
            v[i] = -v[i]
            return tuple(v)

        def flip_rot(r):
            r = list(r)
            for k in range(3):
                if k != i:
                    r[k] = -r[k]
            return tuple(r)

        def clone(node, par):
            if isinstance(node, Cube):
                a, b = flip(node.frm), flip(node.to)
                frm = tuple(min(p, q) for p, q in zip(a, b))
                to = tuple(max(p, q) for p, q in zip(a, b))
                c = Cube(swap(node.name), frm, to, origin=flip(node.origin),
                         rotation=flip_rot(node.rotation), inflate=node.inflate,
                         box_uv=node.box_uv, uv_offset=node.uv_offset,
                         mirror_uv=not node.mirror_uv, texture=node.texture,
                         faces=dict(node.faces_override), color=node.color)
                return self._attach(c, par)
            if isinstance(node, Group):
                g = self.group(swap(node.name), flip(node.origin),
                               flip_rot(node.rotation), parent=par)
                g.extra.update(node.extra)
                for ch in node.children:
                    clone(ch, g)
                return g
            raise TypeError("mirror supports Cube and Group")
        return clone(src, parent)

    # serialising ----------------------------------------------------------
    def to_json(self) -> dict:
        d = {
            "meta": {"format_version": FORMAT_VERSION, "model_format": self.fmt,
                     "box_uv": self.box_uv},
            "name": self.name,
            "model_identifier": self.identifier,
            "visible_box": self.visible_box,
            "variable_placeholders": "",
            "variable_placeholder_buttons": [],
            "timeline_setups": [],
            "unhandled_root_fields": {},
            "resolution": {"width": self.texture_size[0],
                           "height": self.texture_size[1]},
            "elements": [self._fix_tex(e.to_json()) for e in self.elements],
            "outliner": [n.uuid if isinstance(n, Element) else n.to_outliner()
                         for n in self.root],
            "textures": [t.to_json(self.texture_size) for t in self.textures],
        }
        if self.animations:
            d["animations"] = [a.to_json() for a in self.animations]
        if self.display:
            d["display"] = self.display
        d.update(self.extra)
        return d

    def _fix_tex(self, ej: dict) -> dict:
        # no textures yet -> faces stay blank instead of pointing at slot 0
        if not self.textures and isinstance(ej.get("faces"), dict):
            for fd in ej["faces"].values():
                if fd.get("texture") == 0:
                    fd["texture"] = None
        return ej

    def save(self, path: str, validate: bool = True, strict: bool = True) -> List[str]:
        data = self.to_json()
        problems = validate_data(data) if validate else []
        errors = [p for p in problems if p.startswith("ERROR")]
        if strict and errors:
            raise ValueError("model failed validation:\n  " + "\n  ".join(errors))
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent="\t", ensure_ascii=False)
        return problems


# --------------------------------------------------------------------------
# Validation
# --------------------------------------------------------------------------
def _walk_outliner(nodes, groups, refs, depth=0):
    for n in nodes:
        if isinstance(n, str):
            refs.append(n)
        elif isinstance(n, dict):
            groups.append((n, depth))
            _walk_outliner(n.get("children", []), groups, refs, depth + 1)


def validate_data(d: dict, fmt: Optional[str] = None) -> List[str]:
    """Return a list of 'ERROR: ...' / 'WARN: ...' strings."""
    out: List[str] = []
    E = lambda m: out.append("ERROR: " + m)
    W = lambda m: out.append("WARN: " + m)

    meta = d.get("meta", {})
    fmt = fmt or meta.get("model_format", "free")
    if fmt not in FORMATS:
        W(f"unknown model_format {fmt!r} (plugin format?) - format rules skipped")
    if "format_version" not in meta:
        E("meta.format_version missing")
    if "groups" in d:
        W("file uses the 5.x 'groups' array; only outliner-inline groups are checked")

    elements = d.get("elements", [])
    textures = d.get("textures", [])
    by_uuid = {}
    for e in elements:
        u = e.get("uuid")
        if not u:
            E(f"element {e.get('name')!r} has no uuid")
        elif u in by_uuid:
            E(f"duplicate element uuid {u}")
        by_uuid[u] = e

    groups, refs = [], []
    _walk_outliner(d.get("outliner", []), groups, refs)
    for r in refs:
        if r not in by_uuid and "groups" not in d:
            E(f"outliner references missing element {r}")
    unref = set(by_uuid) - set(refs)
    for u in unref:
        W(f"element {by_uuid[u].get('name')!r} is not in the outliner (invisible in tree)")

    names_seen: Dict[str, int] = {}
    for g, depth in groups:
        names_seen[g.get("name")] = names_seen.get(g.get("name"), 0) + 1
    if fmt in ("bedrock", "bedrock_old", "bedrock_block", "modded_entity",
               "optifine_entity"):
        for n, c in names_seen.items():
            if c > 1:
                E(f"bone name {n!r} used {c} times - bones must be unique in {fmt}")

    ntex = len(textures)
    tw = d.get("resolution", {}).get("width", 16)
    th = d.get("resolution", {}).get("height", 16)
    for e in elements:
        name = e.get("name")
        t = e.get("type", "cube")
        if t == "mesh" and fmt not in MESH_FORMATS:
            E(f"mesh {name!r} not supported in format {fmt} (use Generic Model 'free')")
        if t == "cube":
            frm, to = e.get("from"), e.get("to")
            if not (frm and to and len(frm) == 3 and len(to) == 3):
                E(f"cube {name!r} needs from/to")
                continue
            if any(b < a for a, b in zip(frm, to)):
                W(f"cube {name!r} has to < from on some axis (negative size)")
            for face, fd in (e.get("faces") or {}).items():
                tex = fd.get("texture")
                if tex is not None and isinstance(tex, int) and tex >= ntex:
                    E(f"cube {name!r} face {face} uses texture {tex} but only {ntex} exist")
                uv = fd.get("uv")
                if uv and (max(uv[0], uv[2]) > tw or max(uv[1], uv[3]) > th
                           or min(uv) < 0):
                    W(f"cube {name!r} face {face} UV {uv} outside {tw}x{th} texture")
            rot = e.get("rotation", [0, 0, 0])
            if fmt == "java_block":
                if sum(1 for r in rot if r) > 1:
                    E(f"cube {name!r}: Java Block allows rotation on ONE axis only")
                for r in rot:
                    if r and r not in JAVA_ANGLES:
                        E(f"cube {name!r}: Java angle {r} not in {JAVA_ANGLES}")
                for v in list(frm) + list(to):
                    if v < -16 or v > 32:
                        E(f"cube {name!r}: Java Block coords must be within -16..32 (got {v})")
                if e.get("box_uv"):
                    W(f"cube {name!r}: box UV is unusual for Java Block")
        if t == "mesh":
            verts = e.get("vertices", {})
            for fk, fd in e.get("faces", {}).items():
                vs = fd.get("vertices", [])
                if len(vs) not in (3, 4):
                    W(f"mesh {name!r} face {fk} has {len(vs)} vertices (3 or 4 recommended)")
                for v in vs:
                    if v not in verts:
                        E(f"mesh {name!r} face {fk} references missing vertex {v}")

    if fmt == "java_block":
        for g, _ in groups:
            if any(g.get("rotation", [0, 0, 0])):
                W(f"group {g.get('name')!r} rotation is ignored on Java Block export")
        if len(elements) > 1024:
            W("very high element count for a Java block model (performance)")
        for slot in d.get("display", {}):
            if slot not in JAVA_DISPLAY_SLOTS and slot != "on_shelf":
                W(f"unknown display slot {slot!r}")
    if fmt in ("bedrock", "bedrock_old") and elements and not groups:
        E("Bedrock entity cubes must live inside a bone (group)")
    if fmt in ("bedrock", "bedrock_old"):
        for r in refs:
            pass
        for n in d.get("outliner", []):
            if isinstance(n, str):
                E(f"element {by_uuid.get(n, {}).get('name')!r} is at the root; "
                  f"Bedrock needs every cube inside a bone")

    group_uuids = {g.get("uuid") for g, _ in groups}
    for a in d.get("animations", []):
        if fmt == "java_block":
            W("animations are not exported by Java Block/Item")
        if a.get("loop") not in ("once", "hold", "loop"):
            E(f"animation {a.get('name')!r} loop must be once/hold/loop")
        for key, an in (a.get("animators") or {}).items():
            if an.get("type") == "bone" and key not in group_uuids:
                E(f"animation {a.get('name')!r} targets missing bone {key}")
            for kf in an.get("keyframes", []):
                if kf.get("time", 0) > a.get("length", 0) + 1e-6:
                    W(f"animation {a.get('name')!r}: keyframe at {kf.get('time')}s "
                      f"after length {a.get('length')}s")
    for t in textures:
        src = t.get("source", "")
        if not src.startswith("data:image/png;base64,") and not t.get("path"):
            W(f"texture {t.get('name')!r} has no embedded source or path")
    return out


# --------------------------------------------------------------------------
# CLI
# --------------------------------------------------------------------------
def _info(d: dict) -> str:
    groups, refs = [], []
    _walk_outliner(d.get("outliner", []), groups, refs)
    els = d.get("elements", [])
    kinds: Dict[str, int] = {}
    for e in els:
        kinds[e.get("type", "cube")] = kinds.get(e.get("type", "cube"), 0) + 1
    lines = [f"name: {d.get('name')}  format: {d.get('meta', {}).get('model_format')}"
             f"  version: {d.get('meta', {}).get('format_version')}",
             f"texture size: {d.get('resolution')}",
             f"elements: {kinds}  groups/bones: {len(groups)}",
             f"textures: {[t.get('name') for t in d.get('textures', [])]}",
             f"animations: {[a.get('name') for a in d.get('animations', [])]}"]
    by_uuid = {e.get("uuid"): e for e in els}

    def tree(nodes, ind=0):
        for n in nodes:
            if isinstance(n, str):
                e = by_uuid.get(n, {})
                lines.append("  " * ind + f"- {e.get('name')} [{e.get('type', 'cube')}]")
            else:
                lines.append("  " * ind + f"+ {n.get('name')} (pivot {n.get('origin')})")
                tree(n.get("children", []), ind + 1)
    lines.append("outliner:")
    tree(d.get("outliner", []), 1)
    return "\n".join(lines)


def preview(d: dict, out_path: str, scale: int = 8):
    """Orthographic front (-Z looking +Z), side (from +X) and top silhouettes of
    all cubes and mesh vertices, painted back-to-front. Rotations are ignored."""
    boxes = []
    palette = ["#e07a5f", "#3d405b", "#81b29a", "#f2cc8f", "#6d597a", "#277da1",
               "#f94144", "#90be6d", "#f9844a", "#4d908e"]
    for i, e in enumerate(d.get("elements", [])):
        if e.get("type", "cube") == "cube" and e.get("from"):
            f, t = e["from"], e["to"]
            inf = e.get("inflate", 0)
            boxes.append(([min(a, b) - inf for a, b in zip(f, t)],
                          [max(a, b) + inf for a, b in zip(f, t)], palette[i % 10]))
        elif e.get("type") == "mesh":
            o = e.get("origin", [0, 0, 0])
            vs = [[o[k] + v[k] for k in range(3)] for v in e.get("vertices", {}).values()]
            if vs:
                boxes.append(([min(v[k] for v in vs) for k in range(3)],
                              [max(v[k] for v in vs) for k in range(3)], palette[i % 10]))
    if not boxes:
        raise ValueError("nothing to preview")
    lo = [min(b[0][k] for b in boxes) for k in range(3)]
    hi = [max(b[1][k] for b in boxes) for k in range(3)]
    # views: (horizontal axis, flip_h, vertical axis, depth axis, depth_near_is_low)
    views = [(0, True, 1, 2, True),    # front: viewer at -Z, +X appears on the left
             (2, False, 1, 0, False),  # side: viewer at +X
             (0, True, 2, 1, False)]   # top: viewer at +Y
    pad = 2
    sizes = [(math.ceil(hi[h] - lo[h]) + pad * 2, math.ceil(hi[v] - lo[v]) + pad * 2)
             for h, _, v, _, _ in views]
    W = sum(w for w, _ in sizes) * scale + scale * 2
    H = max(h for _, h in sizes) * scale
    img = Texture.blank("preview", W, H, "#ffffff")
    x0 = 0
    for (h, fliph, v, dep, near_low), (w, hh) in zip(views, sizes):
        order = sorted(boxes, key=lambda b: (b[0][dep] if near_low else -b[1][dep]),
                       reverse=True)
        for bmin, bmax, col in order:
            if fliph:
                px1, px2 = hi[h] - bmax[h], hi[h] - bmin[h]
            else:
                px1, px2 = bmin[h] - lo[h], bmax[h] - lo[h]
            if v == 1:
                py1, py2 = hi[v] - bmax[v], hi[v] - bmin[v]
            else:
                py1, py2 = bmin[v] - lo[v], bmax[v] - lo[v]
            X = x0 + int(round((px1 + pad) * scale))
            Y = int(round((py1 + pad) * scale))
            ww = max(1, int(round((px2 - px1) * scale)))
            hh2 = max(1, int(round((py2 - py1) * scale)))
            img.fill_rect(X, Y, ww, hh2, col)
            img.outline_rect(X, Y, ww, hh2, "#111111")
        x0 += w * scale + scale
        img.fill_rect(x0 - scale // 2, 0, 1, H, "#cccccc")
    img.save_png(out_path)
    return out_path


def main(argv: List[str]) -> int:
    if len(argv) < 2 or argv[0] not in ("validate", "info", "extract-textures", "preview"):
        print(__doc__)
        return 2
    cmd, path = argv[0], argv[1]
    d = json.load(open(path, encoding="utf-8"))
    if cmd == "info":
        print(_info(d))
        return 0
    if cmd == "preview":
        out = argv[2] if len(argv) > 2 else os.path.splitext(path)[0] + "_preview.png"
        print("wrote", preview(d, out))
        return 0
    if cmd == "extract-textures":
        outdir = argv[2] if len(argv) > 2 else "."
        os.makedirs(outdir, exist_ok=True)
        for t in d.get("textures", []):
            src = t.get("source", "")
            if src.startswith("data:image/png;base64,"):
                p = os.path.join(outdir, os.path.basename(t.get("name", "tex.png")))
                open(p, "wb").write(base64.b64decode(src.split(",", 1)[1]))
                print("wrote", p)
        return 0
    fmt = None
    if "--format" in argv:
        fmt = argv[argv.index("--format") + 1]
    probs = validate_data(d, fmt)
    for p in probs:
        print(p)
    errs = sum(p.startswith("ERROR") for p in probs)
    print(f"{errs} error(s), {len(probs) - errs} warning(s)")
    return 1 if errs else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
