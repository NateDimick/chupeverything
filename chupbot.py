"""
Chupbot phase 2: chup looks fine but must looks like shit
author: Nate Dimick
"""
import tweepy as tp 
import json
from PIL import Image, ImageDraw
import numpy as np
from colormath.color_diff import delta_e_cie2000
from colormath.color_objects import LabColor, sRGBColor
from colormath.color_conversions import convert_color
from os import sep
from os.path import dirname, realpath, join
import sys
from random import sample
from datetime import datetime, date, time
from time import sleep
from platform import system
import socket
import traceback

def get_script_path():
    return dirname(realpath(sys.argv[0]))

def get_json(filename, mode='r'):
    return open(join(get_script_path(), "json", filename), mode)

letters = 'abcdefghijklmnopqrstuvwxyz1234567890'
font = {}
with get_json("chars.json") as f:
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
        char = replace_color3(char, [0,0,0], color, tolerance=200, mode='w')
        base_img.paste(char, [x, y - s])
        x += text[0] + 2
        s += slope

def replace_color3(image, color, replacement, tolerance, mode):
    """
    replaces all pixels that are within the tolerance of cie2000 color distance from the given color with the replacement color, altered to reflect the difference
    """
    # make image a np array to easily edit it
    pic = np.array(image)
    # get the LabColor of the target color to replace
    lcolor = sRGBColor(color[0], color[1], color[2])
    lcolor = convert_color(lcolor, LabColor)
    try:
        with get_json("color_diffs.json") as f:
            diff_store = json.load(f)
    except:
        diff_store = {}  # store all color differences to that some claculations don't have to repeated. Dynamic programming FTW. TODO: store this to a file to make repeated operations faster. 
    for y in range(len(pic)):
        for x in range(len(pic[0])):                          # iterate through all pixels in the image
            pixel = pic[y, x]
            diff = diff_store.get(str(tuple(pixel)) + mode, -1)           # get the difference. -1 if no difference exits yet. 
            if diff < 0:
                diff = color_distance(lcolor, tuple(pixel))   # calculate the difference and store it. 
                diff_store[str(tuple(pixel)) + mode] = diff
            if diff < tolerance:                              # if the color difference/ distance is less than the given tolerance
                err = []
                for v in range(3):
                    err.append(pixel[v] - color[v])           # calculate the error of the to be replaced pixel from the target color
                bc = better_color(replacement, err, mode=4)   # get the "better color" in what i call value cap mode
                pic[y, x] = np.array(bc)
    with get_json("color_diffs.json", mode='w') as f:
        json.dump(diff_store, f)
    return Image.fromarray(pic)


def color_distance(c1, c2):
    # finds difference between a LabColor (assumed to be constant through a loop) and an rgb color
    color1 = c1
    color2 = c2
    color2 = sRGBColor(color2[0], color2[1], color2[2])
    color2 = convert_color(color2, LabColor)
    de = delta_e_cie2000(color1, color2)
    return de

def better_color(color, error, mode=1, debug=False):
    """
    chooses the better resulting color and error combination - to cap the sum of original and error at 0 and 255 or to allow overflow 
    modes: 
    1 = larger chroma value (default)
    2 = least rgb error
    3 = mod only (c + e) % 255
    4 = cap only 
    """
    result = [c + e for c, e in zip(color, error)]
    mod = [c % 255 for c in result]
    cap = [c for c in result]
    for i in range(len(cap)):
        if cap[i] > 255:
            cap[i] = 255
        if cap[i] < 0:
            cap[i] = 0
    if mode == 1:
        mod_chroma = max(mod) - min(mod)
        cap_chroma = max(cap) - min(cap)
        if mod_chroma > cap_chroma:
            result = mod
        else:
            result = cap
    elif mode == 2:
        mod_err = sum(m - c for m, c in zip(mod, color))
        cap_err = sum(a - c for a, c in zip(cap, color))
        if mod_err < cap_err:
            result = mod
        else:
            result = cap
    elif mode == 3:
        result = mod
    elif mode == 4:
        result = cap

    if debug:
        print("input {}, got mod{} and cap{}, chose {}".format(color, mod, cap, result))
        vis = Image.new('RGB', [400, 400])
        vd = ImageDraw.Draw(vis)
        vd.rectangle([0, 0, 200, 400], fill=tuple(color))
        vd.rectangle([200, 0, 400, 200], fill=tuple(mod))
        vd.rectangle([200, 200, 400, 400], fill=tuple(cap))
        vis.show()
    return result

def brand(image, bname, sauce_type):
    if sauce_type == 'must':
        put_word_on_area(image, bname, [160, 200, 240, 230], text=[15,30])
    else:
        put_word_on_area(image, bname, [150, 200, 260, 230])

def flavor(image, text, color, sauce_type):
    if sauce_type == 'must':
        put_word_on_area(image, text, [120, 253, 195, 285], slope=-1, text=[17, 32], color=color)
    else:
        put_word_on_area(image, text, [114, 250, 200, 290], slope=-1, text=[20, 32], color=color)
    image = sauce(image, color, sauce_type)
    return image

def sauce(image, color, sauce):
    if sauce == 'chup':
        image = replace_color3(image, [245, 186, 126], color, 42.5, 'c')  # this is the most common color
    elif sauce == 'must':
        image = replace_color3(image, [221, 202, 117], color, 14.5, 'm')
    return image

def turn_word_to_color(word, cap=True):
    """
    synthethize a color from a given word, based on synesthesia kinda. start with the color of the first letter, then accumulate error ofver the rest of the word to make the color unique, but not brown. 
    """
    with get_json("synesthesia.json") as f:
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
        
    return better_color(dominant_color, err)#, debug=True)
    
def generate_tweet(api, dm=True):
    sauce_type = sample(['chup', 'chup', 'chup', 'chup', 'chup', 'chup', 'chup', 'must'], 1)[0]  # becuae the quality of must tweets is lower, they get a 1/8 chance
    with get_json("words.json") as f:
        im = Image.open(get_script_path() + sep + 'images' + sep + 'mayo{}_uncompressed.png'.format(sauce_type))
        words = json.load(f)
        flavors = words[0]
        brands = words[1]

        todays_flavor = sample(flavors, 1)[0] 
        todays_brand = sample(brands, 1)[0]
        chup = turn_word_to_color(todays_flavor)
        with get_json("skeletons.json") as f2:  # get one tweet skeleton
            statuses = json.load(f2)
            template = sample(statuses, 1)[0]
        if system() == 'Linux' and dm:
            bot_api.send_direct_message(creds['owner'], 'new tweet incoming: {}-{}-{}'.format(todays_brand, todays_flavor, chup))
        else: 
            print(chup, end=' ')

        brand(im, todays_brand, sauce_type)  # puts the "brand" name where it belongs
        im = flavor(im, todays_flavor, chup, sauce_type)  # recolors the image and puts the "flavor" on the image
        im.save(get_script_path() + sep + 'images' + sep + 'tweetthis.png')  # save the image for tweeting
        
        try:
            return template.format(todays_brand.capitalize(), todays_flavor.capitalize(), sauce_type)
        except:
            print(template)
            exit()


if __name__ == "__main__":
    # get credentials
    creds = json.load(get_json("tokens.json"))  # NOTE that this file is not included in the repo for security purposes
    auth = tp.OAuthHandler(creds['api_key'], creds['api_secret'])
    auth.set_access_token(creds['access'], creds['access_secret'])
    bot_api = tp.API(auth)

    try: 
        with get_json("settings.json") as sfile:
            settings = json.load(sfile)
        status = generate_tweet(bot_api, dm=settings["new_tweet_dm"])
        if not settings['debug']:
            bot_api.update_with_media(join(get_script_path() ,'images' , 'tweetthis.png'), status)
        else:
            print(status)
    except Exception as e:
        with open(join(get_script_path(), "err_log.txt"), "a") as f:
            f.write("{}: {}\n-------\n".format(datetime.now().isoformat(), traceback.format_exc()))  # collect errors in a file
            bot_api.send_direct_message(creds['owner'], '{} occurred and I didn\'t tweet Please fix and program better'.format(e))

                
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