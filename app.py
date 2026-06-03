from flask import Flask, render_template, request, send_from_directory
import pandas as pd
import os
import qrcode
import cv2

from pymongo import MongoClient
from datetime import datetime

from PIL import Image, ImageDraw, ImageFont

app = Flask(__name__)

UPLOAD_FOLDER = "uploads"
IDCARD_FOLDER = "idcards"

os.makedirs(UPLOAD_FOLDER, exist_ok=True)
os.makedirs(IDCARD_FOLDER, exist_ok=True)

# MongoDB
client = MongoClient("mongodb://localhost:27017/")
db = client["attendance_system"]
attendance_collection = db["attendance"]


@app.route("/")
def home():
    return render_template("register.html")


@app.route("/register", methods=["POST"])
def register():

    name = request.form["name"]
    division = request.form["division"]
    dob = request.form["dob"]

    photo = request.files["photo"]

    excel_file = "students.xlsx"

    if os.path.exists(excel_file):
        df = pd.read_excel(excel_file)
        count = len(df) + 1
    else:
        count = 1

    enrollment_no = f"2026{count:06d}"

    photo_name = f"{enrollment_no}_{photo.filename}"
    photo_path = os.path.join(UPLOAD_FOLDER, photo_name)

    photo.save(photo_path)

    # Save Student Excel
    new_data = pd.DataFrame({
        "Enrollment No": [enrollment_no],
        "Name": [name],
        "Division": [division],
        "DOB": [dob],
        "Photo": [photo_name]
    })

    if os.path.exists(excel_file):
        old = pd.read_excel(excel_file)
        final = pd.concat([old, new_data], ignore_index=True)
        final.to_excel(excel_file, index=False)
    else:
        new_data.to_excel(excel_file, index=False)

    # QR
    qr_data = f"""
Enrollment No : {enrollment_no}
Name : {name}
Division : {division}
DOB : {dob}
"""

    qr_obj = qrcode.QRCode(
        version=3,
        box_size=10,
        border=4
    )

    qr_obj.add_data(qr_data)
    qr_obj.make(fit=True)

    qr = qr_obj.make_image(
        fill_color="black",
        back_color="white"
    )

    qr = qr.convert("RGB")
    qr = qr.resize((320, 320))

    # ID Card
    card = Image.new("RGB", (900, 550), "white")
    draw = ImageDraw.Draw(card)

    try:
        title_font = ImageFont.truetype("arial.ttf", 34)
        text_font = ImageFont.truetype("arial.ttf", 22)
    except:
        title_font = ImageFont.load_default()
        text_font = ImageFont.load_default()

    draw.rectangle((0, 0, 900, 90), fill=(0, 51, 102))

    draw.text(
        (300, 20),
        "LJ UNIVERSITY",
        fill="white",
        font=title_font
    )

    student_photo = Image.open(photo_path)
    student_photo = student_photo.resize((180, 220))

    card.paste(student_photo, (40, 130))

    draw.text((260, 140), f"Name : {name}", fill="black", font=text_font)
    draw.text((260, 190), f"Enrollment : {enrollment_no}", fill="black", font=text_font)
    draw.text((260, 240), f"Division : {division}", fill="black", font=text_font)
    draw.text((260, 290), f"DOB : {dob}", fill="black", font=text_font)

    card.paste(qr, (550, 140))

    idcard_name = f"{enrollment_no}.png"
    idcard_path = os.path.join(IDCARD_FOLDER, idcard_name)

    card.save(idcard_path)

    return f"""
<!DOCTYPE html>
<html>
<head>
    <title>Registration Successful</title>

    <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.3/dist/css/bootstrap.min.css" rel="stylesheet">

    <style>
        body {{
            background: #f4f7fc;
        }}

        .success-card {{
            max-width: 700px;
            margin: 80px auto;
            padding: 40px;
            border-radius: 20px;
            box-shadow: 0 0 25px rgba(0,0,0,0.1);
            background: white;
            text-align: center;
        }}

        .enrollment {{
            font-size: 28px;
            font-weight: bold;
            color: #0d6efd;
        }}

        .btn {{
            width: 250px;
            margin: 10px;
            font-size: 18px;
        }}
    </style>
</head>

<body>

<div class="success-card">

    <h1 class="text-success mb-4">
        Registration Successful
    </h1>

    <p class="enrollment">
        Enrollment No: {enrollment_no}
    </p>

    <hr>

    <a href="/idcards/{idcard_name}"
       target="_blank"
       class="btn btn-primary btn-lg">
       View ID Card
    </a>

    <br>

    <a href="/"
       class="btn btn-success btn-lg">
       Add New Student
    </a>

    <br>

    <a href="/scan_attendance"
       class="btn btn-warning btn-lg">
       Scan Attendance
    </a>

</div>

</body>
</html>
"""


@app.route("/scan_attendance")
def scan_attendance():

    cap = cv2.VideoCapture(0)

    # Fast Camera
    cap.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)

    detector = cv2.QRCodeDetector()

    # Small Window
    cv2.namedWindow("QR Scanner", cv2.WINDOW_NORMAL)
    cv2.resizeWindow("QR Scanner", 500, 350)

    while True:

        ret, frame = cap.read()

        if not ret:
            continue

        # Green Guide Box
        h, w = frame.shape[:2]

        x1 = w // 2 - 120
        y1 = h // 2 - 120

        x2 = w // 2 + 120
        y2 = h // 2 + 120

        cv2.rectangle(
            frame,
            (x1, y1),
            (x2, y2),
            (0, 255, 0),
            2
        )

        cv2.putText(
            frame,
            "Place QR Here",
            (x1, y1 - 10),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.6,
            (0, 255, 0),
            2
        )

        gray = cv2.cvtColor(
            frame,
            cv2.COLOR_BGR2GRAY
        )

        data, bbox, _ = detector.detectAndDecode(gray)

        if data:

            enrollment = ""
            name = ""

            lines = data.split("\n")

            for line in lines:

                if "Enrollment No" in line:
                    enrollment = line.split(":")[1].strip()

                if "Name" in line:
                    name = line.split(":")[1].strip()

            now = datetime.now()

            date = now.strftime("%d-%m-%Y")
            time = now.strftime("%H:%M:%S")

            attendance_data = pd.DataFrame({
                "Date": [date],
                "Time": [time],
                "Enrollment No": [enrollment],
                "Name": [name]
            })

            file = "attendance.xlsx"

            if os.path.exists(file):

                old = pd.read_excel(file)

                # Duplicate Attendance Stop
                duplicate = old[
                    (old["Enrollment No"] == enrollment) &
                    (old["Date"] == date)
                ]

                if len(duplicate) == 0:

                    final = pd.concat(
                        [old, attendance_data],
                        ignore_index=True
                    )

                    final.to_excel(
                        file,
                        index=False
                    )

            else:

                attendance_data.to_excel(
                    file,
                    index=False
                )

            attendance_collection.insert_one({
                "date": date,
                "time": time,
                "enrollment_no": enrollment,
                "name": name
            })

            cap.release()
            cv2.destroyAllWindows()

            return f"""
            <html>
            <head>

            <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.3/dist/css/bootstrap.min.css" rel="stylesheet">

            </head>

            <body style="background:#f4f7fc">

            <div class="container mt-5">

            <div class="card shadow p-5 text-center">

            <h1 class="text-success">
            Attendance Saved Successfully
            </h1>

            <hr>

            <h3>{name}</h3>

            <h4>{enrollment}</h4>

            <br>

            <a href="/"
            class="btn btn-primary">

            Back To Home

            </a>

            </div>

            </div>

            </body>
            </html>
            """

        cv2.imshow("QR Scanner", frame)

        key = cv2.waitKey(1) & 0xFF

        if key == 27:
            break

        if key == ord("q"):
            break

        # Close Button (X) Support
        if cv2.getWindowProperty(
            "QR Scanner",
            cv2.WND_PROP_VISIBLE
        ) < 1:
            break

    cap.release()
    cv2.destroyAllWindows()

    return """
    <h2>Scanner Closed</h2>
    <a href="/">Back</a>
    """

@app.route("/idcards/<filename>")
def view_idcard(filename):
    return send_from_directory(IDCARD_FOLDER, filename)


if __name__ == "__main__":
    app.run(debug=True)