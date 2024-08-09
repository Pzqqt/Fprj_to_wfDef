import os
import sys
import json

from PIL import Image


WIDTH = 192
HEIGHT = 490
FORCE_ONE_BIT_DATA_SRCS = frozenset({
    "0911", "911",  # 小时(个)
    "0A11", "10911", "1000911",  # 小时(十)
    "1111",  # 分钟(个)
    "1211",  # 分钟(十)
    "1911",  # 秒(个)
    "1A11", "11911", "1001911",  # 秒(十)
    "2012",  # 星期
    "1912",  # 日期-日(个)
    "1A12", "11912", "1001912",  # 日期-日(十)
})

class PreviewImg:

    def __init__(self, image_dir: str, color=None):
        self.image_dir = image_dir
        self.res_images = os.listdir(image_dir)
        self.img = Image.new("RGBA", (WIDTH, HEIGHT), color=color)

    def find_image_file(self, file_name: str) -> str:
        for f in self.res_images:
            if f.rsplit('.', 1)[0] == file_name:
                return os.path.join(self.image_dir, f)
        raise FileNotFoundError(os.path.join(self.image_dir, file_name))

    def add_element(self, element: dict):
        if element["x"] >= 2 ** 15:
            element["x"] = 2 ** 16 - element["x"]
        if element["y"] >= 2 ** 15:
            element["y"] = 2 ** 16 - element["y"]
        if element["type"] == "element":
            with Image.open(self.find_image_file(element["image"])) as img_:
                try:
                    self.img.alpha_composite(img_, (element["x"], element["y"]))
                except ValueError:
                    self.img.paste(img_, (element["x"], element["y"]))
        elif element["type"] == "widge_imagelist":
            index = 0
            if element["dataSrc"] in ("0911", "911"):
                index = 9
            elif element["dataSrc"] == "1211":
                index = 2
            elif element["dataSrc"] == "1111":
                index = 8
            elif element["dataSrc"] == "2012":
                index = 5
            with Image.open(self.find_image_file(element["imageList"][index])) as img_:
                self.img.alpha_composite(img_, (element["x"], element["y"]))
        elif element["type"] == "widge_dignum":
            self._add_widge_dignum(element)
        elif element["type"] == "widge_pointer":
            new_img = self.__class__(self.image_dir)
            element_tmp = element.copy()
            element_tmp["type"] = "element"
            new_img.add_element(element_tmp)
            new_img = new_img.img
            if element["dataSrc"] in ("0811", "811"):  # 分针旋转60度(指向2的位置)
                new_img = new_img.rotate(
                    -60, center=(element["x"] + element["imageRotateX"], element["y"] + element["imageRotateY"])
                )
            elif element["dataSrc"] == "1811":  # 秒针旋转150度(指向5的位置)
                new_img = new_img.rotate(
                    -150, center=(element["x"] + element["imageRotateX"], element["y"] + element["imageRotateY"])
                )
            self.img.alpha_composite(new_img, (0, 0))
        else:
            print("Warning: Unsupported element type: " + str(element["type"]))

    def _add_widge_dignum(self, element: dict) -> int:
        assert element["type"] == "widge_dignum", \
            "Error: The '_add_widge_dignum' method only supports adding widgets of type 'widge_dignum'. " \
            "Please use the 'add_element' method instead."
        # if element["x"] >= 2 ** 15:
        #     element["x"] = 2 ** 16 - element["x"]
        # if element["y"] >= 2 ** 15:
        #     element["y"] = 2 ** 16 - element["y"]
        show_count = int(element["showCount"])
        align = int(element["align"])  # 0: 右对齐 1: 左对齐, 2: 居中
        spacing = int(element.get("spacing", 0))
        if spacing >= 2 ** 7:
            spacing = 2 ** 8 - spacing
        # show_zero = int(element["showZero"])  # unused
        if element["dataSrc"] in FORCE_ONE_BIT_DATA_SRCS:
            show_count = 1
        if align not in (0, 1, 2):
            raise ValueError("Invalid align value: " + str(element["align"]))
        if align == 1:  # 左对齐
            x_now = element["x"]
            draw_width = 0
            nums_index = range(show_count)
            if element["dataSrc"] in ("0841", "841") and show_count == 3:
                nums_index = (1, 0, 0)
            for image_index in nums_index:
                with Image.open(self.find_image_file(element["imageList"][image_index])) as img_:
                    self.img.alpha_composite(img_, (x_now, element["y"]))
                    x_now += img_.width + spacing
                    draw_width += img_.width + spacing
            x_now -= spacing
            draw_width -= spacing
            if append_image := element.get("image"):
                with Image.open(self.find_image_file(append_image)) as img_:
                    self.img.alpha_composite(img_, (x_now, element["y"]))
                    x_now += img_.width
                    draw_width += img_.width
            return draw_width
        elif align == 0:  # 右对齐
            new_img = self.__class__(self.image_dir)
            element_cpy = element.copy()
            element_cpy["align"] = "1"
            element_cpy["x"] = 0
            element_cpy["y"] = 0
            new_img_draw_width = new_img._add_widge_dignum(element_cpy)
            self.img.alpha_composite(new_img.img, (element["x"] - new_img_draw_width, element["y"]))
            return new_img_draw_width
        elif align == 2:  # 居中
            new_img = self.__class__(self.image_dir)
            element_cpy = element.copy()
            element_cpy["align"] = "1"
            element_cpy["x"] = 0
            element_cpy["y"] = 0
            new_img_draw_width = new_img._add_widge_dignum(element_cpy)
            self.img.alpha_composite(new_img.img, (element["x"] - int(new_img_draw_width / 2), element["y"]))
            return new_img_draw_width

    def save(self, *args, **kwargs):
        self.img.save(*args, **kwargs)

def main(prj_path: str):
    with open(os.path.join(prj_path, "wfDef.json"), 'r', encoding="utf-8") as f:
        data = json.load(f)

    elements = data.get("elementsNormal", [])
    edit_nums = {element.get("editNum1") for element in elements if element.get("editNum1")}
    if not edit_nums:
        edit_nums = {None, }
    for edit_num in sorted(edit_nums):
        preview_img = PreviewImg(os.path.join(prj_path, "images"), color="black")
        for element in elements:
            element_edit_num = element.get("editNum1")
            if element_edit_num is None or element_edit_num == edit_num:
                preview_img.add_element(element)
        preview_file_name = "preview_normal"
        if edit_num:
            preview_file_name += '_' + str(edit_num)
        preview_file_name += ".png"
        print("Info: Drawing", preview_file_name, "...")
        preview_img.save(os.path.join(prj_path, preview_file_name), "PNG")

    elements_aod = data.get("elementsAod", [])
    preview_aod_img = PreviewImg(os.path.join(prj_path, "images_aod"), color="black")
    for element in elements_aod:
        preview_aod_img.add_element(element)
    print("Info: Drawing preview_aod.png ...")
    preview_aod_img.save(os.path.join(prj_path, "preview_aod.png"), "PNG")
    print("Info: Done!")

if __name__ == '__main__':
    if len(sys.argv) >= 2:
        main(sys.argv[1])
    else:
        print("Usage: %s <wfDef_project_dir>" % sys.argv[0])
