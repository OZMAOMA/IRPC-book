# Driving Blockbench with JavaScript

Use a script when the user already has a project open and wants changes made
inside Blockbench, or when you need something the `.bbmodel` JSON can't easily
express (using Blockbench's own UV packing, export codecs, or batch edits on
an existing model).

Ways to run code:
1. **Dev console:** *Help → Developer → Open Dev Tools* (desktop app, Ctrl+Shift+I), then
   paste the code into the Console tab. This is quickest for one-off edits.
2. **Plugin file:** save as `my_tool.js`, then *File → Plugins → Load Plugin from File*.
   Use this for reusable tools that add menu items.
3. **Web app** (web.blockbench.net): plugins work there too. Node APIs (`fs`, `require`)
   only work in the desktop app.

API docs: https://www.blockbench.net/wiki/api/ and the type definitions in the
`blockbench-types` npm package. Check names there when unsure, because the API
changes between major versions.

## Always wrap edits in Undo

```js
Undo.initEdit({ elements: [], outliner: true, textures: [] });
// ... create / modify ...
Undo.finishEdit('Describe the edit', { elements: newElements, outliner: true });
Canvas.updateAll();   // refresh the 3D view
```
For edits to existing elements, pass them in `initEdit({elements: selected})` *before* you change them.

## Core objects

```js
// Project
newProject(Formats.bedrock);            // Formats.java_block, Formats.free, ...
Project.name = 'robot';
Project.texture_width = 64; Project.texture_height = 64;
Format.id;                               // current format

// Groups (bones)
const body = new Group({ name: 'body', origin: [0, 12, 0], rotation: [0, 0, 0] }).init();
const head = new Group({ name: 'head', origin: [0, 24, 0] }).addTo(body).init();

// Cubes
const torso = new Cube({
  name: 'torso', from: [-4, 12, -2], to: [4, 24, 2], origin: [0, 12, 0],
  box_uv: true, uv_offset: [16, 16], inflate: 0
}).addTo(body).init();
torso.extend({ rotation: [0, 0, 10] });
torso.applyTexture(Texture.all[0], true);   // true = all faces
torso.faces.north.uv = [0, 0, 8, 12];

// Meshes (Generic Model)
const mesh = new Mesh({ name: 'gem', vertices: {} }).init();
const [a, b, c, d] = mesh.addVertices([0,0,0], [4,0,0], [4,4,0], [0,4,0]);
mesh.addFaces(new MeshFace(mesh, { vertices: [a, b, c, d] }));

// Locators / null objects
new Locator({ name: 'rightitem', position: [-6, 12, 0] }).addTo(head).init();
new NullObject({ name: 'leg_ik', position: [2, 0, 0] }).init();

// Textures
const tex = new Texture({ name: 'robot.png' }).fromDataURL(dataUrl).add();
// or blank, then paint with a canvas:
const t2 = new Texture({ name: 'skin.png', width: 64, height: 64 }).fromDataURL(
  (() => { const c = document.createElement('canvas'); c.width = c.height = 64;
           const ctx = c.getContext('2d'); ctx.fillStyle = '#7a5'; ctx.fillRect(0,0,64,64);
           return c.toDataURL(); })()).add();
tex.edit((canvas) => { const ctx = canvas.getContext('2d'); ctx.fillRect(0, 0, 4, 4); });

// Selection & iteration
Cube.all, Group.all, Mesh.all, Outliner.selected, Cube.selected, Group.first_selected
Cube.all.filter(c => c.name.startsWith('leg')).forEach(c => c.extend({ inflate: 0.25 }));

// Animations
const anim = new Animation({ name: 'animation.robot.walk', length: 1, loop: 'loop' }).add();
const animator = anim.getBoneAnimator(head);
animator.addKeyframe({ channel: 'rotation', time: 0,   data_points: [{ x: 0,  y: 0, z: 0 }] });
animator.addKeyframe({ channel: 'rotation', time: 0.5, data_points: [{ x: 15, y: 0, z: 0 }], interpolation: 'catmullrom' });
anim.select();
```

## Export from code

```js
Codecs.project.compile();                  // .bbmodel JSON string
Codecs.java_block.compile();               // Java model JSON
Codecs.bedrock.compile();                  // geometry JSON
Codecs.obj.compile(); Codecs.gltf.compile( /* options */ );
// write a file (desktop):
Blockbench.export({ type: 'JSON Model', extensions: ['json'], name: 'robot',
                    content: Codecs.java_block.compile() });
```

## Minimal plugin skeleton

```js
(function () {
  let action;
  Plugin.register('mirror_all_left', {
    title: 'Mirror All Left Parts',
    author: 'you',
    description: 'Duplicates every *_left cube as *_right, mirrored on X.',
    icon: 'flip',
    version: '1.0.0',
    variant: 'both',            // desktop + web
    onload() {
      action = new Action('mirror_all_left', {
        name: 'Mirror All Left Parts',
        icon: 'flip',
        click() {
          const src = Cube.all.filter(c => c.name.includes('left'));
          Undo.initEdit({ elements: [], outliner: true });
          const made = src.map(c => {
            const n = new Cube(c).init();       // copy
            n.name = c.name.replace('left', 'right');
            const [fx, tx] = [-c.to[0], -c.from[0]];
            n.from[0] = fx; n.to[0] = tx; n.origin[0] = -c.origin[0];
            n.rotation[1] *= -1; n.rotation[2] *= -1;
            n.mirror_uv = !c.mirror_uv;
            n.addTo(c.parent === 'root' ? undefined : c.parent);
            return n;
          });
          Undo.finishEdit('Mirror left parts', { elements: made, outliner: true });
          Canvas.updateAll();
        }
      });
      MenuBar.addAction(action, 'filter');   // the Tools menu
    },
    onunload() { action.delete(); }
  });
})();
```

Useful UI helpers: `Blockbench.showQuickMessage('Done')`,
`new Dialog({ id, title, form: { size: { label: 'Size', type: 'number', value: 8 } }, onConfirm(r) {...} }).show()`,
`Blockbench.read(paths, { readtype: 'image' }, files => {...})`.
