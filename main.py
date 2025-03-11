import customtkinter as ctk
import tkinter as tk
from tkinter import messagebox, ttk, filedialog
import yt_dlp
import json
import os
import shutil
from threading import Thread
from PIL import Image
import browser_cookie3
import time
import logging
import traceback

# 配置日志
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(levelname)s - %(message)s'
)

class VideoDownloader(ctk.CTk):
    def __init__(self):
        super().__init__()
        self.logger = logging.getLogger(__name__)

        # 配置窗口
        self.title("StreamHarvester - 视频下载工具")
        self.geometry("800x700")
        
        # 设置主题
        ctk.set_appearance_mode("dark")
        ctk.set_default_color_theme("blue")

        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(0, weight=1)

        # 创建主框架
        self.main_frame = ctk.CTkFrame(self)
        self.main_frame.grid(row=0, column=0, padx=20, pady=20, sticky="nsew")
        self.main_frame.grid_columnconfigure(0, weight=1)

        # URL输入框
        self.url_label = ctk.CTkLabel(self.main_frame, text="视频链接:")
        self.url_label.grid(row=0, column=0, padx=10, pady=(10, 5), sticky="w")
        
        self.url_entry = ctk.CTkEntry(self.main_frame, width=400)
        self.url_entry.grid(row=1, column=0, padx=10, pady=(0, 10), sticky="ew")

        # Cookie设置框架
        self.cookie_frame = ctk.CTkFrame(self.main_frame)
        self.cookie_frame.grid(row=2, column=0, padx=10, pady=5, sticky="ew")
        self.cookie_frame.grid_columnconfigure(1, weight=1)
        
        self.cookie_label = ctk.CTkLabel(self.cookie_frame, text="Cookie来源:")
        self.cookie_label.grid(row=0, column=0, padx=5, pady=5)
        
        # Cookie选项
        self.cookie_var = tk.StringVar(value="不使用Cookie")
        self.cookie_options = ["不使用Cookie", "Chrome", "Firefox", "Edge", "Opera", "Brave"]
        
        # 创建Cookie选择下拉菜单
        self.browser_menu = ttk.Combobox(
            self.cookie_frame, 
            values=self.cookie_options,
            textvariable=self.cookie_var,
            state="readonly"
        )
        self.browser_menu.grid(row=0, column=1, padx=5, pady=5, sticky="ew")
        
        # Cookie状态标签
        self.cookie_status = ctk.CTkLabel(self.cookie_frame, text="")
        self.cookie_status.grid(row=1, column=0, columnspan=2, padx=5, pady=5)

        self.cookie_file_path = None  # 存储临时cookie文件路径

        # 下载目录选择
        self.dir_frame = ctk.CTkFrame(self.main_frame)
        self.dir_frame.grid(row=3, column=0, padx=10, pady=5, sticky="ew")
        
        self.dir_label = ctk.CTkLabel(self.dir_frame, text="下载目录:")
        self.dir_label.grid(row=0, column=0, padx=5, pady=5)
        
        self.dir_entry = ctk.CTkEntry(self.dir_frame, width=300)
        self.dir_entry.grid(row=0, column=1, padx=5, pady=5, sticky="ew")
        self.dir_entry.insert(0, os.path.expanduser("~/Downloads"))
        
        self.dir_button = ctk.CTkButton(self.dir_frame, text="选择目录", command=self.choose_directory)
        self.dir_button.grid(row=0, column=2, padx=5, pady=5)
        
        self.dir_frame.grid_columnconfigure(1, weight=1)

        # 下载质量选择
        self.quality_frame = ctk.CTkFrame(self.main_frame)
        self.quality_frame.grid(row=4, column=0, padx=10, pady=5, sticky="ew")
        
        self.quality_label = ctk.CTkLabel(self.quality_frame, text="下载质量:")
        self.quality_label.grid(row=0, column=0, padx=5, pady=5)
        
        self.quality_var = tk.StringVar(value="best")
        self.quality_options = {
            "最佳质量": "bestvideo+bestaudio",
            "最佳视频": "bestvideo",
            "最佳音频": "bestaudio",
            "自定义格式": "custom"
        }
        
        for i, (text, value) in enumerate(self.quality_options.items()):
            radio = ctk.CTkRadioButton(
                self.quality_frame, 
                text=text, 
                variable=self.quality_var, 
                value=value,
                command=self.on_quality_change
            )
            radio.grid(row=0, column=i+1, padx=5, pady=5)

        # 获取格式按钮
        self.fetch_button = ctk.CTkButton(self.main_frame, text="获取可用格式", command=self.fetch_formats)
        self.fetch_button.grid(row=5, column=0, padx=10, pady=10)

        # 格式选择框
        self.format_frame = ctk.CTkFrame(self.main_frame)
        self.format_frame.grid(row=6, column=0, padx=10, pady=10, sticky="ew")
        self.format_frame.grid_columnconfigure(0, weight=1)

        # 视频格式选择
        self.video_var = tk.StringVar()
        self.video_label = ctk.CTkLabel(self.format_frame, text="视频格式:")
        self.video_label.grid(row=0, column=0, padx=5, pady=5, sticky="w")
        
        self.video_menu = ttk.Combobox(self.format_frame, textvariable=self.video_var, state="readonly")
        self.video_menu.grid(row=1, column=0, padx=5, pady=5, sticky="ew")
        self.video_menu.bind('<<ComboboxSelected>>', self.on_video_format_change)

        # 音频格式选择
        self.audio_frame = ctk.CTkFrame(self.format_frame)
        self.audio_frame.grid(row=2, column=0, padx=5, pady=5, sticky="ew")
        
        self.audio_var = tk.StringVar()
        self.audio_label = ctk.CTkLabel(self.audio_frame, text="音频格式:")
        self.audio_label.grid(row=0, column=0, padx=5, pady=5, sticky="w")
        
        self.audio_menu = ttk.Combobox(self.audio_frame, textvariable=self.audio_var, state="readonly")
        self.audio_menu.grid(row=1, column=0, padx=5, pady=5, sticky="ew")

        # 下载按钮
        self.download_button = ctk.CTkButton(self.main_frame, text="开始下载", command=self.start_download)
        self.download_button.grid(row=7, column=0, padx=10, pady=10)

        # 进度条
        self.progress_bar = ctk.CTkProgressBar(self.main_frame)
        self.progress_bar.grid(row=8, column=0, padx=10, pady=10, sticky="ew")
        self.progress_bar.set(0)

        # 状态标签
        self.status_label = ctk.CTkLabel(self.main_frame, text="")
        self.status_label.grid(row=9, column=0, padx=10, pady=10)

        self.formats_info = None

    def choose_directory(self):
        dir_path = filedialog.askdirectory(initialdir=self.dir_entry.get())
        if dir_path:
            self.dir_entry.delete(0, tk.END)
            self.dir_entry.insert(0, dir_path)

    def on_quality_change(self):
        quality = self.quality_var.get()
        if quality == "custom":
            self.format_frame.grid()
        else:
            self.format_frame.grid_remove()

    def format_size(self, size):
        if size is None:
            return "未知大小"
        for unit in ['B', 'KB', 'MB', 'GB']:
            if size < 1024:
                return f"{size:.1f}{unit}"
            size /= 1024
        return f"{size:.1f}TB"

    def on_video_format_change(self, event=None):
        selected = self.video_var.get()
        format_id = selected.split(' - ')[0]
        
        for f in self.formats_info:
            if str(f.get('format_id')) == format_id:
                if f.get('acodec') != 'none':
                    self.audio_frame.grid_remove()
                else:
                    self.audio_frame.grid()
                break

    def get_cookie_options(self):
        cookie_mode = self.cookie_var.get()
        self.logger.info(f"Cookie模式: {cookie_mode}")
        
        if cookie_mode == "不使用Cookie":
            return {}
            
        try:
            if cookie_mode in ["Chrome", "Firefox", "Edge", "Opera", "Brave"]:
                url = self.url_entry.get()
                if not url:
                    raise Exception("请先输入视频链接")
                
                self.cookie_status.configure(text="正在获取Cookie...")
                
                # 从URL中提取域名
                domain = url.split('/')[2]
                self.logger.info(f"正在从{cookie_mode}获取 {domain} 的cookies")
                
                # 创建临时cookie文件
                cookie_file = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'temp_cookies.txt')
                self.cookie_file_path = cookie_file
                
                # 根据不同浏览器获取cookies
                try:
                    if cookie_mode == "Chrome":
                        cj = browser_cookie3.chrome(domain_name=domain)
                    elif cookie_mode == "Firefox":
                        cj = browser_cookie3.firefox(domain_name=domain)
                    elif cookie_mode == "Edge":
                        cj = browser_cookie3.edge(domain_name=domain)
                    elif cookie_mode == "Opera":
                        cj = browser_cookie3.opera(domain_name=domain)
                    elif cookie_mode == "Brave":
                        cj = browser_cookie3.brave(domain_name=domain)
                except Exception as e:
                    raise Exception(f"无法从{cookie_mode}获取Cookie: {str(e)}")
                
                # 将cookies保存为Netscape格式
                with open(cookie_file, 'w', encoding='utf-8') as f:
                    # 写入Netscape格式的头部
                    f.write("# Netscape HTTP Cookie File\n")
                    f.write("# https://curl.haxx.se/rfc/cookie_spec.html\n")
                    f.write("# This is a generated file!  Do not edit.\n\n")
                    
                    # 写入cookies
                    for cookie in cj:
                        # 确保domain不以点开头
                        cookie_domain = cookie.domain.lstrip('.')
                        # 确保path不为空
                        cookie_path = cookie.path if cookie.path else '/'
                        # 转换secure标志
                        secure = 'TRUE' if cookie.secure else 'FALSE'
                        # 处理过期时间
                        expires = str(int(cookie.expires)) if cookie.expires else str(int(time.time() + 3600))
                        
                        # 写入cookie行
                        f.write(f"{cookie_domain}\tTRUE\t{cookie_path}\t{secure}\t{expires}\t{cookie.name}\t{cookie.value}\n")
                
                self.cookie_status.configure(text="Cookie获取成功")
                return {'cookiefile': cookie_file}
                
        except Exception as e:
            error_msg = f"Cookie处理失败: {str(e)}"
            self.logger.error(f"{error_msg}\n{traceback.format_exc()}")
            self.cookie_status.configure(text=error_msg)
            raise Exception(error_msg)

    def fetch_formats(self):
        def fetch():
            url = self.url_entry.get()
            if not url:
                messagebox.showerror("错误", "请输入视频链接")
                return

            try:
                self.logger.info(f"开始获取视频信息: {url}")
                ydl_opts = {
                    'quiet': False,  # 显示详细输出
                    'no_warnings': False,  # 显示警告
                    'verbose': True,  # 添加详细日志
                }

                # 添加cookie选项
                try:
                    cookie_opts = self.get_cookie_options()
                    ydl_opts.update(cookie_opts)
                    self.logger.debug(f"Cookie选项: {cookie_opts}")
                except Exception as e:
                    self.logger.error(f"Cookie错误: {str(e)}\n{traceback.format_exc()}")
                    messagebox.showerror("Cookie错误", str(e))
                    return

                with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                    self.logger.debug("开始提取视频信息")
                    try:
                        info = ydl.extract_info(url, download=False)
                        if not info:
                            raise Exception("无法获取视频信息")
                        self.formats_info = info.get('formats', [])
                        if not self.formats_info:
                            raise Exception("无法获取视频格式")
                        self.logger.debug(f"获取到{len(self.formats_info)}个格式")

                        # 分离视频和音频格式
                        video_formats = []
                        audio_formats = []

                        for f in self.formats_info:
                            if f.get('vcodec') != 'none':
                                has_audio = f.get('acodec') != 'none'
                                format_str = (
                                    f"{f['format_id']} - "
                                    f"{f.get('height', 'N/A')}p "
                                    f"[{self.format_size(f.get('filesize'))}] "
                                    f"{'[带音频]' if has_audio else '[无音频]'}"
                                )
                                video_formats.append(format_str)
                            elif f.get('acodec') != 'none':
                                format_str = (
                                    f"{f['format_id']} - "
                                    f"{f.get('acodec', 'N/A')} "
                                    f"[{self.format_size(f.get('filesize'))}]"
                                )
                                audio_formats.append(format_str)

                        self.video_menu['values'] = video_formats
                        self.audio_menu['values'] = audio_formats

                        if video_formats:
                            self.video_menu.set(video_formats[0])
                            self.on_video_format_change()
                        if audio_formats:
                            self.audio_menu.set(audio_formats[0])

                        self.status_label.configure(text="格式获取成功！")
                    except Exception as e:
                        self.logger.error(f"提取视频信息失败: {str(e)}\n{traceback.format_exc()}")
                        raise Exception(f"提取视频信息失败: {str(e)}")

            except Exception as e:
                error_msg = f"获取视频信息失败: {str(e)}"
                self.logger.error(f"{error_msg}\n{traceback.format_exc()}")
                messagebox.showerror("错误", error_msg)
                self.status_label.configure(text="获取格式失败")

        Thread(target=fetch).start()

    def start_download(self):
        def download():
            url = self.url_entry.get()
            quality = self.quality_var.get()

            if not url:
                messagebox.showerror("错误", "请输入视频链接")
                return

            try:
                ydl_opts = {
                    'progress_hooks': [self.progress_hook],
                    'outtmpl': os.path.join(self.dir_entry.get(), '%(title)s.%(ext)s'),
                    # 添加重试和超时设置
                    'retries': 10,  # 重试次数
                    'fragment_retries': 10,  # 片段下载重试次数
                    'retry_sleep': 5,  # 重试等待时间
                    'socket_timeout': 30,  # Socket超时时间
                    'extractor_retries': 5,  # 提取器重试次数
                    'file_access_retries': 5,  # 文件访问重试次数
                }

                # 添加cookie选项
                try:
                    cookie_opts = self.get_cookie_options()
                    ydl_opts.update(cookie_opts)
                except Exception as e:
                    messagebox.showerror("Cookie错误", str(e))
                    return

                if quality == "custom":
                    video_format = self.video_var.get().split(' - ')[0]
                    has_audio = '[带音频]' in self.video_var.get()
                    if not has_audio:
                        audio_format = self.audio_var.get().split(' - ')[0]
                        ydl_opts['format'] = f'{video_format}+{audio_format}'
                    else:
                        ydl_opts['format'] = video_format
                else:
                    ydl_opts['format'] = quality

                with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                    ydl.download([url])

                self.status_label.configure(text="下载完成！")
                self.progress_bar.set(1.0)
                messagebox.showinfo("成功", "视频下载完成！")

            except Exception as e:
                error_msg = f"下载失败: {str(e)}"
                self.logger.error(f"{error_msg}\n{traceback.format_exc()}")
                messagebox.showerror("错误", error_msg)
                self.status_label.configure(text="下载失败")

        Thread(target=download).start()

    def progress_hook(self, d):
        if d['status'] == 'downloading':
            if 'total_bytes' in d and 'downloaded_bytes' in d and d['total_bytes'] is not None:
                progress = d['downloaded_bytes'] / d['total_bytes']
                self.progress_bar.set(progress)
            if 'speed' in d and d['speed'] is not None:
                speed = d['speed'] / 1024 / 1024
                self.status_label.configure(text=f"下载中... {speed:.1f} MB/s")
            else:
                self.status_label.configure(text="下载中...")

    def __del__(self):
        # 清理临时cookie文件
        if self.cookie_file_path and os.path.exists(self.cookie_file_path):
            try:
                os.remove(self.cookie_file_path)
            except:
                pass

if __name__ == "__main__":
    app = VideoDownloader()
    app.mainloop() 