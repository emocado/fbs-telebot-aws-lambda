import datetime
import logging
import re
from pymongo import MongoClient
from telegram import InlineKeyboardMarkup, InlineKeyboardButton, ReplyKeyboardRemove, Update, Bot
from telegram.ext import CallbackQueryHandler, CommandHandler, ConversationHandler, MessageHandler, Filters, Dispatcher
import json
import os

# fill in bot token and mongoDB uri
TOKEN = os.environ['TOKEN']
MONGO_URI = os.environ['MONGO_URI']

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
"School of Computing & Information Systems 1",
"School of Economics/School of Computing & Information Systems 2",
"School of Social Sciences/College of Integrative Studies",
"SMU Connexion",
"Yong Pung How School of Law/Kwa Geok Choo Law Library"
]
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
"School of Economics/School of Computing & Information Systems 2": "SOE/SCIS2",
"School of Computing & Information Systems 1": "SCIS1",
"School of Social Sciences/College of Integrative Studies": "SOSS/CIS",
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
    update.message.reply_text('Greetings! This bot can show you the available facilities in SMU now\n\nIf you trust this bot and the developer with your password you can try out fbs auto recurring booking (2 weeks in advance) here /book', reply_markup=ReplyKeyboardRemove())
    update.message.reply_text('Choose how you would want to search', reply_markup=markup)
    database.fbs_logs.insert_one({'username': update.message.from_user.username, 'text': update.message.text, 'chat_id': update.message.chat_id, 'time': (datetime.datetime.now() + datetime.timedelta(hours=8)).strftime("%H:%M:%S"), 'date': (datetime.datetime.now() + datetime.timedelta(hours=8)).strftime("%Y-%m-%d")})

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

    database.fbs_logs.insert_one({'username': update.callback_query.message.chat.username, 'text': choose, 'chat_id': chat_id, 'time': (datetime.datetime.now() + datetime.timedelta(hours=8)).strftime("%H:%M:%S"), 'date': (datetime.datetime.now() + datetime.timedelta(hours=8)).strftime("%Y-%m-%d")})

def help(update, context):
    """Send a message when the command /help is issued."""
    update.message.reply_text('Save time by using this bot instead of logging in to FBS to see which rooms are available.\n\nClick /start to get started.')
    database.fbs_logs.insert_one({'username': update.message.from_user.username, 'text': update.message.text, 'chat_id': update.message.chat_id, 'time': (datetime.datetime.now() + datetime.timedelta(hours=8)).strftime("%H:%M:%S"), 'date': (datetime.datetime.now() + datetime.timedelta(hours=8)).strftime("%Y-%m-%d")})

def book(update, context):
    """Book fbs when the command /book is issued."""
    markup_list = []
    keyboard_row = []
    for school in list_school:
        if len(keyboard_row) == 3:
            markup_list.append(keyboard_row)
            keyboard_row = []
        school_short = school_shortcut[school]
        if isinstance(school_short, list):
            school_short = ' / '.join(school_short)
        keyboard_row.append(InlineKeyboardButton(school_short, callback_data=school))
    if keyboard_row:
        markup_list.append(keyboard_row)
    markup_list.append([InlineKeyboardButton('cancel', callback_data='cancel')])
    markup = InlineKeyboardMarkup(markup_list)
    update.message.reply_text('select the building you want to book', reply_markup=markup)
    database.fbs_logs.insert_one({'username': update.message.from_user.username, 'text': update.message.text, 'chat_id': update.message.chat_id, 'time': (datetime.datetime.now() + datetime.timedelta(hours=8)).strftime("%H:%M:%S"), 'date': (datetime.datetime.now() + datetime.timedelta(hours=8)).strftime("%Y-%m-%d")})

    return "building_info"

def schedules(update, context):
    """Show schedules when the command /schedules is issued."""
    update.message.reply_text("key in your school email. Eg: john.2023@scis.smu.edu.sg")
    return "email"

def cancel_schedule(update, context):
    """Cancel scheduled bookings"""
    update.message.reply_text("key in your school email. Eg: john.2023@scis.smu.edu.sg")
    return "email"

def cancel_schedule_button(update, context):
    """Cancel scheduled bookings"""
    query = update.callback_query
    query.answer()
    chat_id = update.callback_query.message.chat_id
    if query.data == 'cancel':
        query.edit_message_text("process canceled !")
        return ConversationHandler.END
    schedule_data_to_delete = query.data
    day, room, start_time, end_time = schedule_data_to_delete.split(', ')
    delete_result = database.schedule.delete_one({'day': day, 'room': room, 'start_time': start_time, 'end_time': end_time, 'chat_id': chat_id})
    if delete_result.deleted_count == 0:
        query.edit_message_text(f"Failed to delete schedule: {schedule_data_to_delete}")
    else:
        query.edit_message_text(f"Deleted schedule: {schedule_data_to_delete}")
    return ConversationHandler.END

def building_info(update, context):
    """Book fbs when the command /book is issued."""
    query = update.callback_query
    query.answer()
    chat_id = update.callback_query.message.chat_id
    if query.data == 'cancel':
        query.edit_message_text("process canceled !")
        return ConversationHandler.END
    building = query.data
    global_dict[chat_id] = {'building': building}
    markup_list = []
    keyboard_row = []
    for faci_type in types_facilities:
        if len(keyboard_row) == 3:
            markup_list.append(keyboard_row)
            keyboard_row = []
        faci_type_short = school_shortcut[faci_type]
        if isinstance(faci_type_short, list):
            faci_type_short = ' / '.join(faci_type_short)
        keyboard_row.append(InlineKeyboardButton(faci_type_short, callback_data=faci_type))
    if keyboard_row:
        markup_list.append(keyboard_row)
    markup_list.append([InlineKeyboardButton('cancel', callback_data='cancel')])
    markup = InlineKeyboardMarkup(markup_list)
    query.edit_message_text('select the facility you want to book', reply_markup=markup)
    return "facility_type_info"

def facility_type_info(update, context):
    """Book fbs when the command /book is issued."""
    query = update.callback_query
    query.answer()
    chat_id = update.callback_query.message.chat_id
    if query.data == 'cancel' or chat_id not in global_dict or 'building' not in global_dict[chat_id]:
        query.edit_message_text("process canceled !")
        return ConversationHandler.END
    facility_type_short = school_shortcut[query.data]
    if isinstance(facility_type_short, list):
        facility_type_short = '|'.join(facility_type_short)
    building_short = school_shortcut[global_dict[chat_id]['building']]
    if isinstance(building_short, list):
        building_short = '|'.join(building_short)
    buildings_rgx = re.compile('.*' + building_short + '.*', re.IGNORECASE)
    facilities_rgx = re.compile('.*' + facility_type_short + '.*', re.IGNORECASE)
    print(buildings_rgx, facilities_rgx, building_short, facility_type_short)
    filtered_facilities = database.facilities.find({'$and': [{'facility': buildings_rgx}, {'facility': facilities_rgx}]})
    markup_list = []
    keyboard_row = []
    for obj in filtered_facilities:
        if len(keyboard_row) == 3:
            markup_list.append(keyboard_row)
            keyboard_row = []
        keyboard_row.append(InlineKeyboardButton(obj['facility'], callback_data=obj['facility']))
    if keyboard_row:
        markup_list.append(keyboard_row)
    markup_list.append([InlineKeyboardButton('cancel', callback_data='cancel')])
    markup = InlineKeyboardMarkup(markup_list)
    query.edit_message_text('select the room you want to book', reply_markup=markup)
    return "room_info"

def book_room_info(update, context):
    """Book fbs when the command /book is issued."""
    query = update.callback_query
    query.answer()
    chat_id = update.callback_query.message.chat_id
    if query.data == 'cancel' or chat_id not in global_dict:
        query.edit_message_text("process canceled !")
        return ConversationHandler.END
    room = query.data
    global_dict[chat_id]['room'] = room
    markup_list = [
        [InlineKeyboardButton('Monday', callback_data='Monday'), InlineKeyboardButton('Tuesday', callback_data='Tuesday'), InlineKeyboardButton('Wednesday', callback_data='Wednesday')],
        [InlineKeyboardButton('Thursday', callback_data='Thursday'), InlineKeyboardButton('Friday', callback_data='Friday'), InlineKeyboardButton('Saturday', callback_data='Saturday')],
        [InlineKeyboardButton('Sunday', callback_data='Sunday')],
        [InlineKeyboardButton('cancel', callback_data='cancel')]
    ]
    markup = InlineKeyboardMarkup(markup_list)
    query.edit_message_text('Choose day you want to book the room', reply_markup=markup)
    return "day_info"

def book_day_info(update, context):
    """Book fbs when the command /book is issued."""
    query = update.callback_query
    query.answer()
    chat_id = update.callback_query.message.chat_id
    if query.data == 'cancel' or chat_id not in global_dict:
        query.edit_message_text("process canceled !")
        return ConversationHandler.END
    day = query.data
    global_dict[chat_id]['day'] = day
    markup_list = [] 
    time_list = create_time_list()[:-1]
    keyboard_row = []
    for time in time_list:
        if len(keyboard_row) == 3:
            markup_list.append(keyboard_row)
            keyboard_row = []
        keyboard_row.append(InlineKeyboardButton(time, callback_data=time))
    if keyboard_row:
        markup_list.append(keyboard_row)
    markup_list.append([InlineKeyboardButton('cancel', callback_data='cancel')])
    markup = InlineKeyboardMarkup(markup_list)
    query.edit_message_text('Choose your start time', reply_markup=markup)
    return "start_time_info"

def book_start_time_info(update, context):
    """Book fbs when the command /book is issued."""
    query = update.callback_query
    query.answer()
    chat_id = update.callback_query.message.chat_id
    if query.data == 'cancel' or chat_id not in global_dict:
        query.edit_message_text("process canceled !")
        return ConversationHandler.END
    start_time = query.data
    global_dict[chat_id]['start_time'] = start_time
    markup_list = [] 
    time_list = create_time_list()[1:]
    keyboard_row = []
    for time in time_list:
        if len(keyboard_row) == 3:
            markup_list.append(keyboard_row)
            keyboard_row = []
        keyboard_row.append(InlineKeyboardButton(time, callback_data=time))
    if keyboard_row:
        markup_list.append(keyboard_row)
    markup_list.append([InlineKeyboardButton('cancel', callback_data='cancel')])
    markup = InlineKeyboardMarkup(markup_list)
    query.edit_message_text('Choose your end time', reply_markup=markup)
    return "end_time_info"

def book_end_time_info(update, context):
    """Book fbs when the command /book is issued."""
    query = update.callback_query
    query.answer()
    chat_id = update.callback_query.message.chat_id
    if query.data == 'cancel' or chat_id not in global_dict:
        query.edit_message_text("process canceled !")
        return ConversationHandler.END
    end_time = query.data
    global_dict[chat_id]['end_time'] = end_time
    query.edit_message_text('key in the co-booker. Eg: john.2023 or john.2023@scis.smu.edu.sg')
    return "co_booker_info"

def book_co_booker_info(update, context):
    """Book fbs when the command /book is issued."""
    chat_id = update.message.chat_id
    co_booker = update.message.text
    global_dict[chat_id]['co_booker'] = co_booker
    update.message.reply_text('key in your school email. Eg: john.2023@scis.smu.edu.sg')
    return "email_info"

def book_email_info(update, context):
    """Book fbs when the command /book is issued."""
    chat_id = update.message.chat_id
    email = update.message.text
    global_dict[chat_id]['email'] = email
    update.message.reply_text('key in your school password')
    return "password_info"

def book_password_info(update, context):
    """Book fbs when the command /book is issued."""
    chat_id = update.message.chat_id
    password = update.message.text
    global_dict[chat_id]['password'] = password
    booking_info = global_dict[chat_id]
    try:
        insert_res = database.schedule.insert_one({
            'chat_id': chat_id,
            'email': booking_info['email'],
            'password': booking_info['password'],
            'day': booking_info['day'],
            'room': booking_info['room'],
            'start_time': booking_info['start_time'],
            'end_time': booking_info['end_time'],
            'co_booker': booking_info['co_booker']
        })
        if not insert_res.inserted_id:
            raise Exception('Failed to insert booking')
    except Exception as e:
        update.message.reply_text(f'Booking failed: {e}')
        return ConversationHandler.END
    update.message.reply_text('Scheduled successfully!\n\nThis bot will help you to book the room 2 weeks in advance.\n\nYou can view and edit your bookings by clicking /schedules')
    return ConversationHandler.END


def email(update, context):
    """Show schedules of given email when the command /schedules is issued."""
    email = update.message.text
    schedule_list = [f"{data['day']}, {data['room']}, {data['start_time']}, {data['end_time']}" for data in database.schedule.find({'email': email})]
    markup_list = [[InlineKeyboardButton(schedule, callback_data=schedule)] for schedule in schedule_list]
    markup_list.append([InlineKeyboardButton('cancel', callback_data='cancel')])
    markup = InlineKeyboardMarkup(markup_list)
    update.message.reply_text("Here is your schedule bookings.\nIf you would like to remove any scheduling please click on the respective button below", reply_markup=markup)
    return "cancel_schedule_button"

def cancel(update, context):
    """Cancel the conversation."""
    chat_id = update.message.chat_id
    bot.send_message(chat_id , text = "process canceled !")
    return ConversationHandler.END

def echo(update, context):
    """Echo the user message."""
    update.message.reply_text(update.message.text)
    database.fbs_logs.insert_one({'username': update.message.from_user.username, 'text': update.message.text, 'chat_id': update.message.chat_id, 'time': (datetime.datetime.now() + datetime.timedelta(hours=8)).strftime("%H:%M:%S"), 'date': (datetime.datetime.now() + datetime.timedelta(hours=8)).strftime("%Y-%m-%d")})

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
    # blocks_of_30mins = [True]*len(time_list)
    start_time, end_time = booking_time.split('-')
    if start_time == '00:00' and end_time == '00:00':
        for i in range(len(blocks_of_30mins)):
            blocks_of_30mins[i] = False
    if end_time == '00:00':
        end_time = '23:59'

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
                end_free_time = time_list[i]
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
    schedules_CH = ConversationHandler(
        entry_points = [CommandHandler("schedules", schedules)],
        states = {
            "email" : [MessageHandler(Filters.text , email)],
            "cancel_schedule_button" : [CallbackQueryHandler(cancel_schedule_button)]
        },
        fallbacks = [MessageHandler(Filters.regex('cancel'), cancel)]
    )
    cancel_schedule_CH = ConversationHandler(
        entry_points = [CommandHandler("cancel_schedule", cancel_schedule)],
        states = {
            "email" : [MessageHandler(Filters.text , email)],
            "cancel_schedule_button" : [CallbackQueryHandler(cancel_schedule_button)]
        },
        fallbacks = [MessageHandler(Filters.regex('cancel'), cancel)]
    )
    book_CH = ConversationHandler(
        entry_points = [CommandHandler("book", book)],
        states = {
            "building_info" : [CallbackQueryHandler(building_info)],
            "facility_type_info" : [CallbackQueryHandler(facility_type_info)],
            "room_info" : [CallbackQueryHandler(book_room_info)],
            "day_info" : [CallbackQueryHandler(book_day_info)],
            "start_time_info" : [CallbackQueryHandler(book_start_time_info)],
            "end_time_info" : [CallbackQueryHandler(book_end_time_info)],
            "co_booker_info" : [MessageHandler(Filters.text, book_co_booker_info)],
            "email_info" : [MessageHandler(Filters.text, book_email_info)],
            "password_info" : [MessageHandler(Filters.text, book_password_info)]
        },
        fallbacks = [MessageHandler(Filters.regex('cancel'), cancel)])
    dispatcher.add_handler(schedules_CH)
    dispatcher.add_handler(cancel_schedule_CH)
    dispatcher.add_handler(book_CH)
    dispatcher.add_handler(CommandHandler("start", start))
    dispatcher.add_handler(CommandHandler("help", help))
    dispatcher.add_handler(CommandHandler("book", book))
    dispatcher.add_handler(CallbackQueryHandler(button))

    # on noncommand i.e message - echo the message on Telegram
    # dispatcher.add_handler(MessageHandler(Filters.text, echo))

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

