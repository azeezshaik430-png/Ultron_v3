/**
 * ULTRON V3 — Cinematic 3D AI Reactor Core
 * Inspired by deep concentric mechanical construction with energy network,
 * glowing nodes, and a blazing central core. Fully 3D with perspective camera.
 */

class ULTRONAvatar {
    constructor(canvasId) {
        this.canvas = document.getElementById(canvasId);
        if (!this.canvas) return;

        this.container = this.canvas.parentElement;
        this.clock = new THREE.Clock();

        this._targetEnergy = 1.0;
        this._targetRotSpeed = 1.0;
        this._curEnergy = 1.0;
        this._curRotSpeed = 1.0;

        this._initScene();
        this._buildReactor();
        this._addLighting();
        this._resize();
        this._animate();

        window.addEventListener('resize', () => this._resize());
        if (window.uiStateMachine) {
            window.uiStateMachine.subscribe((s) => this._onState(s));
        }
    }

    /* ═══════ SCENE ═══════ */
    _initScene() {
        this.scene = new THREE.Scene();
        this.scene.fog = new THREE.FogExp2(0x020304, 0.04);

        this.camera = new THREE.PerspectiveCamera(35, this._aspect(), 0.1, 100);
        this.camera.position.set(0, 0.5, 7.0);
        this.camera.lookAt(0, 0, 0);

        this._camOrbitRadius = 7.0;
        this._camOrbitAngle = 0;
        this._camOrbitTilt = 0.5;
        this._camOrbitSpeed = 0.04;
        this._camBreatheAmp = 0.06;
        this._camBreatheSpeed = 0.3;

        this.renderer = new THREE.WebGLRenderer({
            canvas: this.canvas,
            alpha: true,
            antialias: true,
        });
        this.renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2));
        this.renderer.toneMapping = THREE.ACESFilmicToneMapping;
        this.renderer.toneMappingExposure = 1.0;
        this.renderer.outputEncoding = THREE.sRGBEncoding;
        this.renderer.shadowMap.enabled = true;
        this.renderer.shadowMap.type = THREE.PCFSoftShadowMap;
        this.renderer.setClearColor(0x000000, 0);
    }

    _aspect() {
        if (!this.container) return 1;
        return this.container.clientWidth / Math.max(this.container.clientHeight, 1);
    }

    /* ═══════ MATERIALS ═══════ */
    _mats() {
        this.matHousing = new THREE.MeshStandardMaterial({
            color: 0x1a1d24, metalness: 0.94, roughness: 0.12,
        });
        this.matHousingDark = new THREE.MeshStandardMaterial({
            color: 0x0e1015, metalness: 0.9, roughness: 0.2,
        });
        this.matGold = new THREE.MeshStandardMaterial({
            color: 0xd4a843, metalness: 0.95, roughness: 0.08,
        });
        this.matGoldDim = new THREE.MeshStandardMaterial({
            color: 0x8b7230, metalness: 0.9, roughness: 0.16,
        });
        this.matGoldBright = new THREE.MeshStandardMaterial({
            color: 0xf5c842, metalness: 0.85, roughness: 0.1,
            emissive: 0xd4a843, emissiveIntensity: 0.3,
        });
        this.matAmber = new THREE.MeshStandardMaterial({
            color: 0xe8a020, emissive: 0xe8a020, emissiveIntensity: 0.6,
            metalness: 0.3, roughness: 0.3,
            transparent: true, opacity: 0.6,
        });
        this.matCore = new THREE.MeshStandardMaterial({
            color: 0xffffff, emissive: 0xffe8b0, emissiveIntensity: 3.0,
            metalness: 0.0, roughness: 0.0,
        });
        this.matCoreGlow = new THREE.MeshBasicMaterial({
            color: 0xd4a843, transparent: true, opacity: 0.2,
        });
        this.matCoreOuter = new THREE.MeshBasicMaterial({
            color: 0xe8a020, transparent: true, opacity: 0.08,
        });
        this.matGlass = new THREE.MeshStandardMaterial({
            color: 0xd4a843, transparent: true, opacity: 0.03,
            metalness: 0.0, roughness: 0.05, side: THREE.DoubleSide,
        });
        this.matNetwork = new THREE.MeshBasicMaterial({
            color: 0xd4a843, transparent: true, opacity: 0.25,
        });
        this.matNode = new THREE.MeshBasicMaterial({
            color: 0xf5c842, transparent: true, opacity: 0.7,
        });
        this.matNodeSmall = new THREE.MeshBasicMaterial({
            color: 0xd4a843, transparent: true, opacity: 0.5,
        });
        this.matPanel = new THREE.MeshStandardMaterial({
            color: 0x12141a, metalness: 0.88, roughness: 0.22,
        });
    }

    /* ═══════ BUILD REACTOR ═══════ */
    _buildReactor() {
        this._mats();
        this.reactor = new THREE.Group();

        this._buildDeepHousing();
        this._buildConcentricRings();
        this._buildNetworkLines();
        this._buildNodes();
        this._buildCoreAssembly();
        this._buildSupportStruts();

        this.scene.add(this.reactor);

        // Core lights
        this.coreLight = new THREE.PointLight(0xd4a843, 3.0, 6.0, 1.5);
        this.coreLight.position.set(0, 0, 0);
        this.reactor.add(this.coreLight);

        this.coreLight2 = new THREE.PointLight(0xffffff, 1.5, 3.0, 2);
        this.coreLight2.position.set(0, 0, 0.1);
        this.reactor.add(this.coreLight2);

        this.warmFill = new THREE.PointLight(0xe8a020, 0.6, 4.0, 2);
        this.warmFill.position.set(0, 0.3, 0.2);
        this.reactor.add(this.warmFill);
    }

    /* ── Deep Housing: massive outer rings with Z-depth ── */
    _buildDeepHousing() {
        const g = new THREE.Group();

        // 5 layers of housing torus, progressively deeper
        const layers = [
            { r: 2.4, tube: 0.14, z: 0.0, mat: this.matHousing },
            { r: 2.55, tube: 0.06, z: 0.12, mat: this.matHousingDark },
            { r: 2.55, tube: 0.06, z: -0.12, mat: this.matHousingDark },
            { r: 2.65, tube: 0.04, z: 0.2, mat: this.matHousingDark },
            { r: 2.65, tube: 0.04, z: -0.2, mat: this.matHousingDark },
        ];

        this.housingRings = [];
        for (const l of layers) {
            const geo = new THREE.TorusGeometry(l.r, l.tube, 16, 80);
            const m = new THREE.Mesh(geo, l.mat);
            m.position.z = l.z;
            m.castShadow = true;
            m.receiveShadow = true;
            g.add(m);
            this.housingRings.push(m);
        }

        // Gold accent rings on outer housing
        for (const z of [0.14, -0.14]) {
            const geo = new THREE.TorusGeometry(2.58, 0.015, 8, 80);
            const m = new THREE.Mesh(geo, this.matGold);
            m.position.z = z;
            g.add(m);
        }

        // Panel detail — 12 segments around the housing
        for (let i = 0; i < 12; i++) {
            const a = (i / 12) * Math.PI * 2;
            const geo = new THREE.BoxGeometry(0.25, 0.08, 0.28);
            const m = new THREE.Mesh(geo, this.matPanel);
            m.position.set(Math.cos(a) * 2.4, Math.sin(a) * 2.4, 0);
            m.rotation.z = a;
            m.castShadow = true;
            g.add(m);

            // Gold accent stripe on panel
            const sGeo = new THREE.BoxGeometry(0.26, 0.012, 0.29);
            const s = new THREE.Mesh(sGeo, this.matGoldDim);
            s.position.set(Math.cos(a) * 2.4, Math.sin(a) * 2.4, 0);
            s.rotation.z = a;
            g.add(s);
        }

        // Bolts
        for (let i = 0; i < 24; i++) {
            const a = (i / 24) * Math.PI * 2;
            const geo = new THREE.CylinderGeometry(0.018, 0.018, 0.03, 6);
            const m = new THREE.Mesh(geo, this.matGoldDim);
            m.position.set(Math.cos(a) * 2.52, Math.sin(a) * 2.52, 0.2);
            m.rotation.x = Math.PI / 2;
            g.add(m);
        }

        this.reactor.add(g);
        this.outerHousing = g;
    }

    /* ── Concentric Rings: 8 rings at different Z-depths and tilts ── */
    _buildConcentricRings() {
        const ringDefs = [
            { r: 2.0, tube: 0.04, z: 0.05, tiltX: 0, tiltY: 0, mat: this.matGold, speed: 0.08 },
            { r: 1.85, tube: 0.025, z: -0.08, tiltX: 8, tiltY: 0, mat: this.matGoldDim, speed: -0.12 },
            { r: 1.65, tube: 0.035, z: 0.12, tiltX: -5, tiltY: 3, mat: this.matGold, speed: 0.15 },
            { r: 1.45, tube: 0.02, z: -0.05, tiltX: 12, tiltY: -4, mat: this.matGoldBright, speed: -0.2 },
            { r: 1.25, tube: 0.03, z: 0.08, tiltX: -8, tiltY: 6, mat: this.matGold, speed: 0.25 },
            { r: 1.05, tube: 0.018, z: -0.03, tiltX: 15, tiltY: -2, mat: this.matAmber, speed: -0.3 },
            { r: 0.85, tube: 0.025, z: 0.06, tiltX: -3, tiltY: 10, mat: this.matGold, speed: 0.35 },
            { r: 0.65, tube: 0.015, z: 0.0, tiltX: 6, tiltY: -8, mat: this.matAmber, speed: -0.4 },
        ];

        this.concentricRings = [];
        for (const d of ringDefs) {
            const geo = new THREE.TorusGeometry(d.r, d.tube, 12, 64);
            const m = new THREE.Mesh(geo, d.mat);
            m.position.z = d.z;
            m.rotation.x = (d.tiltX * Math.PI) / 180;
            m.rotation.y = (d.tiltY * Math.PI) / 180;
            m.castShadow = true;
            this.reactor.add(m);
            this.concentricRings.push({ mesh: m, speed: d.speed, mat: d.mat });
        }

        // Tick marks on ring 1
        for (let i = 0; i < 48; i++) {
            const a = (i / 48) * Math.PI * 2;
            const geo = new THREE.BoxGeometry(0.008, 0.04, 0.012);
            const m = new THREE.Mesh(geo, this.matGoldDim);
            m.position.set(Math.cos(a) * 2.0, Math.sin(a) * 2.0, 0.05);
            m.rotation.z = a;
            this.reactor.add(m);
        }
    }

    /* ── Network Lines: thin golden energy paths connecting rings ── */
    _buildNetworkLines() {
        const lineGroup = new THREE.Group();

        // Radial lines — 16 lines from outer to inner
        for (let i = 0; i < 16; i++) {
            const a = (i / 16) * Math.PI * 2;
            const innerR = 0.5;
            const outerR = 2.0;

            const points = [];
            const segCount = 8;
            for (let j = 0; j <= segCount; j++) {
                const t = j / segCount;
                const r = innerR + (outerR - innerR) * t;
                const z = Math.sin(t * Math.PI) * 0.15; // slight depth curve
                points.push(new THREE.Vector3(Math.cos(a) * r, Math.sin(a) * r, z));
            }

            const curve = new THREE.CatmullRomCurve3(points);
            const tubeGeo = new THREE.TubeGeometry(curve, 12, 0.004, 4, false);
            const tube = new THREE.Mesh(tubeGeo, this.matNetwork);
            lineGroup.add(tube);
        }

        // Cross-connecting arcs at mid-radius
        for (let i = 0; i < 8; i++) {
            const a1 = (i / 8) * Math.PI * 2;
            const a2 = ((i + 1) / 8) * Math.PI * 2;
            const midR = 1.3;

            const points = [];
            const steps = 6;
            for (let j = 0; j <= steps; j++) {
                const t = j / steps;
                const a = a1 + (a2 - a1) * t;
                const r = midR + Math.sin(t * Math.PI) * 0.15;
                const z = Math.sin(t * Math.PI * 2) * 0.08;
                points.push(new THREE.Vector3(Math.cos(a) * r, Math.sin(a) * r, z));
            }

            const curve = new THREE.CatmullRomCurve3(points);
            const tubeGeo = new THREE.TubeGeometry(curve, 8, 0.003, 4, false);
            const tube = new THREE.Mesh(tubeGeo, this.matNetwork);
            lineGroup.add(tube);
        }

        this.reactor.add(lineGroup);
        this.networkLines = lineGroup;
    }

    /* ── Nodes: glowing intersection points ── */
    _buildNodes() {
        const nodeGroup = new THREE.Group();
        this.nodeMeshes = [];

        // Outer ring nodes (16)
        for (let i = 0; i < 16; i++) {
            const a = (i / 16) * Math.PI * 2;
            const geo = new THREE.SphereGeometry(0.03, 8, 8);
            const m = new THREE.Mesh(geo, this.matNode.clone());
            m.position.set(Math.cos(a) * 2.0, Math.sin(a) * 2.0, 0);
            nodeGroup.add(m);
            this.nodeMeshes.push(m);
        }

        // Mid ring nodes (12)
        for (let i = 0; i < 12; i++) {
            const a = (i / 12) * Math.PI * 2;
            const geo = new THREE.SphereGeometry(0.025, 8, 8);
            const m = new THREE.Mesh(geo, this.matNode.clone());
            m.position.set(Math.cos(a) * 1.3, Math.sin(a) * 1.3, Math.sin(a * 2) * 0.08);
            nodeGroup.add(m);
            this.nodeMeshes.push(m);
        }

        // Inner ring nodes (8)
        for (let i = 0; i < 8; i++) {
            const a = (i / 8) * Math.PI * 2;
            const geo = new THREE.SphereGeometry(0.02, 8, 8);
            const m = new THREE.Mesh(geo, this.matNodeSmall.clone());
            m.position.set(Math.cos(a) * 0.7, Math.sin(a) * 0.7, 0.04);
            nodeGroup.add(m);
            this.nodeMeshes.push(m);
        }

        this.reactor.add(nodeGroup);
        this.nodeGroup = nodeGroup;
    }

    /* ── Core Assembly: layered energy core ── */
    _buildCoreAssembly() {
        // Innermost ring
        const innerGeo = new THREE.TorusGeometry(0.45, 0.012, 10, 32);
        this.innerRing = new THREE.Mesh(innerGeo, this.matAmber);
        this.innerRing.position.z = 0.02;
        this.reactor.add(this.innerRing);

        // Energy containment ring
        const eGeo = new THREE.TorusGeometry(0.35, 0.008, 8, 32);
        this.energyRing = new THREE.Mesh(eGeo, this.matAmber);
        this.energyRing.position.z = 0.03;
        this.energyRing.rotation.x = 15 * Math.PI / 180;
        this.reactor.add(this.energyRing);

        // Second energy ring
        const e2Geo = new THREE.TorusGeometry(0.28, 0.006, 8, 24);
        this.energyRing2 = new THREE.Mesh(e2Geo, this.matAmber);
        this.energyRing2.position.z = 0.025;
        this.energyRing2.rotation.x = -20 * Math.PI / 180;
        this.reactor.add(this.energyRing2);

        // Wireframe inner mechanism
        const icoGeo = new THREE.IcosahedronGeometry(0.3, 0);
        const icoMat = new THREE.MeshBasicMaterial({
            color: 0xd4a843, wireframe: true, transparent: true, opacity: 0.3,
        });
        this.innerIco = new THREE.Mesh(icoGeo, icoMat);
        this.innerIco.position.z = 0.02;
        this.reactor.add(this.innerIco);

        // Core sphere — white-hot
        const coreGeo = new THREE.SphereGeometry(0.12, 32, 32);
        this.coreMesh = new THREE.Mesh(coreGeo, this.matCore);
        this.coreMesh.position.z = 0.02;
        this.reactor.add(this.coreMesh);

        // Core glow shell 1
        const glow1Geo = new THREE.SphereGeometry(0.2, 16, 16);
        this.coreGlow1 = new THREE.Mesh(glow1Geo, this.matCoreGlow);
        this.coreGlow1.position.z = 0.02;
        this.reactor.add(this.coreGlow1);

        // Core glow shell 2 (larger, more diffuse)
        const glow2Geo = new THREE.SphereGeometry(0.35, 16, 16);
        this.coreGlow2 = new THREE.Mesh(glow2Geo, this.matCoreOuter);
        this.coreGlow2.position.z = 0.02;
        this.reactor.add(this.coreGlow2);

        // Glass dome over core
        const domeGeo = new THREE.SphereGeometry(0.5, 24, 12, 0, Math.PI * 2, 0, Math.PI / 2);
        this.glassDome = new THREE.Mesh(domeGeo, this.matGlass);
        this.glassDome.rotation.x = -Math.PI / 2;
        this.glassDome.position.z = 0.03;
        this.reactor.add(this.glassDome);
    }

    /* ── Support Struts ── */
    _buildSupportStruts() {
        const strutMat = new THREE.MeshStandardMaterial({
            color: 0x1a1c22, metalness: 0.9, roughness: 0.2,
        });

        for (let i = 0; i < 8; i++) {
            const a = (i / 8) * Math.PI * 2;
            const outerR = 2.2;
            const innerR = 0.55;

            const ox = Math.cos(a) * outerR;
            const oy = Math.sin(a) * outerR;
            const ix = Math.cos(a) * innerR;
            const iy = Math.sin(a) * innerR;

            const length = Math.sqrt((ox - ix) ** 2 + (oy - iy) ** 2);
            const geo = new THREE.CylinderGeometry(0.012, 0.012, length, 6);
            const m = new THREE.Mesh(geo, strutMat);
            m.position.set((ox + ix) / 2, (oy + iy) / 2, 0);
            m.rotation.z = a + Math.PI / 2;
            this.reactor.add(m);

            // Bracket at outer end
            const bGeo = new THREE.BoxGeometry(0.04, 0.04, 0.06);
            const b = new THREE.Mesh(bGeo, this.matHousingDark);
            b.position.set(ox, oy, 0);
            this.reactor.add(b);

            // Bracket at inner end
            const biGeo = new THREE.BoxGeometry(0.025, 0.025, 0.04);
            const bi = new THREE.Mesh(biGeo, this.matGoldDim);
            bi.position.set(ix, iy, 0.02);
            this.reactor.add(bi);
        }
    }

    /* ═══════ LIGHTING ═══════ */
    _addLighting() {
        // Key — warm gold from above-right
        const key = new THREE.DirectionalLight(0xd4a843, 1.0);
        key.position.set(4, 5, 4);
        key.castShadow = true;
        key.shadow.mapSize.set(1024, 1024);
        this.scene.add(key);

        // Fill — steel from left
        const fill = new THREE.DirectionalLight(0x888899, 0.25);
        fill.position.set(-4, 2, 3);
        this.scene.add(fill);

        // Rim — behind
        const rim = new THREE.DirectionalLight(0xd4a843, 0.4);
        rim.position.set(0, 3, -5);
        this.scene.add(rim);

        // Bottom
        const bottom = new THREE.DirectionalLight(0x8b7230, 0.12);
        bottom.position.set(0, -4, 2);
        this.scene.add(bottom);

        this.scene.add(new THREE.AmbientLight(0x0a0b10, 0.35));
        this.scene.add(new THREE.HemisphereLight(0x1a1d24, 0x060708, 0.25));
    }

    /* ═══════ STATE ═══════ */
    _onState(state) {
        const label = document.getElementById('avatarStateLabel');
        const map = {
            IDLE:                 { energy: 1.0, rot: 1.0, label: 'STANDBY', color: 0xd4a843, ei: 3.0 },
            LISTENING:            { energy: 1.4, rot: 1.5, label: 'LISTENING', color: 0xe8a020, ei: 3.5 },
            THINKING:             { energy: 1.7, rot: 2.5, label: 'THINKING', color: 0xf5c842, ei: 4.0 },
            PROCESSING:           { energy: 1.7, rot: 2.5, label: 'PROCESSING', color: 0xf5c842, ei: 4.0 },
            SPEAKING:             { energy: 1.3, rot: 1.2, label: 'SPEAKING', color: 0xf5c842, ei: 3.5 },
            EXECUTING:            { energy: 2.0, rot: 3.0, label: 'EXECUTING', color: 0xd4a843, ei: 4.0 },
            WAITING_CONFIRMATION: { energy: 1.1, rot: 0.5, label: 'CONFIRM', color: 0xcc3333, ei: 3.5 },
            SUCCESS:              { energy: 2.5, rot: 2.0, label: 'SUCCESS', color: 0x33aa55, ei: 4.5 },
            ERROR:                { energy: 0.4, rot: 0.3, label: 'ERROR', color: 0xcc3333, ei: 1.5 },
            OFFLINE:              { energy: 0.15, rot: 0.0, label: 'OFFLINE', color: 0x333333, ei: 0.5 },
        };

        const cfg = map[state] || map.IDLE;
        this._targetEnergy = cfg.energy;
        this._targetRotSpeed = cfg.rot;

        this.matCore.color.setHex(cfg.color);
        this.matCore.emissive.setHex(cfg.color);
        this.matCore.emissiveIntensity = cfg.ei;

        this.matCoreGlow.color.setHex(cfg.color);
        this.matCoreOuter.color.setHex(cfg.color);

        this.coreLight.color.setHex(cfg.color);
        this.coreLight2.color.setHex(cfg.color);
        this.warmFill.color.setHex(cfg.color);

        if (label) label.textContent = cfg.label;
    }

    /* ═══════ RESIZE ═══════ */
    _resize() {
        if (!this.container || !this.renderer) return;
        const w = this.container.clientWidth;
        const h = this.container.clientHeight;
        if (w === 0 || h === 0) return;
        this.camera.aspect = w / h;
        this.camera.updateProjectionMatrix();
        this.renderer.setSize(w, h);
    }

    /* ═══════ ANIMATION ═══════ */
    _animate() {
        requestAnimationFrame(() => this._animate());
        const dt = Math.min(this.clock.getDelta(), 0.05);
        const t = this.clock.getElapsedTime();

        const lerp = 1 - Math.pow(0.03, dt);
        this._curEnergy += (this._targetEnergy - this._curEnergy) * lerp;
        this._curRotSpeed += (this._targetRotSpeed - this._curRotSpeed) * lerp;
        const E = this._curEnergy;
        const RS = this._curRotSpeed;

        // ── Camera orbit ──
        this._camOrbitAngle += this._camOrbitSpeed * dt;
        const cx = Math.sin(this._camOrbitAngle) * this._camOrbitRadius;
        const cz = Math.cos(this._camOrbitAngle) * this._camOrbitRadius;
        const cb = Math.sin(t * this._camBreatheSpeed) * this._camBreatheAmp;
        this.camera.position.set(cx, this._camOrbitTilt + cb, cz);
        this.camera.lookAt(0, 0, 0);

        // ── Outer housing: very slow rotation ──
        if (this.outerHousing) {
            this.outerHousing.rotation.z += 0.015 * RS * dt;
        }

        // ── Concentric rings: each at its own speed ──
        for (const ring of this.concentricRings) {
            ring.mesh.rotation.z += ring.speed * RS * dt;
        }

        // ── Inner ring ──
        if (this.innerRing) {
            this.innerRing.rotation.z += 0.35 * RS * dt;
        }

        // ── Energy rings ──
        if (this.energyRing) {
            this.energyRing.rotation.z += 0.45 * RS * dt;
            this.matAmber.emissiveIntensity = 0.3 + Math.sin(t * 2.0) * 0.25 * E + (E - 1) * 0.4;
        }
        if (this.energyRing2) {
            this.energyRing2.rotation.z -= 0.55 * RS * dt;
        }

        // ── Wireframe icosahedron ──
        if (this.innerIco) {
            this.innerIco.rotation.x += 0.2 * RS * dt;
            this.innerIco.rotation.y += 0.15 * RS * dt;
        }

        // ── Core breathing ──
        if (this.coreMesh) {
            const cs = 1.0 + Math.sin(t * 2.2) * 0.05 * E;
            this.coreMesh.scale.setScalar(cs);
            this.matCore.emissiveIntensity = 2.5 + Math.sin(t * 2.5) * 0.4 * E + (E - 1) * 0.8;
        }
        if (this.coreGlow1) {
            const gs1 = 1.0 + Math.sin(t * 1.8) * 0.08 * E;
            this.coreGlow1.scale.setScalar(gs1);
            this.coreGlow1.material.opacity = 0.15 + Math.sin(t * 2.0) * 0.08 * E;
        }
        if (this.coreGlow2) {
            const gs2 = 1.0 + Math.sin(t * 1.2) * 0.06 * E;
            this.coreGlow2.scale.setScalar(gs2);
            this.coreGlow2.material.opacity = 0.06 + Math.sin(t * 1.5) * 0.04 * E;
        }

        // ── Core lights ──
        if (this.coreLight) {
            this.coreLight.intensity = 2.5 + Math.sin(t * 2.5) * 0.5 * E + (E - 1) * 0.8;
        }
        if (this.coreLight2) {
            this.coreLight2.intensity = 1.2 + Math.sin(t * 3.0) * 0.3 * E;
        }

        // ── Nodes pulsing ──
        for (let i = 0; i < this.nodeMeshes.length; i++) {
            const n = this.nodeMeshes[i];
            const phase = i * 0.7;
            n.material.opacity = 0.3 + Math.sin(t * 1.5 + phase) * 0.25 * E;
            const ns = 1.0 + Math.sin(t * 2.0 + phase) * 0.15 * E;
            n.scale.setScalar(ns);
        }

        // ── Network lines subtle pulse ──
        if (this.networkLines) {
            this.networkLines.children.forEach((child, i) => {
                if (child.material) {
                    child.material.opacity = 0.15 + Math.sin(t * 0.8 + i * 0.3) * 0.08 * E;
                }
            });
        }

        // ── Glass dome ──
        if (this.glassDome) {
            this.glassDome.material.opacity = 0.02 + Math.sin(t * 0.6) * 0.01;
        }

        this.renderer.render(this.scene, this.camera);
    }
}

window.ULTRONAvatar = ULTRONAvatar;
