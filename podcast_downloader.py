import customtkinter as ctk
import tkinter as tk
from tkinter import messagebox, ttk, filedialog
import yt_dlp
import os
import json
import requests
from bs4 import BeautifulSoup
import logging
from threading import Thread
import re
import xml.etree.ElementTree as ET
from datetime import datetime
import time
import traceback
import queue
from concurrent.futures import ThreadPoolExecutor

class PodcastDownloader(ctk.CTkFrame):
    def __init__(self, parent):
        super().__init__(parent)
        self.logger = logging.getLogger(__name__)
        self.stop_requested = False  # 中止下载标志
        self.all_selected_var = ctk.BooleanVar(value=False) # 追踪全选状态
        self.current_file_progress = 0 # 追踪当前文件的下载进度
        self.download_thread = None
        self.download_queue = queue.Queue()
        self.download_pool = ThreadPoolExecutor(max_workers=5) # 限制5个并发
        self.active_downloads = {} # 追踪活跃的下载任务
        self.total_downloads = 0
        self.completed_downloads = 0
        self.file_progress = {} # url -> {percent: float, downloaded_bytes: int, speed: float}
        self.errors_occurred = False
        
        # 配置网格
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(1, weight=1)
        
        # 创建主框架
        self.main_frame = ctk.CTkFrame(self)
        self.main_frame.grid(row=0, column=0, padx=20, pady=20, sticky="nsew")
        self.main_frame.grid_columnconfigure(0, weight=1)
        
        # URL输入框
        self.url_label = ctk.CTkLabel(self.main_frame, text="播客链接:")
        self.url_label.grid(row=0, column=0, padx=10, pady=(10, 5), sticky="w")
        
        self.url_entry = ctk.CTkEntry(self.main_frame, width=400)
        self.url_entry.grid(row=1, column=0, padx=10, pady=(0, 10), sticky="ew")
        
        # 设置默认下载目录
        self.default_download_dir = os.path.expanduser("~/Downloads/Podcasts").strip()
        
        # 下载目录选择
        self.dir_frame = ctk.CTkFrame(self.main_frame)
        self.dir_frame.grid(row=2, column=0, padx=10, pady=5, sticky="ew")
        
        self.dir_label = ctk.CTkLabel(self.dir_frame, text="下载目录:")
        self.dir_label.grid(row=0, column=0, padx=5, pady=5)
        
        self.dir_entry = ctk.CTkEntry(self.dir_frame, width=300)
        self.dir_entry.grid(row=0, column=1, padx=5, pady=5, sticky="ew")
        self.dir_entry.insert(0, self.default_download_dir)
        
        self.dir_button = ctk.CTkButton(self.dir_frame, text="选择目录", command=self.choose_directory)
        self.dir_button.grid(row=0, column=2, padx=5, pady=5)
        
        self.dir_frame.grid_columnconfigure(1, weight=1)
        
        # 选项框架
        self.options_frame = ctk.CTkFrame(self.main_frame)
        self.options_frame.grid(row=3, column=0, padx=10, pady=5, sticky="ew")
        
        # 倒序选项
        self.reverse_order_var = ctk.BooleanVar(value=False)
        self.reverse_order_checkbox = ctk.CTkCheckBox(self.options_frame, text="曲目序号倒序", 
                                                     variable=self.reverse_order_var,
                                                     command=self.refresh_track_numbers)
        self.reverse_order_checkbox.grid(row=0, column=0, padx=5, pady=5, sticky="w")
        
        # 播客列表框架
        self.list_frame = ctk.CTkFrame(self)
        self.list_frame.grid(row=1, column=0, padx=20, pady=10, sticky="nsew")
        self.list_frame.grid_columnconfigure(0, weight=1)
        self.list_frame.grid_rowconfigure(0, weight=1)
        
        # 创建表格
        self.tree = ttk.Treeview(self.list_frame, columns=("选择", "曲目号", "标题", "时长", "发布日期"), show="headings")

        # --- 使用原生 Treeview Header Command ---
        style = ttk.Style()
        style.configure("THeading", background="#2b2b2b", foreground="white", relief="flat", 
                        padding=[0, 5, 0, 5], font=('TkDefaultFont', 16, 'bold'))
        style.map("THeading", background=[("active", "#2b2b2b")])

        self.tree.heading("选择", text="☐", anchor="center", command=self.toggle_all_selection)
        self.tree.heading("曲目号", text="曲目号")
        self.tree.heading("标题", text="标题")
        self.tree.heading("时长", text="时长")
        self.tree.heading("发布日期", text="发布日期")
        
        # 设置列宽
        self.tree.column("选择", width=50, anchor="center", stretch=tk.NO) # 固定复选框列宽
        self.tree.column("曲目号", width=80, anchor="center")
        self.tree.column("标题", width=300)
        self.tree.column("时长", width=80, anchor="center")
        self.tree.column("发布日期", width=100, anchor="center")
        
        self.tree.grid(row=0, column=0, sticky="nsew")

        # 绑定点击事件，用于切换复选框状态
        self.tree.bind("<Button-1>", self.on_tree_click)
        
        # 添加滚动条
        scrollbar = ttk.Scrollbar(self.list_frame, orient="vertical", command=self.tree.yview)
        scrollbar.grid(row=0, column=1, sticky="ns")
        self.tree.configure(yscrollcommand=scrollbar.set)
        
        # 按钮框架
        self.button_frame = ctk.CTkFrame(self)
        self.button_frame.grid(row=2, column=0, padx=20, pady=10, sticky="ew")
        
        # 获取列表按钮
        self.fetch_button = ctk.CTkButton(self.button_frame, text="获取播客列表", command=self.fetch_podcast_list)
        self.fetch_button.grid(row=0, column=0, padx=5, pady=5)
        
        # 下载选中按钮
        self.download_button = ctk.CTkButton(self.button_frame, text="下载选中", command=self.download_selected)
        self.download_button.grid(row=0, column=1, padx=5, pady=5)
        
        # 中止下载按钮
        self.stop_button = ctk.CTkButton(self.button_frame, text="中止下载", command=self.stop_download, state="disabled")
        self.stop_button.grid(row=0, column=2, padx=5, pady=5)
        
        # --- 进度条和百分比标签框架 ---
        self.progress_frame = ctk.CTkFrame(self)
        self.progress_frame.grid(row=3, column=0, padx=20, pady=10, sticky="ew")
        self.progress_frame.grid_columnconfigure(0, weight=1)

        self.progress_bar = ctk.CTkProgressBar(self.progress_frame)
        self.progress_bar.grid(row=0, column=0, padx=(0, 10), pady=5, sticky="ew")
        self.progress_bar.set(0)
        
        self.progress_label = ctk.CTkLabel(self.progress_frame, text="0.0%", width=40)
        self.progress_label.grid(row=0, column=1, padx=(0, 5), pady=5, sticky="e")
        
        # 状态标签
        self.status_label = ctk.CTkLabel(self, text="")
        self.status_label.grid(row=4, column=0, padx=20, pady=10)
        
        self.podcast_items = []
        self.original_podcast_items = []  # 存储原始顺序的播客项目
        self.podcast_title = ""
        self.item_states = {} # 存储每个项目的选中状态
        self.download_futures = [] # 存储 future 对象以便中止
        
    def on_tree_click(self, event):
        """处理 Treeview 上的点击事件以切换复选框状态"""
        region = self.tree.identify_region(event.x, event.y)
        if region == "cell":
            column_id = self.tree.identify_column(event.x)
            item_id = self.tree.identify_row(event.y)
            
            if item_id and column_id == "#1": # "#1" 是第一列 "选择"
                # 切换状态
                self.item_states[item_id] = not self.item_states.get(item_id, False)
                self.update_row_checkbox(item_id)
                self.update_header_checkbox_state()

    def update_row_checkbox(self, item_id):
        """更新指定行的复选框外观"""
        is_checked = self.item_states.get(item_id, False)
        checkbox_char = "☑" if is_checked else "☐"
        self.tree.set(item_id, "选择", checkbox_char)

    def toggle_all_selection(self):
        """响应表头点击事件，切换选择状态"""
        new_state = not self.all_selected_var.get()
        if new_state:
            self.select_all()
        else:
            self.deselect_all()
            
    def update_header_checkbox_state(self):
        """根据行选中状态更新表头复选框"""
        all_items_selected = True
        has_items = False
        for item_id in self.tree.get_children():
            has_items = True
            if not self.item_states.get(item_id, False):
                all_items_selected = False
                break
        
        # 如果逻辑状态与UI不符，则更新UI
        if has_items and all_items_selected:
            if not self.all_selected_var.get():
                self.all_selected_var.set(True)
                self.tree.heading("选择", text="☑")
        else:
            if self.all_selected_var.get():
                self.all_selected_var.set(False)
                self.tree.heading("选择", text="☐")

    def choose_directory(self):
        dir_path = filedialog.askdirectory(initialdir=self.dir_entry.get().strip())
        if dir_path:
            # 确保路径有效
            dir_path = dir_path.strip()
            self.dir_entry.delete(0, tk.END)
            self.dir_entry.insert(0, dir_path)
            
    def format_duration(self, duration):
        try:
            if isinstance(duration, str):
                # 尝试将字符串转换为秒数
                if ':' in duration:
                    parts = duration.split(':')
                    if len(parts) == 2:
                        minutes, seconds = parts
                        duration = int(minutes) * 60 + int(seconds)
                    elif len(parts) == 3:
                        hours, minutes, seconds = parts
                        duration = int(hours) * 3600 + int(minutes) * 60 + int(seconds)
                else:
                    duration = float(duration)
            
            # 确保duration是数字
            duration = float(duration)
            minutes = int(duration // 60)
            seconds = int(duration % 60)
            return f"{minutes:02d}:{seconds:02d}"
        except:
            return "00:00"

    def parse_rss_feed(self, feed_url):
        try:
            response = requests.get(feed_url)
            response.raise_for_status()
            
            # 解析RSS内容
            items = []
            soup = BeautifulSoup(response.content, 'xml')
            
            # 获取播客标题（唱片集名称）
            channel = soup.find('channel')
            self.podcast_title = channel.title.text if channel and channel.title else "未知播客"
            
            for item in soup.find_all('item'):
                title = item.title.text if item.title else "未知标题"
                pub_date = item.pubDate.text if item.pubDate else ""
                duration = item.duration.text if item.duration else "0"
                enclosure = item.enclosure
                
                if enclosure and enclosure.get('url'):
                    url = enclosure['url']
                    items.append({
                        'title': title,
                        'url': url,
                        'duration': duration,
                        'upload_date': pub_date
                    })
            
            return items
            
        except Exception as e:
            raise Exception(f"解析RSS feed失败: {str(e)}")
            
    def get_rss_feed(self, apple_url):
        try:
            # 从 Apple Podcast URL 中提取播客 ID
            match = re.search(r'/id(\d+)', apple_url)
            if not match:
                raise Exception("无法从链接中提取播客ID")
            podcast_id = match.group(1)
            
            # 构建 RSS feed URL
            lookup_url = f"https://itunes.apple.com/lookup?id={podcast_id}&entity=podcast"
            
            # 获取播客信息
            response = requests.get(lookup_url)
            response.raise_for_status()
            data = response.json()
            
            if not data.get('results'):
                raise Exception("未找到播客信息")
                
            # 获取播客 RSS feed URL
            feed_url = data['results'][0].get('feedUrl')
            if not feed_url:
                raise Exception("未找到 RSS feed URL")
                
            return feed_url
            
        except Exception as e:
            raise Exception(f"获取 RSS feed 失败: {str(e)}")
            
    def format_date(self, date_str):
        try:
            # 尝试解析多种日期格式
            for fmt in ['%a, %d %b %Y %H:%M:%S %z', '%Y-%m-%d', '%Y%m%d']:
                try:
                    dt = datetime.strptime(date_str, fmt)
                    return dt.strftime('%Y-%m-%d')
                except ValueError:
                    continue
            return date_str[:10]  # 如果无法解析，返回前10个字符
        except:
            return ""

    def _find_key(self, obj, key):
        """递归搜索字典或列表中的指定键"""
        if isinstance(obj, dict):
            if key in obj:
                yield obj[key]
            for v in obj.values():
                yield from self._find_key(v, key)
        elif isinstance(obj, list):
            for item in obj:
                yield from self._find_key(item, key)

    def parse_xiaoyuzhou_episode(self, episode_url):
        """解析小宇宙单集页面"""
        try:
            resp = requests.get(
                episode_url,
                headers={"User-Agent": "Mozilla/5.0"},
                timeout=15,
            )
            resp.raise_for_status()

            soup = BeautifulSoup(resp.text, "html.parser")
            script = soup.find("script", id="__NEXT_DATA__")
            if not script or not script.string:
                raise Exception("未找到页面数据")

            data = json.loads(script.string)

            # 从 __NEXT_DATA__ 中递归查找所需字段
            audio_url = next(self._find_key(data, "audioUrl"), None)
            if not audio_url:
                audio_url = next(self._find_key(data, "url"), None)
            title = next(self._find_key(data, "title"), "未知标题")
            duration = next(self._find_key(data, "duration"), 0)
            publish_date = next(
                self._find_key(data, "publishedAt"),
                next(self._find_key(data, "publishDate"), ""),
            )

            podcast_title = next(self._find_key(data, "podcastTitle"), None)
            if not podcast_title:
                podcast_title = next(self._find_key(data, "podcast"), {}).get(
                    "title", "小宇宙播客"
                )
            self.podcast_title = podcast_title or "小宇宙播客"

            if not audio_url:
                raise Exception("未找到音频链接")

            return [
                {
                    "title": title,
                    "url": audio_url,
                    "duration": duration,
                    "upload_date": publish_date,
                }
            ]
        except Exception as e:
            raise Exception(f"解析小宇宙页面失败: {str(e)}")

    def parse_xiaoyuzhou_podcast(self, podcast_url):
        """解析小宇宙播客主页，尝试获取所有单集"""
        try:
            resp = requests.get(
                podcast_url,
                headers={"User-Agent": "Mozilla/5.0"},
                timeout=15,
            )
            resp.raise_for_status()

            soup = BeautifulSoup(resp.text, "html.parser")
            script = soup.find("script", id="__NEXT_DATA__")
            if not script or not script.string:
                raise Exception("未找到页面数据")

            data = json.loads(script.string)
            episodes = None
            for item in self._find_key(data, "episodes"):
                if isinstance(item, list):
                    episodes = item
                    break

            if episodes is None:
                # 如果未找到列表，则尝试将整个页面作为单集解析
                return self.parse_xiaoyuzhou_episode(podcast_url)

            podcast_title = next(self._find_key(data, "title"), "小宇宙播客")
            self.podcast_title = podcast_title

            items = []
            for ep in episodes:
                audio_url = None
                if isinstance(ep, dict):
                    audio_url = ep.get("audioUrl") or (
                        ep.get("audio", {}).get("url") if isinstance(ep.get("audio"), dict) else None
                    )
                    title = ep.get("title", "未知标题")
                    duration = ep.get("duration", 0)
                    upload_date = (
                        ep.get("publishedAt")
                        or ep.get("publishDate")
                        or ep.get("date")
                        or ""
                    )
                else:
                    continue

                if audio_url:
                    items.append(
                        {
                            "title": title,
                            "url": audio_url,
                            "duration": duration,
                            "upload_date": upload_date,
                        }
                    )

            if not items:
                raise Exception("未找到播客列表")

            return items
        except Exception as e:
            raise Exception(f"解析小宇宙播客失败: {str(e)}")
            
    def fetch_podcast_list(self):
        def fetch():
            url = self.url_entry.get()
            if not url:
                messagebox.showerror("错误", "请输入播客链接")
                return

            try:
                self.status_label.configure(text="正在获取播客列表...")
                
                # 清空旧数据
                for i in self.tree.get_children():
                    self.tree.delete(i)
                self.podcast_items = []
                self.original_podcast_items = []
                self.item_states = {}

                items = []
                # ... (处理不同播客源的逻辑) ...
                if "podcasts.apple.com" in url:
                    feed_url = self.get_rss_feed(url)
                    self.logger.info(f"获取到 RSS feed URL: {feed_url}")
                    items = self.parse_rss_feed(feed_url)
                elif "xiaoyuzhoufm.com/podcast/" in url:
                    items = self.parse_xiaoyuzhou_podcast(url)
                elif "xiaoyuzhoufm.com/episode/" in url:
                    items = self.parse_xiaoyuzhou_episode(url)
                else:
                    try:
                        self.logger.info(f"尝试将链接作为通用 RSS feed 解析: {url}")
                        items = self.parse_rss_feed(url)
                    except Exception as rss_error:
                        self.logger.error(f"无法将链接作为通用 RSS feed 解析: {rss_error}")
                        raise Exception("不支持的播客链接，目前支持 Apple Podcast、小宇宙或有效的 RSS feed")

                # 根据播客标题设置下载子目录
                if self.podcast_title:
                    safe_title = re.sub(r'[\\/*?:"<>|]', "_", self.podcast_title.strip())
                    new_dir = os.path.join(self.default_download_dir, safe_title)
                    self.dir_entry.delete(0, tk.END)
                    self.dir_entry.insert(0, new_dir)
                
                self.original_podcast_items = items
                self.refresh_podcast_list()
                
                self.status_label.configure(text=f"成功获取 {len(items)} 个曲目")

            except Exception as e:
                self.logger.error(f"获取播客列表失败: {str(e)}\n{traceback.format_exc()}")
                messagebox.showerror("错误", f"获取播客列表失败: {str(e)}")
                self.status_label.configure(text="获取失败")
        
        Thread(target=fetch, daemon=True).start()
        
    def refresh_podcast_list(self):
        # 清空 treeview
        for i in self.tree.get_children():
            self.tree.delete(i)
        
        # 根据倒序选项决定使用哪个列表
        podcast_items_to_display = list(self.original_podcast_items)
        if self.reverse_order_var.get():
            podcast_items_to_display.reverse()

        self.podcast_items = podcast_items_to_display # 更新当前显示的列表
        
        for i, item in enumerate(self.podcast_items):
            track_num = i + 1
            
            # 确保每个item都有唯一的ID
            item_id = self.tree.insert("", "end", values=(
                "☐",
                track_num, 
                item.get('title', 'N/A'), 
                self.format_duration(item.get('duration', 0)), 
                self.format_date(item.get('pubDate', ''))
            ))
            item['id'] = item_id # 将 treeview 的 item id 存入字典
            
            # 初始化或恢复该项目的选中状态
            self.item_states[item_id] = self.item_states.get(item_id, False)
            self.update_row_checkbox(item_id)
            
        self.update_header_checkbox_state()

        # 如果之前是全选状态，则取消它，因为列表已刷新
        self.tree.heading("选择", text="☐")
        self.all_selected_var.set(False)
        
    def download_selected(self):
        selected_ids = [item_id for item_id, selected in self.item_states.items() if selected]
        if not selected_ids:
            messagebox.showinfo("提示", "请选择要下载的播客。")
            return

        self.stop_requested = False
        self.download_button.configure(state="disabled")
        self.stop_button.configure(state="normal")
        self.fetch_button.configure(state="disabled")
        self.progress_bar.set(0)
        self.progress_label.configure(text="0.0%")
        
        # 重置状态
        self.total_downloads = len(selected_ids)
        self.completed_downloads = 0
        self.active_downloads.clear()
        self.download_futures.clear()
        self.file_progress.clear()
        self.errors_occurred = False
        
        # 下载立即开始，进度条直接进入确定模式
        self.progress_bar.configure(mode="determinate")

        dir_path = self.dir_entry.get().strip()
        if not os.path.exists(dir_path):
            os.makedirs(dir_path)

        items_to_download = []
        for item_id in selected_ids:
            item = next((p for p in self.podcast_items if p.get('id') == item_id), None)
            if item:
                items_to_download.append(item)
        
        if len(items_to_download) != self.total_downloads:
            self.logger.warning("部分选中的项目无法找到，可能已被刷新。")
            self.total_downloads = len(items_to_download)

        for item in items_to_download:
            item_title = item.get('title', 'Unknown Title')
            url = item.get('url')

            if not url:
                self.logger.error(f"播客 '{item_title}' 的 URL 无效。")
                self.total_downloads -= 1
                continue

            ydl_opts = {
                'format': 'bestaudio/best',
                'outtmpl': os.path.join(dir_path, f'{self.podcast_title} - {item_title}.%(ext)s'),
                'quiet': True,
                'no_warnings': True,
                'logger': self.logger,
                'progress_hooks': [self.progress_hook],
            }

            future = self.download_pool.submit(self._download_task_worker, ydl_opts, url)
            self.download_futures.append(future)

        self.status_label.configure(text=f"已将 {self.total_downloads} 个任务加入下载队列...")
        self.process_queue()

    def _download_task_worker(self, ydl_opts, url):
        """
        这个方法由线程池的单个工作线程执行，负责一个文件的完整下载过程。
        """
        try:
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                ydl.download([url])
        except Exception as e:
            # 捕获 yt_dlp 本身的异常，包括用户中止的异常
            # progress_hook 会处理具体的状态，这里只捕获意外错误
            if "Download cancelled by user" not in str(e):
                 self.download_queue.put({'status': 'error', 'error': str(e), 'url': url})

    def progress_hook(self, d):
        if self.stop_requested:
            raise yt_dlp.utils.DownloadError("Download cancelled by user.")

        # 从回调信息中获取最可靠的原始URL
        url = d.get('info_dict', {}).get('original_url') or d.get('info_dict', {}).get('webpage_url')
        if not url: # 如果在某些情况下无法获取，则不发送消息
            self.logger.warning(f"无法从progress_hook确定URL。状态: {d['status']}")
            return

        message = {
            'status': d['status'],
            'data': d,
            'url': url
        }
        self.download_queue.put(message)

    def process_queue(self):
        try:
            while not self.download_queue.empty():
                msg = self.download_queue.get_nowait()
                status = msg.get('status')
                url = msg.get('url')
                data = msg.get('data', {})

                if url not in self.file_progress:
                    self.file_progress[url] = {'percent': 0, 'downloaded_bytes': 0, 'speed': 0}

                if status == 'downloading':
                    downloaded_bytes = data.get('downloaded_bytes', 0)
                    total_bytes = data.get('total_bytes') or data.get('total_bytes_estimate', 0)
                    speed = data.get('speed') or 0

                    self.file_progress[url]['downloaded_bytes'] = downloaded_bytes
                    self.file_progress[url]['speed'] = speed
                    if total_bytes > 0:
                        percent = (downloaded_bytes / total_bytes) * 100
                        self.file_progress[url]['percent'] = percent

                elif status == 'finished':
                    self.completed_downloads += 1
                    self.file_progress[url]['percent'] = 100
                    self.file_progress[url]['speed'] = 0
                
                elif status == 'error':
                    self.errors_occurred = True
                    self.completed_downloads += 1
                    self.file_progress[url]['percent'] = 100 # 将失败的任务视为"完成"以推进总进度
                    self.logger.error(f"下载失败: {msg.get('error')}")

            # --- 虚拟总进度计算 ---
            if self.total_downloads > 0:
                # 如果有任何详细的进度数据，则使用虚拟百分比方法
                if self.file_progress:
                    total_percent = sum(item['percent'] for item in self.file_progress.values())
                    overall_progress = total_percent / self.total_downloads
                    
                    total_downloaded_mb = sum(item['downloaded_bytes'] for item in self.file_progress.values()) / 1024 / 1024
                    total_speed_mbps = sum(item['speed'] for item in self.file_progress.values()) / 1024 / 1024

                    self.progress_bar.set(overall_progress / 100)
                    self.progress_label.configure(text=f"{overall_progress:.1f}%")
                    
                    speed_text = f"{total_speed_mbps:.2f} MB/s" if total_speed_mbps > 0 else "..."
                    status_text = f"已下载: {total_downloaded_mb:.2f} MB | 速度: {speed_text}"
                    self.status_label.configure(text=status_text)
                # 否则，回退到按完成数量显示进度
                else:
                    self.update_progress_by_count()


            if self.completed_downloads == self.total_downloads and self.total_downloads > 0:
                 self.download_finished()
                 return

        except queue.Empty:
            pass
        
        if not self.stop_requested:
            self.after(100, self.process_queue)

    def update_progress_by_count(self):
        """按文件完成数量更新进度（作为备用）"""
        if self.total_downloads > 0:
            progress = (self.completed_downloads / self.total_downloads) * 100
            self.progress_bar.set(progress / 100)
            self.progress_label.configure(text=f"{progress:.1f}%")
            self.status_label.configure(text="下载中...")
            
    def download_finished(self, status_text="所有任务已完成。"):
        self.progress_bar.stop()
        self.progress_bar.configure(mode="determinate")
        self.download_button.configure(state="normal")
        self.stop_button.configure(state="disabled")
        self.fetch_button.configure(state="normal")
        
        # 优先显示错误信息
        if self.errors_occurred:
            status_text = "下载完成，但有错误发生。"
        
        if status_text:
            self.status_label.configure(text=status_text)
        
        self.total_downloads = 0
        self.completed_downloads = 0
        self.active_downloads.clear()
        self.download_futures.clear()

    def stop_download(self):
        self.stop_requested = True
        
        # 尝试取消线程池中未开始的任务
        for future in self.download_futures:
            future.cancel()

        # 停止正在运行的线程
        for thread in self.active_downloads.values():
            thread.stop()
            
        # 清空队列
        while not self.download_queue.empty():
            try:
                self.download_queue.get_nowait()
            except queue.Empty:
                break
                
        self.download_pool.shutdown(wait=False, cancel_futures=True) # 立即关闭
        self.download_pool = ThreadPoolExecutor(max_workers=5) # 重建线程池

        self.download_finished("下载已中止。")

    def select_all(self):
        self.all_selected_var.set(True)
        self.tree.heading("选择", text="☑")

    def deselect_all(self):
        """取消选中所有曲目并更新UI"""
        for item_id in self.tree.get_children():
            if self.item_states.get(item_id, False):
                self.item_states[item_id] = False
                self.update_row_checkbox(item_id)
        self.all_selected_var.set(False)
        self.tree.heading("选择", text="☐")

    def refresh_track_numbers(self):
        """当"倒序"复选框状态改变时，刷新列表"""
        self.refresh_podcast_list()
        
    def _is_url(self, text):
        return re.match(r'https?://', text) is not None