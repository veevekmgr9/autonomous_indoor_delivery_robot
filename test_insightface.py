import insightface
import onnxruntime as ort

print("InsightFace:", insightface.__version__)
print("ONNX Runtime:", ort.__version__)
print("Providers:", ort.get_available_providers())

app = insightface.app.FaceAnalysis(
    name="buffalo_l",
    providers=["CPUExecutionProvider"]
)

app.prepare(
    ctx_id=-1,
    det_size=(640, 640)
)

print("InsightFace model loaded successfully!")
