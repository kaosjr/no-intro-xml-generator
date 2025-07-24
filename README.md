# no-intro-xml-generator
No-Intro XML Submission Generator in Python

## Note
This script is in very early development. Issues are expected. Please report either via GitHub's issue tracker or using @kaosjr on Discord.

## Setup
### General Requirements
For all scripts:
- Python 3.11 or later
- Windows (may expand to Linux eventually)

### nds.py
Dumps to be processed should be dumped with either [GodMode9](https://github.com/d0k3/GodMode9) or [GodMode9i](https://github.com/DS-Homebrew/GodMode9i). The .txt file from the dump is currently required and should have the same name as the .nds file, just with a .txt extension. (This may become optional later.)

Additional requirements (to be placed in the same folder as the script):
- [NDecrypt](https://github.com/SabreTools/NDecrypt/releases/tag/0.3.2) (exe format)
- [config.json](https://gist.github.com/Dimensional/82f212a0b35bcf9caaa2bc9a70b3a92a) with the NitroEncryptionData key for encryption

## Usage
### nds.py
Run using `python nds.py <path>`, drag the .nds file onto the script, or omit the path to be prompted when the program starts.

Follow the instructions in the script.

On output, an XML file will be generated in the same location as your .nds file.