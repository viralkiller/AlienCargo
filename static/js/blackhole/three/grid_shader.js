export const MAX_PLANETS = 8;

export function makeGridMaterial(THREE) {
  const uniforms = {
    uTime: { value: 0 },
    uGridScale: { value: 0.35 },
    uLineWidth: { value: 2.0 },
    // [TUNED] Softening 5.0 = Distinct "Marble" size curve (not too sharp, not too flat)
    uSoftening: { value: 5.0 },
    // [TUNED] Depth 80.0 = Very deep heavy weight
    uDepth: { value: 80.0 },
    uFlowSpeed: { value: 2.0 },
    uFlowStrength: { value: 2.0 }, // Increased flow visual
    uPlanetCount: { value: 0 },
    uPlanetPos: {
      value: Array.from({ length: MAX_PLANETS }, () => new THREE.Vector3(9999, 0, 9999))
    },
    uPlanetMass: { value: new Array(MAX_PLANETS).fill(0) },
    ...THREE.UniformsLib.fog
  };

  const material = new THREE.ShaderMaterial({
    uniforms,
    side: THREE.DoubleSide,
    vertexShader: `
      uniform float uTime;
      uniform float uSoftening;
      uniform float uDepth;
      uniform int uPlanetCount;
      uniform vec3 uPlanetPos[${MAX_PLANETS}];
      uniform float uPlanetMass[${MAX_PLANETS}];

      varying vec2 vWorldXZ;
      varying float vWell;

      #include <fog_pars_vertex>

      float hash(vec2 p) { return fract(sin(dot(p, vec2(12.9898, 78.233))) * 43758.5453); }
      float noise(vec2 p) {
        vec2 i = floor(p); vec2 f = fract(p);
        f = f * f * (3.0 - 2.0 * f);
        return mix(mix(hash(i), hash(i + vec2(1.0, 0.0)), f.x),
                   mix(hash(i + vec2(0.0, 1.0)), hash(i + vec2(1.0, 1.0)), f.x), f.y);
      }
      float fbm(vec2 p, float t) {
        float total = 0.0; float amp = 1.0; float freq = 0.03;
        vec2 shift = vec2(t * 0.5, t * 0.25);
        for(int i = 0; i < 3; i++) {
            total += noise(p * freq + shift) * amp;
            freq *= 2.0; amp *= 0.5;
        }
        return total;
      }

      float well(vec2 d, float m) {
        float distSq = dot(d,d);
        // [NOTE] 1.0 / sqrt(...) creates the funnel
        return m / sqrt(distSq + uSoftening);
      }

      void main() {
        vec3 worldPos = (modelMatrix * vec4(position, 1.0)).xyz;

        float w = 0.0;
        for (int i = 0; i < ${MAX_PLANETS}; i++) {
          if (i >= uPlanetCount) break;
          w += well(worldPos.xz - uPlanetPos[i].xz, uPlanetMass[i]);
        }

        float terrain = fbm(worldPos.xz, uTime) * 4.0;

        vec3 p = position;
        p.y -= uDepth * w;
        p.y += terrain;

        vWorldXZ = worldPos.xz;
        vWell = w;

        vec4 mvPosition = modelViewMatrix * vec4(p, 1.0);
        gl_Position = projectionMatrix * mvPosition;
        #include <fog_vertex>
      }
    `,
    fragmentShader: `
      uniform float uTime;
      uniform float uGridScale;
      uniform float uLineWidth;
      uniform float uSoftening;
      uniform float uFlowSpeed;
      uniform float uFlowStrength;
      uniform int uPlanetCount;
      uniform vec3 uPlanetPos[${MAX_PLANETS}];
      uniform float uPlanetMass[${MAX_PLANETS}];

      varying vec2 vWorldXZ;
      varying float vWell;

      #include <fog_pars_fragment>

      float gridLines(vec2 p) {
        vec2 g = p * uGridScale;
        vec2 a = abs(fract(g - 0.5) - 0.5) / fwidth(g);
        float line = 1.0 - min(min(a.x, a.y), 1.0);
        return smoothstep(0.0, 1.0, line * uLineWidth);
      }

      void main() {
        vec2 flow = vec2(0.0);

        for (int i = 0; i < ${MAX_PLANETS}; i++) {
          if (i >= uPlanetCount) break;

          vec2 d = uPlanetPos[i].xz - vWorldXZ;
          float distSq = dot(d,d) + 1.0;
          float dist = sqrt(distSq);

          float speed = sqrt(uPlanetMass[i] / dist) * 2.0;

          vec2 radial = normalize(d);
          vec2 tangent = vec2(-radial.y, radial.x);
          vec2 dir = mix(radial, tangent, 0.4);

          flow += dir * speed;
        }

        vec2 baseRiver = vec2(0.0, 1.0);
        vec2 finalFlow = baseRiver * 0.2 + flow * uFlowStrength;
        vec2 sampleXZ = vWorldXZ - finalFlow * (uTime * uFlowSpeed);
        float line = gridLines(sampleXZ);

        vec3 bg = vec3(0.02, 0.02, 0.08);

        // [FIX] Boost glow to make the dip visible
        float glow = clamp(vWell * 4.0, 0.0, 1.2);

        vec3 col = mix(bg, vec3(1.0), line);
        // Add cyan glow in the wells
        col += glow * vec3(0.2, 0.8, 1.0);

        gl_FragColor = vec4(clamp(col, 0.0, 1.0), 1.0);

        #include <fog_fragment>
      }
    `,
    transparent: false,
    depthWrite: true,
    fog: true
  });

  return { material, uniforms };
}