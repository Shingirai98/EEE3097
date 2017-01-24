__author__ = 'Fabian Gebhart'


"""
SMART ALARM

Features of this python script so far:
- displaying the actual time on the alphanumeric display
- scrolling text messages through the display
- figuring out the most recent dlf news
- download the news
- play the news
- stop the news play with a tactile button connected to the GPIOs
- talk to you, using text to speech synthesis
- reading the user settings from a xml file (created over html server)
- accept individual wake-up message, if there is none use default
    wake-up message
- delete the unneeded old news file
- display if alarm is activated by turning last decimal point on
- using multithreading in order to:
    * enable decimal point blinking while news are played
    * download news file while saying individual wake-up message
- choose between "news" and "music"
- offline mp3 wake-up music enabled
- dim display brightness, since default value is too damn bright for sleeping
- enabled volume adjustment
- enabled internet radio / music streaming as possible wake-up sound
- button interrupt instead of waiting
- turn off and on amplifier in order to suppress background noise
- checks provided podcast + stream url if they are ok, if not play default url
- possibility to press button without any alarm going: informs you about the next alarm
- writing error log to 'error.log' file

mpc stations:

OrangeFM                http://orange-01.live.sil.at:8000
SmoothLounge with Ads:  http://streaming.radionomy.com/The-Smooth-Lounge?lang=en-US%2cen%3bq%3d0.8%2cde%3bq%3d0.6


"""


import urllib2
import RPi.GPIO as GPIO
import threading
from display_class import Display
try:
    from sounds import Sound
except:
    pass
from xml_belongings import *
import time
import os
import sys


def write_to_log(message):
    """enables logging, provided message will be written to logfile see 'error.log'"""

    # get current time
    localtime = time.localtime()
    logging_time = time.strftime("[%Y-%m-%d--%H:%M:%S] ", localtime)

    # Define the log file
    f = str(project_path) + '/error.log'
    # Append to existing log file.
    # Change 'a' to 'w' to recreate the log file each time.
    error_log = open(f, 'a')

    # write time and message to file
    error_log.write(str(logging_time) + str(message) + '\n')
    # close error file in order to save text while program is rnning
    error_log.close()


def check_internet():
    """checks if internet connection is available. If not writes
    error to log file"""
    try:
        response=urllib2.urlopen('http://www.google.com',timeout=2)
    except:
        write_to_log("-> internet connection lost")


def button_callback(channel):
    """define a threaded callback function to run when events are detected"""
    start_timer = time.time()
    timer = 0

    if GPIO.input(button_input_pin) and sound.sound_active is False:  # if port 24 == 1
        while GPIO.input(button_input_pin) and timer < 3:
            loop_timer = time.time()
            timer = loop_timer - start_timer
            time.sleep(0.1)

        if timer < 3:
            write_to_log('-> button pressed for < 3 sec')
            tell_when_button_pressed(alarm_active, alarm_days, alarm_time)
        if timer >= 3:
            write_to_log('-> button pressed for > 3 sec')
            shutdown_pi()

    sound.stopping_sound()


def download_file(link_to_file):
    """function for downloading files"""
    file_name = link_to_file.split('/')[-1]
    u = urllib2.urlopen(link_to_file)
    f = open(file_name, 'wb')
    print "-> downloading: %s" % file_name

    # buffer the file in order to download it
    file_size_dl = 0
    block_sz = 8192
    while True:
        buffer = u.read(block_sz)
        if not buffer:
            break

        file_size_dl += len(buffer)
        f.write(buffer)

    f.close()
    # XML file now is saved (to the same directory like this file)
    print "-> download done"
    return file_name


def set_ind_msg(ind_msg_active, ind_msg_text):
    """takes and checks the to two arguments and sets the
    individual message"""
    if ind_msg_active == '0':
        # ind msg is deactivated, therefore create default message
        print '-> individual message deactivated - constructing default message'
        sayable_time = str(time.strftime("%H %M"))
        today = time.strftime('%A')
        standard_message = 'good morning. It is ' + today + '  ' + sayable_time
        individual_message = standard_message
    else:
        individual_message = ind_msg_text

    return individual_message


def delete_old_files(time_to_alarm, alarm_active):
    """checks for old mp3 files and deletes them"""
    # find all mp3 files and append them to a list
    list_of_mp3_files = []
    # check the projects directory
    for file in os.listdir(project_path):
        if file.endswith('.mp3'):
            list_of_mp3_files.append(project_path + '/' + str(file))

    # as well check the home folder
    for file in os.listdir('/home/pi'):
        if file.endswith('.mp3'):
            list_of_mp3_files.append('/home/pi/' + str(file))

    # either if the time_to_alarm is 10 minutes away from going off, or if it is deactivated
    if time_to_alarm < -10 or time_to_alarm > 10 or alarm_active == '0':
        for file in range(len(list_of_mp3_files)):
            os.remove(list_of_mp3_files[file])


def read_photocell():
    """reads the surrounding brightness using the
    connected photocell and transforms the values to
    a scale of 0 - 15 in order to adjust the displays
    brightness"""

    photocell_input_pin = 20
    upper_limit = 400
    lower_limit = 1
    counter = 0
    summed_up_brightness = 0
    max_iterations = 5

    while counter < max_iterations:
        brightness = 0
        # needs to be put low first, so the capacitor is empty
        GPIO.setup(photocell_input_pin, GPIO.OUT)
        GPIO.output(photocell_input_pin, GPIO.LOW)

        time.sleep(0.1)

        # set to input to read out
        GPIO.setup(photocell_input_pin, GPIO.IN)
        # increases the brightness variable depending on the charge
        # of the capacitor (400 = dark; 0 = bright)
        while GPIO.input(photocell_input_pin) == GPIO.LOW:
            brightness += 1

        summed_up_brightness = summed_up_brightness + brightness
        counter += 1

    # calculate the mean of the last 'max_iterations' measurements:
    brightness = summed_up_brightness / max_iterations

    # turn values up-side down: dark-to-bright
    brightness = upper_limit - brightness

    # limit the value of measured brightness
    if brightness > upper_limit:
        brightness = brightness - (brightness - upper_limit)
    elif brightness < lower_limit:
        brightness = brightness - brightness + lower_limit

    # scale brightness to the scale of 0 - 15
    brightness = brightness / (upper_limit / 15)

    return brightness


def tell_when_button_pressed(alarm_active, alarm_days, alarm_time):
    """when button is pressed and alarm is not active
    tell the user some information about the upcoming alarms"""

    next_alarm_day_found = None
    info_message = 'shit. didnt work'

    # figure out the weekdays:
    weekdays = ['sunday', 'monday', 'tuesday', 'wednesday', 'thursday', 'friday', 'saturday']

    # fetch date and time information and convert it to the needed format
    today_as_number = time.strftime('%w')
    now = time.strftime("%H%M")
    time_to_alarm = (int(alarm_time[:2]) * 60 + int(alarm_time[3:])) - (int(now[:2]) * 60 + int(now[2:]))

    # check if alarm is active, then distinguish the four possibilities
    if alarm_active == '1':
        # P1: alarm today + tta > 0
        if str(today_as_number) in alarm_days and time_to_alarm > 0:
            hours_left = time_to_alarm / 60
            minutes_left = time_to_alarm % 60
            info_message = 'The next alarm is today, at %s, which is in %s hours and %s minutes.' % (str(alarm_time), str(hours_left), str(minutes_left))
            if hours_left == 0:
                info_message = 'The next alarm is today, at %s, which is in %s minutes.' % (str(alarm_time), str(minutes_left))

        # P2: tta < 0
        elif time_to_alarm <= 0 or str(today_as_number) not in alarm_days:

            days_to_alarm = 0
            next_alarm_day = int(today_as_number)
            # start loop to findout the up next day which is set to alarm
            while next_alarm_day_found is None:
                days_to_alarm += 1
                next_alarm_day += 1
                if next_alarm_day > 6:
                    next_alarm_day = 0
                if str(next_alarm_day) in alarm_days:
                    next_alarm_day_found = True

            # P3: tta < 0 + not today
            if time_to_alarm <= 0:
                time_left_in_minutes = 1440 + int(time_to_alarm)
                hours_left = time_left_in_minutes / 60
                minutes_left = time_left_in_minutes % 60
                days_to_alarm -= 1
                next_alarm_day = weekdays[next_alarm_day]
                info_message = 'The next alarm is on %s at %s, which is in %s days, %s hours and %s minutes.'\
                               % (str(next_alarm_day), str(alarm_time), str(days_to_alarm), str(hours_left), str(minutes_left))
                if days_to_alarm == 0:
                    info_message = 'The next alarm is tomorrow at %s, which is in %s hours and %s minutes.' \
                                   % (str(alarm_time), str(hours_left), str(minutes_left))
            # P4: tta > 0 + not today
            elif time_to_alarm > 0:
                hours_left = time_to_alarm / 60
                minutes_left = time_to_alarm % 60
                next_alarm_day = weekdays[next_alarm_day]
                info_message = 'The next alarm is on %s at %s, which is in %s days, %s hours and %s minutes.' \
                               % (str(next_alarm_day), str(alarm_time), str(days_to_alarm), str(hours_left), str(minutes_left))
                if days_to_alarm == 1:
                    info_message = 'The next alarm is tomorrow at %s, which is in one day %s hours and %s minutes.' \
                                   % (str(alarm_time), str(hours_left), str(minutes_left))
    elif alarm_active == '0':
        info_message = 'No alarm set.'

    sound.say(info_message)


def test_alarm():
    """test alarm function is executed when 'Test Alarm' button on gui is pressed"""
    # fetch current settings from data.xml
    settings = read_xml_file_namedtuple(str(project_path) + '/data.xml')
    # only content and individual message are relevant
    content = settings.content
    individual_msg_active = settings.individual_message
    individual_message = settings.text

    # start alarm based on settings:
    if content == 'podcast':
        # set the updated individual wake-up message in order to play it
        individual_message = set_ind_msg(individual_msg_active, individual_message)

        # wake up with individual message
        z = threading.Thread(target=sound.say, args=(individual_message,))
        z.start()

        # download podcast_xml_file according to the podcast_url
        podcast_xml_file = download_file(podcast_url)

        # now parse the podcast_xml_file in order to find the most_recent_news_url
        most_recent_news_url = find_most_recent_news_url_in_xml_file(podcast_xml_file)

        # download the most recent news_mp3_file according to the most_recent_news_url
        news_mp3_file = download_file(most_recent_news_url)

        # wait untill thread z (say) is done
        while z.isAlive() == True:
            time.sleep(0.5)

        # play the most recent news_mp3_file
        a = threading.Thread(target=sound.play_mp3_file, args=(news_mp3_file,))
        a.start()
    elif content == 'mp3':
        # set the updated individual wake-up message in order to play it
        individual_message = set_ind_msg(individual_msg_active, individual_message)

        # wake up with individual message
        sound.say(individual_message)

        b = threading.Thread(target=sound.play_wakeup_music, args=())
        b.start()
    elif content == 'stream':
        # set the updated individual wake-up message in order to play it
        individual_message = set_ind_msg(individual_msg_active, individual_message)

        # wake up with individual message
        sound.say(individual_message)

        c = threading.Thread(target=sound.play_online_stream, args=())
        c.start()


def check_if_podcast_url_correct(url):
    """check if the provided url is okay, if not, inform master and use default podcast url"""
    # manage default podcast url
    default_podcast_url = "http://www.bbc.co.uk/programmes/p02nq0gn/episodes/downloads.rss"
    # BBC News: http://www.bbc.co.uk/programmes/p02nq0gn/episodes/downloads.rss
    # DLF News: http://www.deutschlandfunk.de/podcast-nachrichten.1257.de.podcast.xml
    most_recent_news_url = 'no_mp3_file'

    if url.startswith(('http://', 'https://', 'www.')):
        pass
    else:
        sound.say('provided podcast url does not look like a proper url. Playing default podcast instead!')
        return default_podcast_url

    try:
        podcast_xml_file = download_file(podcast_url)
        most_recent_news_url = find_most_recent_news_url_in_xml_file(podcast_xml_file)
    finally:
        if most_recent_news_url.endswith('.mp3'):
            return url
        else:
            sound.say('Cant find any m p 3 file in the provided podcast url. Playing default podcast instead!')
            return default_podcast_url


def shutdown_pi():
    """function is executed when button is pressed and hold for 5 seconds
    asks the user to shut down and does so by pressing the button again"""
    o = threading.Thread(target=sound.say, args=('Wanna shut me down?',))
    o.start()
    start_timer = time.time()
    timer = 0
    shutdown = False

    while GPIO.input(button_input_pin) == 1:
        time.sleep(0.1)

    if GPIO.input(button_input_pin) == 0:

        while timer < 5:
            #print 'shut down timer: ', timer
            loop_timer = time.time()
            timer = loop_timer - start_timer
            if GPIO.input(button_input_pin):
                shutdown = True
                break
            time.sleep(0.1)

        if shutdown:
            q = threading.Thread(target=display.shutdown, args=(6,))
            q.start()
            sound.say('O K. Bye!')
            print '... now shutting down ...'
            os.system('sudo poweroff')


def if_interrupt():
    """stuff to do when script crashed because of interrupt or whatever"""
    k = threading.Thread(target=sound.say, args=('Outsch!',))
    k.start()
    display.snake(1)
    GPIO.output(amp_switch_pin, 0)  # switch amp off
    # write stdout stream to error log
    error_log = open(str(project_path) + '/error.log', 'a')
    sys.stdout = error_log
    sys.stderr = error_log
    print '\n... crashed ... bye!\n'
    error_log.close()


if __name__ == '__main__':
    # read environmental variable for project path
    project_path = os.environ['smart_alarm_path']

    # delete old log file
    try:
        os.system('rm ' + str(project_path) + '/error.log')
    finally:
        pass

    write_to_log('_____________SMART ALARM STARTED_______________')

    # import dispay_class
    display = Display()

    # import sound class
    sound = Sound()

    # set button input pin
    button_input_pin = 24
    # set pin for amplifier switch
    amp_switch_pin = 12

    # turn off GPIO warnings
    GPIO.setwarnings(False)
    # configure RPI GPIO. Make sure to use 1k ohms resistor to protect input pin
    GPIO.setmode(GPIO.BCM)
    GPIO.setup(button_input_pin, GPIO.IN)
    # set pin to output
    GPIO.setup(amp_switch_pin, GPIO.OUT)
    # set output low in order to turn off amplifier and nullify noise
    GPIO.output(amp_switch_pin, 0)

    # alternative starting display
    y = threading.Thread(target=display.big_stars, args=(7,))
    y.start()

    # say welcome message
    welcome_message = 'What is my purpose?'
    sound.say(welcome_message)

    # start the the button interrupt thread
    GPIO.add_event_detect(button_input_pin, GPIO.BOTH, callback=button_callback)

    # read out the settings in 'data.xml' from the same folder
    xml_data = update_settings(str(project_path) + '/data.xml')

    # assign the xml data to the corresponding variables
    alarm_active, alarm_time, content, alarm_days, individual_msg_active, individual_message, volume,\
        podcast_url, stream_url = update_settings(str(project_path) + '/data.xml')

    # set flag for just played the news
    just_played_alarm = False

    # set loop counter to one (needed to calculate mean of 10 iterations for the display brightness control)
    loop_counter = 1

    # set brightness_data to zero in order to initialize the variable
    brightness_data = 0

    # set the number of iterations to go through for the mean of brightness value
    # 5 looks pretty stable, but does not act too fast on sharp changes. Increase value for more stability,
    # decrease it for faster response time
    number_of_iterations = 5

    # set decimal point flag - for decimal point blinking
    point = False

    write_to_log('-> starting main loop...')

    try:
        while True:
            # write stdout stream to error log
            error_log = open(str(project_path) + '/error.log', 'a')
            sys.stdout = error_log
            sys.stderr = error_log

            # organise time format
            now = time.strftime("%H%M")

            # reset display
            display.clear_class()

            # read xml file and store data to xml_data
            new_xml_data = update_settings(str(project_path) + '/data.xml')

            # check if xml file was updated. If so, update the variables
            if xml_data != new_xml_data:
                write_to_log('-> data.xml file changed - now update settings')
                # set the updated variables
                alarm_active, alarm_time, content, alarm_days, individual_msg_active, individual_message, volume,\
                    podcast_url, stream_url = update_settings(str(project_path) + '/data.xml')

                sound.adjust_volume(volume)

            time_to_alarm = int(int(str(alarm_time[:2]) + str(alarm_time[3:]))) - int(now)

            # check if alarm is activated
            if alarm_active == '1' and just_played_alarm == False:     # alarm is activated start managing to go off
                # find the actual day of the week in format of a number in order to compare to the xml days variable
                today_nr = time.strftime('%w')

                if today_nr in alarm_days:      # check if current day is programmed to alarm
                    # alarm is set to go off today, calculate the remaining time to alarm

                    if time_to_alarm == 0:
                        write_to_log('---> now starting alarm')

                        # check if news or audio (offline mp3) is programmed
                        if content == 'podcast':

                            # display the current time
                            display.show_time(now)
                            # write content to display
                            display.write()

                            # set the updated individual wake-up message in order to play it
                            individual_message = set_ind_msg(individual_msg_active, individual_message)

                            # wake up with individual message
                            z = threading.Thread(target=sound.say, args=(individual_message,))
                            z.start()

                            # check if the provided podcast url is working. If not function chooses deafult url
                            podcast_url = check_if_podcast_url_correct(podcast_url)

                            # download podcast_xml_file according to the podcast_url
                            podcast_xml_file = download_file(podcast_url)

                            # now parse the podcast_xml_file in order to find the most_recent_news_url
                            most_recent_news_url = find_most_recent_news_url_in_xml_file(podcast_xml_file)

                            # download the most recent news_mp3_file according to the most_recent_news_url
                            news_mp3_file = download_file(most_recent_news_url)

                            # wait untill thread z (say) is done
                            while z.isAlive() == True:
                                time.sleep(0.5)

                            # play the most recent news_mp3_file
                            a = threading.Thread(target=sound.play_mp3_file, args=(news_mp3_file,))
                            a.start()

                            # set flag for just played alarm
                            just_played_alarm = True


                        elif content == 'mp3':
                            # since music is preferred, play the offline mp3 files

                            # display the current time
                            display.show_time(now)
                            # write content to display
                            display.write()

                            # set the updated individual wake-up message in order to play it
                            individual_message = set_ind_msg(individual_msg_active, individual_message)

                            # wake up with individual message
                            sound.say(individual_message)

                            b = threading.Thread(target=sound.play_wakeup_music, args=())
                            b.start()

                            # set flag for just played alarm
                            just_played_alarm = True


                        elif content == 'stream':
                            # since internet-radio is preferred, play the online stream
                            # display the current time
                            display.show_time(now)
                            # write content to display
                            display.write()

                            # set the updated individual wake-up message in order to play it
                            individual_message = set_ind_msg(individual_msg_active, individual_message)

                            # wake up with individual message
                            sound.say(individual_message)

                            c = threading.Thread(target=sound.play_online_stream, args=())
                            c.start()

                            # set flag for just played alarm
                            just_played_alarm = True

            if time_to_alarm != 0:
                # set just_played_alarm back to False in order to not miss the next alarm
                just_played_alarm = False

            # display the current time
            display.show_time(now)

            # check if alarm is active and set third decimal point
            if alarm_active == '1':
                display.set_decimal(3, True)
            else:
                # else if alarm is deactivated, turn last decimal point off
                display.set_decimal(3, False)

            if point:
                display.set_decimal(1, point)
                point = False
                # write content to display
                display.write()
                time.sleep(0.5)
            else:
                display.set_decimal(1, point)
                point = True
                # write content to display
                display.write()
                time.sleep(0.5)

            # delete old and unneeded mp3 files
            delete_old_files(time_to_alarm, alarm_active)

            # update xml file in order to find differences in next loop
            xml_data = new_xml_data

            # read area brightness with photocell, save the data to current_brightness and add it the brightness_data
            # in order to calculate the mean of an set of measurements
            current_brightness = read_photocell()
            brightness_data += current_brightness

            # print 'loop_counter: %s \t current_brightness: %s \t brightness_data: %s ' % (loop_counter, current_brightness, brightness_data)

            # increase loop counter +1 since loop is about to start again
            loop_counter += 1
            if loop_counter > number_of_iterations:
                display.set_brightness(int(brightness_data) / number_of_iterations)
                loop_counter = 1
                brightness_data = 0

            # close error log file in order to enable live tracking of errors
            error_log.close()

    finally:  # this block will run no matter how the try block exits
        if_interrupt()


