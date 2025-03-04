import os
import struct
import time
import binascii

def read_bytes(file, offset, length):
    file.seek(offset)
    return file.read(length)

def hex_to_ascii(hex_str):
    return binascii.unhexlify(hex_str).decode('ascii')

def main():
    infilename = input("Please enter path and filename (Default:Desktop/q.dd): ") or "Desktop/q.dd"
    print("\n")

    with open(infilename, 'rb') as f:
        # Read File System from Boot Sector Byte 54
        asciifilesystem = hex_to_ascii(binascii.hexlify(read_bytes(f, 54, 5)).decode('ascii'))
        print(f"The File System is {asciifilesystem} \n")

        # Read Volume Name
        hexvolname = binascii.hexlify(read_bytes(f, 43, 10)).decode('ascii')
        asciivolname = hex_to_ascii(hexvolname)
        print(f"The volume name is {asciivolname} \n")

        # Read Number of Sectors per FAT
        hexsecperfat = binascii.hexlify(read_bytes(f, 22, 2)).decode('ascii')
        decimalsecperfat = int(hexsecperfat, 16)
        print(f"The sectors per fat is {decimalsecperfat} \n")

        # Read Sector Size
        hexsector = binascii.hexlify(read_bytes(f, 11, 2)).decode('ascii')
        decimalsectorsize = int(hexsector, 16)
        print(f"There are {decimalsectorsize} bytes per sector \n")

        # Read Cluster Size
        hexcluster = binascii.hexlify(read_bytes(f, 13, 1)).decode('ascii')
        decimalsecpercluster = int(hexcluster, 16)
        decimalclustersize = decimalsectorsize * decimalsecpercluster
        print(f"The cluster size in bytes is {decimalclustersize} \n")

        # Read Reserved Sectors
        hexressector = binascii.hexlify(read_bytes(f, 14, 2)).decode('ascii')
        decimalressectors = int(hexressector, 16)
        print(f"The reserved sectors in bytes is {decimalressectors} \n")

        # Read Number of FAT Copies
        hexfatcopies = binascii.hexlify(read_bytes(f, 16, 1)).decode('ascii')
        decimalnumfatcopies = int(hexfatcopies, 16)
        print(f"The number of FAT Tables is {decimalnumfatcopies} \n")
        decimalsizeoffat = decimalsecperfat * decimalsectorsize
        print(f"Each FAT table in bytes is: {decimalsizeoffat} \n")

        fat0end = decimalressectors + (decimalsecperfat * decimalnumfatcopies) - 1
        print(f"Fat 0: {decimalressectors} - {fat0end} \n")
        fat1start = fat0end + 1
        fat1end = decimalressectors + (decimalsecperfat * decimalnumfatcopies) - 1
        print(f"Fat 1: {fat1start} - {fat1end} \n")

        # Read Number of Root Directory Entries
        hexnumrootdir = binascii.hexlify(read_bytes(f, 17, 2)).decode('ascii')
        decimalnumrootdir = int(hexnumrootdir, 16)
        print(f"The number of root directory entries is {decimalnumrootdir} \n")

        # The size of the root directory is the number of root directory entries times 32 bytes
        decimalsizerootdirectory = decimalnumrootdir * 32
        decimalsectorsrootdirectory = decimalsizerootdirectory // decimalsectorsize
        decimalclustersrootdirectory = decimalsizerootdirectory // decimalclustersize
        print(f"The size of the root directory in bytes is {decimalsizerootdirectory} \n")

        # The size of the disk in bytes is at bytes 32 33 34 (number of sectors x sector size)
        hextotalsectors = binascii.hexlify(read_bytes(f, 32, 3)).decode('ascii')
        decimaltotalsectors = int(hextotalsectors, 16)
        decimalvolumetotalbytes = decimaltotalsectors * decimalsectorsize
        print(f"The total size of the disk in bytes is {decimalvolumetotalbytes} \n")

        # Root Directory Start and End Calculation
        decimalrootdirectorystart = decimalressectors + decimalsecperfat * decimalnumfatcopies
        rootdirectoryend = decimalressectors + decimalsecperfat + decimalsecperfat + decimalsectorsrootdirectory - 1
        rootdirectorystartbyte = decimalrootdirectorystart * decimalsectorsize
        rootdirectoryendbyte = rootdirectoryend * decimalsectorsize
        startofdata = rootdirectoryend + 1

        # Skip to the start of the Data Area
        skipvalue = rootdirectorystartbyte + 128
        diskname = binascii.hexlify(read_bytes(f, decimalrootdirectorystart * decimalsectorsize, 10)).decode('ascii')
        asciidiskname = hex_to_ascii(diskname)
        print(f"The disk name is {asciidiskname} \n")

        # The calculation to find the first byte of the first file metadata line
        metastart = (decimalressectors * decimalsectorsize) + (decimalsizeoffat * decimalnumfatcopies) + 128
        print(f"The first file's metadata begins at byte {metastart} \n")

        hexfirstfilename = binascii.hexlify(read_bytes(f, metastart, 8)).decode('ascii')
        hexasciifirstfileext = binascii.hexlify(read_bytes(f, metastart + 8, 3)).decode('ascii')
        asciifirstfilename = hex_to_ascii(hexfirstfilename)
        asciifirstfileext = hex_to_ascii(hexasciifirstfileext)
        print(f"The first filename is {asciifirstfilename}.{asciifirstfileext} \n")

        # Current date and time
        currentdate = time.strftime('%d-%m-%y %H:%M:%S')
        print(f"The current date and time is: {currentdate}\n")

if __name__ == "__main__":
    main()
