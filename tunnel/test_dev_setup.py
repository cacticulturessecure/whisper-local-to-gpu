from pathlib import Path
import requests
import time
from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.progress import Progress, SpinnerColumn, TextColumn, TimeElapsedColumn
from rich.box import MINIMAL
from typing import Dict, Any

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

class DevEnvironmentTester:
    def __init__(self):
        self.services = {
            'ollama': {
                'url': 'http://localhost:11434/api/version',
                'method': 'GET'
            },
            'webapp': {
                'url': 'http://localhost:8001/health',  # Updated port and endpoint
                'method': 'GET'
            }
        }

    def test_services(self) -> Dict[str, Any]:
        results = {}
        
        with Progress(
            SpinnerColumn(),
            TextColumn("[bold blue]{task.description}"),
            TimeElapsedColumn(),
            console=console,
            transient=True
        ) as progress:
            for service_name, config in self.services.items():
                task = progress.add_task(
                    f"Testing {service_name}...",
                    total=None
                )
                
                try:
                    start_time = time.time()
                    response = requests.request(
                        method=config['method'],
                        url=config['url'],
                        timeout=5
                    )
                    duration = time.time() - start_time
                    
                    results[service_name] = {
                        "status": response.status_code,
                        "duration": duration,
                        "success": response.status_code == 200
                    }
                except Exception as e:
                    results[service_name] = {
                        "status": None,
                        "duration": 0,
                        "success": False,
                        "error": str(e)
                    }
                
                progress.update(task, completed=True)
        
        return results

    def test_ollama_chat(self) -> Dict[str, Any]:
        """Test Ollama chat functionality through FastAPI endpoint"""
        try:
            chat_payload = {
                "messages": [
                    {
                        "role": "system",
                        "content": "You are a Fastly Solutions Engineer with extensive experience in CDN architecture and edge computing. You're in a meeting with a VP from Ashley Furniture who is considering switching from Akamai to Fastly. Be professional, knowledgeable, and focus on Fastly's strengths in edge computing, real-time performance, and global distribution."
                    },
                    {
                        "role": "user",
                        "content": "Hi, I'm the VP of Digital Operations at Ashley Furniture. We're currently using Akamai but I'm interested in learning how Fastly might help us improve our global content delivery and edge computing capabilities."
                    }
                ],
                "temperature": 0.7,
                "max_tokens": 2000
            }

            console.print(Panel(
                "[bold]Initiating Business Context Chat Test[/bold]\n\n"
                "Testing via FastAPI endpoint\n"
                "Context: CDN Migration Discussion",
                title="Test Scenario",
                border_style=STYLES['INFO']
            ))

            response = requests.post(
                "http://localhost:8001/api/v1/chat",
                json=chat_payload,
                timeout=200  # Extended timeout for longer response
            )

            if response.ok:
                result = response.json()
                return {
                    "success": True,
                    "response": result,
                    "scenario": "business_context"
                }
            else:
                return {
                    "success": False,
                    "error": f"Chat failed: {response.status_code} - {response.text}",
                    "scenario": "business_context"
                }
        except requests.exceptions.Timeout:
            return {
                "success": False,
                "error": "Request timed out after 200 seconds",
                "scenario": "business_context"
            }
        except Exception as e:
            return {
                "success": False,
                "error": f"Error: {str(e)}",
                "scenario": "business_context"
            }

    def display_results(self, results: Dict[str, Any], chat_test: Dict[str, Any]):
        # Service Status Table
        table = Table(
            show_header=True,
            header_style=STYLES['HEADER'],
            box=MINIMAL,
            expand=False
        )
        
        table.add_column("Service")
        table.add_column("Status")
        table.add_column("Response Time")
        table.add_column("Details")  # Added column for error details
        
        for service, data in results.items():
            status = "[green]OK[/green]" if data['success'] else f"[red]Failed[/red]"
            duration = f"{data['duration']:.2f}s" if data['success'] else "N/A"
            details = "OK" if data['success'] else data.get('error', 'Unknown error')
            
            table.add_row(
                service.title(),
                status,
                duration,
                str(details)
            )

        console.print("\n", table)

        # Chat Test Results
        if chat_test['success']:
            response_content = chat_test['response'].get('message', {}).get('content', 'No content')
            console.print(Panel(
                "[bold]Business Context Chat Test Results[/bold]\n\n"
                f"[green]Success![/green]\n\n"
                f"[cyan]AI Response:[/cyan]\n"
                f"{response_content}\n\n"
                f"[yellow]Response Analysis:[/yellow]\n"
                "• Check if the response maintains professional tone\n"
                "• Verify technical accuracy about Fastly\n"
                "• Confirm appropriate business context",
                border_style=STYLES['SUCCESS'],
                padding=(1, 2)
            ))
        else:
            console.print(Panel(
                f"[bold red]Chat Test Failed[/bold red]\n\n"
                f"Error: {chat_test.get('error', 'Unknown error')}\n\n"
                "[yellow]Troubleshooting Steps:[/yellow]\n"
                "1. Verify FastAPI service is running:\n"
                "   curl http://localhost:8080/health\n\n"
                "2. Check Ollama service:\n"
                "   curl http://localhost:11434/api/version\n\n"
                "3. Verify tunnel connections:\n"
                "   python setup_dev_tunnel.py status\n\n"
                "4. Check FastAPI logs on GPU server\n\n"
                "5. Monitor GPU resources:\n"
                "   nvidia-smi (on GPU server)",
                border_style=STYLES['ERROR'],
                padding=(1, 2)
            ))

        # Add system status summary
        console.print(f"\n{STYLES['SEPARATOR']}")
        console.print("[bold]System Status Summary[/bold]")
        console.print(f"{STYLES['SEPARATOR']}")
        
        status_table = Table(show_header=True, box=MINIMAL)
        status_table.add_column("Component")
        status_table.add_column("Status")
        
        status_table.add_row(
            "Ollama API",
            "[green]Connected[/green]" if results['ollama']['success'] else "[red]Failed[/red]"
        )
        status_table.add_row(
            "FastAPI Service",
            "[green]Connected[/green]" if results['webapp']['success'] else "[red]Failed[/red]"
        )
        status_table.add_row(
            "Chat Function",
            "[green]Working[/green]" if chat_test['success'] else "[red]Failed[/red]"
        )
        
        console.print(status_table)

def main():
    console.print(Panel.fit(
        "Development Environment Test Suite\n"
        "Verifying Ollama and Web Application Setup",
        style=STYLES['HEADER'],
        border_style=STYLES['BORDER'],
        padding=(1, 2)
    ))

    tester = DevEnvironmentTester()
    
    try:
        # Test basic services
        console.print("\n[yellow]Testing services...[/yellow]")
        results = tester.test_services()
        
        # Test Ollama chat if basic services are up
        if results['ollama']['success']:
            console.print("\n[yellow]Testing Ollama chat functionality...[/yellow]")
            chat_test = tester.test_ollama_chat()
        else:
            chat_test = {"success": False, "error": "Ollama service not available"}
        
        # Display results
        tester.display_results(results, chat_test)
    except requests.exceptions.ConnectionError as e:
        console.print(f"[red]Connection error: {str(e)}[/red]")
        console.print("[yellow]Please verify that the tunnels are running:[/yellow]")
        console.print("python setup_dev_tunnel.py status")
    except Exception as e:
        console.print(f"[red]Unexpected error: {str(e)}[/red]")
        console.print("Please check all services and try again")

if __name__ == "__main__":
    main()
