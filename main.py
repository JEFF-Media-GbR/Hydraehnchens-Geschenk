import RPi.GPIO as GPIO
import time
import i2clcd
import locale
import speedtest
import os
import sys
import textwrap
import subprocess
import inspect
import urllib.request, json
from unidecode import unidecode
from datetime import datetime
from urllib.parse import unquote as urllib_unquote

# pip3 install RPi.GPIO i2clcd smbus speedtest-cli Unidecode

locale.setlocale(locale.LC_ALL, "de_DE.utf8")

DISPLAY_WIDTH = 20
DISPLAY_HEIGHT = 4

PIN_LEFT = 10 # 10 = GPIO 15 (RXD)
BUTTON_LEFT = 4
PIN_RIGHT = 12 # 12 = GPIO 18 (PCM_C)
BUTTON_RIGHT = 2
PIN_RESET = 40 # 40 = GPIO 21 (SCLK)
BUTTON_RESET = 1

WAIT_SPLASH = 3

NEWS_URL = "http://newsapi.org/v2/top-headlines?country=de&apiKey="
NEWS_API_KEY = "53d27f03fe224162a43195aa7b208ba8"

GPIO.setwarnings(False)
GPIO.setmode(GPIO.BOARD)
GPIO.setup(PIN_LEFT, GPIO.IN, pull_up_down=GPIO.PUD_DOWN)
GPIO.setup(PIN_RIGHT, GPIO.IN, pull_up_down=GPIO.PUD_DOWN)
GPIO.setup(PIN_RESET, GPIO.IN, pull_up_down=GPIO.PUD_DOWN)

lcd = i2clcd.i2clcd(i2c_bus=1, i2c_addr=0x27, lcd_width=DISPLAY_WIDTH)
lcd.init()
lcd.set_backlight(True)

debugEnabled = True

os.chdir("/home/pi/haehnchens-geraet/")

def getSetting(file):
    return os.path.isfile("settings."+file)

def setSetting(file, enabled):
    if enabled:
        with open("settings."+file, "w") as file:
            file.write("siggi")
    else:
        os.remove("settings."+file)


wikiShowAll = getSetting("wikipedia.showall")

def debug(text):
    if debugEnabled:
        print("debug: "+text)
        
def drawLine(char):
    result = ""
    for i in range(0,DISPLAY_WIDTH):
        result = result + char
    return result
        
def getButton():
    result = 0
    if GPIO.input(PIN_LEFT) == GPIO.HIGH:
        result = result + BUTTON_LEFT
    if GPIO.input(PIN_RIGHT) == GPIO.HIGH:
        result = result + BUTTON_RIGHT
    if GPIO.input(PIN_RESET) == GPIO.HIGH:
        result = result + BUTTON_RESET
    return result

def showMenu(entries, start = 0, selected = 0, align="LEFT", returnInt=False):

    debug("showMenu Stack: "+str(len(inspect.stack())))

    # Pre checks: Start and Selected nicht out of bounds
    if start < 0:
        debug("correcting out of bound: start < 0")
        start = 0
    elif start > len(entries)-DISPLAY_HEIGHT:
        debug("correcting out of bound: start > len(entries)-DISPLAY_HEIGHT")
        start = len(entries)-DISPLAY_HEIGHT

    if selected < 0:
        debug("correcting out of bound: selected < 0")
        selected = 0
    elif selected >= len(entries):
        debug("correcting out of bound: selected >= len(entries)")
        selected = len(entries)-1

    for i in range(0,DISPLAY_HEIGHT):
        cursor=" "
        if start+i < len(entries):
            debug("writing line"+str(i))
            if selected == start+i:
                debug("line "+str(i) +" is selected, menu item "+str(selected)+" ("+entries[start+i]+")")
                cursor=">"
            lcd.print_line(cursor+remove_non_ascii(entries[start+i]),i)
        else:
            lcd.print_line(" ",i)
    button = waitGetButton()
    if button == BUTTON_RIGHT:
        return showMenu(entries, start + 1, selected+1, align, returnInt)
    elif button == BUTTON_LEFT:
        return showMenu(entries, start - 1, selected-1, align, returnInt)
    elif button != BUTTON_RESET:
        return showMenu(entries, start, align, returnInt)
    else:
        debug("showMenu chosen no "+str(selected)+": "+entries[selected])
        return selected if returnInt else entries[selected]

def showTextRaw(textWrapped, start = 0, align = "LEFT"):

    debug("showTextRaw Stack: "+str(len(inspect.stack())))

    for i, s in enumerate(textWrapped):
        textWrapped[i] = remove_non_ascii(textWrapped[i])

    if start < 0:
        debug("start < 0")
        start = 0
    elif start > len(textWrapped)-DISPLAY_HEIGHT:
        debug("start > len(textWrapped)-DISPLAY_HEIGHT")
        start = len(textWrapped)-DISPLAY_HEIGHT
    for i in range(0,DISPLAY_HEIGHT):
        if start+i < len(textWrapped):
            debug("writing line "+str(i))
            lcd.print_line(textWrapped[start+i],i, align)
        else:
            lcd.print_line("^^^",i,"CENTER")
    button = waitGetButton()
    if button == BUTTON_RIGHT:
        showTextRaw(textWrapped, start + DISPLAY_HEIGHT, align)
    elif button == BUTTON_LEFT:
        showTextRaw(textWrapped, start - DISPLAY_HEIGHT, align)
    elif button != BUTTON_RESET:
        showTextRaw(textWrapped, start, align)
    
def showText(text, start = 0):

    debug("showText Stack: "+str(len(inspect.stack())))

    text = remove_non_ascii(text)
    textWrapped = textwrap.wrap(text,DISPLAY_WIDTH)
    if start < 0:
        debug("start < 0")
        start = 0
    elif start > len(textWrapped)-DISPLAY_HEIGHT:
        debug("start > len(textWrapped)-DISPLAY_HEIGHT")
        start = len(textWrapped)-DISPLAY_HEIGHT
    for i in range(0,DISPLAY_HEIGHT):
        if start+i < len(textWrapped):
            debug("writing line "+str(i))
            lcd.print_line(textWrapped[start+i],i)
        else:
            lcd.print_line("^^^",i,"CENTER")
    button = waitGetButton()
    if button == BUTTON_RIGHT:
        showText(text, start + DISPLAY_HEIGHT)
    elif button == BUTTON_LEFT:
        showText(text, start - DISPLAY_HEIGHT)
    elif button != BUTTON_RESET:
        showText(text, start)
        
def waitGetButton():
    while getButton() == 0:
        time.sleep(0.01)
    button = getButton()
    while getButton() != 0:
        time.sleep(0.01)
    return button
    
def waitNoButton(clearDisplay = True, fingerWeg = False):
    if clearDisplay and fingerWeg:
        lcd.clear()
        lcd.print_line("Finger",0,"CENTER")
        lcd.print_line("weg",1,"CENTER")
    while getButton() != 0:
        time.sleep(0.01)
    if clearDisplay:
        lcd.clear()
        
def waitForButton(button, clearDisplay):
    if getButton() != button:
        return True
    waitNoButton(clearDisplay)
    return False

def menu_internet(start):

    debug("menu_internet Stack: "+str(len(inspect.stack())))

    waitNoButton()
    if start == 0:
        lcd.print_line(">IP anzeigen",0)
        lcd.print_line(" Speedtest",1)
    elif start == 1:
        lcd.print_line(">Speedtest",0)
        lcd.print_line(" Zurueck",1)
    elif start == 2:
        lcd.print_line(">Zurueck",0)
        lcd.print_line("",1)

    button = waitGetButton()
    if button == BUTTON_LEFT and start > 0:
        menu_internet(start-1)
    elif button == BUTTON_RIGHT and start < 2:
        menu_internet(start+1)
    elif button == BUTTON_RESET:
        waitNoButton()
        if start == 0:
            ip_anzeigen()
        elif start == 1:
            routine_speedtest()
        else:
            mainMenu(0)
            # zurueck zum hauptmenu
    else:
        mainMenu(0)

def ip_anzeigen():
    line(0)
    lcd.print_line("Teste Haehnchens",1,"CENTER");
    lcd.print_line("IP-Adresse ...",2,"CENTER")
    line(3)
    localIP = subprocess.check_output(["hostname","-I"]).split()[0].decode()
    publicIP = subprocess.check_output(["curl","ifconfig.me"]).split()[0].decode()
    lcd.print_line(localIP,1,"CENTER")
    lcd.print_line(publicIP,2,"CENTER")
    while waitForButton(BUTTON_RESET,True):
        time.sleep(0.01)
    menu_internet(0)

        
def mainMenu(start):
    debug("mainMenu Stack: "+str(len(inspect.stack())))
    menu = ["Alles Gute <3","Wikipedia","Nachrichten","Uhr","Internet","Einstellungen"]
    ##
    chosen = showMenu(menu)
    startRoutine(chosen,start)
    ##
    # lcd.print_line(">"+menu[start],0)
    # lcd.print_line(" "+menu[start+1],1)
    # button = waitGetButton()
    # if button == BUTTON_LEFT and start > 0:
    #     mainMenu(start-1)
    # elif button == BUTTON_RIGHT and start < len(menu)-2:
    #     mainMenu(start+1)
    # elif button == BUTTON_RESET:
    #     debug("Main Menu: "+menu[start])
    #     startRoutine(menu[start],start)
    # else:
    #     mainMenu(start)
        
def startRoutine(routine, start):

    debug("startRoutine Stack: "+str(len(inspect.stack())))

    waitNoButton(True)
    if routine == "Uhr":
        routine_uhr()
    elif routine == "Internet":
        menu_internet(0)
    elif routine == "Wikipedia":
        routine_wikipedia()
    elif routine == "Nachrichten":
        routine_nachrichten()
    elif routine == "Alles Gute <3":
        routine_hilfe()
    elif routine == "Einstellungen":
        routine_debug()
    mainMenu(start)
    
def remove_non_ascii(text):

    debug("remove_non_ascii Stack: "+str(len(inspect.stack())))

    text = text.replace("ü","ue")
    text = text.replace("ä","ae")
    text = text.replace("ö","oe")
    text = text.replace("Ü","Ue")
    text = text.replace("Ö","Oe")
    text = text.replace("Ä","Ae")
    text = text.replace("ß","ss")
    return unidecode(text)
    
def remove_prefix(text, prefix):
    return text[text.startswith(prefix) and len(prefix):]

def options_wikipedia():
    global wikiShowAll
    setting = "Ja" if wikiShowAll else "Nein"
    chosenWiki = showMenu(["Ganz.Art.: "+setting, "Zurueck"])
    
    if chosenWiki.startswith("Ganz.Art.: "):
        wikiShowAll = not wikiShowAll
        setSetting("wikipedia.showall",wikiShowAll)
        options_wikipedia()

def routine_debug(start=0):
    menu = ["Wikipedia","Ueber","Debug","Zurueck","Beenden"]
    chosen = showMenu(menu,start)

    if chosen == "Wikipedia":
        options_wikipedia()

    
    elif chosen == "Beenden":
        line(0)
        lcd.print_line("Knorken Knack,",1,"CENTER")
        lcd.print_line("Haehnchen!",2,"CENTER")
        line(3)
        time.sleep(3)
        lcd.clear()
        lcd.set_backlight(False)
        sys.exit(0)

    elif chosen == "Zurueck":
        pass
        
        
def routine_wikipedia():
    line(0)
    lcd.print_line("Suche zufaelligen",1,"CENTER")
    lcd.print_line("Artikel ...",2,"CENTER")
    line(3)
    os.system("curl -Ls -o /dev/null -w %{url_effective} https://de.wikipedia.org/wiki/Spezial:Zuf%C3%A4llige_Seite > /tmp/wikipedialink")
    articleName = open("/tmp/wikipedialink").read()
    articleName = urllib_unquote(remove_prefix(articleName, "https://de.wikipedia.org/wiki/"))
    debug("Random article: " + articleName)
    line(0)
    lcd.print_line("Artikel",1,"CENTER")
    lcd.print_line("laden ...",2,"CENTER")
    line(3)
    showAll = "--all" if wikiShowAll else ""
    downloadCommand = "echo 'Artikel: "+articleName.replace("_"," ")+" "+drawLine("=")+"' > /tmp/wikipedia; wikit "+articleName+" -l de "+showAll+" >> /tmp/wikipedia"
    debug("DownloadCommand:")
    debug(downloadCommand)
    os.system(downloadCommand)
    line(0)
    lcd.print_line("Artikel",1,"CENTER")
    lcd.print_line("verarbeiten ...",2,"CENTER")
    line(3)
    file = open("/tmp/wikipedia")
    article = file.read()
    debug(article)
    lcd.print_line("Fertig!",0)
    showText(article)

def routine_nachrichten():
    line(0)
    lcd.print_line("Lade unserioese",1,"CENTER")
    lcd.print_line("Nachrichten ...",2,"CENTER")
    line(3)
    titles = ["Zurück"]
    shortTitles = ["Zurück"]
    descriptions = ["Zurück"]
    contents = ["Zurück"]
    finalContents = ["Zurück"]
    with urllib.request.urlopen(NEWS_URL + NEWS_API_KEY) as url:
        data = json.loads(url.read().decode())
        for article in data['articles']:
            debug("Article found")
            for key, value in article.items():
                debug("  found key "+key)
                if key == "title":
                    titles.append(value)
                    #shortTitles.append(remove_non_ascii(textwrap.shorten(value, width=15, placeholder="...")))
                    shortTitles.append(remove_non_ascii(value))
                elif key == "description":
                    descriptions.append(value)
                elif key == "content":
                    contents.append(value)
    for i in range(0,len(titles)):
        if descriptions[i] != "" and descriptions[i] is not None:
            finalContents.append(descriptions[i])
        elif contents[i] != "" and contents[i] is not None:
            finalContents.append(contents[i])
        else:
            finalContents[i] = "- Kein Inhalt Hähnchen :( -"
    titles.append("Zurück")
    shortTitles.append("Zurück")
    descriptions.append("Zurück")
    contents.append("Zurück")
    finalContents.append("Zurück")
    menu_nachrichten(titles, shortTitles, finalContents, 0)

def menu_nachrichten(titles, shortTitles, contents, start):
    chosen = showMenu(shortTitles, start, start, returnInt=True)
    debug("Article chosen: "+str(chosen))
    if(chosen != 0 and chosen != len(titles) and chosen != len(titles) -1 ):
        showText(titles[chosen] + " =~=~=~=~=~=~=~=~=~= " + contents[chosen])
        menu_nachrichten(titles,shortTitles,contents,chosen)
    
def routine_uhr():
    while waitForButton(BUTTON_RESET,True):
        now = datetime.now()
        current_time = now.strftime("%H:%M:%S")
        current_date = now.strftime("%a %d. %b. %Y")
        lcd.print_line(current_time,1,"CENTER")
        lcd.print_line(current_date,2,"CENTER")
        line(0)
        line(3)
        time.sleep(0.01)

def display_speedtest(download,upload,ping):
    text = [
        getLine(),
        "    Download   >",
        download,
        getLine(),
        
        getLine(),
        "<    Upload    >",
        upload,
        getLine(),
        
        getLine(),
        "<     Ping      ",
        ping,
        getLine()
        ]
    showTextRaw(text,0,"CENTER")

        
        
def menu_speedtest(start,download,upload,ping):
    menu = ["Download","Upload","Ping","Zurueck",""]
    lcd.print_line(">"+menu[start],0)
    lcd.print_line(" "+menu[start+1],1)
    button = waitGetButton()
    if button == BUTTON_LEFT and start > 0:
        menu_speedtest(start-1,download,upload,ping)
    elif button == BUTTON_RIGHT and start < len(menu)-2:
        menu_speedtest(start+1, download, upload, ping)
    elif button == BUTTON_RESET:
        debug("Speedtest Menu: "+menu[start])
        startSpeedtestRoutine(menu[start],start, download, upload, ping)
    else:
        menu_speedtest(start,download,upload,ping)
        
def startSpeedtestRoutine(routine, start, download, upload, ping):
    waitNoButton(True)
    if routine == "Download":
        line(0)
        line(3)
        lcd.print_line("< Download",1)
        lcd.print_line(download,2)
    elif routine == "Upload":
        line(0)
        line(3)
        lcd.print_line("< Upload",1)
        lcd.print_line(upload,2)
    elif routine == "Ping":
        line(0)
        line(3)
        lcd.print_line("< Ping",1)
        lcd.print_line(ping,2)
    elif routine == "Zurueck":
        waitNoButton(True)
    if routine != "Zurueck":
        while waitForButton(BUTTON_RESET,True):
            time.sleep(0.01)
        menu_speedtest(start,download,upload,ping)
        
def routine_hilfe():
    showText("Alles alles alles gute zum 25. Geburtstag, liebstes Hydrähnchen! <3 Dieses Gerät soll dir helfen, dein Wissen stetig zu erweitern, damit du, wenn du bald richtig alt bist, wenigstens nicht so blöd dastehst ^^ :*")
        
def routine_speedtest():
    debug("Speedtest... this can take a while")
    line(0)
    lcd.print_line("Teste Haehnchens",1,"CENTER");
    lcd.print_line("Internet ...",2,"CENTER")
    line(3)
    st = speedtest.Speedtest()
    mbit_download = st.download()*0.0000076294
    mbit_download_string = f'{mbit_download:.3f}' + " Mbit/s"
    mbit_upload = st.upload()*0.0000076294
    mbit_upload_string = f'{mbit_upload:.3f}' + " Mbit/s"
    best_server = st.get_best_server()
    ping = "? ms"
    for key, value in best_server.items():
        debug(key + ' : ' + str(value))
        if key == "latency":
            ping = f'{value:.3f}'  + " ms"
    debug("MBit/s Download: "+mbit_download_string)
    debug("MBit/s Upload: "+mbit_upload_string)
    display_speedtest(mbit_download_string,mbit_upload_string,ping)
    
def line(number):
    lcd.print_line("~=~=~=~=~=~=~=~=~=~=",number)
    
def getLine():
    return "~=~=~=~=~=~=~=~=~=~="
    
        
    
debug("Splash Start")

line(0)
lcd.print_line("Hydraehnchen's",1,"CENTER")
lcd.print_line("Geraet",2,"CENTER")
line(3)
time.sleep(WAIT_SPLASH)
lcd.clear()
debug("Splash End")


mainMenu(0)
