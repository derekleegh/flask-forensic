import os
import struct
from pathlib import Path
import exiftool

# Constants
DIR_ENTRY_SIZE = 32
SECTOR_SIZE = 512
JPEG_HEADER = b'\xFF\xD8'
JPEG_FOOTER = b'\xFF\xD9'

def read_raw_device(device_path, offset, size):
    with open(device_path, 'rb') as f:
        f.seek(offset)
        return f.read(size)

def get_cluster_data(device_path, cluster, bytes_per_cluster):
    data_offset = (cluster - 2) * bytes_per_cluster  # Simplified; adjust for real FAT layout
    return read_raw_device(device_path, data_offset, bytes_per_cluster * 10)

def is_deleted_entry(entry):
    return entry[0] == 0xE5

def extract_filename(entry):
    """Extract the short filename from a deleted directory entry."""
    # For deleted files, first byte is 0xE5; use remaining bytes
    name_part = entry[1:8].decode('ascii', errors='ignore').strip()  # Bytes 1-7
    ext_part = entry[8:11].decode('ascii', errors='ignore').strip()  # Bytes 8-10
    
    # Combine name and extension, using '_' as a placeholder for the lost first character
    if name_part or ext_part:
        return f"_{name_part}.{ext_part}" if ext_part else f"_{name_part}"
    return f"recovered_{id(entry)}"  # Fallback if name is empty

def recover_jpeg(device_path, entry, output_folder, cluster_size):
    start_cluster = struct.unpack('<H', entry[26:28])[0]
    file_size = struct.unpack('<I', entry[28:32])[0]
    
    data = get_cluster_data(device_path, start_cluster, cluster_size)
    if data.startswith(JPEG_HEADER):
        end_idx = data.find(JPEG_FOOTER) + 2 if JPEG_FOOTER in data else len(data)
        jpeg_data = data[:end_idx if file_size == 0 else min(file_size, end_idx)]
        
        filename = extract_filename(entry)
        output_path = Path(output_folder) / f"{filename}.jpg"
        with open(output_path, 'wb') as f:
            f.write(jpeg_data)
        return output_path
    return None

def extract_exif(file_path):
    with exiftool.ExifTool() as et:
        metadata = et.get_metadata(str(file_path))
    return metadata

def main(device_path, output_folder):
    Path(output_folder).mkdir(parents=True, exist_ok=True)
    offset = 0
    cluster_size = 4096  # Adjust based on your USB
    
    while True:
        sector = read_raw_device(device_path, offset, SECTOR_SIZE)
        if not sector:
            break
        
        for i in range(0, len(sector), DIR_ENTRY_SIZE):
            entry = sector[i:i + DIR_ENTRY_SIZE]
            if len(entry) < DIR_ENTRY_SIZE:
                break
            
            if is_deleted_entry(entry):
                recovered_file = recover_jpeg(device_path, entry, output_folder, cluster_size)
                if recovered_file:
                    print(f"Recovered: {recovered_file}")
                    try:
                        metadata = extract_exif(recovered_file)
                        print("EXIF Metadata:", metadata)
                    except Exception as e:
                        print(f"Failed to extract EXIF: {e}")
        
        offset += SECTOR_SIZE

if __name__ == "__main__":
    device_path = "/dev/sdX"  # Replace with your USB or image file
    output_folder = "./recovered_images"
    main(device_path, output_folder)
