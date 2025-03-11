import PyInstaller.__main__
import os
import shutil

def build():
    # 清理之前的构建文件
    if os.path.exists('dist'):
        shutil.rmtree('dist')
    if os.path.exists('build'):
        shutil.rmtree('build')
        
    # PyInstaller 配置
    PyInstaller.__main__.run([
        'main.py',
        '--name=StreamHarvester',
        '--windowed',  # 不显示控制台窗口
        '--noconfirm',  # 覆盖输出目录
        '--clean',  # 清理临时文件
        '--onefile',  # 打包成单个文件
    ])

if __name__ == '__main__':
    build() 