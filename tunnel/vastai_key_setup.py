from pathlib import Path
import subprocess
import os
import stat
from rich.console import Console
from rich.panel import Panel
from rich.prompt import Confirm
from rich.progress import Progress, SpinnerColumn, TextColumn, BarColumn, TimeElapsedColumn
from rich.box import MINIMAL
from rich.table import Table
from typing import Tuple

console = Console()

# Style constants
STYLES = {
    'BORDER': "blue",
    'HEADER': "bold blue",
    'SUCCESS': "green",
    'WARNING': "yellow",
    'ERROR': "red",
    'INFO': "cyan",
    'SEPARATOR': "─" * 80
}

class VastAIKeySetup:
    def __init__(self):
        self.config_dir = Path.home() / ".connections"
        self.keys_dir = self.config_dir / "keys"
        self._ensure_directories()

    def _ensure_directories(self):
        """Create necessary directories if they don't exist"""
        self.config_dir.mkdir(exist_ok=True)
        self.keys_dir.mkdir(exist_ok=True)

    def generate_key(self, name: str) -> Tuple[Path, Path]:
        """Generate an SSH key pair with appropriate permissions"""
        key_path = self.keys_dir / name
        pub_key_path = self.keys_dir / f"{name}.pub"

        if key_path.exists():
            if not Confirm.ask(
                "\nKey already exists. Generate a new one?",
                default=False,
                style=STYLES['WARNING']
            ):
                return key_path, pub_key_path

        with Progress(
            SpinnerColumn(),
            TextColumn("[bold blue]{task.description}"),
            BarColumn(bar_width=40),
            TimeElapsedColumn(),
            console=console,
            expand=False,
            transient=True
        ) as progress:
            task = progress.add_task("Generating SSH key pair...", total=None)
            
            # Generate ed25519 key without passphrase
            subprocess.run([
                "ssh-keygen",
                "-t", "ed25519",
                "-f", str(key_path),
                "-N", ""  # Empty passphrase for automation
            ], check=True, capture_output=True)
            
            progress.update(task, completed=True)

        # Set secure permissions
        key_path.chmod(stat.S_IRUSR | stat.S_IWUSR)  # 600 - user read/write only
        pub_key_path.chmod(
            stat.S_IRUSR | stat.S_IWUSR |
            stat.S_IROTH | stat.S_IRGRP    # 644 - user read/write, others read
        )

        return key_path, pub_key_path

    def display_key_info(self, key_path: Path):
        """Display key information in a table"""
        table = Table(
            show_header=True,
            header_style=STYLES['HEADER'],
            box=MINIMAL,
            expand=False
        )
        
        table.add_column("Property")
        table.add_column("Value")
        
        table.add_row(
            "Location",
            str(key_path)
        )
        table.add_row(
            "Permissions",
            oct(key_path.stat().st_mode)[-3:]
        )
        
        console.print("\n", table)

    def display_instructions(self, name: str, pub_key: str):
        """Show formatted instructions for adding key to Vast.ai"""
        steps_panel = Panel(
            f"[{STYLES['INFO']}]Please add this SSH public key to your Vast.ai instance:[/{STYLES['INFO']}]\n\n"
            f"{pub_key}\n\n"
            f"[{STYLES['WARNING']}]Steps:[/{STYLES['WARNING']}]\n"
            "1. Go to [link]https://cloud.vast.ai/instances/[/link]\n"
            "2. Click on your instance\n"
            "3. Look for the 'SSH Keys' section\n"
            "4. Click 'Add SSH Key'\n"
            "5. Paste the entire key shown above\n"
            "6. Click Save or Add\n\n"
            f"[{STYLES['SUCCESS']}]Next Steps:[/{STYLES['SUCCESS']}]\n"
            "Run the connection test script to verify your setup:\n"
            "python test_ssh_connection.py",
            title="🔑 Vast.ai SSH Key Setup",
            border_style=STYLES['BORDER'],
            padding=(1, 2)
        )
        console.print(steps_panel)

def display_error(message: str):
    """Display error message in consistent format"""
    console.print(Panel(
        message,
        style=STYLES['ERROR'],
        border_style=STYLES['ERROR'],
        expand=False
    ))

def main():
    # Display header
    console.print(Panel.fit(
        "SSH Key Generator for Vast.ai\n"
        "A minimalist approach to secure key management",
        style=STYLES['HEADER'],
        border_style=STYLES['BORDER'],
        padding=(1, 2)
    ))

    # Get key name
    name = console.input("\nEnter a name for this key (e.g., vastai_instance1): ").strip()
    if not name:
        display_error("Key name cannot be empty")
        return

    try:
        # Initialize key setup
        setup = VastAIKeySetup()
        
        # Generate the key pair
        key_path, pub_key_path = setup.generate_key(name)
        
        # Display key information
        setup.display_key_info(key_path)
        
        # Read and display the public key with instructions
        pub_key = pub_key_path.read_text().strip()
        setup.display_instructions(name, pub_key)
        
        # Final success message
        console.print(f"\n{STYLES['SEPARATOR']}")
        console.print(
            f"[{STYLES['SUCCESS']}]Key generation complete![/{STYLES['SUCCESS']}]"
        )
        console.print(
            f"[{STYLES['WARNING']}]Important: Save this key name for future use:[/{STYLES['WARNING']}] {name}"
        )
        
    except Exception as e:
        display_error(f"Error during setup: {str(e)}")
        raise

if __name__ == "__main__":
    main()

