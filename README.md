# StreamHarvester - 视频下载工具

一个支持多平台视频下载的图形界面工具，基于 yt-dlp 开发。

## 功能特点

- 支持多个视频平台的视频下载
- 支持多浏览器 Cookie 导入（Chrome、Firefox、Edge、Opera、Brave）
- 支持自定义视频质量和格式选择
- 支持下载进度显示
- 支持视频和音频分离下载

## 系统要求

- Python 3.8 或更高版本
- Windows/Linux/MacOS

## 安装

1. 克隆仓库：
```bash
git clone https://github.com/yourusername/StreamHarvester.git
cd StreamHarvester
```

2. 安装依赖：
```bash
pip install -r requirements.txt
```

## 使用说明

1. 运行程序：
```bash
python main.py
```

2. 基本使用流程：
   - 输入要下载的视频链接
   - 选择是否使用浏览器 Cookie（如需要登录的视频）
   - 选择下载目录
   - 选择下载质量（最佳质量/最佳视频/最佳音频/自定义格式）
   - 点击"获取可用格式"
   - 如选择自定义格式，在列表中选择需要的视频和音频格式
   - 点击"开始下载"

3. Cookie 使用说明：
   - 如需下载需要登录的视频，请先在对应浏览器中登录网站
   - 在程序中选择对应的浏览器
   - 程序会自动获取浏览器中的 Cookie

4. 格式选择说明：
   - 最佳质量：自动选择最佳视频和音频质量并合并
   - 最佳视频：仅下载最高质量视频流
   - 最佳音频：仅下载最高质量音频流
   - 自定义格式：手动选择视频和音频格式

## 注意事项

- 下载需要登录的视频时，请确保已在选择的浏览器中登录相应网站
- 某些视频可能因为地区限制或版权问题无法下载
- 下载速度受网络条件和服务器限制影响

## 依赖项

- customtkinter
- yt-dlp
- browser-cookie3
- Pillow

## 许可证

MIT License 