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

class PodcastDownloader(ctk.CTkFrame):
    def __init__(self, parent):
        super().__init__(parent)
        self.logger = logging.getLogger(__name__)
        
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
        self.tree = ttk.Treeview(self.list_frame, columns=("曲目号", "标题", "时长", "发布日期"), show="headings")
        self.tree.heading("曲目号", text="曲目号")
        self.tree.heading("标题", text="标题")
        self.tree.heading("时长", text="时长")
        self.tree.heading("发布日期", text="发布日期")
        
        # 设置列宽
        self.tree.column("曲目号", width=80, anchor="center")
        self.tree.column("标题", width=300)
        self.tree.column("时长", width=80, anchor="center")
        self.tree.column("发布日期", width=100, anchor="center")
        
        self.tree.grid(row=0, column=0, sticky="nsew")
        
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
        
        # 全选按钮
        self.select_all_button = ctk.CTkButton(self.button_frame, text="全选", command=self.select_all)
        self.select_all_button.grid(row=0, column=2, padx=5, pady=5)
        
        # 取消全选按钮
        self.deselect_all_button = ctk.CTkButton(self.button_frame, text="取消全选", command=self.deselect_all)
        self.deselect_all_button.grid(row=0, column=3, padx=5, pady=5)
        
        # 进度条
        self.progress_bar = ctk.CTkProgressBar(self)
        self.progress_bar.grid(row=3, column=0, padx=20, pady=10, sticky="ew")
        self.progress_bar.set(0)
        
        # 状态标签
        self.status_label = ctk.CTkLabel(self, text="")
        self.status_label.grid(row=4, column=0, padx=20, pady=10)
        
        self.podcast_items = []
        self.original_podcast_items = []  # 存储原始顺序的播客项目
        self.podcast_title = ""
        
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
            url = self.url_entry.get().strip()
            if not url:
                messagebox.showerror("错误", "请输入播客链接")
                return
                
            try:
                # 重置下载目录为默认值
                self.dir_entry.delete(0, tk.END)
                self.dir_entry.insert(0, self.default_download_dir)
                
                self.status_label.configure(text="正在获取播客列表...")
                self.fetch_button.configure(state="disabled")
                
                # Apple Podcast 链接
                if 'podcasts.apple.com' in url:
                    feed_url = self.get_rss_feed(url)
                    self.logger.info(f"获取到 RSS feed URL: {feed_url}")
                    podcast_items = self.parse_rss_feed(feed_url)

                    if self.podcast_title:
                        safe_title = (
                            self.podcast_title.replace('/', '_')
                            .replace('\\', '_')
                            .replace(':', '_')
                            .replace('*', '_')
                            .replace('?', '_')
                            .replace('"', '_')
                            .replace('<', '_')
                            .replace('>', '_')
                            .replace('|', '_')
                        )
                        new_dir = os.path.join(self.default_download_dir, safe_title)
                        self.dir_entry.delete(0, tk.END)
                        self.dir_entry.insert(0, new_dir)

                # 小宇宙 FM 链接
                elif 'xiaoyuzhoufm.com' in url:
                    if '/episode/' in url:
                        podcast_items = self.parse_xiaoyuzhou_episode(url)
                    else:
                        podcast_items = self.parse_xiaoyuzhou_podcast(url)

                    if self.podcast_title:
                        safe_title = (
                            self.podcast_title.replace('/', '_')
                            .replace('\\', '_')
                            .replace(':', '_')
                            .replace('*', '_')
                            .replace('?', '_')
                            .replace('"', '_')
                            .replace('<', '_')
                            .replace('>', '_')
                            .replace('|', '_')
                        )
                        new_dir = os.path.join(self.default_download_dir, safe_title)
                        self.dir_entry.delete(0, tk.END)
                        self.dir_entry.insert(0, new_dir)

                else:
                    raise Exception("目前仅支持 Apple Podcast 或 小宇宙FM 链接")
                
                # 清空现有列表
                for item in self.tree.get_children():
                    self.tree.delete(item)
                self.podcast_items = []
                
                # 存储原始播客项目（未排序）
                self.original_podcast_items = []
                for item in podcast_items:
                    title = item['title']
                    duration_str = self.format_duration(item['duration'])
                    upload_date = self.format_date(item['upload_date'])
                    
                    self.original_podcast_items.append({
                        'title': title,
                        'url': item['url'],
                        'duration': duration_str,
                        'upload_date': upload_date
                    })
                
                # 根据当前复选框状态决定是否倒序
                self.refresh_track_numbers()
                
            except Exception as e:
                error_msg = f"获取播客列表失败: {str(e)}"
                self.logger.error(error_msg)
                messagebox.showerror("错误", error_msg)
                self.status_label.configure(text="获取列表失败")
                
            finally:
                self.fetch_button.configure(state="normal")
                
        Thread(target=fetch, daemon=True).start()
        
    def download_selected(self):
        def download():
            selected_items = self.tree.selection()
            if not selected_items:
                messagebox.showwarning("警告", "请选择要下载的播客")
                return
                
            try:
                self.download_button.configure(state="disabled")
                total_selected = len(selected_items)
                completed = 0
                failed = 0
                
                # 确保下载目录存在，并清理路径中的空白字符和换行符
                download_dir = self.dir_entry.get().strip()
                
                # 检查路径是否有效
                if not download_dir or '\n' in download_dir:
                    self.logger.error(f"无效的下载路径: {download_dir}")
                    messagebox.showerror("错误", "下载路径无效，请重新选择下载目录")
                    self.download_button.configure(state="normal")
                    return
                
                os.makedirs(download_dir, exist_ok=True)
                
                # 计算曲目号需要的位数，使用整个播客列表的长度
                total_episodes = len(self.podcast_items)
                digits = len(str(total_episodes))
                
                for item in selected_items:
                    index = self.tree.index(item)
                    podcast = self.podcast_items[index]
                    
                    # 直接使用显示的曲目号的第一部分（不包含"/"）作为文件名的曲目号
                    display_track_number = podcast['track_number']
                    file_track_number = display_track_number.split('/')[0]
                    
                    # 格式化文件名为"曲目号.曲目标题"
                    formatted_title = f"{file_track_number}.{podcast['title']}"
                    
                    self.status_label.configure(text=f"正在下载: {formatted_title}")
                    
                    # 配置yt-dlp选项，增加重试次数和超时时间
                    ydl_opts = {
                        'outtmpl': os.path.join(download_dir, formatted_title + '.%(ext)s'),
                        'quiet': True,
                        'retries': 10,                      # 增加重试次数
                        'fragment_retries': 10,             # 增加片段重试次数
                        'skip_unavailable_fragments': True, # 跳过不可用片段
                        'socket_timeout': 60,               # 增加套接字超时时间
                        'extractor_retries': 5,             # 增加提取器重试次数
                    }
                    
                    # 尝试下载，最多重试3次
                    max_attempts = 3
                    for attempt in range(max_attempts):
                        try:
                            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                                ydl.download([podcast['url']])
                            break  # 下载成功，跳出重试循环
                        except Exception as e:
                            self.logger.warning(f"下载尝试 {attempt+1}/{max_attempts} 失败: {str(e)}")
                            if attempt == max_attempts - 1:  # 最后一次尝试
                                self.logger.error(f"下载失败: {str(e)}")
                                failed += 1
                                messagebox.showwarning("警告", f"无法下载 '{formatted_title}': {str(e)}\n将继续下载其他文件。")
                            else:
                                # 等待一段时间后重试
                                self.status_label.configure(text=f"重试下载 {formatted_title}... ({attempt+2}/{max_attempts})")
                                time.sleep(3)  # 等待3秒后重试
                    
                    completed += 1
                    progress = completed / total_selected
                    self.progress_bar.set(progress)
                    
                if failed > 0:
                    self.status_label.configure(text=f"下载完成，但有 {failed} 个文件失败")
                    messagebox.showinfo("部分成功", f"成功下载 {completed - failed} 个播客，{failed} 个失败")
                else:
                    self.status_label.configure(text="下载完成！")
                    messagebox.showinfo("成功", f"成功下载 {completed} 个播客")
                
            except Exception as e:
                error_msg = f"下载失败: {str(e)}"
                self.logger.error(error_msg)
                messagebox.showerror("错误", error_msg)
                self.status_label.configure(text="下载失败")
                
            finally:
                self.download_button.configure(state="normal")
                
        Thread(target=download, daemon=True).start()
        
    def select_all(self):
        for item in self.tree.get_children():
            self.tree.selection_add(item)
            
    def deselect_all(self):
        for item in self.tree.get_children():
            self.tree.selection_remove(item)
            
    def refresh_track_numbers(self):
        """根据当前倒序选项刷新列表中的曲目号"""
        if not self.original_podcast_items:
            return  # 如果没有原始播客项目，不执行任何操作
            
        # 保存当前选中的项目
        selected_indices = [self.tree.index(item) for item in self.tree.selection()]
            
        # 清空现有列表
        for item in self.tree.get_children():
            self.tree.delete(item)
        self.podcast_items = []
        
        # 根据当前复选框状态决定是否倒序
        reverse_order = self.reverse_order_var.get()
        
        # 创建新的排序列表（基于原始顺序）
        sorted_items = list(self.original_podcast_items)
        if reverse_order:
            sorted_items.reverse()
            
        # 重新添加播客条目
        total_episodes = len(sorted_items)
        digits = len(str(total_episodes))  # 计算需要的位数
        total_str = str(total_episodes).zfill(digits)  # 格式化总数
        
        for index, item in enumerate(sorted_items):
            title = item['title']
            duration_str = item['duration']
            upload_date = item['upload_date']
            # 使用零填充格式化曲目号
            track_number = f"{str(index + 1).zfill(digits)}/{total_str}"
            
            self.podcast_items.append({
                'title': title,
                'url': item['url'],
                'duration': duration_str,
                'upload_date': upload_date,
                'track_number': track_number
            })
            
            self.tree.insert("", "end", values=(track_number, title, duration_str, upload_date))
        
        # 恢复选中状态
        for idx in selected_indices:
            if idx < len(self.tree.get_children()):  # 确保索引有效
                self.tree.selection_add(self.tree.get_children()[idx])
            
        self.status_label.configure(text=f"曲目顺序已{'倒序' if reverse_order else '正序'}排列") 