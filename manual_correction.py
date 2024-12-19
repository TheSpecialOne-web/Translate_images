import os
import json
from pathlib import Path
import numpy as np
from PIL import Image, ImageDraw, ImageFont
import easyocr
from deep_translator import GoogleTranslator
import re
import tkinter as tk
from tkinter import simpledialog
from tkinter import font

# Chemin vers le fichier JSON pour stocker les corrections
CORRECTIONS_FILE = "corrections.json"


# Charger les corrections existantes
def load_corrections():
    if os.path.exists(CORRECTIONS_FILE):
        with open(CORRECTIONS_FILE, "r", encoding="utf-8") as f:
            return json.load(f)  # Retourne le contenu du fichier JSON
    return {}  # Retourne un dictionnaire vide si le fichier n'existe pas

# Sauvegarder les corrections dans un fichier JSON sans écraser les anciennes
def save_corrections(new_corrections):
    # Charger les anciennes corrections
    corrections = load_corrections()
    
    # Ajouter/mettre à jour avec les nouvelles corrections
    corrections.update(new_corrections)
    
    # Sauvegarder le tout dans le fichier
    with open(CORRECTIONS_FILE, "w", encoding="utf-8") as f:
        json.dump(corrections, f, ensure_ascii=False, indent=4)
        

# Charger les corrections au début du programme
corrections_dict = load_corrections()


# Fonction pour vérifier si le texte contient des caractères japonais
def contains_japanese(text):
    return bool(
        re.search(r"[\u3040-\u309F\u30A0-\u30FF\u4E00-\u9FFF]", text)
    )  # Retourne True si des caractères japonais sont trouvés


# Fonction pour extraire le texte et les zones de texte d'une image
def extract_text_from_image(image_path):
    reader = easyocr.Reader(
        ["ja", "en"]
    )  # Initialiser le lecteur EasyOCR pour le japonais et l'anglais
    image = Image.open(image_path).convert(
        "RGB"
    )  # Ouvrir l'image et la convertir en RGB
    image_np = np.array(image)  # Convertir l'image en tableau numpy
    results = reader.readtext(
        image_np, detail=1, paragraph=False
    )  # Lire le texte dans l'image
    text_and_boxes = [
        (result[1], result[0]) for result in results
    ]  # Extraire le texte et les coordonnées
    return text_and_boxes  # Retourner le texte et les zones


# Fonction pour traduire le texte japonais en anglais
def translate_text(text, src_lang="ja", dest_lang="en"):
    # Si le texte a déjà été corrigé, retourner la traduction corrigée
    if text in corrections_dict:
        print(f"Using learned correction for: {text}")  # Utiliser la correction apprise
        return corrections_dict[text]

    translator = GoogleTranslator(
        source=src_lang, target=dest_lang
    )  # Initialiser le traducteur
    try:
        return translator.translate(text)  # Traduire le texte
    except Exception as e:
        print(f"Translation error: {e}")  # Afficher l'erreur de traduction
        return text  # Retourner le texte original en cas d'erreur


# Fonction pour récupérer la couleur de fond derrière le texte
def get_background_color(image, box):
    box = [
        (int(coord[0]), int(coord[1])) for coord in box
    ]  # Convertir les coordonnées en entiers
    x1, y1 = box[0]  # Coin supérieur gauche
    x2, y2 = box[2]  # Coin inférieur droit
    extension = 10  # Extension pour le remplissage de couleur
    x1, y1 = max(0, x1 - extension), max(
        0, y1 - extension
    )  # Limiter les coordonnées à l'image
    x2, y2 = min(image.width, x2 + extension), min(image.height, y2 + extension)

    pixels = [
        image.getpixel((x, y)) for x in range(x1, x2) for y in range(y1, y2)
    ]  # Récupérer les pixels dans la zone
    pixel_counts = {}
    for color in pixels:
        if color not in pixel_counts:
            pixel_counts[color] = 0
        pixel_counts[color] += 1  # Compter les occurrences de chaque couleur

    most_common_color = max(
        pixel_counts, key=pixel_counts.get
    )  # Trouver la couleur la plus commune
    return most_common_color  # Retourner la couleur de fond la plus commune


# Fonction pour effacer le texte dans l'image
def erase_text(image, bounding_boxes):
    draw = ImageDraw.Draw(image)  # Créer un objet de dessin pour l'image
    for box in bounding_boxes:
        if isinstance(box, list):
            box = [tuple(point) for point in box]  # Convertir les coordonnées en tuples
        bg_color = get_background_color(image, box)  # Obtenir la couleur de fond
        draw.polygon(box, fill=bg_color)  # Dessiner un polygone avec la couleur de fond
    return image  # Retourner l'image modifiée


# Fonction pour ajuster la taille de la police en fonction de la boîte
def estimate_font_size(box, text):
    x1, y1 = box[0]  # Coin supérieur gauche
    x2, y2 = box[2]  # Coin inférieur droit
    box_height = y2 - y1  # Calculer la hauteur de la boîte
    base_font_size = max(
        int(box_height * 0.8), 8
    )  # Déterminer la taille de police de base

    font_path = "C:/Windows/Fonts/arial.ttf"  # Chemin vers la police
    font_size = base_font_size

    try:
        font = ImageFont.truetype(font_path, font_size)  # Charger la police
    except OSError:
        print(
            "Error: Unable to open font resource. Check the font path."
        )  # Gérer les erreurs de chargement de la police
        return None

    if text is None:
        print(
            "Warning: Translated text is None."
        )  # Avertir si le texte traduit est None
        return None

    # Ajuster la taille de la police jusqu'à ce qu'elle tienne dans la boîte
    while font.getbbox(text)[2] > (x2 - x1) and base_font_size > 8:
        base_font_size -= 1
        try:
            font = ImageFont.truetype(
                font_path, base_font_size
            )  # Réduire la taille de la police
        except OSError:
            font = (
                ImageFont.load_default()
            )  # Charger la police par défaut en cas d'erreur

    return font  # Retourner la police ajustée


# Fonction pour ajuster la couleur du texte en fonction de la couleur de fond
def adjust_text_color(bg_color):
    r, g, b = bg_color  # Décomposer la couleur de fond en ses composants RGB
    if (r * 0.299 + g * 0.587 + b * 0.114) < 128:  # Calculer la luminosité
        return (255, 255, 255)  # Retourner du blanc si le fond est sombre
    return (0, 0, 0)  # Retourner du noir sinon


# Fonction pour ajouter un contour au texte
def add_text_outline(draw, text, position, font, color, outline_color, outline_width=2):
    x, y = position  # Position du texte
    # Dessiner le contour autour du texte
    for offset in range(-outline_width, outline_width + 1):
        draw.text(
            (x + offset, y), text, font=font, fill=outline_color
        )  # Dessiner en haut et en bas
        draw.text(
            (x, y + offset), text, font=font, fill=outline_color
        )  # Dessiner à gauche et à droite
        draw.text(
            (x + offset, y + offset), text, font=font, fill=outline_color
        )  # Dessiner en diagonale
        draw.text((x + offset, y - offset), text, font=font, fill=outline_color)
        draw.text((x - offset, y + offset), text, font=font, fill=outline_color)
    draw.text((x, y), text, font=font, fill=color)  # Dessiner le texte principal


# Fonction pour récupérer les noms d'images dans un répertoire spécifié
def recuperer_noms_images(input_directory):
    image_names = []  # Liste pour stocker les noms des images

    # Utiliser os.walk pour parcourir les sous-répertoires
    for _, _, files in os.walk(input_directory):
        for file in files:
            if file.lower().endswith(
                (".png", ".jpg", ".jpeg")
            ):  # Vérifier les extensions d'image
                image_path = os.path.join(file)  # Chemin complet du fichier
                image_names.append(
                    image_path
                )  # Ajouter le chemin complet du fichier à la liste

    return image_names  # Retourner la liste des noms d'images


# Fonction pour gérer le passage au widget suivant lors de l'utilisation de la touche Tab
def on_tab(event):
    event.widget.tk_focusNext().focus()  # Passe le focus au widget suivant
    return "break"  # Empêche l'insertion d'une tabulation dans le widget


index_image = -1


def ouvrir_fenetre_par_lots(textes_traductions, batch_size=5):
    corrections = {}  # Dictionnaire pour stocker les corrections
    current_index = 0  # Index actuel pour suivre le lot de traductions affiché
    total_texts = len(textes_traductions)  # Nombre total de textes à traduire
    
    
  
    
    def submit_corrections(entries, traductions_proposees):
        nonlocal current_index
        global index_image
        for index, (texte_extrait, _) in enumerate(
            textes_traductions[current_index : current_index + batch_size]
        ):
            correction = (
                entries[index].get("1.0", tk.END).strip()
            )  # Récupérer le texte du widget Text
            if correction and correction != traductions_proposees[index]:
                corrections[texte_extrait] = correction
                save_corrections(corrections)
            else :
                corrections[texte_extrait] = traductions_proposees[index]

        # Passe au lot suivant
        current_index += batch_size
        afficher_fenetre()  # Affiche la nouvelle page
        
        
    
    def afficher_fenetre():
        nonlocal current_index
        global index_image
        # Supprime les widgets existants avant d'afficher la nouvelle page
        for widget in root.winfo_children():
            widget.destroy()

        # Quitte si tous les textes ont été traités
        if current_index >= total_texts:
            root.quit()
            return
        if current_index // batch_size == 0:
            index_image += 1  # Incrémente l'index de l'image à afficher

        # Initialisation de la fenêtre
        image_names = recuperer_noms_images("data_jp")  # Récupère les noms des images
        root.title(
            f"Image {index_image + 1}:  {image_names[index_image]}."
        )  # Définit le titre de la fenêtre
        root.configure(bg="#f0f0f0")  # Configure la couleur de fond de la fenêtre

        entries = []  # Liste pour stocker les champs de texte pour les corrections
        traductions_proposees = []  # Liste pour stocker les traductions proposées

        bold_font = font.Font(
            family="Arial", size=13, weight="bold"
        )  # Définit la police en gras

        # Boucle pour afficher les textes extraits et les traductions proposées
        for index, (texte_extrait, traduction_proposee) in enumerate(
            textes_traductions[current_index : current_index + batch_size]
        ):
            label_frame = tk.Frame(root)  # Crée un cadre pour chaque texte
            label_frame.pack(pady=(20, 10), padx=10)

            # Label pour le texte japonais
            label_texte = tk.Label(
                label_frame,
                text="Jap_Text: ",
                fg="#FFFFFF",
                bg="#A9A9A9",
                font=("Arial", 10),
            )
            label_texte.pack(side="left")

            # Affiche le texte extrait
            label_extrait = tk.Label(
                label_frame,
                text=texte_extrait,
                fg="#000000",
                bg="#D3F3D3",
                font=("Arial", 12),
                width=100,
                wraplength=800,
            )
            label_extrait.pack(side="left")

            # Crée un cadre pour la traduction
            frame_traduction = tk.Frame(root)
            frame_traduction.pack(pady=(0, 10), padx=10)

            # Label pour la traduction proposée
            label_traduction = tk.Label(
                frame_traduction,
                text="Translation: ",
                fg="#FFFFFF",
                bg="#A9A9A9",
                font=("Arial", 10),
            )
            label_traduction.pack(side="left")
            text_widget = tk.Text(
                frame_traduction, width=100, height=2, font=bold_font, wrap="word"
            )

            # Insère la traduction proposée dans le champ de texte
            text_widget.insert(tk.END, traduction_proposee)
            text_widget.pack(pady=(0, 10), padx=10)

            text_widget.bind(
                "<Tab>", on_tab
            )  # Lie la touche Tab pour passer au champ suivant
            entries.append(text_widget)  # Ajoute le champ de texte à la liste
            traductions_proposees.append(
                traduction_proposee
            )  # Ajoute la traduction proposée à la liste

        # Affiche la pagination
        page_number = f"Page {current_index // batch_size + 1} / {((total_texts - 1) // batch_size) + 1}"
        pagination_label = tk.Label(root, text=page_number, font=("Arial", 10))
        pagination_label.pack(pady=(0, 10))

        # Création d'un cadre pour les boutons de navigation
        navigation_frame = tk.Frame(root)
        navigation_frame.pack(pady=10)

        # Bouton "Previous" pour revenir au lot précédent
        previous_button = tk.Button(
            navigation_frame,
            text="Previous",
            command=lambda: navigate(-1),
            font=("Arial", 12),
        )
        previous_button.pack(side="left", padx=(0, 200), fill="x", expand=True)

        # Bouton de soumission pour enregistrer les corrections
        submit_button = tk.Button(
            navigation_frame,
            text="Submit correction",
            command=lambda: submit_corrections(entries, traductions_proposees),
            font=("Arial", 12),
        )
        submit_button.pack(side="left", padx=(200, 0), fill="x", expand=True)

        # Désactiver ou activer les boutons selon le contexte
        if current_index == 0:
            previous_button.config(
                state=tk.DISABLED
            )  # Désactive le bouton "Previous" si sur la première page

        # Lier les touches du clavier pour la soumission
        root.bind(
            "<Return>", lambda event: submit_corrections(entries, traductions_proposees)
        )

        root.mainloop()  # Démarre la boucle principale de l'interface graphique

    def navigate(direction):
        nonlocal current_index
        current_index += (
            direction * batch_size
        )  # Change le lot en fonction de la direction
        afficher_fenetre()  # Affiche la nouvelle fenêtre

    # Création de la fenêtre principale
    root = tk.Tk()
    root.geometry("1920x1080")  # Définit la taille de la fenêtre
    afficher_fenetre()  # Affiche la première fenêtre

    return (
        corrections if corrections else {}
    )  # Retourne les corrections si elles existent, sinon un dictionnaire vide


def manual_adjustments(text_and_boxes, batch_size=5):
    # Traduire chaque texte qui contient des caractères japonais
    textes_traductions = [
        (text, translate_text(text.strip()))
        for text, _ in text_and_boxes
        if contains_japanese(text)
    ]
    corrections = ouvrir_fenetre_par_lots(
        textes_traductions, batch_size=batch_size
    )  # Ouvre la fenêtre de corrections

    adjusted_translations = []
    # Boucle pour ajuster les traductions en fonction des corrections
    for text, box in text_and_boxes:
        if contains_japanese(text):
            translated_text = corrections.get(
                text, translate_text(text.strip()) if corrections else ""
            )
            adjusted_translations.append(
                (text, box, translated_text)
            )  # Ajoute le texte ajusté à la liste

    #save_corrections(corrections)  # Sauvegarde les corrections dans un fichier

    return adjusted_translations  # Retourne les traductions ajustées


# Fonction pour traiter les images avec ajustements
def process_images_with_adjustments(
    input_image_path, output_image_path, adjusted_translations
):
    # Vérifie si le chemin du fichier d'entrée est valide
    if not os.path.isfile(input_image_path):
        raise FileNotFoundError(f"The file {input_image_path} does not exist.")

    # Ouvre l'image d'entrée et la convertit en mode RGB
    image = Image.open(input_image_path).convert("RGB")

    # Efface le texte aux emplacements spécifiés dans adjusted_translations
    image = erase_text(image, [box for _, box, _ in adjusted_translations])

    # Crée un objet de dessin pour ajouter du texte à l'image
    draw = ImageDraw.Draw(image)

    # Parcourt chaque traduction ajustée pour dessiner le texte sur l'image
    for _, box, translated_text in adjusted_translations:
        # Récupère la couleur de fond à l'emplacement du texte
        bg_color = get_background_color(image, box)
        # Ajuste la couleur du texte pour qu'il soit lisible sur le fond
        text_color = adjust_text_color(bg_color)
        # Estime la taille de la police pour le texte traduit
        font = estimate_font_size(box, translated_text)

        # Ignore si la taille de la police n'a pas pu être déterminée
        if font is None:
            continue

        # Si la couleur de fond est noire, ajoute une bordure blanche autour du texte
        if bg_color == (0, 0, 0):
            add_text_outline(
                draw,
                translated_text,
                (box[0][0], box[0][1]),
                font,
                text_color,
                (255, 255, 255),  # Couleur de la bordure (blanc)
            )
        else:
            # Dessine le texte traduit sur l'image à la position spécifiée
            draw.text(
                (box[0][0], box[0][1]), translated_text, font=font, fill=text_color
            )

    # Sauvegarde l'image traitée à l'emplacement de sortie spécifié
    image.save(output_image_path)

#======================================MAIN=========================================
# Répertoires d'entrée et de sortie
input_directory = Path("data_jp")  # Dossier contenant les images en japonais
output_directory = Path("data_en")  # Dossier pour les images traduites en anglais

# S'assurer que le répertoire de sortie existe, le crée si nécessaire
output_directory.mkdir(exist_ok=True)

# Traiter chaque fichier image dans le répertoire d'entrée
for subdir, _, files in os.walk(
    input_directory
):  # Parcourt les sous-dossiers du dossier d'entrée
    for file in files:
        # Vérifie si le fichier est une image (png, jpg, jpeg)
        if file.lower().endswith((".png", ".jpg", ".jpeg")):
            input_image_path = Path(subdir) / file  # Chemin complet de l'image d'entrée
            # Crée le chemin du sous-dossier de sortie correspondant
            output_subdir = output_directory / Path(subdir).relative_to(input_directory)
            # Crée le sous-dossier de sortie si nécessaire
            output_subdir.mkdir(parents=True, exist_ok=True)
            output_image_path = (
                output_subdir / file
            )  # Chemin complet de l'image de sortie

            # Extrait le texte et les emplacements de l'image d'entrée
            text_and_boxes = extract_text_from_image(input_image_path)
            # Ajuste les traductions du texte extrait
            adjusted_translations = manual_adjustments(text_and_boxes)
            # Traite l'image avec les ajustements de texte
            process_images_with_adjustments(
                input_image_path, output_image_path, adjusted_translations
            )
