"""Pantheon CLI Wrapper — Routes commands to different operational modes."""

import argparse
import os
import subprocess
import sys
import shutil


def get_sudo_cmd(cmd: list[str]) -> list[str]:
    """Prepend sudo to a command if needed and available."""
    if os.geteuid() == 0:
        return cmd # Already root
        
    if shutil.which("sudo"):
        return ["sudo"] + cmd
        
    # Running as non-root without sudo available, just return original command and let it fail naturally
    return cmd


def run_systemctl(action: str) -> None:
    """Run a systemctl command for the apex service."""
    # Special handling for reset
    if action == "reset":
        print("Resetting service (clearing session memory and reloading schedules)...")
        action = "restart"

    try:
        # Check if we have sudo privileges or can run systemctl
        cmd = get_sudo_cmd(["systemctl", action, "apex"])
            
        print(f"Executing: {' '.join(cmd)}")
        subprocess.run(cmd, check=True)
    except subprocess.CalledProcessError as e:
        print(f"Error managing service: {e}", file=sys.stderr)
        sys.exit(1)
    except FileNotFoundError:
        print("Error: 'systemctl' not found. Is this a systemd environment?", file=sys.stderr)
        sys.exit(1)


def cmd_service(args: argparse.Namespace) -> None:
    """Handle the 'service' subcommand."""
    action = args.action
    
    if action in ["start", "stop", "restart", "status", "reset"]:
        run_systemctl(action)
    else:
        # If no arguments provided or invalid, just run the background service inline
        # This is what systemd will actually execute
        import logging
        logging.basicConfig(
            level=logging.WARNING, # Changed to WARNING to reduce noise by default
            format="%(asctime)s [%(name)s] %(levelname)s: %(message)s",
            datefmt="%H:%M:%S",
            force=True,
        )
        logging.getLogger("pantheon").setLevel(logging.INFO)
        
        import asyncio
        from pantheon.main import start
        
        print("Starting APEX in service mode (Telegram + Schedulers)...")
        try:
            asyncio.run(start(mode="telegram", no_schedulers=False))
        except KeyboardInterrupt:
            pass
        except Exception as e:
            logging.error("Fatal error: %s", e, exc_info=True)
            sys.exit(1)


def cmd_chat(args: argparse.Namespace) -> None:
    """Handle the 'chat' subcommand."""
    import logging
    logging.basicConfig(
        level=logging.WARNING,
        format="%(asctime)s [%(name)s] %(levelname)s: %(message)s",
        datefmt="%H:%M:%S",
        force=True,
    )
    logging.getLogger("pantheon").setLevel(logging.INFO)
    
    import asyncio
    from pantheon.main import start
    
    # Run the interactive CLI without background schedulers
    try:
        asyncio.run(start(mode="cli", no_schedulers=True))
    except KeyboardInterrupt:
        pass
    except Exception as e:
        logging.error("Fatal error: %s", e, exc_info=True)
        sys.exit(1)


def cmd_config(args: argparse.Namespace) -> None:
    """Handle the 'config' subcommand."""
    from pantheon.configurator import run_configurator
    run_configurator()


def cmd_uninstall(args: argparse.Namespace) -> None:
    """Handle the 'uninstall' subcommand."""
    print("Warning: This will completely remove APEX, its configuration, and its memory database.")
    
    if os.geteuid() != 0 and not shutil.which("sudo"):
        print("Please run this command as root (e.g. su -c 'pantheon uninstall')", file=sys.stderr)
        sys.exit(1)
    elif os.geteuid() != 0:
        print("Please run this command with sudo: sudo pantheon uninstall", file=sys.stderr)
        sys.exit(1)
        
    confirm = input("Are you sure you want to uninstall? (y/N): ")
    if confirm.lower() != 'y':
        print("Uninstall cancelled.")
        sys.exit(0)

    print("Stopping and removing background service...")
    try:
        stop_cmd = get_sudo_cmd(["systemctl", "stop", "apex"])
        disable_cmd = get_sudo_cmd(["systemctl", "disable", "apex"])
        subprocess.run(stop_cmd, stderr=subprocess.DEVNULL)
        subprocess.run(disable_cmd, stderr=subprocess.DEVNULL)
    except Exception:
        pass
        
    service_file = "/etc/systemd/system/apex.service"
    if os.path.exists(service_file):
        try:
            rm_cmd = get_sudo_cmd(["rm", "-f", service_file])
            subprocess.run(rm_cmd, check=True)
            reload_cmd = get_sudo_cmd(["systemctl", "daemon-reload"])
            subprocess.run(reload_cmd, stderr=subprocess.DEVNULL)
        except Exception:
            pass
            
    symlink_path = "/usr/local/bin/pantheon"
    install_dir = "/opt/apex"
    
    if os.path.islink(symlink_path):
        target = os.readlink(symlink_path)
        if ".venv" in target:
            install_dir = target.split(".venv")[0].rstrip("/")
        try:
            rm_link_cmd = get_sudo_cmd(["rm", "-f", symlink_path])
            subprocess.run(rm_link_cmd)
        except Exception:
            pass
        
    print(f"Removing installation directory: {install_dir} ...")
    
    # Spawn a detached process to delete the folder to avoid issues with deleting the running python binary
    delete_cmd = get_sudo_cmd(["bash", "-c", f"sleep 1 && rm -rf '{install_dir}'"])
    subprocess.Popen(delete_cmd)
    
    print("Pantheon APEX has been successfully scheduled for uninstallation. It will disappear in a moment. Goodbye!")
    sys.exit(0)


def cmd_update(args: argparse.Namespace) -> None:
    """Handle the 'update' subcommand."""
    print("Checking for updates from https://github.com/bryanmandville/pantheon_bot ...")
    
    install_dir = "/opt/apex"
    symlink_path = "/usr/local/bin/pantheon"
    if os.path.islink(symlink_path):
        target = os.readlink(symlink_path)
        if ".venv" in target:
            install_dir = target.split(".venv")[0].rstrip("/")
            
    try:
        os.chdir(install_dir)
    except FileNotFoundError:
        print(f"Error: Installation directory not found at {install_dir}")
        sys.exit(1)
        
    if not os.path.exists(".git"):
        print("Error: The installation directory is not a git repository.")
        print("Please clone https://github.com/bryanmandville/pantheon_bot into this directory.")
        sys.exit(1)
        
    try:
        # Check permissions
        if not os.access(install_dir, os.W_OK) and os.geteuid() != 0:
            if shutil.which("sudo"):
                print("Warning: You may need to run this command with sudo to update files.", file=sys.stderr)
            else:
                print("Warning: You may need to run this command as root to update files.", file=sys.stderr)
            
        # Fetch latest
        subprocess.run(["git", "fetch"], check=True)
        
        # Compare HEAD with upstream config
        local_hash = subprocess.check_output(["git", "rev-parse", "HEAD"]).strip().decode('utf-8')
        try:
            remote_hash = subprocess.check_output(["git", "rev-parse", "@{u}"]).strip().decode('utf-8')
        except subprocess.CalledProcessError:
            print("No upstream branch configured. Pulling main manually...")
            subprocess.run(["git", "pull", "origin", "main"], check=True)
            remote_hash = subprocess.check_output(["git", "rev-parse", "HEAD"]).strip().decode('utf-8')

        if local_hash == remote_hash:
            print("Pantheon APEX is already up-to-date!")
            return
            
        print("Updates found! Stashing any local operational changes...")
        # Stash changes to files like CRON.md or agents/ to prevent overwrite conflicts
        stash_result = subprocess.run(["git", "stash"], capture_output=True, text=True)
        stashed = "No local changes" not in stash_result.stdout
            
        print("Pulling latest core system changes...")
        subprocess.run(["git", "pull"], check=True)
        
        if stashed:
            print("Restoring local operational changes...")
            try:
                subprocess.run(["git", "stash", "pop"], check=True, capture_output=True)
            except subprocess.CalledProcessError:
                print("Warning: Merge conflict restoring local changes. Please check git status.", file=sys.stderr)
        
        print("Re-installing dependencies to ensure everything is current...")
        subprocess.run([".venv/bin/pip", "install", "-e", "."], check=True)
        
        print("Restarting background service to apply changes...")
        run_systemctl("restart")
        
        print("Update complete! 🎉")
        
    except subprocess.CalledProcessError as e:
        print(f"Error during update process: {e.cmd}", file=sys.stderr)
        sys.exit(1)
    except Exception as e:
        print(f"Unexpected error: {e}", file=sys.stderr)
        sys.exit(1)


def main() -> None:
    """Main CLI entrypoint."""
    parser = argparse.ArgumentParser(
        description="Pantheon — AI Agent Mesh powered by Gemini 2.5 Pro",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  pantheon chat                Start the interactive CLI
  pantheon config              Run the interactive configuration wizard
  pantheon service start       Start the background systemd service
  pantheon service reset       Restart the service, wiping in-memory session 
  pantheon update              Check for updates from GitHub and apply them
  pantheon uninstall           Completely remove APEX from this system
"""
    )
    
    subparsers = parser.add_subparsers(dest="command", required=True)

    # Chat subcommand
    chat_parser = subparsers.add_parser("chat", help="Start the interactive terminal chat CLI")
    
    # Config subcommand
    config_parser = subparsers.add_parser("config", help="Run the interactive configuration wizard")
    
    # Update subcommand
    update_parser = subparsers.add_parser("update", help="Check for updates from GitHub and apply them")
    
    # Uninstall subcommand
    uninstall_parser = subparsers.add_parser("uninstall", help="Completely remove APEX from this system")
    
    # Service subcommand
    service_parser = subparsers.add_parser("service", help="Manage the background systemd service")
    # Action is optional because systemd will run `pantheon service` with no actions to start the daemon process
    service_parser.add_argument(
        "action", 
        nargs="?",
        choices=["start", "stop", "restart", "status", "reset", "daemon"],
        default="daemon",
        help="Systemctl action (omit to run the daemon process inline)"
    )

    args = parser.parse_args()

    if args.command == "chat":
        cmd_chat(args)
    elif args.command == "config":
        cmd_config(args)
    elif args.command == "service":
        cmd_service(args)
    elif args.command == "update":
        cmd_update(args)
    elif args.command == "uninstall":
        cmd_uninstall(args)

if __name__ == "__main__":
    main()
