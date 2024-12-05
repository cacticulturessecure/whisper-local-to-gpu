from pathlib import Path
import subprocess
import time
import json
from rich.console import Console
from rich.panel import Panel
from rich.progress import Progress, SpinnerColumn, TextColumn, TimeElapsedColumn
from rich.table import Table
from rich.box import MINIMAL
from typing import Dict, List
import sys

console = Console()

STYLES = {
    'BORDER': "blue",
    'HEADER': "bold blue",
    'SUCCESS': "green",
    'WARNING': "yellow",
    'ERROR': "red",
    'INFO': "cyan",
    'SEPARATOR': "─" * 80
}

class DevTunnelManager:
    def __init__(self):
        self.config_dir = Path.home() / ".connections"
        self.keys_dir = self.config_dir / "keys"
        self.tunnel_info_file = self.config_dir / "dev_tunnel_info.json"
        self.ports = {
            'ollama': {'local': 11434, 'remote': 11434},
            'webapp': {'local': 8001, 'remote': 8001}  # Update if this matches your FastAPI port
        }


    def create_tunnels(self, host: str, ssh_port: int, key_path: Path) -> bool:
        """Create SSH tunnels for development"""
        try:
            # Kill any existing tunnel processes
            self.stop_tunnels()

            # Create tunnel command with multiple port forwards
            tunnel_cmd = [
                "ssh",
                "-i", str(key_path),
                "-o", "IdentitiesOnly=yes",
                "-o", "ExitOnForwardFailure=yes",
                "-o", "ServerAliveInterval=30",
                "-o", "ServerAliveCountMax=3",
                "-p", str(ssh_port),
                "-N",  # No remote commands
                "-v"   # Verbose output
            ]

            # Add port forwarding for each service
            for service, ports in self.ports.items():
                tunnel_cmd.extend([
                    "-L", f"{ports['local']}:localhost:{ports['remote']}"
                ])

            # Add the destination host
            tunnel_cmd.append(f"root@{host}")  # Add this line

            console.print(f"[cyan]Executing command: {' '.join(tunnel_cmd)}[/cyan]")

            process = subprocess.Popen(
                tunnel_cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                start_new_session=True
            )
            
            # Wait briefly to ensure tunnel is established
            time.sleep(2)
            
            if process.poll() is None:  # Process is still running
                self._save_tunnel_info(host, ssh_port, key_path.name, process.pid)
                return True
            
            # If process failed, print output
            out, err = process.communicate(timeout=5)
            console.print(f"[red]Tunnel failed with error:[/red]\n{err.decode()}")
            return False

        except Exception as e:
            console.print(f"[red]Error creating tunnels: {str(e)}[/red]")
            return False

    def verify_connections(self) -> Dict[str, bool]:
        """Verify all tunnel connections"""
        results = {}
        
        with Progress(
            SpinnerColumn(),
            TextColumn("[bold blue]{task.description}"),
            TimeElapsedColumn(),
            console=console,
            transient=True
        ) as progress:
            # Check Ollama API
            task = progress.add_task("Checking Ollama API...", total=None)
            results['ollama'] = self._check_ollama()
            progress.update(task, completed=True)

            # Check Web App
            task = progress.add_task("Checking Web App...", total=None)
            results['webapp'] = self._check_webapp()
            progress.update(task, completed=True)

        return results

    def _check_ollama(self) -> bool:
        """Check Ollama API connection"""
        try:
            result = subprocess.run(
                ["curl", "-s", "http://localhost:11434/api/version"],
                capture_output=True,
                text=True
            )
            return result.returncode == 0
        except:
            return False

    def _check_webapp(self) -> bool:
        """Check Web App connection"""
        try:
            result = subprocess.run(
                ["curl", "-s", "http://localhost:8008/health"],
                capture_output=True,
                text=True
            )
            return result.returncode == 0
        except:
            return False

    def display_status(self, connection_results: Dict[str, bool]):
        """Display tunnel status in a table"""
        table = Table(
            show_header=True,
            header_style=STYLES['HEADER'],
            box=MINIMAL,
            expand=False
        )
        
        table.add_column("Service")
        table.add_column("Local Port")
        table.add_column("Remote Port")
        table.add_column("Status")

        for service, ports in self.ports.items():
            status = "[green]Connected[/green]" if connection_results.get(service, False) else "[red]Failed[/red]"
            table.add_row(
                service.title(),
                str(ports['local']),
                str(ports['remote']),
                status
            )

        console.print("\n", table)

    def _save_tunnel_info(self, host: str, port: int, key_name: str, pid: int):
        """Save tunnel information to file"""
        info = {
            "host": host,
            "port": port,
            "key_name": key_name,
            "pid": pid,
            "ports": self.ports,
            "created_at": time.strftime("%Y-%m-%d %H:%M:%S")
        }
        with open(self.tunnel_info_file, 'w') as f:
            json.dump(info, f)

    def stop_tunnels(self):
        """Stop existing tunnel processes"""
        if self.tunnel_info_file.exists():
            try:
                with open(self.tunnel_info_file, 'r') as f:
                    info = json.load(f)
                    if 'pid' in info:
                        subprocess.run(['kill', str(info['pid'])], stderr=subprocess.DEVNULL)
            except:
                pass
            self.tunnel_info_file.unlink()

def main():
    console.print(Panel.fit(
        "Development Environment Tunnel Manager\n"
        "Sets up secure tunnels for Ollama API and Web Application",
        style=STYLES['HEADER'],
        border_style=STYLES['BORDER'],
        padding=(1, 2)
    ))

    if len(sys.argv) > 1:
        if sys.argv[1] == "stop":
            DevTunnelManager().stop_tunnels()
            console.print("[green]Tunnels stopped successfully[/green]")
            return
        elif sys.argv[1] == "status":
            manager = DevTunnelManager()
            results = manager.verify_connections()
            manager.display_status(results)
            return

    # Get connection details
    connection_name = console.input("\nEnter the name of your SSH key: ").strip()
    host = console.input("Enter Vast.ai host IP: ").strip()
    port = int(console.input("Enter SSH port: ").strip())

    manager = DevTunnelManager()
    key_path = manager.keys_dir / connection_name

    if not key_path.exists():
        console.print(f"[red]Error: SSH key not found at {key_path}[/red]")
        return

    # Create tunnels
    console.print("\n[yellow]Setting up development tunnels...[/yellow]")
    if not manager.create_tunnels(host, port, key_path):
        console.print("[red]Failed to create tunnels[/red]")
        return

    # Verify connections
    console.print("\n[yellow]Verifying connections...[/yellow]")
    results = manager.verify_connections()
    manager.display_status(results)

    if all(results.values()):
        console.print("\n[green]Development environment ready![/green]")
        console.print("\nUse the following commands to manage tunnels:")
        console.print("  python setup_dev_tunnel.py status  - Check tunnel status")
        console.print("  python setup_dev_tunnel.py stop    - Stop all tunnels")
    else:
        console.print("\n[red]Some services failed to connect. Please check the status above.[/red]")

if __name__ == "__main__":
    main()
