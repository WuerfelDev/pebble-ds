# Pebble Offline Dictation Service

This is a replacement dictation service based on Vosk Offline Speech To Text library.

## Options

There are two options near the top of the [code](./app/__init__.py):

* `audio_debug = False`: Enable/Disable the audio debug functionality. All messages are saved as sound files with text, time and language. If enabled, they are listed on \<server\>/audio-debug
* `current_lang = "en-us"`: Set the default language that is used when the server starts. However once a language based subdomain is used, this gets overwritten. To see a list of available language, run `vosk-transcriber --list-languages`.
## How to install

This software relies on the [Speex Python Library](https://pypi.org/project/speex/) which is unfortunately outdated and works only with <=Python 3.7. Therefore you first need to install Python 3.7 on your system. There are plenty of tutorials online.

Installation process
```shell
# Install requirements
sudo apt-get install build-essential libspeex-dev libspeexdsp-dev libpulse-dev ffmpeg

# Clone the project
git clone https://github.com/WuerfelDev/pebble-ds.git
cd pebble-ds
# Create a virtual environment
python3.7 -m venv .venv
source .venv/bin/activate
# Install the required Python modules:
pip install -r requirements.txt
```

## Runnig pebble-ds

You can start the server by running `python app.py`. Make sure that you've activated the .venv beforehand. The server runs on port 443. Be aware that for the first run of every language, it will download the speech model and while it downloads, your dictation will time out.

**Install as service**

The service will start the server automatically when you boot. You want to double check the paths used in the [service](./pebble-ds.service) as they might not be the same as on your system. It assumes "/root/pebble-ds/" as the installed directory.

```shell
# Install service file
sudo cp ./pebble-ds.service /etc/systemd/system/
# Start the service automatic at boot
sudo systemctl enable --now  pebble-ds.service
```

## Setting up your hosting

Since vosk does not automatically switch between multiple languages, you can use subdomains to controll the language used for the detection. For example you can point "en-us.pebble-asr.example.com" and "de.pebble-asr.example.com" to your server and it will select the language accordingly. To see a list of available language, run `vosk-transcriber --list-languages`. Don't worry, if you don't do that it will use the configured language (default: "en-us").

## Prepare Pebble App

In the Pebble app the domain endpoints for external urls are changeable through a configuration link. Rebble has some helper tools for that.

Steps on Rebble Website:

* Login on [rebble.io](https://rebble.io)
* Click on the button on the bottom "I know what I'm doing, show me the options anyway!"
* Change the configuration in:

```json
{
    "config": {
        "voice": {
            "languages": [
                {
                    "endpoint": "YOUR_HOSTNAME_HERE",
                    "six_char_locale": "eng_USA",
                    "four_char_locale": "en_US"
                }
            ],
            "first_party_uuids": [
                ""
            ]
        }
    }
}
```

Change `six_char_locale` and `four_char_locale` to reflect those of your language. This is not the same language code as in your subdomain.

**Warning:** if you write an invalid `six_char_locale` or `four_char_locale` the configuration will be still accepted but won't work while configuring the Pebble app on your phone.
**It fails silently**, no error is showing up. Make sure to use "_" instead of "-".

* Click on "Ok, well, I guess that looks good."
* Open [boot.rebble.io](https://boot.rebble.io) on your phone and run configuration.

If everything has been done correctly, in the Pebble App settings, Dictation section, you should see only the languages that you configured as available. **Be sure to select a language to override the default settings**.

## Resources:
* Vosk: https://github.com/alphacep/vosk-api
* Rebble ASR: https://github.com/pebble-dev/rebble-asr
* Reddit discussion for Rebble Service configuration: https://www.reddit.com/r/pebble/comments/llqdv6/self_hosted_dictation_service/
