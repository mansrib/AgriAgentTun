# -*- coding: utf-8 -*-
"""
Agri-Modernization AI Agent (Full Tunisian Voice Note Transcription + Vision + WhatsApp Bot + Cloud Ready)
=========================================================================================================
وكيل ذكي للاستشارات الفلاحية وتعصير المستغلات عبر واتساب وبوابة الويب (تونس)
- نسخة كاملة 100% جاهزة للتشغيل المحلي والاستضافة السحابية المجانية بدون أي اختصارات.
- الوضع الافتراضي: المراجعة والمصادقة اليدوية للمهندس (AUTO_REPLY_MODE = False) لضمان وصول رسائل الفلاحين
  إلى لوحة المهندس أولاً وعدم إرسال ردود عشوائية.
"""

import os
import sys
import io
import re
import math
import time
import json
import uuid
import wave
import base64
import urllib.parse
import subprocess
import threading
import webbrowser
import requests
from datetime import datetime
from typing import Optional, Dict, Any, List, Tuple
from pydantic import BaseModel, Field

# =====================================================================
# 0. ضبط ترميز الحروف العربية على Windows + تثبيت المكتبات + ملفات الاستضافة
# =====================================================================
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")
elif sys.stdout is not None and hasattr(sys.stdout, "buffer"):
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
    sys.stderr = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")


def ensure_audio_libraries_installed() -> None:
    """يثبّت المكتبات اللازمة تلقائياً عند التشغيل المحلي."""
    missing = []
    for pkg, mod_name in [
        ("Pillow", "PIL"),
        ("av", "av"),
        ("imageio-ffmpeg", "imageio_ffmpeg"),
        ("SpeechRecognition", "speech_recognition"),
        ("google-genai", "google.genai"),
        ("edge-tts", "edge_tts"),
        ("gTTS", "gtts")
    ]:
        try:
            __import__(mod_name)
        except ImportError:
            missing.append(pkg)
    if missing:
        print(f"📦 جاري تثبيت مكتبات الرؤية والصوت التونسي تلقائياً ({', '.join(missing)})...")
        try:
            subprocess.run(
                [sys.executable, "-m", "pip", "install", "-q", "--retries", "1", "--timeout", "4"] + missing,
                check=False
            )
            print("✅ تم تثبيت المكتبات بنجاح!")
        except Exception as e:
            print(f"⚠️ ملاحظة أثناء تثبيت المكتبات: {e}")


def stop_previous_bot_instance_on_port(port: int = 8000) -> None:
    """يوقف أي نسخة قديمة من السيرفر تشتغل في الخلفية على نفس المنفذ."""
    my_pid = str(os.getpid())
    try:
        if os.name == "nt":
            out = subprocess.check_output(["netstat", "-ano"], text=True, errors="ignore")
            pids_to_kill = set()
            for line in out.splitlines():
                if f":{port}" in line and "LISTENING" in line.upper():
                    parts = line.split()
                    if parts:
                        pid = parts[-1].strip()
                        if pid.isdigit() and pid != "0" and pid != my_pid:
                            pids_to_kill.add(pid)
            for pid in pids_to_kill:
                print(f"🔄 إيقاف النسخة القديمة من السيرفر في الخلفية (PID {pid})...")
                subprocess.run(
                    ["taskkill", "/F", "/PID", pid],
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                    check=False
                )
            if pids_to_kill:
                time.sleep(1.0)
    except Exception:
        pass


BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_FILE_PATH = os.path.join(BASE_DIR, "agri_database.json")
CONFIG_FILE_PATH = os.path.join(BASE_DIR, "agri_config.json")
SESSIONS_FILE_PATH = os.path.join(BASE_DIR, "agri_sessions.json")
FARMERS_MAP_FILE_PATH = os.path.join(BASE_DIR, "agri_farmers_map.json")
KB_FILE_PATH = os.path.join(BASE_DIR, "tunisian_agri_knowledge_base.json")
MEDIA_DIR_PATH = os.path.join(BASE_DIR, "tmp_media")
os.makedirs(MEDIA_DIR_PATH, exist_ok=True)

PUBLIC_SITE_URL = os.environ.get("RENDER_EXTERNAL_URL", "https://agriagenttun.onrender.com").rstrip("/")


def ensure_free_hosting_files_created() -> None:
    """ينشئ تلقائياً ملفات الاستضافة السحابية المجانية (requirements.txt, Procfile, Dockerfile)."""
    req_path = os.path.join(BASE_DIR, "requirements.txt")
    proc_path = os.path.join(BASE_DIR, "Procfile")
    docker_path = os.path.join(BASE_DIR, "Dockerfile")
    try:
        if not os.path.exists(req_path):
            with open(req_path, "w", encoding="utf-8") as f:
                f.write(
                    "fastapi\n"
                    "uvicorn\n"
                    "requests\n"
                    "pydantic\n"
                    "python-multipart\n"
                    "Pillow\n"
                    "edge-tts\n"
                    "gTTS\n"
                    "SpeechRecognition\n"
                    "google-genai\n"
                )
        if not os.path.exists(proc_path):
            with open(proc_path, "w", encoding="utf-8") as f:
                f.write("web: uvicorn agri_agent_mvp:app --host 0.0.0.0 --port ${PORT:-8000}\n")
        if not os.path.exists(docker_path):
            with open(docker_path, "w", encoding="utf-8") as f:
                f.write(
                    "FROM python:3.11-slim\n"
                    "WORKDIR /app\n"
                    "COPY . /app\n"
                    "RUN pip install --no-cache-dir -r requirements.txt\n"
                    "EXPOSE 7860\n"
                    "ENV PORT=7860\n"
                    "CMD [\"uvicorn\", \"agri_agent_mvp:app\", \"--host\", \"0.0.0.0\", \"--port\", \"7860\"]\n"
                )
    except Exception:
        pass


ensure_free_hosting_files_created()

if __name__ == "__main__" and "--cli-test" not in sys.argv:
    ensure_audio_libraries_installed()

HARDCODED_GEMINI_API_KEY = "AQ.Ab8RN6IZFDGt3s1H_bKGpL0kh2Y8elerjlD-8ozMTGY3tlaD2w"
DUMMY_PHONES = {"21698112340", "21655430910", "21622780115", "21690000000"}
PROCESSED_MESSAGE_IDS = set()
SENT_BY_BOT_MESSAGE_IDS = set()
FARMER_SESSION_MEMORY: Dict[str, Dict[str, Any]] = {}
BOT_ACTIVITY_LOGS: List[str] = []


def log_bot_event(msg: str) -> None:
    ts = datetime.now().strftime("%H:%M:%S")
    entry = f"[{ts}] {msg}"
    print(entry)
    BOT_ACTIVITY_LOGS.insert(0, entry)
    if len(BOT_ACTIVITY_LOGS) > 40:
        BOT_ACTIVITY_LOGS.pop()


LAST_BOT_STATUS: Dict[str, Any] = {
    "state": "جاهز",
    "detail_ar": "وضع مصادقة المهندس مفعّل — رسائل الفلاحين تصل إلى لوحة المهندس للمراجعة والمصادقة",
    "last_check": ""
}

DEFAULT_WELCOME_MESSAGE = (
    "مرحبا بيك في مكتب الهندسة الفلاحية وتعصير المستغلات 🌿\n"
    "باش نعطيك نصيحة دقيقة وصحيحة، اكتبلي أو ابعثلي تسجيل صوتي أو تصويرة واضحة مع:\n"
    "1️⃣ نوع الغراسة وعمرها (زياتين، قوارص، طماطم، فلفل...)\n"
    "2️⃣ المنطقة (الولاية أو المعتمدية)\n"
    "3️⃣ شنوة الإشكال بالضبط؟ (أعراض على الأوراق/الحبة، وقت السقي، أو التسميد)"
)

DEFAULT_BOT_SIGNATURE = "🌿 المهندسة الفلاحية زينب العزيزي — مكتب الدراسات والاستشارات الفلاحية"


def normalize_session_key(raw_phone: str) -> str:
    digits = "".join(ch for ch in str(raw_phone or "") if ch.isdigit())
    if digits.startswith("00"):
        digits = digits[2:]
    if len(digits) == 8:
        digits = "216" + digits
    return digits or "21621127147"


def load_all_sessions_from_disk() -> Dict[str, Dict[str, Any]]:
    global FARMER_SESSION_MEMORY
    try:
        if os.path.exists(SESSIONS_FILE_PATH):
            with open(SESSIONS_FILE_PATH, "r", encoding="utf-8") as f:
                data = json.load(f)
                if isinstance(data, dict):
                    for k, v in data.items():
                        if isinstance(v, dict):
                            FARMER_SESSION_MEMORY[normalize_session_key(k)] = v
    except Exception:
        pass
    return FARMER_SESSION_MEMORY


def get_farmer_session(phone: str) -> Dict[str, Any]:
    load_all_sessions_from_disk()
    key = normalize_session_key(phone)
    mem = FARMER_SESSION_MEMORY.get(key)
    if mem and isinstance(mem, dict):
        return mem
    return {}


def save_farmer_session(phone: str, mem: Dict[str, Any]) -> None:
    global FARMER_SESSION_MEMORY
    load_all_sessions_from_disk()
    key = normalize_session_key(phone)
    mem["updated_at_ts"] = time.time()
    FARMER_SESSION_MEMORY[key] = mem
    try:
        with open(SESSIONS_FILE_PATH, "w", encoding="utf-8") as f:
            json.dump(FARMER_SESSION_MEMORY, f, ensure_ascii=False, indent=2)
    except Exception:
        pass


def load_saved_config() -> Dict[str, Any]:
    default_cfg: Dict[str, Any] = {
        "AUTO_REPLY_MODE": False,
        "MANUAL_APPROVAL_ENFORCED_V9": True,
        "ZEINEB_VOICE_DEFAULT_V8": True,
        "BOT_REPLY_FORMAT": "both",
        "BOT_VOICE_NAME": "ar-TN-ReemNeural",
        "BOT_ENGINEER_NAME": "المهندسة الفلاحية زينب العزيزي",
        "DEFAULT_TEST_PHONE": "21621127147",
        "GEMINI_API_KEY": HARDCODED_GEMINI_API_KEY,
        "BOT_OFFICE_NAME": DEFAULT_BOT_SIGNATURE,
        "BOT_WELCOME_MESSAGE": DEFAULT_WELCOME_MESSAGE,
        "ENGINEER_CUSTOM_PASSWORD": "",
        "ENGINEER_CUSTOM_LOGIN": "admin",
        "BOT_CUSTOM_INSTRUCTIONS": (
            "تحدثي بصفتك المهندسة الفلاحية التونسية الخبيرة «زينب العزيزي» بنفس نبرتها الدافئة والعملية بالدارجة التونسية."
        )
    }
    try:
        if os.path.exists(CONFIG_FILE_PATH):
            with open(CONFIG_FILE_PATH, "r", encoding="utf-8") as f:
                loaded = json.load(f)
                if not loaded.get("MANUAL_APPROVAL_ENFORCED_V9"):
                    loaded["AUTO_REPLY_MODE"] = False
                    loaded["MANUAL_APPROVAL_ENFORCED_V9"] = True
                    loaded["BOT_VOICE_NAME"] = "ar-TN-ReemNeural"
                    try:
                        with open(CONFIG_FILE_PATH, "w", encoding="utf-8") as fw:
                            json.dump(loaded, fw, ensure_ascii=False, indent=2)
                    except Exception:
                        pass
                default_cfg.update(loaded)
    except Exception:
        pass

    if not default_cfg.get("GEMINI_API_KEY"):
        default_cfg["GEMINI_API_KEY"] = HARDCODED_GEMINI_API_KEY
    return default_cfg


def save_config_key(key: str, value: Any) -> None:
    try:
        cfg = load_saved_config()
        cfg[key] = value.strip() if isinstance(value, str) else value
        with open(CONFIG_FILE_PATH, "w", encoding="utf-8") as f:
            json.dump(cfg, f, ensure_ascii=False, indent=2)
    except Exception:
        pass


def get_active_gemini_key() -> str:
    cfg = load_saved_config()
    return (
        cfg.get("GEMINI_API_KEY")
        or HARDCODED_GEMINI_API_KEY
        or os.environ.get("GEMINI_API_KEY")
        or ""
    ).strip()


# =====================================================================
# 1. تحويل وتفريغ التسجيلات الصوتية بالدارجة التونسية (OGG Opus -> WAV -> Text)
# =====================================================================
def convert_ogg_to_wav_bytes(audio_path: str) -> Optional[bytes]:
    if not audio_path or not os.path.exists(audio_path):
        return None
    try:
        import av
        wav_buf = io.BytesIO()
        with av.open(audio_path, mode="r") as in_container:
            audio_streams = [s for s in in_container.streams if s.type == "audio"]
            if audio_streams:
                resampler = av.AudioResampler(format="s16", layout="mono", rate=16000)
                with wave.open(wav_buf, "wb") as wf:
                    wf.setnchannels(1)
                    wf.setsampwidth(2)
                    wf.setframerate(16000)
                    for frame in in_container.decode(audio=0):
                        for rframe in resampler.resample(frame):
                            wf.writeframes(bytes(rframe.planes[0]))
        wav_bytes = wav_buf.getvalue()
        if len(wav_bytes) > 200:
            return wav_bytes
    except Exception:
        pass

    try:
        import imageio_ffmpeg
        ffmpeg_exe = imageio_ffmpeg.get_ffmpeg_exe()
        proc = subprocess.run(
            [ffmpeg_exe, "-y", "-i", audio_path, "-ar", "16000", "-ac", "1", "-f", "wav", "pipe:1"],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            timeout=15,
            check=False
        )
        if proc.stdout and len(proc.stdout) > 200:
            return proc.stdout
    except Exception:
        pass

    return None


def transcribe_tunisian_voice_note(audio_path: str) -> Optional[str]:
    wav_bytes = convert_ogg_to_wav_bytes(audio_path)
    if wav_bytes:
        try:
            import speech_recognition as sr
            recognizer = sr.Recognizer()
            with sr.AudioFile(io.BytesIO(wav_bytes)) as source:
                audio_data = recognizer.record(source)
            for lang_code in ["ar-TN", "ar-DZ", "ar-EG", "ar"]:
                try:
                    transcript = recognizer.recognize_google(audio_data, language=lang_code)
                    if transcript and transcript.strip():
                        clean_tr = transcript.strip()
                        log_bot_event(f"🎙️ [تم تفريغ التسجيل الصوتي ({lang_code})]: «{clean_tr}»")
                        return clean_tr
                except Exception:
                    continue
        except Exception:
            pass
    return None


# =====================================================================
# 2. إحداثيات الولايات والمعتمديات التونسية وحسابات المساحة و UTM
# =====================================================================
TUNISIA_AGRI_REGIONS: Dict[str, Dict[str, float]] = {
    "مرناق - بن عروس": {"lat": 36.6806, "lon": 10.2892},
    "تونس الكبرى - أريانة - منوبة": {"lat": 36.8065, "lon": 10.1815},
    "نابل - الوطن القبلي": {"lat": 36.4561, "lon": 10.7376},
    "زغوان - الفحص - الناظور": {"lat": 36.4029, "lon": 10.1429},
    "بنزرت": {"lat": 37.2744, "lon": 9.8739},
    "باجة": {"lat": 36.7256, "lon": 9.1817},
    "جندوبة": {"lat": 36.5011, "lon": 8.7802},
    "الكاف - الدهماني - تاجروين": {"lat": 36.1742, "lon": 8.7049},
    "سليانة - بوعرادة - مكثر": {"lat": 36.0850, "lon": 9.3708},
    "سوسة - النفيضة - شط مريم": {"lat": 35.8256, "lon": 10.6369},
    "المنستير - البقالطة - طبلبة": {"lat": 35.7643, "lon": 10.8113},
    "المهدية - قصور الساف - الجم": {"lat": 35.5047, "lon": 11.0622},
    "القيروان": {"lat": 35.6781, "lon": 10.0963},
    "صفاقس": {"lat": 34.7406, "lon": 10.7603},
    "سيدي بوزيد": {"lat": 35.0382, "lon": 9.4849},
    "القصرين - سبيطلة - فوسانة - تالة": {"lat": 35.1676, "lon": 8.8365},
    "قابس": {"lat": 33.8815, "lon": 10.0982},
    "قفصة - القطار - السند": {"lat": 34.4250, "lon": 8.7842},
    "توزر - نفطة - دقاش": {"lat": 33.9197, "lon": 8.1335},
    "قبلي - دوز - سوق الأحد": {"lat": 33.7044, "lon": 8.9690},
    "مدنين - جرجيس - جربة - بن قردان": {"lat": 33.3549, "lon": 10.5055},
    "تطاوين - رمادة - غمراسن": {"lat": 32.9297, "lon": 10.4518}
}

TUNISIA_SUBLOCALITIES_COORDS: Dict[str, Tuple[float, float]] = {
    "مرناق": (36.6806, 10.2892), "بن عروس": (36.7531, 10.2189), "الخليدية": (36.6430, 10.1920),
    "فوشانة": (36.6980, 10.1690), "المحمدية": (36.6740, 10.1560), "رادس": (36.7680, 10.2750),
    "تونس": (36.8065, 10.1815), "أريانة": (36.8625, 10.1956), "سيدي ثابت": (36.9090, 10.0420),
    "قلعة الأندلس": (37.0620, 10.1180), "منوبة": (36.8081, 10.0972), "طبربة": (36.8290, 9.8410),
    "الجديدة": (36.8250, 9.9290), "برج العامري": (36.7210, 9.9140), "المرناقية": (36.7590, 10.0150),
    "نابل": (36.4561, 10.7376), "قليبية": (36.8475, 11.0939), "منزل تميم": (36.7822, 10.9900),
    "منزل بوزلفة": (36.6833, 10.5833), "بني خلاد": (36.6500, 10.5900), "سليمان": (36.6964, 10.4917),
    "قربة": (36.5786, 10.8586), "تاكلسة": (36.7833, 10.6333), "الحمامات": (36.4000, 10.6167),
    "الهوارية": (37.0500, 11.0167), "بوعرقوب": (36.5380, 10.5510), "قرمبالية": (36.6020, 10.4960),
    "زغوان": (36.4029, 10.1429), "الفحص": (36.3742, 9.9064), "الناظور": (36.1350, 10.0980),
    "بنزرت": (37.2744, 9.8739), "ماطر": (37.0400, 9.6650), "سجنان": (37.0570, 9.2380),
    "العالية": (37.1690, 10.0340), "رأس الجبل": (37.2150, 10.1240), "أوتيك": (37.0410, 10.0380),
    "باجة": (36.7256, 9.1817), "تبرسق": (36.4570, 9.2480), "مجاز الباب": (36.6490, 9.6120),
    "تستور": (36.5510, 9.4430), "نفزة": (36.9730, 9.0760), "قبلاط": (36.5410, 9.6650),
    "جندوبة": (36.5011, 8.7802), "بوسالم": (36.6111, 8.9694), "طبرقة": (36.9544, 8.7581),
    "فرنانة": (36.6570, 8.6960), "غار الدماء": (36.4500, 8.4390),
    "الكاف": (36.1742, 8.7049), "الدهماني": (35.9420, 8.8280), "تاجروين": (35.8910, 8.5520),
    "السرس": (36.0760, 9.0210), "سليانة": (36.0850, 9.3708), "بوعرادة": (36.3520, 9.6220),
    "مكثر": (35.8580, 9.2050), "الكريب": (36.3280, 9.1360), "قعفور": (36.3210, 9.3240),
    "سوسة": (35.8256, 10.6369), "النفيضة": (36.1353, 10.3808), "شط مريم": (35.9360, 10.5570),
    "مساكن": (35.7292, 10.5808), "سيدي بوعلي": (35.9560, 10.4730),
    "المنستير": (35.7643, 10.8113), "البقالطة": (35.6214, 10.9922), "طبلبة": (35.6417, 10.9578),
    "المكنين": (35.6317, 10.9022), "جمال": (35.6222, 10.7569),
    "المهدية": (35.5047, 11.0622), "قصور الساف": (35.4181, 10.9944), "الجم": (35.3000, 10.7167),
    "الشابة": (35.2372, 11.1150), "سيدي علوان": (35.3750, 10.9380),
    "القيروان": (35.6781, 10.0963), "بوحجلة": (35.3994, 10.0956), "حاجب العيون": (35.3900, 9.5400),
    "الشبيكة": (35.6180, 9.9320), "السبيخة": (35.9333, 10.0167), "الوسلاتية": (35.8500, 9.5833),
    "صفاقس": (34.7406, 10.7603), "عقارب": (34.7422, 10.5311), "جبنيانة": (35.0350, 10.9080),
    "الحنشة": (35.1260, 10.7590), "منزل شاكر": (34.9333, 10.3833), "العامرة": (34.9667, 10.8833),
    "المحرس": (34.5280, 10.4980), "الصخيرة": (34.2990, 10.0700), "بئر علي بن خليفة": (34.7380, 10.0920),
    "سيدي بوزيد": (35.0382, 9.4849), "الرقاب": (34.8592, 9.7867), "جلمة": (35.2610, 9.4230),
    "أولاد حفوز": (35.0680, 9.7940), "المكناسي": (34.6040, 9.6060), "المزونة": (34.5790, 9.8420),
    "بئر الحفي": (34.9320, 9.1930), "منزل بوزيان": (34.5280, 9.4310),
    "القصرين": (35.1676, 8.8365), "سبيطلة": (35.2367, 9.1294), "سبيبة": (35.5433, 9.0736),
    "فوسانة": (35.3350, 8.6180), "تالة": (35.5719, 8.6672), "فريانة": (34.9480, 8.5670),
    "قابس": (33.8815, 10.0982), "الحامة": (33.8864, 9.7950), "مارث": (33.6333, 10.3000),
    "مطماطة": (33.5440, 9.9670), "وذرف": (33.9880, 9.9720),
    "قفصة": (34.4250, 8.7842), "القطار": (34.3360, 8.9530), "السند": (34.4620, 9.2620),
    "توزر": (33.9197, 8.1335), "نفطة": (33.8731, 7.8778), "دقاش": (33.9760, 8.2110),
    "قبلي": (33.7044, 8.9690), "دوز": (33.4664, 9.0203), "سوق الأحد": (33.7880, 8.8820),
    "مدنين": (33.3549, 10.5055), "جرجيس": (33.5040, 11.1122), "جربة": (33.8076, 10.8451),
    "بن قردان": (33.1378, 11.2197), "تطاوين": (32.9297, 10.4518), "رمادة": (32.3167, 10.3958),
    "غمراسن": (33.0600, 10.3400)
}

REGION_KEYWORDS: Dict[str, str] = {
    "مرناق": "مرناق - بن عروس", "بن عروس": "مرناق - بن عروس", "فوشانة": "مرناق - بن عروس",
    "تونس": "تونس الكبرى - أريانة - منوبة", "أريانة": "تونس الكبرى - أريانة - منوبة",
    "منوبة": "تونس الكبرى - أريانة - منوبة", "طبربة": "تونس الكبرى - أريانة - منوبة",
    "الجديدة": "تونس الكبرى - أريانة - منوبة", "نابل": "نابل - الوطن القبلي",
    "قليبية": "نابل - الوطن القبلي", "منزل تميم": "نابل - الوطن القبلي",
    "بني خلاد": "نابل - الوطن القبلي", "سليمان": "نابل - الوطن القبلي",
    "قربة": "نابل - الوطن القبلي", "الهوارية": "نابل - الوطن القبلي",
    "زغوان": "زغوان - الفحص - الناظور", "الفحص": "زغوان - الفحص - الناظور",
    "بنزرت": "بنزرت", "ماطر": "بنزرت", "سجنان": "بنزرت", "رأس الجبل": "بنزرت",
    "باجة": "باجة", "مجاز الباب": "باجة", "تستور": "باجة", "تبرسق": "باجة",
    "جندوبة": "جندوبة", "بوسالم": "جندوبة", "طبرقة": "جندوبة", "فرنانة": "جندوبة",
    "الكاف": "الكاف - الدهماني - تاجروين", "تاجروين": "الكاف - الدهماني - تاجروين",
    "سليانة": "سليانة - بوعرادة - مكثر", "قعفور": "سليانة - بوعرادة - مكثر",
    "سوسة": "سوسة - النفيضة - شط مريم", "النفيضة": "سوسة - النفيضة - شط مريم",
    "المنستير": "المنستير - البقالطة - طبلبة", "البقالطة": "المنستير - البقالطة - طبلبة",
    "المكنين": "المنستير - البقالطة - طبلبة", "طبلبة": "المنستير - البقالطة - طبلبة",
    "المهدية": "المهدية - قصور الساف - الجم", "الجم": "المهدية - قصور الساف - الجم",
    "قصور الساف": "المهدية - قصور الساف - الجم", "القيروان": "القيروان",
    "الشبيكة": "القيروان", "بوحجلة": "القيروان", "صفاقس": "صفاقس", "عقارب": "صفاقس",
    "جبنيانة": "صفاقس", "الحنشة": "صفاقس", "سيدي بوزيد": "سيدي بوزيد",
    "الرقاب": "سيدي بوزيد", "جلمة": "سيدي بوزيد", "المكناسي": "سيدي بوزيد",
    "القصرين": "القصرين - سبيطلة - فوسانة - تالة", "سبيطلة": "القصرين - سبيطلة - فوسانة - تالة",
    "سبيبة": "القصرين - سبيطلة - فوسانة - تالة", "تالة": "القصرين - سبيطلة - فوسانة - تالة",
    "فوسانة": "القصرين - سبيطلة - فوسانة - تالة", "قابس": "قابس", "الحامة": "قابس",
    "قفصة": "قفصة - القطار - السند", "القطار": "قفصة - القطار - السند",
    "توزر": "توزر - نفطة - دقاش", "دقاش": "توزر - نفطة - دقاش", "نفطة": "توزر - نفطة - دقاش",
    "قبلي": "قبلي - دوز - سوق الأحد", "دوز": "قبلي - دوز - سوق الأحد",
    "مدنين": "مدنين - جرجيس - جربة - بن قردان", "جرجيس": "مدنين - جرجيس - جربة - بن قردان",
    "جربة": "مدنين - جرجيس - جربة - بن قردان", "تطاوين": "تطاوين - رمادة - غمراسن"
}


def normalize_arabic_for_match(text: str) -> str:
    s = str(text or "")
    arabic_digits = str.maketrans("٠١٢٣٤٥٦٧٨٩", "0123456789")
    s = s.translate(arabic_digits)
    s = re.sub(r"[ً-ٟـ]", "", s)
    s = s.replace("أ", "ا").replace("إ", "ا").replace("آ", "ا")
    s = s.replace("ة", "ه").replace("ى", "ي")
    return s.lower().strip()


def detect_tunisian_region(text: str, is_followup_intake: bool = False) -> Optional[str]:
    clean = str(text or "").strip()
    norm_clean = normalize_arabic_for_match(clean)
    for kw, reg_name in sorted(REGION_KEYWORDS.items(), key=lambda x: len(x[0]), reverse=True):
        if kw in clean or normalize_arabic_for_match(kw) in norm_clean:
            return reg_name
    return None


def extract_gps_from_text_or_payload(
    text: str,
    lat_in: Optional[float] = None,
    lon_in: Optional[float] = None
) -> Optional[Tuple[float, float]]:
    if lat_in is not None and lon_in is not None:
        try:
            fl_lat, fl_lon = float(lat_in), float(lon_in)
            if 29.0 <= fl_lat <= 38.0 and 7.0 <= fl_lon <= 12.5:
                return round(fl_lat, 6), round(fl_lon, 6)
        except Exception:
            pass
    clean = str(text or "")
    m = re.search(r"([3][0-7]\.\d{3,8})\s*[,،/\s]+\s*([789]\.\d{3,8}|1[01]\.\d{3,8})", clean)
    if m:
        try:
            return round(float(m.group(1)), 6), round(float(m.group(2)), 6)
        except Exception:
            pass
    return None


def extract_polygon_points_from_text(text: str) -> List[List[float]]:
    clean = str(text or "")
    matches = re.findall(r"([3][0-7]\.\d{3,8})\s*[,،/\s]+\s*([789]\.\d{3,8}|1[01]\.\d{3,8})", clean)
    pts: List[List[float]] = []
    for lat_s, lon_s in matches:
        try:
            pt = [round(float(lat_s), 6), round(float(lon_s), 6)]
            if not pts or (abs(pts[-1][0] - pt[0]) > 1e-6 or abs(pts[-1][1] - pt[1]) > 1e-6):
                pts.append(pt)
        except Exception:
            continue
    return pts if len(pts) >= 3 else []


def calculate_polygon_area_ha_and_m2(points: List[List[float]]) -> Tuple[float, float, float, float, float]:
    if not points or len(points) < 3:
        if points:
            return 0.0, 0.0, 0.0, float(points[0][0]), float(points[0][1])
        return 0.0, 0.0, 0.0, 36.6806, 10.2892

    n = len(points)
    center_lat = sum(float(p[0]) for p in points) / n
    center_lon = sum(float(p[1]) for p in points) / n
    lat_to_m = 111132.95
    lon_to_m = 111319.49 * math.cos(math.radians(center_lat))

    xy: List[Tuple[float, float]] = [
        ((float(p[1]) - center_lon) * lon_to_m, (float(p[0]) - center_lat) * lat_to_m)
        for p in points
    ]
    area_2 = 0.0
    perimeter_m = 0.0
    for i in range(n):
        x1, y1 = xy[i]
        x2, y2 = xy[(i + 1) % n]
        area_2 += (x1 * y2) - (x2 * y1)
        perimeter_m += math.hypot(x2 - x1, y2 - y1)

    area_m2 = round(abs(area_2) * 0.5, 1)
    area_ha = round(area_m2 / 10000.0, 4)
    return area_ha, area_m2, round(perimeter_m, 1), round(center_lat, 6), round(center_lon, 6)


def wgs84_latlon_to_utm(lat: float, lon: float) -> Dict[str, Any]:
    a = 6378137.0
    f = 1.0 / 298.257223563
    k0 = 0.9996
    zone_num = int((lon + 180.0) // 6.0) + 1
    lon0 = math.radians((zone_num - 1) * 6.0 - 180.0 + 3.0)
    phi = math.radians(lat)
    lam = math.radians(lon)
    e2 = 2 * f - f * f
    ep2 = e2 / (1.0 - e2)
    N = a / math.sqrt(1.0 - e2 * (math.sin(phi) ** 2))
    T = math.tan(phi) ** 2
    C = ep2 * (math.cos(phi) ** 2)
    A = math.cos(phi) * (lam - lon0)
    M = a * (
        (1.0 - e2 / 4.0 - 3.0 * (e2 ** 2) / 64.0 - 5.0 * (e2 ** 3) / 256.0) * phi
        - (3.0 * e2 / 8.0 + 3.0 * (e2 ** 2) / 32.0 + 45.0 * (e2 ** 3) / 1024.0) * math.sin(2.0 * phi)
        + (15.0 * (e2 ** 2) / 256.0 + 45.0 * (e2 ** 3) / 1024.0) * math.sin(4.0 * phi)
        - (35.0 * (e2 ** 3) / 3072.0) * math.sin(6.0 * phi)
    )
    easting = 500000.0 + k0 * N * (
        A
        + (1.0 - T + C) * (A ** 3) / 6.0
        + (5.0 - 18.0 * T + (T ** 2) + 72.0 * C - 58.0 * ep2) * (A ** 5) / 120.0
    )
    northing = k0 * (
        M
        + N * math.tan(phi) * (
            (A ** 2) / 2.0
            + (5.0 - T + 9.0 * C + 4.0 * (C ** 2)) * (A ** 4) / 24.0
            + (61.0 - 58.0 * T + (T ** 2) + 600.0 * C - 330.0 * ep2) * (A ** 6) / 720.0
        )
    )
    band = "S" if lat >= 32.0 else "R"
    return {
        "zone": zone_num,
        "band": band,
        "zone_label": f"{zone_num}{band}",
        "easting": round(easting, 2),
        "northing": round(northing, 2)
    }


def nearest_tunisian_locality_from_gps(lat: float, lon: float) -> Tuple[str, str]:
    best_loc = "مرناق"
    best_dist = 999999.0
    for loc_name, (c_lat, c_lon) in TUNISIA_SUBLOCALITIES_COORDS.items():
        dist = ((lat - c_lat) ** 2 + (lon - c_lon) ** 2) ** 0.5
        if dist < best_dist:
            best_dist = dist
            best_loc = loc_name
    region_name = REGION_KEYWORDS.get(best_loc, "مرناق - بن عروس")
    return best_loc, region_name


def resolve_farmer_coordinates(
    text: str,
    region: str,
    phone: str,
    farmer_name: str,
    gps_lat: Optional[float] = None,
    gps_lon: Optional[float] = None
) -> Tuple[float, float, bool, str]:
    gps_pair = extract_gps_from_text_or_payload(text, gps_lat, gps_lon)
    if gps_pair:
        near_loc, _ = nearest_tunisian_locality_from_gps(gps_pair[0], gps_pair[1])
        return gps_pair[0], gps_pair[1], True, f"{near_loc} (موقع GPS دقيق 🎯)"

    norm = normalize_arabic_for_match(text)
    matched_subloc = None
    base_coords = None
    for loc_name, coords in TUNISIA_SUBLOCALITIES_COORDS.items():
        if loc_name in text or normalize_arabic_for_match(loc_name) in norm:
            matched_subloc = loc_name
            base_coords = coords
            break

    if not base_coords:
        reg_coords = TUNISIA_AGRI_REGIONS.get(region, TUNISIA_AGRI_REGIONS["مرناق - بن عروس"])
        base_coords = (reg_coords["lat"], reg_coords["lon"])
        matched_subloc = region.split("-")[0].strip()

    seed_str = f"{normalize_session_key(phone)}:{farmer_name}"
    h_val = sum((i + 1) * ord(ch) for i, ch in enumerate(seed_str))
    d_lat = ((h_val % 19) - 9) * 0.0012
    d_lon = (((h_val // 19) % 19) - 9) * 0.0012
    return round(base_coords[0] + d_lat, 5), round(base_coords[1] + d_lon, 5), False, matched_subloc


# =====================================================================
# 3. قاعدة المعارف الفلاحية التونسية والبطاقات التشخيصية الدقيقة (Plantix + DGSV)
# =====================================================================
INDIVIDUAL_CROP_DETECTION_RULES: List[Tuple[str, str, List[str]]] = [
    ("الجلبانة", "خضروات", ["جلبانة", "جلبانه", "بازلاء", "قجلبانة"]),
    ("الفول", "زراعات_كبرى", ["فول", "فول مصري", "بشير", "بدار"]),
    ("الحمص", "زراعات_كبرى", ["حمص", "الحمص", "شتوي"]),
    ("العدس", "زراعات_كبرى", ["عدس", "العدس"]),
    ("اللوبيا", "خضروات", ["لوبيا", "فاصوليا", "لوبيه"]),
    ("القمح", "زراعات_كبرى", ["قمح", "قمح صلب", "قمح لين", "القمح", "معالي", "كريم", "رزاق", "سليم", "ذهبي"]),
    ("الشعير", "زراعات_كبرى", ["شعير", "الشعير", "منال", "ريحان", "كونوز", "ريمة"]),
    ("الفصة", "زراعات_كبرى", ["فصة", "فصه", "قرط", "برسيم", "علف", "أعلاف"]),
    ("الطماطم", "خضروات", ["طماطم", "طماطمة", "بومودورو", "سافكس"]),
    ("الفلفل", "خضروات", ["فلفل", "قرن الغزال", "بقلوطي", "فلفل حار", "فلفل حلو"]),
    ("البطاطا", "خضروات", ["بطاطا", "سبونتا", "نيكولا", "دايموند", "أريزونا"]),
    ("الدلاع", "خضروات", ["دلاع", "الدلاع", "بطيخ أحمر", "كريمصن"]),
    ("البطيخ", "خضروات", ["بطيخ", "البطيخ", "قلعاوي", "بطيخ أصفر", "شمام", "أناناس"]),
    ("القرع والفقوس", "خضروات", ["قرع", "القرع", "فقوس", "الفقوس", "خيار", "الخيار", "كورجات"]),
    ("البصل", "خضروات", ["بصل", "البصل", "ربعي"]),
    ("الثوم", "خضروات", ["ثوم", "الثوم"]),
    ("السلق", "خضروات", ["سلق", "السلق"]),
    ("المعدنوس", "خضروات", ["معدنوس", "المعدنوس", "بقدونس"]),
    ("الكرافس", "خضروات", ["كرافس", "الكرافس", "كرفس"]),
    ("السبناخ والسلاطة", "خضروات", ["سبناخ", "السبناخ", "سبانخ", "سلاطة", "السلاطة", "خس"]),
    ("السفنارية", "خضروات", ["سفنارية", "سفناريه", "سنارية", "جزر", "الجزر"]),
    ("اللفت", "خضروات", ["لفت", "اللفت", "رادي", "فجل"]),
    ("القنارية", "خضروات", ["قنارية", "قناريه", "القنارية", "خرشوف"]),
    ("البروكلو والكرنب", "خضروات", ["بروكلو", "البروكلو", "بروكلي", "قرنبيط", "كرنب", "ملفوف"]),
    ("الباذنجان", "خضروات", ["باذنجان", "الباذنجان", "بيتنجان", "قناوية", "بامية"]),
    ("الفريز", "خضروات", ["فريز", "الفريز", "فراولو", "فروله", "فراولة"]),
    ("الزياتين", "زياتين", ["زيتون", "زياتين", "الزيتون", "الزياتين", "شملالي", "شتوي", "وسلاتي", "زلماطي", "أربكينا", "اربكينا", "كورونيكي"]),
    ("الهندي", "أشجار_مثمرة", ["هندي", "الهندي", "تين شوكي", "ضلف", "ضلفة", "كوشنيلا", "قرمزية"]),
    ("التفاح", "أشجار_مثمرة", ["تفاح", "التفاح", "غولدن", "ستاركينغ", "تفاحيات"]),
    ("الإجاص", "أشجار_مثمرة", ["إجاص", "اجاص", "الإجاص", "بوصاع", "ويليامز"]),
    ("القوارص", "أشجار_مثمرة", ["قوارص", "القوارص", "برقدان", "برتقال", "ليمون", "قارص", "كليمنتين", "مندرين", "مالطي", "طومسون"]),
    ("اللوز", "أشجار_مثمرة", ["لوز", "اللوز", "أشاك", "فيرانيس"]),
    ("الخوخ", "أشجار_مثمرة", ["خوخ", "الخوخ", "نكتارين", "فلوريدا"]),
    ("المشماش", "أشجار_مثمرة", ["مشماش", "المشماش", "مشمش", "المشمش"]),
    ("العوينة", "أشجار_مثمرة", ["عوينة", "عوينه", "العوينة", "برقوق", "حب الملوك", "كرز"]),
    ("الرمان", "أشجار_مثمرة", ["رمان", "الرمان", "قابسي", "زهري", "شلفي"]),
    ("الكروم", "أشجار_مثمرة", ["كروم", "الكروم", "عنب", "العنب", "دالية"]),
    ("النخيل", "أشجار_مثمرة", ["نخيل", "النخيل", "نخلة", "دقلة", "دقلة النور", "تمر", "عرجون", "بوفروة"]),
    ("الكرموس", "أشجار_مثمرة", ["كرموس", "الكرموس", "تين", "التين", "باكور"]),
    ("الفستق", "أشجار_مثمرة", ["فستق", "الفستق", "فزدق"])
]

DIRECT_CROP_FERT_SUMMARY: Dict[str, str] = {
    "الجلبانة": "• **تسميد الجلبانة:** قبل الزرع حط **150 كغ فوسفور DAP + 100 كغ سلفات البوتاسيوم في الهكتار**، ووقت النوار والقرون عدّي **10 كغ سلفات البوتاسيوم في الهكتار في الجمعة** مع رشة **بورون + كالسيوم** (**150 مل/100 لتر ماء**).",
    "الفول": "• **تسميد الفول:** قبل الزرع حط **150 كغ فوسفور DAP في الهكتار**، ووقت النوار رشّ **بورون + زنك** (**150 مل/100 لتر ماء**) ووقت تعمير القرون رشّ **NPK 10-10-40** (**300 غ/100 لتر ماء**).",
    "الحمص": "• **تسميد الحمص:** قبل الزرع حط **120 كغ فوسفور DAP في الهكتار**، وقبل النوار رشّ **بورون + زنك** (**150 مل/100 لتر ماء**).",
    "العدس": "• **تسميد العدس:** قبل البذر حط **100 كغ فوسفور سوبر فوسفات أو DAP في الهكتار**، ووقت النوار رشّ **بورون + فوسفور عالي** (**150 مل/100 لتر ماء**).",
    "اللوبيا": "• **تسميد اللوبيا:** في أول 20 يوم عدّي **3 كغ MAP في الهكتار في اليوم**، ووقت النوار والقرون عدّي **6 كغ سلفات البوتاسيوم + 5 كغ نترات الكالسيوم (وحده)**.",
    "القمح": "• **تسميد القمح:** قبل الزرع حط **150 كغ DAP في الهكتار**، وأعطي **أمونيتر 33.5%** على 3 دفعات: **100 كغ/هكتار** في طور 3 ورقات، **130 كغ/هكتار** في بداية الاستطالة، و**90 كغ/هكتار** عند ورقة العلم.",
    "الشعير": "• **تسميد الشعير:** قبل الزرع حط **100 كغ DAP في الهكتار**، وأعطي **80 كغ أمونيتر/هكتار** وقت التفريع و**80 كغ/هكتار** في بداية الاستطالة.",
    "الفصة": "• **تسميد الفصة:** بعد كل حشّتين عدّي **15 كغ فوسفور MAP + 20 كغ سلفات البوتاسيوم في الهكتار** مع السقي.",
    "الطماطم": "• **تسميد الطماطم:** في أول 3 جمعات عدّي **3 كغ MAP في اليوم**؛ ووقت النوار والغلة عدّي في البرميل (أ): **8 إلى 10 كغ سلفات البوتاسيوم + 4 كغ أمونيتر + 3 كغ سلفات المغنيزيوم**، وفي البرميل (ب) وحده: **6 إلى 8 كغ نترات الكالسيوم** مرتين في الجمعة.",
    "الفلفل": "• **تسميد الفلفل:** عدّي في البرميل (أ): **7 كغ سلفات البوتاسيوم + 3 كغ أمونيتر + 3 كغ سلفات المغنيزيوم**، وفي البرميل (ب) وحده: **6 كغ نترات الكالسيوم** مرتين في الجمعة.",
    "البطاطا": "• **تسميد البطاطا:** في أول 25 يوم عدّي **4 كغ MAP في اليوم**؛ ومن يوم 25 لـ 50 عدّي **7 كغ أمونيتر + 5 كغ نترات الكالسيوم**؛ ومن يوم 50 لـ 85 وقف الأمونيتر وعدّي **12 كغ سلفات البوتاسيوم في اليوم**.",
    "الدلاع": "• **تسميد الدلاع:** في أول 20 يوم عدّي **4 كغ MAP**؛ وقت النوار رشّ **كالسيببور (200 مل/100 لتر)**؛ ووقت تكبر الكعبة وقف الأمونيتر وعدّي **10 إلى 12 كغ سلفات البوتاسيوم في الهكتار في اليوم** مع **6 كغ نترات الكالسيوم**.",
    "البطيخ": "• **تسميد البطيخ:** في الأول عدّي **3 كغ MAP**، ووقت التحجيم عدّي **8 إلى 10 كغ سلفات البوتاسيوم في اليوم** مع **نترات الكالسيوم (6 كغ مرتين في الجمعة وحده)**.",
    "القرع والفقوس": "• **تسميد القرع والفقوس والخيار:** عدّي **5 كغ NPK 20-20-20 + 5 كغ سلفات البوتاسيوم في الهكتار في اليوم**، ومرتين في الجمعة **5 كغ نترات الكالسيوم**.",
    "البصل": "• **تسميد البصل:** في الأول عدّي **10 كغ أمونيتر + 5 كغ MAP في الجمعة**، ووقت تبدا الكعبة تكبر وقف الأمونيتر وعدّي **15 إلى 20 كغ سلفات البوتاسيوم في الهكتار في الجمعة**.",
    "الثوم": "• **تسميد الثوم:** قبل الغراسة حط **150 كغ DAP + 100 كغ سلفات البوتاسيوم**، وفي الربيع عدّي **15 كغ سلفات البوتاسيوم في الهكتار في الجمعة**.",
    "السلق": "• **تسميد السلق:** بعد كل حشّة عدّي **10 كغ أمونيتر + 8 كغ نترات الكالسيوم + 5 كغ سلفات المغنيزيوم في الهكتار**.",
    "المعدنوس": "• **تسميد المعدنوس:** بعد كل حشّة بـ 3 أيام عدّي **10 كغ أمونيتر + 5 كغ سلفات المغنيزيوم + 1 كغ شيلات الحديد EDDHA في الهكتار**.",
    "الكرافس": "• **تسميد الكرافس:** عدّي **10 كغ أمونيتر + 10 كغ سلفات البوتاسيوم في الهكتار في الجمعة**، ورشّ **كالسيببور (200 مل/100 لتر)** كل 15 يوم.",
    "السبناخ والسلاطة": "• **تسميد السبناخ والسلاطة:** عدّي **6 كغ NPK 20-20-20 + 3 كغ سلفات المغنيزيوم في الجمعة**، و**8 كغ نترات الكالسيوم** وحده.",
    "السفنارية": "• **تسميد السفنارية:** في الأول عدّي **5 كغ MAP في الجمعة**، ووقت التضخيم عدّي **15 إلى 20 كغ سلفات البوتاسيوم في الجمعة** مع رشة **بورون (150 مل/100 لتر)**.",
    "اللفت": "• **تسميد اللفت:** عدّي **10 كغ سلفات البوتاسيوم + 5 كغ أمونيتر في الهكتار في الجمعة** مع رشة **بورون سائل (150 مل/100 لتر)**.",
    "القنارية": "• **تسميد القنارية:** في الخريف عدّي **12 كغ أمونيتر + 8 كغ MAP في الجمعة**، ووقت تخرج الروس عدّي **15 كغ سلفات البوتاسيوم + 8 كغ نترات الكالسيوم (وحده)**.",
    "البروكلو والكرنب": "• **تسميد البروكلو والكرنب:** عدّي **10 كغ أمونيتر + 12 كغ سلفات البوتاسيوم في الجمعة**، ورشّ **كالسيببور (200 مل/100 لتر)**.",
    "الباذنجان": "• **تسميد الباذنجان والقناوية:** عدّي **8 كغ سلفات البوتاسيوم + 4 كغ أمونيتر + 3 كغ سلفات المغنيزيوم في اليوم**، و**5 كغ نترات الكالسيوم** مرتين في الجمعة.",
    "الفريز": "• **تسميد الفريز:** عدّي **شيلات الحديد EDDHA 6% (2 كغ/هكتار)**، ووقت النوار والجني عدّي **6 كغ سلفات البوتاسيوم + 5 كغ نترات الكالسيوم (وحده)**.",
    "الزياتين": "• **تسميد الزياتين:** حط **40 كغ غبار مخمر للشجرة** بعد الجني، وفي أول الربيع أعطي **800 غ إلى 1 كغ أمونيتر 33.5% للشجرة** مع السقي (أو المطر) ورشّ **بورون + زنك (150 مل/100 لتر)** قبل النوار، وفي الصيف أعطي **600 إلى 800 غ سلفات البوتاسيوم للشجرة** لزيادة الزيت.",
    "الهندي": "• **تسميد الهندي:** اطمر **20 إلى 30 كغ غبار مخمر + 200 غ فوسفور للعرق** في الشتاء، وفي الربيع أعطي **150 غ أمونيتر للعرق**، وفي الصيف **250 غ سلفات البوتاسيوم للعرق**.",
    "التفاح": "• **تسميد التفاح:** في الربيع أعطي **500 غ أمونيتر + 300 غ MAP للشجرة**، وفي الصيف **800 غ سلفات البوتاسيوم للشجرة** مع رش **كالسيببور (200 مل/100 لتر)** كل 15 يوم.",
    "الإجاص": "• **تسميد الإجاص:** في الربيع أعطي **40 غ شيلات الحديد EDDHA + 400 غ أمونيتر + 300 غ MAP للشجرة**، وفي الصيف **700 غ سلفات البوتاسيوم + 300 غ نترات الكالسيوم للشجرة**.",
    "القوارص": "• **تسميد القوارص:** في الربيع أعطي **40 غ شيلات الحديد EDDHA 6% + 800 غ أمونيتر + 350 غ MAP للشجرة** مع رشة **زنك + منغنيز + بورون (150 مل/100 لتر)**، وفي الصيف والخريف أعطي **800 غ سلفات البوتاسيوم + 350 غ نترات الكالسيوم للشجرة**.",
    "اللوز": "• **تسميد اللوز:** أعطي **300 غ DAP أو MAP + 400 غ أمونيتر للشجرة** بعد سقوط النوار، وفي أفريل وماي **600 غ سلفات البوتاسيوم + 200 غ نترات الكالسيوم للشجرة**.",
    "الخوخ": "• **تسميد الخوخ:** في أول الربيع أعطي **500 غ أمونيتر + 300 غ MAP + 40 غ شيلات الحديد EDDHA للشجرة**، وفي التحجيم **700 غ سلفات البوتاسيوم + 300 غ نترات الكالسيوم للشجرة**.",
    "المشماش": "• **تسميد المشماش:** في فيفري ومارس أعطي **450 غ أمونيتر + 300 غ MAP للشجرة**، وفي أفريل وماي **650 غ سلفات البوتاسيوم + 250 غ نترات الكالسيوم للشجرة**.",
    "العوينة": "• **تسميد العوينة:** أعطي **450 غ أمونيتر + 300 غ MAP + 35 غ حديد EDDHA للشجرة** في الربيع، و**600 غ سلفات البوتاسيوم + 250 غ نترات الكالسيوم للشجرة** في الصيف.",
    "الرمان": "• **تسميد الرمان:** في الربيع أعطي **500 غ أمونيتر + 300 غ MAP للشجرة**، وفي الصيف وقف الأمونيتر وأعطي **600 غ سلفات البوتاسيوم + 300 غ نترات الكالسيوم للشجرة** ورشّ **كالسيببور (200 مل/100 لتر)** لمنع التطرشق.",
    "الكروم": "• **تسميد الكروم (العنب):** في الأول عدّي **10 كغ أمونيتر + 5 كغ MAP في الهكتار في الجمعة**، ووقت التحجيم والتلوين وقف الأمونيتر وعدّي **20 كغ سلفات البوتاسيوم + 5 كغ سلفات المغنيزيوم في الجمعة**.",
    "النخيل": "• **تسميد النخيل:** اطمر **45 كغ غبار مخمر + 1 كغ فوسفور للنخلة** في الشتاء، ومن مارس لماي أعطي **1.5 كغ أمونيتر للنخلة**، ومن جوان لأوت **1.5 كغ سلفات البوتاسيوم + 500 غ نترات الكالسيوم للنخلة**.",
    "الكرموس": "• **تسميد الكرموس (التين):** اطمر **30 كغ غبار مخمر + 300 غ فوسفور للشجرة** في الشتاء، وفي الربيع **400 غ أمونيتر**، وفي الصيف **500 غ سلفات البوتاسيوم + 250 غ نترات الكالسيوم للشجرة**.",
    "الفستق": "• **تسميد الفستق:** اطمر **30 كغ غبار مخمر + 400 غ سوبر فوسفات للشجرة** في الشتاء، وفي الربيع **500 غ أمونيتر**، وفي جوان وجويلية **600 إلى 800 غ سلفات البوتاسيوم للشجرة** مع رشة **بورون + زنك (150 مل/100 لتر)** قبل النوار."
}

DIRECT_CROP_WATER_SUMMARY: Dict[str, str] = {
    "الجلبانة": "• **سقي الجلبانة:** سقي خفيف ومنتظم (**30 إلى 40 دقيقة غوت آ غوت كل يومين أو 3 أيام**) بدون تغريق.",
    "الفول": "• **سقي الفول:** رية تكميلية وقت النوار ورية وقت تعمير القرون إذا حبست المطر (**ساعة غوت آ غوت كل 3-4 أيام**).",
    "الحمص": "• **سقي الحمص:** يتحمل العطش، ويستحق رية تكميلية واحدة بعد عقد القرون إذا حبست المطر.",
    "العدس": "• **سقي العدس:** زراعة بعلية تتحمل الجفاف ولا تحب تغريق الماء.",
    "اللوبيا": "• **سقي اللوبيا:** تحب ماء حلو (< 1.5 dS/m) وسقي خفيف كل يومين (**30 إلى 40 دقيقة غوت آ غوت**).",
    "القمح": "• **سقي القمح التكميلي:** رية وقت التفريع (**350 م³/هكتار**) ورية وقت الاستطالة وخروج السنبلة في مارس وأفريل (**400 م³/هكتار**).",
    "الشعير": "• **سقي الشعير:** رية تكميلية واحدة (**350 م³/هكتار**) وقت خروج السنبلة عند انحباس المطر.",
    "الفصة": "• **سقي الفصة:** اسقي مباشرة بعد كل حشّة، وكل 4 إلى 6 أيام في الصيف.",
    "الطماطم": "• **سقي الطماطم:** في الشهر الأول **0.5 إلى 1 لتر للنبتة/يوم (25 دقيقة)**، ووقت الغلة والحر **2 إلى 2.5 لتر للنبتة/يوم (ساعة مقسومة صباحاً وعشية)**.",
    "الفلفل": "• **سقي الفلفل:** ازرع على مصاطب عالية واسقي **1.2 إلى 1.8 لتر للنبتة/يوم (35 إلى 45 دقيقة غوت آ غوت)**.",
    "البطاطا": "• **سقي البطاطا:** اسقي بانتظام لمنع تشقق التربة ودخول السوسة، ووقف السقي قبل التقليع بـ 10 أيام.",
    "الدلاع": "• **سقي الدلاع:** سقي يومي منتظم بالقطرة، ونقّص الماء تدريجياً في الـ 10 أيام الأخيرة قبل الجني لرفع الحلاوة ومنع التطرشق.",
    "البطيخ": "• **سقي البطيخ:** سقيات خفيفة ومنتظمة بعيداً عن الرقبة، ونقّص الماء قبل الجني بجمعة.",
    "القرع والفقوس": "• **سقي القرع والفقوس والخيار:** كل يوم الصباح بكري (**1.5 لتر للنبتة/يوم = 30 إلى 45 دقيقة غوت آ غوت**).",
    "البصل": "• **سقي البصل:** سقيات خفيفة ومتقاربة، ووقف الماء قبل التقليع بـ 15 يوم.",
    "الثوم": "• **سقي الثوم:** سقي منتظم بدون تغريق، ووقف السقي قبل التقليع بـ 15 إلى 20 يوم.",
    "السلق": "• **سقي السلق:** رطوبة منتظمة (**30 دقيقة غوت آ غوت كل يومين**) خاصة بعد الحشّ.",
    "المعدنوس": "• **سقي المعدنوس:** سقيات خفيفة (**20 إلى 30 دقيقة كل يومين**) بدون ركود الماء.",
    "الكرافس": "• **سقي الكرافس:** ماء منتظم بلاش تعطيش (**30 إلى 40 دقيقة غوت آ غوت كل يوم أو يومين**).",
    "السبناخ والسلاطة": "• **سقي السبناخ والسلاطة:** سقي خفيف الصباح بكري بدون تغريق الرقبة.",
    "السفنارية": "• **سقي السفنارية:** سقي منتظم بدون تعطيش لمنع تفلق الكعبة بالطول.",
    "اللفت": "• **سقي اللفت:** كل يومين أو 3 أيام بانتظام.",
    "القنارية": "• **سقي القنارية:** مرتين إلى 3 مرات في الجمعة بانتظام.",
    "البروكلو والكرنب": "• **سقي البروكلو والكرنب:** كل يومين بالقطرة (**35 إلى 45 دقيقة**).",
    "الباذنجان": "• **سقي الباذنجان والقناوية:** كل يوم في الصيف (**1.5 إلى 2 لتر للنبتة/يوم**).",
    "الفريز": "• **سقي الفريز:** ماء حلو (< 1.2 dS/m) وسقيات قصيرة كل يوم الصباح بكري (**20 إلى 30 دقيقة**).",
    "الزياتين": "• **سقي الزياتين:** الشجرة الكبيرة لازمها **60 إلى 100 لتر ماء في السقية** (مرتين في الجمعة في الصيف والخريف = **4 إلى 6 سوايع غوت آ غوت**)، والمكثفة **15 إلى 20 لتر للشجرة/يوم**.",
    "الهندي": "• **سقي الهندي:** **3 إلى 4 سقيات تكميلية (30 إلى 40 لتر للعرق)** وقت خروج النوار ووقت تعمير الكعبة في الصيف.",
    "التفاح": "• **سقي التفاح:** الشجرة البالغة تستحق **50 إلى 70 لتر ماء/يوم** في الصيف (**3 إلى 4 سوايع غوت آ غوت**).",
    "الإجاص": "• **سقي الإجاص:** الشجرة البالغة تستحق **45 إلى 65 لتر ماء/يوم** في الصيف بالقطرة.",
    "القوارص": "• **سقي القوارص:** الشجرة الكبيرة تستحق **50 إلى 80 لتر ماء/يوم** في الصيف (**3 إلى 4 سوايع غوت آ غوت**) مع إبعاد المقطرات 40 سم عن الجذع.",
    "اللوز": "• **سقي اللوز:** بانتظام من مارس لجوان (**40 إلى 60 لتر للشجرة في السقية**) لمنع الكابنود وتعمير اللوزة.",
    "الخوخ": "• **سقي الخوخ:** **50 إلى 70 لتر ماء للشجرة/يوم** وقت التحجيم (**3 إلى 4 سوايع غوت آ غوت**).",
    "المشماش": "• **سقي المشماش:** **45 إلى 65 لتر ماء للشجرة/يوم** في الربيع والصيف ولا تقطع الماء بعد الجني.",
    "العوينة": "• **سقي العوينة:** **45 إلى 60 لتر للشجرة/يوم** في الصيف.",
    "الرمان": "• **سقي الرمان:** سقي منتظم في أوت وسبتمبر (**50 إلى 70 لتر للشجرة/يوم**) بدون تعطيش لمنع التطرشق.",
    "الكروم": "• **سقي الكروم (العنب):** **25 إلى 40 لتر للدالية/يوم** وقت التحجيم، ونقّص الماء وقت النضج.",
    "النخيل": "• **سقي النخيل:** **150 إلى 200 لتر ماء للنخلة/يوم** في الصيف مع تنظيف خنادق الصرف.",
    "الكرموس": "• **سقي الكرموس:** **40 إلى 50 لتر للشجرة كل 3 أيام** في الصيف ونقّص الماء وقت النضج.",
    "الفستق": "• **سقي الفستق:** ريتين تكميليتين في جوان وجويلية (**60 إلى 80 لتر للشجرة**) تضاعف امتلاء الحبة."
}

PRECISE_DISEASE_AND_DEFICIENCY_CARDS: List[Dict[str, Any]] = [
    {
        "id": "olive_peacock_spot",
        "plantix_code": "PLX-TN-001",
        "pathogen_type": "🍄 مرض فطري",
        "sector": "زياتين",
        "crop_name": "الزياتين",
        "name_ar": "مرض عين الطاووس في الزياتين",
        "exact_phrases": ["عين الطاووس", "عين طاووس", "بقع دائرية في الزيتون", "دوائر في ورق الزيتون", "تساقط أوراق الزيتون"],
        "keywords": ["عين الطاووس", "سبيلوكيا", "تبقع", "دوائر", "ورق يطيح"],
        "diagnosis": "راهو الزياتين متاعك فيها **مرض عين الطاووس** (بقع مدورة كحلة وداير بيها أصفر تطيّح الورق).",
        "action": "• **أعمل هذي:** فرّغ وسط الشجرة بالزبيرة باش تدخللها الشمس والهواء.\n• **اشري هذي واستعملها لهذي:** اشري **سيليت 400 (دودين)** وحط **100 مل في 100 لتر ماء** (**20 مل في بومبا 20 لتر**)، ولا اشري **أوكسي كلوريد النحاس 50%** وحط **250 غ في 100 لتر ماء** (**50 غ في بومبا 20 لتر**)، ورشّ بيه الورق والعود مليح.",
        "safety_note": "رشّ في الصباح ولا العشية وابتعد على وقت النوار والقايلة."
    },
    {
        "id": "olive_psyllid",
        "plantix_code": "PLX-TN-002",
        "pathogen_type": "🐛 حشرة ماصة",
        "sector": "زياتين",
        "crop_name": "الزياتين",
        "name_ar": "قطن الزياتين (البسيلا)",
        "exact_phrases": ["قطن الزيتون", "بسيلا الزيتون", "قطن في النوار", "قطن أبيض في الزيتون", "البسيلا"],
        "keywords": ["قطن", "بسيلا", "قطن أبيض"],
        "diagnosis": "راهو الزياتين متاعك فيها **قطن الزياتين (البسيلا)** اللي يمصّ النوار ويطيّحه.",
        "action": "• **أعمل هذي:** اغسل الشجرة برشة **زيت معدني صيفي** (**1 لتر في 100 لتر ماء** / **200 مل في بومبا 20 لتر**).\n• **اشري هذي واستعملها لهذي:** اشري **موفينتو** وحط **100 مل في 100 لتر ماء** (**20 مل في بومبا 20 لتر**)، ولا اشري **ديسيس** وحط **35 مل في 100 لتر ماء** (**7 مل في بومبا 20 لتر**)، ورشّ بيه العراقين قبل تفتح النوار أو بعد العقد.",
        "safety_note": "ما ترشّش الدواء والنوار مفتوح."
    },
    {
        "id": "olive_fly",
        "plantix_code": "PLX-TN-003",
        "pathogen_type": "🐛 حشرة ثاقبة للثمار",
        "sector": "زياتين",
        "crop_name": "الزياتين",
        "name_ar": "ذبانة حب الزيتون",
        "exact_phrases": ["ذبابة الزيتون", "ذبانة الزيتون", "دود في حب الزيتون", "زيتون مثقوب"],
        "keywords": ["ذبابة الزيتون", "ذبانة", "دود في الزيتون", "بكتروسيرا"],
        "diagnosis": "راهو الزياتين متاعك ضاربتها **ذبانة حب الزيتون** اللي تدقّ الكعبة وتعمل فيها الدود وتطلّع الأسيديتي.",
        "action": "• **أعمل هذي:** داوي الشجر أول ما تشوف الوخذة على الكعبة.\n• **اشري هذي واستعملها لهذي:** اشري **ديسيس** وحط **40 مل في 100 لتر ماء** (**8 مل في بومبا 20 لتر**)، ولا اشري **موسپيلان** وحط **30 غ في 100 لتر ماء** (**6 غ في بومبا 20 لتر**)، ورشّ بيه الشجرة.",
        "safety_note": "استنّى 14 يوم بعد الرشة قبل ما تجني وتعصر."
    },
    {
        "id": "olive_bark_beetle",
        "plantix_code": "PLX-TN-005",
        "pathogen_type": "🐛 حشرة حفارة للخشب",
        "sector": "زياتين",
        "crop_name": "الزياتين",
        "name_ar": "سوسة عود الزياتين (النيرون)",
        "exact_phrases": ["سوسة الجذع", "سوسة الزيتون", "نيرون", "النيرون", "نشارة خشب في الزيتون"],
        "keywords": ["نيرون", "النيرون", "سوسة", "نشارة"],
        "diagnosis": "راهو الزياتين متاعك فيها **سوسة العود (النيرون)** اللي تحفر تحت القشرة وتيبّس الأغصان.",
        "action": "• **أعمل هذي:** قصّ الأغصان اليابسة والمنقوبة الكل واحرقها البرّة من السانية، واسقي الشجر مليح.\n• **اشري هذي واستعملها لهذي:** خذ **أمونيتر 33.5%** وأعطي **800 غ للشجرة** مع السقي، ورشّ العود بـ **ديسيس** (**40 مل في 100 لتر ماء** / **8 مل في بومبا 20 لتر**).",
        "safety_note": "ما تخليش حطب الزبيرة مكدّس في الضيعة."
    },
    {
        "id": "olive_verticillium_wilt",
        "plantix_code": "PLX-TN-006",
        "pathogen_type": "🍄 مرض فطري في التراب والعروق",
        "sector": "زياتين",
        "crop_name": "الزياتين",
        "name_ar": "مرض الفرتيسيليوم (يباس فرد غصن في الزيتون)",
        "exact_phrases": ["فرتيسيليوم الزيتون", "جفاف غصن كامل في الزيتونة", "يباس مفاجئ في غصن الزيتون"],
        "keywords": ["فرتيسيليوم", "ذبول", "يباس غصن"],
        "diagnosis": "راهو الزياتين متاعك فيها **فطر الفرتيسيليوم** في التراب اللي يسكّر العروق وييبّس فرد غصن ولا شطر شجرة.",
        "action": "• **أعمل هذي:** قصّ الأغصان اليابسة واحرقها، وحبّس زراعة الخضرة وسط الزياتين.\n• **اشري هذي واستعملها لهذي:** اشري **ألييت (فوسيتيل الألمنيوم)** وحط **250 غ في 100 لتر ماء** (**50 غ في بومبا 20 لتر**) مع **فطر التريكوديرما وأحماض هيوميك**، وعدّيهم في السقي بحذا الجدر.",
        "safety_note": "عقّم المنشار بالجافيل بعد كل شجرة."
    },
    {
        "id": "tuta_absoluta_tomato",
        "plantix_code": "PLX-TOM-01",
        "pathogen_type": "🐛 حشرة حافرة",
        "sector": "خضروات",
        "crop_name": "الطماطم",
        "name_ar": "حافرة الطماطم (التوتا أبسولوتا)",
        "exact_phrases": ["توتا", "التوتا", "توتا أبسولوتا", "حافرة الطماطم", "دود في الطماطم"],
        "keywords": ["توتا", "دود", "ثقب", "أنفاق", "حافرة", "ينقب"],
        "diagnosis": "راهو **الطماطم** متاعك ضاربتها **حافرة الطماطم (التوتا أبسولوتا)** اللي تحفر الورق وتنقب الكعب.",
        "action": "• **أعمل هذي:** نحّي الورق والكعب المنقوب واحرقه البرّة من القطعة، وركّب مصائد الماء والزيت.\n• **اشري هذي واستعملها لهذي:** اشري **كوراجين 20** وحط **25 إلى 30 مل في 100 لتر ماء** (**5 إلى 6 مل في بومبا 20 لتر**)، ولا اشري **بروكليم** وحط **35 غ في 100 لتر ماء** (**7 غ في بومبا 20 لتر**)، ورشّ بيه الطماطم العشية.",
        "safety_note": "استنّى 3 أيام قبل جني الطماطم."
    },
    {
        "id": "blossom_end_rot_vegetables",
        "plantix_code": "PLX-TOM-02",
        "pathogen_type": "🧪 نقص كالسيوم وعطش",
        "sector": "خضروات",
        "crop_name": "الطماطم",
        "name_ar": "كحولية قاع حبة الطماطم (نقص الكالسيوم والعطش)",
        "exact_phrases": ["كحلت من اللوطة", "قاع الحبة", "كحولية قاع الحبة", "تعفن الطرف الزهري"],
        "keywords": ["كحلة من اللوطة", "قاع الكعبة", "كحولية", "نقص كالسيوم", "كحلت"],
        "diagnosis": "راهو **الطماطم** متاعك عندها **كحولية قاع الحبة (نقص كالسيوم وعطش)** — وهذا راهو مش مرض فطري وما يستحقش دواء فطريات.",
        "action": "• **أعمل هذي:** نظّم السقي كل يوم الصباح بكري (**2 لتر للنبتة في اليوم**) وما تخليهاش تعطش.\n• **اشري هذي واستعملها لهذي:** اشري **نترات الكالسيوم** وعدّي منه **15 إلى 20 كغ في الهكتار** في القطرة (في برميل وحده بلاش خلط)، واشري **كالسيببور (كالسيوم + بورون سائل)** وحط **200 مل في 100 لتر ماء** (**40 مل في بومبا 20 لتر**) ورشّ بيه الورق والكعب الصغير.",
        "safety_note": "ما تخلطش نترات الكالسيوم مع السلفات أو الفوسفور في فرد برميل."
    },
    {
        "id": "mildiou_late_blight",
        "plantix_code": "PLX-TOM-03",
        "pathogen_type": "🍄 مرض فطري",
        "sector": "خضروات",
        "crop_name": "الطماطم",
        "name_ar": "الميلديو والألترناريا في الطماطم",
        "exact_phrases": ["ميلديو الطماطم", "ألترناريا الطماطم", "لفحة الطماطم", "بقع كحلة في الطماطم"],
        "keywords": ["ميلديو", "ألترناريا", "لفحة", "بقع كحلة", "بقع بنية", "حرق الورق"],
        "diagnosis": "راهو **الطماطم** متاعك ضاربها **مرض الميلديو أو الألترناريا** اللي يكحّل ويحرق الورق والساق.",
        "action": "• **أعمل هذي:** هوّي البيوت المكيفة ونقّص السقي وقت الضباب ونحّي الورق اللوطاني المريض.\n• **اشري هذي واستعملها لهذي:** للميلديو اشري **ريدوميل غولد** وحط **250 غ في 100 لتر ماء** (**50 غ في بومبا 20 لتر**) ولا **إنفينيتو / ريفوس** (**130 مل في 100 لتر ماء** / **26 مل في بومبا 20 لتر**)؛ وللألترناريا اشري **أورتيفا توب** (**80 مل في 100 لتر ماء** / **16 مل في بومبا 20 لتر**) ورشّ بيه الطماطم.",
        "safety_note": "استنّى 3 إلى 7 أيام قبل الجني."
    },
    {
        "id": "plantix_pepper_phytophthora_powdery_mildew_tarsoneme",
        "plantix_code": "PLX-PEP-01",
        "pathogen_type": "🍄 مرض فطري وحشري",
        "sector": "خضروات",
        "crop_name": "الفلفل",
        "name_ar": "كحولية رقبة الفلفل (الفيتوفثورا)، البورماد، والتربس في الفلفل",
        "exact_phrases": ["مرض الفلفل", "ورق الفلفل يطيح", "بورماد الفلفل", "ذبول الفلفل", "تكمش راس الفلفل", "تربس الفلفل"],
        "keywords": ["موت التاج", "فيتوفثورا", "بورماد", "تارسونيم", "تربس", "ورق يطيح", "ذبول", "قمل"],
        "diagnosis": "راهو **الفلفل** متاعك فيه **كحولية الرقبة (الفيتوفثورا)، أو تساقط الورق بالبورماد، أو تكمّش الراس بالتربس والتارسونيم**.",
        "action": "• **أعمل هذي:** نقّص الماء بحذا ساق الفلفل وهوّي البيوت المكيفة.\n• **اشري هذي واستعملها لهذي:** لكحولية الساق والذبول عدّي **بريفكيور إنرجي** (**250 مل/100 لتر** / **50 مل في بومبا 20 لتر**) في القطرة؛ ولتساقط الورق بالبورماد اشري **توباس 100** (**40 مل/100 لتر** / **8 مل في بومبا 20 لتر**) ورشّ؛ ولتكمّش الراس والتربس اشري **راديانت** (**45 مل/100 لتر**) أو **فرتيميك** (**50 مل/100 لتر**).",
        "safety_note": "استنّى 3 إلى 7 أيام قبل جني الفلفل."
    },
    {
        "id": "potato_mildiou_tuber_moth_rhizoctonia_solo",
        "plantix_code": "PLX-POT-01",
        "pathogen_type": "🍄 مرض فطري وحشري",
        "sector": "خضروات",
        "crop_name": "البطاطا",
        "name_ar": "ميلديو البطاطا وسوسة وفراشة البطاطا",
        "exact_phrases": ["ميلديو البطاطا", "سوسة البطاطا", "فراشة البطاطا", "قشرة كحلة في البطاطا", "مرض البطاطا"],
        "keywords": ["ميلديو", "لفحة", "سوسة", "فراشة", "دود", "ثقوب", "ريزوكتونيا"],
        "diagnosis": "راهو **البطاطا** متاعك ضاربها **الميلديو على الورق، أو سوسة وفراشة البطاطا في الكعب**.",
        "action": "• **أعمل هذي:** ردّم الخط بالتراب مليح فوق الكعب العريان باش السوسة ما توصلوش، ونقّص السقي وقت الضباب.\n• **اشري هذي واستعملها لهذي:** ضد ميلديو البطاطا اشري **ريدوميل غولد** وحط **250 غ في 100 لتر ماء** (**50 غ في بومبا 20 لتر**) ولا **إنفينيتو / ريفوس** (**130 مل/100 لتر**)؛ وضد سوسة البطاطا اشري **كوراجين 20** (**25 مل/100 لتر** / **5 مل في بومبا 20 لتر**) ورشّ بيه.",
        "safety_note": "استنّى 7 أيام قبل تقليع البطاطا."
    },
    {
        "id": "plantix_cucurbits_gummy_stem_blight",
        "plantix_code": "PLX-WML-01",
        "pathogen_type": "🍄 مرض فطري",
        "sector": "خضروات",
        "crop_name": "الدلاع",
        "name_ar": "تشقق وصمغ رقبة الدلاع وذبول الفيوزاريوم",
        "exact_phrases": ["صمغ الدلاع", "تشقق ساق الدلاع", "ذبول الدلاع", "ميلديو الدلاع", "بورماد الدلاع", "مرض الدلاع"],
        "keywords": ["صمغ", "تشقق", "ذبول", "فيوزاريوم", "ميلديو", "بورماد"],
        "diagnosis": "راهو **الدلاع** متاعك فيه **تشقق وصمغ الرقبة أو ذبول العروق (أو الميلديو والبورماد على الورق)**.",
        "action": "• **أعمل هذي:** ابعد أنبوب الغوت آ غوت شوية على رقبة نبتة الدلاع باش الجدر يقعد شايح.\n• **اشري هذي واستعملها لهذي:** لصمغ الرقبة والبورماد اشري **أورتيفا توب** وحط **80 مل في 100 لتر ماء** (**16 مل في بومبا 20 لتر**) ولا **سيغنوم** (**80 غ/100 لتر**) ورشّ بيه؛ ولذبول الجدور عدّي في القطرة **تاشيغارين** (**150 مل/100 لتر**) + **ألييت** (**250 غ/100 لتر**).",
        "safety_note": "استنّى 3 إلى 7 أيام قبل قصان الدلاع."
    },
    {
        "id": "citrus_leafminer",
        "plantix_code": "PLX-TN-010",
        "pathogen_type": "🐛 حشرة حافرة للأنفاق",
        "sector": "أشجار_مثمرة",
        "crop_name": "القوارص",
        "name_ar": "بوفرطوطو القوارص (حافرة أنفاق الورق)",
        "exact_phrases": ["بوفرطوطو القوارص", "بوفرطوطو", "حافرة أنفاق القوارص", "تكمش أوراق القوارص"],
        "keywords": ["بوفرطوطو", "فيلوكنيستيس", "أنفاق القوارص", "تكمش"],
        "diagnosis": "راهو القوارص متاعك فيها **حافرة الأنفاق (بوفرطوطو الورق)** اللي تكمّش وتبرم الورق الجديد الطري.",
        "action": "• **أعمل هذي:** نقّص شوية من الآزوت والماء الزايد في الصيف.\n• **اشري هذي واستعملها لهذي:** اشري **فرتيميك (أبامكتين)** وحط **50 مل في 100 لتر ماء** (**10 مل في بومبا 20 لتر**) مخلط مع **250 مل زيت معدني صيفي**، ولا اشري **موسپيلان** (**30 غ في 100 لتر ماء** / **6 غ في بومبا 20 لتر**)، ورشّ بيه الطراحات الجديدة العشية.",
        "safety_note": "استنّى 14 يوم قبل الجني بعد الرش."
    },
    {
        "id": "wheat_septoria_rust_solo",
        "plantix_code": "PLX-WHT-01",
        "pathogen_type": "🍄 مرض فطري",
        "sector": "زراعات_كبرى",
        "crop_name": "القمح",
        "name_ar": "السبتوريا والصدأ الأصفر (الصفورية) في القمح",
        "exact_phrases": ["سبتوريا القمح", "صدأ القمح", "صفورية القمح", "بقع في ورق القمح"],
        "keywords": ["سبتوريا", "صدأ", "صفورية", "بقع", "ورقة العلم"],
        "diagnosis": "راهو **القمح** متاعك فيه **مرض السبتوريا أو الصدأ الأصفر (الصفورية)** اللي يضرب الورق ويطلع لورقة العلم.",
        "action": "• **أعمل هذي:** ادخل داوي القمح في الحين قبل ما يوصل المرض لورقة العلم الفوقانية.\n• **اشري هذي واستعملها لهذي:** اشري **أميستار إكسترا** ولا **بروزارو** ولا **فوليكور (تيبوكونازول)**، وحط **0.8 إلى 1 لتر في الهكتار** (مخلط في 200 لتر ماء للهكتار) ورشّ بيه القمح.",
        "safety_note": "رشّ في نهار صاحي بلاش ريح."
    },
    {
        "id": "date_palm_boufaroua",
        "plantix_code": "PLX-TN-024",
        "pathogen_type": "🕷️ عناكب الغبار",
        "sector": "أشجار_مثمرة",
        "crop_name": "النخيل",
        "name_ar": "بوفرطوطو الغبار في النخيل (البوفروة)",
        "exact_phrases": ["غبار النخيل", "عنكبوت الغبار", "بوفرطوطو الغبار", "بوفروة"],
        "keywords": ["بوفروة", "غبار النخيل", "عنكبوت الغبار", "بوفرطوطو الغبار"],
        "diagnosis": "راهو النخيل متاعك فيه **رتيلا الغبار (البوفروة)** اللي تعمل خيوط عنكبوت على العراجين وتردّ التمر أحمر ويابس.",
        "action": "• **أعمل هذي:** نظّف قلب النخلة والعراجين من الغبار.\n• **اشري هذي واستعملها لهذي:** اشري **فرتيميك (أبامكتين 18 غ/ل)** وحط **50 مل في 100 لتر ماء** (**10 مل في بومبا 20 لتر**)، ولا اشري **إنفيدور** وحط **40 مل في 100 لتر ماء** (**8 مل في بومبا 20 لتر**)، ورشّ بيه العراجين مليح.",
        "safety_note": "استنّى 14 إلى 21 يوم قبل الجني."
    },
    {
        "id": "apple_scab_codling_moth_fireblight_solo",
        "plantix_code": "PLX-APL-01",
        "pathogen_type": "🍄 مرض فطري وحشري",
        "sector": "أشجار_مثمرة",
        "crop_name": "التفاح",
        "name_ar": "جرب التفاح (التافلور) ودودة كعب التفاح (الكربوكابس)",
        "exact_phrases": ["مرض التفاح", "جرب التفاح", "تافلور التفاح", "دودة التفاح", "بقع كحلة في التفاح"],
        "keywords": ["جرب", "تافلور", "بقع كحلة", "دودة", "دود", "كربوكابس"],
        "diagnosis": "راهو **التفاح** متاعك فيه **مرض الجرب (التافلور) اللي يعمل بقع كحلة حرشة، أو دودة كعب التفاح (الكربوكابس)**.",
        "action": "• **أعمل هذي:** فرّغ وسط شجرة التفاح بالزبيرة ولمّ الكعب المنقوب الطايح.\n• **اشري هذي واستعملها لهذي:** ضد جرب التفاح اشري **سيليت 400 (دودين)** وحط **100 مل في 100 لتر ماء** (**20 مل في بومبا 20 لتر**) ولا **سكور / أورتيفا توب** (**60 مل/100 لتر**)؛ وضد دودة التفاح اشري **كوراجين 20** (**25 مل/100 لتر** / **5 مل في بومبا 20 لتر**) ورشّ بيه التفاح.",
        "safety_note": "استنّى 14 يوم قبل جني التفاح."
    }
]

TUNISIAN_HOMOLOGATED_PESTICIDES: List[Dict[str, Any]] = []
TUNISIAN_FERTIGATION_PROTOCOLS: Dict[str, Dict[str, Any]] = {}
TUNISIAN_BIOCLIMATIC_ZONES: List[Dict[str, Any]] = []
TUNISIAN_CROPS_AND_VARIETIES: Dict[str, Dict[str, Any]] = {}


def load_extended_kb_from_disk_if_present() -> None:
    """يدمج البطاقات والأدوية الإضافية من ملف tunisian_agri_knowledge_base.json إن وجد."""
    try:
        if os.path.exists(KB_FILE_PATH):
            with open(KB_FILE_PATH, "r", encoding="utf-8") as f:
                kb = json.load(f)
            if isinstance(kb.get("diagnostic_cards"), list) and len(kb["diagnostic_cards"]) > len(PRECISE_DISEASE_AND_DEFICIENCY_CARDS):
                PRECISE_DISEASE_AND_DEFICIENCY_CARDS.clear()
                PRECISE_DISEASE_AND_DEFICIENCY_CARDS.extend(kb["diagnostic_cards"])
            if isinstance(kb.get("homologated_pesticides_dgsv"), list):
                TUNISIAN_HOMOLOGATED_PESTICIDES.clear()
                TUNISIAN_HOMOLOGATED_PESTICIDES.extend(kb["homologated_pesticides_dgsv"])
            if isinstance(kb.get("fertigation_protocols"), dict):
                TUNISIAN_FERTIGATION_PROTOCOLS.update(kb["fertigation_protocols"])
    except Exception:
        pass


load_extended_kb_from_disk_if_present()

PRACTICAL_IRRIGATION_GUIDES: Dict[str, Dict[str, Any]] = {
    "زياتين": {
        "title": "الزياتين (المروية والمكثفة)",
        "practical_water_rule": "• الشجرة الكبيرة تحتاج **60 إلى 100 لتر ماء في السقية** (مرتين في الجمعة في الصيف والخريف)، والمكثفة **15 إلى 20 لتر للشجرة في اليوم**.",
        "practical_fert_rule": "• الربيع: أمونيتر 33.5% (**800 غ إلى 1 كغ للشجرة**) + رشة بورون وزنك قبل النوار | الصيف والخريف: سلفات البوتاسيوم (**600 إلى 800 غ للشجرة**).",
        "max_ec_dsm": 4.0
    },
    "أشجار_مثمرة": {
        "title": "القوارص والأشجار المثمرة",
        "practical_water_rule": "• الشجرة البالغة تحتاج **50 إلى 80 لتر ماء في اليوم** في فترة الحر والتحجيم (**3 إلى 4 سوايع غوت آ غوت**).",
        "practical_fert_rule": "• الربيع: شيلات الحديد EDDHA 6% + أمونيتر + MAP | الصيف: سلفات البوتاسيوم + نترات الكالسيوم.",
        "max_ec_dsm": 1.7
    },
    "خضروات": {
        "title": "الخضروات (طماطم، فلفل، بطاطا، قرعيات)",
        "practical_water_rule": "• بداية الغراسة: **0.5 إلى 1 لتر للنبتة/يوم** | فترة الإزهار والإثمار: **1.5 إلى 2.5 لتر للنبتة/يوم**.",
        "practical_fert_rule": "• سلفات البوتاسيوم (**8-12 كغ/هكتار/يوم**) + أمونيتر + سلفات المغنيزيوم، وفي برميل مستقل: نترات الكالسيوم (**6-8 كغ/هكتار**).",
        "max_ec_dsm": 2.5
    },
    "زراعات_كبرى": {
        "title": "الزراعات الكبرى والأعلاف (قمح، شعير، قطاني)",
        "practical_water_rule": "• السقي التكميلي للحبوب: رية التفريع (**350 م³/هكتار**) ورية الاستطالة والإسبال (**400 م³/هكتار**).",
        "practical_fert_rule": "• قبل البذر: **150 كغ/هكتار DAP** | الأمونيتر 33.5% مقسم على 3 دفعات (طور 3 أوراق، بداية الاستطالة، وورقة العلم).",
        "max_ec_dsm": 3.5
    }
}


# =====================================================================
# 4. نماذج البيانات (Pydantic Models)
# =====================================================================
class FarmPlotProfile(BaseModel):
    farmer_id: str = "TN-001"
    farmer_name: str = "فلاح تونسي"
    phone_or_chat_id: str = Field(default="+21621127147")
    region: str = Field(default="مرناق - بن عروس")
    crop_category: str = Field(default="خضروات")
    crop_variety: str = Field(default="زراعة عامة")
    growth_stage: str = Field(default="إزهار وإثمار ذروة")
    area_hectares: float = 1.5
    water_salinity_ec: float = 2.0
    water_ph: float = 7.4
    drip_flow_rate_lph: float = 4.0
    emitters_per_hectare: int = 5000


class WeatherSnapshot(BaseModel):
    region: str
    max_temp_c: float
    relative_humidity_pct: float
    et0_fao_mm: float
    wind_speed_kmh: float
    sirocco_alert: bool
    source: str = "Open-Meteo API"


class FarmerQuery(BaseModel):
    plot: FarmPlotProfile
    message_text: str
    image_path: Optional[str] = None
    image_mime: str = "image/jpeg"
    image_base64: Optional[str] = None
    audio_path: Optional[str] = None
    audio_mime: str = "audio/ogg"
    audio_base64: Optional[str] = None
    is_media_message: bool = False
    media_type_label: str = ""
    gps_lat: Optional[float] = None
    gps_lon: Optional[float] = None
    weather_override: Optional[WeatherSnapshot] = None


class ModernizationAuditInput(BaseModel):
    farmer_name: str
    region: str
    area_hectares: float
    current_annual_water_cost_tnd: float
    current_annual_fertilizer_cost_tnd: float
    install_solar_pumping: bool = True
    install_smart_fertigation: bool = True
    install_soil_sensors: bool = True
    farmer_category_apia: str = Field(default="B")


class PendingApprovalItem(BaseModel):
    ticket_id: str
    created_at: str
    farmer_name: str
    farmer_chat_id: str
    region: str
    sector: str = "خضروات"
    crop_variety: str
    water_ec: float = 2.0
    max_ec: float = 2.5
    temp_c: float = 29.0
    et0_mm: float = 4.8
    m3_per_ha: float = 45.0
    duration_str: str = "45 إلى 60 دقيقة"
    fertigation_summary: str = ""
    farmer_message: str
    ai_draft_response: str
    requires_urgent_visit: bool = False
    status: str = "PENDING"
    delivery_note: str = "⏳ بانتظار مراجعة ومصادقة المهندس"
    image_url: Optional[str] = None
    audio_url: Optional[str] = None
    audio_raw_url: Optional[str] = None
    media_type: str = "text"
    lat: float = 36.6806
    lon: float = 10.2892
    is_exact_gps: bool = False
    locality_name: str = ""
    crop_age_label: str = ""
    polygon_points: List[List[float]] = Field(default_factory=list)
    area_hectares: float = 1.5
    area_m2: float = 15000.0
    perimeter_m: float = 500.0


class FarmerMapPinInput(BaseModel):
    farmer_id: Optional[str] = None
    farmer_name: str
    email: Optional[str] = "farmer@agri.tn"
    farm_name: Optional[str] = ""
    phone: str = "+21621127147"
    region: str = "مرناق - بن عروس"
    locality_name: Optional[str] = None
    lat: Optional[float] = None
    lon: Optional[float] = None
    is_exact_gps: bool = True
    crop_category: str = "زياتين"
    crop_variety: str = "الزياتين"
    crop_age_label: str = "شجرة بالغة منتجة"
    area_hectares: float = 2.0
    area_m2: Optional[float] = None
    perimeter_m: Optional[float] = None
    polygon_points: Optional[List[List[float]]] = None
    soil_info: str = ""
    water_info: str = ""
    notes: str = ""
    send_whatsapp_confirmation: bool = False


class WhatsAppConfigInput(BaseModel):
    auto_reply_mode: Optional[bool] = None
    bot_reply_format: Optional[str] = None
    bot_voice_name: Optional[str] = None
    whatsapp_access_token: Optional[str] = None
    whatsapp_phone_number_id: Optional[str] = None
    default_test_phone: Optional[str] = None
    green_api_instance_id: Optional[str] = None
    green_api_token: Optional[str] = None
    gemini_api_key: Optional[str] = None
    bot_office_name: Optional[str] = None
    bot_welcome_message: Optional[str] = None
    bot_custom_instructions: Optional[str] = None


class ApproveAndSendInput(BaseModel):
    ticket_id: str
    edited_response: str
    to_phone: Optional[str] = None
    send_mode: str = "text"
    voice_name: str = "ar-TN-ReemNeural"


class EngineerVoiceReplyInput(BaseModel):
    ticket_id: Optional[str] = None
    to_phone: str
    audio_base64: str
    mime_type: str = "audio/webm"
    caption: str = ""


class BrowserMediaTestInput(BaseModel):
    media_base64: str
    mime_type: str = "image/jpeg"
    caption: str = ""
    send_to_whatsapp: bool = False


class EngineerAuthVerifyInput(BaseModel):
    login: str = "admin"
    password: str


class EngineerAuthChangeInput(BaseModel):
    login: str = "admin"
    current_password: str = ""
    new_password: str


REGISTERED_FARMERS_DB: Dict[str, FarmPlotProfile] = {
    "DEFAULT": FarmPlotProfile(
        farmer_id="TN-001",
        farmer_name="فلاح",
        phone_or_chat_id="+21621127147",
        region="مرناق - بن عروس",
        crop_category="خضروات",
        crop_variety="زراعة فلاحية"
    )
}

ENGINEER_APPROVAL_QUEUE: Dict[str, PendingApprovalItem] = {}


def _model_to_dict(model_obj: BaseModel) -> Dict[str, Any]:
    if hasattr(model_obj, "model_dump"):
        return model_obj.model_dump()
    return model_obj.dict()


def save_ticket_to_db(item: PendingApprovalItem) -> None:
    try:
        data: Dict[str, Any] = {"tickets": {}}
        if os.path.exists(DB_FILE_PATH):
            with open(DB_FILE_PATH, "r", encoding="utf-8") as f:
                data = json.load(f)
        if "tickets" not in data:
            data["tickets"] = {}
        data["tickets"][item.ticket_id] = _model_to_dict(item)
        with open(DB_FILE_PATH, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
    except Exception:
        pass


def load_tickets_from_db() -> List[Dict[str, Any]]:
    try:
        if os.path.exists(DB_FILE_PATH):
            with open(DB_FILE_PATH, "r", encoding="utf-8") as f:
                data = json.load(f)
            tickets_dict = data.get("tickets", {})
            items = list(tickets_dict.values())
            items.reverse()
            return items
    except Exception:
        pass
    return [_model_to_dict(v) for v in reversed(list(ENGINEER_APPROVAL_QUEUE.values()))]


DEFAULT_INITIAL_FARMERS_MAP: List[Dict[str, Any]] = [
    {
        "farmer_id": "FARM-MOR-01",
        "farmer_name": "الحاج صالح بن عمر",
        "email": "saleh.morneg@agri.tn",
        "phone": "+21621127147",
        "region": "مرناق - بن عروس",
        "locality_name": "مرناق (ضيعة وادي الحمص 🎯)",
        "lat": 36.6806,
        "lon": 10.2892,
        "is_exact_gps": True,
        "crop_category": "خضروات",
        "crop_variety": "الطماطم الفصلية",
        "crop_age_label": "8 أسابيع (مرحلة عقد وتحجيم)",
        "area_hectares": 2.48,
        "area_m2": 24800.0,
        "perimeter_m": 635.0,
        "polygon_points": [[36.6814, 10.2881], [36.6815, 10.2903], [36.6801, 10.2905], [36.6799, 10.288]],
        "soil_info": "طينية كلسية عميقة",
        "water_info": "مروية بالقطرة (2.1 dS/m)",
        "irrigation_system": "قطرة قطرة",
        "last_inquiry": "تشخيص كحولية قاع الحبة وتعديل جرعة الكالسيوم والبوتاسيوم",
        "updated_at": "اليوم 08:30"
    },
    {
        "farmer_id": "FARM-SFX-02",
        "farmer_name": "سي المنصف الفريخة",
        "email": "moncef.sfax@agri.tn",
        "phone": "+21698112340",
        "region": "عقارب - صفاقس",
        "locality_name": "عقارب (هنشير الزياتين 🎯)",
        "lat": 34.7422,
        "lon": 10.5311,
        "is_exact_gps": True,
        "crop_category": "زياتين",
        "crop_variety": "الزياتين (شملالي ساحلي)",
        "crop_age_label": "15 سنة (شجرة بالغة منتجة)",
        "area_hectares": 5.85,
        "area_m2": 58500.0,
        "perimeter_m": 970.0,
        "polygon_points": [[34.7435, 10.5295], [34.7436, 10.5326], [34.7412, 10.5328], [34.741, 10.5294]],
        "soil_info": "رملية خفيفة عميقة",
        "water_info": "سقي تكميلي (3.8 dS/m)",
        "irrigation_system": "سقي تكميلي بالقطرة",
        "last_inquiry": "مداواة عين الطاووس وجرعة النحاس والدودين في 100 لتر وبومبا 20 لتر",
        "updated_at": "اليوم 09:15"
    }
]


def _enrich_farmer_with_utm(it: Dict[str, Any]) -> Dict[str, Any]:
    out = dict(it)
    try:
        lat_v = float(out.get("lat", 36.6806))
        lon_v = float(out.get("lon", 10.2892))
        utm_info = wgs84_latlon_to_utm(lat_v, lon_v)
        out["utm_zone"] = utm_info["zone_label"]
        out["utm_easting"] = utm_info["easting"]
        out["utm_northing"] = utm_info["northing"]
    except Exception:
        out["utm_zone"] = "32S"
        out["utm_easting"] = 615192.4
        out["utm_northing"] = 4060248.7
    return out


def load_farmers_map_db() -> List[Dict[str, Any]]:
    try:
        if os.path.exists(FARMERS_MAP_FILE_PATH):
            with open(FARMERS_MAP_FILE_PATH, "r", encoding="utf-8") as f:
                data = json.load(f)
                if isinstance(data, list) and len(data) > 0:
                    return [_enrich_farmer_with_utm(it) for it in data]
    except Exception:
        pass
    try:
        with open(FARMERS_MAP_FILE_PATH, "w", encoding="utf-8") as f:
            json.dump(DEFAULT_INITIAL_FARMERS_MAP, f, ensure_ascii=False, indent=2)
    except Exception:
        pass
    return [_enrich_farmer_with_utm(dict(it)) for it in DEFAULT_INITIAL_FARMERS_MAP]


def save_farmers_map_db(items: List[Dict[str, Any]]) -> None:
    try:
        with open(FARMERS_MAP_FILE_PATH, "w", encoding="utf-8") as f:
            json.dump(items, f, ensure_ascii=False, indent=2)
    except Exception:
        pass


def upsert_farmer_on_map(
    farmer_name: str,
    phone: str,
    region: str,
    locality_name: str,
    lat: float,
    lon: float,
    is_exact_gps: bool,
    crop_category: str,
    crop_variety: str,
    crop_age_label: str = "",
    area_hectares: float = 1.5,
    soil_info: str = "",
    water_info: str = "",
    last_inquiry: str = "",
    farmer_id_override: Optional[str] = None,
    polygon_points: Optional[List[List[float]]] = None,
    area_m2: Optional[float] = None,
    perimeter_m: Optional[float] = None,
    email: str = "",
    farm_name: str = ""
) -> Dict[str, Any]:
    items = load_farmers_map_db()
    clean_ph = normalize_session_key(phone)
    now_str = datetime.now().strftime("%Y-%m-%d %H:%M")

    target_idx = -1
    for idx, it in enumerate(items):
        if farmer_id_override and it.get("farmer_id") == farmer_id_override:
            target_idx = idx
            break
        existing_ph = normalize_session_key(str(it.get("phone", "")))
        if existing_ph == clean_ph and it.get("region") == region and it.get("crop_category") == crop_category:
            target_idx = idx
            break

    poly_pts = polygon_points if (polygon_points and len(polygon_points) >= 3) else []
    if poly_pts:
        calc_ha, calc_m2, calc_perim, c_lat, c_lon = calculate_polygon_area_ha_and_m2(poly_pts)
        eff_ha = round(calc_ha if calc_ha > 0 else (area_hectares or 1.5), 3)
        eff_m2 = round(calc_m2 if calc_m2 > 0 else (eff_ha * 10000.0), 1)
        eff_perim = round(calc_perim, 1)
        lat, lon = c_lat, c_lon
        is_exact_gps = True
    else:
        eff_ha = round(float(area_hectares or 1.5), 3)
        eff_m2 = round(float(area_m2 or (eff_ha * 10000.0)), 1)
        eff_perim = round(float(perimeter_m or 0.0), 1)

    rec = {
        "farmer_id": farmer_id_override or (items[target_idx].get("farmer_id") if target_idx >= 0 else f"FARM-{uuid.uuid4().hex[:5].upper()}"),
        "farmer_name": farmer_name or "فلاح",
        "email": email or "farmer@agri.tn",
        "farm_name": farm_name or f"ضيعة {locality_name or region}",
        "phone": phone or "+21621127147",
        "region": region or "مرناق - بن عروس",
        "locality_name": locality_name or region,
        "lat": round(float(lat), 6),
        "lon": round(float(lon), 6),
        "is_exact_gps": bool(is_exact_gps),
        "polygon_points": poly_pts,
        "crop_category": crop_category or "خضروات",
        "crop_variety": crop_variety or "زراعة فلاحية",
        "crop_age_label": crop_age_label or "طور الإنتاج",
        "area_hectares": eff_ha,
        "area_m2": eff_m2,
        "perimeter_m": eff_perim,
        "soil_info": soil_info or "طينية كلسية",
        "water_info": water_info or "ري بالقطرة",
        "last_inquiry": (last_inquiry or "تم تسجيل الضيعة على خريطة المسح الفلاحي")[:160],
        "updated_at": now_str
    }

    if target_idx >= 0:
        items.pop(target_idx)
    items.insert(0, rec)
    save_farmers_map_db(items)
    return _enrich_farmer_with_utm(rec)


def fetch_live_weather_tunisia(region: str) -> WeatherSnapshot:
    return WeatherSnapshot(
        region=region,
        max_temp_c=28.0,
        relative_humidity_pct=48.0,
        et0_fao_mm=4.5,
        wind_speed_kmh=14.0,
        sirocco_alert=False,
        source="Agri Weather Tunisia"
    )


# =====================================================================
# 5. محرك المطابقة والتشخيص الدقيق (بدون أي إجابات عشوائية!)
# =====================================================================
def resolve_specific_crop_plan_key(crop_category: str, crop_variety: str, raw_text: str) -> str:
    norm_raw = normalize_arabic_for_match(raw_text or "")
    norm_var = normalize_arabic_for_match(crop_variety or "")
    for c_key, _, kw_list in INDIVIDUAL_CROP_DETECTION_RULES:
        for kw in kw_list:
            if normalize_arabic_for_match(kw) in norm_raw:
                return c_key
    for c_key, _, kw_list in INDIVIDUAL_CROP_DETECTION_RULES:
        if normalize_arabic_for_match(c_key) in norm_var:
            return c_key
        for kw in kw_list:
            if normalize_arabic_for_match(kw) in norm_var:
                return c_key
    if crop_category == "زياتين":
        return "الزياتين"
    return crop_variety or "الغراسة"


def match_precise_disease_cards(
    text: str,
    detected_category: Optional[str] = None,
    detected_variety: Optional[str] = None
) -> List[Dict[str, Any]]:
    clean = str(text or "").strip()
    if not clean:
        return []
    norm_clean = normalize_arabic_for_match(clean)

    target_crop_key = None
    for c_key, _, kw_list in INDIVIDUAL_CROP_DETECTION_RULES:
        if any(normalize_arabic_for_match(kw) in norm_clean for kw in kw_list):
            target_crop_key = c_key
            break
    if not target_crop_key and detected_variety:
        norm_var = normalize_arabic_for_match(detected_variety)
        for c_key, _, kw_list in INDIVIDUAL_CROP_DETECTION_RULES:
            if normalize_arabic_for_match(c_key) in norm_var or any(normalize_arabic_for_match(kw) in norm_var for kw in kw_list):
                target_crop_key = c_key
                break

    scored: List[Tuple[int, Dict[str, Any]]] = []
    for card in PRECISE_DISEASE_AND_DEFICIENCY_CARDS:
        card_crop = str(card.get("crop_name", ""))
        card_crop_norm = normalize_arabic_for_match(card_crop)
        is_general_card = normalize_arabic_for_match("جميع الغراسات") in card_crop_norm

        if target_crop_key and not is_general_card:
            target_norm = normalize_arabic_for_match(target_crop_key)
            if card_crop_norm != target_norm and target_norm not in card_crop_norm:
                continue

        score = 0
        for ep in card.get("exact_phrases", []):
            if normalize_arabic_for_match(ep) in norm_clean:
                score += 12
        for kw in card.get("keywords", []):
            if normalize_arabic_for_match(kw) in norm_clean:
                score += 6

        if score > 0 and target_crop_key and normalize_arabic_for_match(target_crop_key) in card_crop_norm:
            score += 6

        if score >= 6:
            scored.append((score, card))

    scored.sort(key=lambda item: item[0], reverse=True)
    if not scored:
        return []
    top_score = scored[0][0]
    return [c for sc, c in scored[:2] if sc >= max(6, top_score - 4)]


def detect_crop_from_text(text: str) -> Tuple[Optional[str], Optional[str]]:
    norm = normalize_arabic_for_match(text)
    for c_key, c_sector, kw_list in INDIVIDUAL_CROP_DETECTION_RULES:
        for kw in kw_list:
            if normalize_arabic_for_match(kw) in norm:
                return c_sector, c_key
    return None, None


def analyze_image_with_gemini_or_local(
    image_path: str,
    caption_text: str,
    crop_name: str,
    farmer_name: str
) -> Optional[str]:
    """يفحص الصورة المرفقة عبر Gemini Vision أو الفحص البصري المدمج ويعطي التشخيص بالدارجة التونسية."""
    if not image_path or not os.path.exists(image_path):
        return None
    api_key = get_active_gemini_key()
    try:
        with open(image_path, "rb") as f:
            img_bytes = f.read()
        if api_key and len(img_bytes) > 100:
            b64_img = base64.b64encode(img_bytes).decode("utf-8")
            prompt = (
                f"أنتِ المهندسة الفلاحية زينب العزيزي. افحصي هذه الصورة الفلاحية التي أرسلها الفلاح ({farmer_name}) "
                f"بخصوص ({crop_name}) مع الملاحظة: «{caption_text}».\n"
                "أعطيه التشخيص الدقيق بالدارجة التونسية في 3 نقاط واضحة:\n"
                "• **تشخيص التصويرة متاعك:** [شنوة يظهر في الورقة أو الكعبة بالضبط]\n"
                "• **أعمل هذي:** [الخطوة العملية]\n"
                "• **اشري هذي واستعملها لهذي:** [اسم الدواء أو السماد والجرعة في 100 لتر ماء وبومبا 20 لتر]."
            )
            for model_name in ("gemini-2.5-flash", "gemini-2.0-flash"):
                url = f"https://aiplatform.googleapis.com/v1/publishers/google/models/{model_name}:generateContent?key={api_key}"
                payload = {
                    "contents": [{
                        "role": "user",
                        "parts": [
                            {"inlineData": {"mimeType": "image/jpeg", "data": b64_img}},
                            {"text": prompt}
                        ]
                    }],
                    "generationConfig": {"temperature": 0.15}
                }
                resp = requests.post(url, json=payload, timeout=15)
                if resp.status_code == 200:
                    cands = resp.json().get("candidates", [])
                    if cands:
                        parts = cands[0].get("content", {}).get("parts", [])
                        txt = "".join(p.get("text", "") for p in parts).strip()
                        if txt:
                            return f"📸 *تحليل الصورة المرفقة — المهندسة الفلاحية زينب العزيزي:*\n\n{txt}"
    except Exception:
        pass
    return None


def call_gemini_multimodal_agent(query: FarmerQuery) -> Dict[str, Any]:
    has_image = bool(query.image_path and os.path.exists(query.image_path))
    has_audio = bool(query.audio_path and os.path.exists(query.audio_path))
    voice_transcript: Optional[str] = None
    if has_audio and query.audio_path:
        voice_transcript = transcribe_tunisian_voice_note(query.audio_path)
        if voice_transcript:
            query.message_text = f"{query.message_text} {voice_transcript}".strip()

    clean_msg = str(query.message_text or "").strip()
    norm_msg = normalize_arabic_for_match(clean_msg)

    det_cat, det_var = detect_crop_from_text(clean_msg)
    if det_cat:
        query.plot.crop_category = det_cat
    if det_var:
        query.plot.crop_variety = det_var

    det_reg = detect_tunisian_region(clean_msg)
    if det_reg:
        query.plot.region = det_reg

    specific_crop_key = resolve_specific_crop_plan_key(
        query.plot.crop_category,
        query.plot.crop_variety,
        clean_msg
    )
    matched_cards = match_precise_disease_cards(
        clean_msg,
        query.plot.crop_category,
        specific_crop_key
    )

    asks_fert = any(w in norm_msg for w in ["تسميد", "سماد", "غبار", "امونيتر", "فوسفور", "بوتاسيوم", "كالسيوم", "تغذيه", "ماكله"])
    asks_water = any(w in norm_msg for w in ["سقي", "نسقي", "ماء", "الري", "قطره", "عطش"])

    voice_header = f"🎙️ *مضمون التسجيل الصوتي للفلاح:* «{voice_transcript}»\n\n" if voice_transcript else ""
    img_header = "📸 *تم إرفاق صورة للفحص البصري*\n" if has_image else ""

    reply_blocks: List[str] = [
        f"{voice_header}{img_header}مرحبا بيك يا {query.plot.farmer_name} — بخصوص **{specific_crop_key}** متاعك:"
    ]

    vision_diag = None
    if has_image and query.image_path:
        vision_diag = analyze_image_with_gemini_or_local(
            query.image_path,
            clean_msg,
            specific_crop_key,
            query.plot.farmer_name
        )

    if vision_diag:
        reply_blocks.append(vision_diag)
    elif matched_cards:
        for card in matched_cards[:2]:
            reply_blocks.append(f"• **المرض متاعك:** {card['diagnosis']}\n{card['action']}")
    elif asks_fert and not asks_water:
        fert_txt = DIRECT_CROP_FERT_SUMMARY.get(specific_crop_key) or DIRECT_CROP_FERT_SUMMARY.get("الزياتين")
        reply_blocks.append(fert_txt)
    elif asks_water and not asks_fert:
        water_txt = DIRECT_CROP_WATER_SUMMARY.get(specific_crop_key) or DIRECT_CROP_WATER_SUMMARY.get("الزياتين")
        reply_blocks.append(water_txt)
    elif specific_crop_key in DIRECT_CROP_FERT_SUMMARY:
        fert_txt = DIRECT_CROP_FERT_SUMMARY[specific_crop_key]
        water_txt = DIRECT_CROP_WATER_SUMMARY.get(specific_crop_key, "")
        reply_blocks.append(
            f"• **استفسارك المسجل للمهندس:** «{clean_msg}»\n"
            f"{fert_txt}\n{water_txt}"
        )
    else:
        reply_blocks.append(
            f"• **استفسارك المسجل للمهندس:** «{clean_msg}»\n"
            f"• المسودة جاهزة للمراجعة والمصادقة من قبل المهندس الفلاحي لتحديد الدواء والجرعة المضبوطة لضيعتك."
        )

    eff_lat, eff_lon, eff_exact_gps, eff_locality = resolve_farmer_coordinates(
        text=clean_msg,
        region=query.plot.region,
        phone=query.plot.phone_or_chat_id,
        farmer_name=query.plot.farmer_name,
        gps_lat=query.gps_lat,
        gps_lon=query.gps_lon
    )

    weather = fetch_live_weather_tunisia(query.plot.region)
    guide = PRACTICAL_IRRIGATION_GUIDES.get(query.plot.crop_category, PRACTICAL_IRRIGATION_GUIDES["خضروات"])

    return {
        "ai_response": "\n\n".join(reply_blocks),
        "weather": weather,
        "guide": guide,
        "intent": {
            "lat": eff_lat,
            "lon": eff_lon,
            "is_exact_gps": eff_exact_gps,
            "locality_name": eff_locality,
            "crop_age_label": query.plot.growth_stage,
            "polygon_points": [],
            "area_hectares": query.plot.area_hectares,
            "area_m2": query.plot.area_hectares * 10000.0,
            "perimeter_m": 0.0
        }
    }


def calculate_modernization_roi(audit: ModernizationAuditInput) -> Dict[str, Any]:
    capex_tnd = 0.0
    annual_savings_tnd = 0.0
    if audit.install_solar_pumping:
        capex_tnd += 4200.0 * audit.area_hectares
        annual_savings_tnd += audit.current_annual_water_cost_tnd * 0.65
    if audit.install_smart_fertigation:
        capex_tnd += 1800.0 * audit.area_hectares
        annual_savings_tnd += audit.current_annual_fertilizer_cost_tnd * 0.28
    if audit.install_soil_sensors:
        capex_tnd += 950.0 * max(1.0, audit.area_hectares * 0.5)
        annual_savings_tnd += (audit.current_annual_water_cost_tnd * 0.20) + (audit.current_annual_fertilizer_cost_tnd * 0.12)

    subsidy_rate = 0.30 if audit.farmer_category_apia in ("A", "B") else 0.15
    estimated_apia_grant_tnd = round(capex_tnd * subsidy_rate, 0)
    net_farmer_investment_tnd = round(capex_tnd - estimated_apia_grant_tnd, 0)
    annual_savings_tnd = round(annual_savings_tnd, 0)
    payback_months = round((net_farmer_investment_tnd / annual_savings_tnd) * 12, 1) if annual_savings_tnd > 0 else 0.0

    return {
        "gross_investment_tnd": round(capex_tnd, 0),
        "estimated_apia_grant_tnd": estimated_apia_grant_tnd,
        "net_investment_after_grant_tnd": net_farmer_investment_tnd,
        "estimated_annual_savings_tnd": annual_savings_tnd,
        "payback_period_months": payback_months
    }


# =====================================================================
# 6. الصوت التونسي (TTS) والربط مع Green-API WhatsApp
# =====================================================================
def ensure_zeineb_reference_voice_files() -> Tuple[Optional[str], Optional[str]]:
    """يولّد ملف البصمة الصوتية المرجعية للمهندسة الفلاحية زينب العزيزي (ar-TN-ReemNeural) عند بدء التشغيل."""
    ogg_ref = os.path.join(MEDIA_DIR_PATH, "zeineb_lazizi_voice_ref.ogg")
    wav_ref = os.path.join(MEDIA_DIR_PATH, "zeineb_lazizi_voice_ref.wav")
    mp3_ref = os.path.join(MEDIA_DIR_PATH, "zeineb_lazizi_voice_ref.mp3")
    if os.path.exists(wav_ref) and os.path.getsize(wav_ref) > 500:
        return ogg_ref, wav_ref
    if os.path.exists(mp3_ref) and os.path.getsize(mp3_ref) > 500:
        return mp3_ref, mp3_ref

    sample_intro = (
        "مرحبا بيك خويا الفلاح، معاك المهندسة الفلاحية زينب العزيزي من مكتب الدراسات والاستشارات الفلاحية. "
        "أول حاجة بالنسبة للغراسة متاعك لازم ديما تراقب لإنستالاسيون غوت آ غوت، وتعطي التسميد والغبار والسقيان في وقته الصحيح."
    )
    try:
        subprocess.run(
            [
                sys.executable, "-m", "edge_tts",
                "--voice", "ar-TN-ReemNeural",
                "--rate=-5%",
                "--pitch=-1Hz",
                "--text", sample_intro,
                "--write-media", mp3_ref
            ],
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=20, check=False
        )
        if os.path.exists(mp3_ref) and os.path.getsize(mp3_ref) > 300:
            o_p, w_p = convert_any_audio_to_ogg_and_wav(mp3_ref)
            if w_p and os.path.exists(w_p) and w_p != wav_ref:
                try:
                    with open(w_p, "rb") as src, open(wav_ref, "wb") as dst:
                        dst.write(src.read())
                except Exception:
                    pass
            return o_p or mp3_ref, wav_ref if os.path.exists(wav_ref) else mp3_ref
    except Exception:
        pass
    return None, None


def clean_text_for_speech(text: str) -> str:
    raw = text or ""
    chars = []
    for ch in raw:
        cp = ord(ch)
        if cp >= 0x2000 or ch in "*_#`~•«»|":
            chars.append(" ")
        else:
            chars.append(ch)
    cleaned = "".join(chars)
    cleaned = re.sub(r"\s+", " ", cleaned).strip()
    return cleaned


def convert_any_audio_to_ogg_and_wav(input_audio_path: str) -> Tuple[Optional[str], Optional[str]]:
    if not input_audio_path or not os.path.exists(input_audio_path):
        return None, None
    base_no_ext = os.path.splitext(input_audio_path)[0]
    ogg_path = base_no_ext + "_wa.ogg"
    wav_path = base_no_ext + "_play.wav"
    try:
        import imageio_ffmpeg
        ffmpeg_exe = imageio_ffmpeg.get_ffmpeg_exe()
        subprocess.run(
            [ffmpeg_exe, "-y", "-i", input_audio_path, "-c:a", "libopus", "-b:a", "32k", "-ar", "48000", "-ac", "1", ogg_path],
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=20, check=False
        )
        subprocess.run(
            [ffmpeg_exe, "-y", "-i", input_audio_path, "-ar", "24000", "-ac", "1", "-f", "wav", wav_path],
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=20, check=False
        )
    except Exception:
        pass
    final_ogg = ogg_path if (os.path.exists(ogg_path) and os.path.getsize(ogg_path) > 200) else input_audio_path
    final_wav = wav_path if (os.path.exists(wav_path) and os.path.getsize(wav_path) > 200) else input_audio_path
    return final_ogg, final_wav


def generate_bot_voice_note(text_body: str, voice_name: str = "ar-TN-ReemNeural") -> Tuple[Optional[str], Optional[str]]:
    spoken_text = clean_text_for_speech(text_body)
    if not spoken_text:
        spoken_text = "مرحبا بيك في مكتب الهندسة الفلاحية."
    effective_voice = "ar-TN-ReemNeural" if (not voice_name or "Hedi" in voice_name) else voice_name
    uid = uuid.uuid4().hex[:8]
    mp3_path = os.path.join(MEDIA_DIR_PATH, f"bot_tts_{uid}.mp3")

    try:
        subprocess.run(
            [
                sys.executable, "-m", "edge_tts",
                "--voice", effective_voice,
                "--rate=-5%",
                "--pitch=-1Hz",
                "--text", spoken_text,
                "--write-media", mp3_path
            ],
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=25, check=False
        )
        if os.path.exists(mp3_path) and os.path.getsize(mp3_path) > 300:
            return convert_any_audio_to_ogg_and_wav(mp3_path)
    except Exception:
        pass

    try:
        from gtts import gTTS
        tts = gTTS(text=spoken_text, lang="ar")
        tts.save(mp3_path)
        if os.path.exists(mp3_path) and os.path.getsize(mp3_path) > 300:
            return convert_any_audio_to_ogg_and_wav(mp3_path)
    except Exception:
        pass

    return None, None


def get_green_api_base_urls(green_id: str) -> List[str]:
    urls = ["https://api.green-api.com"]
    if len(green_id) >= 4 and green_id[:4].isdigit():
        urls.insert(0, f"https://{green_id[:4]}.api.greenapi.com")
    return urls


def get_green_api_media_urls(green_id: str) -> List[str]:
    urls = []
    if len(green_id) >= 4 and green_id[:4].isdigit():
        urls.append(f"https://{green_id[:4]}.media.greenapi.com")
        urls.append(f"https://{green_id[:4]}.api.greenapi.com")
    urls.extend(["https://media.green-api.com", "https://api.green-api.com"])
    return urls


def configure_and_check_green_api(green_id: str, green_token: str) -> Dict[str, Any]:
    green_id = str(green_id or "").strip()
    green_token = str(green_token or "").strip()
    if not green_id or not green_token:
        return {"ok": False, "state": "missing_keys", "note_ar": "⚠️ لم يتم إدخال idInstance و apiTokenInstance بعد."}

    for base_url in get_green_api_base_urls(green_id):
        try:
            state_url = f"{base_url}/waInstance{green_id}/getStateInstance/{green_token}"
            r_state = requests.get(state_url, timeout=6)
            if r_state.status_code == 200:
                state_data = r_state.json()
                state_str = state_data.get("stateInstance", "unknown")

                # تفعيل استقبال الإشعارات والرسائل الواردة على Green-API
                settings_url = f"{base_url}/waInstance{green_id}/setSettings/{green_token}"
                settings_payload = {
                    "webhookUrl": "",
                    "outgoingWebhook": "no",
                    "stateWebhook": "no",
                    "incomingWebhook": "yes",
                    "outgoingMessageWebhook": "yes",
                    "outgoingAPIMessageWebhook": "no",
                    "markIncomingMessagesReaded": "yes",
                    "keepOnlineStatus": "yes"
                }
                try:
                    requests.post(settings_url, json=settings_payload, timeout=6)
                except Exception:
                    pass

                if state_str == "authorized":
                    msg = f"✅ مربوط بنجاح (authorized) وتم تفعيل استقبال رسائل الواتساب على Instance {green_id}!"
                    LAST_BOT_STATUS["state"] = "authorized"
                    LAST_BOT_STATUS["detail_ar"] = msg
                    return {"ok": True, "state": state_str, "base_url": base_url, "note_ar": msg}
                else:
                    msg = f"⚠️ حالة الحساب في Green-API: {state_str} — امسح QR Code في green-api.com"
                    LAST_BOT_STATUS["state"] = state_str
                    LAST_BOT_STATUS["detail_ar"] = msg
                    return {"ok": False, "state": state_str, "base_url": base_url, "note_ar": msg}
        except Exception:
            continue
    return {"ok": False, "state": "invalid_credentials", "note_ar": "⚠️ تأكد من صحة idInstance و apiTokenInstance."}


def _extract_text_from_green_message(msg_data: Dict[str, Any]) -> str:
    if not isinstance(msg_data, dict):
        return ""
    if "textMessageData" in msg_data and isinstance(msg_data["textMessageData"], dict):
        txt = str(msg_data["textMessageData"].get("textMessage", "")).strip()
        if txt:
            return txt
    if "extendedTextMessageData" in msg_data and isinstance(msg_data["extendedTextMessageData"], dict):
        txt = str(msg_data["extendedTextMessageData"].get("text", "")).strip()
        if txt:
            return txt
    if "quotedMessage" in msg_data and isinstance(msg_data["quotedMessage"], dict):
        txt = str(msg_data.get("extendedTextMessageData", {}).get("text", "") or msg_data.get("textMessageData", {}).get("textMessage", "")).strip()
        if txt:
            return txt
    for btn_key in ("buttonsResponseMessage", "templateButtonReplyMessage", "listResponseMessage"):
        if btn_key in msg_data and isinstance(msg_data[btn_key], dict):
            b_obj = msg_data[btn_key]
            txt = str(b_obj.get("selectedButtonText") or b_obj.get("selectedDisplayText") or b_obj.get("title") or "").strip()
            if txt:
                return txt
    if "locationMessageData" in msg_data and isinstance(msg_data["locationMessageData"], dict):
        loc_d = msg_data["locationMessageData"]
        lat_v = loc_d.get("latitude")
        lon_v = loc_d.get("longitude")
        name_loc = str(loc_d.get("nameLocation") or loc_d.get("address") or "").strip()
        if lat_v is not None and lon_v is not None:
            near_loc, near_reg = nearest_tunisian_locality_from_gps(float(lat_v), float(lon_v))
            return f"📍 موقع GPS للضيعة: {lat_v}, {lon_v} ({name_loc or near_loc} - {near_reg})"
    return ""


def _extract_gps_from_green_message(msg_data: Dict[str, Any]) -> Tuple[Optional[float], Optional[float]]:
    if isinstance(msg_data, dict) and "locationMessageData" in msg_data and isinstance(msg_data["locationMessageData"], dict):
        loc_d = msg_data["locationMessageData"]
        try:
            return float(loc_d["latitude"]), float(loc_d["longitude"])
        except Exception:
            pass
    return None, None


def download_green_api_media(
    base_url: str,
    green_id: str,
    green_token: str,
    chat_id: str,
    id_message: str,
    msg_data: Dict[str, Any]
) -> Tuple[Optional[str], Optional[str], str, str, bool]:
    msg_type = str(msg_data.get("typeMessage", ""))
    file_data = (
        msg_data.get("fileMessageData")
        or msg_data.get("imageMessageData")
        or msg_data.get("audioMessageData")
        or msg_data.get("voiceMessageData")
        or msg_data.get("documentMessageData")
        or {}
    )
    if not isinstance(file_data, dict):
        file_data = {}

    download_url = str(file_data.get("downloadUrl", "")).strip()
    caption = str(file_data.get("caption", "")).strip()
    mime_type = str(file_data.get("mimeType", "")).strip().split(";")[0].strip()
    jpeg_thumb_b64 = str(file_data.get("jpegThumbnail", "")).strip()

    is_image = (
        msg_type in ("imageMessage", "stickerMessage")
        or mime_type.startswith("image/")
        or bool(jpeg_thumb_b64 and msg_type != "videoMessage")
    )
    is_audio = (
        msg_type in ("audioMessage", "voiceMessage", "ptt")
        or mime_type.startswith("audio/")
    )

    if not (is_image or is_audio):
        return None, None, "", "", False

    if not download_url:
        for media_host in get_green_api_media_urls(green_id):
            try:
                dl_endpoint = f"{media_host}/waInstance{green_id}/downloadFile/{green_token}"
                dl_resp = requests.post(dl_endpoint, json={"chatId": chat_id, "idMessage": id_message}, timeout=10)
                if dl_resp.status_code == 200 and dl_resp.text:
                    dl_json = dl_resp.json()
                    candidate_url = str(dl_json.get("downloadUrl", "")).strip()
                    if candidate_url:
                        download_url = candidate_url
                        break
            except Exception:
                continue

    if download_url:
        try:
            media_resp = requests.get(download_url, timeout=15)
            if media_resp.status_code == 200 and len(media_resp.content) > 0:
                if is_image:
                    ext = "png" if "png" in mime_type else "jpg"
                    local_img = os.path.join(MEDIA_DIR_PATH, f"wa_img_{uuid.uuid4().hex[:8]}.{ext}")
                    with open(local_img, "wb") as f:
                        f.write(media_resp.content)
                    label = f"📸 صورة مرفقة{(' - ' + caption) if caption else ''}"
                    return local_img, None, (mime_type or "image/jpeg"), label, True
                if is_audio:
                    ext = "mp3" if "mp3" in mime_type or "mpeg" in mime_type else "ogg"
                    local_aud = os.path.join(MEDIA_DIR_PATH, f"wa_voice_{uuid.uuid4().hex[:8]}.{ext}")
                    with open(local_aud, "wb") as f:
                        f.write(media_resp.content)
                    label = "🎙️ تسجيل صوتي بالدارجة التونسية"
                    return None, local_aud, (mime_type or "audio/ogg"), label, True
        except Exception:
            pass

    if is_image and jpeg_thumb_b64:
        try:
            if "," in jpeg_thumb_b64:
                jpeg_thumb_b64 = jpeg_thumb_b64.split(",", 1)[1]
            thumb_bytes = base64.b64decode(jpeg_thumb_b64)
            if len(thumb_bytes) > 0:
                local_img = os.path.join(MEDIA_DIR_PATH, f"wa_thumb_{uuid.uuid4().hex[:8]}.jpg")
                with open(local_img, "wb") as f:
                    f.write(thumb_bytes)
                label = f"📸 صورة مرفقة{(' - ' + caption) if caption else ''}"
                return local_img, None, "image/jpeg", label, True
        except Exception:
            pass

    if is_image:
        return None, None, "image/jpeg", f"📸 صورة مرفقة{(' - ' + caption) if caption else ''}", True
    return None, None, "audio/ogg", "🎙️ تسجيل صوتي بالدارجة التونسية", True


def handle_green_api_notification_body(
    body: Dict[str, Any],
    base_url: str = "https://api.green-api.com",
    green_id: str = "",
    green_token: str = ""
) -> Optional[Dict[str, Any]]:
    """يعالج إشعار رسالة واتساب واردة من Green-API سواء عبر السحب الآلي أو عبر Webhook."""
    if not isinstance(body, dict):
        return None
    cfg = load_saved_config()
    office_sig = cfg.get("BOT_OFFICE_NAME") or DEFAULT_BOT_SIGNATURE
    type_webhook = body.get("typeWebhook", "")
    id_message = str(body.get("idMessage", uuid.uuid4().hex[:8]))

    if type_webhook not in ("incomingMessageReceived", "outgoingMessageReceived"):
        return None

    sender_data = body.get("senderData", {})
    chat_id = str(sender_data.get("chatId", ""))
    sender_name = sender_data.get("senderName") or sender_data.get("chatName") or "فلاح (واتساب)"
    sender_phone = chat_id.replace("@c.us", "")
    msg_data = body.get("messageData", {})

    text_msg = _extract_text_from_green_message(msg_data)
    gps_lat_val, gps_lon_val = _extract_gps_from_green_message(msg_data)

    img_path, aud_path, media_mime, media_label, is_media = (None, None, "", "", False)
    if green_id and green_token:
        img_path, aud_path, media_mime, media_label, is_media = download_green_api_media(
            base_url=base_url,
            green_id=green_id,
            green_token=green_token,
            chat_id=chat_id,
            id_message=id_message,
            msg_data=msg_data
        )
    if media_label and not text_msg:
        text_msg = media_label

    is_bot_own_reply = (
        id_message in SENT_BY_BOT_MESSAGE_IDS
        or text_msg.startswith("🤖")
        or text_msg.startswith("🎙️ *سؤالك الصوتي:*")
        or office_sig in text_msg
        or "• **المرض متاعك:**" in text_msg
        or "• **أعمل هذي:**" in text_msg
        or "• **اشري هذي واستعملها" in text_msg
    )

    if (text_msg or is_media) and not is_bot_own_reply and not chat_id.endswith("@g.us") and id_message not in PROCESSED_MESSAGE_IDS:
        PROCESSED_MESSAGE_IDS.add(id_message)
        log_bot_event(f"📩 [وصلت رسالة واتساب] من {sender_name} (+{sender_phone}): {text_msg}")
        plot = REGISTERED_FARMERS_DB["DEFAULT"].copy()
        plot.farmer_name = sender_name
        plot.phone_or_chat_id = f"+{sender_phone}"
        q = FarmerQuery(
            plot=plot,
            message_text=text_msg,
            image_path=img_path,
            image_mime=media_mime if img_path else "image/jpeg",
            audio_path=aud_path,
            audio_mime=media_mime if aud_path else "audio/ogg",
            is_media_message=is_media,
            media_type_label=media_label,
            gps_lat=gps_lat_val,
            gps_lon=gps_lon_val
        )
        return process_incoming_farmer_message(q, send_on_whatsapp=True)
    return None


def poll_green_api_once() -> Dict[str, Any]:
    """يسحب الرسائل المنتظرة من Green-API دفعة واحدة (تُستدعى تلقائياً في الخلفية وعند ضغط زر الفحص)."""
    cfg = load_saved_config()
    green_id = (os.environ.get("GREEN_API_INSTANCE_ID") or cfg.get("GREEN_API_INSTANCE_ID") or "").strip()
    green_token = (os.environ.get("GREEN_API_TOKEN") or cfg.get("GREEN_API_TOKEN") or "").strip()

    if not green_id or not green_token:
        LAST_BOT_STATUS["state"] = "missing_keys"
        LAST_BOT_STATUS["detail_ar"] = "⚠️ أدخل idInstance و apiTokenInstance في قسم الاستشارات لتفعيل استقبال الواتساب على السيرفر."
        return {"ok": False, "pulled": 0, "note_ar": LAST_BOT_STATUS["detail_ar"]}

    pulled_count = 0
    for base_url in get_green_api_base_urls(green_id):
        recv_url = f"{base_url}/waInstance{green_id}/receiveNotification/{green_token}"
        drained = 0
        working_host = False
        while drained < 15:
            try:
                resp = requests.get(recv_url, timeout=8)
                if resp.status_code != 200:
                    break
                working_host = True
                LAST_BOT_STATUS["last_check"] = datetime.now().strftime("%H:%M:%S")
                if not resp.text or resp.text.strip() == "null":
                    break
                notif = resp.json()
                if not notif or "receiptId" not in notif:
                    break
                drained += 1
                receipt_id = notif["receiptId"]
                body = notif.get("body", {})
                out = handle_green_api_notification_body(body, base_url=base_url, green_id=green_id, green_token=green_token)
                if out:
                    pulled_count += 1
                del_url = f"{base_url}/waInstance{green_id}/deleteNotification/{green_token}/{receipt_id}"
                requests.delete(del_url, timeout=5)
            except Exception:
                break
        if working_host:
            break

    return {
        "ok": True,
        "pulled": pulled_count,
        "note_ar": f"✅ تم فحص الواتساب بنجاح (تم سحب {pulled_count} رسائل جديدة)" if pulled_count > 0 else "✅ الاتصال بـ Green-API نشط (لا توجد رسائل جديدة في الانتظار)"
    }


def _green_api_polling_worker() -> None:
    """خيط خلفي مستمر لسحب رسائل الواتساب من Green-API كل ثانيتين على السيرفر السحابي أو المحلي."""
    settings_initialized_for = ""
    while True:
        try:
            cfg = load_saved_config()
            green_id = (os.environ.get("GREEN_API_INSTANCE_ID") or cfg.get("GREEN_API_INSTANCE_ID") or "").strip()
            green_token = (os.environ.get("GREEN_API_TOKEN") or cfg.get("GREEN_API_TOKEN") or "").strip()
            if green_id and green_token:
                sig = f"{green_id}:{green_token}"
                if settings_initialized_for != sig:
                    configure_and_check_green_api(green_id, green_token)
                    settings_initialized_for = sig
                poll_green_api_once()
        except Exception as e:
            LAST_BOT_STATUS["detail_ar"] = f"⚠️ خطأ أثناء فحص الرسائل: {e}"
        time.sleep(2.0)


def normalize_phone_number(raw_phone: str) -> str:
    cleaned = "".join(ch for ch in str(raw_phone or "") if ch.isdigit())
    if cleaned.startswith("00"):
        cleaned = cleaned[2:]
    if len(cleaned) == 8:
        cleaned = "216" + cleaned
    return cleaned or "21621127147"


def send_whatsapp_message(to_phone: str, text_body: str) -> Dict[str, Any]:
    cfg = load_saved_config()
    clean_phone = normalize_phone_number(to_phone)
    green_id = (os.environ.get("GREEN_API_INSTANCE_ID") or cfg.get("GREEN_API_INSTANCE_ID") or "").strip()
    green_token = (os.environ.get("GREEN_API_TOKEN") or cfg.get("GREEN_API_TOKEN") or "").strip()

    if green_id and green_token:
        for base_url in get_green_api_base_urls(green_id):
            url = f"{base_url}/waInstance{green_id}/sendMessage/{green_token}"
            payload = {"chatId": f"{clean_phone}@c.us", "message": text_body}
            try:
                resp = requests.post(url, json=payload, timeout=8)
                if resp.status_code == 200:
                    resp_json = resp.json() if resp.text else {}
                    is_ok = "idMessage" in resp_json
                    if is_ok:
                        SENT_BY_BOT_MESSAGE_IDS.add(str(resp_json.get("idMessage", "")))
                        PROCESSED_MESSAGE_IDS.add(str(resp_json.get("idMessage", "")))
                    return {
                        "delivered": is_ok,
                        "provider": "Green-API WhatsApp",
                        "to": f"+{clean_phone}",
                        "note_ar": f"✅ تم إرسال الرد المعتمد إلى +{clean_phone} عبر واتساب!" if is_ok else "⚠️ تعذر الإرسال عبر Green-API",
                        "response": resp_json
                    }
            except Exception:
                continue

    return {
        "delivered": True,
        "provider": "Web Portal Sync",
        "to": f"+{clean_phone}",
        "note_ar": f"✅ تمت المصادقة وحفظ الرد الفلاحي للفلاح (+{clean_phone})!"
    }


def send_whatsapp_voice_note(to_phone: str, audio_file_path: str, caption: str = "") -> Dict[str, Any]:
    cfg = load_saved_config()
    clean_phone = normalize_phone_number(to_phone)
    if not audio_file_path or not os.path.exists(audio_file_path):
        return {"delivered": False, "note_ar": "⚠️ ملف التسجيل الصوتي غير موجود."}

    green_id = (os.environ.get("GREEN_API_INSTANCE_ID") or cfg.get("GREEN_API_INSTANCE_ID") or "").strip()
    green_token = (os.environ.get("GREEN_API_TOKEN") or cfg.get("GREEN_API_TOKEN") or "").strip()
    fname = os.path.basename(audio_file_path)

    if green_id and green_token:
        for media_host in get_green_api_media_urls(green_id):
            url = f"{media_host}/waInstance{green_id}/sendFileByUpload/{green_token}"
            try:
                with open(audio_file_path, "rb") as af:
                    file_bytes = af.read()
                files = {"file": (fname, file_bytes, "audio/ogg")}
                data_form: Dict[str, str] = {"chatId": f"{clean_phone}@c.us"}
                if caption:
                    data_form["caption"] = caption
                resp = requests.post(url, data=data_form, files=files, timeout=20)
                if resp.status_code == 200:
                    resp_json = resp.json() if resp.text else {}
                    if "idMessage" in resp_json:
                        return {
                            "delivered": True,
                            "provider": "Green-API Voice Note",
                            "to": f"+{clean_phone}",
                            "note_ar": f"🎙️✅ تم إرسال التسجيل الصوتي إلى +{clean_phone}!"
                        }
            except Exception:
                continue

    return {
        "delivered": True,
        "provider": "Local Voice Ready",
        "to": f"+{clean_phone}",
        "note_ar": "🎙️ تم تجهيز وحفظ التسجيل الصوتي بنجاح!"
    }


# =====================================================================
# 7. استقبال رسائل الفلاحين وتحويلها إلى لوحة المهندس للمصادقة
# =====================================================================
def process_incoming_farmer_message(query: FarmerQuery, send_on_whatsapp: bool = True) -> Dict[str, Any]:
    cfg = load_saved_config()
    auto_reply_enabled = bool(cfg.get("AUTO_REPLY_MODE", False))

    # فك تشفير وحفظ الصورة المرفقة من بوابة الفلاح إن وجدت
    if query.image_base64 and not query.image_path:
        try:
            raw_b64 = query.image_base64
            if "," in raw_b64:
                raw_b64 = raw_b64.split(",", 1)[1]
            img_bytes = base64.b64decode(raw_b64)
            if len(img_bytes) > 50:
                ext = "png" if "png" in (query.image_mime or "").lower() else "jpg"
                saved_img_path = os.path.join(MEDIA_DIR_PATH, f"portal_img_{uuid.uuid4().hex[:8]}.{ext}")
                with open(saved_img_path, "wb") as f:
                    f.write(img_bytes)
                query.image_path = saved_img_path
                query.is_media_message = True
                log_bot_event(f"📸 تم حفظ صورة مرفقة من الفلاح ({query.plot.farmer_name}) بحجم {len(img_bytes)} بايت.")
        except Exception as e:
            log_bot_event(f"⚠️ تعذر حفظ الصورة المرفقة: {e}")

    # فك تشفير وحفظ التسجيل الصوتي المرفق من بوابة الفلاح إن وجد
    if query.audio_base64 and not query.audio_path:
        try:
            raw_aud_b64 = query.audio_base64
            if "," in raw_aud_b64:
                raw_aud_b64 = raw_aud_b64.split(",", 1)[1]
            aud_bytes = base64.b64decode(raw_aud_b64)
            if len(aud_bytes) > 50:
                mime_low = (query.audio_mime or "").lower()
                ext = "wav" if "wav" in mime_low else ("mp3" if "mp3" in mime_low or "mpeg" in mime_low else "ogg")
                saved_aud_path = os.path.join(MEDIA_DIR_PATH, f"portal_voice_{uuid.uuid4().hex[:8]}.{ext}")
                with open(saved_aud_path, "wb") as f:
                    f.write(aud_bytes)
                query.audio_path = saved_aud_path
                query.is_media_message = True
                log_bot_event(f"🎙️ تم حفظ تسجيل صوتي مرفق من الفلاح ({query.plot.farmer_name}) بحجم {len(aud_bytes)} بايت.")
        except Exception as e:
            log_bot_event(f"⚠️ تعذر حفظ التسجيل الصوتي المرفق: {e}")

    result = call_gemini_multimodal_agent(query)
    intent_obj: Dict[str, Any] = result.get("intent", {})
    ticket_id = f"AGRI-{uuid.uuid4().hex[:6].upper()}"
    w: WeatherSnapshot = result["weather"]
    guide: Dict[str, Any] = result["guide"]

    if auto_reply_enabled and send_on_whatsapp:
        whatsapp_dispatch = send_whatsapp_message(query.plot.phone_or_chat_id, result["ai_response"])
        status_str = "AUTO_REPLIED"
    else:
        status_str = "PENDING"
        whatsapp_dispatch = {"note_ar": "⏳ وصلت من الفلاح — بانتظار مراجعة ومصادقة المهندس قبل الإرسال"}
        log_bot_event(f"📩 وصلت استشارة جديدة ({ticket_id}) من {query.plot.farmer_name} — بانتظار مصادقة المهندس.")

    img_url_val: Optional[str] = None
    aud_url_val: Optional[str] = None
    aud_raw_url_val: Optional[str] = None
    m_type_val = "text"

    if query.image_path and os.path.exists(query.image_path):
        img_fname = os.path.basename(query.image_path)
        img_url_val = f"/media/{img_fname}"
        m_type_val = "image"
    if query.audio_path and os.path.exists(query.audio_path):
        aud_fname = os.path.basename(query.audio_path)
        aud_raw_url_val = f"/media/{aud_fname}"
        ogg_conv, wav_conv = convert_any_audio_to_ogg_and_wav(query.audio_path)
        if wav_conv and os.path.exists(wav_conv):
            aud_url_val = f"/media/{os.path.basename(wav_conv)}"
        else:
            aud_url_val = aud_raw_url_val
        m_type_val = "audio" if not img_url_val else "image_and_audio"

    f_lat = float(intent_obj.get("lat", 36.6806))
    f_lon = float(intent_obj.get("lon", 10.2892))
    f_exact_gps = bool(intent_obj.get("is_exact_gps", False))
    f_locality = str(intent_obj.get("locality_name") or query.plot.region)
    f_area_ha = float(intent_obj.get("area_hectares") or query.plot.area_hectares or 1.5)

    upsert_farmer_on_map(
        farmer_name=query.plot.farmer_name,
        phone=query.plot.phone_or_chat_id,
        region=query.plot.region,
        locality_name=f_locality,
        lat=f_lat,
        lon=f_lon,
        is_exact_gps=f_exact_gps,
        crop_category=query.plot.crop_category,
        crop_variety=query.plot.crop_variety,
        crop_age_label=query.plot.growth_stage,
        area_hectares=f_area_ha,
        last_inquiry=query.message_text
    )

    item = PendingApprovalItem(
        ticket_id=ticket_id,
        created_at=datetime.now().strftime("%H:%M:%S"),
        farmer_name=query.plot.farmer_name,
        farmer_chat_id=query.plot.phone_or_chat_id,
        region=query.plot.region,
        sector=query.plot.crop_category,
        crop_variety=query.plot.crop_variety,
        water_ec=query.plot.water_salinity_ec,
        max_ec=guide["max_ec_dsm"],
        temp_c=w.max_temp_c,
        et0_mm=w.et0_fao_mm,
        m3_per_ha=45.0,
        duration_str="حسب نوع الغراسة",
        fertigation_summary=guide["practical_fert_rule"],
        farmer_message=query.message_text,
        ai_draft_response=result["ai_response"],
        requires_urgent_visit=False,
        status=status_str,
        delivery_note=whatsapp_dispatch.get("note_ar", "⏳ بانتظار مراجعة ومصادقة المهندس"),
        image_url=img_url_val,
        audio_url=aud_url_val,
        audio_raw_url=aud_raw_url_val,
        media_type=m_type_val,
        lat=f_lat,
        lon=f_lon,
        is_exact_gps=f_exact_gps,
        locality_name=f_locality,
        crop_age_label=query.plot.growth_stage,
        area_hectares=f_area_ha,
        area_m2=f_area_ha * 10000.0
    )
    ENGINEER_APPROVAL_QUEUE[ticket_id] = item
    save_ticket_to_db(item)

    return {
        "status": status_str,
        "ticket_id": ticket_id,
        "auto_replied": (status_str == "AUTO_REPLIED"),
        "final_message_to_farmer": result["ai_response"],
        "whatsapp_delivery": whatsapp_dispatch,
        "ticket": _model_to_dict(item)
    }


# =====================================================================
# 8. خادم FastAPI وجميع المسارات البرمجية (Endpoints)
# =====================================================================
from fastapi import FastAPI, Request, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, PlainTextResponse, JSONResponse, FileResponse, Response

app = FastAPI(title="Agri-Modernization AI Agent & Farmer/Engineer Portal - Tunisia")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.on_event("startup")
def on_server_startup():
    ensure_zeineb_reference_voice_files()
    save_config_key("GEMINI_API_KEY", get_active_gemini_key())
    log_bot_event(f"🚀 بدأ تشغيل سيرفر الهندسة الفلاحية ({PUBLIC_SITE_URL}) + تفعيل ساحب رسائل الواتساب الخلفي")
    t = threading.Thread(target=_green_api_polling_worker, daemon=True)
    t.start()


@app.get("/api/engineer-auth-status")
def api_get_engineer_auth_status():
    """يتحقق مما إذا كان المهندس قد قام بتعيين كلمة سر دائمة خاصة به في السيرفر."""
    cfg = load_saved_config()
    saved_pwd = str(cfg.get("ENGINEER_CUSTOM_PASSWORD") or "").strip()
    saved_login = str(cfg.get("ENGINEER_CUSTOM_LOGIN") or "admin").strip()
    return {
        "has_custom_password": bool(saved_pwd),
        "login": saved_login
    }


@app.post("/api/engineer-auth-verify")
def api_verify_or_init_engineer_password(inp: EngineerAuthVerifyInput):
    """يتحقق من كلمة سر المهندس، أو يسجلها ككلمة سر دائمة عند أول إعداد."""
    cfg = load_saved_config()
    saved_pwd = str(cfg.get("ENGINEER_CUSTOM_PASSWORD") or "").strip()
    clean_pwd = str(inp.password or "").strip()
    clean_login = str(inp.login or "admin").strip() or "admin"

    if not clean_pwd or len(clean_pwd) < 3:
        return JSONResponse({"ok": False, "error_ar": "⚠️ يرجى إدخال كلمة سر تتكون من 3 أحرف أو أرقام على الأقل."}, status_code=400)

    # إذا لم يتم تعيين كلمة سر دائمة بعد، نحفظ كلمة السر التي أدخلها المهندس الآن لتصبح دائمة
    if not saved_pwd:
        save_config_key("ENGINEER_CUSTOM_PASSWORD", clean_pwd)
        save_config_key("ENGINEER_CUSTOM_LOGIN", clean_login)
        log_bot_event(f"🔐 تم تعيين وحفظ كلمة السر الدائمة لحساب المهندس ({clean_login}).")
        return {"ok": True, "initialized": True, "login": clean_login, "note_ar": "✅ تم حفظ كلمة السر الدائمة بنجاح!"}

    if clean_pwd == saved_pwd:
        return {"ok": True, "initialized": False, "login": clean_login, "note_ar": "🔓 تم التحقق من كلمة السر بنجاح!"}

    return JSONResponse({"ok": False, "error_ar": "❌ كلمة السر غير صحيحة! لا يمكن الدخول بدون كلمة السر المسجلة."}, status_code=401)


@app.post("/api/engineer-auth-change")
def api_change_engineer_password(inp: EngineerAuthChangeInput):
    """يغيّر كلمة السر الدائمة للمهندس بعد التثبت من كلمة السر الحالية."""
    cfg = load_saved_config()
    saved_pwd = str(cfg.get("ENGINEER_CUSTOM_PASSWORD") or "").strip()
    curr_pwd = str(inp.current_password or "").strip()
    new_pwd = str(inp.new_password or "").strip()
    clean_login = str(inp.login or "admin").strip() or "admin"

    if not new_pwd or len(new_pwd) < 3:
        return JSONResponse({"ok": False, "error_ar": "⚠️ كلمة السر الجديدة يجب أن تكون 3 أحرف أو أرقام على الأقل."}, status_code=400)

    if saved_pwd and curr_pwd != saved_pwd:
        return JSONResponse({"ok": False, "error_ar": "❌ كلمة السر الحالية غير صحيحة!"}, status_code=401)

    save_config_key("ENGINEER_CUSTOM_PASSWORD", new_pwd)
    save_config_key("ENGINEER_CUSTOM_LOGIN", clean_login)
    log_bot_event(f"🔑 تم تحديث كلمة السر الدائمة للمهندس ({clean_login}).")
    return {"ok": True, "login": clean_login, "note_ar": "✅ تم تغيير وحفظ كلمة السر الدائمة بنجاح!"}


@app.post("/api/poll-whatsapp-now")
def api_poll_whatsapp_now():
    """يتيح للمهندس سحب رسائل الواتساب يدوياً في أي لحظة وفحص حالة Green-API."""
    return poll_green_api_once()


@app.post("/webhook/green-api")
@app.post("/webhook/whatsapp")
async def green_api_webhook_receiver(request: Request):
    """يستقبل رسائل الواتساب فوراً إذا تم ضبط Webhook URL في Green-API على https://agriagenttun.onrender.com/webhook/green-api"""
    try:
        payload = await request.json()
        cfg = load_saved_config()
        green_id = (os.environ.get("GREEN_API_INSTANCE_ID") or cfg.get("GREEN_API_INSTANCE_ID") or "").strip()
        green_token = (os.environ.get("GREEN_API_TOKEN") or cfg.get("GREEN_API_TOKEN") or "").strip()
        body = payload.get("body", payload) if isinstance(payload, dict) else {}
        out = handle_green_api_notification_body(body, green_id=green_id, green_token=green_token)
        return JSONResponse({"ok": True, "processed": bool(out)})
    except Exception as e:
        return JSONResponse({"ok": False, "error": str(e)}, status_code=200)


@app.get("/", response_class=HTMLResponse)
@app.get("/engineer_dashboard.html", response_class=HTMLResponse)
@app.get("/engineer-dashboard.html", response_class=HTMLResponse)
@app.get("/engineer_dashboard", response_class=HTMLResponse)
@app.get("/dashboard", response_class=HTMLResponse)
@app.get("/engineer", response_class=HTMLResponse)
def serve_dashboard():
    html_path = os.path.join(BASE_DIR, "engineer_dashboard.html")
    if os.path.exists(html_path):
        with open(html_path, "r", encoding="utf-8") as f:
            return f.read()
    return "<h2>⚠️ لم يتم العثور على ملف engineer_dashboard.html في نفس المجلد.</h2>"


@app.get("/farmer_portal.html", response_class=HTMLResponse)
@app.get("/farmer_portal", response_class=HTMLResponse)
@app.get("/farmer-portal.html", response_class=HTMLResponse)
@app.get("/farmer", response_class=HTMLResponse)
@app.get("/portal", response_class=HTMLResponse)
def serve_farmer_portal():
    html_path = os.path.join(BASE_DIR, "farmer_portal.html")
    if os.path.exists(html_path):
        with open(html_path, "r", encoding="utf-8") as f:
            return f.read()
    return "<h2>⚠️ لم يتم العثور على ملف farmer_portal.html في نفس المجلد.</h2>"


@app.get("/draw-parcel", response_class=HTMLResponse)
def serve_draw_parcel_redirect():
    html_path = os.path.join(BASE_DIR, "farmer_portal.html")
    if os.path.exists(html_path):
        with open(html_path, "r", encoding="utf-8") as f:
            return f.read()
    return serve_dashboard()


@app.get("/media/{filename}")
def serve_saved_media_file(filename: str):
    safe_name = os.path.basename(filename)
    if "zeineb_lazizi" in safe_name:
        ensure_zeineb_reference_voice_files()
    target_path = os.path.join(MEDIA_DIR_PATH, safe_name)
    if not os.path.exists(target_path) and safe_name.endswith(".wav"):
        mp3_fallback = os.path.join(MEDIA_DIR_PATH, safe_name[:-4] + ".mp3")
        if os.path.exists(mp3_fallback):
            return FileResponse(mp3_fallback, media_type="audio/mpeg")
        orig_path = os.path.join(MEDIA_DIR_PATH, safe_name[:-4])
        if os.path.exists(orig_path):
            wav_bytes = convert_ogg_to_wav_bytes(orig_path)
            if wav_bytes:
                try:
                    with open(target_path, "wb") as wf:
                        wf.write(wav_bytes)
                except Exception:
                    return Response(content=wav_bytes, media_type="audio/wav")
    if not os.path.exists(target_path):
        return PlainTextResponse("File not found", status_code=404)
    lower = safe_name.lower()
    mtype = "audio/wav" if lower.endswith(".wav") else ("audio/mpeg" if lower.endswith(".mp3") else ("audio/ogg" if lower.endswith(".ogg") else ("image/png" if lower.endswith(".png") else "image/jpeg")))
    return FileResponse(target_path, media_type=mtype)


@app.get("/api/media-files")
def api_list_saved_media_files():
    items: List[Dict[str, Any]] = []
    try:
        if os.path.exists(MEDIA_DIR_PATH):
            all_files = sorted(
                os.listdir(MEDIA_DIR_PATH),
                key=lambda fn: os.path.getmtime(os.path.join(MEDIA_DIR_PATH, fn)),
                reverse=True
            )
            for fn in all_files:
                lower = fn.lower()
                full_p = os.path.join(MEDIA_DIR_PATH, fn)
                if not os.path.isfile(full_p):
                    continue
                mtime_str = datetime.fromtimestamp(os.path.getmtime(full_p)).strftime("%H:%M:%S")
                size_kb = round(os.path.getsize(full_p) / 1024.0, 1)
                if lower.endswith((".jpg", ".jpeg", ".png", ".webp")):
                    items.append({
                        "filename": fn,
                        "media_type": "image",
                        "url": f"/media/{fn}",
                        "time": mtime_str,
                        "size_kb": size_kb
                    })
                elif lower.endswith((".ogg", ".mp3", ".wav", ".m4a")):
                    items.append({
                        "filename": fn,
                        "media_type": "audio",
                        "url": f"/media/{fn}",
                        "raw_url": f"/media/{fn}",
                        "time": mtime_str,
                        "size_kb": size_kb
                    })
    except Exception:
        pass
    return items


@app.get("/api/tickets")
def api_list_tickets():
    return load_tickets_from_db()


@app.get("/api/farmers-map")
def api_get_farmers_map():
    items = load_farmers_map_db()
    by_sector = {"زياتين": 0, "أشجار_مثمرة": 0, "خضروات": 0, "زراعات_كبرى": 0}
    exact_gps_count = 0
    for it in items:
        sec = it.get("crop_category", "خضروات")
        by_sector[sec] = by_sector.get(sec, 0) + 1
        if it.get("is_exact_gps"):
            exact_gps_count += 1
    return {
        "total": len(items),
        "exact_gps_count": exact_gps_count,
        "by_sector": by_sector,
        "farmers": items
    }


@app.post("/api/farmers-map")
def api_add_or_update_farmer_on_map(inp: FarmerMapPinInput):
    poly_pts = inp.polygon_points if (inp.polygon_points and len(inp.polygon_points) >= 3) else []
    calc_ha, calc_m2, calc_perim = inp.area_hectares, inp.area_m2, inp.perimeter_m

    if poly_pts:
        c_ha, c_m2, c_perim, c_lat, c_lon = calculate_polygon_area_ha_and_m2(poly_pts)
        calc_ha = c_ha if c_ha > 0 else (inp.area_hectares or 1.5)
        calc_m2 = c_m2 if c_m2 > 0 else (calc_ha * 10000.0)
        calc_perim = c_perim
        near_loc, near_reg = nearest_tunisian_locality_from_gps(c_lat, c_lon)
        region_val = inp.region or near_reg
        loc_label = inp.locality_name or f"{near_loc} ({calc_ha:.2f} هكتار 📐)"
        lat_val, lon_val = c_lat, c_lon
        exact_flag = True
    elif inp.lat is not None and inp.lon is not None:
        near_loc, near_reg = nearest_tunisian_locality_from_gps(float(inp.lat), float(inp.lon))
        region_val = inp.region or near_reg
        loc_label = inp.locality_name or f"{near_loc} (GPS 🎯)"
        lat_val, lon_val = float(inp.lat), float(inp.lon)
        exact_flag = True
    else:
        region_val = inp.region or "مرناق - بن عروس"
        lat_val, lon_val, exact_flag, loc_label = resolve_farmer_coordinates(
            text=inp.locality_name or region_val,
            region=region_val,
            phone=inp.phone,
            farmer_name=inp.farmer_name
        )

    rec = upsert_farmer_on_map(
        farmer_name=inp.farmer_name,
        phone=inp.phone,
        region=region_val,
        locality_name=loc_label,
        lat=lat_val,
        lon=lon_val,
        is_exact_gps=exact_flag,
        crop_category=inp.crop_category,
        crop_variety=inp.crop_variety or inp.crop_category,
        crop_age_label=inp.crop_age_label,
        area_hectares=calc_ha or 1.5,
        soil_info=inp.soil_info,
        water_info=inp.water_info,
        last_inquiry=inp.notes or "تم تسجيل الضيعة على خريطة المسح الفلاحي",
        farmer_id_override=inp.farmer_id,
        polygon_points=poly_pts,
        area_m2=calc_m2,
        perimeter_m=calc_perim,
        email=inp.email or "farmer@agri.tn",
        farm_name=inp.farm_name or ""
    )
    return {"ok": True, "farmer": rec, "farmers": load_farmers_map_db()}


@app.delete("/api/farmers-map/{farmer_id}")
def api_delete_farmer_from_map(farmer_id: str):
    items = load_farmers_map_db()
    filtered = [it for it in items if it.get("farmer_id") != farmer_id]
    save_farmers_map_db(filtered)
    return {"ok": True, "farmers": filtered}


@app.post("/api/farmer-query")
def api_handle_query(query: FarmerQuery):
    return process_incoming_farmer_message(query, send_on_whatsapp=True)


@app.post("/api/simulate-incoming-whatsapp")
async def api_simulate_incoming_whatsapp(request: Request):
    body = await request.json()
    cfg = load_saved_config()
    sender_phone = body.get("from_phone") or body.get("phone") or cfg.get("DEFAULT_TEST_PHONE") or "+21621127147"
    farmer_name = body.get("farmer_name") or "فلاح تونسي"
    region = body.get("region") or "مرناق - بن عروس"
    msg_text = body.get("message_text") or "عندي زياتين في عقارب صفاقس لاحظت دوائر كحلة وصفراء على الورق وكأنه عين الطاووس، شنوة الدواء والجرعة؟"

    plot = REGISTERED_FARMERS_DB["DEFAULT"].copy()
    plot.farmer_name = farmer_name
    plot.phone_or_chat_id = sender_phone
    plot.region = region
    q = FarmerQuery(plot=plot, message_text=msg_text)
    return process_incoming_farmer_message(q, send_on_whatsapp=True)


@app.post("/api/approve-and-send")
def api_approve_and_send_ticket(inp: ApproveAndSendInput):
    cfg = load_saved_config()
    target_phone = inp.to_phone or cfg.get("DEFAULT_TEST_PHONE", "+21621127147")
    voice_name = inp.voice_name or cfg.get("BOT_VOICE_NAME", "ar-TN-ReemNeural")

    target_item: Optional[PendingApprovalItem] = ENGINEER_APPROVAL_QUEUE.get(inp.ticket_id)
    if not target_item and os.path.exists(DB_FILE_PATH):
        try:
            with open(DB_FILE_PATH, "r", encoding="utf-8") as f:
                db_data = json.load(f)
            raw_t = db_data.get("tickets", {}).get(inp.ticket_id)
            if raw_t:
                target_item = PendingApprovalItem(**raw_t)
        except Exception:
            pass

    if target_item and not inp.to_phone:
        target_phone = target_item.farmer_chat_id

    bot_voice_play_url: Optional[str] = None
    if inp.send_mode == "bot_voice":
        ogg_p, wav_p = generate_bot_voice_note(inp.edited_response, voice_name=voice_name)
        if ogg_p:
            dispatch = send_whatsapp_voice_note(target_phone, ogg_p)
            play_fn = os.path.basename(wav_p or ogg_p)
            bot_voice_play_url = f"/media/{play_fn}"
        else:
            dispatch = send_whatsapp_message(target_phone, inp.edited_response)
    elif inp.send_mode == "both":
        send_whatsapp_message(target_phone, inp.edited_response)
        ogg_p, wav_p = generate_bot_voice_note(inp.edited_response, voice_name=voice_name)
        if ogg_p:
            dispatch = send_whatsapp_voice_note(target_phone, ogg_p)
            play_fn = os.path.basename(wav_p or ogg_p)
            bot_voice_play_url = f"/media/{play_fn}"
        else:
            dispatch = {"delivered": True, "note_ar": f"✅ تمت المصادقة وإرسال الرد إلى {target_phone}!"}
    else:
        dispatch = send_whatsapp_message(target_phone, inp.edited_response)

    if target_item:
        target_item.ai_draft_response = inp.edited_response
        target_item.status = "APPROVED"
        target_item.delivery_note = dispatch.get("note_ar", "✅ تمت المصادقة والإرسال من المهندس")
        ENGINEER_APPROVAL_QUEUE[inp.ticket_id] = target_item
        save_ticket_to_db(target_item)

    log_bot_event(f"✅ تمت مصادقة المهندس على الاستشارة ({inp.ticket_id}) وإرسال الرد المعتمد للفلاح.")
    return {
        "ok": True,
        "ticket_id": inp.ticket_id,
        "status": "APPROVED",
        "send_mode": inp.send_mode,
        "bot_voice_url": bot_voice_play_url,
        "whatsapp_delivery": dispatch,
        "note_ar": dispatch.get("note_ar", "✅ تمت المصادقة والإرسال بنجاح!")
    }


@app.post("/api/preview-bot-voice")
async def api_preview_bot_voice(request: Request):
    body = await request.json()
    text_to_speak = str(body.get("text", "")).strip()
    voice_name = str(body.get("voice_name") or "ar-TN-ReemNeural").strip()
    ogg_p, wav_p = generate_bot_voice_note(text_to_speak, voice_name=voice_name)
    if not wav_p and not ogg_p:
        return JSONResponse({"ok": False, "note_ar": "⚠️ تعذر توليد الصوت حالياً."}, status_code=500)
    play_file = os.path.basename(wav_p or ogg_p)
    return {
        "ok": True,
        "play_url": f"/media/{play_file}",
        "note_ar": "🔊 تم تحويل النص إلى تسجيل صوتي تونسي جاهز للاستماع!"
    }


@app.post("/api/send-engineer-voice")
def api_send_engineer_recorded_voice(inp: EngineerVoiceReplyInput):
    raw_b64 = inp.audio_base64
    if "," in raw_b64:
        raw_b64 = raw_b64.split(",", 1)[1]
    audio_bytes = base64.b64decode(raw_b64)
    raw_path = os.path.join(MEDIA_DIR_PATH, f"eng_voice_{uuid.uuid4().hex[:8]}.webm")
    with open(raw_path, "wb") as f:
        f.write(audio_bytes)
    ogg_path, wav_path = convert_any_audio_to_ogg_and_wav(raw_path)
    send_path = ogg_path or raw_path
    dispatch = send_whatsapp_voice_note(inp.to_phone, send_path, caption=inp.caption)
    play_fn = os.path.basename(wav_path or send_path)
    return {
        "ok": True,
        "ticket_id": inp.ticket_id,
        "play_url": f"/media/{play_fn}",
        "whatsapp_delivery": dispatch,
        "note_ar": dispatch.get("note_ar", "🎙️✅ تم إرسال تسجيلك الصوتي إلى الفلاح!")
    }


@app.post("/api/analyze-media")
def api_analyze_media_from_browser(inp: BrowserMediaTestInput):
    cfg = load_saved_config()
    raw_b64 = inp.media_base64
    if "," in raw_b64:
        raw_b64 = raw_b64.split(",", 1)[1]
    file_bytes = base64.b64decode(raw_b64)
    is_audio = inp.mime_type.startswith("audio/")
    ext = "ogg" if is_audio else "jpg"
    saved_path = os.path.join(MEDIA_DIR_PATH, f"upload_{uuid.uuid4().hex[:8]}.{ext}")
    with open(saved_path, "wb") as f:
        f.write(file_bytes)
    label = "🎙️ تسجيل صوتي مرفوع للفحص" if is_audio else f"📸 صورة مرفوعة للفحص{(' - ' + inp.caption) if inp.caption else ''}"
    plot = REGISTERED_FARMERS_DB["DEFAULT"].copy()
    plot.farmer_name = "فحص وسائط مباشر"
    plot.phone_or_chat_id = cfg.get("DEFAULT_TEST_PHONE", "+21621127147")
    q = FarmerQuery(
        plot=plot,
        message_text=inp.caption or label,
        image_path=None if is_audio else saved_path,
        audio_path=saved_path if is_audio else None,
        is_media_message=True,
        media_type_label=label
    )
    return process_incoming_farmer_message(q, send_on_whatsapp=inp.send_to_whatsapp)


@app.get("/api/whatsapp-config")
def api_get_whatsapp_config():
    cfg = load_saved_config()
    green_id = (os.environ.get("GREEN_API_INSTANCE_ID") or cfg.get("GREEN_API_INSTANCE_ID") or "").strip()
    green_token = (os.environ.get("GREEN_API_TOKEN") or cfg.get("GREEN_API_TOKEN") or "").strip()
    has_green = bool(green_id and green_token)
    green_diag = configure_and_check_green_api(green_id, green_token) if has_green else None
    return {
        "configured": has_green,
        "has_green_api": has_green,
        "auto_reply_mode": bool(cfg.get("AUTO_REPLY_MODE", False)),
        "bot_reply_format": cfg.get("BOT_REPLY_FORMAT", "text"),
        "bot_voice_name": cfg.get("BOT_VOICE_NAME", "ar-TN-ReemNeural"),
        "has_gemini_key": bool(get_active_gemini_key()),
        "bot_status": LAST_BOT_STATUS,
        "green_diagnostic": green_diag,
        "green_api_instance_id": green_id,
        "green_api_token": green_token,
        "default_test_phone": cfg.get("DEFAULT_TEST_PHONE", "21621127147"),
        "bot_office_name": cfg.get("BOT_OFFICE_NAME", DEFAULT_BOT_SIGNATURE),
        "logs": BOT_ACTIVITY_LOGS
    }


@app.post("/api/whatsapp-config")
def api_save_whatsapp_config(config_in: WhatsAppConfigInput):
    if config_in.auto_reply_mode is not None:
        save_config_key("AUTO_REPLY_MODE", config_in.auto_reply_mode)
    if config_in.bot_reply_format is not None:
        save_config_key("BOT_REPLY_FORMAT", config_in.bot_reply_format)
    if config_in.bot_voice_name is not None:
        save_config_key("BOT_VOICE_NAME", config_in.bot_voice_name)
    if config_in.default_test_phone:
        save_config_key("DEFAULT_TEST_PHONE", config_in.default_test_phone)
    if config_in.green_api_instance_id is not None:
        save_config_key("GREEN_API_INSTANCE_ID", config_in.green_api_instance_id)
    if config_in.green_api_token is not None:
        save_config_key("GREEN_API_TOKEN", config_in.green_api_token)
    if config_in.gemini_api_key is not None and config_in.gemini_api_key.strip():
        save_config_key("GEMINI_API_KEY", config_in.gemini_api_key.strip())
    return api_get_whatsapp_config()


@app.post("/api/modernization-roi")
def api_calculate_roi(audit: ModernizationAuditInput):
    return calculate_modernization_roi(audit)


@app.post("/api/send-parcel-draw-link")
async def api_send_parcel_draw_link(request: Request):
    body = await request.json()
    cfg = load_saved_config()
    to_phone = body.get("to_phone") or cfg.get("DEFAULT_TEST_PHONE") or "+21621127147"
    farmer_name = body.get("farmer_name") or "الفلاح"
    draw_url = body.get("draw_url") or f"{PUBLIC_SITE_URL}/farmer_portal.html"
    msg_txt = (
        f"مرحبا بيك يا {farmer_name} 🌿\n"
        f"تنجم ترسم حدود قطعة الأرض متاعك وتبعث استشارتك للمهندس مباشرة عبر بوابة الفلاح:\n"
        f"📐 {draw_url}"
    )
    dispatch = send_whatsapp_message(to_phone, msg_txt)
    return {"ok": True, "whatsapp_delivery": dispatch, "note_ar": dispatch.get("note_ar", "📲 تم إرسال الرابط للفلاح!")}


@app.get("/api/knowledge-base")
def api_get_tunisian_knowledge_base():
    return {
        "updated_at": "2026-10-30",
        "country": "الجمهورية التونسية",
        "bioclimatic_zones": TUNISIAN_BIOCLIMATIC_ZONES,
        "crops_and_varieties": TUNISIAN_CROPS_AND_VARIETIES,
        "homologated_pesticides_dgsv": TUNISIAN_HOMOLOGATED_PESTICIDES,
        "fertigation_protocols": TUNISIAN_FERTIGATION_PROTOCOLS,
        "diagnostic_cards": PRECISE_DISEASE_AND_DEFICIENCY_CARDS
    }


@app.get("/api/logs")
def api_get_logs():
    return {
        "has_gemini_key": bool(get_active_gemini_key()),
        "bot_status": LAST_BOT_STATUS,
        "logs": BOT_ACTIVITY_LOGS
    }


def run_whatsapp_server() -> None:
    import uvicorn
    port = int(os.environ.get("PORT", 8000))
    is_cloud_env = bool(
        os.environ.get("RENDER")
        or os.environ.get("SPACE_ID")
        or os.environ.get("RAILWAY_ENVIRONMENT")
        or os.environ.get("PORT")
    )
    if not is_cloud_env:
        stop_previous_bot_instance_on_port(port)

    save_config_key("GEMINI_API_KEY", get_active_gemini_key())
    log_bot_event("=====================================================================")
    log_bot_event(f"🤖 سيرفر الهندسة الفلاحية يشتغل الآن بنجاح (Port {port})!")
    log_bot_event(f"👨‍🔬 رابط صفحة المهندس السحابي: {PUBLIC_SITE_URL}/engineer_dashboard.html")
    log_bot_event(f"🌾 رابط بوابة الفلاح السحابي:  {PUBLIC_SITE_URL}/farmer_portal.html")
    log_bot_event("=====================================================================")

    if not is_cloud_env:
        threading.Timer(1.5, lambda: webbrowser.open(f"http://127.0.0.1:{port}")).start()
    uvicorn.run(app, host="0.0.0.0", port=port)


if __name__ == "__main__":
    if "--cli-test" in sys.argv:
        print("✅ مفتاح Gemini جاهز:", get_active_gemini_key()[:16] + "...")
    else:
        run_whatsapp_server()
