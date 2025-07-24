from xml.dom import minidom
import xml.etree.ElementTree as ElementTree
import codecs
import sys
import tomllib
import os
from time import sleep

valid_regions = ['Australia', 'Brazil', 'Canada', 'China', 'Denmark', 'Europe', 'Finland', 'France', 'Germany', 'Greece', 'Italy', 'Japan', 'Korea', 'Mexico', 'Netherlands', 'Norway', 'Russia', 'Scandinavia', 'Spain', 'Sweden', 'United Kingdom', 'Unknown', 'USA', 'World', 'Japan, USA', 'USA, Australia', 'USA, Europe']
valid_languages = ['Cs', 'Da', 'De', 'El', 'En', 'Es', 'Es-XL', 'Fi', 'Fr', 'Fr-CA', 'Hu', 'It', 'Ja', 'Ko', 'Nl', 'No', 'Pl', 'Pt', 'Pt-BR', 'Ru', 'Sv', 'Tr', 'Zh', 'nolang']

print("No-Intro NDS XML Generator v0.1 by kaos\n")

# Check for input file
try:
    file_path = sys.argv[1]
except IndexError:
    file_path = None
    while file_path is None:
        file_path = input("Please enter a file path to use (must end in .nds). ")
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
        print(f"constants.toml tried loading {nds_dat_path} but no file was found. Defaulting to disabled dat usage.")
        ds_dat_loaded = False

# Extract what we can from the gm9 log.
gm9_output_lines = gm9_output.split('\n')
internal_serial = gm9_output_lines[1].split('Product Code : ')[1][0:4]
cart_id = gm9_output_lines[3].split('Cart ID      : ')[1]
save_chip_id = gm9_output_lines[6].split('Save chip ID : ')[1]
dump_date = gm9_output_lines[7].split('Timestamp    : ')[1][:10]
# GM9 or GM9i?
if gm9_output_lines[8].split(' ')[0] == 'GM9i':
    tool = "GodMode9i "+gm9_output_lines[8].split('GM9i Version : ')[1]
else:
    tool = "GodMode9 "+gm9_output_lines[8].split('GM9 Version  : ')[1]

# Prompt for GameHeader input. We need this before we can do NDS dat checks.
gameheader_data = ''
print("Please open GameHeader, load your game, and paste its output here (ctrl-v): ")
while True:
    data = input()
    if data == '':
        break
    else:
        gameheader_data += "\n"+data
        pass

gameheader_filedata = gameheader_data.split("----| Header Data |------------------------------------------------\n")[0].split('\n')
file_size = gameheader_filedata[7].split("Size (Bytes):       ")[1]
dec_crc32 = gameheader_filedata[8].split("CRC32:              ")[1].lower()
dec_md5 = gameheader_filedata[9].split("MD5:                ")[1].lower()
dec_sha1 = gameheader_filedata[10].split("SHA1:               ")[1].lower()
dec_sha256 = gameheader_filedata[11].split("SHA256:             ")[1].lower()

gameheader_encryptdata = gameheader_data.split("----| Encrypted Data |---------------------------------------------\n")[1].split('\n')
enc_crc32 = gameheader_encryptdata[1].split("Encrypted CRC32:    ")[1].lower()
enc_md5 = gameheader_encryptdata[2].split("Encrypted MD5:      ")[1].lower()
enc_sha1 = gameheader_encryptdata[3].split("Encrypted SHA1:     ")[1].lower()
enc_sha256 = gameheader_encryptdata[4].split("Encrypted SHA256:   ")[1].lower()

# Just make sure any extra newlines gameheader throws don't get caught by the next input block
sleep(0.5)

languages = None
special = None
game_name = None
region = None

name_set = False
region_set = False

if ds_dat_loaded:
    # Load NDS dat
    tree = ElementTree.parse(nds_dat_path)
    root = tree.getroot()

    breakout = False
    no_intro_name = None
    for game in root:
        for rom in game.iter('rom'):
            if rom.attrib['sha1'] == dec_sha1 and rom.attrib['size'] == file_size:
                no_intro_name = game.attrib['name']
                no_intro_id = game.attrib['id']
                no_intro_serial = rom.attrib['serial']
                print("Match found in DS dat. \nName:", no_intro_name, "\nNo-Intro ID:", no_intro_id, "\nSHA-1 Hash:", rom.attrib['sha1'], "\nInternal Serial:", no_intro_serial, "\n")
                breakout = True
                break
        if breakout:
            break

    if no_intro_name is not None:
        # Split name into components
        split_name = no_intro_name.split(' (')
        game_name = split_name[0]
        region = split_name[1].split(')')[0]

        try:
            additional = split_name[2]
            if additional[0:2] in valid_languages:
                languages = additional.split(')')[0]
        except IndexError:
            print("Language not listed in dat.")

        name_set = True
        region_set = True
    else:
        print("No match found in DS dat. Please enter data manually.")

if not name_set:
    game_name = input("Enter game name: ")

if region is not None:
    confirm = input(f"Is the region {region} correct? (y/n) ")
    if confirm[0] != 'y':
        region_set = False

if not region_set:
    while True:
        region = input("Enter region: ")
        if region not in valid_regions:
            print("Not a valid region! Please enter region again.")
        else:
            break

language_checked = input("Did you check the languages? (y/n) ")
if language_checked[0] == 'y':
    language_checked = 'yes'
elif language_checked[0] == 'n':
    language_checked = 'no'
else:
    language_checked = 'unk'

if languages is None:
    languages = input("Enter languages (ISO 639-1 format): ")

front_serial = input("\nEnter front serial (starts with NTR- or TWL-): ")
back_serial = input(f"Enter back serial (starts with {internal_serial}): ")
pcb_serial = input("Enter PCB serial (copy: ▼ •): ")

loose_str = input("Is this a loose cart? (y/n): ")
if loose_str[0] == 'y':
    loose = True
    box_serial = ""
    box_barcode = ""
    manual_serial = ""
else:
    loose = False
    box_serial = input("Enter box serials (comma-separated): ")
    box_barcode = input("Enter box barcode (include spaces): ")
    manual_serial = input("Enter manual serials (comma-separated): ")

# Create XML
doc = minidom.Document()

datafile = doc.createElement("datafile")
doc.appendChild(datafile)

game = doc.createElement("game")
game.setAttribute('name', game_name)
datafile.appendChild(game)

archive = doc.createElement("archive")
# archive.setAttribute('clone', 'P')  # clone from parent
archive.setAttribute('name', game_name)
archive.setAttribute('region', region)
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
details.setAttribute('comment1', f'Cart ID: {cart_id}\nSave chip ID: {save_chip_id}')
if manual_serial != "":
    details.setAttribute('comment2', f'Manual serial(s): {manual_serial}')
details.setAttribute('originalformat', 'Decrypted')
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

xml_str = datafile.toprettyxml(indent = "    ")
print("\nGenerated XML:")
print(xml_str)

output_path = "\\".join((file_path.split('\\')[:-1]))+f"\\{game_name} - {dumper} - {dump_date}.xml"

with codecs.open(output_path, "w", "utf-8") as f:
    f.write(xml_str)

print(f"\nXML has been written to {output_path}")
