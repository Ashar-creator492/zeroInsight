import { useEffect, useRef } from 'react'
import * as THREE from 'three'
import { GLTFLoader } from 'three/examples/jsm/loaders/GLTFLoader.js'

export default function WatchDisplay() {
  const host = useRef<HTMLDivElement>(null)
  useEffect(() => {
    const el = host.current
    if (!el) return
    let renderer: THREE.WebGLRenderer
    try { renderer = new THREE.WebGLRenderer({ alpha: true, antialias: true }) } catch { return }
    renderer.setPixelRatio(Math.min(window.devicePixelRatio, 1.5))
    renderer.outputColorSpace = THREE.SRGBColorSpace
    renderer.toneMapping = THREE.ACESFilmicToneMapping
    el.appendChild(renderer.domElement)
    const scene = new THREE.Scene(), camera = new THREE.PerspectiveCamera(30, 1, .01, 100)
    camera.position.z = 6
    scene.add(new THREE.HemisphereLight(0xffffff, 0x47383b, 2.1))
    const key = new THREE.DirectionalLight(0xfff3e9, 3); key.position.set(-3, 5, 6); scene.add(key)
    const rim = new THREE.DirectionalLight(0xe01818, 2); rim.position.set(4, 0, -2); scene.add(rim)
    const fill = new THREE.DirectionalLight(0xffffff, 1.4); fill.position.set(4, 2, 4); scene.add(fill)
    const watch = new THREE.Group(); scene.add(watch)
    let disposed = false
    new GLTFLoader().load('/models/lunawatch.glb', gltf => {
      if (disposed) return
      const bounds = new THREE.Box3().setFromObject(gltf.scene)
      const size = bounds.getSize(new THREE.Vector3()), center = bounds.getCenter(new THREE.Vector3())
      gltf.scene.position.copy(center).multiplyScalar(-1)
      const scaled = new THREE.Group(); scaled.scale.setScalar(2.1 / Math.max(size.x, size.y, size.z)); scaled.add(gltf.scene); watch.add(scaled)
    }, undefined, () => { el.dataset.failed = 'true' })
    const resize = () => { const { width, height } = el.getBoundingClientRect(); if (!width || !height) return; camera.aspect = width / height; camera.updateProjectionMatrix(); renderer.setSize(width, height, false) }
    const observer = new ResizeObserver(resize); observer.observe(el); resize()
    const motion = window.matchMedia('(prefers-reduced-motion: reduce)')
    let frame = 0
    const draw = (ms: number) => { const t = ms / 1000; if (!motion.matches) { watch.rotation.y = t * Math.PI * 2 / 26; watch.position.y = Math.sin(t * Math.PI * 2 / 5) * .09 } renderer.render(scene, camera); frame = requestAnimationFrame(draw) }
    frame = requestAnimationFrame(draw)
    return () => { disposed = true; cancelAnimationFrame(frame); observer.disconnect(); scene.traverse(o => { if (o instanceof THREE.Mesh) { o.geometry.dispose(); (Array.isArray(o.material) ? o.material : [o.material]).forEach(m => { if (m instanceof THREE.MeshStandardMaterial) m.map?.dispose(); m.dispose() }) } }); renderer.dispose(); renderer.domElement.remove() }
  }, [])
  return <div className="watch-display" ref={host} role="img" aria-label="Animated Luna watch model" />
}
