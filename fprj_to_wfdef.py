import os
import re
import json
import shutil
import sys

from bs4 import BeautifulSoup
from PIL import Image
import lxml


del lxml

def remove_path(path: str):
    if os.path.isdir(path):
        shutil.rmtree(path)
    elif os.path.isfile(path):
        os.remove(path)

def mkdir(path: str):
    if os.path.exists(path):
        remove_path(path)
    os.makedirs(path)

class WatchFace:

    def __init__(self, src_dir: str, dst_dir: str):
        self.src_dir = src_dir
        self.dst_dir = dst_dir
        self.fprj_info = self.parse_fprj_dir(src_dir)
        if not (self.fprj_info["conf_file"] and self.fprj_info["images"] and self.fprj_info["aod"]):
            raise Exception("Sorry, %s is not a valid fprj project!" % self.src_dir)

    @staticmethod
    def rm_subfix(file_name: str) -> str:
        return file_name.rsplit('.', 1)[0]

    @staticmethod
    def switch_alignment_value(val: int) -> int:
        # EasyFace: 0: 左对齐, 1: 居中, 2: 右对齐
        # WatchfacePackTool: 0: 右对齐 1: 左对齐, 2: 居中
        if val == 0:
            return 1
        if val == 1:
            return 2
        if val == 2:
            return 0
        raise ValueError

    @staticmethod
    def split_bitmap_list(bitmap: str) -> list:
        files = bitmap.split('|')
        if not re.match(r'\((\d+)\):(.+)', files[0]):
            return files
        files_group = []
        for file in files:
            if re_match := re.match(r'\((\d+)\):(.+)', file):
                files_group.append(
                    (int(re_match.group(1)), re_match.group(2))
                )
        return sorted(files_group)

    @classmethod
    def parse_fprj_dir(cls, fprj_dir: str) -> dict:
        fprj_info = {
            "conf_file": "",
            "images": [],
            "aod": None,
        }
        for filename in os.listdir(fprj_dir):
            file_path = os.path.join(fprj_dir, filename)
            if os.path.isfile(file_path) and filename.endswith(".fprj"):
                fprj_info["conf_file"] = os.path.join(fprj_dir, filename)
            elif os.path.isdir(file_path) and filename == "images":
                fprj_info["images"] = os.listdir(file_path)
            elif os.path.isdir(file_path) and filename == "AOD":
                fprj_info["aod"] = cls.parse_fprj_dir(file_path)
        return fprj_info

    def parse_fprj_conf_file(self):
        info_dic = {}

        fprj_conf_file = self.fprj_info["conf_file"]
        with open(fprj_conf_file, 'r', encoding='utf-8') as f:
            bs_obj = BeautifulSoup(f.read(), features="xml")
        info_dic["name"] = bs_obj.FaceProject.Screen["Title"]
        info_dic["id"] = ""  # None
        info_dic["previewImg"] = self.rm_subfix(bs_obj.FaceProject.Screen["Bitmap"])

        def _parse_elements(fprj_conf_file_, bs_obj_):
            elements = []
            for widget in bs_obj_.select("FaceProject > Screen > Widget"):
                widget_info = {}

                widget_name = widget["Name"]
                element_type = ""
                if widget["Shape"] == "30":
                    element_type = "element"
                elif widget["Shape"] == "31":
                    element_type = "widge_imagelist"
                elif widget["Shape"] == "32":
                    element_type = "widge_dignum"
                elif widget["Shape"] == "27":
                    print("Warning: Widget: '%s': This tool does not yet support converting "
                          "clock hand widget. skipping..." % widget_name)
                    continue
                if not element_type:
                    print("Warning: Invalid Widget: '%s', element type: %s" % (widget_name, widget["Shape"]))
                    continue

                if re.match(r'.*?_angle\[\d+\]$', widget_name):
                    print("Warning: The rotation angle of widget '%s' will be ignored." % widget_name)

                # Attrs
                widget_info["type"] = element_type
                widget_info["x"] = int(widget["X"])
                widget_info["y"] = int(widget["Y"])
                if element_type == "widge_imagelist":
                    widget_info["dataSrc"] = widget["Index_Src"]
                    if widget["Index_Src"] in ("10911", "1000911"):
                        widget_info["dataSrc"] = "0A11"
                    elif widget["Index_Src"] in ("11911", "1001911"):
                        widget_info["dataSrc"] = "1A11"
                elif element_type == "widge_dignum":
                    widget_info["showCount"] = int(widget["Digits"])
                    widget_info["align"] = self.switch_alignment_value(int(widget["Alignment"]))
                    widget_info["showZero"] = not bool(int(widget["Blanking"]))
                    widget_info["dataSrc"] = widget["Value_Src"]
                    widget_info["spacing"] = int(widget["Spacing"])

                # Images
                if element_type == "element":
                    widget_info["image"] = self.rm_subfix(widget.get("Bitmap", ""))
                elif element_type == "widge_imagelist":
                    image_list = self.split_bitmap_list(widget.get("BitmapList"))
                    assert image_list and isinstance(image_list[0], tuple)
                    widget_info["imageList"] = [self.rm_subfix(f_[1]) for f_ in image_list]
                    widget_info["imageIndexList"] = [f_[0] for f_ in image_list]
                elif element_type == "widge_dignum":
                    image_list = self.split_bitmap_list(widget.get("BitmapList"))
                    assert image_list and isinstance(image_list[0], str)
                    widget_info["imageList"] = [self.rm_subfix(f_) for f_ in image_list]

                # Correct X coordinate
                if element_type == "widge_dignum":
                    if widget_info["align"] in (0, 2):
                        sample_file = widget_info["imageList"][0]
                        images_dir = os.path.join(os.path.dirname(fprj_conf_file_), "images")
                        for f__ in os.listdir(images_dir):
                            if f__.startswith(sample_file+'.'):
                                sample_file = f__
                                break
                        with Image.open(os.path.join(images_dir, sample_file)) as img:
                            width = img.width
                        len_ = widget_info["showCount"] * (width + widget_info["spacing"]) - widget_info["spacing"]
                        if widget_info["align"] == 0:
                            widget_info["x"] += len_
                        elif widget_info["align"] == 2:
                            widget_info["x"] += int(len_ / 2)
                        print("Info: Correct X coordinate for %s element." % widget_name)

                elements.append(widget_info)
            return elements

        info_dic["elementsNormal"] = _parse_elements(fprj_conf_file, bs_obj)

        fprj_conf_file = self.fprj_info["aod"]["conf_file"]
        with open(fprj_conf_file, 'r', encoding='utf-8') as f:
            bs_aod_obj = BeautifulSoup(f.read(), features="xml")
        info_dic["elementsAod"] = _parse_elements(fprj_conf_file, bs_aod_obj)

        return info_dic

    def make(self):
        mkdir(self.dst_dir)
        shutil.copytree(os.path.join(self.src_dir, "images"), os.path.join(self.dst_dir, "images"))
        shutil.copytree(os.path.join(self.src_dir, "AOD", "images"), os.path.join(self.dst_dir, "images_aod"))
        with open(os.path.join(self.dst_dir, "wfDef.json"), 'w', encoding='utf-8') as f:
            json.dump(self.parse_fprj_conf_file(), f, indent=4, ensure_ascii=False)
        print("Warning: Edit %s and fill in the id attribute manually." % os.path.join(self.dst_dir, "wfDef.json"))

if __name__ == '__main__':
    if len(sys.argv) >= 3:
        WatchFace(sys.argv[1], sys.argv[2]).make()
    else:
        print("Usage: %s <src_dir> <dst_dir>" % sys.argv[0])
