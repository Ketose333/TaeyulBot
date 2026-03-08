from __future__ import annotations

from pathlib import Path

from utility.common.path_roots import MEDIA_ROOT, WORKSPACE_ROOT

MEDIA_IMAGE_DIR = (MEDIA_ROOT / 'image').resolve()
MEDIA_AUDIO_DIR = (MEDIA_ROOT / 'audio').resolve()
MEDIA_VIDEO_DIR = (MEDIA_ROOT / 'video').resolve()
MEDIA_AVATAR_DIR = (MEDIA_ROOT / 'avatars').resolve()

DEFAULT_IMAGE_MODEL = 'nano-banana-pro-preview'
DEFAULT_IMAGE_ASPECT_RATIO = '1:1'

DEFAULT_VEO_MODEL = 'models/veo-3.1-generate-preview'
DEFAULT_VEO_ASPECT_RATIO = '1:1'

DEFAULT_TTS_MODEL = 'gemini-2.5-flash-preview-tts'
DEFAULT_TTS_VOICE = 'Fenrir'

DEFAULT_TAEYUL_REF_IMAGE = str((WORKSPACE_ROOT / 'avatars' / 'taeyul.png').resolve())
DEFAULT_TAEYUL_2D_REF_IMAGE = str((MEDIA_AVATAR_DIR / 'taeyul2D.png').resolve())
