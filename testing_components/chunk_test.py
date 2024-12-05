# chunk_test.py
from pydub import AudioSegment
import os
from pathlib import Path
from datetime import datetime
from rich.console import Console
from rich.progress import Progress, SpinnerColumn, TextColumn, BarColumn, TimeElapsedColumn
from rich.table import Table
from rich.panel import Panel
import argparse
from typing import List, Dict

console = Console()

class AudioChunkTester:
    def __init__(self, chunk_size_seconds: int = 30):
        self.chunk_size_ms = chunk_size_seconds * 1000
        self.output_dir = Path("chunks")
        self.output_dir.mkdir(exist_ok=True)
        
    def verify_audio(self, audio: AudioSegment) -> Dict:
        """Verify audio file properties"""
        return {
            "channels": audio.channels,
            "sample_width": audio.sample_width * 8,  # Convert to bits
            "frame_rate": audio.frame_rate,
            "duration": len(audio) / 1000,
            "frame_count": len(audio.get_array_of_samples())
        }
        
    def verify_chunk(self, chunk: AudioSegment, expected_duration_ms: int) -> bool:
        """Verify chunk integrity"""
        duration_diff = abs(len(chunk) - expected_duration_ms)
        return duration_diff < 100  # Allow 100ms tolerance
        
    def process_audio(self, input_file: str, cleanup: bool = False) -> Dict:
        """Process audio file into chunks and return metadata"""
        try:
            console.print(f"\n[yellow]Loading audio file: {input_file}[/yellow]")
            audio = AudioSegment.from_wav(input_file)
            
            # Verify audio properties
            audio_info = self.verify_audio(audio)
            
            total_duration = len(audio)
            num_chunks = total_duration // self.chunk_size_ms + (1 if total_duration % self.chunk_size_ms else 0)
            
            chunks_info = []
            failed_chunks = []
            
            with Progress() as progress:
                task = progress.add_task("[cyan]Chunking audio...", total=num_chunks)
                
                for i in range(num_chunks):
                    start_time = i * self.chunk_size_ms
                    end_time = min((i + 1) * self.chunk_size_ms, total_duration)
                    
                    chunk = audio[start_time:end_time]
                    
                    # Verify chunk
                    expected_duration = min(self.chunk_size_ms, total_duration - start_time)
                    if not self.verify_chunk(chunk, expected_duration):
                        failed_chunks.append(i + 1)
                    
                    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                    chunk_filename = f"chunk_{i+1:03d}_{timestamp}.wav"
                    chunk_path = self.output_dir / chunk_filename
                    
                    chunk.export(str(chunk_path), format="wav")
                    
                    chunks_info.append({
                        "index": i + 1,
                        "filename": chunk_filename,
                        "start_time": start_time / 1000,
                        "end_time": end_time / 1000,
                        "duration": (end_time - start_time) / 1000,
                        "size": os.path.getsize(chunk_path)
                    })
                    
                    progress.update(task, advance=1)
            
            results = {
                "audio_info": audio_info,
                "original_duration": total_duration / 1000,
                "num_chunks": num_chunks,
                "chunk_size": self.chunk_size_ms / 1000,
                "total_size": sum(chunk["size"] for chunk in chunks_info),
                "chunks": chunks_info,
                "failed_chunks": failed_chunks
            }
            
            if cleanup:
                self.cleanup_chunks()
                
            return results
            
        except Exception as e:
            console.print(f"[red]Error processing audio: {str(e)}[/red]")
            raise
            
    def cleanup_chunks(self):
        """Remove all chunks"""
        for chunk_file in self.output_dir.glob("*.wav"):
            chunk_file.unlink()
        self.output_dir.rmdir()

def display_results(results: Dict):
    """Display chunking results in a formatted table"""
    # Audio Information
    console.print(Panel(
        f"Channels: {results['audio_info']['channels']}\n"
        f"Sample Width: {results['audio_info']['sample_width']} bits\n"
        f"Frame Rate: {results['audio_info']['frame_rate']} Hz\n"
        f"Duration: {results['audio_info']['duration']:.2f} seconds",
        title="Audio Properties"
    ))
    
    # Summary Table
    table = Table(title="Chunking Summary")
    table.add_column("Property")
    table.add_column("Value")
    
    table.add_row("Total Chunks", str(results['num_chunks']))
    table.add_row("Chunk Size", f"{results['chunk_size']} seconds")
    table.add_row("Total Size", f"{results['total_size'] / (1024*1024):.2f} MB")
    table.add_row("Failed Chunks", str(len(results['failed_chunks'])))
    
    console.print(table)
    
    # Show failed chunks if any
    if results['failed_chunks']:
        console.print("[red]Failed Chunks:[/red]", ", ".join(map(str, results['failed_chunks'])))

def main():
    parser = argparse.ArgumentParser(description="Audio File Chunker")
    parser.add_argument("--cleanup", action="store_true", help="Clean up chunks after processing")
    parser.add_argument("--chunk-size", type=int, default=30, help="Chunk size in seconds")
    args = parser.parse_args()
    
    if not Path("audio.wav").exists():
        console.print("[red]Error: audio.wav not found in current directory[/red]")
        return
    
    chunker = AudioChunkTester(chunk_size_seconds=args.chunk_size)
    
    try:
        results = chunker.process_audio("audio.wav", cleanup=args.cleanup)
        display_results(results)
        
        if not args.cleanup:
            console.print("\n[green]Chunks have been saved to the 'chunks' directory[/green]")
        
    except Exception as e:
        console.print(f"[red]Error: {str(e)}[/red]")

if __name__ == "__main__":
    main()
