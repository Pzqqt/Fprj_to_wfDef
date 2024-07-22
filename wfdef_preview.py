import os
import sys
import json

from PIL import Image


WIDTH = 192
HEIGHT = 490
FORCE_ONE_BIT_DATA_SRCS = (
    "0911", "911",  # 小时(个)
    "0A11", "10911", "1000911",  # 小时(十)
    "1111",  # 分钟(个)
    "1211",  # 分钟(十)
    "1911",  # 秒(个)
    "1A11", "11911", "1001911",  # 秒(十)
)

class PreviewImg:

    def __init__(self, image_dir: str):
        self.image_dir = image_dir
        self.res_images = os.listdir(image_dir)
        self.img = Image.new("RGBA", (WIDTH, HEIGHT))

    def find_image_file(self, file_name: str) -> str:
        for f in self.res_images:
            if f.rsplit('.', 1)[0] == file_name:
                return os.path.join(self.image_dir, f)
        raise FileNotFoundError

    def add_element(self, element: dict) -> (int, int):
        if element["type"] == "element":
            with Image.open(self.find_image_file(element["image"])) as img_:
                try:
                    self.img.paste(img_, (element["x"], element["y"]), img_)
                except ValueError:
                    self.img.paste(img_, (element["x"], element["y"]))
                return img_.width, img_.height
        elif element["type"] == "widge_imagelist":
            with Image.open(self.find_image_file(element["imageList"][0])) as img_:
                self.img.paste(img_, (element["x"], element["y"]), img_)
                return img_.width, img_.height
        elif element["type"] == "widge_dignum":
            show_count = int(element["showCount"])
            align = int(element["align"])  # 0: 右对齐 1: 左对齐, 2: 居中
            spacing = int(element.get("spacing", 0))
            # show_zero = int(element["showZero"])  # unused
            if element["dataSrc"] in FORCE_ONE_BIT_DATA_SRCS:
                show_count = 1
            if align not in (0, 1, 2):
                raise ValueError("Invalid align value: " + str(element["align"]))
            if align == 1:  # 左对齐
                x_now = element["x"]
                draw_width = 0
                draw_height = 0
                for image_index in range(show_count):
                    with Image.open(self.find_image_file(element["imageList"][image_index])) as img_:
                        self.img.paste(img_, (x_now, element["y"]), img_)
                        x_now += img_.width + spacing
                        draw_width += img_.width + spacing
                        draw_height = max(draw_height, img_.height)
                x_now -= spacing
                draw_width -= spacing
                if append_image := element.get("image"):
                    with Image.open(self.find_image_file(append_image)) as img_:
                        self.img.paste(img_, (x_now, element["y"]), img_)
                        x_now += img_.width
                        draw_width += img_.width
                        draw_height = max(draw_height, img_.height)
                return draw_width, draw_height
            elif align == 0:  # 右对齐
                new_img = self.__class__(self.image_dir)
                element_cpy = element.copy()
                element_cpy["align"] = "1"
                element_cpy["x"] = 0
                element_cpy["y"] = 0
                new_img_draw_width, new_img_draw_height = new_img.add_element(element_cpy)
                self.img.paste(new_img.img, (element["x"] - new_img_draw_width, element["y"]), new_img.img)
                return new_img_draw_width, new_img_draw_height
            elif align == 2:  # 居中
                new_img = self.__class__(self.image_dir)
                element_cpy = element.copy()
                element_cpy["align"] = "1"
                element_cpy["x"] = 0
                element_cpy["y"] = 0
                new_img_draw_width, new_img_draw_height = new_img.add_element(element_cpy)
                self.img.paste(new_img.img, (element["x"] - int(new_img_draw_width / 2), element["y"]), new_img.img)
                return new_img_draw_width, new_img_draw_height
        elif element["type"] == "widge_pointer":
            box_width = element["imageRotateY"] * 2 - 1
            box_height = box_width
            new_img = Image.new("RGBA", size=(box_width, box_height))
            with Image.open(self.find_image_file(element["image"])) as img_:
                new_img.paste(img_, (element["imageRotateY"] - element["imageRotateX"], 0), img_)
            if element["dataSrc"] in ("0811", "811"):  # 时针旋转60度(指向2的位置)
                new_img = new_img.rotate(-60, center=((box_width + 1) // 2, (box_height + 1) // 2))
            elif element["dataSrc"] == "1811":  # 时针旋转150度(指向5的位置)
                new_img = new_img.rotate(-150, center=((box_width + 1) // 2, (box_height + 1) // 2))
            self.img.paste(
                new_img,
                (element["x"] - (element["imageRotateY"] - element["imageRotateX"]), element["y"]),
                new_img
            )
            return new_img.width, new_img.height
        else:
            print("Warning: Unsupported element type: " + str(element["type"]))
            return 0, 0

    def save(self, *args, **kwargs):
        self.img.save(*args, **kwargs)

def main(prj_path: str):
    with open(os.path.join(prj_path, "wfDef.json"), 'r', encoding="utf-8") as f:
        data = json.load(f)

    elements = data.get("elementsNormal", [])
    edit_nums = {element.get("editNum1") for element in elements if element.get("editNum1")}
    if not edit_nums:
        edit_nums = {None, }
    for edit_num in edit_nums:
        preview_img = PreviewImg(os.path.join(prj_path, "images"))
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
    preview_aod_img = PreviewImg(os.path.join(prj_path, "images_aod"))
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
