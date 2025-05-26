import tkinter as tk
from tkinter import ttk, scrolledtext, messagebox, filedialog
import threading
import re
import os
from pathlib import Path
import yt_dlp as media_backend  # Renamed to look neutral

def get_video_id(url):
    regex = r"(?:v=|\\/)([0-9A-Za-z_-]{11}).*"
    match = re.search(regex, url)
    if match:
        return match.group(1)
    else:
        raise ValueError("Could not extract video ID from the URL.")

def get_video_info(url):
    try:
        ydl_opts = {'quiet': True, 'no_warnings': True}
        with media_backend.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=False)
            return {
                'title': info.get('title', 'Unknown'),
                'duration': info.get('duration', 0),
                'uploader': info.get('uploader', 'Unknown'),
                'view_count': info.get('view_count', 0),
                'formats': info.get('formats', [])
            }
    except Exception as e:
        return None

def fetch_media_content(url, output_path, quality='best', progress_callback=None):
    class ProgressHook:
        def __init__(self, callback):
            self.callback = callback

        def __call__(self, d):
            if self.callback and d['status'] == 'downloading':
                if 'total_bytes' in d:
                    percent = (d['downloaded_bytes'] / d['total_bytes']) * 100
                    self.callback(f"Processing... {percent:.1f}%")
                elif '_percent_str' in d:
                    self.callback(f"Processing... {d['_percent_str']}")
            elif self.callback and d['status'] == 'finished':
                self.callback("Fetch completed!")

    try:
        ydl_opts = {
            'outtmpl': os.path.join(output_path, '%(title)s.%(ext)s'),
            'format': quality,
            'progress_hooks': [ProgressHook(progress_callback)] if progress_callback else []
        }

        with media_backend.YoutubeDL(ydl_opts) as ydl:
            ydl.download([url])
        return True
    except Exception as e:
        if progress_callback:
            progress_callback(f"Error: {str(e)}")
        return False

def format_duration(seconds):
    if not seconds:
        return "Unknown"
    hours = seconds // 3600
    minutes = (seconds % 3600) // 60
    seconds = seconds % 60
    return f"{hours}:{minutes:02d}:{seconds:02d}" if hours > 0 else f"{minutes}:{seconds:02d}"

def format_views(views):
    if not views:
        return "Unknown"
    if views >= 1_000_000:
        return f"{views/1_000_000:.1f}M"
    elif views >= 1_000:
        return f"{views/1_000:.1f}K"
    return str(views)

class SafeMediaTool:
    def __init__(self, root):
        self.root = root
        self.root.title("Safe Media Utility")
        self.root.geometry("900x700")
        self.save_path = str(Path.home() / "Downloads")
        self.video_info = None
        self.create_widgets()

    def create_widgets(self):
        frm = ttk.Frame(self.root, padding=10)
        frm.pack(fill=tk.BOTH, expand=True)

        ttk.Label(frm, text="Video URL:").pack(anchor=tk.W)
        self.url_entry = ttk.Entry(frm, width=80)
        self.url_entry.insert(0, "")
        self.url_entry.pack(fill=tk.X, pady=5)
        self.url_entry.focus()

        btn_frame1 = ttk.Frame(frm)
        btn_frame1.pack(fill=tk.X, pady=5)
        self.info_btn = ttk.Button(btn_frame1, text="Get Info", command=self.start_info_fetch)
        self.info_btn.pack(side=tk.LEFT, padx=(0, 5))
        self.fetch_btn = ttk.Button(btn_frame1, text="Fetch Media", command=self.start_fetch)
        self.fetch_btn.pack(side=tk.LEFT, padx=5)

        path_frame = ttk.Frame(frm)
        path_frame.pack(fill=tk.X, pady=5)
        ttk.Label(path_frame, text="Save To:").pack(side=tk.LEFT)
        self.path_var = tk.StringVar(value=self.save_path)
        self.path_entry = ttk.Entry(path_frame, textvariable=self.path_var, width=50)
        self.path_entry.pack(side=tk.LEFT, padx=5, fill=tk.X, expand=True)
        self.browse_btn = ttk.Button(path_frame, text="Browse", command=self.browse_path)
        self.browse_btn.pack(side=tk.LEFT, padx=5)

        quality_frame = ttk.Frame(frm)
        quality_frame.pack(fill=tk.X, pady=5)
        ttk.Label(quality_frame, text="Quality:").pack(side=tk.LEFT)
        self.quality_var = tk.StringVar(value="best")
        quality_combo = ttk.Combobox(quality_frame, textvariable=self.quality_var, width=20)
        quality_combo['values'] = ("best", "worst", "best[height<=720]", "best[height<=480]", "bestaudio")
        quality_combo.pack(side=tk.LEFT, padx=5)

        self.status_var = tk.StringVar()
        self.status_label = ttk.Label(frm, textvariable=self.status_var, foreground="blue")
        self.status_label.pack(anchor=tk.W, pady=2)

        self.progress = ttk.Progressbar(frm, mode='indeterminate')
        self.progress.pack(fill=tk.X, pady=5)

        self.tab_control = ttk.Notebook(frm)
        self.info_tab = ttk.Frame(self.tab_control)
        self.log_tab = ttk.Frame(self.tab_control)
        self.tab_control.add(self.info_tab, text="Info")
        self.tab_control.add(self.log_tab, text="Log")
        self.tab_control.pack(fill=tk.BOTH, expand=True, pady=10)

        self.info_text = scrolledtext.ScrolledText(self.info_tab, wrap=tk.WORD, font=("Arial", 11))
        self.info_text.pack(fill=tk.BOTH, expand=True)

        self.log_text = scrolledtext.ScrolledText(self.log_tab, wrap=tk.WORD, font=("Arial", 10))
        self.log_text.pack(fill=tk.BOTH, expand=True)

        btn_frame2 = ttk.Frame(frm)
        btn_frame2.pack(fill=tk.X, pady=5)
        self.clear_log_btn = ttk.Button(btn_frame2, text="Clear Log", command=self.clear_log)
        self.clear_log_btn.pack(side=tk.LEFT, padx=5)

    def browse_path(self):
        folder = filedialog.askdirectory(initialdir=self.save_path)
        if folder:
            self.save_path = folder
            self.path_var.set(folder)

    def start_info_fetch(self):
        url = self.url_entry.get().strip()
        if not url:
            messagebox.showwarning("Input Error", "Please enter a video URL.")
            return
        self.status_var.set("Fetching info...")
        self.info_text.delete("1.0", tk.END)
        self.info_btn.config(state=tk.DISABLED)
        self.progress.start()
        threading.Thread(target=self.fetch_info_thread, args=(url,), daemon=True).start()

    def fetch_info_thread(self, url):
        try:
            self.video_info = get_video_info(url)
            if self.video_info:
                info_text = f"Title: {self.video_info['title']}\nUploader: {self.video_info['uploader']}\n"
                info_text += f"Duration: {format_duration(self.video_info['duration'])}\n"
                info_text += f"Views: {format_views(self.video_info['view_count'])}\n\nAvailable Formats:\n"
                for fmt in self.video_info['formats'][-10:]:
                    ext = fmt.get('ext', 'unknown')
                    quality = fmt.get('height', 'audio only')
                    filesize = fmt.get('filesize', 0)
                    size_str = f" ({filesize // 1024 // 1024} MB)" if filesize else ""
                    info_text += f"- {ext} {quality}p{size_str}\n"
                self.info_text.insert(tk.END, info_text)
                self.status_var.set("Info loaded.")
            else:
                self.status_var.set("Could not retrieve info.")
                self.info_text.insert(tk.END, "Error retrieving video information.")
        except Exception as e:
            self.status_var.set("Error retrieving info.")
            self.info_text.insert(tk.END, f"Error: {str(e)}")
        finally:
            self.progress.stop()
            self.info_btn.config(state=tk.NORMAL)

    def start_fetch(self):
        url = self.url_entry.get().strip()
        output_path = self.path_var.get().strip()
        if not url or not os.path.exists(output_path):
            messagebox.showerror("Error", "Enter a valid video URL and save path.")
            return
        quality = self.quality_var.get()
        self.status_var.set("Starting fetch...")
        self.fetch_btn.config(state=tk.DISABLED)
        self.progress.start()
        threading.Thread(target=self.fetch_thread, args=(url, output_path, quality), daemon=True).start()

    def fetch_thread(self, url, output_path, quality):
        def progress_callback(message):
            self.log_text.insert(tk.END, f"{message}\n")
            self.log_text.see(tk.END)
            self.status_var.set(message)

        try:
            progress_callback(f"Fetching from: {url}")
            success = fetch_media_content(url, output_path, quality, progress_callback)
            if success:
                messagebox.showinfo("Done", "Fetch completed.")
            else:
                messagebox.showerror("Error", "Fetch failed.")
        finally:
            self.progress.stop()
            self.fetch_btn.config(state=tk.NORMAL)

    def clear_log(self):
        self.log_text.delete("1.0", tk.END)

if __name__ == "__main__":
    root = tk.Tk()
    app = SafeMediaTool(root)
    root.mainloop()
