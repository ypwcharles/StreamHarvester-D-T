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
        
        # 下载目录选择
        self.dir_frame = ctk.CTkFrame(self.main_frame)
        self.dir_frame.grid(row=2, column=0, padx=10, pady=5, sticky="ew")
        
        self.dir_label = ctk.CTkLabel(self.dir_frame, text="下载目录:")
        self.dir_label.grid(row=0, column=0, padx=5, pady=5)
        
        self.dir_entry = ctk.CTkEntry(self.dir_frame, width=300)
        self.dir_entry.grid(row=0, column=1, padx=5, pady=5, sticky="ew")
        self.dir_entry.insert(0, os.path.expanduser("~/Downloads/Podcasts"))
        
        self.dir_button = ctk.CTkButton(self.dir_frame, text="选择目录", command=self.choose_directory)
        self.dir_button.grid(row=0, column=2, padx=5, pady=5)
        
        self.dir_frame.grid_columnconfigure(1, weight=1)
        
        # 播客列表框架
        self.list_frame = ctk.CTkFrame(self)
        self.list_frame.grid(row=1, column=0, padx=20, pady=10, sticky="nsew")
        self.list_frame.grid_columnconfigure(0, weight=1)
        self.list_frame.grid_rowconfigure(0, weight=1)
        
        # 创建表格
        self.tree = ttk.Treeview(self.list_frame, columns=("标题", "时长", "发布日期"), show="headings")
        self.tree.heading("标题", text="标题")
        self.tree.heading("时长", text="时长")
        self.tree.heading("发布日期", text="发布日期")
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
        
    def choose_directory(self):
        dir_path = filedialog.askdirectory(initialdir=self.dir_entry.get())
        if dir_path:
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
            
    def fetch_podcast_list(self):
        def fetch():
            url = self.url_entry.get()
            if not url:
                messagebox.showerror("错误", "请输入播客链接")
                return
                
            try:
                self.status_label.configure(text="正在获取播客列表...")
                self.fetch_button.configure(state="disabled")
                
                # 如果是 Apple Podcast 链接，获取并解析 RSS feed
                if 'podcasts.apple.com' in url:
                    feed_url = self.get_rss_feed(url)
                    self.logger.info(f"获取到 RSS feed URL: {feed_url}")
                    podcast_items = self.parse_rss_feed(feed_url)
                else:
                    raise Exception("目前仅支持 Apple Podcast 链接")
                
                # 清空现有列表
                for item in self.tree.get_children():
                    self.tree.delete(item)
                self.podcast_items = []
                
                # 添加播客条目
                for item in podcast_items:
                    title = item['title']
                    duration_str = self.format_duration(item['duration'])
                    upload_date = self.format_date(item['upload_date'])
                    
                    self.podcast_items.append({
                        'title': title,
                        'url': item['url'],
                        'duration': duration_str,
                        'upload_date': upload_date
                    })
                    
                    self.tree.insert("", "end", values=(title, duration_str, upload_date))
                    
                self.status_label.configure(text=f"成功获取 {len(self.podcast_items)} 个播客")
                
            except Exception as e:
                error_msg = f"获取播客列表失败: {str(e)}"
                self.logger.error(error_msg)
                messagebox.showerror("错误", error_msg)
                self.status_label.configure(text="获取列表失败")
                
            finally:
                self.fetch_button.configure(state="normal")
                
        Thread(target=fetch).start()
        
    def download_selected(self):
        def download():
            selected_items = self.tree.selection()
            if not selected_items:
                messagebox.showwarning("警告", "请选择要下载的播客")
                return
                
            try:
                self.download_button.configure(state="disabled")
                total = len(selected_items)
                completed = 0
                
                for item in selected_items:
                    index = self.tree.index(item)
                    podcast = self.podcast_items[index]
                    
                    self.status_label.configure(text=f"正在下载: {podcast['title']}")
                    
                    ydl_opts = {
                        'outtmpl': os.path.join(self.dir_entry.get(), '%(title)s.%(ext)s'),
                        'quiet': True,
                    }
                    
                    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                        ydl.download([podcast['url']])
                        
                    completed += 1
                    progress = completed / total
                    self.progress_bar.set(progress)
                    
                self.status_label.configure(text="下载完成！")
                messagebox.showinfo("成功", f"成功下载 {completed} 个播客")
                
            except Exception as e:
                error_msg = f"下载失败: {str(e)}"
                self.logger.error(error_msg)
                messagebox.showerror("错误", error_msg)
                self.status_label.configure(text="下载失败")
                
            finally:
                self.download_button.configure(state="normal")
                
        Thread(target=download).start()
        
    def select_all(self):
        for item in self.tree.get_children():
            self.tree.selection_add(item)
            
    def deselect_all(self):
        for item in self.tree.get_children():
            self.tree.selection_remove(item) 