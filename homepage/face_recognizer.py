import os, json
import numpy as np
from PIL import Image
from insightface.app import FaceAnalysis

EMBEDDINGS_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'data', 'face_embeddings.json')
FACE_DATASET_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'static', 'face_dataset')
SIMILARITY_THRESHOLD = 0.5

_app = None
_embeddings_cache = None

def _get_app():
    global _app
    if _app is None:
        _app = FaceAnalysis(name='buffalo_l', root='~/.insightface', providers=['CPUExecutionProvider'])
        _app.prepare(ctx_id=0, det_size=(640, 640))
    return _app

def _get_embedding(image):
    app = _get_app()
    img = np.array(image.convert('RGB'))
    faces = app.get(img)
    if not faces:
        return None
    return faces[0].normed_embedding

def _load_embeddings():
    global _embeddings_cache
    if _embeddings_cache is not None:
        return _embeddings_cache
    if os.path.exists(EMBEDDINGS_PATH):
        with open(EMBEDDINGS_PATH, 'r') as f:
            _embeddings_cache = json.load(f)
    else:
        _embeddings_cache = []
    return _embeddings_cache

def _save_embeddings(data):
    os.makedirs(os.path.dirname(EMBEDDINGS_PATH), exist_ok=True)
    with open(EMBEDDINGS_PATH, 'w') as f:
        json.dump(data, f)
    global _embeddings_cache
    _embeddings_cache = data

def extract_embedding(image):
    emb = _get_embedding(image)
    if emb is None:
        return None
    return emb.tolist()

def recognize(image):
    emb = _get_embedding(image)
    if emb is None:
        return None, 0.0
    stored = _load_embeddings()
    if not stored:
        return None, 0.0
    best_doc = None
    best_sim = 0.0
    for entry in stored:
        stored_emb = np.array(entry['embedding'])
        sim = float(np.dot(emb, stored_emb))
        if sim > best_sim:
            best_sim = sim
            best_doc = entry['document']
    if best_sim >= SIMILARITY_THRESHOLD:
        return best_doc, best_sim
    return None, best_sim

def retrain():
    if not os.path.exists(FACE_DATASET_DIR):
        return {'error': 'face_dataset directory not found'}
    data = []
    for item in sorted(os.listdir(FACE_DATASET_DIR)):
        doc_dir = os.path.join(FACE_DATASET_DIR, item)
        if not os.path.isdir(doc_dir):
            continue
        for fname in sorted(os.listdir(doc_dir)):
            if not fname.lower().endswith(('.jpg', '.jpeg', '.png')):
                continue
            fpath = os.path.join(doc_dir, fname)
            try:
                img = Image.open(fpath).convert('RGB')
                emb = _get_embedding(img)
                if emb is not None:
                    data.append({'document': item, 'embedding': emb.tolist()})
            except Exception as e:
                print(f'Error processing {fpath}: {e}')
    if not data:
        return {'ok': False, 'error': 'No se pudieron extraer embeddings de ninguna foto'}
    _save_embeddings(data)
    users = len(set(e['document'] for e in data))
    return {'ok': True, 'users': users, 'photos': len(data)}

def is_available():
    try:
        _get_app()
        return len(_load_embeddings()) > 0
    except Exception:
        return False

if __name__ == '__main__':
    result = retrain()
    print(json.dumps(result, indent=2))
