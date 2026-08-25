/**
 * ULTRON V3 — Premium Cinematic Humanoid Avatar
 * Three.js robotic AI visual with metallic materials, energy core,
 * glowing eyes, armor plates, holographic rings, and state-reactive lighting.
 */

class ULTRONAvatar {
    constructor(canvasId) {
        this.canvas = document.getElementById(canvasId);
        if (!this.canvas) return;

        this.container = this.canvas.parentElement;
        this.clock = new THREE.Clock();
        this.stateMaterials = [];
        this.glowMaterials = [];
        this.energyPulse = 0;
        this.breathPhase = 0;
        this.ringRotation = 0;

        this._initScene();
        this._buildRobot();
        this._addLighting();
        this._addEffects();
        this._resize();
        this._animate();

        window.addEventListener('resize', () => this._resize());

        if (window.uiStateMachine) {
            window.uiStateMachine.subscribe((s) => this._onState(s));
        }
    }

    /* ── Scene Setup ── */
    _initScene() {
        this.scene = new THREE.Scene();
        this.camera = new THREE.PerspectiveCamera(38, this._aspect(), 0.1, 100);
        this.camera.position.set(0, 1.2, 6.5);
        this.camera.lookAt(0, 0.8, 0);

        this.renderer = new THREE.WebGLRenderer({
            canvas: this.canvas,
            alpha: true,
            antialias: true,
        });
        this.renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2));
        this.renderer.toneMapping = THREE.ACESFilmicToneMapping;
        this.renderer.toneMappingExposure = 1.1;
        this.renderer.outputEncoding = THREE.sRGBEncoding;

        this.scene.fog = new THREE.FogExp2(0x040506, 0.08);
    }

    _aspect() {
        if (!this.container) return 1;
        return this.container.clientWidth / Math.max(this.container.clientHeight, 1);
    }

    /* ── Build Robot ── */
    _buildRobot() {
        this.robot = new THREE.Group();

        const bodyMat = this._metalMat(0x22252a, 0.55);
        const armorMat = this._metalMat(0x2e3036, 0.7);
        const darkMat = this._metalMat(0x14151a, 0.8);
        const jointMat = this._metalMat(0x1a1c22, 0.4);

        this._buildHead(bodyMat, darkMat);
        this._buildNeck(jointMat);
        this._buildTorso(bodyMat, armorMat);
        this._buildShoulders(armorMat);
        this._buildArms(jointMat, bodyMat);
        this._buildEnergyCore();
        this._buildWaist(darkMat);

        this.robot.position.y = -0.3;
        this.scene.add(this.robot);
    }

    _metalMat(color, metalness) {
        return new THREE.MeshStandardMaterial({
            color,
            metalness,
            roughness: 0.35 - metalness * 0.15,
            envMapIntensity: 0.8,
        });
    }

    /* ── HEAD ── */
    _buildHead(bodyMat, darkMat) {
        const head = new THREE.Group();

        // Skull shell — elongated box with bevels
        const skullGeo = new THREE.BoxGeometry(0.56, 0.52, 0.52);
        const skull = new THREE.Mesh(skullGeo, bodyMat);
        skull.position.y = 0;
        head.add(skull);

        // Top crest
        const crestGeo = new THREE.BoxGeometry(0.3, 0.08, 0.4);
        const crest = new THREE.Mesh(crestGeo, armorMat(0x2a2d32, 0.65));
        crest.position.set(0, 0.28, 0);
        head.add(crest);

        function armorMat(c, m) {
            return new THREE.MeshStandardMaterial({ color: c, metalness: m, roughness: 0.3 });
        }

        // Face plate — dark visor area
        const faceGeo = new THREE.BoxGeometry(0.48, 0.28, 0.08);
        const face = new THREE.Mesh(faceGeo, darkMat);
        face.position.set(0, -0.04, 0.24);
        head.add(face);

        // Eyes — glowing amber
        const eyeMat = new THREE.MeshStandardMaterial({
            color: 0xd4a843,
            emissive: 0xd4a843,
            emissiveIntensity: 1.8,
            metalness: 0.2,
            roughness: 0.1,
        });
        this.stateMaterials.push(eyeMat);

        const eyeGeo = new THREE.BoxGeometry(0.1, 0.035, 0.02);

        const eyeL = new THREE.Mesh(eyeGeo, eyeMat);
        eyeL.position.set(-0.12, 0.0, 0.29);
        head.add(eyeL);

        const eyeR = new THREE.Mesh(eyeGeo, eyeMat);
        eyeR.position.set(0.12, 0.0, 0.29);
        head.add(eyeR);

        this.eyeL = eyeL;
        this.eyeR = eyeR;
        this.eyeMat = eyeMat;

        // Brow ridges
        const browGeo = new THREE.BoxGeometry(0.14, 0.025, 0.04);
        const browMat = new THREE.MeshStandardMaterial({ color: 0x3a3d44, metalness: 0.6, roughness: 0.3 });

        const browL = new THREE.Mesh(browGeo, browMat);
        browL.position.set(-0.12, 0.045, 0.28);
        browL.rotation.z = 0.1;
        head.add(browL);

        const browR = new THREE.Mesh(browGeo, browMat);
        browR.position.set(0.12, 0.045, 0.28);
        browR.rotation.z = -0.1;
        head.add(browR);

        // Chin detail
        const chinGeo = new THREE.BoxGeometry(0.2, 0.04, 0.06);
        const chin = new THREE.Mesh(chinGeo, bodyMat);
        chin.position.set(0, -0.26, 0.2);
        head.add(chin);

        // Side vents
        const ventGeo = new THREE.BoxGeometry(0.03, 0.12, 0.25);
        const ventMat = new THREE.MeshStandardMaterial({ color: 0x1a1c22, metalness: 0.5, roughness: 0.4 });

        const ventL = new THREE.Mesh(ventGeo, ventMat);
        ventL.position.set(-0.3, -0.02, 0);
        head.add(ventL);

        const ventR = new THREE.Mesh(ventGeo, ventMat);
        ventR.position.set(0.3, -0.02, 0);
        head.add(ventR);

        head.position.y = 2.55;
        this.head = head;
        this.robot.add(head);
    }

    /* ── NECK ── */
    _buildNeck(jointMat) {
        const neckGeo = new THREE.CylinderGeometry(0.1, 0.12, 0.18, 8);
        const neck = new THREE.Mesh(neckGeo, jointMat);
        neck.position.y = 2.2;
        this.robot.add(neck);

        // Neck ring
        const ringGeo = new THREE.TorusGeometry(0.13, 0.015, 8, 16);
        const ringMat = new THREE.MeshStandardMaterial({ color: 0xd4a843, emissive: 0xd4a843, emissiveIntensity: 0.3, metalness: 0.8, roughness: 0.2 });
        const ring = new THREE.Mesh(ringGeo, ringMat);
        ring.position.y = 2.15;
        ring.rotation.x = Math.PI / 2;
        this.robot.add(ring);
    }

    /* ── TORSO ── */
    _buildTorso(bodyMat, armorMat) {
        const torsoGroup = new THREE.Group();

        // Main chest
        const chestGeo = new THREE.BoxGeometry(0.9, 1.0, 0.55);
        const chest = new THREE.Mesh(chestGeo, bodyMat);
        chest.position.y = 1.55;
        torsoGroup.add(chest);

        // Chest armor plates (angled)
        const plateGeo = new THREE.BoxGeometry(0.35, 0.4, 0.08);

        const plateL = new THREE.Mesh(plateGeo, armorMat);
        plateL.position.set(-0.22, 1.7, 0.28);
        plateL.rotation.z = 0.08;
        plateL.rotation.x = -0.05;
        torsoGroup.add(plateL);

        const plateR = new THREE.Mesh(plateGeo, armorMat);
        plateR.position.set(0.22, 1.7, 0.28);
        plateR.rotation.z = -0.08;
        plateR.rotation.x = -0.05;
        torsoGroup.add(plateR);

        // Center chest ridge
        const ridgeGeo = new THREE.BoxGeometry(0.06, 0.8, 0.12);
        const ridgeMat = new THREE.MeshStandardMaterial({ color: 0x3a3d44, metalness: 0.6, roughness: 0.3 });
        const ridge = new THREE.Mesh(ridgeGeo, ridgeMat);
        ridge.position.set(0, 1.55, 0.3);
        torsoGroup.add(ridge);

        // Side panels
        const sideGeo = new THREE.BoxGeometry(0.06, 0.9, 0.45);
        const sideL = new THREE.Mesh(sideGeo, new THREE.MeshStandardMaterial({ color: 0x1a1c22, metalness: 0.4, roughness: 0.5 }));
        sideL.position.set(-0.48, 1.55, 0);
        torsoGroup.add(sideL);

        const sideR = sideL.clone();
        sideR.position.set(0.48, 1.55, 0);
        torsoGroup.add(sideR);

        // Abdominal segments
        for (let i = 0; i < 3; i++) {
            const segGeo = new THREE.BoxGeometry(0.7 - i * 0.04, 0.06, 0.4);
            const seg = new THREE.Mesh(segGeo, new THREE.MeshStandardMaterial({ color: 0x1e2028, metalness: 0.5, roughness: 0.4 }));
            seg.position.set(0, 1.08 - i * 0.1, 0.02);
            torsoGroup.add(seg);
        }

        this.torsoGroup = torsoGroup;
        this.robot.add(torsoGroup);
    }

    /* ── SHOULDERS ── */
    _buildShoulders(armorMat) {
        const shoulderGeo = new THREE.BoxGeometry(0.28, 0.22, 0.32);

        const shoulderL = new THREE.Mesh(shoulderGeo, armorMat);
        shoulderL.position.set(-0.62, 1.98, 0);
        this.robot.add(shoulderL);

        const shoulderR = new THREE.Mesh(shoulderGeo, armorMat);
        shoulderR.position.set(0.62, 1.98, 0);
        this.robot.add(shoulderR);

        // Shoulder accent rings
        const ringGeo = new THREE.TorusGeometry(0.16, 0.015, 8, 16);
        const ringMat = new THREE.MeshStandardMaterial({
            color: 0xd4a843,
            emissive: 0xd4a843,
            emissiveIntensity: 0.25,
            metalness: 0.8,
            roughness: 0.2,
        });

        const ringL = new THREE.Mesh(ringGeo, ringMat);
        ringL.position.set(-0.62, 1.98, 0.17);
        this.robot.add(ringL);

        const ringR = new THREE.Mesh(ringGeo, ringMat);
        ringR.position.set(0.62, 1.98, 0.17);
        this.robot.add(ringR);

        this.shoulderRingL = ringL;
        this.shoulderRingR = ringR;
    }

    /* ── ARMS ── */
    _buildArms(jointMat, bodyMat) {
        const buildArm = (side) => {
            const x = side === 'L' ? -0.62 : 0.62;
            const arm = new THREE.Group();

            // Upper arm
            const upperGeo = new THREE.CylinderGeometry(0.08, 0.07, 0.5, 8);
            const upper = new THREE.Mesh(upperGeo, bodyMat);
            upper.position.y = -0.3;
            arm.add(upper);

            // Elbow joint
            const elbowGeo = new THREE.SphereGeometry(0.07, 8, 8);
            const elbow = new THREE.Mesh(elbowGeo, jointMat);
            elbow.position.y = -0.55;
            arm.add(elbow);

            // Forearm
            const foreGeo = new THREE.CylinderGeometry(0.065, 0.055, 0.45, 8);
            const fore = new THREE.Mesh(foreGeo, bodyMat);
            fore.position.y = -0.8;
            arm.add(fore);

            // Hand
            const handGeo = new THREE.BoxGeometry(0.1, 0.12, 0.08);
            const hand = new THREE.Mesh(handGeo, jointMat);
            hand.position.y = -1.08;
            arm.add(hand);

            // Arm accent line
            const lineGeo = new THREE.BoxGeometry(0.02, 0.4, 0.02);
            const lineMat = new THREE.MeshStandardMaterial({ color: 0xd4a843, emissive: 0xd4a843, emissiveIntensity: 0.15 });
            const line = new THREE.Mesh(lineGeo, lineMat);
            line.position.set(side === 'L' ? 0.05 : -0.05, -0.3, 0.07);
            arm.add(line);

            arm.position.set(x, 1.85, 0);
            return arm;
        };

        this.robot.add(buildArm('L'));
        this.robot.add(buildArm('R'));
    }

    /* ── ENERGY CORE ── */
    _buildEnergyCore() {
        const coreGroup = new THREE.Group();

        // Outer ring
        const outerRingGeo = new THREE.TorusGeometry(0.14, 0.02, 12, 24);
        const outerRingMat = new THREE.MeshStandardMaterial({
            color: 0xd4a843,
            emissive: 0xd4a843,
            emissiveIntensity: 0.6,
            metalness: 0.9,
            roughness: 0.1,
        });
        const outerRing = new THREE.Mesh(outerRingGeo, outerRingMat);
        outerRing.rotation.x = Math.PI / 2;
        coreGroup.add(outerRing);
        this.outerCoreRing = outerRing;

        // Inner ring
        const innerRingGeo = new THREE.TorusGeometry(0.08, 0.012, 8, 16);
        const innerRingMat = new THREE.MeshStandardMaterial({
            color: 0xf5c842,
            emissive: 0xf5c842,
            emissiveIntensity: 0.8,
            metalness: 0.8,
            roughness: 0.15,
        });
        const innerRing = new THREE.Mesh(innerRingGeo, innerRingMat);
        innerRing.rotation.x = Math.PI / 2;
        coreGroup.add(innerRing);
        this.innerCoreRing = innerRing;

        // Core sphere (emissive)
        const coreGeo = new THREE.SphereGeometry(0.06, 16, 16);
        const coreMat = new THREE.MeshStandardMaterial({
            color: 0xf5c842,
            emissive: 0xf5c842,
            emissiveIntensity: 1.2,
            metalness: 0.3,
            roughness: 0.1,
            transparent: true,
            opacity: 0.9,
        });
        const core = new THREE.Mesh(coreGeo, coreMat);
        coreGroup.add(core);
        this.coreMat = coreMat;

        coreGroup.position.set(0, 1.55, 0.35);
        this.coreGroup = coreGroup;
        this.robot.add(coreGroup);

        // Point light from core
        this.coreLight = new THREE.PointLight(0xd4a843, 1.5, 4);
        this.coreLight.position.copy(coreGroup.position);
        this.robot.add(this.coreLight);
    }

    /* ── WAIST ── */
    _buildWaist(darkMat) {
        const waistGeo = new THREE.BoxGeometry(0.65, 0.12, 0.4);
        const waist = new THREE.Mesh(waistGeo, darkMat);
        waist.position.y = 0.95;
        this.robot.add(waist);

        // Belt accent
        const beltGeo = new THREE.BoxGeometry(0.66, 0.03, 0.42);
        const beltMat = new THREE.MeshStandardMaterial({ color: 0xd4a843, metalness: 0.8, roughness: 0.2 });
        const belt = new THREE.Mesh(beltGeo, beltMat);
        belt.position.y = 0.93;
        this.robot.add(belt);
    }

    /* ── Lighting ── */
    _addLighting() {
        // Key light — warm gold from above-right
        const keyLight = new THREE.DirectionalLight(0xd4a843, 1.2);
        keyLight.position.set(3, 5, 4);
        this.scene.add(keyLight);

        // Fill light — cool steel from left
        const fillLight = new THREE.DirectionalLight(0x667788, 0.4);
        fillLight.position.set(-3, 2, 2);
        this.scene.add(fillLight);

        // Rim light — from behind
        const rimLight = new THREE.DirectionalLight(0xd4a843, 0.6);
        rimLight.position.set(0, 3, -4);
        this.scene.add(rimLight);

        // Ambient
        const ambient = new THREE.AmbientLight(0x111318, 0.6);
        this.scene.add(ambient);

        // Hemisphere
        const hemi = new THREE.HemisphereLight(0x22252a, 0x08090b, 0.4);
        this.scene.add(hemi);
    }

    /* ── Effects ── */
    _addEffects() {
        // Holographic rings around robot
        this.holoRings = [];
        const ringConfigs = [
            { radius: 1.2, y: 1.5, speed: 0.3, opacity: 0.12 },
            { radius: 1.5, y: 1.0, speed: -0.2, opacity: 0.08 },
            { radius: 0.9, y: 2.0, speed: 0.4, opacity: 0.1 },
        ];

        for (const cfg of ringConfigs) {
            const geo = new THREE.TorusGeometry(cfg.radius, 0.005, 4, 64);
            const mat = new THREE.MeshBasicMaterial({
                color: 0xd4a843,
                transparent: true,
                opacity: cfg.opacity,
            });
            const ring = new THREE.Mesh(geo, mat);
            ring.position.y = cfg.y;
            ring.rotation.x = Math.PI / 2 + 0.3;
            ring.userData = { speed: cfg.speed };
            this.scene.add(ring);
            this.holoRings.push(ring);
        }

        // Floating particle dots
        this.particles = [];
        const particleGeo = new THREE.SphereGeometry(0.015, 6, 6);
        const particleMat = new THREE.MeshBasicMaterial({ color: 0xd4a843, transparent: true, opacity: 0.4 });

        for (let i = 0; i < 20; i++) {
            const p = new THREE.Mesh(particleGeo, particleMat.clone());
            const angle = (i / 20) * Math.PI * 2;
            const radius = 1.0 + Math.random() * 0.8;
            p.position.set(
                Math.cos(angle) * radius,
                0.5 + Math.random() * 2.5,
                Math.sin(angle) * radius,
            );
            p.userData = {
                angle,
                radius,
                speed: 0.1 + Math.random() * 0.3,
                yBase: p.position.y,
                yAmp: 0.05 + Math.random() * 0.1,
            };
            this.scene.add(p);
            this.particles.push(p);
        }
    }

    /* ── State Handling ── */
    _onState(state) {
        const label = document.getElementById('avatarStateLabel');
        const map = {
            IDLE:                 { color: 0xd4a843, emissive: 0x8b7230, label: 'STANDBY', intensity: 1.5 },
            LISTENING:            { color: 0x33aa55, emissive: 0x1a6630, label: 'LISTENING', intensity: 1.8 },
            THINKING:             { color: 0xe8a020, emissive: 0x8b5010, label: 'THINKING', intensity: 2.0 },
            PROCESSING:           { color: 0xe8a020, emissive: 0x8b5010, label: 'PROCESSING', intensity: 2.0 },
            SPEAKING:             { color: 0xf5c842, emissive: 0xaa8020, label: 'SPEAKING', intensity: 2.5 },
            EXECUTING:            { color: 0xd4a843, emissive: 0x8b7230, label: 'EXECUTING', intensity: 2.0 },
            WAITING_CONFIRMATION: { color: 0xcc3333, emissive: 0x881a1a, label: 'CONFIRM', intensity: 2.2 },
            SUCCESS:              { color: 0x33aa55, emissive: 0x1a6630, label: 'SUCCESS', intensity: 2.0 },
            ERROR:                { color: 0xcc3333, emissive: 0x881a1a, label: 'ERROR', intensity: 2.5 },
            OFFLINE:              { color: 0x555555, emissive: 0x222222, label: 'OFFLINE', intensity: 0.3 },
        };

        const cfg = map[state] || map.IDLE;

        // Update eye material
        this.eyeMat.color.setHex(cfg.color);
        this.eyeMat.emissive.setHex(cfg.emissive);
        this.eyeMat.emissiveIntensity = cfg.intensity;

        // Update core
        this.coreMat.color.setHex(cfg.color);
        this.coreMat.emissive.setHex(cfg.emissive);
        this.coreMat.emissiveIntensity = cfg.intensity * 0.8;

        // Update core light
        if (this.coreLight) {
            this.coreLight.color.setHex(cfg.color);
            this.coreLight.intensity = cfg.intensity * 0.8;
        }

        // Update label
        if (label) label.textContent = cfg.label;
    }

    /* ── Resize ── */
    _resize() {
        if (!this.container || !this.renderer) return;
        const w = this.container.clientWidth;
        const h = this.container.clientHeight;
        if (w === 0 || h === 0) return;
        this.camera.aspect = w / h;
        this.camera.updateProjectionMatrix();
        this.renderer.setSize(w, h);
    }

    /* ── Animation Loop ── */
    _animate() {
        requestAnimationFrame(() => this._animate());
        const dt = this.clock.getDelta();
        const elapsed = this.clock.getElapsedTime();

        // Gentle robot sway
        if (this.robot) {
            this.robot.rotation.y = Math.sin(elapsed * 0.3) * 0.04;
            this.robot.position.y = -0.3 + Math.sin(elapsed * 0.5) * 0.02;
        }

        // Head subtle movement
        if (this.head) {
            this.head.rotation.y = Math.sin(elapsed * 0.7) * 0.03;
            this.head.rotation.x = Math.sin(elapsed * 0.4) * 0.015;
        }

        // Energy core pulse
        this.energyPulse = (Math.sin(elapsed * 2.5) + 1) * 0.5;
        if (this.coreMat) {
            this.coreMat.emissiveIntensity = 0.8 + this.energyPulse * 0.8;
        }
        if (this.coreLight) {
            this.coreLight.intensity = 1.0 + this.energyPulse * 0.8;
        }

        // Core rings rotation
        if (this.outerCoreRing) {
            this.outerCoreRing.rotation.z = elapsed * 0.5;
        }
        if (this.innerCoreRing) {
            this.innerCoreRing.rotation.z = -elapsed * 0.8;
        }

        // Holographic rings
        for (const ring of this.holoRings) {
            ring.rotation.z += ring.userData.speed * dt;
            ring.material.opacity = 0.06 + Math.sin(elapsed * 0.8 + ring.userData.speed * 10) * 0.04;
        }

        // Floating particles
        for (const p of this.particles) {
            const d = p.userData;
            d.angle += d.speed * dt;
            p.position.x = Math.cos(d.angle) * d.radius;
            p.position.z = Math.sin(d.angle) * d.radius;
            p.position.y = d.yBase + Math.sin(elapsed * d.speed * 2) * d.yAmp;
            p.material.opacity = 0.2 + Math.sin(elapsed * 1.5 + d.angle) * 0.2;
        }

        this.renderer.render(this.scene, this.camera);
    }
}

window.ULTRONAvatar = ULTRONAvatar;
