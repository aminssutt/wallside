"""Batch download vehicle images: official sites -> Wikipedia -> fallback. With U2Net bg removal."""
import sys, os, time
import numpy as np
from PIL import Image
import onnxruntime as ort
from playwright.sync_api import sync_playwright
from io import BytesIO
from pathlib import Path

MODEL_PATH = os.path.join(os.environ.get("USERPROFILE", "."), ".u2net", "u2net.onnx")
session = ort.InferenceSession(MODEL_PATH, providers=["CPUExecutionProvider"])
INPUT_NAME = session.get_inputs()[0].name
OUT = Path(__file__).parent / "data" / "vehicle_images"


def remove_bg_save(img_bytes, output_path):
    img = Image.open(BytesIO(img_bytes)).convert("RGB")
    w, h = img.size
    resized = img.resize((320, 320), Image.LANCZOS)
    arr = np.array(resized, dtype=np.float32) / 255.0
    arr = (arr - [0.485, 0.456, 0.406]) / [0.229, 0.224, 0.225]
    arr = arr.transpose(2, 0, 1)[np.newaxis, :].astype(np.float32)
    result = session.run(None, {INPUT_NAME: arr})[0][0, 0]
    result = ((result - result.min()) / (result.max() - result.min() + 1e-8) * 255).astype(np.uint8)
    mask = Image.fromarray(result).resize((w, h), Image.LANCZOS)
    rgba = img.convert("RGBA")
    rgba.putalpha(mask)
    bbox = rgba.getbbox()
    if bbox:
        rgba = rgba.crop(bbox)
    if rgba.size[0] > 1400:
        rgba = rgba.resize((1400, int(1400 * rgba.size[1] / rgba.size[0])), Image.LANCZOS)
    rgba.save(str(output_path), "PNG", optimize=True)
    return rgba.size


def try_official(ctx, brand, model_name, filename):
    """Try official manufacturer sites for press photos."""
    OFFICIAL_URLS = {
        "Toyota": "https://www.toyota.fr/new-cars/{model}",
        "BMW": "https://www.bmw.fr/fr/tous-les-modeles/{model}.html",
        "Mercedes": "https://www.mercedes-benz.fr/passengercars/models/{model}.html",
        "Ford": "https://www.ford.fr/voitures/{model}",
        "Volvo": "https://www.volvocars.com/fr/cars/{model}/",
        "Fiat": "https://www.fiat.fr/modeles/{model}",
        "Opel": "https://www.opel.fr/vehicules/{model}.html",
        "Nissan": "https://www.nissan.fr/vehicules/{model}.html",
        "Mazda": "https://www.mazda.fr/voitures/{model}/",
        "Cupra": "https://www.cupraofficial.fr/modeles/{model}.html",
        "Renault": "https://www.renault.fr/vehicules/{model}.html",
        "Volkswagen": "https://www.volkswagen.fr/fr/modeles/{model}.html",
    }
    template = OFFICIAL_URLS.get(brand)
    if not template:
        return False

    # Normalize model name for URL
    model_key = model_name.lower().split("(")[0].strip()
    model_key = model_key.replace(brand.lower(), "").strip()
    model_key = model_key.replace(" ", "-").replace("é", "e")

    url = template.format(model=model_key)
    try:
        page = ctx.new_page()
        page.goto(url, wait_until="domcontentloaded", timeout=8000)
        time.sleep(2)
        # Find largest car image
        imgs = page.eval_on_selector_all(
            "img[src]",
            """els => els.map(e => ({src: e.src, w: e.naturalWidth || e.width}))
            .filter(i => i.w > 400 && (i.src.includes('.jpg') || i.src.includes('.png') || i.src.includes('.webp')))
            .sort((a,b) => b.w - a.w)""",
        )
        page.close()
        if imgs:
            resp = ctx.request.get(imgs[0]["src"], timeout=8000)
            if resp.ok and len(resp.body()) > 20000:
                size = remove_bg_save(resp.body(), OUT / filename)
                return size
    except Exception:
        pass
    return False


def try_wikipedia(ctx, wiki_page, filename):
    """Try Wikipedia infobox image."""
    try:
        page = ctx.new_page()
        page.goto(f"https://en.wikipedia.org/wiki/{wiki_page}", wait_until="domcontentloaded", timeout=10000)
        time.sleep(1)
        imgs = page.eval_on_selector_all(
            ".infobox img, .thumb img",
            'els => els.map(e => e.src).filter(s => s.includes("upload.wikimedia") && !s.includes("svg"))',
        )
        page.close()
        if not imgs:
            return False
        for src in imgs[:3]:
            if "/thumb/" in src:
                src = src.replace("/thumb/", "/").rsplit("/", 1)[0]
            fname = src.split("/")[-1]
            parts = src.split("/commons/")[-1]
            thumb = f"https://upload.wikimedia.org/wikipedia/commons/thumb/{parts}/1280px-{fname}"
            time.sleep(1)
            resp = ctx.request.get(thumb, timeout=10000)
            if resp.ok and len(resp.body()) > 15000:
                size = remove_bg_save(resp.body(), OUT / filename)
                return size
    except Exception:
        pass
    return False


VEHICLES = [
    # (filename, brand, display_name, wiki_page)
    ("renault megane e-tech.png", "Renault", "Renault Megane E-Tech", "Renault_M%C3%A9gane_E-Tech_Electric"),
    ("renault scenic e-tech.png", "Renault", "Renault Scenic E-Tech", "Renault_Sc%C3%A9nic#Fifth_generation"),
    ("volkswagen golf 6.png", "Volkswagen", "VW Golf 6", "Volkswagen_Golf_Mk6"),
    ("toyota yaris.png", "Toyota", "Toyota Yaris", "Toyota_Yaris#Fourth_generation"),
    ("toyota yaris cross.png", "Toyota", "Toyota Yaris Cross", "Toyota_Yaris_Cross"),
    ("toyota corolla.png", "Toyota", "Toyota Corolla", "Toyota_Corolla_(E210)"),
    ("toyota aygo x.png", "Toyota", "Toyota Aygo X", "Toyota_Aygo_X"),
    ("toyota camry.png", "Toyota", "Toyota Camry", "Toyota_Camry_(XV70)"),
    ("bmw serie 5.png", "BMW", "BMW Serie 5", "BMW_5_Series_(G60)"),
    ("bmw x1.png", "BMW", "BMW X1", "BMW_X1_(U11)"),
    ("bmw x3.png", "BMW", "BMW X3", "BMW_X3_(G01)"),
    ("bmw x5.png", "BMW", "BMW X5", "BMW_X5_(G05)"),
    ("bmw ix.png", "BMW", "BMW iX", "BMW_iX"),
    ("bmw i4.png", "BMW", "BMW i4", "BMW_i4"),
    ("mercedes classe a.png", "Mercedes", "Mercedes Classe A", "Mercedes-Benz_A-Class_(W177)"),
    ("mercedes classe b.png", "Mercedes", "Mercedes Classe B", "Mercedes-Benz_B-Class#Third_generation_(W247;_2019)"),
    ("mercedes classe e.png", "Mercedes", "Mercedes Classe E", "Mercedes-Benz_E-Class_(W214)"),
    ("ford puma.png", "Ford", "Ford Puma", "Ford_Puma_(crossover)"),
    ("ford focus.png", "Ford", "Ford Focus", "Ford_Focus_(fourth_generation)"),
    ("ford fiesta.png", "Ford", "Ford Fiesta", "Ford_Fiesta#Seventh_generation_(2017)"),
    ("volvo xc40.png", "Volvo", "Volvo XC40", "Volvo_XC40"),
    ("volvo xc60.png", "Volvo", "Volvo XC60", "Volvo_XC60#Second_generation_(SPA;_2017)"),
    ("volvo xc90.png", "Volvo", "Volvo XC90", "Volvo_XC90#Second_generation_(SPA;_2014)"),
    ("volvo v60.png", "Volvo", "Volvo V60", "Volvo_V60#Second_generation_(Z)"),
    ("volvo s60.png", "Volvo", "Volvo S60", "Volvo_S60#Third_generation_(Z)"),
    ("fiat 500.png", "Fiat", "Fiat 500", "Fiat_New_500"),
    ("fiat 500x.png", "Fiat", "Fiat 500X", "Fiat_500X"),
    ("fiat tipo.png", "Fiat", "Fiat Tipo", "Fiat_Tipo_(2015)"),
    ("fiat panda.png", "Fiat", "Fiat Panda", "Fiat_Panda_(2012)"),
    ("opel corsa.png", "Opel", "Opel Corsa", "Opel_Corsa#Corsa_F_(2019)"),
    ("opel astra.png", "Opel", "Opel Astra", "Opel_Astra#Astra_L_(2021)"),
    ("opel mokka.png", "Opel", "Opel Mokka", "Opel_Mokka#Second_generation_(2020)"),
    ("opel crossland.png", "Opel", "Opel Crossland", "Opel_Crossland_X"),
    ("nissan qashqai.png", "Nissan", "Nissan Qashqai", "Nissan_Qashqai#Third_generation_(J12;_2021)"),
    ("nissan juke.png", "Nissan", "Nissan Juke", "Nissan_Juke#Second_generation_(F16;_2019)"),
    ("nissan leaf.png", "Nissan", "Nissan Leaf", "Nissan_Leaf#Second_generation_(ZE1;_2017)"),
    ("mazda cx-5.png", "Mazda", "Mazda CX-5", "Mazda_CX-5#Second_generation_(KF;_2017)"),
    ("mazda 3.png", "Mazda", "Mazda 3", "Mazda3#Fourth_generation_(BP;_2019)"),
    ("cupra formentor.png", "Cupra", "Cupra Formentor", "Cupra_Formentor"),
]


if __name__ == "__main__":
    print(f"Processing {len(VEHICLES)} vehicle images\n")
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        ctx = browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
        )

        ok = fail = 0
        for filename, brand, name, wiki in VEHICLES:
            print(f"  {name:35s} ", end="", flush=True)

            # Strategy 1: Official site
            size = try_official(ctx, brand, name, filename)
            if size:
                print(f"OFFICIAL ({size[0]}x{size[1]})")
                ok += 1
                continue

            # Strategy 2: Wikipedia
            time.sleep(1)
            size = try_wikipedia(ctx, wiki, filename)
            if size:
                print(f"WIKI ({size[0]}x{size[1]})")
                ok += 1
                continue

            print("FAILED")
            fail += 1

        browser.close()
    print(f"\nDone! OK: {ok}, Failed: {fail}")
