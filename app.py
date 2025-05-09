import os
import csv
import json
import hashlib
import shutil
from threading import Thread
from uuid import uuid4
from datetime import datetime
from flask import Flask, render_template, request, redirect, url_for, session, send_file
import folium
from folium.plugins import TimestampedGeoJson
from dd_recovery import DDRecovery

# TODO:
# 1. Extract dd metadata to be shown after upload

app = Flask(__name__)
app.config["RESULTS_FOLDER"] = "results/"
app.secret_key = 'supersecretkey'  # Needed for session management
RECOVERED_FILES = "deleted.dd_results.csv"
tasks = {}

@app.route("/", methods=["GET", "POST"])
def upload_file():
    if request.method == "POST":
        if 'file' not in request.files:
            return "No file part"
        file = request.files['file']
        if file.filename == '':
            return "No selected file"
        if not file.filename.endswith('.dd'):
            return '''
                <p>Only .dd files are allowed</p>
                <button onclick="window.location.href='/'">Return</button>
            ''', 400
        file_path = file.filename
        file.save(file_path)

        file_upload_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        file_size = os.path.getsize(file_path)
        task_id = str(uuid4())

        # Calculate the file hash (SHA-256)
        hasher = hashlib.sha256()
        with open(file_path, 'rb') as f:
            while chunk := f.read(8192):
                hasher.update(chunk)
        file_hash = hasher.hexdigest()

        # Store the file metadata in a dictionary
        file_metadata = {
            'filename': file.filename,
            'size': file_size,
            'path': file_path,
            'hash': file_hash,
            'datetime': file_upload_time,
            "task_id": task_id
        }

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
    return render_template("display.html", file_data=file_data, **file_metadata)


def background_task(task_id, file_metadata):
    processor = DDRecovery(file_metadata['path'], 'exif', task_id)
    processor.run()
    tasks[task_id]['status'] = 'completed'
    file_metadata['task_id'] = task_id
    file_metadata['status'] = 'completed'

    # Save the metadata to a JSON file
    metadata_file_path = os.path.join(app.config['RESULTS_FOLDER'], task_id, "metadata.json")
    os.makedirs(os.path.dirname(metadata_file_path), exist_ok=True)
    with open(metadata_file_path, 'w') as f:
        json.dump(file_metadata, f, indent=4)

@app.route("/extract", methods=["POST"])
def extract():
    file_data = session.get('file_data')
    file_metadata = session.get('file_metadata')
    if not file_metadata:
        return redirect(url_for('upload_file'))

    task_id = file_metadata.get("task_id")

    tasks[task_id] = {
        'taskid': task_id,
        'filename': file_metadata['filename'],
        'datetime': file_metadata['datetime'],
        'status': 'in_progress'
    }

    thread = Thread(target=background_task, args=(task_id, file_metadata))
    thread.start()

    return redirect(url_for('tasks_list'))

@app.route("/tasks")
def tasks_list():
    ttasks = {}
    results_folder = app.config["RESULTS_FOLDER"]
    for task_id in os.listdir(results_folder):
        task_path = os.path.join(results_folder, task_id)
        metadata_file = os.path.join(task_path, "metadata.json")
        if os.path.exists(metadata_file):
            with open(metadata_file, "r") as f:
                task_metadata = json.load(f)
                ttasks[task_id] = task_metadata
                tasks[task_id] = {
                    'taskid': task_id,
                    'filename': task_metadata['filename'],
                    'datetime': task_metadata['datetime'],
                    'status': task_metadata['status']
                }
    
    # Join with tasks dictionary and deduplicate
    for task_id, task in tasks.items():
        if task_id not in ttasks:
            ttasks[task_id] = task

    # Sort tasks by datetime
    sorted_tasks = dict(sorted(ttasks.items(), key=lambda x: datetime.strptime(x[1]['datetime'], "%Y-%m-%d %H:%M:%S"), reverse=True))

    return render_template("tasks_list.html", tasks=sorted_tasks)

@app.route("/task_status/<task_id>")
def task_status(task_id):
    metadata_file_path = os.path.join(app.config['RESULTS_FOLDER'], task_id, "metadata.json")
    if not os.path.exists(metadata_file_path):
        # get from the tasks dictionary
        task = tasks.get(task_id)
    else:
        with open(metadata_file_path, "r") as f:
            task = json.load(f)

    if not task:
        return "Task not found", 404
    return render_template("task_status.html", task_id=task_id, filename=task["filename"], status=task['status'])

@app.route("/extraction_result")
def extraction_result():
    task_id = request.args.get('task_id')
    start_date = request.args.get('start_date')
    end_date = request.args.get('end_date')
    has_exif = request.args.get('has_exif')  # Get the "Has EXIF Data" filter value

    if not task_id:
        return "Task ID not provided", 400

    file_metadata = session.get('file_metadata')
    if not file_metadata or file_metadata.get("task_id") != task_id:
        # check if the task_id exists in the results folder
        results_folder = app.config["RESULTS_FOLDER"]
        task_path = os.path.join(results_folder, task_id)
        metadata_file = os.path.join(task_path, "metadata.json")
        if not os.path.exists(metadata_file):
            return "Invalid task ID", 400

    csv_file_path = os.path.join(app.config['RESULTS_FOLDER'], task_id, file_metadata['filename'] + "_results.csv")
    table_data = []

    if os.path.exists(csv_file_path):
        with open(csv_file_path, newline='', encoding="utf-8") as csvfile:
            reader = csv.DictReader(csvfile)
            for row in reader:
                if row['datetime'] != "":
                    row_date = datetime.strptime(row['datetime'], "%Y:%m:%d %H:%M:%S")
                    if start_date and end_date:
                        start_date_obj = datetime.strptime(start_date, "%Y-%m-%d")
                        end_date_obj = datetime.strptime(end_date, "%Y-%m-%d")
                        if start_date_obj <= row_date <= end_date_obj:
                            if has_exif and row.get('has_EXIF_data') == "true":
                                table_data.append(row)
                            elif has_exif != "true":
                                table_data.append(row)
                    else:
                        if has_exif and row.get('has_EXIF_data') == "true":
                            table_data.append(row)
                        elif has_exif != "true":
                            table_data.append(row)
                else:
                    if has_exif and row.get('has_EXIF_data') == "true":
                        table_data.append(row)
                    elif has_exif != "true":
                        table_data.append(row)

    # Store the filtered data in the session
    session['filtered_data'] = table_data

    # Calculate the total number of files
    total_files = len(table_data)

    return render_template("extraction_result.html", table_data=table_data, total_files=total_files)

@app.route("/download_results", methods=["GET"])
def download_results():
    task_id = request.args.get("task_id")
    if not task_id:
        return "Task ID not provided", 400

    # Path to the task directory
    task_dir = os.path.join(app.config["RESULTS_FOLDER"], task_id)
    if not os.path.exists(task_dir):
        return "Task directory not found", 404

    # Create a ZIP file for the task directory
    zip_path = os.path.join(app.config["RESULTS_FOLDER"], f"{task_id}.zip")
    shutil.make_archive(zip_path.replace(".zip", ""), 'zip', task_dir)

    # Serve the ZIP file for download
    return send_file(zip_path, as_attachment=True, download_name=f"{task_id}.zip")

@app.route("/map_from_csv")
def map_from_csv():
    """Load GPS coordinates from CSV and add them as markers on a map."""
    filtered_data = session.get('filtered_data')
    if not filtered_data:
        return "No filtered data available", 400

    record_with_gps = []
    coordinates = []
    features = []

    for row in filtered_data:
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

# Use this to render as a template to give more flexibility
# map_html = m._repr_html_()
# return render_template('timeline.html', map_html=map_html)

if __name__ == "__main__":
    app.run(debug=True)
