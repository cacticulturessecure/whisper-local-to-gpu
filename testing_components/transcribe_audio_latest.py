import os
from pathlib import Path
import tempfile
import time
from pydub import AudioSegment
import requests
from rich.console import Console
from rich.live import Live
from rich.panel import Panel
from rich.layout import Layout
from rich.progress import Progress, BarColumn, TextColumn, TimeElapsedColumn
from rich.text import Text
import json
from typing import List, Dict

console = Console()

class AudioTranscriptionClient:
    def __init__(self, api_url: str = "http://localhost:8008"):
        self.api_url = api_url
        self.chunk_length_ms = 30000  # 30 seconds
        self.results = []
        self.temp_dir = Path(tempfile.mkdtemp())
        
    def create_layout(self) -> Layout:
        """Create the layout for the live display"""
        layout = Layout()
        layout.split_column(
            Layout(name="progress", size=3),
            Layout(name="transcription")
        )
        return layout

    def split_audio(self, audio_path: str) -> List[dict]:
        """Split audio file into chunks and return chunk information"""
        console.print("[yellow]Loading audio file...[/yellow]")
        audio = AudioSegment.from_wav(audio_path)
        chunks_info = []
        
        for i in range(0, len(audio), self.chunk_length_ms):
            chunk = audio[i:i + self.chunk_length_ms]
            chunk_id = f"chunk_{i//self.chunk_length_ms:04d}"
            chunk_path = self.temp_dir / f"{chunk_id}.wav"
            chunk.export(chunk_path, format="wav")
            
            chunks_info.append({
                "chunk_id": chunk_id,
                "path": str(chunk_path),
                "start_time": i / 1000.0,  # Convert to seconds
                "duration": len(chunk) / 1000.0
            })
            
        return chunks_info

    def transcribe_chunk(self, chunk_info: dict) -> dict:
        """Transcribe a single chunk"""
        try:
            with open(chunk_info["path"], "rb") as f:
                files = {"audio_file": f}
                params = {"chunk_id": chunk_info["chunk_id"]}
                response = requests.post(
                    f"{self.api_url}/api/v1/transcribe",
                    files=files,
                    params=params,
                    headers={"Accept": "application/json"}
                )
                response.raise_for_status()
                result = response.json()
                result.update({
                    "start_time": chunk_info["start_time"],
                    "duration": chunk_info["duration"]
                })
                return result
        except Exception as e:
            return {
                "chunk_id": chunk_info["chunk_id"],
                "text": "",
                "status": "error",
                "error": str(e),
                "start_time": chunk_info["start_time"],
                "duration": chunk_info["duration"]
            }

    def process_audio_file(self, audio_path: str):
        """Process complete audio file with real-time feedback"""
        chunks_info = self.split_audio(audio_path)
        total_chunks = len(chunks_info)
        
        # Create progress bar
        progress = Progress(
            TextColumn("[progress.description]{task.description}"),
            BarColumn(),
            TextColumn("{task.completed}/{task.total}"),
            TimeElapsedColumn(),
        )
        task = progress.add_task("Processing chunks...", total=total_chunks)
        
        # Create layout
        layout = self.create_layout()
        layout["progress"].update(progress)
        
        try:
            with Live(layout, refresh_per_second=4) as live:
                for chunk_info in chunks_info:
                    # Process chunk
                    result = self.transcribe_chunk(chunk_info)
                    self.results.append(result)
                    
                    # Update transcription display
                    transcript_text = "\n".join([
                        f"[{r['start_time']:.1f}s]: {r['text']}"
                        for r in sorted(
                            [r for r in self.results if r['status'] == 'success'],
                            key=lambda x: x['start_time']
                        )
                    ])
                    
                    layout["transcription"].update(
                        Panel(transcript_text, title="Live Transcription", border_style="blue")
                    )
                    
                    # Update progress
                    progress.update(task, advance=1)
                    
            # Save final results
            self.save_results()
            
        finally:
            # Cleanup temporary files
            for chunk_info in chunks_info:
                try:
                    os.remove(chunk_info["path"])
                except:
                    pass
            os.rmdir(self.temp_dir)

    def save_results(self):
        """Save transcription results to file"""
        output_file = "transcription_results.json"
        
        results = {
            "chunks": self.results,
            "complete_text": "\n".join([
                r['text'] for r in sorted(
                    [r for r in self.results if r['status'] == 'success'],
                    key=lambda x: x['start_time']
                )
            ])
        }
        
        with open(output_file, "w") as f:
            json.dump(results, f, indent=2)
            
        console.print(f"\n[green]Results saved to {output_file}[/green]")

def main():
    console.print(Panel.fit(
        "Audio Transcription Client\n"
        "Processes audio files in chunks with real-time transcription",
        style="bold blue"
    ))

    audio_path = console.input("\nEnter path to WAV file: ").strip()
    if not os.path.exists(audio_path):
        console.print("[red]Error: File not found[/red]")
        return

    client = AudioTranscriptionClient()
    client.process_audio_file(audio_path)

if __name__ == "__main__":
    main()
