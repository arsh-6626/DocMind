import gradio as gr
import logging
from backend.main import (
    generate_paper,
    generate_script,
    generate_assets,
    generate_video,
)
from pathlib import Path
import tempfile
import shutil
import dotenv
import os
import time
import openai

dotenv.load_dotenv()
logging.basicConfig(level="INFO")
logger = logging.getLogger(__name__)
openai.api_key = os.getenv("OPENAI_API_KEY")

# Defaults
DEFAULT_METHOD_PAPER = "arxiv_html"
DEFAULT_METHOD_SCRIPT = "openai"
DEFAULT_METHOD_AUDIO = "elevenlabs"
DEFAULT_PAPER_ID = "2404.02905"
VIDEO_DIR = Path("generated_videos")
VIDEO_DIR.mkdir(exist_ok=True)

# Video pipeline
def process_and_generate_video(
    method_paper, paper_id, method_script, method_audio, api_base_url=None
):
    status = "Starting pipeline..."
    yield gr.update(value=status), None
    temp_dir = None
    try:
        status = "Generating paper markdown..."
        yield gr.update(value=status), None
        paper_md = generate_paper(method_paper, paper_id)
        status = "Generating script..."
        yield gr.update(value=status), None
        script = generate_script(method_script, paper_md, paper_id, api_base_url)
        temp_dir = tempfile.mkdtemp()
        tp = Path(temp_dir)
        audio_path = tp / "audio.wav"
        srt_path = tp / "subtitles.srt"
        rich_path = tp / "rich.json"
        vid_out = tp / "output.mp4"
        status = "Generating assets..."
        yield gr.update(value=status), None
        generate_assets(
            script, method_audio,
            mp3_output=str(audio_path),
            srt_output=str(srt_path),
            rich_output=str(rich_path)
        )
        status = "Generating video..."
        yield gr.update(value=status), None
        generate_video(tp, vid_out)
        final = VIDEO_DIR / f"video_{paper_id}_{int(time.time())}.mp4"
        shutil.move(str(vid_out), str(final))
        status = f"Done! Saved at {final}"
        yield gr.update(value=status), str(final)
    except Exception as e:
        logger.error(e)
        yield gr.update(value=f"Error: {e}"), None
    finally:
        if temp_dir:
            shutil.rmtree(temp_dir)

# Chat helper
def chat_with_gpt(paper_id, chat_history, message):
    chat_history = chat_history or []
    chat_history.append((message, None))
    system_prompt = f"You are familiar with ArXiv paper {paper_id}."
    msgs = [{"role": "system", "content": system_prompt}]
    for u, b in chat_history:
        msgs.append({"role": "user", "content": u})
        if b:
            msgs.append({"role": "assistant", "content": b})
    msgs.append({"role": "user", "content": message})
    resp = openai.ChatCompletion.create(model="gpt-4o-mini", messages=msgs, max_tokens=300)
    ans = resp.choices[0].message.content.strip()
    chat_history[-1] = (message, ans)
    return chat_history, ""

# CSS
def get_custom_css():
    return """
@import url('https://fonts.googleapis.com/css2?family=Quantico:wght@400;700&display=swap');

body {
  font-family: 'Quantico', sans-serif;
  margin: 0;
  background: linear-gradient(135deg, #2a004f 0%, #000 100%);
}

.gradio-container {
  padding: 20px;
}

.component-title {
  color: #b19cd9;
  font-size: 24px;
  transition: color 0.3s ease;
}

.component-title:hover {
  color: #7f00ff;
}

#cols {
  display: flex;
  gap: 20px;
  height: 90vh; /* Increased height for all columns */
  align-items: stretch;
}

.studio, .video, .pdf {
  background-color: #160029;
  border: 1px solid rgba(189, 140, 246, 0.3);
  border-radius: 12px;
  padding: 10px;
  display: flex;
  flex-direction: column;
  min-height: 0;
}

.studio {
  flex: 0.1; /* Reduced width */
}

.video {
  flex: 3.5; /* Increased width */
  display: flex;
  flex-direction: column;
}

.pdf {
  flex: 1.5; /* Slightly increased width, benefits from taller height too */
  display: flex;
  flex-direction: column;
}

/* Video fills top, chat limited below */
.video video {
  flex: 2;
  max-height: none;
  min-height: 0;
}

.video .chatbot {
  flex: 1;
  max-height: 40px;
  overflow-y: auto;
  margin-top: 5px;
}

.video .input-textbox {
  margin-top: 8px;
  width: 100%;
  flex: none;
}

/* Ensure iframe fills entire PDF column */
.pdf iframe {
  flex: 1;
  border: none;
  width: 100%;
  height: 100%;
  min-height: 0;
}
"""


# Build interface
with gr.Blocks(css=get_custom_css(), title="ArXFlix AI Interface") as demo:
    gr.HTML(
        "<h1 class='component-title' style='text-align:center; margin-bottom:20px;'>ArXFlix Video Generator</h1>"
    )
    with gr.Row(elem_id="cols"):
        with gr.Column(elem_classes="studio"):
            gr.Markdown("**Studio**", elem_classes="component-title")
            method_paper = gr.Dropdown(
                ["arxiv_html", "arxiv_gpt"], label="Paper Method", value=DEFAULT_METHOD_PAPER
            )
            paper_id = gr.Textbox(label="ArXiv ID", value=DEFAULT_PAPER_ID)
            method_script = gr.Dropdown(
                ["openai", "local", "gemini"], label="Script Method", value=DEFAULT_METHOD_SCRIPT
            )
            method_audio = gr.Dropdown(
                ["elevenlabs", "lmnt"], label="Audio Method", value=DEFAULT_METHOD_AUDIO
            )
            api_url = gr.Textbox(label="API Base URL (optional)")
            btn = gr.Button("Generate Video")
            status = gr.Textbox(label="Status", interactive=False, value="Idle...")
        with gr.Column(elem_classes="video"):
            gr.Markdown("**Video Summary**", elem_classes="component-title")
            video_out = gr.Video(label="Generated Video")
            chat = gr.Chatbot(label="Chat", elem_id="chatbot")
            chat_input = gr.Textbox(
                show_label=False,
                placeholder="Ask about the paper...",
                elem_classes="input-textbox",
            )
            chat_input.submit(
                chat_with_gpt,
                inputs=[paper_id, chat, chat_input],
                outputs=[chat, chat_input],
            )
        with gr.Column(elem_classes="pdf"):
            gr.Markdown("**PDF Reader**", elem_classes="component-title")
            pdf_frame = gr.HTML(
                f"<iframe src='https://arxiv.org/pdf/{DEFAULT_PAPER_ID}.pdf'></iframe>"
            )
            paper_id.change(
                lambda pid: f"<iframe src='https://arxiv.org/pdf/{pid}.pdf'></iframe>",
                inputs=[paper_id],
                outputs=[pdf_frame],
            )
    btn.click(
        process_and_generate_video,
        inputs=[method_paper, paper_id, method_script, method_audio, api_url],
        outputs=[status, video_out],
    )

if __name__ == "__main__":
    demo.launch(share=True)
