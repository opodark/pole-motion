import * as THREE from 'three';
import { GLTFLoader } from '/vendor/GLTFLoader.js';
import { OrbitControls } from '/vendor/OrbitControls.js';

const SEGMENTS = [
  ['Abdomen', [23, 24], [11, 12]], ['Neck', [11, 12], [7, 8]],
  ['UpperArm.L', 11, 13], ['LowerArm.L', 13, 15], ['Palm.L', 15, 19],
  ['UpperArm.R', 12, 14], ['LowerArm.R', 14, 16], ['Palm.R', 16, 20],
  ['UpperLeg.L', 23, 25], ['LowerLeg.L', 25, 27], ['Foot.L', 27, 31],
  ['UpperLeg.R', 24, 26], ['LowerLeg.R', 26, 28], ['Foot.R', 28, 32],
];

const indices = value => Array.isArray(value) ? value : [value];
const visibility = (points, value) => Math.min(...indices(value).map(index => points[index][3]));
const point = (points, value) => {
  const result = new THREE.Vector3();
  for (const index of indices(value)) result.add(new THREE.Vector3(points[index][0], -points[index][1], -points[index][2]));
  return result.multiplyScalar(1 / indices(value).length);
};
const midpoint = (points, a, b) => point(points, a).add(point(points, b)).multiplyScalar(0.5);

export class RealAvatar {
  constructor(canvas, sample, sampleRoot, status) {
    this.canvas = canvas;
    this.sample = sample;
    this.sampleRoot = sampleRoot;
    this.status = status;
    this.motion = null;
    this.source = null;
    this.lastTime = null;
    this.bones = new Map();
    this.rest = new Map();
    this.followY = 0;
    this.renderer = new THREE.WebGLRenderer({ canvas, antialias: true });
    this.renderer.setPixelRatio(Math.min(devicePixelRatio, 2));
    this.renderer.shadowMap.enabled = true;
    this.renderer.shadowMap.type = THREE.PCFSoftShadowMap;
    this.renderer.outputColorSpace = THREE.SRGBColorSpace;
    this.renderer.toneMapping = THREE.ACESFilmicToneMapping;
    this.renderer.toneMappingExposure = 1.15;
    this.scene = new THREE.Scene();
    this.scene.background = new THREE.Color(0x101b17);
    this.scene.fog = new THREE.Fog(0x101b17, 5, 9);
    this.camera = new THREE.PerspectiveCamera(32, 1, 0.01, 30);
    this.camera.position.set(0, 1.1, 4.2);
    this.controls = new OrbitControls(this.camera, canvas);
    this.controls.enableDamping = true;
    this.controls.target.set(0, 0.95, 0);
    this.controls.minDistance = 2.1;
    this.controls.maxDistance = 7;
    this.scene.add(new THREE.HemisphereLight(0xd9edff, 0x223125, 1.7));
    const key = new THREE.DirectionalLight(0xfff0dd, 3.3);
    key.position.set(-2.5, 4.5, 3.5);
    key.castShadow = true;
    key.shadow.mapSize.set(2048, 2048);
    key.shadow.camera.left = key.shadow.camera.bottom = -2.5;
    key.shadow.camera.right = key.shadow.camera.top = 2.5;
    this.scene.add(key);
    const rim = new THREE.DirectionalLight(0x69cfff, 2.2);
    rim.position.set(3, 2.2, -3);
    this.scene.add(rim);
    const floor = new THREE.Mesh(new THREE.CircleGeometry(2.3, 96), new THREE.MeshStandardMaterial({ color: 0x22352c, roughness: 0.72, metalness: 0.05 }));
    floor.rotation.x = -Math.PI / 2;
    floor.receiveShadow = true;
    this.scene.add(floor);
    const pole = new THREE.Mesh(new THREE.CylinderGeometry(0.018, 0.018, 3.5, 24), new THREE.MeshStandardMaterial({ color: 0xd9dde0, roughness: 0.18, metalness: 0.9 }));
    pole.position.set(0.48, 1.75, -0.05);
    pole.castShadow = pole.receiveShadow = true;
    this.scene.add(pole);
    this.ready = new GLTFLoader().loadAsync('/models/female-athlete.glb').then(gltf => {
      this.model = gltf.scene;
      this.model.traverse(object => {
        if (object.isMesh) {
          object.castShadow = object.receiveShadow = true;
          if (object.material) {
            object.material.roughness = Math.max(0.42, object.material.roughness ?? 0.7);
            object.material.metalness = Math.min(0.05, object.material.metalness ?? 0);
          }
        }
        if (object.isBone) {
          this.bones.set(object.name, object);
          // GLTFLoader sanitizes dots from bone names used by animation tracks.
          for (const [name] of SEGMENTS) {
            if (THREE.PropertyBinding.sanitizeNodeName(name) === object.name) this.bones.set(name, object);
          }
        }
      });
      const box = new THREE.Box3().setFromObject(this.model);
      const scale = 1.72 / box.getSize(new THREE.Vector3()).y;
      this.model.scale.setScalar(scale);
      box.setFromObject(this.model);
      this.model.position.y = -box.min.y;
      this.basePosition = this.model.position.clone();
      this.targetPosition = this.basePosition.clone();
      this.model.rotation.y = 0;
      this.scene.add(this.model);
      this.model.updateMatrixWorld(true);
      for (const [name] of SEGMENTS) {
        const bone = this.bones.get(name);
        const child = bone?.children.find(object => object.isBone) || bone?.children[0];
        if (!bone || !child) continue;
        this.rest.set(name, { quaternion: bone.quaternion.clone(), direction: child.position.clone().applyQuaternion(bone.quaternion).normalize() });
      }
      this.lastTime = null;
      this.status('Modello 3D pronto. Il movimento viene trasferito sul rig umano.');
    }).catch(error => {
      this.status('Modello 3D non caricato: ' + error.message);
      throw error;
    });
    this.animate();
  }

  setMotion(motion, source) {
    this.motion = motion;
    this.source = source;
    this.lastTime = null;
    this.rootOrigin = motion.frames.map(frame => frame.root).find(root => root && root[2] >= 0.25) || null;
    if (this.basePosition) this.targetPosition = this.basePosition.clone();
  }

  view(name) {
    const d = 4.2;
    const height = 1.1 + this.followY;
    const position = name === 'side' ? [d, height, 0] : name === 'rear' ? [0, height, -d] : [0, height, d];
    this.camera.position.set(...position);
    this.controls.target.set(0, 0.95 + this.followY, 0);
    this.controls.update();
  }

  resize() {
    const width = Math.max(1, this.canvas.clientWidth);
    const height = Math.max(1, this.canvas.clientHeight);
    const pixelRatio = Math.min(devicePixelRatio, 2);
    if (this.canvas.width !== Math.round(width * pixelRatio) || this.canvas.height !== Math.round(height * pixelRatio)) {
      this.renderer.setSize(width, height, false);
      this.camera.aspect = width / height;
      this.camera.updateProjectionMatrix();
    }
  }

  apply(points, root) {
    if (!this.model) return;
    if (root && this.rootOrigin && root[2] >= 0.25 && this.basePosition) {
      this.targetPosition.set(
        this.basePosition.x + (root[0] - this.rootOrigin[0]) * 3.0,
        this.basePosition.y + (this.rootOrigin[1] - root[1]) * 3.4,
        this.basePosition.z
      );
    }
    const hips = this.bones.get('Hips');
    if (hips && [11, 12, 23, 24].every(index => points[index][3] >= 0.45)) {
      const torso = midpoint(points, 11, 12).sub(midpoint(points, 23, 24)).normalize();
      hips.rotation.z = THREE.MathUtils.clamp(-Math.atan2(torso.x, torso.y), -1.2, 1.2);
    }
    for (const [name, start, end] of SEGMENTS) {
      const bone = this.bones.get(name), rest = this.rest.get(name);
      if (!bone || !rest || Math.min(visibility(points, start), visibility(points, end)) < 0.25) continue;
      bone.quaternion.copy(rest.quaternion);
      bone.updateWorldMatrix(true, false);
      const parentWorld = bone.parent.getWorldQuaternion(new THREE.Quaternion());
      const desired = point(points, end).sub(point(points, start)).normalize().applyQuaternion(parentWorld.invert());
      bone.quaternion.copy(new THREE.Quaternion().setFromUnitVectors(rest.direction, desired).multiply(rest.quaternion));
      bone.updateWorldMatrix(true, true);
    }

    // This FBX rig stores feet outside the leg hierarchy (Blender IK controls).
    // glTF has no Blender constraints: attach each foot to its animated ankle.
    for (const side of ['L', 'R']) {
      const foot = this.bones.get('Foot.' + side);
      const leg = this.bones.get('LowerLeg.' + side);
      const ankle = leg?.children[0];
      if (foot && ankle) {
        const position = ankle.getWorldPosition(new THREE.Vector3());
        foot.position.copy(foot.parent.worldToLocal(position));
        foot.updateWorldMatrix(true, true);
      }
    }

  }

  animate() {
    requestAnimationFrame(() => this.animate());
    this.resize();
    this.controls.update();
    if (this.motion && this.source && this.source.currentTime !== this.lastTime) {
      this.lastTime = this.source.currentTime;
      const points = this.sample(this.motion.frames, this.lastTime);
      const root = this.sampleRoot(this.motion.frames, this.lastTime);
      if (points) this.apply(points, root);
    }
    if (this.model && this.targetPosition) {
      this.model.position.lerp(this.targetPosition, 0.2);
      const nextFollowY = this.model.position.y - this.basePosition.y;
      const followDelta = nextFollowY - this.followY;
      this.camera.position.y += followDelta;
      this.controls.target.y += followDelta;
      this.followY = nextFollowY;
    }
    this.renderer.render(this.scene, this.camera);
  }
}

export const createAvatar = (canvas, sample, sampleRoot, status) => new RealAvatar(canvas, sample, sampleRoot, status);
