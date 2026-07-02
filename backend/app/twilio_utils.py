import struct
import logging

logger = logging.getLogger("voice-agent")

# Precompute G.711 mu-law to 16-bit linear PCM lookup table
MULAW_TO_PCM = []
for i in range(256):
    mu = ~i & 0xFF
    sign = mu & 0x80
    exponent = (mu >> 4) & 0x07
    mantissa = mu & 0x0F
    sample = (mantissa << 3) + 132
    sample <<= exponent
    sample -= 132
    if sign:
        sample = -sample
    MULAW_TO_PCM.append(sample)

# Precompute 16-bit signed PCM to G.711 mu-law lookup table
# Mapped such that lookup is index = sample + 32768
PCM_TO_MULAW = []
for sample in range(-32768, 32768):
    if sample < 0:
        sign = 0x80
        sample = -sample
    else:
        sign = 0x00
        
    if sample > 32635:
        sample = 32635
        
    sample += 132
    
    # Exponent
    exponent = 7
    mask = 0x4000
    while (sample & mask) == 0 and exponent > 0:
        mask >>= 1
        exponent -= 1
        
    mantissa = (sample >> (exponent + 3)) & 0x0F
    mu = sign | (exponent << 4) | mantissa
    PCM_TO_MULAW.append(~mu & 0xFF)


def pcm_to_mulaw(pcm_bytes: bytes) -> bytes:
    """
    Converts 16-bit signed linear PCM bytes (little-endian) to 8-bit mu-law bytes.
    """
    num_samples = len(pcm_bytes) // 2
    # Unpack little-endian signed 16-bit integers
    samples = struct.unpack(f"<{num_samples}h", pcm_bytes)
    # Convert using precomputed table
    mulaw = bytearray(PCM_TO_MULAW[s + 32768] for s in samples)
    return bytes(mulaw)


def mulaw_to_pcm(mulaw_bytes: bytes) -> bytes:
    """
    Converts 8-bit mu-law bytes to 16-bit signed linear PCM bytes (little-endian).
    """
    # Convert using precomputed table
    samples = [MULAW_TO_PCM[b] for b in mulaw_bytes]
    # Pack as little-endian signed 16-bit integers
    return struct.pack(f"<{len(samples)}h", *samples)


def pcm_to_wav(pcm_bytes: bytes, sample_rate: int = 8000, num_channels: int = 1) -> bytes:
    """
    Wraps raw 16-bit linear PCM bytes inside a standard WAV (RIFF) header.
    """
    byte_rate = sample_rate * num_channels * 2
    block_align = num_channels * 2
    
    header = struct.pack(
        '<4sI4s4sIHHIIHH4sI',
        b'RIFF',
        36 + len(pcm_bytes),
        b'WAVE',
        b'fmt ',
        16,              # Subchunk1Size
        1,               # AudioFormat (1 = PCM)
        num_channels,
        sample_rate,
        byte_rate,
        block_align,
        16,              # BitsPerSample (16-bit)
        b'data',
        len(pcm_bytes)
    )
    return header + pcm_bytes


class EnergyVAD:
    """
    Simple and fast Voice Activity Detection (VAD) for 8kHz mu-law audio streams.
    """
    def __init__(self, threshold: float = 1200.0, silence_duration: float = 1.0, sample_rate: int = 8000):
        self.threshold = threshold
        self.silence_duration_limit = silence_duration
        self.sample_rate = sample_rate
        
        self.is_speaking = False
        self.silence_samples = 0
        self.speech_samples = 0

    def reset(self):
        self.is_speaking = False
        self.silence_samples = 0
        self.speech_samples = 0

    def process_chunk(self, mulaw_bytes: bytes) -> dict:
        """
        Processes a chunk of mu-law bytes.
        Returns a dict: {
            "speech_start_detected": bool,
            "speech_end_detected": bool,
            "is_speaking": bool
        }
        """
        if not mulaw_bytes:
            return {"speech_start_detected": False, "speech_end_detected": False, "is_speaking": self.is_speaking}

        # Convert to PCM values and compute RMS energy
        samples = [MULAW_TO_PCM[b] for b in mulaw_bytes]
        rms = (sum(s * s for s in samples) / len(samples)) ** 0.5

        chunk_size = len(mulaw_bytes)
        
        speech_start_detected = False
        speech_end_detected = False

        if rms > self.threshold:
            self.speech_samples += chunk_size
            self.silence_samples = 0
            if not self.is_speaking:
                # User has started speaking
                self.is_speaking = True
                speech_start_detected = True
                logger.info(f"EnergyVAD: User speech START detected (RMS: {rms:.1f})")
        else:
            if self.is_speaking:
                self.silence_samples += chunk_size
                silence_time = self.silence_samples / self.sample_rate
                if silence_time >= self.silence_duration_limit:
                    # User has stopped speaking
                    self.is_speaking = False
                    self.silence_samples = 0
                    self.speech_samples = 0
                    speech_end_detected = True
                    logger.info("EnergyVAD: User speech END detected")

        return {
            "speech_start_detected": speech_start_detected,
            "speech_end_detected": speech_end_detected,
            "is_speaking": self.is_speaking
        }
