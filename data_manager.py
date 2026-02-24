# data_manager.py - 负责所有数据的加载与保存
import os
import json
from pathlib import Path

SAVE_DIR = "Save"
FOLDERS_FILE = os.path.join(SAVE_DIR, "FolderPath.json")
LABELS_FILE = os.path.join(SAVE_DIR, "AllMoviesLabel.json")
ALL_TAGS_FILE = os.path.join(SAVE_DIR, "AllKnownTags.json")

os.makedirs(SAVE_DIR, exist_ok=True)

class DataManager:
    def __init__(self):
        self.folders = []
        self.all_videos_info = {}
        self.all_known_tags = set()
        self.load_all()

    def load_all(self):
        self.load_folders()
        self.load_labels()
        self.load_all_known_tags()

    def load_folders(self):
        self.folders = []
        try:
            if os.path.exists(FOLDERS_FILE):
                with open(FOLDERS_FILE, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    folders = data.get("folders", [])
                    for f in folders:
                        if os.path.exists(f):
                            self.folders.append(os.path.normpath(f))
        except Exception as e:
            print(f"[Data Load Error] 读取 {FOLDERS_XFILE} 出错: {e}")

    def save_folders(self, folders):
        try:
            with open(FOLDERS_FILE, 'w', encoding='utf-8') as f:
                json.dump({"folders": folders}, f, indent=4, ensure_ascii=False)
            print(f"[Data Save] 已保存文件夹列表到 {FOLDERS_FILE}")
        except Exception as e:
            print(f"[Data Save Error] 保存 {FOLDERS_FILE} 出错: {e}")

    def load_labels(self):
        self.all_videos_info = {}
        try:
            if os.path.exists(LABELS_FILE):
                with open(LABELS_FILE, 'r', encoding='utf-8') as f:
                    self.all_videos_info = json.load(f)
                for info in self.all_videos_info.values():
                    self.all_known_tags.update(info.get('tags', []))
        except Exception as e:
            print(f"[Data Load Error] 读取 {LABELS_FILE} 出错: {e}")

    def save_labels(self, all_videos_info):
        try:
            with open(LABELS_FILE, 'w', encoding='utf-8') as f:
                json.dump(all_videos_info, f, indent=4, ensure_ascii=False)
            print(f"[Data Save] 已保存视频标签到 {LABELS_FILE}")
        except Exception as e:
            print(f"[Data Save Error] 保存 {LABELS_FILE} 出错: {e}")

    def load_all_known_tags(self):
        try:
            if os.path.exists(ALL_TAGS_FILE):
                with open(ALL_TAGS_FILE, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    self.all_known_tags = set(data.get("tags", []))
        except Exception as e:
            print(f"[Data Load Error] 读取 {ALL_TAGS_FILE} 出错: {e}")

    def save_all_known_tags(self, tags_set):
        try:
            with open(ALL_TAGS_FILE, 'w', encoding='utf-8') as f:
                json.dump({"tags": list(tags_set)}, f, indent=4, ensure_ascii=False)
            print(f"[Data Save] 已保存全局标签到 {ALL_TAGS_FILE}")
        except Exception as e:
            print(f"[Data Save Error] 保存 {ALL_TAGS_FILE} 出错: {e}")