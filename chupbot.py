"""
Chupbot phase 1: shitty images and limited repitoire
author: Nate Dimick
"""
import tweepy as tp 
import json
from PIL import Image
import numpy as np
from colormath.color_diff import delta_e_cie2000
from colormath.color_objects import LabColor, sRGBColor
from colormath.color_conversions import convert_color
from os import sep
from os.path import dirname, realpath
import sys
import pickle
from random import sample
from datetime import datetime, date, time
from time import sleep
from platform import system
import socket
import traceback

def get_script_path():
    return dirname(realpath(sys.argv[0]))

letters = 'abcdefghijklmnopqrstuvwxyz1234567890'
font = {}
with open(get_script_path() + sep + 'chars.json', 'r') as f:
    font = json.load(f)
    cmap = {}
    for c, box in zip(letters, font):
        cmap[c] = box
    font = cmap

def put_word_on_area(base_img, word, area, slope=0, text=[20,30], color=[0,0,0]):
    # base_img: an Image
    # word: a string
    # area: 4 tuple box
    raw_text = Image.open(get_script_path() + sep + "images" + sep + 'font.jpg')
    x = area[0]
    y = area[1]
    s = slope
    for l in word: 
        char = raw_text.crop(font[l])
        char = char.resize([text[0], text[1]], resample=Image.BICUBIC)
        char = replace_color3(char, [0,0,0], color, tolerance=255)
        base_img.paste(char, [x, y - s])
        x += text[0] + 2
        s += slope

def replace_color3(image, color, replacement, tolerance):
    # make image a np array to easily edit it
    pic = np.array(image)
    # get the LabColor of the target color to replace
    lcolor = sRGBColor(color[0], color[1], color[2])
    lcolor = convert_color(lcolor, LabColor)
    diff_store = {}
    for y in range(len(pic)):
        for x in range(len(pic[0])):
            pixel = pic[y, x]
            diff = diff_store.get(tuple(pixel), -1)
            if diff < 0:
                diff = color_distance(lcolor, tuple(pixel))
                diff_store[tuple(pixel)] = diff
            if diff < tolerance:
                err = []
                for v in range(3):
                    err.append(pixel[v] - color[v])
                for i in range(3):
                    if replacement[i] + err[i] > 255:
                        pic[y,x,i] = 255
                    elif replacement[i] + err[i] < 0:
                        pic[y,x,i] = 0
                    else: 
                        pic[y,x,i] = replacement[i] + err[i]

    return Image.fromarray(pic)


def color_distance(c1, c2):
    # finds difference between a LabColor (assumed to be constant through a loop) and an rgb color
    color1 = c1
    color2 = c2
    color2 = sRGBColor(color2[0], color2[1], color2[2])
    color2 = convert_color(color2, LabColor)
    de = delta_e_cie2000(color1, color2)
    return de

def brand(image, text):
    put_word_on_area(image, text, [150, 200, 260, 230])

def flavor(image, text, color):
    put_word_on_area(image, text, [114, 250, 200, 290], slope=-1, text=[20, 32], color=color)
    image = sauce(image, color)
    return image

def sauce(image, color):
    image = replace_color3(image, [250, 188, 129], color, tolerance=25)
    image = replace_color3(image, [228, 215, 183], color, tolerance=25)
    image = replace_color3(image, [240, 235, 200], color, tolerance=20)

    return image

def turn_word_to_color(word, cap=True):
    with open(get_script_path() + sep + 'synesthesia.json', 'r') as f:
        colors = json.load(f)
    wc = []
    for l in word.lower(): 
        wc.append(colors[l])

    dominant_color = wc[0]
    err = [0,0,0]
    for x in range(1, len(word)):
        l = word[x]
        for y in range(3):
            e = colors[l][y] - dominant_color[y]
            err[y] += e

    for i in range(3):
        dominant_color[i] += err[i]
        if not cap:
            dominant_color[i] = dominant_color[i] % 255
        else:
            if dominant_color[i] < 0:
                dominant_color[i] = 0
            elif dominant_color[i] > 255:
                dominant_color[i] = 255
        
    return dominant_color
    
def generate_tweet(api):
    with open(get_script_path() + sep + 'words.pickle', 'rb') as f:
        im = Image.open(get_script_path() + sep + 'images' + sep + 'mayochup_edit.jpg')
        words = pickle.load(f)
        flavors = words[0]
        brands = words[1]

        todays_flavor = sample(flavors, 1)[0] 
        todays_brand = sample(brands, 1)[0]
        chup = turn_word_to_color(todays_flavor)
        with open(get_script_path() + sep + 'skeletons.json', 'r') as f2:
            statuses = json.load(f2)
            template = sample(statuses, 1)[0]
        if system() == 'Linux':
            bot_api.send_direct_message(creds['owner'], 'new tweet incoming: {}-{}-{}'.format(todays_brand, todays_flavor, chup))

        brand(im, todays_brand)
        im = flavor(im, todays_flavor, chup)
        im.save(get_script_path() + sep + 'images' + sep + 'tweetthis.jpg')
        
        return template.format(todays_brand, todays_flavor)


def bot_loop(api, debug=False):
    tweet_hour = 9
    while True:
        if tweet_hour <= datetime.today().hour:
            status = generate_tweet(api)
            if not debug:
                api.update_with_media(get_script_path() + sep + 'images' + sep + 'tweetthis.jpg', status)
            else:
                print(status)
            if tweet_hour == 9:
                tweet_hour = 15
            else:
                tweet_hour = 9

    sleep(240)


if __name__ == "__main__":
    # get credentials
    creds = json.load(open(get_script_path() + sep + 'tokens.json', 'r'))  # NOTE that this file is not included in the repo for security purposes
    auth = tp.OAuthHandler(creds['api_key'], creds['api_secret'])
    auth.set_access_token(creds['access'], creds['access_secret'])
    bot_api = tp.API(auth)

    # only notify owner that bot is up if it is on a linux machine - (this is a dead giveaway that I'm writing this on windows and running it on a linux based os)
    if system() == 'Linux':
        bot_api.send_direct_message(creds['owner'], 'as of {}:{} chupbot is running on IP {}'.format(datetime.now().hour, datetime.now().minute, socket.gethostbyname(socket.gethostname())))

    try:
        bot_loop(bot_api) # set debug=True for testing
    except KeyboardInterrupt:
        print('exited normally')
    except Exception as e:
        # this is where it would DM me 
        print('an {} occurred'.format(e))
        traceback.print_exc()
        if system() == 'Linux':
            bot_api.send_direct_message(creds['owner'], '{} occured and I shutdown. Please restart me and program better'.format(e))
"""
notes on the color synthesis:
to mod or to cap? 
mod might lead to more true colors (nate == yellow)
cap leads to fun colors (nate == pink)
examples (if two, first is mod, second is cap)
shale: pale blue, bright yellow
aaron: jade both ways
talya: pastel violet, dark yellow
roman: pastel yellow, green
ryan: same as roman
tess: brown, purple
chuck: dull red both ways
larry: olive grey, maroon
kerry: dull pink, magenta
"""