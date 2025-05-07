import tkinter as tk
from tkinter import ttk, messagebox, scrolledtext
import subprocess
import threading
import os
from tkinter.font import Font


def log_to_textbox(line):
    text_log.insert(tk.END, line + '\n')
    text_log.see(tk.END)
    text_log.update_idletasks()


def check_docker_ready():
    try:
        result = subprocess.run(["docker", "info"],
                                stdout=subprocess.PIPE,
                                stderr=subprocess.PIPE,
                                text=True)
        if result.returncode == 0:
            return True
        log_to_textbox(f"❌ Docker error: {result.stderr.strip()}")
        return False
    except FileNotFoundError:
        log_to_textbox("❌ Docker not found. Is Docker installed and in your PATH?")
        return False
    except Exception as e:
        log_to_textbox(f"❌ Docker check failed: {str(e)}")
        return False


def image_exists(image_name):
    try:
        result = subprocess.run(["docker", "images", "-q", image_name],
                                stdout=subprocess.PIPE,
                                stderr=subprocess.PIPE,
                                text=True)
        return bool(result.stdout.strip())
    except Exception as e:
        log_to_textbox(f"❌ Error checking image: {str(e)}")
        return False


def run_command(command, description, input_text=None, timeout=600):
    log_to_textbox(f">>> {description}: {' '.join(command)}")
    log_to_textbox(f"📂 Working dir: {os.getcwd()}")

    try:
        process = subprocess.Popen(
            command,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            stdin=subprocess.PIPE,
            text=True,
            bufsize=1,
            universal_newlines=True
        )

        if input_text:
            stdout, _ = process.communicate(input=input_text + "\n", timeout=timeout)
            log_to_textbox(stdout)
        else:
            for line in process.stdout:
                log_to_textbox(line.strip())

        exit_code = process.wait(timeout=timeout)
        log_to_textbox(f"⌛ Exit code: {exit_code}")

        if exit_code != 0:
            raise subprocess.CalledProcessError(exit_code, command)

        return exit_code

    except subprocess.TimeoutExpired:
        process.kill()
        log_to_textbox(f"⏱️ Timeout after {timeout} seconds")
        raise
    except Exception as e:
        log_to_textbox(f"❌ Error: {str(e)}")
        raise


def download_and_push():
    # Get all input values
    image_name = entry_image.get().strip()
    nexus_repo = entry_nexus.get().strip()
    new_name = entry_new_name.get().strip()  # This can be empty
    username = entry_user.get().strip()
    password = entry_pass.get().strip()

    if not all([image_name, nexus_repo, username, password]):
        messagebox.showerror("Error", "All fields except New Image Name must be filled!")
        return

    def task():
        nonlocal image_name, new_name  # Allow modifying these variables in nested scope
        btn.config(state=tk.DISABLED)
        text_log.delete("1.0", tk.END)

        try:
            # Verify Docker is ready
            if not check_docker_ready():
                raise RuntimeError("Docker service not available")

            # Check Docker version
            run_command(["docker", "version"], "Check Docker Version", timeout=10)

            # Remove existing image to force fresh pull
            if image_exists(image_name):
                log_to_textbox(f"ℹ️ Removing existing image: {image_name}")
                run_command(["docker", "rmi", "-f", image_name],
                            "Remove existing image")

            # Pull image with progress
            log_to_textbox("⬇️ Starting image download...")
            run_command(["docker", "pull", image_name],
                        "Pull image",
                        timeout=300)

            # Rename image if new_name is provided
            if new_name:  # Only execute if new_name is not empty
                # Get original tag if not specified in new_name
                if ':' not in new_name:
                    original_tag = image_name.split(':')[-1] if ':' in image_name else 'latest'
                    new_name = f"{new_name}:{original_tag}"

                # Create new tagged image
                run_command(["docker", "tag", image_name, new_name],
                            "Tag with new name")

                # Remove old tag
                run_command(["docker", "rmi", image_name],
                            "Remove original tag")

                # Update image_name to the new name
                image_name = new_name
                log_to_textbox(f"✅ Image renamed to: {image_name}")

            # Tag for Nexus
            target_name = image_name.split("/")[-1]
            nexus_tag = f"{nexus_repo}/{target_name}"
            run_command(["docker", "tag", image_name, nexus_tag],
                        "Tag image for Nexus")

            # Login to Nexus
            log_to_textbox("🔐 Logging in to Nexus...")
            run_command(["docker", "login", nexus_repo, "-u", username, "--password-stdin"],
                        "Login to Nexus",
                        input_text=password,
                        timeout=60)

            # Push to Nexus
            log_to_textbox("⬆️ Pushing to Nexus...")
            run_command(["docker", "push", nexus_tag],
                        "Push to Nexus",
                        timeout=600)

            log_to_textbox("✅ Success: Image successfully pushed to Nexus.")
            messagebox.showinfo("Success", "Image successfully pushed to Nexus.")

        except subprocess.CalledProcessError as e:
            log_to_textbox(f"❌ Command failed with exit code {e.returncode}")
        except Exception as e:
            log_to_textbox(f"❌ Process failed: {str(e)}")
            messagebox.showerror("Error", f"Process failed: {str(e)}")
        finally:
            btn.config(state=tk.NORMAL)

    threading.Thread(target=task, daemon=True).start()
def toggle_password():
    if entry_pass.cget('show') == '*':
        entry_pass.config(show='')
        btn_toggle_pass.config(text="Hide Password")
    else:
        entry_pass.config(show='*')
        btn_toggle_pass.config(text="Show Password")


# GUI Setup
root = tk.Tk()
root.title("MDP - DockerHub to Nexus Pusher")
root.geometry("900x750")
root.resizable(False, False)

# Style configuration
style = ttk.Style()
style.configure('TFrame', background='#f0f0f0')
style.configure('TLabel', background='#f0f0f0', font=('Segoe UI', 10))
style.configure('TButton', font=('Segoe UI', 10))
style.map('TButton', background=[('active', '#45a049')])

# Main container
main_frame = ttk.Frame(root, padding="20")
main_frame.pack(fill=tk.BOTH, expand=True)

# Header
header_frame = ttk.Frame(main_frame)
header_frame.pack(fill=tk.X, pady=(0, 20))

title_font = Font(family='Segoe UI', size=14, weight='bold')
ttk.Label(header_frame, text="DockerHub to Nexus Image Pusher", font=title_font,
          background='#f0f0f0').pack(side=tk.LEFT)

# Form container
form_frame = ttk.LabelFrame(main_frame, text="Image Details", padding=15)
form_frame.pack(fill=tk.X, pady=(0, 20))

# Form fields
fields = [
    ("DockerHub Image (e.g., nginx:latest):", "entry_image"),
    ("Nexus Repository (e.g., nexus.example.com/repository/docker):", "entry_nexus"),
    ("New Image Name (optional - e.g., myapp:v1):", "entry_new_name"),
    ("Nexus Username:", "entry_user"),
    ("Nexus Password:", "entry_pass")
]

for i, (label_text, var_name) in enumerate(fields):
    label = ttk.Label(form_frame, text=label_text)
    label.grid(row=i * 2, column=0, sticky=tk.W, pady=(5 if i > 0 else 0))

    if var_name == "entry_pass":
        entry_frame = ttk.Frame(form_frame)
        entry_frame.grid(row=i * 2 + 1, column=0, sticky=tk.EW, pady=2)

        entry = ttk.Entry(entry_frame, width=60, show="*")
        entry.pack(side=tk.LEFT, fill=tk.X, expand=True)

        btn_toggle_pass = ttk.Button(entry_frame, text="Show", width=8, command=toggle_password)
        btn_toggle_pass.pack(side=tk.LEFT, padx=5)
    else:
        entry = ttk.Entry(form_frame, width=70)
        entry.grid(row=i * 2 + 1, column=0, sticky=tk.EW, pady=2)

    globals()[var_name] = entry

    form_frame.columnconfigure(0, weight=1)

# Set default values for testing
entry_image.insert(0, "nginx:latest")
entry_nexus.insert(0, "nexus.example.com/repository/docker")
entry_new_name.insert(0, "")
entry_user.insert(0, "admin")

# Action button
btn_frame = ttk.Frame(main_frame)
btn_frame.pack(fill=tk.X, pady=(0, 20))

btn = ttk.Button(btn_frame, text="Download & Push to Nexus", command=download_and_push,
                 style='Accent.TButton')
btn.pack(pady=5)

# Log area
log_frame = ttk.LabelFrame(main_frame, text="Process Log", padding=10)
log_frame.pack(fill=tk.BOTH, expand=True)

text_log = scrolledtext.ScrolledText(log_frame, width=100, height=18,
                                     font=('Consolas', 9), wrap=tk.WORD)
text_log.pack(fill=tk.BOTH, expand=True)

# Custom style for the main button
style.configure('Accent.TButton', font=('Segoe UI', 10, 'bold'),
                foreground='black', background='#4CAF50')
style.map('Accent.TButton',
          background=[('active', '#45a049'), ('disabled', '#cccccc')])

# Set focus to first field
entry_image.focus()

root.mainloop()