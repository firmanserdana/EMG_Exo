import os
import glob
import cv2
import easyocr
import numpy as np

# --- CONFIGURATION ---
INPUT_DIRECTORY = "stopwatch_screenshots"
OUTPUT_FILE = "raw_ocr_output.txt"
# --- END CONFIGURATION ---

def robust_cv_read(image_path: str) -> np.ndarray | None:
    """
    Uses np.fromfile and cv2.imdecode to read images with
    potential special characters in the path (common on Windows).
    """
    try:
        n = np.fromfile(image_path, np.uint8)
        image = cv2.imdecode(n, cv2.IMREAD_COLOR)
        if image is None:
            print(f"Warning: 'cv2.imdecode' returned None for {image_path}. File might be corrupt.")
        return image
    except Exception as e:
        print(f"Error reading file {image_path} with robust_cv_read: {e}")
        return None

def preprocess_for_ocr(image: np.ndarray) -> np.ndarray | None:
    """
    Applies pre-processing steps: grayscale and binary threshold.
    """
    if image is None or image.size == 0:
        return None
        
    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    # Apply binary thresholding (inverts white-on-black text)
    _, binarized = cv2.threshold(gray, 127, 255, cv2.THRESH_BINARY_INV)
    return binarized

def main():
    print("Initializing EasyOCR... (This may take a moment)")
    # Using CPU mode for maximum compatibility across different hardware.
    reader = easyocr.Reader(['en'], gpu=False)
    print("EasyOCR initialized.")

    print(f"Scanning '{INPUT_DIRECTORY}' for images...")
    image_paths = glob.glob(os.path.join(INPUT_DIRECTORY, '*.png')) + \
                  glob.glob(os.path.join(INPUT_DIRECTORY, '*.jpg')) + \
                  glob.glob(os.path.join(INPUT_DIRECTORY, '*.jpeg'))

    if not image_paths:
        print(f"Error: No images found in '{INPUT_DIRECTORY}'.")
        return

    print(f"Found {len(image_paths)} images. Starting OCR extraction...")
    
    # 'w' mode to clear the file on each new run
    with open(OUTPUT_FILE, 'w', encoding='utf-8') as f:
        pass # Just to clear the file

    for i, image_path in enumerate(image_paths):
        basename = os.path.basename(image_path)
        print(f"  Processing file {i+1}/{len(image_paths)}: {basename}")
        
        try:
            image = robust_cv_read(image_path)
            if image is None:
                print(f"    Warning: Could not read image. Skipping.")
                continue

            processed_image = preprocess_for_ocr(image)
            if processed_image is None:
                print(f"    Warning: Preprocessing failed. Skipping.")
                continue
                
            # Run OCR on the *full* image.
            # paragraph=True joins nearby text into blocks, which is good.
            text_blocks = reader.readtext(processed_image, detail=0, paragraph=True)
            
            # 'a' mode to append results for each file
            with open(OUTPUT_FILE, 'a', encoding='utf-8') as f:
                f.write(f"--- START: {basename} ---\n")
                if not text_blocks:
                    f.write("[NO TEXT DETECTED]\n")
                for block in text_blocks:
                    f.write(f"{block}\n")
                f.write(f"--- END: {basename} ---\n\n")

        except Exception as e:
            print(f"    ERROR processing {basename}: {e}")
            
    print(f"\n--- Extraction Complete ---")
    print(f"All extracted text has been saved to '{OUTPUT_FILE}'.")
    print("Please review the file, then run 'step2_parse_raw_text.py'.")

if __name__ == "__main__":
    main()
