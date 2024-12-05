from pathlib import Path
import subprocess
from rich.console import Console
from rich.panel import Panel

console = Console()

class SSHConnectionTest:
    def __init__(self):
        self.config_dir = Path.home() / ".connections"
        self.keys_dir = self.config_dir / "keys"

    def verify_key_exists(self, connection_name: str) -> tuple[bool, Path]:
        """Verify that the SSH key exists and has correct permissions"""
        key_path = self.keys_dir / connection_name
        pub_key_path = self.keys_dir / f"{connection_name}.pub"
        
        if not key_path.exists() or not pub_key_path.exists():
            return False, key_path
            
        return True, key_path

    def test_ssh_connection(self, host: str, port: int, key_path: Path) -> bool:
        """
        Test SSH connection using IdentitiesOnly to prevent other keys from being tried
        """
        console.print("\n[yellow]Testing SSH connection...[/yellow]")
        
        try:
            subprocess.run([
                "ssh",
                "-i", str(key_path),
                "-o", "IdentitiesOnly=yes",  # Only use our specified key
                "-o", "StrictHostKeyChecking=accept-new",
                "-o", "ConnectTimeout=10",
                "-p", str(port),
                f"root@{host}",
                "echo 'Connection test successful'"
            ], check=True)
            
            return True
        except subprocess.CalledProcessError as e:
            console.print(f"[red]SSH connection failed with error: {e}[/red]")
            return False
        except Exception as e:
            console.print(f"[red]Unexpected error during connection test: {str(e)}[/red]")
            return False

def main():
    # Get connection details
    connection_name = input("Enter the name used for key generation: ")
    host = input("Enter Vast.ai host IP: ")
    port = int(input("Enter SSH port (default: 41605): ") or "41605")
    
    # Initialize connection tester
    tester = SSHConnectionTest()
    
    # First verify the key exists
    key_exists, key_path = tester.verify_key_exists(connection_name)
    if not key_exists:
        console.print(Panel(
            f"SSH key not found at {key_path}\n"
            "Please run the key generation script (step 1) first",
            title="Error",
            style="red"
        ))
        return

    # Test the connection
    console.print(Panel(
        "Testing SSH connection to your Vast.ai instance.\n"
        "This will verify that:\n"
        "1. Your SSH key is properly configured\n"
        "2. The Vast.ai instance is accepting connections\n"
        "3. Authentication is successful",
        title="SSH Connection Test",
        style="yellow"
    ))

    if tester.test_ssh_connection(host, port, key_path):
        console.print(Panel(
            "✓ SSH key is properly configured\n"
            "✓ Connection to Vast.ai instance successful\n"
            "first run ssh -i ~/.connections/keys/<<<YOURKEYNAMEFROMSTEPONEHERE>>> -o IdentitiesOnly=yes -p <<<YOUTPORTNUMBERHEREFORVASTAI-41857>>>> <<<<YOURURLFORVASTAI-root@50.217.254.161>>>>\n"
            "You can proceed to the next step to set up the Ollama tunnel.",
            title="Connection Test Complete",
            style="green"
        ))
    else:
        console.print(Panel(
            "Please check:\n"
            "1. The SSH key has been added to your Vast.ai instance\n"
            "2. The instance is running\n"
            "3. The IP address and port are correct\n"
            "4. The instance's SSH service is running",
            title="Connection Failed",
            style="red"
        ))

if __name__ == "__main__":
    main()

