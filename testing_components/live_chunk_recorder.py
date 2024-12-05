# live_chunk_recorder.py
import sounddevice as sd
import wave
import threading
import queue
import time
from pathlib import Path
from datetime import datetime
from rich.console import Console
from rich.live import Live
from rich.panel import Panel
from rich.table import Table
from rich.prompt import IntPrompt
import numpy as np

console = Console()

class AudioDeviceManager:
    def __init__(self):
        self.devices = self._get_audio_devices()
        
    def _get_audio_devices(self):
        """Get list of available audio devices"""
        devices = []
        try:
            device_list = sd.query_devices()
            for idx, device in enumerate(device_list):
                if device['max_input_channels'] > 0:  # Only input devices
                    devices.append({
                        'index': idx,
                        'name': device['name'],
                        'channels': device['max_input_channels'],
                        'default_samplerate': device['default_samplerate'],
                        'hostapi': device['hostapi']
                    })
        except Exception as e:
            console.print(f"[red]Error getting audio devices: {str(e)}[/red]")
        
        return devices

    def display_devices(self):
        """Display available audio devices in a table"""
        table = Table(title="Available Audio Input Devices")
        table.add_column("Index")
        table.add_column("Name")
        table.add_column("Channels")
        table.add_column("Sample Rate")
        table.add_column("Host API")
        
        for device in self.devices:
            table.add_row(
                str(device['index']),
                device['name'],
                str(device['channels']),
                f"{device['default_samplerate']:.0f} Hz",
                sd.query_hostapis(device['hostapi'])['name']
            )
        
        console.print(table)
        
    def get_device_by_index(self, index):
        """Get device info by index"""
        for device in self.devices:
            if device['index'] == index:
                return device
        return None

class LiveAudioChunker:
    def __init__(self, device_info, chunk_seconds=15):
        self.device_info = device_info
        self.chunk_seconds = chunk_seconds
        self.channels = device_info['channels']
        self.rate = int(device_info['default_samplerate'])
        self.dtype = np.float32
        
        # Setup directories
        self.output_dir = Path("live_chunks")
        self.output_dir.mkdir(exist_ok=True)
        
        # Initialize queues and buffers
        self.audio_queue = queue.Queue()
        self.current_buffer = []
        self.is_recording = False
        self.chunks_created = 0
        
        # Statistics
        self.recording_start_time = None
        self.total_audio_processed = 0
        
        # Calculate frames for chunk
        self.frames_per_chunk = int(self.rate * self.chunk_seconds)
        
    def audio_callback(self, indata, frames, time, status):
        """Callback for audio input"""
        if status:
            console.print(f"[yellow]Status: {status}[/yellow]")
        self.audio_queue.put(indata.copy())
        
    def start_recording(self):
        """Start the recording process"""
        self.is_recording = True
        self.recording_start_time = datetime.now()
        
        # Start the stream
        self.stream = sd.InputStream(
            device=self.device_info['index'],
            channels=self.channels,
            samplerate=self.rate,
            callback=self.audio_callback,
            dtype=self.dtype
        )
        self.stream.start()
        
        # Start processing thread
        self.process_thread = threading.Thread(target=self._process_audio)
        self.process_thread.start()
        
    def stop_recording(self):
        """Stop the recording process"""
        self.is_recording = False
        if hasattr(self, 'stream'):
            self.stream.stop()
            self.stream.close()
        self.process_thread.join()
        self._save_final_chunk()
        
    def _process_audio(self):
        """Process audio chunks from queue"""
        current_samples = []
        samples_needed = self.frames_per_chunk * self.channels
        
        while self.is_recording or not self.audio_queue.empty():
            if not self.audio_queue.empty():
                data = self.audio_queue.get()
                current_samples.extend(data.flatten())
                self.total_audio_processed += len(data)
                
                while len(current_samples) >= samples_needed:
                    # Extract chunk
                    chunk_samples = current_samples[:samples_needed]
                    current_samples = current_samples[samples_needed:]
                    
                    # Save chunk
                    self._save_chunk(np.array(chunk_samples))
                    
    def _save_chunk(self, samples):
        """Save audio chunk as WAV file"""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = self.output_dir / f"chunk_{self.chunks_created:03d}_{timestamp}.wav"
        
        with wave.open(str(filename), 'wb') as wf:
            wf.setnchannels(self.channels)
            wf.setsampwidth(4)  # 32-bit float
            wf.setframerate(self.rate)
            wf.writeframes(samples.astype(self.dtype).tobytes())
            
        self.chunks_created += 1
        
    def _save_final_chunk(self):
        """Save any remaining audio as final chunk"""
        while not self.audio_queue.empty():
            data = self.audio_queue.get()
            if len(data) > 0:
                self._save_chunk(data.flatten())
                
    def get_stats(self):
        """Get current recording statistics"""
        if not self.recording_start_time:
            return {}
            
        current_duration = (datetime.now() - self.recording_start_time).total_seconds()
        return {
            "duration": current_duration,
            "chunks_created": self.chunks_created,
            "device": self.device_info['name'],
            "sample_rate": self.rate,
            "channels": self.channels,
            "chunk_size": self.chunk_seconds
        }

def display_stats(chunker):
    """Create a status display"""
    stats = chunker.get_stats()
    if not stats:
        return Panel("Recording not started")
        
    table = Table(show_header=False)
    table.add_column("Metric")
    table.add_column("Value")
    
    table.add_row("Device", stats['device'])
    table.add_row("Sample Rate", f"{stats['sample_rate']} Hz")
    table.add_row("Channels", str(stats['channels']))
    table.add_row(
        "Recording Duration",
        f"{stats['duration']:.1f} seconds"
    )
    table.add_row(
        "Chunks Created",
        str(stats['chunks_created'])
    )
    table.add_row(
        "Chunk Size",
        f"{stats['chunk_size']} seconds"
    )
    
    return Panel(
        table,
        title="Recording Status",
        border_style="green"
    )

def main():
    console.print("[bold blue]Live Audio Chunker[/bold blue]")
    
    # Initialize device manager
    device_manager = AudioDeviceManager()
    
    # Display available devices
    device_manager.display_devices()
    
    if not device_manager.devices:
        console.print("[red]No audio input devices found![/red]")
        return
        
    # Get device selection
    while True:
        try:
            device_index = IntPrompt.ask(
                "\nSelect audio device (enter index number)",
                default=0
            )
            device_info = device_manager.get_device_by_index(device_index)
            if device_info:
                break
            console.print("[red]Invalid device index![/red]")
        except Exception as e:
            console.print(f"[red]Invalid input: {str(e)}[/red]")
    
    # Get chunk size
    chunk_seconds = IntPrompt.ask(
        "Enter chunk size in seconds",
        default=15
    )
    
    try:
        chunker = LiveAudioChunker(device_info, chunk_seconds=chunk_seconds)
        
        with Live(display_stats(chunker), refresh_per_second=4) as live:
            chunker.start_recording()
            
            console.print("\n[green]Recording started! Press Enter to stop...[/green]")
            input()
            
            chunker.stop_recording()
            
            # Final stats update
            live.update(display_stats(chunker))
            
    except KeyboardInterrupt:
        console.print("\n[yellow]Recording interrupted...[/yellow]")
    except Exception as e:
        console.print(f"[red]Error: {str(e)}[/red]")
    
    console.print(f"\n[green]Recording finished! Chunks saved in: {Path('live_chunks').absolute()}[/green]")

if __name__ == "__main__":
    main()
