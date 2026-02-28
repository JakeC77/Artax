"""
CLI.py - Streamlined CLI Framework for AI Workflow Tool
Essential components for building a navigable, interactive CLI interface.
"""

import os
import sys
import threading
import time
from typing import List, Dict, Any, Optional, Callable
from dataclasses import dataclass


# ============================================================================
# COLORS (Simple, can disable if needed)
# ============================================================================

class Colors:
    """Basic ANSI colors for better readability"""
    RESET = '\033[0m'
    BOLD = '\033[1m'
    DIM = '\033[2m'
    RED = '\033[31m'
    GREEN = '\033[32m'
    YELLOW = '\033[33m'
    BLUE = '\033[34m'
    CYAN = '\033[36m'


# ============================================================================
# DATA STRUCTURES
# ============================================================================

@dataclass
class MenuItem:
    """A single menu option"""
    key: str              # What user types to select (e.g., "1", "create")
    label: str            # Display text
    action: Callable      # Function to run when selected
    description: str = "" # Optional help text


@dataclass
class Menu:
    """A navigable menu with multiple options"""
    title: str
    items: List[MenuItem]
    back_enabled: bool = True  # Allow going back?


# ============================================================================
# CORE CLI CLASS
# ============================================================================

class CLI:
    """Main CLI interface - your single source of truth for interactions"""
    
    def __init__(self):
        self.menu_stack = []  # Track navigation history (breadcrumbs)
        self.running = True
        self.Colors = Colors  # Make colors accessible via cli.Colors
    
    # ========================================================================
    # DISPLAY METHODS
    # ========================================================================
    
    def clear(self):
        """Clear the screen"""
        os.system('cls' if os.name == 'nt' else 'clear')
    
    def header(self, text: str):
        """Display a header"""
        print(f"\n{Colors.BOLD}{'=' * 60}{Colors.RESET}")
        print(f"{Colors.BOLD}{text.center(60)}{Colors.RESET}")
        print(f"{Colors.BOLD}{'=' * 60}{Colors.RESET}\n")
    
    def section(self, text: str):
        """Display a section divider"""
        print(f"\n{Colors.CYAN}{text}{Colors.RESET}")
        print(f"{Colors.DIM}{'-' * len(text)}{Colors.RESET}")
    
    def breadcrumbs(self):
        """Show where user is in navigation"""
        if len(self.menu_stack) > 1:
            path = " > ".join([m.title for m in self.menu_stack])
            print(f"{Colors.DIM}📍 {path}{Colors.RESET}\n")
    
    def success(self, message: str):
        """Show success message"""
        print(f"{Colors.GREEN}✓ {message}{Colors.RESET}")
    
    def error(self, message: str):
        """Show error message"""
        print(f"{Colors.RED}✗ {message}{Colors.RESET}")
    
    def warning(self, message: str):
        """Show warning message"""
        print(f"{Colors.YELLOW}⚠ {message}{Colors.RESET}")
    
    def info(self, message: str):
        """Show info message"""
        print(f"{Colors.BLUE}ℹ {message}{Colors.RESET}")
    
    def print(self, text: str):
        """Regular print"""
        print(text)
    
    def table(self, headers: List[str], rows: List[List[str]]):
        """Display simple table"""
        # Calculate column widths
        widths = [len(h) for h in headers]
        for row in rows:
            for i, cell in enumerate(row):
                widths[i] = max(widths[i], len(str(cell)))
        
        # Print header
        header_line = " | ".join(h.ljust(w) for h, w in zip(headers, widths))
        print(f"\n{Colors.BOLD}{header_line}{Colors.RESET}")
        print("-" * len(header_line))
        
        # Print rows
        for row in rows:
            print(" | ".join(str(c).ljust(w) for c, w in zip(row, widths)))
        print()
    
    # ========================================================================
    # INPUT METHODS
    # ========================================================================
    
    def input_text(self, prompt: str, required: bool = True, default: str = None) -> Optional[str]:
        """
        Get text input from user
        
        Args:
            prompt: What to ask the user
            required: If True, must provide input
            default: Default value if user presses Enter
        
        Returns:
            User's input or None if cancelled
        """
        # Build prompt with default hint
        full_prompt = prompt
        if default:
            full_prompt += f" {Colors.DIM}[{default}]{Colors.RESET}"
        full_prompt += ": "
        
        try:
            value = input(full_prompt).strip()
            
            # Handle empty input
            if not value:
                if default:
                    return default
                elif required:
                    self.error("Input required. Please try again.")
                    return self.input_text(prompt, required, default)
                else:
                    return None
            
            return value
            
        except KeyboardInterrupt:
            print()  # New line after ^C
            if self.exit_handler():
                raise KeyboardInterrupt  # Re-raise to fully exit
            return None  # User cancelled the quit, return None to cancel input
    
    def input_number(self, prompt: str, min_val: int = None, max_val: int = None) -> Optional[int]:
        """
        Get numeric input with validation
        
        Args:
            prompt: What to ask the user
            min_val: Minimum allowed value
            max_val: Maximum allowed value
        
        Returns:
            Integer or None if cancelled
        """
        value = self.input_text(prompt, required=True)
        if value is None:
            return None
        
        try:
            num = int(value)
            
            # Validate range
            if min_val is not None and num < min_val:
                self.error(f"Value must be at least {min_val}")
                return self.input_number(prompt, min_val, max_val)
            
            if max_val is not None and num > max_val:
                self.error(f"Value must be at most {max_val}")
                return self.input_number(prompt, min_val, max_val)
            
            return num
            
        except ValueError:
            self.error("Please enter a valid number")
            return self.input_number(prompt, min_val, max_val)
    
    def confirm(self, prompt: str, default: bool = False) -> bool:
        """
        Ask yes/no confirmation
        
        Args:
            prompt: Question to ask
            default: Default if user just presses Enter
        
        Returns:
            True for yes, False for no
        """
        options = "[Y/n]" if default else "[y/N]"
        response = self.input_text(f"{prompt} {options}", required=False)
        
        if response is None:
            return False  # Cancelled = No
        
        if not response:
            return default
        
        return response.lower() in ['y', 'yes']
    
    def select_from_list(self, items: List[str], prompt: str = "Select an option", 
                        allow_cancel: bool = True) -> Optional[int]:
        """
        Show numbered list and let user select
        
        Args:
            items: List of options to show
            prompt: Instruction text
            allow_cancel: If True, user can cancel with 0
        
        Returns:
            Index of selected item (0-based), or None if cancelled
        """
        print(f"\n{prompt}:")
        for i, item in enumerate(items, 1):
            print(f"  {i}. {item}")
        
        if allow_cancel:
            print(f"  0. Cancel")
        
        max_val = len(items)
        min_val = 0 if allow_cancel else 1
        
        choice = self.input_number(f"\nEnter choice ({min_val}-{max_val})", min_val, max_val)
        
        if choice is None or choice == 0:
            return None
        
        return choice - 1  # Convert to 0-based index
    
    # ========================================================================
    # LOADING INDICATORS
    # ========================================================================
    
    def loading_spinner(self, message: str = "Working"):
        """
        Returns a LoadingSpinner context manager for long operations
        
        Usage:
            with cli.loading_spinner("Processing files"):
                # Do work here
                time.sleep(2)
        """
        return LoadingSpinner(message)
    
    def progress_bar(self, total: int, prefix: str = "Progress"):
        """
        Returns a ProgressBar for tracking progress
        
        Usage:
            progress = cli.progress_bar(100, "Downloading")
            for i in range(100):
                # Do work
                progress.update(i + 1)
            progress.complete()
        """
        return ProgressBar(total, prefix)
    
    # ========================================================================
    # NAVIGATION & MENUS
    # ========================================================================
    
    def show_menu(self, menu: Menu):
        """
        Display menu and handle user selection
        
        Args:
            menu: Menu object to display
        """
        self.menu_stack.append(menu)
        try:

            while True:
                self.clear()
                self.header(menu.title)
                self.breadcrumbs()
                
                # Show menu items
                for item in menu.items:
                    desc = f" - {Colors.DIM}{item.description}{Colors.RESET}" if item.description else ""
                    print(f"  [{item.key}] {item.label}{desc}")
                
                # Show navigation options
                print()
                if menu.back_enabled:
                    print(f"  {Colors.DIM}[b] Go Back{Colors.RESET}")
                print(f"  {Colors.DIM}[q] Quit{Colors.RESET}")
                print(f"  {Colors.DIM}[?] Help{Colors.RESET}")
                
                # Get user choice
                choice = self.input_text("\nSelect an option", required=True)
                
                if not choice:
                    continue
                
                choice = choice.lower()
                
                # Handle special commands
                if choice == 'q':
                    if self.exit_handler():
                        # Pop all menus to fully exit
                        self.menu_stack.clear()
                        return
                    continue
                
                elif choice == 'b' and menu.back_enabled:
                    self.menu_stack.pop()
                    return
                
                elif choice == '?':
                    self.show_help()
                    continue
                
                # Find matching menu item
                selected = None
                for item in menu.items:
                    if item.key.lower() == choice:
                        selected = item
                        break
                
                if selected:
                    try:
                        # Execute the action
                        result = selected.action()
                        
                        # If action returns False, stay on current menu
                        # If returns True or None, continue showing menu
                        if result is False:
                            self.menu_stack.pop()
                            return
                            
                    except KeyboardInterrupt:
                        print()
                        self.warning("Action cancelled")
                        self.pause()
                        
                    except Exception as e:
                        self.error(f"Error: {str(e)}")
                        self.pause()
                else:
                    self.error(f"Invalid option: {choice}")
                    self.pause()
        except KeyboardInterrupt:
            # Ctrl+C pressed - treat like quit
            print()  # New line after ^C
            if self.exit_handler():
                # User confirmed quit
                self.menu_stack.clear()
                return
    
    def navigate_to(self, menu: Menu):
        """Navigate to a new menu (shorthand for show_menu)"""
        self.show_menu(menu)
    
    # ========================================================================
    # HELP SYSTEM
    # ========================================================================
    
    def show_help(self):
        """Display help information"""
        self.clear()
        self.header("Help")
        
        print("📖 Navigation:")
        print("  • Type the key shown in [brackets] to select an option")
        print("  • Type 'b' or 'back' to go to previous menu")
        print("  • Type 'q' or 'quit' to exit the application")
        print("  • Type '?' or 'help' to see this help screen")
        
        print("\n💡 Tips:")
        print("  • Windows + H: Use speech-to-text input (Windows only)")
        print("  • Press Ctrl+C to cancel most operations")
        print("  • Use breadcrumbs at top to see your location")
        
        print("\n⌨️  Input Types:")
        print("  • Text: Type any text and press Enter")
        print("  • Numbers: Enter numbers when prompted")
        print("  • Yes/No: Type 'y' for yes, 'n' for no")
        print("  • Lists: Enter the number next to your choice")
        
        self.pause()
    
    # ========================================================================
    # UTILITIES
    # ========================================================================
    
    def pause(self, message: str = "Press Enter to continue..."):
        """Wait for user to press Enter"""
        input(f"\n{Colors.DIM}{message}{Colors.RESET}")
    
    def exit_handler(self) -> bool:
        """
        Handle application exit
        Returns True if should exit, False to cancel
        """
        if self.confirm("Are you sure you want to quit?", default=False):
            self.clear()
            self.success("Goodbye! 👋")
            self.running = False
            return True
        return False
    
    def run(self, main_menu: Menu):
        """
        Start the CLI application
        
        Args:
            main_menu: The root menu to start with
        """
        try:
            self.show_menu(main_menu)
        except KeyboardInterrupt:
            print()
            self.exit_handler()
        finally:
            self.cleanup()
    
    def cleanup(self):
        """Clean up before exit (placeholder for logging, etc.)"""
        pass
    
    # ========================================================================
    # LOGGING (Minimal)
    # ========================================================================
    
    def log(self, message: str, level: str = "INFO"):
        """
        Simple logging - can expand later
        For now just prints to console with timestamp
        """
        timestamp = time.strftime("%Y-%m-%d %H:%M:%S")
        print(f"{Colors.DIM}[{timestamp}] {level}: {message}{Colors.RESET}")


# ============================================================================
# LOADING INDICATORS
# ============================================================================

class LoadingSpinner:
    """Animated spinner for long operations"""
    
    def __init__(self, message: str = "Loading"):
        self.message = message
        self.spinning = False
        self.thread = None
    
    def _spin(self):
        """Animation loop"""
        spinner = ['⠋', '⠙', '⠹', '⠸', '⠼', '⠴', '⠦', '⠧', '⠇', '⠏']
        idx = 0
        while self.spinning:
            sys.stdout.write(f'\r{Colors.CYAN}{spinner[idx]} {self.message}...{Colors.RESET}')
            sys.stdout.flush()
            idx = (idx + 1) % len(spinner)
            time.sleep(0.1)
        sys.stdout.write('\r' + ' ' * (len(self.message) + 10) + '\r')
        sys.stdout.flush()
    
    def __enter__(self):
        self.spinning = True
        self.thread = threading.Thread(target=self._spin)
        self.thread.start()
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        self.spinning = False
        if self.thread:
            self.thread.join()


class ProgressBar:
    """Simple progress bar for tracking completion"""
    
    def __init__(self, total: int, prefix: str = "Progress", width: int = 40):
        self.total = total
        self.prefix = prefix
        self.width = width
        self.current = 0
    
    def update(self, current: int):
        """Update progress bar to current value"""
        self.current = current
        percent = (current / self.total) * 100
        filled = int(self.width * current / self.total)
        bar = '█' * filled + '░' * (self.width - filled)
        
        sys.stdout.write(f'\r{self.prefix}: |{bar}| {percent:.1f}%')
        sys.stdout.flush()
    
    def complete(self):
        """Mark as complete and move to next line"""
        self.update(self.total)
        print(f" {Colors.GREEN}✓{Colors.RESET}")


# ============================================================================
# EXAMPLE USAGE
# ============================================================================

if __name__ == "__main__":
    # Create CLI instance
    cli = CLI()
    
    # Define some example actions
    def create_workflow():
        cli.clear()
        cli.header("Create New Workflow")
        
        name = cli.input_text("Workflow name", required=True)
        if not name:
            return
        
        description = cli.input_text("Description (optional)", required=False)
        
        # Simulate processing
        with cli.loading_spinner("Creating workflow"):
            time.sleep(2)
        
        cli.success(f"Workflow '{name}' created successfully!")
        cli.pause()
    
    def list_workflows():
        cli.clear()
        cli.header("Your Workflows")
        
        # Example data
        workflows = [
            ["Workflow 1", "Data Processing", "Active"],
            ["Workflow 2", "API Integration", "Draft"],
            ["Workflow 3", "Email Automation", "Active"]
        ]
        
        cli.table(["Name", "Description", "Status"], workflows)
        cli.pause()
    
    def settings_menu():
        settings = Menu(
            title="Settings",
            items=[
                MenuItem("1", "View Configuration", lambda: cli.info("Config: Default settings") or cli.pause()),
                MenuItem("2", "Change Theme", lambda: cli.warning("Theme changing not implemented") or cli.pause()),
            ]
        )
        cli.navigate_to(settings)
    
    # Create main menu
    main_menu = Menu(
        title="AI Workflow Manager",
        items=[
            MenuItem("1", "Create Workflow", create_workflow, "Start a new workflow"),
            MenuItem("2", "List Workflows", list_workflows, "View all your workflows"),
            MenuItem("3", "Settings", settings_menu, "Configure application"),
        ],
        back_enabled=False  # Main menu has no back button
    )
    
    # Run the application
    cli.run(main_menu)