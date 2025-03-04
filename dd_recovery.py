import argparse
import subprocess
import os
import shutil
from uuid import uuid4
from geopy.geocoders import Nominatim
from exif import Image
from prettytable import PrettyTable

class DDRecovery:
    def __init__(self, filename, required_info,task_id):
        self.filename = filename
        self.required_info = required_info
        self.task_id = task_id
        self.table = self.setup_table(required_info)
        self.output_dir = f"results/{self.task_id}"

    def setup_table(self, required_info):
        table = PrettyTable()
        if required_info == "exif":
            table.field_names = ["fileName", "has EXIF data", 'model', 'make', 'datetime', "GPS Coordinates", "Address"]
        return table

    def recover_dd(self):
        # Run subprocess to extract the dd via foremost
        print(f"Performing dd extract on {self.filename} to {self.output_dir}")
        if not os.path.exists(self.output_dir):
            os.makedirs(self.output_dir)
        result = subprocess.run(["foremost", "-o", self.output_dir, self.filename], capture_output=True, text=True)
        print(f"Result: {result.stdout}")

        if result.stdout is None:
            print("Extraction successful")

    def process_files(self):
        folders = os.listdir(self.output_dir)

        for folder in folders:
            if folder == "audit.txt":
                continue

            files = os.listdir(f"{self.output_dir}/{folder}")
            for file in files:
                print(f"Processing file: ({file}) from {folder} folder")
                file_dir = f"{self.output_dir}/{folder}/{file}"

                if self.required_info == "exif":
                    self.extract_exif(file_dir, file)

    def extract_exif(self, file_dir, file_name):
        try:
            with open(file_dir, "rb") as f:
                img = Image(file_dir)
                has_exif = img.has_exif
                if has_exif:
                    print(f"{file_name} contains exif data")

                    # Extract coordinates
                    coords = (self.decimal_coords(img.gps_latitude, img.gps_latitude_ref),
                              self.decimal_coords(img.gps_longitude, img.gps_longitude_ref))
                    # Get Address from the coordinates
                    geo_loc = Nominatim(user_agent="GetLoc")
                    locname = geo_loc.reverse(coords)
                    self.table.add_row([file_name, "true", img.get('make'), img.get('model'), img.get("datetime_original"), coords, locname.address])
                else:
                    self.table.add_row([file_name, "false", "", "", "", "", ""])
        except Exception as e:
            print(f"Error: {e}")
            print(f"Ignoring {file_name} as it is not the target required Info: ({self.required_info})")
            self.table.add_row([file_name, "false", "", "", "", "", ""])

    def decimal_coords(self, coords, ref):
        decimal_degrees = coords[0] + coords[1] / 60 + coords[2] / 3600
        if ref == "S" or ref == "W":
            decimal_degrees = -decimal_degrees
        return decimal_degrees

    def run(self):
        self.recover_dd()
        self.process_files()
        print(self.table)
        with open(f"{self.output_dir}/{self.filename}_results.csv", "w", newline="") as output:
            output.write(self.table.get_csv_string())

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--filename", help="File Name with paths")
    parser.add_argument("--requiredInfo", help="Required type info to extract")
    parser.add_argument("--task_id", help="Task ID",default=str(uuid4()))
    args = parser.parse_args()

    processor = DDRecovery(args.filename, args.requiredInfo, args.task_id)
    processor.run()
