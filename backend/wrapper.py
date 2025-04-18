#!/usr/bin/env python
import argparse
import json
import sys
import traceback
from pathlib import Path

# Import your modules
from utils.generate_paper import process_article
from utils.generate_script import process_script
from utils.generate_assets import generate_audio_and_caption, export_mp3, export_srt, export_rich_content_json, fill_rich_content_time
from utils.generate_video import process_video

def main():
    parser = argparse.ArgumentParser(description='Process ArXiv papers into videos')
    subparsers = parser.add_subparsers(dest='command', help='Command to execute')
    paper_parser = subparsers.add_parser('process_paper', help='Process ArXiv paper')
    paper_parser.add_argument('--method', type=str, required=True, choices=['arxiv_gpt', 'arxiv_html'], 
                             help='Method to process the paper')
    paper_parser.add_argument('--paper_id', type=str, required=True, help='ArXiv paper ID')
    script_parser = subparsers.add_parser('generate_script', help='Generate video script')
    script_parser.add_argument('--method', type=str, required=True, 
                              choices=['openai', 'local', 'gemini', 'groq'], 
                              help='Method to generate the script')
    script_parser.add_argument('--paper_markdown', type=str, required=True, help='Paper markdown content')
    script_parser.add_argument('--paper_id', type=str, required=True, help='ArXiv paper ID')
    script_parser.add_argument('--api_base_url', type=str, default=None, help='Base URL for API')
    assets_parser = subparsers.add_parser('generate_assets', help='Generate audio and captions')
    assets_parser.add_argument('--method', type=str, required=True, 
                              choices=['elevenlabs', 'lmnt'], 
                              help='Method to generate audio')
    assets_parser.add_argument('--script', type=str, required=True, help='Video script')
    assets_parser.add_argument('--output_dir', type=str, required=True, help='Output directory')
    video_parser = subparsers.add_parser('process_video', help='Generate video')
    video_parser.add_argument('--input', type=str, required=True, help='Input directory with assets')
    video_parser.add_argument('--output', type=str, required=True, help='Output video path')
    args = parser.parse_args()
    try:
        if args.command == 'process_paper':
            result = process_article(method=args.method, paper_id=args.paper_id)
            print(result)
            
        elif args.command == 'generate_script':
            result = process_script(
                method=args.method, 
                paper_markdown=args.paper_markdown, 
                paper_id=args.paper_id,
                end_point_base_url=args.api_base_url or ""
            )
            print(result)
            
        elif args.command == 'generate_assets':
            from type import Text, RichContent
            script_contents = _parse_script(args.script)
            script_contents = generate_audio_and_caption(method=args.method, script=args.script)
            script_contents = fill_rich_content_time(script_contents)
            text_content = [item for item in script_contents if isinstance(item, Text)]
            rich_content = [item for item in script_contents if isinstance(item, RichContent)]
            output_dir = Path(args.output_dir)
            output_dir.mkdir(parents=True, exist_ok=True)
            audio_path = output_dir / "audio.wav"
            srt_path = output_dir / "subtitles.srt"
            rich_json_path = output_dir / "rich.json"
            export_mp3(text_content, str(audio_path))
            export_srt(str(audio_path), str(srt_path))
            export_rich_content_json(rich_content, str(rich_json_path))
            print(json.dumps({
                "audio_path": str(audio_path),
                "srt_path": str(srt_path),
                "rich_json_path": str(rich_json_path)
            }))
            
        elif args.command == 'process_video':
            output = process_video(
                input=Path(args.input),
                output=Path(args.output)
            )
            print(str(output))
            
        else:
            print(json.dumps({"error": "Invalid command"}))
            sys.exit(1)
            
    except Exception as e:
        print(json.dumps({
            "error": str(e),
            "traceback": traceback.format_exc()
        }), file=sys.stderr)
        sys.exit(1)

if __name__ == "__main__":
    main()