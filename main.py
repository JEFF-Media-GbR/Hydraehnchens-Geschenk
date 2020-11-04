import RPi.GPIO as GPIO
import time
import i2clcd
import locale
import speedtest
import os
import textwrap
from unidecode import unidecode
from datetime import datetime
from urllib.parse import unquote as urllib_unquote

locale.setlocale(locale.LC_ALL, "de_DE.utf8")

DISPLAY_WIDTH = 16
DISPLAY_HEIGHT = 2

PIN_LEFT = 10 # 10 = GPIO 15 (RXD)
BUTTON_LEFT = 4
PIN_RIGHT = 12 # 12 = GPIO 18 (PCM_C)
BUTTON_RIGHT = 2
PIN_RESET = 40 # 40 = GPIO 21 (SCLK)
BUTTON_RESET = 1

WAIT_SPLASH = 1

GPIO.setwarnings(False)
GPIO.setmode(GPIO.BOARD)
GPIO.setup(PIN_LEFT, GPIO.IN, pull_up_down=GPIO.PUD_DOWN)
GPIO.setup(PIN_RIGHT, GPIO.IN, pull_up_down=GPIO.PUD_DOWN)
GPIO.setup(PIN_RESET, GPIO.IN, pull_up_down=GPIO.PUD_DOWN)

lcd = i2clcd.i2clcd(i2c_bus=1, i2c_addr=0x27, lcd_width=DISPLAY_WIDTH)
lcd.init()

debugEnabled = True

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
    
def showText(text, start = 0):
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
    
def waitNoButton(clearDisplay):
    if clearDisplay:
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
        
def mainMenu(start):
    menu = ["WTF, Hilfe :o","Wikipedia","Uhr","Internet",""]
    lcd.print_line(">"+menu[start],0)
    lcd.print_line(" "+menu[start+1],1)
    button = waitGetButton()
    if button == BUTTON_LEFT and start > 0:
        mainMenu(start-1)
    elif button == BUTTON_RIGHT and start < len(menu)-2:
        mainMenu(start+1)
    elif button == BUTTON_RESET:
        debug("Main Menu: "+menu[start])
        startRoutine(menu[start],start)
    else:
        mainMenu(start)
        
def startRoutine(routine, start):
    waitNoButton(True)
    if routine == "Uhr":
        routine_uhr()
    elif routine == "Internet":
        routine_speedtest()
    elif routine == "Wikipedia":
        routine_wikipedia()
    elif routine == "WTF, Hilfe :o":
        routine_hilfe()
    mainMenu(start)
    
def remove_non_ascii(text):
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
        
        
def routine_wikipedia():
    lcd.print_line("Suche zufaelligen",0,"CENTER")
    lcd.print_line("Artikel ...",1,"CENTER")
    os.system("curl -Ls -o /dev/null -w %{url_effective} https://de.wikipedia.org/wiki/Spezial:Zuf%C3%A4llige_Seite > /tmp/wikipedialink")
    articleName = open("/tmp/wikipedialink").read()
    articleName = urllib_unquote(remove_prefix(articleName, "https://de.wikipedia.org/wiki/"))
    debug("Random article: " + articleName)
    lcd.print_line("Artikel",0,"CENTER")
    lcd.print_line("laden ...",1,"CENTER")
    downloadCommand = "echo 'Artikel: "+articleName.replace("_"," ")+" "+drawLine("=")+"' > /tmp/wikipedia; wikit "+articleName+" -l de >> /tmp/wikipedia"
    debug("DownloadCommand:")
    debug(downloadCommand)
    os.system(downloadCommand)
    lcd.print_line("Artikel",0,"CENTER")
    lcd.print_line("verarbeiten ...",1,"CENTER")
    file = open("/tmp/wikipedia")
    article = file.read()
    debug(article)
    lcd.print_line("Fertig!",0)
    showText(article)

    
def routine_uhr():
    while waitForButton(BUTTON_RESET,True):
        now = datetime.now()
        current_time = now.strftime("%H:%M:%S")
        current_date = now.strftime("%a %d. %b. %Y")
        lcd.print_line(current_time,0,"CENTER")
        lcd.print_line(current_date,1,"CENTER")
        time.sleep(0.01)
        
        
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
        lcd.print_line("< Download",0)
        lcd.print_line(download,1)
    elif routine == "Upload":
        lcd.print_line("< Upload",0)
        lcd.print_line(upload,1)
    elif routine == "Ping":
        lcd.print_line("< Ping",0)
        lcd.print_line(ping,1)
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
    lcd.print_line("Teste Haehnchens",0,"CENTER");
    lcd.print_line("Internet ...",1,"CENTER")
    st = speedtest.Speedtest()
    mbit_download = st.download()*0.0000076294
    mbit_download_string = f'{mbit_download:.3f}' + " Mbit/s"
    mbit_upload = st.upload()*0.0000076294
    mbit_upload_string = f'{mbit_upload:.3f}' + " Mbit/s"
    best_server = st.get_best_server()
    ping = "? ms"
    for key, value in best_server.items():
        debug(key, ' : ', value)
        if key == "latency":
            ping = f'{value:.3f}'  + " ms"
    debug("MBit/s Download: "+mbit_download_string)
    debug("MBit/s Upload: "+mbit_upload_string)
    menu_speedtest(0,mbit_download_string,mbit_upload_string,ping)
    #while waitForButton(BUTTON_RESET,True):
    #    time.sleep(0.01)
        
    
debug("Splash Start")
lcd.print_line("Hydraehnchen's",0,"CENTER")
lcd.print_line("Geraet",1,"CENTER")
time.sleep(WAIT_SPLASH)
lcd.clear()
debug("Splash End")


mainMenu(0)
