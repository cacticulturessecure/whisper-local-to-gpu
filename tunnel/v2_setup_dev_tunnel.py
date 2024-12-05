#!/usr/bin/env python3

import os
import sys
import subprocess
import psutil
import time
from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich.prompt import Prompt

console = Console()

def check_port_usage(port):
    """Check what process is using a specific port"""
    table = Table(title=f"Processes using port {port}")
    table.add_column("PID")
    table.add_column("Name")
    table.add_column("Command")
    table.add_column("Connections")

    for proc in psutil.process_iter(['pid', 'name', 'cmdline']):
        try:
            connections = proc.connections()
            for conn in connections:
                if conn.laddr.port == port:
                    cmd = ' '.join(filter(None, proc.cmdline()))
                    table.add_row(
                        str(proc.pid),
                        proc.name(),
                        cmd[:50] + '...' if len(cmd) > 50 else cmd,
                        f"{conn.laddr.ip}:{conn.laddr.port} -> {conn.raddr.ip if conn.raddr else 'N/A'}:{conn.raddr.port if conn.raddr else 'N/A'}"
                    )
        except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
            pass

    return table

def check_docker_containers():
    """Check running Docker containers"""
    try:
        result = subprocess.run(['docker', 'ps', '--format', '{{.ID}}\t{{.Names}}\t{{.Ports}}'], 
                              capture_output=True, text=True)
        
        table = Table(title="Running Docker Containers")
        table.add_column("Container ID")
        table.add_column("Name")
        table.add_column("Ports")

        for line in result.stdout.strip().split('\n'):
            if line:
                container_id, name, ports = line.split('\t')
                table.add_row(container_id, name, ports)

        return table
    except subprocess.CalledProcessError:
        return "No Docker containers found or Docker is not running"


def setup_tunnel(ssh_key, host, port):
    """Setup SSH tunnel with detailed logging"""
    # Ensure we're using the full path
    if not ssh_key.startswith('/'):
        ssh_key = f"/home/securemeup/.connections/keys/{ssh_key}"

    tunnel_cmd = [
        'ssh',
        '-i', ssh_key,
        '-o', 'IdentitiesOnly=yes',
        '-o', 'ExitOnForwardFailure=yes',
        '-o', 'ServerAliveInterval=30',
        '-o', 'ServerAliveCountMax=3',
        '-p', str(port),
        '-N', '-v',
        '-L', '11434:localhost:11434',
        '-L', '8004:localhost:8001',
        f'root@{host}'
    ]

    console.print("\n[yellow]Attempting to create SSH tunnel...[/yellow]")
    console.print("[blue]Command:[/blue]", ' '.join(tunnel_cmd))

    # Verify key file exists
    if not os.path.exists(ssh_key):
        raise Exception(f"SSH key not found at: {ssh_key}")

    # Verify key file permissions
    key_permissions = oct(os.stat(ssh_key).st_mode)[-3:]
    if key_permissions != '600':
        console.print(f"[yellow]Warning: SSH key has permissions {key_permissions}, should be 600[/yellow]")
        if Prompt.ask("Would you like to fix the permissions?", choices=["y", "n"], default="y") == "y":
            os.chmod(ssh_key, 0o600)

    try:
        process = subprocess.Popen(
            tunnel_cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            universal_newlines=True
        )
        
        # Wait a bit to check if the process fails immediately
        time.sleep(2)
        
        if process.poll() is not None:
            _, stderr = process.communicate()
            raise Exception(f"Tunnel failed to start:\n{stderr}")
            
        return process
    except Exception as e:
        console.print(f"[red]Error setting up tunnel:[/red] {str(e)}")
        return None


def main():
    console.print(Panel.fit(
        "Development Environment Tunnel Manager\n"
        "Diagnostic and Setup Tool",
        title="🔧 Debug Mode 🔧"
    ))

    # Check system status before proceeding
    console.print("\n[yellow]Checking system status...[/yellow]")
    
    # Check ports
    for port in [8001, 11434]:
        console.print(f"\n[blue]Checking port {port}...[/blue]")
        console.print(check_port_usage(port))

    # Check Docker containers
    console.print("\n[blue]Checking Docker containers...[/blue]")
    console.print(check_docker_containers())

    # Get connection details
    ssh_key = Prompt.ask("\nEnter the name of your SSH key", 
                        default="/home/securemeup/.connections/keys/vasting")
    host = Prompt.ask("Enter Vast.ai host IP")
    port = Prompt.ask("Enter SSH port", default="40532")

    # Confirm before proceeding
    if Prompt.ask("\nWould you like to proceed with tunnel setup?", 
                  choices=["y", "n"], default="y") == "n":
        return

    # Setup tunnel
    tunnel_process = setup_tunnel(ssh_key, host, port)
    
    if tunnel_process:
        console.print("\n[green]Tunnel process started. Press Ctrl+C to stop.[/green]")
        try:
            while True:
                time.sleep(1)
        except KeyboardInterrupt:
            tunnel_process.terminate()
            console.print("\n[yellow]Tunnel terminated.[/yellow]")

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        console.print("\n[yellow]Process interrupted by user.[/yellow]")
    except Exception as e:
        console.print(f"\n[red]An error occurred:[/red] {str(e)}")
