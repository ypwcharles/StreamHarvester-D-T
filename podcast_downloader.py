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

class DownloadThread(Thread):
    def __init__(self, ydl_opts, urls, queue):
        super().__init__(daemon=True)
        self.ydl_opts = ydl_opts
        self.urls = urls
        self.queue = queue
        self.stop_requested = False

    def run(self):
        try:
            self.ydl_opts['progress_hooks'] = [self.progress_hook]
            with yt_dlp.YoutubeDL(self.ydl_opts) as ydl:
                ydl.download(self.urls)
            if not self.stop_requested:
                self.queue.put({'status': 'task_finished'})
        except Exception as e:
            if "Download cancelled by user" in str(e):
                self.queue.put({'status': 'cancelled'})
            else:
                self.queue.put({'status': 'error', 'error': str(e)})

    def progress_hook(self, d):
        if self.stop_requested:
            raise Exception("Download cancelled by user.")
        self.queue.put({'status': d['status'], 'data': d})

    def stop(self):
        self.stop_requested = True

class PodcastDownloader(ctk.CTkFrame):
    def __init__(self, parent):
        super().__init__(parent)
        self.logger = logging.getLogger(__name__)
        self.stop_requested = False  # 中止下载标志
        self.all_selected_var = ctk.BooleanVar(value=False) # 追踪全选状态
        self.current_file_progress = 0 # 追踪当前文件的下载进度
        self.download_thread = None
        self.download_queue = queue.Queue()
        
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
            
        self.podcast_items = list(self.original_podcast_items) # 复制列表
        
        # 重置全选状态
        self.all_selected_var.set(False)
        self.tree.heading("选择", text="☐")

        total_items = len(self.podcast_items)
        
        # 根据复选框状态决定是否倒序
        if self.reverse_order_var.get():
            self.podcast_items.reverse()
            
        for i, item in enumerate(self.podcast_items):
            track_num = total_items - i if self.reverse_order_var.get() else i + 1
            formatted_date = self.format_date(item.get('upload_date', ''))
            duration = self.format_duration(item.get('duration', 0))
            
            # 插入数据
            item_id = self.tree.insert("", "end", values=(
                "☐", # 默认未选中
                f"{track_num:03d}/{total_items}",
                item['title'],
                duration,
                formatted_date
            ))
            self.item_states[item_id] = False # 初始化状态
            item['item_id'] = item_id # 关联 item 和 item_id

        self.update_header_checkbox_state()
            
    def download_selected(self):
        selected_items_to_download = [
            item for item in self.podcast_items if self.item_states.get(item.get('item_id'))
        ]

        if not selected_items_to_download:
            messagebox.showwarning("无选择", "请先选择要下载的曲目")
            return

        self.stop_requested = False
        self.download_button.configure(state="disabled")
        self.stop_button.configure(state="normal")
        self.progress_bar.set(0)
        self.progress_label.configure(text="0.0%")
        
        download_dir = self.dir_entry.get().strip()
        if not download_dir:
            messagebox.showerror("错误", "下载目录不能为空")
            self.download_button.configure(state="normal")
            self.stop_button.configure(state="disabled")
            return
            
        # The path from the UI is the final destination. Create it if it doesn't exist.
        # This prevents creating a nested folder.
        podcast_dir = download_dir
        os.makedirs(podcast_dir, exist_ok=True)
        
        # 为每个任务创建yt-dlp配置和URL列表
        tasks = []
        for i, item in enumerate(selected_items_to_download):
            # Sanitize filename to prevent invalid characters
            safe_item_title = re.sub(r'[\\/*?:"<>|]', "_", item['title'].strip())
            filename = f"{safe_item_title}.mp3"
            filepath = os.path.join(podcast_dir, filename)
            
            if os.path.exists(filepath):
                self.logger.info(f"文件已存在，跳过: {filename}")
                self.status_label.configure(text=f"已跳过: {filename}")
                continue

            ydl_opts = {
                'outtmpl': filepath,
                'format': 'bestaudio/best',
                'noplaylist': True,
                'quiet': True,
                'no_warnings': True,
                'no_color': True,
                'postprocessors': [{'key': 'FFmpegExtractAudio', 'preferredcodec': 'mp3', 'preferredquality': '192'}],
                'progress_hooks': [], # 将在线程中设置
                # 添加元数据以在钩子中识别
                'progress_template': {'info_dict': {'item_index': i, 'total_files': len(selected_items_to_download)}}
            }
            tasks.append({'opts': ydl_opts, 'url': item['url']})

        # 启动下载线程
        if tasks:
            # Note: This implementation downloads files one by one in a single thread.
            self.tasks = tasks
            self.current_task_index = 0
            self.start_next_download()
        else: # 如果所有文件都已存在
             self.download_finished(status_text="所有选定文件均已存在。")

    def start_next_download(self):
        if self.current_task_index < len(self.tasks):
            task = self.tasks[self.current_task_index]
            self.download_thread = DownloadThread(task['opts'], [task['url']], self.download_queue)
            self.download_thread.start()
            self.process_queue() # 开始处理队列
        else:
            self.download_finished()
            messagebox.showinfo("成功", "所有选定曲目下载完成！")

    def process_queue(self):
        try:
            msg = self.download_queue.get_nowait()
            
            if msg['status'] == 'downloading':
                data = msg['data']
                total_bytes = data.get('total_bytes') or data.get('total_bytes_estimate', 0)
                downloaded_bytes = data.get('downloaded_bytes', 0)
                
                # 从yt-dlp的模板中获取我们自己的元数据
                item_index = self.current_task_index
                total_files = len(self.tasks)

                if total_bytes > 0:
                    current_file_progress = downloaded_bytes / total_bytes
                    overall_progress = (item_index + current_file_progress) / total_files
                    self.progress_bar.set(overall_progress)
                    self.progress_label.configure(text=f"{overall_progress:.1%}")

                # 格式化状态文本
                speed_str = data.get('_speed_str', '...').strip()
                eta_str = data.get('_eta_str', '...').strip()
                filename = data.get('filename', '').split('/')[-1]
                if len(filename) > 35:
                    filename = filename[:32] + '...'

                status_text = f"下载中 ({item_index+1}/{total_files}) | {speed_str} | 预计剩余: {eta_str} | {filename}"
                self.status_label.configure(text=status_text)

            elif msg['status'] == 'task_finished':
                 # 单个文件下载完成，开始下一个
                 self.current_task_index += 1
                 self.start_next_download() # Start the next file
                
            elif msg['status'] == 'cancelled':
                self.download_finished(status_text="下载已中止")
                
            elif msg['status'] == 'error':
                self.download_finished(status_text="下载失败")
                self.logger.error(f"下载线程出错: {msg['error']}")
                messagebox.showerror("错误", f"下载失败: {msg['error']}")
                
        except queue.Empty:
            pass # 队列为空，什么都不做
        finally:
            # 只要线程还在运行，就继续检查
            if self.download_thread and self.download_thread.is_alive():
                self.after(100, self.process_queue)

    def download_finished(self, status_text=""):
        if not status_text:
            self.progress_bar.set(1)
            self.progress_label.configure(text="100.0%")
            self.status_label.configure(text="所有选定曲目下载完成！")
        else:
            self.status_label.configure(text=status_text)
            
        self.download_button.configure(state="normal")
        self.stop_button.configure(state="disabled", text="中止下载")
        self.download_thread = None

    def stop_download(self):
        """中止下载过程"""
        if self.download_thread and self.download_thread.is_alive():
            self.download_thread.stop()
            self.stop_button.configure(state="disabled", text="正在中止...")

    def select_all(self):
        """选中所有曲目并更新UI"""
        for item_id in self.tree.get_children():
            if not self.item_states.get(item_id, False):
                self.item_states[item_id] = True
                self.update_row_checkbox(item_id)
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