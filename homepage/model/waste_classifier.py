import base64
import io
import cv2
import numpy as np
from PIL import Image
from ultralytics import YOLO

COCO_TO_SPANISH = {
    'bottle': 'Botella', 'wine glass': 'Copa', 'cup': 'Taza',
    'fork': 'Tenedor', 'knife': 'Cuchillo', 'spoon': 'Cuchara',
    'bowl': 'Tazón', 'book': 'Libro', 'cell phone': 'Celular',
    'laptop': 'Portátil', 'remote': 'Control remoto', 'keyboard': 'Teclado',
    'tv': 'TV', 'mouse': 'Ratón', 'scissors': 'Tijeras',
    'vase': 'Florero', 'clock': 'Reloj', 'teddy bear': 'Peluche',
    'apple': 'Manzana', 'banana': 'Banano', 'orange': 'Naranja',
    'broccoli': 'Brócoli', 'carrot': 'Zanahoria', 'sandwich': 'Sándwich',
    'hot dog': 'Perro caliente', 'pizza': 'Pizza', 'donut': 'Dona',
    'cake': 'Pastel', 'potted plant': 'Planta',
    'chair': 'Silla', 'couch': 'Sofá', 'bed': 'Cama',
    'toilet': 'Inodoro', 'toothbrush': 'Cepillo dental',
    'hair drier': 'Secador', 'backpack': 'Mochila',
    'handbag': 'Bolso', 'suitcase': 'Maleta',
    'frisbee': 'Disco volador', 'skateboard': 'Patineta',
    'sports ball': 'Pelota deportiva', 'baseball glove': 'Guante de béisbol',
    'umbrella': 'Sombrilla', 'tie': 'Corbata',
    'dining table': 'Mesa', 'tennis racket': 'Raqueta de tenis',
}

WASTE_MAP = {
    'bottle': 'aprovechable', 'wine glass': 'aprovechable', 'cup': 'aprovechable',
    'fork': 'aprovechable', 'knife': 'aprovechable', 'spoon': 'aprovechable',
    'bowl': 'aprovechable', 'book': 'aprovechable', 'cell phone': 'aprovechable',
    'laptop': 'aprovechable', 'remote': 'aprovechable', 'keyboard': 'aprovechable',
    'tv': 'aprovechable', 'mouse': 'aprovechable', 'scissors': 'aprovechable',
    'vase': 'aprovechable', 'clock': 'aprovechable', 'teddy bear': 'aprovechable',

    'apple': 'organico', 'banana': 'organico', 'orange': 'organico',
    'broccoli': 'organico', 'carrot': 'organico', 'sandwich': 'organico',
    'hot dog': 'organico', 'pizza': 'organico', 'donut': 'organico',
    'cake': 'organico', 'potted plant': 'organico',

    'chair': 'no_aprovechable', 'couch': 'no_aprovechable', 'bed': 'no_aprovechable',
    'toilet': 'no_aprovechable', 'toothbrush': 'no_aprovechable',
    'hair drier': 'no_aprovechable', 'backpack': 'no_aprovechable',
    'handbag': 'no_aprovechable', 'suitcase': 'no_aprovechable',
    'frisbee': 'no_aprovechable', 'skateboard': 'no_aprovechable',
    'sports ball': 'no_aprovechable', 'baseball glove': 'no_aprovechable',
    'umbrella': 'no_aprovechable', 'tie': 'no_aprovechable',
    'dining table': 'no_aprovechable', 'tennis racket': 'no_aprovechable',
}

CATEGORY_INFO = {
    'aprovechable': {'label': 'Aprovechable', 'color': (34, 197, 94), 'icon': '\u267b', 'desc': 'Papel, pl\u00e1stico, vidrio, metal'},
    'no_aprovechable': {'label': 'No aprovechable', 'color': (239, 68, 68), 'icon': '\u26d4', 'desc': 'Residuos contaminados o no reciclables'},
    'organico': {'label': 'Org\u00e1nico', 'color': (59, 130, 246), 'icon': '\u2618', 'desc': 'Residuos de comida y vegetales'},
}

DEFAULT_CATEGORY = 'no_aprovechable'
PERSON_CLASS = 'person'
CATEGORY_COLORS_HEX = {
    'aprovechable': '#22c55e',
    'no_aprovechable': '#ef4444',
    'organico': '#3b82f6',
    'person': '#a855f7',
}


class WasteClassifier:
    def __init__(self, model_path='yolov8m.pt'):
        self.model = YOLO(model_path)
        from model.container_detector import detect_containers, validate_disposal
        self._detect_containers = detect_containers
        self._validate_disposal = validate_disposal
        self._img_width = None
        self._img_height = None

    def classify(self, image_bytes):
        image = Image.open(io.BytesIO(image_bytes))
        results = self.model(image)[0]
        self._img_width, self._img_height = image.size

        detections = []
        categories_count = {'aprovechable': 0, 'no_aprovechable': 0, 'organico': 0}

        if len(results.boxes) == 0:
            return {
                'detections': [],
                'categories_count': categories_count,
                'main_category': None,
                'annotated_image': None,
            }

        annotated_frame = results.plot()
        for box in results.boxes:
            cls_id = int(box.cls[0])
            cls_name = results.names[cls_id]
            if cls_name == PERSON_CLASS:
                continue
            confidence = float(box.conf[0])
            x1, y1, x2, y2 = map(int, box.xyxy[0].tolist())

            category = WASTE_MAP.get(cls_name, DEFAULT_CATEGORY)
            categories_count[category] += 1

            detections.append({
                'class': COCO_TO_SPANISH.get(cls_name, cls_name),
                'confidence': round(confidence, 2),
                'category': category,
                'category_label': CATEGORY_INFO[category]['label'],
                'bbox': [x1, y1, x2, y2],
            })

        main_category = max(categories_count, key=categories_count.get)
        if categories_count[main_category] == 0:
            main_category = None

        _, buffer = cv2.imencode('.jpg', annotated_frame)
        annotated_b64 = base64.b64encode(buffer).decode('utf-8')

        return {
            'detections': detections,
            'categories_count': categories_count,
            'main_category': main_category,
            'annotated_image': annotated_b64,
        }

    def detect(self, image_bytes):
        image = Image.open(io.BytesIO(image_bytes))
        results = self.model(image)[0]
        self._img_width, self._img_height = image.size

        waste_items = []
        persons = []
        categories_count = {'aprovechable': 0, 'no_aprovechable': 0, 'organico': 0}

        for box in results.boxes:
            cls_id = int(box.cls[0])
            cls_name = results.names[cls_id]
            confidence = float(box.conf[0])
            x1, y1, x2, y2 = map(int, box.xyxy[0].tolist())

            cls_spanish = COCO_TO_SPANISH.get(cls_name, cls_name)
            item = {
                'class': cls_spanish,
                'confidence': round(confidence, 2),
                'bbox': [x1, y1, x2, y2],
            }

            if cls_name == PERSON_CLASS:
                persons.append(item)
            else:
                category = WASTE_MAP.get(cls_name, DEFAULT_CATEGORY)
                categories_count[category] += 1
                item['category'] = category
                item['category_label'] = CATEGORY_INFO[category]['label']
                waste_items.append(item)

        main_category = max(categories_count, key=categories_count.get)
        if categories_count[main_category] == 0:
            main_category = None

        return {
            'waste_items': waste_items,
            'persons': persons,
            'total_persons': len(persons),
            'categories_count': categories_count,
            'main_category': main_category,
            'img_width': self._img_width,
            'img_height': self._img_height,
        }

    def detect_with_container(self, image_bytes):
        import numpy as np
        image = Image.open(io.BytesIO(image_bytes))
        img_cv = cv2.cvtColor(np.array(image), cv2.COLOR_RGB2BGR)
        results = self.model(image)[0]
        self._img_width, self._img_height = image.size

        waste_items = []
        persons = []
        categories_count = {'aprovechable': 0, 'no_aprovechable': 0, 'organico': 0}

        for box in results.boxes:
            cls_id = int(box.cls[0])
            cls_name = results.names[cls_id]
            confidence = float(box.conf[0])
            x1, y1, x2, y2 = map(int, box.xyxy[0].tolist())

            cls_spanish = COCO_TO_SPANISH.get(cls_name, cls_name)
            item = {
                'class': cls_spanish,
                'confidence': round(confidence, 2),
                'bbox': [x1, y1, x2, y2],
            }

            if cls_name == PERSON_CLASS:
                persons.append(item)
            else:
                category = WASTE_MAP.get(cls_name, DEFAULT_CATEGORY)
                categories_count[category] += 1
                item['category'] = category
                item['category_label'] = CATEGORY_INFO[category]['label']
                waste_items.append(item)

        main_category = max(categories_count, key=categories_count.get)
        if categories_count[main_category] == 0:
            main_category = None

        containers = self._detect_containers(img_cv)
        validation = self._validate_disposal(
            waste_items, containers, persons,
            self._img_width, self._img_height,
        )

        return {
            'waste_items': waste_items,
            'persons': persons,
            'total_persons': len(persons),
            'containers': containers,
            'validation': validation,
            'categories_count': categories_count,
            'main_category': main_category,
            'img_width': self._img_width,
            'img_height': self._img_height,
        }
