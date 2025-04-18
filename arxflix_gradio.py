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

dotenv.load_dotenv()
logging.basicConfig(level="INFO")
logger = logging.getLogger(__name__)

DEFAULT_METHOD_PAPER = "arxiv_html"
DEFAULT_METHOD_SCRIPT = "openai"
DEFAULT_METHOD_AUDIO = "elevenlabs"
DEFAULT_PAPER_ID = "2404.02905"

VIDEO_DIR = Path("generated_videos")
VIDEO_DIR.mkdir(exist_ok=True)

# Custom CSS for black & purple theme
custom_css = '''
:root {
    --bg: #000;
    --fg: #fff;
    --accent: #692fb5;
    --accent-dark: #3a1a63;
}
body { background-color: var(--bg); color: var(--fg); font-family: 'Quantico'; }
.gradio-container { background-color: var(--bg); }
#title { text-align: center; color: var(--accent); margin-bottom: 1rem; font-size: 3.5rem; font-family: Quantico; }
.form-box, .preview-box {
    background-color: #111;
    padding: 1.5rem;
    border-radius: 12px;
    box-shadow: 0 4px 12px rgba(0,0,0,0.5);
    margin-bottom: 1rem;
}
.form-box label { display: block; margin-bottom: .5rem; }
.form-box input, .form-box select {
    width: 100%; padding: .75rem; margin-bottom: 1rem;
    border: none; border-radius: 6px;
    background: #222; color: var(--fg);
}
.form-box button {
    width: 100%; padding: .75rem;
    background: var(--accent); border: none;
    border-radius: 6px; cursor: pointer;
    font-size: 1rem; transition: background .2s;
    color: #fff;
}
.form-box button:disabled {
    background: #555; cursor: default;
}
.form-box button:hover:not(:disabled) { background: var(--accent-dark); }
.status-text { font-style: italic; margin-top: .5rem; }
.preview-box video, .preview-box iframe { max-width: 100%; border-radius: 8px; }
'''

def process_and_generate_video(
    method_paper, paper_id, method_script, method_audio, api_base_url=None
):
    api_base = api_base_url or None
    yield gr.update(value="Starting the pipeline..."), None, None
    temp_dir = None
    try:
        yield gr.update(value="Generating paper markdown..."), None, None
        paper_markdown = generate_paper(method_paper, paper_id)
        logger.info("Paper markdown generated successfully.")
        
        yield gr.update(value="Generating script from markdown..."), None, None
        script = generate_script(
            method_script, paper_markdown, paper_id, api_base
        )
        logger.info("Script generated successfully.")

        temp_dir = tempfile.mkdtemp()
        temp_path = Path(temp_dir)
        mp3_output = temp_path / "audio.wav"
        srt_output = temp_path / "subtitles.srt"
        rich_output = temp_path / "rich.json"
        output_video = temp_path / "output.mp4"

        yield gr.update(value="Generating audio, subtitles, and rich assets..."), None, None
        generate_assets(
            script,
            method_audio,
            mp3_output=str(mp3_output),
            srt_output=str(srt_output),
            rich_output=str(rich_output),
        )
        logger.info("Assets generated successfully.")

        yield gr.update(value="Generating video..."), None, None
        generate_video(str(temp_path), str(output_video))
        logger.info("Video generated successfully.")

        yield gr.update(value="Finalizing and saving video..."), None, None
        safe_id = paper_id.replace('/', '_')
        final_path = VIDEO_DIR / f"video_{safe_id}_{int(time.time())}.mp4"
        shutil.move(str(output_video), str(final_path))
        status = f"Pipeline completed! Video at: {final_path}"

        # Prepare PDF embed HTML
        pdf_url = f"https://arxiv.org/pdf/{paper_id}.pdf"
        pdf_embed_html = f"""
        <h3 style='color: var(--accent); margin-top: 1rem;'>Paper PDF Preview</h3>
        <iframe src="{pdf_url}" width="100%" height="600px"
                style="border-radius:8px; border: none; margin-top: 10px;"></iframe>
        """

        yield gr.update(value=status), str(final_path), pdf_embed_html

    except Exception as e:
        logger.error(f"An error occurred: {e}")
        yield gr.update(value=f"Error: {e}. Check logs."), None, None

    finally:
        if temp_dir:
            shutil.rmtree(temp_dir)

# Build Gradio Interface
def main():
    with gr.Blocks(css=custom_css) as demo:
        gr.HTML("<h1 id='title'>DocMind Research Paper Video Summary</h1>")
        with gr.Row():
            # Input Form Column
            with gr.Column(scale=1, elem_classes="form-box"):
                method_paper_input = gr.Dropdown(
                    ["arxiv_html", "arxiv_gpt"],
                    label="Paper Method",
                    value=DEFAULT_METHOD_PAPER
                )
                paper_id_input = gr.Textbox(
                    label="ArXiv Paper ID",
                    value=DEFAULT_PAPER_ID
                )
                method_script_input = gr.Dropdown(
                    ["openai", "local", "gemini"],
                    label="Script Method",
                    value=DEFAULT_METHOD_SCRIPT
                )
                method_audio_input = gr.Dropdown(
                    ["elevenlabs", "lmnt"],
                    label="Audio Method",
                    value=DEFAULT_METHOD_AUDIO
                )
                api_input = gr.Textbox(
                    label="API Base URL (Optional)",
                    placeholder="https://api.example.com"
                )
                generate_btn = gr.Button("Generate Video")
                status_out = gr.Textbox(
                    label="Status",
                    interactive=False,
                    elem_classes="status-text"
                )

            # Preview Column with styled boxes
            with gr.Column(scale=1):
                with gr.Column(elem_classes="preview-box"):
                    video_out = gr.Video(label="Generated Video")
                with gr.Column(elem_classes="preview-box"):
                    pdf_out = gr.HTML()

        # Bind the pipeline function
        generate_btn.click(
            process_and_generate_video,
            inputs=[
                method_paper_input,
                paper_id_input,
                method_script_input,
                method_audio_input,
                api_input,
            ],
            outputs=[status_out, video_out, pdf_out],
        )

    demo.launch(share=True)

if __name__ == "__main__":
    main()
