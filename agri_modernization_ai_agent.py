# ... existing code ...
MEDIA_DIR_PATH = os.path.join(BASE_DIR, "tmp_media")
os.makedirs(MEDIA_DIR_PATH, exist_ok=True)


def ensure_free_hosting_files_created() -> None:
    """ينشئ تلقائياً ملفات الاستضافة المجانية (requirements.txt, Procfile, Dockerfile) في نفس المجلد لتسهيل رفع الموقع مجاناً."""
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

HARDCODED_GEMINI_API_KEY = "AQ.Ab8RN6IZFDGt3s1H_bKGpL0kh2Y8elerjlD-8ozMTGY3tlaD2w"
# ... existing code ...
    if query.image_path and os.path.exists(query.image_path):
        img_fname = os.path.basename(query.image_path)
        img_url_val = f"/media/{img_fname}"
        m_type_val = "image"
    elif query.audio_path and os.path.exists(query.audio_path):
        aud_fname = os.path.basename(query.audio_path)
        aud_raw_url_val = f"/media/{aud_fname}"
        wav_fname = f"{aud_fname}.wav"
        wav_full_path = os.path.join(MEDIA_DIR_PATH, wav_fname)
        if not os.path.exists(wav_full_path):
            wav_bytes = convert_ogg_to_wav_bytes(query.audio_path)
            if wav_bytes:
                try:
                    with open(wav_full_path, "wb") as wf:
                        wf.write(wav_bytes)
                except Exception:
                    pass
        if os.path.exists(wav_full_path):
            aud_url_val = f"/media/{wav_fname}"
        else:
            aud_url_val = aud_raw_url_val
        m_type_val = "audio"

    # إذا كانت هذه هي الرسالة الثانية (استكمال المعطيات)، نحدّث أيضاً التذكرة الأولى في قاعدة البيانات حتى لا تبقى عالقة على رسالة طلب المعطيات!
# ... existing code ...
                    if lower.endswith((".jpg", ".jpeg", ".png", ".webp")):
                        items.append({
                            "filename": fn,
                            "media_type": "image",
                            "url": f"/media/{fn}",
                            "time": mtime_str,
                            "size_kb": size_kb
                        })
                    elif lower.endswith((".ogg", ".mp3", ".wav", ".m4a")):
                        wav_url = f"/media/{fn}.wav" if not lower.endswith(".wav") else f"/media/{fn}"
                        items.append({
                            "filename": fn,
                            "media_type": "audio",
                            "url": wav_url,
                            "raw_url": f"/media/{fn}",
                            "time": mtime_str,
                            "size_kb": size_kb
                        })
        except Exception:
            pass
        return items

    @app.get("/api/tickets")
# ... existing code ...
    @app.post("/api/preview-bot-voice")
    async def api_preview_bot_voice(request: Request):
        """يولّد تسجيلاً صوتياً (TTS) من النص المعدّل لكي يستمع إليه المهندس في الموقع قبل إرساله للفلاح."""
        body = await request.json()
        text_to_speak = str(body.get("text", "")).strip()
        voice_name = str(body.get("voice_name") or load_saved_config().get("BOT_VOICE_NAME") or "ar-TN-HediNeural").strip()
        ogg_p, wav_p = generate_bot_voice_note(text_to_speak, voice_name=voice_name)
        if not wav_p and not ogg_p:
            return JSONResponse({"ok": False, "note_ar": "⚠️ تعذر توليد الصوت حالياً."}, status_code=500)
        play_file = os.path.basename(wav_p or ogg_p)
        send_file = os.path.basename(ogg_p or wav_p)
        return {
            "ok": True,
            "play_url": f"/media/{play_file}",
            "send_file": send_file,
            "note_ar": "🔊 تم تحويل النص إلى تسجيل صوتي تونسي جاهز للاستماع والإرسال!"
        }

    @app.post("/api/approve-and-send")
    def api_approve_and_send_ticket(inp: ApproveAndSendInput):
# ... existing code ...
        bot_voice_play_url: Optional[str] = None
        if inp.send_mode == "bot_voice":
            ogg_p, wav_p = generate_bot_voice_note(inp.edited_response, voice_name=voice_name)
            if ogg_p:
                dispatch = send_whatsapp_voice_note(target_phone, ogg_p)
                play_fn = os.path.basename(wav_p or ogg_p)
                bot_voice_play_url = f"/media/{play_fn}"
            else:
                dispatch = {"delivered": False, "note_ar": "⚠️ تعذر توليد صوت البوت."}
        elif inp.send_mode == "both":
            send_whatsapp_message(target_phone, inp.edited_response)
            ogg_p, wav_p = generate_bot_voice_note(inp.edited_response, voice_name=voice_name)
            if ogg_p:
                dispatch = send_whatsapp_voice_note(target_phone, ogg_p)
                dispatch["note_ar"] = f"✅🔊 تمت المصادقة وإرسال النص + التسجيل الصوتي إلى {target_phone}!"
                play_fn = os.path.basename(wav_p or ogg_p)
                bot_voice_play_url = f"/media/{play_fn}"
            else:
                dispatch = {"delivered": True, "note_ar": f"✅ تمت المصادقة وإرسال النص إلى {target_phone}."}
        else:
            dispatch = send_whatsapp_message(target_phone, inp.edited_response)
            if dispatch.get("delivered"):
                dispatch["note_ar"] = f"✅ تمت المصادقة وإرسال الرد المعدّل إلى {target_phone}!"
# ... existing code ...
        play_fn = os.path.basename(wav_path or send_path)
        return {
            "ok": True,
            "ticket_id": inp.ticket_id,
            "play_url": f"/media/{play_fn}",
            "whatsapp_delivery": dispatch,
            "note_ar": dispatch.get("note_ar", "🎙️✅ تم إرسال تسجيلك الصوتي إلى واتساب الفلاح!")
        }

    @app.post("/api/approve/{ticket_id}")
# ... existing code ...
def run_whatsapp_server() -> None:
    import uvicorn
    port = int(os.environ.get("PORT", 8000))
    is_cloud_env = bool(os.environ.get("RENDER") or os.environ.get("SPACE_ID") or os.environ.get("RAILWAY_ENVIRONMENT") or os.environ.get("PORT"))
    if not is_cloud_env:
        stop_previous_bot_instance_on_port(port)
    cfg = load_saved_config()
    save_config_key("GEMINI_API_KEY", get_active_gemini_key())
    log_bot_event("=====================================================================")
    log_bot_event(f"🤖 سيرفر البوت والموقع الفلاحي يشتغل الآن على المنفذ {port}!")
    log_bot_event(f"📌 رابط المهندس: http://127.0.0.1:{port}/engineer_dashboard.html")
    log_bot_event(f"📌 رابط الفلاح:  http://127.0.0.1:{port}/farmer_portal.html")
    if cfg.get("GREEN_API_INSTANCE_ID") and cfg.get("GREEN_API_TOKEN"):
        diag = configure_and_check_green_api(cfg["GREEN_API_INSTANCE_ID"], cfg["GREEN_API_TOKEN"])
        log_bot_event(f"📡 حالة Green-API: {diag.get('note_ar')}")
    log_bot_event("=====================================================================")

    if not is_cloud_env:
        threading.Timer(1.5, lambda: webbrowser.open(f"http://127.0.0.1:{port}")).start()
    uvicorn.run(app, host="0.0.0.0", port=port)


if __name__ == "__main__":
# ... existing code ...