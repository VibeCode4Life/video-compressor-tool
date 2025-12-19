import customtkinter as ctk
from tkinter import filedialog, messagebox
import threading
import os
import shutil
import tempfile
 
from PIL import Image, ImageDraw

import sys
import traceback
from compressor import compress_video, get_video_info, get_thumbnail

# Configuration
ctk.set_appearance_mode("Dark")
ctk.set_default_color_theme("blue")

class VideoCompressorApp(ctk.CTk):
    def __init__(self):
        super().__init__()

        # Window Setup
        self.title("Video Compressor Pro")
        self.geometry("1400x900")
        self.input_video_path = None
        self.temp_output_path = None
        
        # Video Metadata
        self.video_duration = 0
        self.last_compressed_resolution = None # Track last success
        self.is_compressing = False
        
        # Threading control
        self.stop_event = threading.Event()
        
        # UI Constants
        self.PREVIEW_WIDTH = 550
        self.PREVIEW_HEIGHT = 380
        
        # Resolution mapping (Label -> Height int)
        self.ALL_RESOLUTIONS = {
            "144p": 144,
            "240p": 240,
            "360p": 360,
            "480p": 480,
            "720p": 720,
            "1080p": 1080,
            "1440p": 1440,
            "2160p (4K)": 2160
        }

        # Grid Layout
        self.grid_columnconfigure(1, weight=1)
        self.grid_rowconfigure(0, weight=1)

        # Sidebar
        self.sidebar_frame = ctk.CTkFrame(self, width=250, corner_radius=0)
        self.sidebar_frame.grid(row=0, column=0, rowspan=4, sticky="nsew")
        self.sidebar_frame.grid_rowconfigure(4, weight=1)

        self.logo_label = ctk.CTkLabel(self.sidebar_frame, text="Compressor Pro", font=ctk.CTkFont(size=24, weight="bold"))
        self.logo_label.grid(row=0, column=0, padx=20, pady=(30, 20))

        self.upload_btn = ctk.CTkButton(self.sidebar_frame, text="Open Video", command=self.open_file_dialog, height=40, font=ctk.CTkFont(size=14))
        self.upload_btn.grid(row=1, column=0, padx=20, pady=15)

        self.res_label = ctk.CTkLabel(self.sidebar_frame, text="Target Resolution:", anchor="w", font=ctk.CTkFont(size=14))
        self.res_label.grid(row=2, column=0, padx=20, pady=(20, 5))

        self.resolution_var = ctk.StringVar(value="Select Video First")
        self.resolution_menu = ctk.CTkOptionMenu(self.sidebar_frame, values=["Select Video First"],
                                                 state="disabled",
                                                 command=self.change_resolution_event, variable=self.resolution_var, height=35)
        self.resolution_menu.grid(row=3, column=0, padx=20, pady=10)

        self.compress_btn = ctk.CTkButton(self.sidebar_frame, text="Start Compression", command=self.start_compression, state="disabled", 
                                          fg_color="green", height=50, font=ctk.CTkFont(size=16, weight="bold"))
        self.compress_btn.grid(row=5, column=0, padx=20, pady=20)
        
        self.save_btn = ctk.CTkButton(self.sidebar_frame, text="Save Video", command=self.save_video, state="disabled", 
                                      fg_color="blue", height=40, font=ctk.CTkFont(size=14, weight="bold"))
        self.save_btn.grid(row=6, column=0, padx=20, pady=(0, 20))

        # Main Area
        self.main_frame = ctk.CTkFrame(self, corner_radius=10)
        self.main_frame.grid(row=0, column=1, padx=20, pady=20, sticky="nsew")
        self.main_frame.grid_columnconfigure(0, weight=1)
        self.main_frame.grid_columnconfigure(1, weight=1)
        self.main_frame.grid_rowconfigure(0, weight=1)

        # === Input Section ===
        self.input_frame = ctk.CTkFrame(self.main_frame, fg_color="transparent")
        self.input_frame.grid(row=0, column=0, padx=10, pady=10, sticky="nsew")
        
        self.input_label_title = ctk.CTkLabel(self.input_frame, text="Input Video", font=ctk.CTkFont(size=18, weight="bold"))
        self.input_label_title.pack(pady=(10,5))
        
        # Info label for resolution
        self.input_info_label = ctk.CTkLabel(self.input_frame, text="", font=ctk.CTkFont(size=13), text_color="gray70")
        self.input_info_label.pack()

        self.input_preview_label = ctk.CTkLabel(self.input_frame, text="No Video Selected\nClick to Open", width=self.PREVIEW_WIDTH, height=self.PREVIEW_HEIGHT, 
                                                fg_color="gray20", corner_radius=15, font=ctk.CTkFont(size=16))
        self.input_preview_label.pack(pady=5, padx=10)
        self.input_preview_label.bind("<Button-1>", lambda e: self.play_video_system(self.input_video_path))
        
        # === Output Section ===
        self.output_frame = ctk.CTkFrame(self.main_frame, fg_color="transparent")
        self.output_frame.grid(row=0, column=1, padx=10, pady=10, sticky="nsew")
        
        self.output_label_title = ctk.CTkLabel(self.output_frame, text="Output Preview", font=ctk.CTkFont(size=18, weight="bold"))
        self.output_label_title.pack(pady=(10,5))
        
        self.output_info_label = ctk.CTkLabel(self.output_frame, text="", font=ctk.CTkFont(size=13), text_color="gray70")
        self.output_info_label.pack()
        
        self.output_preview_label = ctk.CTkLabel(self.output_frame, text="Waiting for compression...", width=self.PREVIEW_WIDTH, height=self.PREVIEW_HEIGHT, 
                                                 fg_color="gray20", corner_radius=15, font=ctk.CTkFont(size=16))
        self.output_preview_label.pack(pady=5, padx=10)
        self.output_preview_label.bind("<Button-1>", lambda e: self.play_video_system(self.temp_output_path))

        # Progress
        self.progressbar = ctk.CTkProgressBar(self.main_frame, height=15)
        self.progressbar.grid(row=2, column=0, columnspan=2, padx=40, pady=(20, 10), sticky="ew")
        self.progressbar.set(0)
        self.status_label = ctk.CTkLabel(self.main_frame, text="Ready", font=ctk.CTkFont(size=14))
        self.status_label.grid(row=3, column=0, columnspan=2, pady=(0, 20))

    def reset_preview_label(self, which="output", text_placeholder="..."):
        """
        Robustly recreates the preview label widget.
        'which' can be 'input' or 'output'.
        This fixes the persistent 'image "pyimage2" doesn't exist' Tkinter error.
        """
        try:
            if which == "output":
                # Destroy old widget if it exists
                if hasattr(self, 'output_preview_label') and self.output_preview_label:
                    try:
                         self.output_preview_label.destroy()
                    except: pass
                
                # Recreate
                self.output_preview_label = ctk.CTkLabel(self.output_frame, text=text_placeholder, width=self.PREVIEW_WIDTH, height=self.PREVIEW_HEIGHT, 
                                                         fg_color="gray20", corner_radius=15, font=ctk.CTkFont(size=16))
                self.output_preview_label.pack(pady=5, padx=10)
                # Rebind
                self.output_preview_label.bind("<Button-1>", lambda e: self.play_video_system(self.temp_output_path))
                
            elif which == "input":
                if hasattr(self, 'input_preview_label') and self.input_preview_label:
                    try:
                        self.input_preview_label.destroy()
                    except: pass
                
                self.input_preview_label = ctk.CTkLabel(self.input_frame, text=text_placeholder, width=self.PREVIEW_WIDTH, height=self.PREVIEW_HEIGHT, 
                                                        fg_color="gray20", corner_radius=15, font=ctk.CTkFont(size=16))
                self.input_preview_label.pack(pady=5, padx=10)
                self.input_preview_label.bind("<Button-1>", lambda e: self.play_video_system(self.input_video_path))
                
        except Exception as e:
            print(f"Critical error resetting label: {e}")
            traceback.print_exc()

    def change_resolution_event(self, new_res):
        try:
            # Check if this resolution was just compressed
            if self.last_compressed_resolution and new_res == self.last_compressed_resolution:
                self.compress_btn.configure(state="disabled")
            else:
                if self.input_video_path:
                    self.compress_btn.configure(state="normal")
        except Exception as e:
            print(f"Error in change resolution: {e}")

    def draw_play_overlay(self, pil_image):
        """Draws a play button overlay on the image."""
        try:
            if not pil_image: return None
            
            overlay_img = pil_image.copy()
            draw = ImageDraw.Draw(overlay_img, "RGBA")
            
            w, h = overlay_img.size
            cx, cy = w // 2, h // 2
            
            # Draw Circle
            radius = 40
            draw.ellipse((cx - radius, cy - radius, cx + radius, cy + radius), fill=(0, 0, 0, 150), outline=(255, 255, 255, 200), width=2)
            
            # Draw Triangle
            tri_radius = 15
            p1 = (cx - tri_radius // 2, cy - tri_radius)
            p2 = (cx - tri_radius // 2, cy + tri_radius)
            p3 = (cx + tri_radius, cy)
            draw.polygon([p1, p2, p3], fill=(255, 255, 255, 255))
            
            return overlay_img
        except Exception as e:
            print(f"Error drawing overlay: {e}")
            return pil_image

    def open_file_dialog(self):
        try:
            file_path = filedialog.askopenfilename(filetypes=[("Video Files", "*.mp4 *.mov *.avi *.mkv")])
            if file_path:
                self.input_video_path = file_path
                self.reset_preview_label("input", "Loading...")
                self.show_thumbnail_with_overlay(file_path, "input")
                
                # Get video info to set resolutions
                info = get_video_info(file_path)
                if info:
                    orig_w = info.get('width', 0)
                    orig_h = info.get('height', 0)
                    self.video_duration = info.get('duration', 0)
                    self.input_info_label.configure(text=f"Original Size: {orig_w}x{orig_h} ")
                    self.update_resolution_options(orig_h)
                else:
                    self.input_info_label.configure(text="Could not read resolution")
                    self.video_duration = 0
                    self.update_resolution_options(9999) 
                
                self.status_label.configure(text=f"Loaded: {os.path.basename(file_path)}")
                
                # Reset output
                self.last_compressed_resolution = None 
                self.reset_preview_label("output", "Waiting for compression...")

                self.output_info_label.configure(text="")
                self.temp_output_path = None
                self.save_btn.configure(state="disabled")
        except Exception as e:
            messagebox.showerror("Error Opening File", f"An error occurred while opening the file:\n{str(e)}")
            traceback.print_exc()

    def update_resolution_options(self, original_height):
        try:
            # Filter resolutions strictly lower than original
            available_res = [k for k, v in self.ALL_RESOLUTIONS.items() if v < original_height]
            
            # Sort them numerically descending
            available_res.sort(key=lambda x: self.ALL_RESOLUTIONS[x], reverse=True)
            
            if not available_res:
                available_res = ["No Lower Res Available"]
                self.resolution_menu.configure(values=available_res, state="disabled")
                self.resolution_var.set("No Lower Res Available")
                self.compress_btn.configure(state="disabled")
            else:
                self.resolution_menu.configure(values=available_res, state="normal")
                self.resolution_var.set(available_res[0]) 
                self.compress_btn.configure(state="normal")
        except Exception as e:
            print(f"Error updating options: {e}")

    def show_thumbnail_with_overlay(self, video_path, which_label="input"):
        try:
            thumb = get_thumbnail(video_path)
            if thumb:
                # Force size for clean UI
                thumb = thumb.resize((self.PREVIEW_WIDTH, self.PREVIEW_HEIGHT), Image.Resampling.LANCZOS)
                
                img_with_overlay = self.draw_play_overlay(thumb)
                
                ctk_image = ctk.CTkImage(light_image=img_with_overlay, dark_image=img_with_overlay, size=(self.PREVIEW_WIDTH, self.PREVIEW_HEIGHT))
                
                label_widget = self.input_preview_label if which_label == "input" else self.output_preview_label
                label_widget.configure(image=ctk_image, text="")
                
                # KEEP A REFERENCE! This prevents the image from being garbage collected
                label_widget.image = ctk_image 
            else:
               pass # Leave as default text
        except Exception as e:
             print(f"Thumb error: {e}")
             # If error setting image, try reset
             self.reset_preview_label(which_label, "Preview Error")

    def play_video_system(self, video_path):
        """Opens the video in the system default player."""
        if not video_path:
            if not self.input_video_path and video_path == self.input_video_path:
                 self.open_file_dialog()
            return
            
        # BLOCK opening output video if currently compressing
        if self.is_compressing and video_path == self.temp_output_path:
            return
        
        try:
            if os.name == 'nt': # Windows
                os.startfile(video_path)
            else: # MacOS/Linux
                import subprocess
                opener = "open" if sys.platform == "darwin" else "xdg-open"
                subprocess.call([opener, video_path])
        except Exception as e:
            messagebox.showerror("Error", f"Could not open video player: {e}")

    def start_compression(self):
        try:
            # Check if already running -> Cancel
            if self.compress_btn.cget('text') == "Cancel Compression":
                self.cancel_compression()
                return
                
            if not self.input_video_path: return
            
            res_str = self.resolution_var.get()
            if res_str not in self.ALL_RESOLUTIONS:
                messagebox.showerror("Error", "Invalid resolution selected")
                return

            target_height = self.ALL_RESOLUTIONS[res_str]
            
            temp_fd, temp_path = tempfile.mkstemp(suffix=".mp4")
            os.close(temp_fd)
            self.temp_output_path = temp_path
            
            # Start New Compression: Clear previous preview by re-creating label
            self.reset_preview_label("output", "Compressing...")
            self.output_info_label.configure(text="")

            self.last_compressed_resolution = None # Reset for this new run
            
            # Set State to Running
            self.stop_event.clear()
            self.is_compressing = True
            
            # Change Button to Cancel
            self.compress_btn.configure(text="Cancel Compression", fg_color="red", hover_color="darkred")
            
            self.upload_btn.configure(state="disabled")
            self.save_btn.configure(state="disabled")
            self.resolution_menu.configure(state="disabled")
            self.progressbar.set(0) # Reset
            self.status_label.configure(text=f"Compressing to {res_str}...")

            threading.Thread(target=self.run_compression_thread, args=(self.input_video_path, self.temp_output_path, target_height), daemon=True).start()
        except Exception as e:
            messagebox.showerror("Error Starting", f"Could not start compression: {e}")
            self.compression_finished(False)

    def cancel_compression(self):
        self.status_label.configure(text="Cancelling...")
        self.stop_event.set()

    def update_progress(self, percentage):
        """Callback to update progress bar from thread."""
        try:
            self.progressbar.set(percentage)
            self.status_label.configure(text=f"Compressing... {int(percentage * 100)}%")
        except:
            pass

    def run_compression_thread(self, input_path, output_path, target_height):
        try:
            def progress_callback(p):
                self.after(0, lambda: self.update_progress(p))
                
            success = compress_video(input_path, output_path, target_height, 
                                     total_duration=self.video_duration, 
                                     progress_callback=progress_callback,
                                     stop_event=self.stop_event)
            self.after(0, lambda: self.compression_finished(success))
        except Exception as e:
            print(f"Thread Error: {e}")
            traceback.print_exc()
            self.after(0, lambda: self.compression_finished(False))

    def compression_finished(self, success):
        self.is_compressing = False
        try:
            # Reset Button to Start
            self.compress_btn.configure(text="Start Compression", fg_color="green", hover_color="darkgreen", state="normal")
            
            self.resolution_menu.configure(state="normal")
            self.upload_btn.configure(state="normal")
            
            if success:
                self.progressbar.set(1)
                self.status_label.configure(text="Compression Done!")
                self.show_thumbnail_with_overlay(self.temp_output_path, "output")
                
                # Show output info
                info = get_video_info(self.temp_output_path)
                if info:
                    self.output_info_label.configure(text=f"Result Size: {info.get('width')}x{info.get('height')} ")
                
                # Mark as last compressed so button disables if user selects this resolution again
                self.last_compressed_resolution = self.resolution_var.get()
                self.change_resolution_event(self.resolution_var.get())
                
                self.save_btn.configure(state="normal")
                messagebox.showinfo("Success", "Compression complete! Click the preview to watch in your media player.")
            else:
                # Cleanup incomplete temp file
                if self.temp_output_path and os.path.exists(self.temp_output_path):
                    try:
                        os.close(os.open(self.temp_output_path, os.O_RDONLY)) # Ensure no handles?
                        os.remove(self.temp_output_path)
                    except: pass
                self.temp_output_path = None

                self.progressbar.set(0)
                if self.stop_event.is_set():
                     self.status_label.configure(text="Compression Cancelled.")
                     self.reset_preview_label("output", "Cancelled")
                else:
                    self.status_label.configure(text="Compression Failed!")
                    self.reset_preview_label("output", "Failed")
                    messagebox.showerror("Error", "Compression failed. Check console.")
        except Exception as e:
            print(f"Error in finish callback: {e}")

    def save_video(self):
        try:
            if not self.temp_output_path: return
            
            original_name = os.path.basename(self.input_video_path)
            
            # Use the resolution that was *actually* compressed, not the pending dropdown selection
            res_tag = self.last_compressed_resolution if self.last_compressed_resolution else self.resolution_var.get()
            default_name = f"compressed_{res_tag.split(' ')[0]}_{original_name}"
            
            save_path = filedialog.asksaveasfilename(defaultextension=".mp4", 
                                                     filetypes=[("MP4 file", "*.mp4")],
                                                     initialfile=default_name)
            if save_path:
                try:
                    shutil.copy2(self.temp_output_path, save_path)
                    messagebox.showinfo("Saved", f"Video saved to:\n{save_path}")
                except Exception as e:
                    messagebox.showerror("Error", f"Failed to save: {e}")
        except Exception as e:
            messagebox.showerror("Error Saving", f"An error occurred: {e}")

if __name__ == "__main__":
    app = VideoCompressorApp()
    app.mainloop()
