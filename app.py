import os
import time
import csv
import json
from threading import Thread
from uuid import uuid4
from datetime import datetime
from flask import Flask, render_template, request, redirect, url_for, session
import folium
from folium.plugins import TimestampedGeoJson
from dd_recovery import DDRecovery

app = Flask(__name__)
app.config['UPLOAD_FOLDER'] = 'uploads/'
app.config["RESULTS_FOLDER"] = "output/"
app.secret_key = 'supersecretkey'  # Needed for session management
RECOVERED_FILES = "deleted.dd_results.csv"

@app.route("/", methods=["GET", "POST"])
def upload_file():
    if request.method == "POST":
        if 'file' not in request.files:
            return "No file part"
        file = request.files['file']
        if file.filename == '':
            return "No selected file"
        # file_path = os.path.join(app.config['UPLOAD_FOLDER'], file.filename)
        file_path = file.filename
        file.save(file_path)

        file_size = os.path.getsize(file_path)
        file_metadata = {
            'filename': file.filename,
            'size': file_size,
            'path': file_path
        }
        print("File metadata:", file_metadata)

        with open(file_path, 'rb') as f:
            file_data = f.read()

        # session['file_data'] = file_data
        session['file_metadata'] = file_metadata

        return redirect(url_for('display_file'))

    return render_template("index.html")

@app.route("/display")
def display_file():
    file_data = session.get('file_data')
    file_metadata = session.get('file_metadata')
    # if not file_data or not file_metadata:
    if not file_metadata:
        return redirect(url_for('upload_file'))
    # return render_template("display.html", file_data=file_data, **file_metadata)
    return render_template("display.html",file_data="", file_metadata=file_metadata)

tasks = {}

def background_task(task_id, file_metadata):
    time.sleep(3)  # Simulate a loading process
    processor = DDRecovery(file_metadata['path'], 'exif')
    processor.run()
    tasks[task_id]['status'] = 'completed'

@app.route("/extract", methods=["POST"])
def extract():
    file_data = session.get('file_data')
    file_metadata = session.get('file_metadata')
    if not file_metadata:
        return redirect(url_for('upload_file'))
    else:
        """Extract metadata from the uploaded file."""

    task_id = str(uuid4())
    tasks[task_id] = {'status': 'in_progress'}

    thread = Thread(target=background_task, args=(task_id, file_metadata))
    thread.start()

    return redirect(url_for('task_status', task_id=task_id))

@app.route("/task_status/<task_id>")
def task_status(task_id):
    task = tasks.get(task_id)
    if not task:
        return "Task not found", 404
    return render_template("task_status.html", task_id=task_id, status=task['status']) 

@app.route("/extraction_result")
def extraction_result():
    file_data = session.get('file_data')
    csv_file_path = os.path.join(app.config['RESULTS_FOLDER'], RECOVERED_FILES)
    table_data = []

    if os.path.exists(csv_file_path):
        with open(csv_file_path, newline='', encoding="utf-8") as csvfile:
            reader = csv.DictReader(csvfile)
            for row in reader:
                table_data.append(row)

    return render_template("extraction_result.html", file_data=file_data, table_data=table_data)

@app.route("/map_from_csv")
def map_from_csv():
    """Load GPS coordinates from CSV and add them as markers on a map."""
    csv_file_path = os.path.join(app.config['RESULTS_FOLDER'], RECOVERED_FILES)

    record_with_gps = []
    coordinates = []
    features = []

    if os.path.exists(csv_file_path):
        with open(csv_file_path, newline='', encoding="utf-8") as csvfile:
            reader = csv.DictReader(csvfile)
            for idx, row in enumerate(reader, start=1):
                if row['GPS Coordinates'] and row['datetime']:
                    coords = row['GPS Coordinates'].strip("()").split(", ")
                    lat, lon = float(coords[0]), float(coords[1])
                    coordinates.append([lon, lat])  # GeoJSON uses [lon, lat] format
                    datetime_str = row['datetime'].replace(" ", "T").replace(":", "-", 2) + "Z"  # Convert to YYYY-MM-DDTHH:MM:SSZ format

                    record_with_gps.append({
                        'lat': lat,
                        'lon': lon,
                        'datetime': datetime_str,
                        'filename': row['fileName'],
                        'address': row['Address']
                    })

        # Sort by datetime
        record_with_gps = sorted(record_with_gps, key=lambda x: datetime.strptime(x['datetime'], "%Y-%m-%dT%H:%M:%SZ"))

        # Set the map centered around the first coordinate
        m = folium.Map(location=[record_with_gps[0]["lat"], record_with_gps[0]["lon"]], zoom_start=10)

        # Create GeoJSON features (this is to generate the line connecting the points)
        for i in range(len(record_with_gps) - 1):
            feature = {
                "type": "Feature",
                "geometry": {
                    "type": "LineString",
                    "coordinates": [
                        [record_with_gps[i]["lon"], record_with_gps[i]["lat"]],
                        [record_with_gps[i + 1]["lon"], record_with_gps[i + 1]["lat"]]
                    ]
                },
                "properties": {
                    "times": [record_with_gps[i]["datetime"], record_with_gps[i + 1]["datetime"]],
                    "style": {"color": "blue", "weight": 5}
                }
            }
            features.append(feature)

        # Add numbered markers with popups as GeoJSON features
        for idx, coord in enumerate(record_with_gps, start=1):
            feature = {
                "type": "Feature",
                "geometry": {
                    "type": "Point",
                    "coordinates": [coord["lon"], coord["lat"]]
                },
                "properties": {
                    "times": [coord["datetime"]],
                    "popup": f"""<b>{idx}.</b>
                        <br>
                        <b>Filename:</b> {coord['filename']}
                        <br>
                        <b>Address:</b> {coord['address']}
                        <br>
                        <b>Time:</b> {coord['datetime']}
                    """
                }
            }
            features.append(feature)

        # Create a GeoJSON object
        geojson = {
            "type": "FeatureCollection",
            "features": features
        }

        # Add the TimestampedGeoJson to the map
        TimestampedGeoJson(
            data=json.dumps(geojson),
            period="PT1H",
            add_last_point=True,
            auto_play=False,
            loop=False,
            max_speed=1,
            loop_button=True,
            date_options='YYYY-MM-DD HH:mm:ss',
            time_slider_drag_update=True
        ).add_to(m)

        # Use this to render directly
        return m.get_root().render()
    else:
        return "No GPS coordinates found in the CSV file or no csv file found.Exiting with error"

    # Use this to render as a template to give more flexibility
    # map_html = m._repr_html_()
    # return render_template('timeline.html', map_html=map_html)

if __name__ == "__main__":
    app.run(debug=True)
