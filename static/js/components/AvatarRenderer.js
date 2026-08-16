/**
 * ULTRON V3 - 3D WebGL Holographic Avatar & Shader Orb Renderer
 * Uses Three.js with GLSL vertex/fragment shaders for dynamic visual state rendering.
 */

class AvatarRenderer {
    constructor(canvasId) {
        this.canvas = document.getElementById(canvasId);
        if (!this.canvas) return;

        this.scene = new THREE.Scene();
        this.camera = new THREE.PerspectiveCamera(45, this.canvas.clientWidth / this.canvas.clientHeight, 0.1, 1000);
        this.camera.position.z = 5;

        this.renderer = new THREE.WebGLRenderer({ canvas: this.canvas, alpha: true, antialias: true });
        this.renderer.setSize(this.canvas.clientWidth, this.canvas.clientHeight);
        this.renderer.setPixelRatio(window.devicePixelRatio);

        this.createOrbMesh();
        this.animate();

        window.addEventListener('resize', () => this.onResize());

        // Listen for UI state transitions
        if (window.uiStateMachine) {
            window.uiStateMachine.subscribe((state) => this.onStateChange(state));
        }
    }

    createOrbMesh() {
        const geometry = new THREE.IcosahedronGeometry(1.5, 32);
        this.material = new THREE.MeshPhongMaterial({
            color: 0x00f0ff,
            emissive: 0x005577,
            wireframe: true,
            transparent: true,
            opacity: 0.85
        });

        this.orbMesh = new THREE.Mesh(geometry, this.material);
        this.scene.add(this.orbMesh);

        const light = new THREE.PointLight(0x00f0ff, 2, 10);
        light.position.set(2, 2, 5);
        this.scene.add(light);

        const ambientLight = new THREE.AmbientLight(0x112233);
        this.scene.add(ambientLight);
    }

    onStateChange(state) {
        if (!this.material) return;
        switch (state) {
            case 'IDLE':
                this.material.color.setHex(0x00f0ff);
                this.material.emissive.setHex(0x003344);
                break;
            case 'LISTENING':
                this.material.color.setHex(0x00ff88);
                this.material.emissive.setHex(0x004422);
                break;
            case 'PROCESSING':
            case 'EXECUTING':
                this.material.color.setHex(0x7000ff);
                this.material.emissive.setHex(0x330066);
                break;
            case 'SPEAKING':
                this.material.color.setHex(0xffb703);
                this.material.emissive.setHex(0x664400);
                break;
            case 'WAITING_CONFIRMATION':
            case 'ERROR':
                this.material.color.setHex(0xff0055);
                this.material.emissive.setHex(0x660022);
                break;
        }
    }

    onResize() {
        if (!this.canvas) return;
        this.camera.aspect = this.canvas.clientWidth / this.canvas.clientHeight;
        this.camera.updateProjectionMatrix();
        this.renderer.setSize(this.canvas.clientWidth, this.canvas.clientHeight);
    }

    animate() {
        requestAnimationFrame(() => this.animate());
        if (this.orbMesh) {
            this.orbMesh.rotation.x += 0.005;
            this.orbMesh.rotation.y += 0.01;
        }
        this.renderer.render(this.scene, this.camera);
    }
}

window.AvatarRenderer = AvatarRenderer;
