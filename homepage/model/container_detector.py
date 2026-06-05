import cv2
import numpy as np

CONTAINER_COLORS = {
    'verde': {
        'label': 'Caneca verde',
        'expected_category': 'organico',
        'icon': '\U0001F7E2',
        'hsv_ranges': [
            (np.array([35, 40, 40]), np.array([90, 255, 220])),
        ],
    },
    'blanca': {
        'label': 'Caneca blanca',
        'expected_category': 'aprovechable',
        'icon': '\u2B1C',
        'hsv_ranges': [
            (np.array([0, 0, 140]), np.array([180, 50, 255])),
        ],
    },
    'negra': {
        'label': 'Caneca negra',
        'expected_category': 'no_aprovechable',
        'icon': '\u2B1B',
        'hsv_ranges': [
            (np.array([0, 0, 0]), np.array([180, 255, 70])),
        ],
    },
}

MAX_CONTAINERS = 2


def detect_containers(image_cv):
    hsv = cv2.cvtColor(image_cv, cv2.COLOR_BGR2HSV)
    h, w = image_cv.shape[:2]
    img_area = h * w
    min_area = int(img_area * 0.02)
    detected = []

    for color_name, config in CONTAINER_COLORS.items():
        mask = None
        for lower, upper in config['hsv_ranges']:
            cur = cv2.inRange(hsv, lower, upper)
            mask = cur if mask is None else cv2.bitwise_or(mask, cur)

        kernel = np.ones((7, 7), np.uint8)
        mask = cv2.morphologyEx(mask, cv2.MORPH_OPEN, kernel)
        mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, kernel)

        contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

        for cnt in contours:
            area = cv2.contourArea(cnt)
            if area < min_area:
                continue

            x, y, cw, ch = cv2.boundingRect(cnt)
            rect_area = cw * ch
            if rect_area == 0:
                continue

            solidity = area / rect_area
            if solidity < 0.2:
                continue

            aspect_ratio = ch / max(cw, 1)
            if aspect_ratio < 0.5 or aspect_ratio > 5.0:
                continue

            confidence = min(1.0, area / (img_area * 0.15))

            detected.append({
                'color': color_name,
                'label': config['label'],
                'expected_category': config['expected_category'],
                'icon': config['icon'],
                'bbox': [x, y, x + cw, y + ch],
                'area': int(area),
                'confidence': round(confidence, 2),
            })

    detected.sort(key=lambda d: d['confidence'], reverse=True)
    return detected[:MAX_CONTAINERS]


def is_person_near_container(person_bbox, container_bbox, img_w, img_h):
    px1, py1, px2, py2 = person_bbox
    cx1, cy1, cx2, cy2 = container_bbox

    p_center_x = (px1 + px2) // 2
    p_center_y = (py1 + py2) // 2

    margin = int(0.4 * img_w)

    expanded_cx1 = max(0, cx1 - margin)
    expanded_cy1 = max(0, cy1 - margin)
    expanded_cx2 = min(img_w, cx2 + margin)
    expanded_cy2 = min(img_h, cy2 + margin)

    return (expanded_cx1 <= p_center_x <= expanded_cx2 and
            expanded_cy1 <= p_center_y <= expanded_cy2)


def validate_disposal(waste_items, containers, persons, img_w, img_h):
    results = []
    overall_valid = True

    if not persons or not waste_items or not containers:
        return {
            'valid': None,
            'message': 'No hay suficiente informaci\u00f3n para validar',
            'checks': [],
        }

    for container in containers:
        for person in persons:
            if is_person_near_container(person['bbox'], container['bbox'], img_w, img_h):
                checks = []
                for waste in waste_items:
                    expected = container['expected_category']
                    actual = waste.get('category')
                    is_correct = actual == expected

                    if not is_correct:
                        overall_valid = False

                    checks.append({
                        'waste_class': waste['class'],
                        'waste_category': actual,
                        'expected_category': expected,
                        'is_correct': is_correct,
                    })

                if checks:
                    results.append({
                        'container': container['label'],
                        'container_color': container['color'],
                        'icon': container['icon'],
                        'checks': checks,
                        'overall': overall_valid,
                    })

    if not results:
        return {
            'valid': None,
            'message': 'Persona no est\u00e1 cerca de ninguna caneca',
            'checks': [],
        }

    all_ok = all(r['overall'] for r in results)
    return {
        'valid': all_ok,
        'message': 'Disposici\u00f3n correcta' if all_ok else 'Disposici\u00f3n incorrecta',
        'results': results,
    }
