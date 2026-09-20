import cv2
from ultralytics import YOLO

model = YOLO("./ml_models/YOLOV8s_Barcode_Detection.pt")  
detector = cv2.QRCodeDetector()
cap = cv2.VideoCapture(0)

while cap.isOpened():
    ret, frame = cap.read()
    if not ret or cv2.waitKey(1) & 0xFF == ord('q'):
        break

    for box in model(frame, verbose=False)[0].boxes:
        x1, y1, x2, y2 = map(int, box.xyxy[0].tolist())
        crop = frame[max(0, y1-10):y2+10, max(0, x1-10):x2+10]
        
        if crop.size > 0:
            data, _, _ = detector.detectAndDecode(crop)
            if data:
                cv2.rectangle(frame, (x1, y1), (x2, y2), (0, 255, 0), 2)
                print(f"Data from QR Code: {data}\n\n")

    cv2.imshow("QR Detection", frame)

cap.release()
cv2.destroyAllWindows()
