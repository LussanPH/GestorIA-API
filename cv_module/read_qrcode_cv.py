import cv2 as cv
import numpy as np
from ultralytics import YOLO

model = YOLO("YOLOV8s_Barcode_Detection.pt")
cap = cv.VideoCapture(0)

qr = cv.QRCodeDetector()


def order_points(pts):
    pts = np.asarray(pts, dtype=np.float32)

    s = pts.sum(axis=1)
    d = np.diff(pts, axis=1).ravel()

    return np.array([
        pts[np.argmin(s)],  # TL
        pts[np.argmin(d)],  # TR
        pts[np.argmax(s)],  # BR
        pts[np.argmax(d)],  # BL
    ], dtype=np.float32)


def rectify(image, corners, size=800):
    corners = order_points(corners)

    dst = np.array([
        [0, 0],
        [size - 1, 0],
        [size - 1, size - 1],
        [0, size - 1]
    ], dtype=np.float32)

    H = cv.getPerspectiveTransform(corners, dst)

    return cv.warpPerspective(
        image,
        H,
        (size, size),
        flags=cv.INTER_CUBIC
    )


def decode(image):
    """
    Try several versions of the ORIGINAL QR pixels.
    """

    images = [image]

    gray = cv.cvtColor(image, cv.COLOR_BGR2GRAY)
    images.append(gray)

    # Sharpen
    sharp = cv.GaussianBlur(gray, (0, 0), 3)
    sharp = cv.addWeighted(gray, 2.0, sharp, -1.0, 0)
    images.append(sharp)

    # Otsu
    _, otsu = cv.threshold(
        gray,
        0,
        255,
        cv.THRESH_BINARY + cv.THRESH_OTSU
    )
    images.append(otsu)

    # Adaptive threshold
    adaptive = cv.adaptiveThreshold(
        gray,
        255,
        cv.ADAPTIVE_THRESH_GAUSSIAN_C,
        cv.THRESH_BINARY,
        31,
        5
    )
    images.append(adaptive)

    for img in images:
        data, points, _ = qr.detectAndDecode(img)

        if data:
            return data

    return None


while True:

    ok, frame = cap.read()

    if not ok:
        break

    results = model(frame, verbose=False)

    for result in results:

        if result.masks is None:
            continue

        for mask in result.masks.data:

            # YOLO mask
            mask = mask.cpu().numpy()

            mask = cv.resize(
                mask,
                (frame.shape[1], frame.shape[0]),
                interpolation=cv.INTER_NEAREST
            )

            mask = (mask > 0.5).astype(np.uint8) * 255

            # Find contour
            contours, _ = cv.findContours(
                mask,
                cv.RETR_EXTERNAL,
                cv.CHAIN_APPROX_SIMPLE
            )

            if not contours:
                continue

            contour = max(contours, key=cv.contourArea)

            # Approximate QR contour
            perimeter = cv.arcLength(contour, True)

            approx = cv.approxPolyDP(
                contour,
                0.02 * perimeter,
                True
            )

            if len(approx) != 4:
                continue

            corners = approx.reshape(4, 2).astype(np.float32)

            # IMPORTANT:
            # Use corners obtained from YOLO,
            # but use ORIGINAL frame pixels.
            qr_image = rectify(frame, corners)

            data = decode(qr_image)

            # Draw detection
            cv.polylines(
                frame,
                [corners.astype(np.int32)],
                True,
                (0, 255, 0),
                3
            )

            if data:
                print("DECODED:", data)

                cv.putText(
                    frame,
                    data,
                    (20, 40),
                    cv.FONT_HERSHEY_SIMPLEX,
                    0.8,
                    (0, 255, 0),
                    2
                )

    cv.imshow("QR", frame)

    if cv.waitKey(1) & 0xFF == ord("q"):
        break


cap.release()
cv.destroyAllWindows()