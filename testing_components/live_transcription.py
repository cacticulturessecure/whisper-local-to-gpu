# test_live_transcription.py
import sounddevice as sd
import numpy as np
import threading
import queue
import requests
import wave
import tempfile
from datetime import datetime
from pathlib import Path
from rich.console import Console
from rich.live import Live
from rich.panel import Panel
from rich.table import Table

console = Console()

class LiveTranscriptionTester:
    def __init__(self, chunk_seconds=15, gpu_service_url="http://localhost:50051"):
        self.chunk_seconds = chunk_seconds
        self.gpu_service_url = gpu_service_url
        self.sample_rate = 44100
        self.channels = 1
        self.dtype = np.float32
        
        # Setup queues and buffers
        self.audio_queue = queue.Queue()
        self.transcription_queue = queue.Queue()
        self.is_recording = False
        self.chunks_processed = 0
        self.transcriptions = []
        
        # Create temp directory for chunks
        self.temp_dir = Path(tempfile.mkdtemp())
        
    def audio_callback(self, indata, frames, time, status):
        """Callback for audio input"""
        if status:
            console.print(f"[yellow]Status: {status}[/yellow]")
        self.audio_queue.put(indata.copy())
        
    def start_recording(self):
        """Start recording and processing"""
        self.is_recording = True
        self.start_time = datetime.now()
        
        # Start audio stream
        self.stream = sd.InputStream(
            channels=self.channels,
            samplerate=self.sample_rate,
            callback=self.audio_callback,
            dtype=self.dtype
        )
        self.stream.start()
        
        # Start processing thread
        self.process_thread = threading.Thread(target=self._process_audio)
        self.process_thread.start()
        
        # Start transcription thread
        self.transcribe_thread = threading.Thread(target=self._process_transcriptions)
        self.transcribe_thread.start()
        
    def stop_recording(self):
        """Stop recording and processing"""
        self.is_recording = False
        self.stream.stop()
        self.stream.close()
        self.process_thread.join()
        self.transcribe_thread.join()
        
    def _save_audio_chunk(self, audio_data: np.ndarray, chunk_id: int) -> str:
        """Save audio chunk as WAV file"""
        filename = self.temp_dir / f"chunk_{chunk_id}.wav"
        
        with wave.open(str(filename), 'wb') as wf:
            wf.setnchannels(self.channels)
            wf.setsampwidth(4)  # 32-bit float
            wf.setframerate(self.sample_rate)
            wf.writeframes(audio_data.astype(self.dtype).tobytes())
            
        return str(filename)
        
    def _process_audio(self):
        """Process audio chunks"""
        samples_per_chunk = int(self.sample_rate * self.chunk_seconds)
        current_samples = []
        
        while self.is_recording or not self.audio_queue.empty():
            if not self.audio_queue.empty():
                data = self.audio_queue.get()
                current_samples.extend(data.flatten())
                
                while len(current_samples) >= samples_per_chunk:
                    # Extract chunk
                    chunk_samples = current_samples[:samples_per_chunk]
                    current_samples = current_samples[samples_per_chunk:]
                    
                    # Save and process chunk
                    chunk_path = self._save_audio_chunk(
                        np.array(chunk_samples),
                        self.chunks_processed
                    )
                    self.transcription_queue.put((self.chunks_processed, chunk_path))
                    self.chunks_processed += 1
                    
    def _process_transcriptions(self):
        """Send chunks to GPU service and collect transcriptions"""
        while self.is_recording or not self.transcription_queue.empty():
            if not self.transcription_queue.empty():
                chunk_id, chunk_path = self.transcription_queue.get()
                
                try:
                    # Send to GPU service
                    with open(chunk_path, 'rb') as f:
                        files = {'file': f}
                        response = requests.post(
                            f"{self.gpu_service_url}/api/v1/transcribe",
                            files=files
                        )
                        
                    if response.status_code == 200:
                        result = response.json()
                        self.transcriptions.append({
                            'chunk_id': chunk_id,
                            'text': result['text'],
                            'timestamp': datetime.now()
                        })
                except Exception as e:
                    console.print(f"[red]Error processing chunk {chunk_id}: {str(e)}[/red]")
                finally:
                    # Cleanup chunk file
                    Path(chunk_path).unlink()
                    
    def get_status(self):
        """Get current status"""
        if not hasattr(self, 'start_time'):
            return {}
            
        return {
            "duration": (datetime.now() - self.start_time).total_seconds(),
            "chunks_processed": self.chunks_processed,
            "transcriptions": self.transcriptions
        }

def display_status(tester):
    """Create status display"""
    stats = tester.get_status()
    if not stats:
        return Panel("Recording not started")
        
    table = Table(show_header=False)
    table.add_column("Metric")
    table.add_column("Value")
    
    table.add_row(
        "Recording Duration",
        f"{stats['duration']:.1f} seconds"
    )
    table.add_row(
        "Chunks Processed",
        str(stats['chunks_processed'])
    )
    
    # Show last 3 transcriptions
    transcriptions = stats['transcriptions'][-3:]
    transcription_text = "\n\n".join(
        f"Chunk {t['chunk_id']}: {t['text']}"
        for t in transcriptions
    )
    
    return Panel(
        f"{table}\n\nRecent Transcriptions:\n{transcription_text}",
        title="Live Transcription Status",
        border_style="green"
    )

def main():
    console.print("[bold blue]Live Transcription Tester[/bold blue]")
    console.print("This will record audio and transcribe it in real-time using the GPU service.")
    
    # Check GPU service
    try:
        response = requests.get("http://localhost:50051/health")
        if response.status_code != 200:
            console.print("[red]GPU service is not available![/red]")
            return
    except:
        console.print("[red]Cannot connect to GPU service![/red]")
        return
    
    console.print("\n[green]GPU service is available[/green]")
    console.print("Press Enter to start recording...")
    input()
    
    tester = LiveTranscriptionTester(chunk_seconds=15)
    
    try:
        with Live(display_status(tester), refresh_per_second=4) as live:
            tester.start_recording()
            
            console.print("\n[green]Recording started! Press Enter to stop...[/green]")
            input()
            
            tester.stop_recording()
            
            # Final status update
            live.update(display_status(tester))
            
    except KeyboardInterrupt:
        console.print("\n[yellow]Recording interrupted...[/yellow]")
    except Exception as e:
        console.print(f"[red]Error: {str(e)}[/red]")
    finally:
        # Cleanup temp directory
        for file in tester.temp_dir.glob("*.wav"):
            file.unlink()
        tester.temp_dir.rmdir()
        
    # Save complete transcription
    if tester.transcriptions:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        output_file = f"transcription_{timestamp}.txt"
        
        with open(output_file, 'w') as f:
            for t in tester.transcriptions:
                f.write(f"Chunk {t['chunk_id']}:\n{t['text']}\n\n")
                
        console.print(f"\n[green]Complete transcription saved to: {output_file}[/green]")

if __name__ == "__main__":
    main()
