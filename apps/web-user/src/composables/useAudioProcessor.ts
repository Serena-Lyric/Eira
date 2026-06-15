/**
 * WebM/Opus → 16kHz 16-bit mono PCM converter.
 *
 * Xunfei IAT requires: 16kHz sample rate, 16-bit, mono, raw PCM.
 * Browsers produce WebM/Opus via MediaRecorder — we decode and resample here.
 */
export interface PcmResult {
  /** Int16 PCM samples as a raw byte buffer. */
  buffer: ArrayBuffer
  /** Sample rate of the output (always 16000). */
  sampleRate: 16000
}

/**
 * Convert a WebM audio blob to 16kHz 16-bit mono PCM.
 *
 * Uses Web Audio API (AudioContext + OfflineAudioContext) for decoding and
 * resampling — no external dependencies.
 */
export async function convertWebMToPcm(blob: Blob): Promise<PcmResult> {
  const arrayBuffer = await blob.arrayBuffer()

  // Decode the WebM/Opus audio
  const audioCtx = new AudioContext()
  let audioBuffer: AudioBuffer
  try {
    audioBuffer = await audioCtx.decodeAudioData(arrayBuffer)
  } finally {
    audioCtx.close()
  }

  const sourceSampleRate = audioBuffer.sampleRate
  const sourceLength = audioBuffer.length
  const channels = audioBuffer.numberOfChannels

  // Extract mono: average all channels, or take first channel
  const mono = new Float32Array(sourceLength)
  if (channels === 1) {
    audioBuffer.copyFromChannel(mono, 0)
  } else {
    // Mix down to mono
    const temp = new Float32Array(sourceLength)
    for (let c = 0; c < channels; c++) {
      audioBuffer.copyFromChannel(temp, c)
      for (let i = 0; i < sourceLength; i++) {
        mono[i] += temp[i]
      }
    }
    for (let i = 0; i < sourceLength; i++) {
      mono[i] /= channels
    }
  }

  // Resample to 16kHz if needed
  const TARGET_RATE = 16000
  let samples: Float32Array
  if (sourceSampleRate === TARGET_RATE) {
    samples = mono
  } else {
    samples = await resample(mono, sourceSampleRate, TARGET_RATE)
  }

  // Convert Float32 → Int16 PCM
  const pcmLength = samples.length
  const pcmBuffer = new ArrayBuffer(pcmLength * 2) // 2 bytes per Int16
  const pcmView = new DataView(pcmBuffer)

  let maxAbs = 0
  for (let i = 0; i < pcmLength; i++) {
    // Clamp to [-1, 1] and convert to Int16
    const clamped = Math.max(-1, Math.min(1, samples[i]))
    const int16 = clamped < 0 ? clamped * 0x8000 : clamped * 0x7FFF
    maxAbs = Math.max(maxAbs, Math.abs(int16))
    pcmView.setInt16(i * 2, int16, true) // little-endian
  }

  // Diagnostic: check audio health
  const durationSec = pcmLength / TARGET_RATE
  const dbFS = 20 * Math.log10(maxAbs / 32767)
  console.log(
    `[AudioProcessor] Source: ${sourceSampleRate}Hz ${channels}ch ${(sourceLength / sourceSampleRate).toFixed(1)}s`,
    `→ PCM: ${TARGET_RATE}Hz ${(pcmBuffer.byteLength / 1024).toFixed(1)}KB ${durationSec.toFixed(1)}s`,
    `peak=${dbFS.toFixed(1)}dBFS`,
    dbFS < -40 ? '(VERY QUIET — check mic gain!)' : '(healthy)',
  )

  return { buffer: pcmBuffer, sampleRate: TARGET_RATE }
}

/**
 * Resample Float32 audio from sourceRate to targetRate using linear interpolation.
 */
async function resample(
  input: Float32Array,
  sourceRate: number,
  targetRate: number,
): Promise<Float32Array> {
  const ratio = sourceRate / targetRate
  const outputLength = Math.floor(input.length / ratio)
  const output = new Float32Array(outputLength)

  // Use OfflineAudioContext for high-quality resampling when ratio is simple
  if (Math.abs(ratio - Math.round(ratio)) < 0.001) {
    return simpleResample(input, Math.round(ratio), outputLength)
  }

  // Generic linear interpolation
  for (let i = 0; i < outputLength; i++) {
    const srcIndex = i * ratio
    const srcFloor = Math.floor(srcIndex)
    const srcCeil = Math.min(srcFloor + 1, input.length - 1)
    const frac = srcIndex - srcFloor
    output[i] = input[srcFloor] * (1 - frac) + input[srcCeil] * frac
  }

  return output
}

/** Integer-ratio resampling (faster, avoids interpolation artifacts). */
function simpleResample(
  input: Float32Array,
  factor: number,
  outputLength: number,
): Float32Array {
  const output = new Float32Array(outputLength)
  for (let i = 0; i < outputLength; i++) {
    const srcIdx = i * factor
    // Average the factor source samples
    let sum = 0
    const end = Math.min(srcIdx + factor, input.length)
    let count = 0
    for (let j = srcIdx; j < end; j++) {
      sum += input[j]
      count++
    }
    output[i] = count > 0 ? sum / count : 0
  }
  return output
}

/**
 * Split PCM buffer into chunks of approximately `chunkMs` milliseconds.
 *
 * At 16kHz 16-bit mono: 1ms = 32 bytes.
 */
export function* pcmChunks(
  pcm: PcmResult,
  chunkMs = 20,
): Generator<ArrayBuffer> {
  const bytesPerMs = pcm.sampleRate * 2 / 1000 // 16-bit = 2 bytes per sample
  const chunkBytes = Math.floor(bytesPerMs * chunkMs)
  const fullChunks = Math.floor(pcm.buffer.byteLength / chunkBytes)

  for (let i = 0; i < fullChunks; i++) {
    yield pcm.buffer.slice(i * chunkBytes, (i + 1) * chunkBytes)
  }

  // Remaining bytes (last partial chunk)
  const remaining = pcm.buffer.byteLength - fullChunks * chunkBytes
  if (remaining > 0) {
    yield pcm.buffer.slice(fullChunks * chunkBytes)
  }
}
