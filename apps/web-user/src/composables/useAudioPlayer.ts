/**
 * TTS Audio Player — Web Audio API based playback with lip sync support.
 *
 * Receives opus audio chunks from /ws/voice, decodes and plays them
 * sequentially, and emits amplitude data for Live2D mouth movement.
 */
import { ref, type Ref } from 'vue'

export interface AudioPlayerCallbacks {
  /** Current audio amplitude (0-1) for lip sync */
  onAmplitude?: (value: number) => void
  /** Playback started */
  onPlayStart?: () => void
  /** Playback finished (queue empty) */
  onPlayEnd?: () => void
}

export function useAudioPlayer() {
  const isPlaying: Ref<boolean> = ref(false)
  const isSupported: Ref<boolean> = ref(true)

  let audioContext: AudioContext | null = null
  let analyser: AnalyserNode | null = null
  let animationFrameId: number | null = null
  let audioQueue: ArrayBuffer[] = []
  let isProcessing = false
  let callbacks: AudioPlayerCallbacks = {}
  const SAMPLE_RATE = 24000

  function getContext(): AudioContext | null {
    if (audioContext && audioContext.state !== 'closed') {
      return audioContext
    }
    try {
      audioContext = new AudioContext({ sampleRate: SAMPLE_RATE })
      analyser = audioContext.createAnalyser()
      analyser.fftSize = 256
      analyser.smoothingTimeConstant = 0.3
      analyser.connect(audioContext.destination)
      return audioContext
    } catch (err) {
      console.warn('[AudioPlayer] Web Audio API not supported:', err)
      isSupported.value = false
      return null
    }
  }

  function enqueue(chunk: ArrayBuffer) {
    audioQueue.push(chunk)
    if (!isProcessing) {
      processQueue()
    }
  }

  async function processQueue() {
    if (isProcessing || audioQueue.length === 0) return
    isProcessing = true
    isPlaying.value = true
    callbacks.onPlayStart?.()
    startAmplitudeLoop()

    const ctx = getContext()
    if (!ctx) {
      // Browser doesn't support Web Audio — skip playback gracefully
      audioQueue = []
      isProcessing = false
      isPlaying.value = false
      stopAmplitudeLoop()
      callbacks.onPlayEnd?.()
      return
    }

    while (audioQueue.length > 0) {
      const chunk = audioQueue.shift()!
      try {
        // Decode the opus audio chunk
        const audioBuffer = await ctx.decodeAudioData(chunk.slice(0))

        // Play the decoded buffer
        const source = ctx.createBufferSource()
        source.buffer = audioBuffer

        if (analyser) {
          source.connect(analyser)
        } else {
          source.connect(ctx.destination)
        }

        // Wait for playback to finish before playing next chunk
        await new Promise<void>((resolve) => {
          source.onended = () => resolve()
          source.start(0)
        })
      } catch (err) {
        // Silently skip failed chunks (mock TTS data won't decode as real opus)
        console.debug('[AudioPlayer] Failed to decode chunk (expected with mock data):', err)
      }
    }

    isProcessing = false
    isPlaying.value = false
    stopAmplitudeLoop()
    callbacks.onPlayEnd?.()
  }

  /** Start amplitude analysis loop for lip sync */
  function startAmplitudeLoop() {
    if (animationFrameId) return

    function loop() {
      if (!analyser || !isPlaying.value) return

      const dataArray = new Uint8Array(analyser.frequencyBinCount)
      analyser.getByteFrequencyData(dataArray)

      // Calculate average amplitude (0-1)
      const avg = dataArray.reduce((a, b) => a + b, 0) / dataArray.length / 255
      callbacks.onAmplitude?.(avg)

      animationFrameId = requestAnimationFrame(loop)
    }

    animationFrameId = requestAnimationFrame(loop)
  }

  /** Stop amplitude analysis */
  function stopAmplitudeLoop() {
    if (animationFrameId) {
      cancelAnimationFrame(animationFrameId)
      animationFrameId = null
    }
    // Reset mouth
    callbacks.onAmplitude?.(0)
  }

  /** Stop all playback and clear queue */
  function stop() {
    audioQueue = []
    isProcessing = false
    isPlaying.value = false
    stopAmplitudeLoop()
    if (audioContext && audioContext.state !== 'closed') {
      audioContext.close().catch(() => {})
      audioContext = null
      analyser = null
    }
  }

  function setCallbacks(cbs: AudioPlayerCallbacks) {
    callbacks = cbs
  }

  return {
    isPlaying,
    isSupported,
    enqueue,
    stop,
    setCallbacks,
  }
}
