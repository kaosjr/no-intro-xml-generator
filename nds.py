program_version = "v0.1.5a"

from xml.dom import minidom
import xml.etree.ElementTree as ElementTree
import codecs
import sys
import tomllib
import os
import shutil
import zlib
import hashlib
import subprocess
import tempfile
import re

from db import *

valid_front_serial_headers = ["NTR", "TWL", "PRE"]

print(f"No-Intro NDS XML Generator {program_version} by kaos\n")

# Check for ndecrypt. I can probably have this clone it in but that requires dealing with More Things than I am willing to deal with right now.
# TODO: This is windows-only. If someone is interested I'll probably make it work on Linux eventually.
ndecrypt_path = "NDecrypt.exe"
if not os.path.isfile(ndecrypt_path):
    input("NDecrypt.exe not found in folder. \nPlease download the latest release from https://github.com/SabreTools/NDecrypt/releases and place the .exe into the same folder as this script. \nPress enter to exit.")
    sys.exit(1)

# Check for config.json for NDecrypt. Don't bother checking the keys, if they made one it's probably fine.
if not os.path.isfile("config.json"):
    input("config.json not found in folder. \nPlease place into the same folder as this script. You can generate a config.json using this script: https://gist.github.com/Dimensional/82f212a0b35bcf9caaa2bc9a70b3a92a. \nPress enter to exit.")
    sys.exit(1)

# Check for input file
try:
    file_path = sys.argv[1]
except IndexError:
    file_path = None
    while file_path is None:
        file_path = input("Please enter a file path to use (must end in .nds). ")
        if file_path[0] == '"':  # remove extraneous " if necessary (windows copy to path adds these which work fine in cmd but not in python)
            file_path = file_path[1:-1]
        if not os.path.isfile(file_path):
            print("Invalid file path. Try again.")
            file_path = None

# Check for dump logs
try:
    gm9_output_path = file_path[:-3]+"txt"
    with codecs.open(gm9_output_path) as f:
        gm9_output = f.read()
except FileNotFoundError:
    input(f"No file found: {file_path[:-3]}txt. Make sure you have a GM9 log in the same directory as the file you are trying to check. Press enter to exit.")
    sys.exit(1)

# Load constants file
try:
    with open("constants.toml", "rb") as cf:
        constants = tomllib.load(cf)
except FileNotFoundError:
    input("No constants.toml file found. Please rename default_constants.toml to constants.toml and fill in the parameters. Press enter to exit.")
    sys.exit(1)

# Load data from constants file
dumper = constants['dumper']
nds_dat_path = ""
ds_dat_loaded = constants['use_nds_dat']
if ds_dat_loaded is True:
    nds_dat_path = constants['nds_dat_path']
    # Check if it's actually there
    if not os.path.isfile(nds_dat_path):
        print(f"constants.toml tried loading dat file {nds_dat_path} but no file was found. Defaulting to disabled dat usage.")
        ds_dat_loaded = False

# Extract what we can from the GM9/GM9i log.
# This is a mess due to the inconsistency between the two when there is no save type.
gm9_output_lines = gm9_output.split('\n')
try:
    internal_serial = gm9_output_lines[1].split('Product Code : ')[1][0:4]
    revision = gm9_output_lines[2].split('Revision     : ')[1]
    cart_id = gm9_output_lines[3].split('Cart ID      : ')[1]
    platform = gm9_output_lines[4].split('Platform     : ')[1]
    save_type = gm9_output_lines[5].split('Save Type    : ')[1]
    if save_type == 'NONE':
        # All the rest of the lines in the file get shifted, but only on GM9i dumps.
        if gm9_output_lines[6] == 'Save chip ID : <none>':  # GM9
            save_chip_id = None
            if gm9_output_lines[7][0:15] == 'Padding Byte : ':
                # gm9 2.2.0 or > log
                padding_byte = int(f"0x{gm9_output_lines[7][15:]}", 16)  # unused
                dump_date = gm9_output_lines[8].split('Timestamp    : ')[1][:10]
                tool = "GodMode9 " + gm9_output_lines[9].split('GM9 Version  : ')[1]
            else:
                dump_date = gm9_output_lines[7].split('Timestamp    : ')[1][:10]
                tool = "GodMode9 " + gm9_output_lines[8].split('GM9 Version  : ')[1]
        else:  # GM9i
            save_chip_id = None
            dump_date = gm9_output_lines[6].split('Timestamp    : ')[1][:10]
            tool = "GodMode9i " + gm9_output_lines[7].split('GM9i Version : ')[1]
    else:
        # GM9 or GM9i?
        if gm9_output_lines[8][0:4] == 'GM9i':
            tool = "GodMode9i "+gm9_output_lines[8].split('GM9i Version : ')[1]
            dump_date = gm9_output_lines[7].split('Timestamp    : ')[1][:10]
            save_chip_id = gm9_output_lines[6].split('Save chip ID : 0x')[1]  # cut off 0x
        else:
            save_chip_id = gm9_output_lines[6].split('Save chip ID : ')[1]  # doesn't have 0x
            if gm9_output_lines[7][0:15] == 'Padding Byte : ':
                # gm9 2.2.0 or > log
                padding_byte = int(f"0x{gm9_output_lines[7][15:]}", 16)  # unused
                dump_date = gm9_output_lines[8].split('Timestamp    : ')[1][:10]
                tool = "GodMode9 " + gm9_output_lines[9].split('GM9 Version  : ')[1]
            else:
                dump_date = gm9_output_lines[7].split('Timestamp    : ')[1][:10]
                tool = "GodMode9 "+gm9_output_lines[8].split('GM9 Version  : ')[1]
except IndexError as e:
    input(f"Error handling GM9/GM9i log: {e}. \nPress enter to exit.")
    sys.exit(1)

# Get decrypted hashes using built-in python functionality.
print("\nGenerating decrypted hashes.")
with open(file_path, 'rb') as f:
    # CRC32 implementation from https://stackoverflow.com/a/58141165, extended to do all comps at the same time
    temp_crc32 = 0
    md5_func = hashlib.md5()
    sha1_func = hashlib.sha1()
    sha256_func = hashlib.sha256()
    while True:
        sample = f.read(65536)
        if not sample:  # no more data
            break
        temp_crc32 = zlib.crc32(sample, temp_crc32)
        md5_func.update(sample)
        sha1_func.update(sample)
        sha256_func.update(sample)
    dec_crc32 = ("%08X" % (temp_crc32 & 0xFFFFFFFF)).lower()
    dec_md5 = md5_func.hexdigest()
    dec_sha1 = sha1_func.hexdigest()
    dec_sha256 = sha256_func.hexdigest()

# print(f"{dec_crc32}\n{dec_md5}\n{dec_sha1}\n{dec_sha256}")

# Prepare for using ndecrypt.
# Main issues:
#   NDecrypt does encryption/decryption in-place, so we need to copy the file first to avoid overwriting the actual dump file.
#   NDS files are up to 512MB in size, so this may take a bit. (Warn user.)
#   No filename can be specified for the hash file, it just inherits the name of the original file but with .hash, which is kinda silly. Would be nice if you could just pipe the output.
# TODO: This is windows-only again.

# Copy to a temporary location (with overwrite).
file_name = os.path.basename(file_path)
temp_dir_loc = os.path.realpath(tempfile.gettempdir())
temp_loc = f'{temp_dir_loc}\\nointroxml\\{file_name}'
hashfile_loc = f"{temp_loc}.hash"
print("Copying file to temporary directory, this may take a moment.")
if not os.path.exists(f"{temp_dir_loc}\\nointroxml"):
    os.mkdir(f"{temp_dir_loc}\\nointroxml")
shutil.copyfile(file_path, temp_loc)

# Run ndecrypt on the new file.
print("Generating encrypted hashes.")
subprocess.run(f'NDecrypt.exe e -h "{temp_loc}"', stdout=subprocess.DEVNULL)
with open(hashfile_loc) as enc_hashfile:
    file_size = enc_hashfile.readline().split(': ')[1][:-1]
    enc_crc32 = enc_hashfile.readline().split(': ')[1][:-1]
    enc_md5 = enc_hashfile.readline().split(': ')[1][:-1]
    enc_sha1 = enc_hashfile.readline().split(': ')[1][:-1]
    enc_sha256 = enc_hashfile.readline().split(': ')[1][:-1]

# Delete temporary files.
if os.path.exists(temp_loc):
    os.remove(temp_loc)
if os.path.exists(hashfile_loc):
    os.remove(hashfile_loc)

# print(f"{file_size}\n{enc_crc32}\n{enc_md5}\n{enc_sha1}\n{enc_sha256}")

languages = None
special = None
game_name = None
region = None
no_intro_region = None
no_intro_id = None

name_set = False
region_set = False

# Check the loaded No-Intro DAT file for a match if enabled.
if ds_dat_loaded:
    tree = ElementTree.parse(nds_dat_path)
    root = tree.getroot()

    breakout = False  # this sucks but doubly-nested for loops need shenanigans to quick exit
    no_intro_name = None
    # Iterate through DAT
    for game in root:
        for rom in game.iter('rom'):
            # Look for matching sha1 and serial - should practically never be a collision. (Most games don't seem to have sha256 in the dat)
            if rom.attrib['sha1'] == dec_sha1 and rom.attrib['size'] == file_size:
                no_intro_name = game.attrib['name']
                no_intro_id = game.attrib['id']
                no_intro_serial = rom.attrib['serial']
                print("\nMatch found in DS dat. \nName:", no_intro_name, "\nNo-Intro ID:", no_intro_id, "\nSHA-1 Hash (decrypted):", rom.attrib['sha1'], "\nInternal Serial:", no_intro_serial, "\n")
                breakout = True
                break
        if breakout:
            break

    # found match
    if no_intro_name is not None:
        # Split name into components
        split_name = no_intro_name.split(' (')
        game_name = split_name[0]
        no_intro_region = split_name[1].split(')')[0]

        try:
            additional = split_name[2]
            #if additional.split(')')[0] in valid_languages:
            languages = additional.split(')')[0]
            # TODO: Handle special tags. It's too annoying to bother right now. NDSi Enhanced is the important one, and the gm9 logs tells us if that's what we have.
        except IndexError:
            pass
            # print("Language not listed in dat.")

        name_set = True
        region_set = True
    else:
        print("\nNo match found in DS dat (could be bad dump or new dump, check online DAT info). Please enter data manually.")
        print(f"\nDecrypted hashes: \nCRC-32: {dec_crc32}\nMD5: {dec_md5}\nSHA-1: {dec_sha1}\nSHA-256: {dec_sha256}")
        print(f"\nInternal serial: {internal_serial}\nRevision: {revision}")

# Manual entries
# Don't force the user to enter some data if the DAT data was found.

if not name_set:
    game_name = input("\nEnter game name: ")

# Dump region may be different from archive region (ex. Canada releases are often US carts, but Canada boxes).
if no_intro_region is not None:
    if no_intro_region in multi_regions:  # Must confirm specific dump region; skip asking.
        print("Please set the region for this specific dump.")
        region_set = False
    else:  # Ask if dump region matches. If it does just set it and skip entering again, otherwise ask.
        confirm = input(f"Is the region {no_intro_region} correct? (y/n) ")
        if confirm[0] == 'y':
            region = no_intro_region
        else:
            region_set = False

if not region_set:
    while True:
        region = input("Enter region: ")
        if region not in valid_regions:
            print("Not a valid region! Please enter region again.")
        else:
            break

language_checked = None
if no_intro_id is not None:  # force a language check if new dump
    while language_checked is None:
        language_checked = input("Did you check the languages? (y/n) ")
        if language_checked[0] == 'y':
            language_checked = 'yes'
        elif language_checked[0] == 'n':
            language_checked = 'no'
            if languages is None:
                languages = ""  # leave language field blank, but don't prompt to enter a language
        else:
            language_checked = None
            print("Invalid selection. Please enter again.")
else:
    print("For new dumps, language entry is required.")
    language_checked = 'yes'

if languages is None:
    while languages is None:
        languages = input("Enter languages (ISO 639-1 format), comma-separated (no spaces): ")
        lang_to_check = languages.split(',')
        for lang in lang_to_check:
            if lang not in valid_languages:
                print("Invalid language, please enter again.")
                languages = None
elif languages != "" and language_checked != 'no':
    confirm = input(f"Are the languages {languages} correct? (y/n) ")
    if confirm[0] == 'y':
        pass
    else:
        languages = input("Enter languages (ISO 639-1 format), comma-separated (no spaces): : ")

front_serial = None
while front_serial is None:
    front_serial = input(f"\nEnter front serial (should start with one of {str(valid_front_serial_headers)[1:-1]}): ")
    if front_serial[0:3] not in valid_front_serial_headers:
        print(f"Invalid front serial, must start with one of {str(valid_front_serial_headers)[1:-1]}. Please enter again.")
        front_serial = None

# The back serial has a standard format but there are exceptions. Easier to just not do sanity checks.
back_serial = input(f"Enter back serial (starts with {internal_serial}): ")
# The PCB serial has a semi-standard format but there are lots of exceptions. Easier to just not do sanity checks.
pcb_serial = input("Enter PCB serial (copy: ▼ •): ")

loose_str = input("Is this a loose cart? (y/n): ")
if loose_str[0] == 'y':
    loose = True
    box_serial = ""
    box_barcode = ""
    manual_serial = ""
else:
    loose = False
    # Serials can be basically any format, so...
    box_serial = input("Enter box serial(s) (comma-separated), or enter if no serial present: ")
    # Barcodes must be only numbers.
    box_barcode = None
    while box_barcode is None:
        box_barcode = input("Enter box barcode (include spaces), or enter if no barcode present: ")
        # https://stackoverflow.com/a/20544434
        if box_barcode != "" and not re.match("^ *[0-9][0-9 ]*$", box_barcode):
            print("Box barcode must be blank, or only contain digits and spaces. Please enter again.")
            box_barcode = None
    manual_serial = input("Enter manual serial(s) (comma-separated), or enter if no serial present: ")

# Create XML
doc = minidom.Document()

datafile = doc.createElement("datafile")
doc.appendChild(datafile)

game = doc.createElement("game")
game.setAttribute('name', game_name)
datafile.appendChild(game)

archive = doc.createElement("archive")
if no_intro_id is not None:  # use existing DAT id if verification
    archive.setAttribute('number', no_intro_id)
archive.setAttribute('name', game_name)
if no_intro_region is not None:  # if verification, use existing no-intro region
    archive.setAttribute('region', no_intro_region)
else:  # new dump, set region for both dump and archive
    archive.setAttribute('region', region)
if revision != '0':
    archive.setAttribute('version1', f"Rev {revision}")
if platform == 'DSi Enhanced':
    archive.setAttribute('special1', f"NDSi Enhanced")
archive.setAttribute('languages', languages)
archive.setAttribute('langchecked',language_checked)
game.appendChild(archive)

source = doc.createElement("source")
game.appendChild(source)

details = doc.createElement("details")
details.setAttribute('section', 'Trusted Dump')  # no-intro verifications are always 'trusted dump'
details.setAttribute('d_date', dump_date)
details.setAttribute('d_date_info', '1')  # dump date checked
details.setAttribute('r_date', '')  # not sure what release date is? I think it's a scene thing
details.setAttribute('r_date_info', '0')  # release date not checked
details.setAttribute('dumper', dumper)
details.setAttribute('project', 'No-Intro')
details.setAttribute('tool', tool)
comment2 = f"Cart ID: {cart_id}"
if save_chip_id is not None:
    comment2 += f"\nSave chip ID: {save_chip_id}"
if manual_serial != "":
    comment2 += f"\nManual serial(s): {manual_serial}"
details.setAttribute('comment2', comment2)
details.setAttribute('originalformat', 'Decrypted')
details.setAttribute('region', region)  # this dump's region specifically
source.appendChild(details)

serials = doc.createElement("serials")
serials.setAttribute('media_serial1', front_serial)
serials.setAttribute('media_serial2', back_serial)
serials.setAttribute('pcb_serial', pcb_serial)
if not loose:
    if box_serial != "":
        serials.setAttribute('box_serial', box_serial)
    if box_barcode != "":
        serials.setAttribute('box_barcode', box_barcode)
source.appendChild(serials)

decrypted_file = doc.createElement("file")
decrypted_file.setAttribute('format', 'Decrypted')
decrypted_file.setAttribute('extension', 'nds')
decrypted_file.setAttribute('size', file_size)
decrypted_file.setAttribute('crc32', dec_crc32)
decrypted_file.setAttribute('md5', dec_md5)
decrypted_file.setAttribute('sha1', dec_sha1)
decrypted_file.setAttribute('sha256', dec_sha256)
decrypted_file.setAttribute('serial', internal_serial)
source.appendChild(decrypted_file)

encrypted_file = doc.createElement("file")
encrypted_file.setAttribute('format', 'Encrypted')
encrypted_file.setAttribute('extension', 'nds')
encrypted_file.setAttribute('size', file_size)
encrypted_file.setAttribute('crc32', enc_crc32)
encrypted_file.setAttribute('md5', enc_md5)
encrypted_file.setAttribute('sha1', enc_sha1)
encrypted_file.setAttribute('sha256', enc_sha256)
encrypted_file.setAttribute('serial', internal_serial)
source.appendChild(encrypted_file)

xml_str = doc.toprettyxml(indent = "    ", encoding="utf-8")
print("\nGenerated XML:")
print(xml_str.decode("utf-8"))

# TODO: Yeah this is windows-only.
output_path = "\\".join((file_path.split('\\')[:-1]))+f"\\{game_name} - {dumper} - {dump_date}.xml"

with codecs.open(output_path, 'wb') as f:
    # noinspection PyTypeChecker
    f.write(xml_str)

input(f"\nXML has been written to {output_path}. Press enter to exit.")
