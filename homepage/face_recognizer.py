# @ Con fines académicos
# por KarolyMaira

import os, json, io
import numpy as np
from PIL import Image
import onnxruntime as ort

_BASE = os.path.dirname(os.path.abspath(__file__))
_PARENT = os.path.dirname(_BASE)
MODEL_PATH = os.path.join(_PARENT, 'mobilenetv2-7.onnx')
if not os.path.exists(MODEL_PATH):
    MODEL_PATH = os.path.join(_BASE, 'mobilenetv2-7.onnx')
EMBEDDINGS_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'data', 'face_embeddings.json')
FACE_DATASET_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'static', 'face_dataset')
INPUT_SIZE = 224
SIMILARITY_THRESHOLD = 0.5

_session = None
_embeddings = None

def _get_session():
    global _session
    if _session is None:
        if not os.path.exists(MODEL_PATH):
            return None
        _session = ort.InferenceSession(MODEL_PATH)
    return _session

def _preprocess(image):
    img = image.convert('RGB')
    img = img.resize((INPUT_SIZE, INPUT_SIZE), Image.LANCZOS)
    arr = np.array(img, dtype=np.float32)
    mean = np.array([123.675, 116.28, 103.53], dtype=np.float32)
    std = np.array([58.395, 57.12, 57.375], dtype=np.float32)
    arr = (arr - mean) / std
    arr = np.transpose(arr, (2, 0, 1))
    arr = np.expand_dims(arr, axis=0)
    return arr

def extract_embedding(image):
    session = _get_session()
    if session is None:
        return None
    input_tensor = _preprocess(image)
    output = session.run(None, {'data': input_tensor})[0]
    emb = output.flatten()
    norm = np.linalg.norm(emb)
    if norm > 0:
        emb = emb / norm
    return emb

def _load_embeddings():
    global _embeddings
    if _embeddings is not None:
        return _embeddings
    if not os.path.exists(EMBEDDINGS_PATH):
        _embeddings = {}
        return _embeddings
    with open(EMBEDDINGS_PATH, 'r') as f:
        data = json.load(f)
    _embeddings = {doc: [np.array(e, dtype=np.float32) for e in embs] for doc, embs in data.items()}
    return _embeddings

def _save_embeddings(emb_dict):
    data = {doc: [e.tolist() for e in embs] for doc, embs in emb_dict.items()}
    os.makedirs(os.path.dirname(EMBEDDINGS_PATH), exist_ok=True)
    with open(EMBEDDINGS_PATH, 'w') as f:
        json.dump(data, f)

def recognize(image):
    emb = extract_embedding(image)
    if emb is None:
        return None, 0.0
    embeddings = _load_embeddings()
    if not embeddings:
        return None, 0.0
    best_doc = None
    best_sim = -1.0
    for doc, doc_embs in embeddings.items():
        for stored_emb in doc_embs:
            sim = float(np.dot(emb, stored_emb))
            if sim > best_sim:
                best_sim = sim
                best_doc = doc
    if best_sim >= SIMILARITY_THRESHOLD:
        return best_doc, best_sim
    return None, best_sim

def retrain():
    if not os.path.exists(FACE_DATASET_DIR):
        return {'error': 'face_dataset directory not found'}
    embeddings = {}
    for item in os.listdir(FACE_DATASET_DIR):
        doc_dir = os.path.join(FACE_DATASET_DIR, item)
        if not os.path.isdir(doc_dir):
            continue
        doc_embs = []
        for fname in sorted(os.listdir(doc_dir)):
            if not fname.lower().endswith(('.jpg', '.jpeg', '.png')):
                continue
            fpath = os.path.join(doc_dir, fname)
            try:
                img = Image.open(fpath)
                emb = extract_embedding(img)
                if emb is not None:
                    doc_embs.append(emb)
            except Exception as e:
                print(f'Error processing {fpath}: {e}')
        if doc_embs:
            embeddings[item] = doc_embs
    _save_embeddings(embeddings)
    total = sum(len(v) for v in embeddings.values())
    return {'ok': True, 'users': len(embeddings), 'photos': total}

def is_available():
    session = _get_session()
    if session is None:
        return False
    embeddings = _load_embeddings()
    return len(embeddings) > 0

if __name__ == '__main__':
    result = retrain()
    print(json.dumps(result, indent=2))
