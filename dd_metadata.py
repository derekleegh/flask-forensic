import argparse
from uuid import uuid4
import subprocess

class DDMetadata:
    def __init__(self, filename, task_id):
        self.filename = filename
        self.task_id = task_id
        self.output_dir = f"results/{self.task_id}"
        self.metadata = {}

    def get_filesystem_type(self):
        try:
            result = subprocess.run(['file', '-s', self.filename], stdout=subprocess.PIPE)
            output = result.stdout.decode()
            if 'FAT (16 bit)' in output:
                return 'FAT16'
            if 'FAT (32 bit)' in output:
                return 'FAT32'
            if 'NTFS' in output:
                return 'NTFS'
            return 'Unknown'
        except Exception as e:
            print(f"Error determining filesystem type: {e}")
            return 'Unknown'

    def get_metadata(self):
        print(f"Getting metadata from {self.filename}")

        # Get filesystem type
        filesystem_type = self.get_filesystem_type()
        print(f"Filesystem type: {filesystem_type}")
        self.metadata['filesystem_type'] = filesystem_type

        # Get number of sector per fat
        try:
            with open(self.filename, 'rb') as f:
                f.seek(36)  # Offset for FAT16/FAT32 sectors per FAT
                sectors_per_fat = int.from_bytes(f.read(2), byteorder='little')
                self.metadata['sectors_per_fat'] = sectors_per_fat
        except Exception as e:
            print(f"Error getting sectors per FAT: {e}")
            self.metadata['sectors_per_fat'] = 'Unknown'



    def run(self):
        self.get_metadata()
        print(self.metadata)

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--filename", help="File Name with paths")
    parser.add_argument("--requiredInfo", help="Required type info to extract")
    parser.add_argument("--task_id", help="Task ID",default=str(uuid4()))
    args = parser.parse_args()

    processor = DDMetadata(args.filename, args.task_id)
    processor.run()
