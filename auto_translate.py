import os
from pathlib import Path
import numpy as np
from PIL import Image, ImageDraw, ImageFont
import easyocr
from deep_translator import GoogleTranslator
import re

def contains_japanese(text):
    return bool(re.search(r'[\u3040-\u309F\u30A0-\u30FF\u4E00-\u9FFF]', text))

def extract_text_from_image(image_path):
    reader = easyocr.Reader(['ja', 'en'])
    
    # Load the image and convert to RGB
    image = Image.open(image_path).convert('RGB')
    
    # Convert PIL image to numpy array
    image_np = np.array(image)
    
    # Pass numpy array to easyocr
    results = reader.readtext(image_np, detail=1, paragraph=False)
    text_and_boxes = [(result[1], result[0]) for result in results]
    
    return text_and_boxes

def translate_text(text, src_lang='ja', dest_lang='en'):
    translator = GoogleTranslator(source=src_lang, target=dest_lang)
    try:
        return translator.translate(text)
    except Exception as e:
        print(f"Translation error: {e}")
        return text

def get_background_color(image, box):
    box = [(int(coord[0]), int(coord[1])) for coord in box]
    x1, y1 = box[0]
    x2, y2 = box[2]
    extension = 10
    x1, y1 = max(0, x1 - extension), max(0, y1 - extension)
    x2, y2 = min(image.width, x2 + extension), min(image.height, y2 + extension)
    
    pixels = [image.getpixel((x, y)) for x in range(x1, x2) for y in range(y1, y2)]
    pixel_counts = {}
    for color in pixels:
        if color not in pixel_counts:
            pixel_counts[color] = 0
        pixel_counts[color] += 1
    
    most_common_color = max(pixel_counts, key=pixel_counts.get)
    return most_common_color

def erase_text(image, bounding_boxes):
    draw = ImageDraw.Draw(image)
    for box in bounding_boxes:
        if isinstance(box, list):
            box = [tuple(point) for point in box]
        bg_color = get_background_color(image, box)
        draw.polygon(box, fill=bg_color)
    return image

def fill_color_spots(image):
    image = image.convert("RGB")
    width, height = image.size
    pixels = image.load()
    color_counts = {}
    for y in range(height):
        for x in range(width):
            color = pixels[x, y]
            if color not in color_counts:
                color_counts[color] = 0
            color_counts[color] += 1
    
    most_common_color = max(color_counts, key=color_counts.get)
    for y in range(height):
        for x in range(width):
            if pixels[x, y] == (255, 255, 255):
                pixels[x, y] = most_common_color
    
    return image

def clean_translated_text(special_chars, translated_text):
    if len(special_chars) == 2:
        return f"{special_chars[0]}{translated_text}{special_chars[1]}".strip()
    return translated_text.strip()

def estimate_font_size(box, text):
    x1, y1 = box[0]
    x2, y2 = box[2]
    box_height = y2 - y1
    base_font_size = max(int(box_height * 0.8), 8)

    font_path = "C:/Windows/Fonts/arial.ttf"
    font_size = base_font_size
    
    try:
        font = ImageFont.truetype(font_path, font_size)
    except OSError:
        print("Error: Unable to open font resource. Check the font path.")
        return None
    
    if text is None:
        print("Warning: Translated text is None.")
        return None

    while font.getbbox(text)[2] > (x2 - x1) and base_font_size > 8:
        base_font_size -= 1
        try:
            font = ImageFont.truetype(font_path, base_font_size)
        except OSError:
            font = ImageFont.load_default()
    
    return font


def adjust_text_color(bg_color):
    r, g, b = bg_color
    if (r*0.299 + g*0.587 + b*0.114) < 128:
        return (255, 255, 255)
    return (0, 0, 0)

def add_text_outline(draw, text, position, font, color, outline_color, outline_width=2):
    x, y = position
    for offset in range(-outline_width, outline_width + 1):
        draw.text((x + offset, y), text, font=font, fill=outline_color)
        draw.text((x, y + offset), text, font=font, fill=outline_color)
        draw.text((x + offset, y + offset), text, font=font, fill=outline_color)
        draw.text((x + offset, y - offset), text, font=font, fill=outline_color)
        draw.text((x - offset, y + offset), text, font=font, fill=outline_color)
    draw.text((x, y), text, font=font, fill=color)

def process_images(input_image_path, output_image_path):
    if not os.path.isfile(input_image_path):
        raise FileNotFoundError(f"The file {input_image_path} does not exist.")
    
    image = Image.open(input_image_path).convert("RGB")
    text_and_boxes = extract_text_from_image(input_image_path)
    japanese_boxes = [box for (text, box) in text_and_boxes if contains_japanese(text)]

    print("Textes extraits et leurs boîtes de délimitation :")
    for text, box in text_and_boxes:
        print(f"Texte : {text} | Boîte : {box}")

    image = erase_text(image, japanese_boxes)
    draw = ImageDraw.Draw(image)
    
    for text, box in text_and_boxes:
        if contains_japanese(text):
            translated_text = translate_text(text.strip())
            bg_color = get_background_color(image, box)
            text_color = adjust_text_color(bg_color)

            font = estimate_font_size(box, translated_text)
            if font is None:
                continue

            if bg_color == (0, 0, 0):
                add_text_outline(draw, translated_text, (box[0][0], box[0][1]), font, text_color, (255, 255, 255))
            else:
                draw.text((box[0][0], box[0][1]), translated_text, font=font, fill=text_color)
                
            print(f"Texte original : {text} | Texte traduit : {translated_text} | Couleur de fond : {bg_color} | Couleur du texte : {text_color}")

    image.save(output_image_path)

# Set input and output directories
input_directory = Path('data_jp')
output_directory = Path('data_en')

# Ensure the output directory exists
output_directory.mkdir(exist_ok=True)

# Process each image file in the input directory
for subdir, _, files in os.walk(input_directory):
    for file in files:
        if file.lower().endswith(('.png', '.jpg', '.jpeg')):
            input_image_path = Path(subdir) / file
            output_subdir = output_directory / Path(subdir).relative_to(input_directory)
            output_subdir.mkdir(parents=True, exist_ok=True)
            output_image_path = output_subdir / file

            process_images(input_image_path, output_image_path)
