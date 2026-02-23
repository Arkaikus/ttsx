import soundfile as sf
from qwen_tts import Qwen3TTSModel

from ttsx.models.registry import ModelRegistry

registry = ModelRegistry()
model_id = "Qwen/Qwen3-TTS-12Hz-0.6B-CustomVoice"
if not registry.is_installed(model_id):
    registry.install(model_id)

model = registry.get(model_id)

for key, value in model.model_dump().items():
    print(f"{key}: {value}")

model = Qwen3TTSModel.from_pretrained(
    model.path,
    device_map="cuda:0",
    # dtype=torch.bfloat16,
    # flash attention requires flash-attn and its failing to install due to mismatch versions of torch and cuda
    # attn_implementation="flash_attention_2",
)

# single inference
wavs, sr = model.generate_custom_voice(
    text="In fact, I really discovered that I am a person who is particularly good at observing other people's emotions.",
    language="English",  # Pass `Auto` (or omit) for auto language adaptive; if the target language is known, set it explicitly.
    speaker="Vivian",
    instruct="Said in a particularly angry tone",  # Omit if not needed.
)
sf.write("sounds/angry_message_1.wav", wavs[0], sr)

# batch inference
wavs, sr = model.generate_custom_voice(
    text=["I'm going to fuck you in the face.", "I'm so happy to see you."],
    language=["English", "English"],
    speaker=["Vivian", "Ryan"],
    instruct=["Said in a particularly angry tone.", "Said in a very happy tone."],
)

sf.write("sounds/angry_message_2.wav", wavs[0], sr)
sf.write("sounds/happy_message_1.wav", wavs[1], sr)
