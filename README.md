# Image Text Translator

Extracts Japanese text from images, translates it to English, and overlays the translation back onto the image while preserving the original layout.

## Features

- OCR-based text extraction with **EasyOCR** (JP + EN)
- Translation via Google Translate API
- In-place text replacement with **Pillow** (preserves font, position, background)
- Manual correction & removal tools (`manual_correction.py`, `manual_remove.py`)
- Tkinter GUI for batch processing

## Architecture

```
.
├── auto_translate.py       # Automated pipeline: OCR -> translate -> overlay
├── manual_correction.py    # GUI to manually fix OCR mistakes
├── manual_remove.py        # GUI to manually remove unwanted text regions
└── requirements.txt
```

### Pipeline

1. Read the input image
2. Run EasyOCR (Japanese model) → extract text + bounding boxes
3. Send each text block to Google Translate (JP → EN)
4. Erase original Japanese text using inpainting / background sampling
5. Render the translated text in-place using Pillow

## Setup

```bash
python -m venv venv
source venv/bin/activate   # Windows: venv\Scripts\activate
pip install -r requirements.txt
```

Place your input images in a `data_jp/` folder (gitignored). Output is written to `data_en/`.

## Usage

```bash
# Automated mode
python auto_translate.py

# Manual correction GUI
python manual_correction.py

# Manual text-removal GUI
python manual_remove.py
```

## Stack

- Python 3.9+
- EasyOCR
- Pillow
- googletrans
- Tkinter (stdlib)

## License

MIT
