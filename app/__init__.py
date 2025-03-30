from flask import Flask, request, Response,render_template
from email.mime.multipart import MIMEMultipart
from email.message import Message
import json
from speex import SpeexDecoder
from vosk import Model, KaldiRecognizer, MODEL_LIST_URL
from rnnoise_wrapper import RNNoise
from pydub import AudioSegment
import audioop
import datetime
import os
import requests

audio_debug = False
current_lang = "en-us"

if audio_debug:
    app = Flask(__name__, static_url_path="/audio", static_folder="audio-debug")
    os.makedirs("app/audio-debug", exist_ok=True)
else:
    app = Flask(__name__)


decoder = SpeexDecoder(1)
model = None
rec = None

# Load language list
response = requests.get(MODEL_LIST_URL, timeout=10)
available_languages = {m["lang"] for m in response.json()}

def change_language(lang):
    global model, rec, current_lang
    del model
    del rec
    model = Model(lang=lang)
    rec = KaldiRecognizer(model, 16000)
    rec.SetWords(True)
    rec.SetPartialWords(True)
    current_lang = lang

change_language(current_lang)


try:
    rnnoise = RNNoise("/usr/local/lib/librnnoise.so")
except Exception as e:
    rnnoise = None
    print("RNNoise not found")


@app.route("/heartbeat")
def heartbeat():
    return "asr"

# Only routed if audio_debug is True
def serve_recordings():
    try:
        files = []
        for filename in sorted(os.listdir("app/audio-debug"), reverse=True):
            if not filename.endswith(".wav"):
                continue
            txt_file = os.path.join("app/audio-debug", os.path.splitext(filename)[0] + ".txt")
            if os.path.isfile(txt_file):
                text = open(txt_file, "r").read().strip()
                try:
                    files.append({"wav": filename, "text": text})
                    continue
                except OSError as t:
                    print("Unable to load txt file", t)
                    pass
            files.append({"wav": filename})
    except OSError as e:
        print("Unable to handle files", e)
        files = []
    return render_template("audio.html", entries=files)

# Route /audio-debug
if audio_debug:
    app.add_url_rule("/audio-debug", view_func=serve_recordings)


# From: https://github.com/pebble-dev/rebble-asr/blob/37302ebed464b7354accc9f4b6aa22736e12b266/asr/__init__.py#L27
def parse_chunks(stream):
    boundary = b'--' + request.headers['content-type'].split(';')[1].split('=')[1].encode(
        'utf-8').strip()  # super lazy/brittle parsing.
    this_frame = b''
    while True:
        content = stream.read(4096)
        this_frame += content
        end = this_frame.find(boundary)
        if end > -1:
            frame = this_frame[:end]
            this_frame = this_frame[end + len(boundary):]
            if frame != b'':
                try:
                    header, content = frame.split(b'\r\n\r\n', 1)
                except ValueError:
                    continue
                yield content[:-2]
        if content == b'':
            break


@app.post("/NmspServlet/")
def asr():
    stream = request.stream

    # Get language from subdomain
    lang = request.host.split('.', 1)[0]
    if current_lang != lang and lang in available_languages:
        change_language(lang)

    # Parsing request
    chunks = list(parse_chunks(stream))[3:]  # 0 = Content Type, 1 = Header?

    # Preparing response
    # From: https://github.com/pebble-dev/rebble-asr/blob/37302ebed464b7354accc9f4b6aa22736e12b266/asr/__init__.py#L92
    # Now for some reason we also need to give back a mime/multipart message...
    parts = MIMEMultipart()
    response_part = Message()
    response_part.add_header('Content-Type', 'application/JSON; charset=utf-8')

    try:
        if audio_debug:
            complete = AudioSegment.empty()

        # Dirty way to remove initial/final button click
        if len(chunks) > 15:
            chunks = chunks[12:-3]
        for chunk in chunks:
            decoded = decoder.decode(chunk)
            # Boosting the audio volume
            decoded = audioop.mul(decoded, 2, 6)
            audio = AudioSegment(decoded, sample_width=2, frame_rate=16000, channels=1)
            if rnnoise:
                audio = rnnoise.filter(audio[0:10]) + rnnoise.filter(audio[10:20])
            # Transcribing audio chunk
            rec.AcceptWaveform(audio.raw_data)
            if audio_debug:
                complete += audio

        if audio_debug:
            identifier = f"app/audio-debug/pbl-debug-{datetime.datetime.now().isoformat()}-{current_lang}"
            complete.export(out_f=identifier + ".wav", format="wav")
        final = json.loads(rec.Result())

        if final["text"]:
            output = []
            for partial in final["result"]:
                output.append({'word': partial["word"], 'confidence': str(partial["conf"])})
            output[0]['word'] += '\\*no-space-before'
            output[0]['word'] = output[0]['word'][0].upper() + output[0]['word'][1:]
            response_part.add_header('Content-Disposition', 'form-data; name="QueryResult"')
            response_part.set_payload(json.dumps({
                'words': [output],
            }))
            if audio_debug:
                try:
                    open(identifier + ".txt", "w").write(final["text"])
                except OSError as e:
                    print("Unable to write file", e)
        else:
            print("No words detected")
            response_part.add_header('Content-Disposition', 'form-data; name="QueryRetry"')
            response_part.set_payload(json.dumps({
                "Cause": 1,
                "Name": "AUDIO_INFO",
                "Prompt": "Sorry, speech not recognized. Please try again."
            }))
    except Exception as e:
        print("Error occurred:", str(e))
        response_part.add_header('Content-Disposition', 'form-data; name="QueryRetry"')
        response_part.set_payload(json.dumps({
            "Cause": 1,
            "Name": "AUDIO_INFO",
            "Prompt": "Error while decoding incoming audio."
        }))

    # Closing response
    # From: https://github.com/pebble-dev/rebble-asr/blob/37302ebed464b7354accc9f4b6aa22736e12b266/asr/__init__.py#L113
    parts.attach(response_part)
    parts.set_boundary('--Nuance_NMSP_vutc5w1XobDdefsYG3wq')
    response = Response('\r\n' + parts.as_string().split("\n", 3)[3].replace('\n', '\r\n'))
    response.headers['Content-Type'] = f'multipart/form-data; boundary={parts.get_boundary()}'

    # Resetting Recognizer
    rec.Reset()
    return response
