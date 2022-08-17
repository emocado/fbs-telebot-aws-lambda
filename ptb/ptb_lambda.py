import datetime
import logging
import re
from pymongo import MongoClient
from telegram import InlineKeyboardMarkup, InlineKeyboardButton, ReplyKeyboardRemove, Update, Bot
from telegram.ext import CallbackQueryHandler, CommandHandler, MessageHandler, Filters, Dispatcher
import json

# fill in bot token and mongoDB uri
TOKEN = ""
MONGO_URI = ""

bot = Bot(token=TOKEN)
dispatcher = Dispatcher(bot, None, use_context=True)


# Enable logging
logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
                    level=logging.INFO)

client = MongoClient(MONGO_URI)
database = client.fbs

logger = logging.getLogger(__name__)
global_dict = {}
list_school = [
"Administration Building",
"Lee Kong Chian School of Business",
"Li Ka Shing Library",
"School of Accountancy",
"School of Economics/School of Social Sciences",
"School of Computing & Information Systems",
"Yong Pung How School of Law/Kwa Geok Choo Law Library",
"SMU Connexion"]
types_facilities = [
"Classroom",
"Group Study Room",
"MPH / Sports Hall",
"Project Room",
"Seminar Room",
"SMUC Facilities",
"Study Booth"]

school_shortcut = {"Administration Building": "Admin",
"Lee Kong Chian School of Business": "LKCSB",
"Li Ka Shing Library": "LKSLIB",
"School of Accountancy": "SOA",
"School of Economics/School of Social Sciences": "SOE/SOSS",
"School of Computing & Information Systems": "SCIS",
"Yong Pung How School of Law/Kwa Geok Choo Law Library": ["YPHSL", "KGC"],
"SMU Connexion": "SMUC",
"Group Study Room": "GSR",
"Project Room": ["PR", "Project Room"],
"SMUC Facilities": "SMUC",
"MPH / Sports Hall": "Admin",
"Classroom": "Classroom",
"Seminar Room": "Seminar Room",
"Study Booth": "Study Booth"
}
def create_time_list():
    time_list = []
    for i in range(24):
        if i < 10:
            time_list.append('0' + str(i) + ':00')
            time_list.append('0' + str(i) + ':30')
        else:
            time_list.append(str(i) + ':00')
            time_list.append(str(i) + ':30')
    return time_list+['23:59']
time_list = create_time_list()


# Define a few command handlers. These usually take the two arguments update and
# context. Error handlers also receive the raised TelegramError object in error.
def start(update, context):
    """Send a message when the command /start is issued."""
    itembtna = InlineKeyboardButton('All facilities search (sort by facilities)', callback_data='sort by facilities')
    itembtna1 = InlineKeyboardButton('All facilities search (sort by time)', callback_data='sort by time')
    itembtna2 = InlineKeyboardButton('Advance Search', callback_data='Advance Search')
    markup = InlineKeyboardMarkup([[itembtna], [itembtna1], [itembtna2]])
    update.message.reply_text('Greetings! This bot can show you the available facilities in SMU now', reply_markup=ReplyKeyboardRemove())
    update.message.reply_text('Choose how you would want to search', reply_markup=markup)
    database.fbs_logs.insert_one({'username': update.message.from_user.username, 'text': update.message.text, 'chat_id': update.message.chat_id, 'time': datetime.datetime.now().strftime("%H:%M:%S"), 'date': str(datetime.date.today())})

def button(update, context):
    query = update.callback_query
    query.answer()
    
    # This will define which button the user tapped on (from what you assigned to "callback_data"):
    choose = query.data
    chat_id = update.callback_query.message.chat_id
    
    # Now u can define what choice ("callback_data") do what like this:
    if choose == 'sort by facilities':
        reply_msg = read_fbs_data(datetime.datetime.now()+datetime.timedelta(hours=8))
        reply_long_msg(reply_msg, query, update, context)

    if choose == 'sort by time':
        reply_msg = read_fbs_data(datetime.datetime.now()+datetime.timedelta(hours=8), sort_by='time')
        reply_long_msg(reply_msg, query, update, context)

    if choose == 'Advance Search':
        global_dict[chat_id] = [set(), set()]
        markup_list = []
        for school in list_school:
            markup_list.append([InlineKeyboardButton(school, callback_data=school)])
        markup = InlineKeyboardMarkup(markup_list)
        query.edit_message_text('select the building you want to include in your search', reply_markup=markup)

    if choose in list_school:
        global_dict[chat_id][0].add(choose)
        markup_list = []
        global_dict[chat_id][0].add(choose)
        reply_msg = ' - ' + '\n - '.join(global_dict[chat_id][0])
        query.edit_message_text(text=f"You have selected:\n{choose}\n\nBuildings included in your search:\n{reply_msg}\n\nYou can continue choosing more buildings")
        markup_list.append([InlineKeyboardButton('DONE', callback_data='facilities type')])
        for school in list_school:
            if school not in global_dict[chat_id][0]:
                markup_list.append([InlineKeyboardButton(school, callback_data=school)])
        markup = InlineKeyboardMarkup(markup_list)
        query.edit_message_reply_markup(reply_markup=markup)

    if choose == 'facilities type':
        markup_list = []
        for faci_type in types_facilities:
            markup_list.append([InlineKeyboardButton(faci_type, callback_data=faci_type)])
        markup = InlineKeyboardMarkup(markup_list)
        query.edit_message_text('select the facility you want to include in your search', reply_markup=markup)

    if choose in types_facilities:
        global_dict[chat_id][1].add(choose)
        markup_list = []
        global_dict[chat_id][1].add(choose)
        reply_msg = ' - ' + '\n - '.join(global_dict[chat_id][1])
        query.edit_message_text(text=f"You have selected:\n{choose}\n\nFacilities types included in your search:\n{reply_msg}\n\nYou can continue choosing more facilities types")
        markup_list.append([InlineKeyboardButton('DONE', callback_data='timing')])
        for faci_type in types_facilities:
            if faci_type not in global_dict[chat_id][1]:
                markup_list.append([InlineKeyboardButton(faci_type, callback_data=faci_type)])
        markup = InlineKeyboardMarkup(markup_list)
        query.edit_message_reply_markup(reply_markup=markup)

    if choose == 'timing':
        markup_list = []
        curr_time = (roundTime(datetime.datetime.now(), 30*60) + datetime.timedelta(hours=8)).time()
        last_time = datetime.datetime.strptime('22:30', '%H:%M').time()

        keyboard_row = []
        while curr_time <= last_time:
            if len(keyboard_row) == 3:
                markup_list.append(keyboard_row)
                keyboard_row = []
            keyboard_row.append(InlineKeyboardButton(curr_time.strftime('%H:%M'), callback_data=curr_time.strftime('%H:%M')))
            curr_time = datetime.datetime.strptime(curr_time.strftime('%H:%M'), '%H:%M') + datetime.timedelta(minutes=30)
            curr_time = curr_time.time()
        if keyboard_row:
            markup_list.append(keyboard_row)
        markup = InlineKeyboardMarkup(markup_list)
        query.edit_message_text("select your start time", reply_markup=markup)

    if choose in time_list:
        start_time = datetime.datetime.strptime(choose, '%H:%M')
        reply_msg = read_fbs_data(start_time, global_dict[chat_id][0], global_dict[update.callback_query.message.chat_id][1])
        reply_long_msg(reply_msg, query, update, context)

    database.fbs_logs.insert_one({'username': update.callback_query.message.from_user.username, 'text': choose, 'chat_id': chat_id, 'time': datetime.datetime.now().strftime("%H:%M:%S"), 'date': str(datetime.date.today())})

def help(update, context):
    """Send a message when the command /help is issued."""
    update.message.reply_text('Save time by using this bot instead of logging in to FBS to see which rooms are available.\n\nClick /start to get started.')
    database.fbs_logs.insert_one({'username': update.message.from_user.username, 'text': update.message.text, 'chat_id': update.message.chat_id, 'time': datetime.datetime.now().strftime("%H:%M:%S"), 'date': str(datetime.date.today())})

def echo(update, context):
    """Echo the user message."""
    update.message.reply_text(update.message.text)
    database.fbs_logs.insert_one({'username': update.message.from_user.username, 'text': update.message.text, 'chat_id': update.message.chat_id, 'time': datetime.datetime.now().strftime("%H:%M:%S"), 'date': str(datetime.date.today())})

def error(update, context):
    """Log Errors caused by Updates."""
    logger.warning('Update "%s" caused error "%s"', update, context.error)

def roundTime(dt=None, roundTo=60):
    """Round a datetime object to any time lapse in seconds
    dt : datetime.datetime object, default now.
    roundTo : Closest number of seconds to round to, default 1 minute.
    Author: Thierry Husson 2012 - Use it as you want but don't blame me.
    """
    if dt == None : dt = datetime.datetime.now()
    seconds = (dt.replace(tzinfo=None) - dt.min).seconds
    rounding = (seconds+roundTo/2) // roundTo * roundTo
    return dt + datetime.timedelta(0,rounding-seconds,-dt.microsecond)

def break_long_message(reply_msg):
    res = []
    max_msg_len = 4096
    len_msg = len(reply_msg)
    if len_msg >= max_msg_len:
        divide_by = len_msg//max_msg_len + 1
        len_each_part = len_msg//divide_by
        for _ in range(divide_by):
            index = len_each_part
            while index < len(reply_msg) and reply_msg[index] != '\n':
                index += 1
            res.append(reply_msg[:index])
            reply_msg = reply_msg[index+1:]
    else:
        res.append(reply_msg)
    return res

def reply_long_msg(reply_msg, query, update, context):
    list_of_msg = break_long_message(reply_msg)
    query.edit_message_reply_markup(reply_markup=InlineKeyboardMarkup([]))
    for i in range(len(list_of_msg)):
        msg = list_of_msg[i]
        if i == 0:
            query.edit_message_text(msg, parse_mode='Markdown')
        else:
            context.bot.send_message(update.effective_chat.id, msg, parse_mode='Markdown')

def update_blocks_of_30mins(booking_time, blocks_of_30mins):
    # blocks_of_30mins = [True]*32
    start_time, end_time = booking_time.split('-')
    if start_time == '00:00' or end_time == '00:00':
        return

    if start_time not in time_list:
        # in case of start time is not in the list for eg. start time is 17:45
        start_time = roundTime(datetime.datetime.strptime(start_time, '%H:%M'), 30*60).strftime('%H:%M')
    start_time_index = time_list.index(start_time)
    if end_time not in time_list:
        # in case of end time is not in the list for eg. end time is 17:45
        end_time = roundTime(datetime.datetime.strptime(end_time, '%H:%M'), 30*60).strftime('%H:%M')
    end_time_index = time_list.index(end_time)
    for i in range(start_time_index, end_time_index):
        blocks_of_30mins[i] = False
    return blocks_of_30mins

def read_fbs_data(curr_time, building = set(), faci_type = set(), sort_by='room'):
    new_building_list = []
    for build in building:
        if type(school_shortcut[build]) == list:
            new_building_list.extend(school_shortcut[build])
        else:
            new_building_list.append(school_shortcut[build])

    new_faci_type_list = []
    for faci in faci_type:
        if type(school_shortcut[faci]) == list:
            new_faci_type_list.extend(school_shortcut[faci])
        else:
            new_faci_type_list.append(school_shortcut[faci])
        
    buildings_rgx = re.compile('.*' + '|'.join(new_building_list) + '.*', re.IGNORECASE)
    facilities_rgx = re.compile('.*' + '|'.join(new_faci_type_list) + '.*', re.IGNORECASE)
    filtered_facilities = database.facilities.find({'$and': [{'facility': buildings_rgx}, {'facility': facilities_rgx}]})
    faci_to_blocks_of_30mins_dict = {obj['facility']: [True]*len(time_list) for obj in filtered_facilities}

    currrent_bookings = database.fbs_data.find({'$and': [{'Room': buildings_rgx}, {'Room': facilities_rgx}, {'Date': (datetime.datetime.now() + datetime.timedelta(hours=8)).strftime("%Y-%m-%d")}]})
    for curr_booking in currrent_bookings:
        update_blocks_of_30mins(curr_booking['Booking Time'], faci_to_blocks_of_30mins_dict[curr_booking['Room']])

    curr_time_str = roundTime(curr_time, 30*60).strftime("%H:%M")
    if curr_time_str not in time_list:
        curr_time_index = 0
    else:
        curr_time_index = time_list.index(curr_time_str)
    faci_message_list_of_tuple = []
    for faci, blocks_of_30mins in faci_to_blocks_of_30mins_dict.items():
        start_free_time, end_free_time = None, None
        if not blocks_of_30mins[curr_time_index]:
            continue
        start_free_time = curr_time_str
        end_free_time = time_list[curr_time_index+1]
        
        for i in range(curr_time_index+1, len(blocks_of_30mins)):
            if blocks_of_30mins[i]:
                end_free_time = time_list[i]
            else:
                break
        if start_free_time:
            faci_message_list_of_tuple.append((faci, f"*{start_free_time} - {end_free_time}*"))
    
    all_text = ''
    if sort_by == 'time':
        faci_message_list_of_tuple.sort(key= lambda x: x[1])

    for faci, start_end_time in faci_message_list_of_tuple:
        all_text += f"{faci}| {start_end_time}\n"

    if all_text == '':
        return 'No room available'
    return all_text

def lambda_handler(event, context):
    
    dispatcher.add_handler(CommandHandler("start", start))
    dispatcher.add_handler(CommandHandler("help", help))
    dispatcher.add_handler(CallbackQueryHandler(button))
    dispatcher.add_handler(MessageHandler(Filters.text, echo))

    # on noncommand i.e message - echo the message on Telegram
    dispatcher.add_handler(MessageHandler(Filters.text, echo))

    # log all errors
    dispatcher.add_error_handler(error)

    try:
        dispatcher.process_update(
            Update.de_json(json.loads(event["body"]), bot)
        )

    except Exception as e:
        print(e)
        return {"statusCode": 500}

    return {"statusCode": 200}

