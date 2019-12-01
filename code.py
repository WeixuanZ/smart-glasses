import datetime
import re
import urllib.parse
from base64 import b64encode
from io import BytesIO
from json import dumps, loads
from subprocess import check_call
from textwrap import TextWrapper
from time import sleep

import Adafruit_SSD1306
import RPi.GPIO as GPIO
import requests
from PIL import Image, ImageDraw, ImageFont, ImageOps
from picamera import PiCamera

# with detection mode and OLED support
# photo is stored as a PIL object
# TODO ** auto scroll (draw.textsize may be useful)


# defining variables

# regular expressions
definite_int = re.compile('.*int_\(\d+\)\^\d+.+d\w')
indefinite_int = re.compile('.*int(?!_\(\d+\)\^\d+).+d\w')

# button
GPIO.setmode(GPIO.BCM)  # set the pin numbering system to BCM
button = 23  # the pin that the button is connected to
GPIO.setup(button, GPIO.IN, pull_up_down=GPIO.PUD_UP)  # set up the pin that the button is connected to

# camera
camera = PiCamera()
camera.resolution = (2592, 1944)
camera.color_effects = (128, 128)  # gray scale

# display
RST = None  # Raspberry Pi pin configuration
# 128x64 display with hardware I2C:
disp = Adafruit_SSD1306.SSD1306_128_64(rst=RST)

# initialize library
disp.begin()

# clear the display
disp.clear()
disp.display()

# create blank image with mode '1' for 1-bit color for drawing
width = disp.width
height = disp.height
margin = 5
image = Image.new('1', (width, height))
# get drawing object to draw on image
draw = ImageDraw.Draw(image)

# load fonts
text_font = ImageFont.truetype('Roboto-Bold.ttf', size=16)
small_text_font = ImageFont.truetype('Roboto-Bold.ttf', size=12)
regular_icon_font = ImageFont.truetype('fa-regular-400.ttf', size=20)
solid_icon_font = ImageFont.truetype('fa-solid-900.ttf', size=20)
frame = ImageFont.truetype('frame.ttf', size=120)


# a function that clears the canvas
def clearImg():
    # draw a black filled box to clear the image
    draw.rectangle((0, 0, width, height), outline=0, fill=0)


# function for camera
def image_capture():
    global stream
    stream = BytesIO()
    camera.capture(stream, format='jpeg')  # capture the image to stream
    stream.seek(0)  # "rewind" the stream to the beginning to read its content
    photo = Image.open(stream).rotate(90).crop(
        (1700, 750, 2150, 900))  # creating a PIL Image object, then rotate and crop the image
    photo = ImageOps.autocontrast(photo, cutoff=0, ignore=None)  # redistribute the brightness
    global modified_stream
    modified_stream = BytesIO()  # create a new stream called modified_stream
    photo.save(modified_stream, format="JPEG")  # save the adjusted image to the new steam


# functions for api
def mathpix_api():
    image_uri = str(b64encode(modified_stream.getvalue()))  # encode the image stored in the modified_stream into base64
    image_uri = "data:image/jpg;base64,{}".format(image_uri[2:len(image_uri) - 1])  # formatting the image uri
    r = requests.post("https://api.mathpix.com/v3/latex",
                      data=dumps({'src': image_uri,
                                  'formats': ['wolfram'], 'ocr': ['math', 'text']}),
                      headers={"app_id": "<app id>", "app_key": "app key",
                               "Content-type": "application/json"})
    global string
    string = loads(r.text)  # reformat the returned json string into a Python dictionary

    try:
        string = string['wolfram']
        return True
    except KeyError:
        append('No text recognised')


def has_numbers(input_string):
    return any(char.isdigit() for char in
               input_string)  # check if there is any digit in the input string, returns True if there is at least one


def get_json():
    url = 'https://api.wolframalpha.com/v2/query?&{}&format=plaintext&output=JSON&appid=<apple id>'.format(
        urllib.parse.urlencode({'input': string}))  # convert the string into url format and add it to the request url
    return requests.get(url).json()  # returns the json string


def wolfram_api():
    global string

    # the maths mode (if there are digits)
    if has_numbers(string) is True:
        json_data = get_json()
        json_status = json_data['queryresult']["success"]  # whether the request is a success

        if json_status is True:

            # get the relevant answers
            for each in json_data['queryresult']['pods']:
                title = each['title']
                if title == 'Real solutions' or title == 'Complex solutions' or title == 'Solutions' or title == 'Result' or title == 'Sum' or title == 'Derivative' or title == 'Exact result' or title == 'Decimal form' or title == 'Limit' or title == 'Limit from the left' or title == 'Limit from the right':
                    append(each['title'] + ': ')
                    answers = []
                    for an_answer in each['subpods']:
                        answers.append(an_answer['plaintext'])
                    append(answers)
                # matching the regular expressions
                elif definite_int.match(string) and title == 'Definite integral':
                    append(each['title'] + ': ')
                    append(each['subpods'][0]['plaintext'])
                elif indefinite_int.match(string) and title == 'Indefinite integral':
                    append(each['title'] + ': ')
                    append(each['subpods'][0]['plaintext'])

            if len(answer) == 0:  # the problem is not in the above categories
                append('This problem is not supported')
        else:
            append('Oops! Try Again')  # if the request is not successful

    # the dictionary mode (if there isn't any digit)
    elif has_numbers(string) is False and len(string) != 0:
        string = 'meaning of {}'.format(string)  # formatting the question
        json_data = get_json()
        json_status = json_data['queryresult']['success']
        if json_status is True:
            pods = json_data['queryresult']['pods']
            append(pods[1]['subpods'][0]['plaintext'])
        else:
            append('Oops! Try Again')


# functions for button
def shutdown_confirm():
    draw.text((margin, height / 2 - 15), chr(61457), font=solid_icon_font, fill=255)  # drawing the power off icon
    draw.multiline_text((margin + 30, height / 2 - 30), 'Press to\nConfirm\nShutdown', fill=255, font=text_font,
                        anchor=None, spacing=0, align="left")
    disp.image(image)
    disp.display()


def shutdown():
    clearImg()
    draw.multiline_text((margin, height / 2 - 30), 'Shutting Down\nNow\n...', fill=255, font=text_font, anchor=None,
                        spacing=0, align="center")
    disp.clear()
    disp.display()
    disp.image(image)
    disp.display()
    sleep(0.5)
    disp.clear()
    disp.display()
    check_call(['sudo', 'poweroff'])  # command for shutting down Raspberry Pi


def current_time():
    draw.text((margin, height / 2 - 10), chr(61463), font=regular_icon_font, fill=255)  # draw the clock icon
    draw.multiline_text((margin + 30, height / 2 - 20), datetime.datetime.now().strftime('%Y-%m-%d\n%H:%M'), fill=255,
                        font=text_font, spacing=10,
                        align="center")  # display the current time in the form of 'Year-Month-Day newline Hour-Minute'
    disp.image(image)
    disp.display()
    sleep(2)  # remains on the display for 2 seconds


def detection_mode():
    draw.text((width / 2 - 10, height / 2 - 10), chr(61788), font=solid_icon_font, fill=255)  # drawing the text icon
    disp.image(image)
    disp.display()
    sleep(1)  # remains for 1 second

    while True:
        clearImg()
        draw.text((0, 5), 'b', font=frame, fill=255)  # drawing the frame
        disp.clear()
        disp.display()
        disp.image(image)
        disp.display()

        # camera.start_preview()

        quit_countdown = 0.5  # two consecutive presses must be within 0.5 second to be registered as a double press for existing the detection mode
        quit_state = False  # whether a double press was registered

        global answer
        answer = []  # the list for the final answers, which is emptied every iteration
        global append
        append = answer.append  # for higher efficiency

        GPIO.wait_for_edge(button,
                           GPIO.RISING)  # pausing the programme until the button is pressed (rising edge because the possibility for double press)

        while quit_countdown > 0:
            if GPIO.input(button) == 0:  # if there is another press within the threshold, exist the detection mode
                quit_state = True
                disp.clear()
                disp.display()
                # camera.stop_preview()
                break  # exist the while loop for the detection mode
            quit_countdown -= 0.1
            sleep(0.1)

        if quit_state is False:  # a single press, capture image and run the detection
            # blink the screen indicating the image capture
            clearImg()
            draw.text((0, 5), 'c', font=frame, fill=255)
            disp.clear()
            disp.display()
            disp.image(image)
            disp.display()
            sleep(0.5)
            disp.clear()
            disp.display()

            image_capture()  # capture the image
            # camera.stop_preview()

            clearImg()
            draw.text((width / 2 - 10, height / 2 - 10), chr(62034), font=solid_icon_font,
                      fill=255)  # drawing the hour glass icon
            disp.image(image)
            disp.display()

            try:
                if mathpix_api() is True:  # if there are texts recognised
                    wolfram_api()
            except requests.exceptions.ConnectionError:
                append('No Internect Connection')

            dispText = ''

            for i in range(len(answer)):
                dispText += str(answer[i]) + '\n'
            wrapper = TextWrapper(width=25, replace_whitespace=False,
                                  max_lines=4)  # newline after a maximum of 25 characters, if the text exceeds 4 lines, replace the rest by [...]
            dispText = wrapper.fill(dispText)

            clearImg()
            draw.multiline_text((0, 0), dispText, font=small_text_font, fill=255)  # display the answer
            disp.clear()
            disp.display()
            disp.image(image)
            disp.display()
            sleep(6)  # remains on display for 6 seconds

        else:
            break


# the main loop
while True:
    clearImg()
    press_time = 0  # the amount of time the button is pressed
    shutdowntime_countdown = 3  # another press must be within 3s from the long press to initiate shutdown
    doublepress_countdown = 0.5  # two consecutive presses must be within 0.5s to be registered as a double press
    run_state = False  # whether a double press was registered (i.e. whether the detection mode is entered)

    # pause the programme until the button is pressed (falling edge because the internal pull-up resistor and to prevent registering the press from the previous iteration)
    GPIO.wait_for_edge(button, GPIO.FALLING)

    # time the amount of time the button is pressed
    while GPIO.input(button) == 0:
        press_time += 0.1
        sleep(0.1)

    # if the time pressed is larger than 3 seconds, register as a long press
    if press_time >= 3:
        shutdown_confirm()
        while shutdowntime_countdown > 0:  # checking whether the shutdown is confirmed within the threshold
            if GPIO.input(button) == 0:
                shutdown()
            shutdowntime_countdown -= 0.1
            sleep(0.1)

    # if less than 3 seconds, register as a press (potentially a double press)
    elif 0 < press_time < 3:
        # if there is another press within the double press threshold, register as a double press
        while doublepress_countdown > 0:
            if GPIO.input(button) == 0:
                run_state = True
                detection_mode()  # run the detection mode
            doublepress_countdown -= 0.1
            sleep(0.1)
        # if there isn't a further press, register as a single press
        if run_state is False:
            current_time()

    disp.clear()
    disp.display()
    sleep(0.5)
