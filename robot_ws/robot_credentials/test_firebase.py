import firebase_admin

from firebase_admin import credentials
from firebase_admin import firestore

SERVICE_ACCOUNT = (
    "/home/robot/Project/robot_ws/robot_credentials/"
    "firebase-service-account.json"
)

cred = credentials.Certificate(
    SERVICE_ACCOUNT
)

firebase_admin.initialize_app(
    cred
)

db = firestore.client()

print("Firebase Admin SDK connected successfully.")

deliveries = (
    db.collection("deliveries")
    .limit(5)
    .stream()
)

for delivery in deliveries:

    data = delivery.to_dict()

    print(
        delivery.id,
        data.get("status"),
        data.get("ticketId")
    )