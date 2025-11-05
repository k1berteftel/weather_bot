from aiogram.fsm.state import State, StatesGroup

# Обычная группа состояний


class startSG(StatesGroup):
    start = State()

    channels = State()
    get_channel = State()
    get_city = State()
    get_time = State()

    choose_channel = State()
    channel_menu = State()
    change_time = State()
    del_channel = State()

    medias = State()
    get_medias = State()
    watch_medias = State()


class adminSG(StatesGroup):
    start = State()
    get_mail = State()
    get_time = State()
    get_keyboard = State()
    confirm_mail = State()
    deeplink_menu = State()
    deeplink_del = State()
    admin_menu = State()
    admin_del = State()
    admin_add = State()
