// BlackHole.js
import * as THREE from 'three';

export function createBlackHole(scene) {
    const geometry = new THREE.PlaneGeometry(150, 150, 70, 70);
    const posAttribute = geometry.getAttribute('position');
    const vec = new THREE.Vector3();

    for (let i = 0; i < posAttribute.count; i++) {
        vec.fromBufferAttribute(posAttribute, i);
        const dist = Math.sqrt(vec.x * vec.x + vec.y * vec.y);

        let zOff = 0;
        if (dist < 30) {
            zOff = -400 / (dist + 5) + 12;
        } else {
            zOff = -2;
        }

        zOff += (Math.random() - 0.5) * 1.5; // Glitchy noise
        posAttribute.setXYZ(i, vec.x, vec.y, zOff);
    }

    geometry.computeVertexNormals();

    const mat = new THREE.MeshStandardMaterial({
        color: 0xaa00ff, // Changed to synthwave purple/pink
        wireframe: true,
        emissive: 0x330066,
        emissiveIntensity: 1.5
    });

    const mesh = new THREE.Mesh(geometry, mat);
    mesh.rotation.x = -Math.PI / 2;
    scene.add(mesh);

    return mesh;
}