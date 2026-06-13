from ultralytics import YOLO
from PIL import Image

model = YOLO('/Users/momen/My Projects/Grad Project/Backend_grad/safesight-backend/graduation_project 2/best (4).pt')
img = Image.open('/tmp/debug_frame.jpg').convert('RGB')
print('Image size:', img.size)
results = model(img, conf=0.1, verbose=False)
r = results[0]
print('Boxes at conf=0.1:', len(r.boxes))
for cls, conf in zip(r.boxes.cls, r.boxes.conf):
    print(f'  {model.names[int(cls)]} conf={float(conf):.2f}')
