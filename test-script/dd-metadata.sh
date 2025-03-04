#!/bin/bash

# This script reads through the boot sector information for a FAT16 file system
# and advises the user where the first cluster chain is and where the first metadata line is


# As the user for the filename including path - do not change this.
# Default values are given so have q.dd on your Desktop and then hit the enter key - you do not need to enter a filename
read -p "Please enter path and filename (Default:Desktop/q.dd): " infilename 
infilename=${infilename:-Desktop/q.dd}
printf "\n"

# ******************************************************************************************************************************
# Read File System from Boot Sector Byte 54 (note that is is -l (-ell, not one, don't confuse l and 1 as they look similar)

# BEGIN HERE!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!

# READ THE FILE SYSTEM OF 5 BYTES AND THEN CONVERT TO ASCII
# USE THE VARIABLE NAME BLOW FOR THE ASCII
# NOW GO TO LINE 107
asciifilesystem=$(xxd -s 54 -l 5 -ps $infilename | xxd -r -ps) 
printf "The File System is $asciifilesystem \n"

# ******************************************************************************************************************************

# Read Volume Name - 'No Name' is the name if there is not a name
hexvolname=$(xxd -s 43 -l 10 -ps $infilename)
read asciivolname < <(echo $hexvolname | xxd -r -ps)
printf "The volume name is $asciivolname \n"

# Read Number of Sectors per FAT Byutes 22-23 (little endian for all bytes from here onwards)
hexsecperfat1=$(xxd -s 22 -l 1 -ps $infilename)
hexsecperfat2=$(xxd -s 23 -l 1 -ps $infilename)
hexsecperfat=$hexsecperfat2$hexsecperfat1
read decimalsecperfat < <(echo $((16#$hexsecperfat)))
printf "The sectors per fat is $decimalsecperfat \n"

# Read Sector Size Bytes 11 and 12
hexsector1=$(xxd -s 11 -l 1 -ps $infilename)
hexsector2=$(xxd -s 12 -l 1 -ps $infilename)
hexsector=$hexsector2$hexsector1
read decimalsectorsize < <(echo $((16#$hexsector)))
printf "There are $decimalsectorsize bytes per sector \n"

# Read Cluster Size Byte 13
hexcluster=$(xxd -s 13 -l 1 -ps $infilename)
read decimalsecpercluster < <(echo $((16#$hexcluster)))
decimalclustersize=$((decimalsectorsize * decimalsecpercluster))
printf "The cluster size in bytes is $decimalclustersize \n"

# Read Reserved Sectors Bytes 14 and 15
hexressector1=$(xxd -s 14 -l 1 -ps $infilename)
hexressector2=$(xxd -s 15 -l 1 -ps $infilename)
hexressector=$hexressector2$hexressector1
read decimalressectors < <(echo $((16#$hexressector)))
printf "The reserved sectors in bytes is $decimalressectors \n"

# Read Number of FAT Copies Byte 16 and calculate size of Fat tables and location of Fat Tables
hexfatcopies=$(xxd -s 16 -l 1 -ps $infilename)
read decimalnumfatcopies < <(echo $((16#$hexfatcopies)))
printf "The number of FAT Tables is $decimalnumfatcopies \n"
decimalsizeoffat=$((decimalsecperfat*decimalsectorsize))
printf "Each FAT table in bytes is: $decimalsizeoffat \n"

fat0end=$((decimalressectors + (decimalsecperfat*decimalnumfatcopies) -1)) 
printf "Fat 0: $decimalressectors - $fat0end \n"
fat1start=$((fat0end+1))
fat1end=$((decimalressectors + (decimalsecperfat*decimalnumfatcopies) - 1))
printf "Fat 1: $fat1start - $fat1end \n"

# Read Number of Root Directory Entries Bytes 17 and 18
hexnumrootdir1=$(xxd -s 17 -l 1 -ps $infilename)
hexnumrootdir2=$(xxd -s 18 -l 1 -ps $infilename)
hexnumrootdir=$hexnumrootdir2$hexnumrootdir1
read decimalnumrootdir < <(echo $((16#$hexnumrootdir)))
printf "The number of root directory entries is $decimalnumrootdir \n"

# The size of the root directory is the number of root directory entries times 32 bytes
decimalsizerootdirectory=$((decimalnumrootdir * 32))
decimalsectorsrootdirectory=$((decimalsizerootdirectory / decimalsectorsize))
decimalclustersrootdirectory=$((decimalsizerootdirectory / decimalclustersize))
printf "The size of the root directory in bytes is $decimalsizerootdirectory \n"
 
# The size of the disk in bytes is at bytes 32 33 34 (number of sectors x sector size) 
hextotalsector1=$(xxd -s 32 -l 1 -ps $infilename)
hextotalsector2=$(xxd -s 33 -l 1 -ps $infilename)
hextotalsector3=$(xxd -s 34 -l 1 -ps $infilename)
hextotalsectors=$hextotalsector3$hextotalsector2$hextotalsector1
decimaltotalsectors=$(printf $((16#$hextotalsectors)))
decimalvolumetotalbytes=$((decimaltotalsectors * decimalsectorsize))
printf "The total size of the disk in bytes is $decimalvolumetotalbytes \n"

# Root Directory Start and End Calculation (The Root Directory End plus 1 is the Name of the Disk eg: mydisk)
decimalrootdirectorystart=$((decimalressectors + decimalsecperfat*decimalnumfatcopies)) 
rootdirectoryend=$((decimalressectors + decimalsecperfat + decimalsecperfat + $sectorsrootdirectory -1))
rootdirectorystartbyte=$((decimalrootdirectorystart * decimalsectorsize))
rootdirectoryendbyte=$((rootdirectoryend * sectorsize))
startofdata=$((rootdirectoryend + 1))

# Skip to the start of the Data Area (the root directory and is always a skip of 128 bytes)
skipvalue=$((rootdirectorystartbyte +128))
diskname=$(xxd -s $((decimalrootdirectorystart * decimalsectorsize)) -l 10 -ps $infilename)       
read asciidiskname < <(echo $diskname | xxd -r -p) 
printf "The disk name is $asciidiskname \n"

# GUO HAO (DEREK) LEE *********************************************************************************************************************************************
# The calculation to find the first byte of the first file metadata line is:
# (reserved sectors times sectorsize) plus (size of fat times number of fats) + 128 which calculates to 127104
metastart=$(( ($decimalressectors*$decimalsectorsize) + ($decimalsizeoffat*$decimalnumfatcopies)  + 128 ))

printf "The first file's metadata begins at byte $metastart \n"

hexfirstfilename=$(xxd -s $metastart -l 8 -ps $infilename)
hexasciifirstfileext=$(xxd -s $(($metastart+8)) -l 3 -ps $infilename)
read asciifirstfilename < <(echo $hexfirstfilename | xxd -r -p)
read asciifirstfileext < <(echo $hexasciifirstfileext | xxd -r -p)

# COMPLETE THIS BY CONVERTING THE FILENAME TO ASCII
# THEN READ THE EXTENSION AND CONVERT TO ASCII
# USE THE VARIABLE NAMES IN THE LINE BELOW
printf "The first filename is $asciifirstfilename.$asciifirstfileext \n\n"

# *********************************************************************************************************************************************

# Current date and time
currentdate=$(date '+%d-%m-%y %H:%M:%S')
printf "The current date and time is: $currentdate\n"

# ************************************************* End Script ***************************************************
