from aiogram.types import ContentType
from aiogram_dialog import Dialog, Window
from aiogram_dialog.widgets.kbd import SwitchTo, Column, Row, Button, Group, Select, Start, Url
from aiogram_dialog.widgets.text import Format, Const
from aiogram_dialog.widgets.input import TextInput, MessageInput
from aiogram_dialog.widgets.media import DynamicMedia

from dialogs.user_dialog import getters

from states.state_groups import startSG, adminSG

user_dialog = Dialog(
    Window(
        Const('Главное меню'),
        Column(
            SwitchTo(Const('Управление каналами'), id='channels_switcher', state=startSG.channels),
            SwitchTo(Const('Управление медиа'), id='medias_switcher', state=startSG.medias),
        ),
        state=startSG.start
    ),
    Window(
        Format('{text}'),
        Column(
            SwitchTo(Const('➕Добавить канал'), id='add_channel_switcher', state=startSG.get_channel),
            SwitchTo(Const('✏️Редактирование каналов'), id='choose_channel_switcher', state=startSG.choose_channel),
        ),
        SwitchTo(Const('⬅️Назад'), id='back', state=startSG.start),
        getter=getters.channels_getter,
        state=startSG.channels
    ),
    Window(
        Const('Введите ID канала или его юзернейм\n\n<em>❗️Убедитесь что вы добавили бота в администраторы канала</em>'),
        TextInput(
            id='get_channel',
            on_success=getters.get_channel
        ),
        SwitchTo(Const('⬅️Назад'), id='back_channels', state=startSG.channels),
        state=startSG.get_channel
    ),
    Window(
        Const('Введите время название города, которое будет отображаться с постах с погодой в каналах'),
        TextInput(
            id='get_city',
            on_success=getters.get_city
        ),
        SwitchTo(Const('⬅️Назад'), id='back_get_channel', state=startSG.get_channel),
        state=startSG.get_city
    ),
    Window(
        Const('Введите время в которое каждый день в канале будет выходить пост о погоде (hh:mm)'),
        TextInput(
            id='get_time',
            on_success=getters.get_time
        ),
        SwitchTo(Const('⬅️Назад'), id='back_get_city', state=startSG.get_city),
        state=startSG.get_time
    ),
    Window(
        Const('Выберите канал, который вы хотели бы подредактировать:'),
        Group(
            Select(
                Format('{item[0]}'),
                id='choose_channel_builder',
                item_id_getter=lambda x: x[1],
                items='items',
                on_click=getters.channel_selector
            ),
            width=1
        ),
        Row(
            Button(Const('◀️'), id='back_channels_pager', on_click=getters.channels_pager, when='not_first'),
            Button(Format('{page}'), id='channels_pager', when='channels'),
            Button(Const('▶️'), id='next_channels_pager', on_click=getters.channels_pager, when='not_last')
        ),
        SwitchTo(Const('⬅️Назад'), id='back_channels', state=startSG.channels),
        getter=getters.choose_channel_getter,
        state=startSG.choose_channel
    ),
    Window(
        Format('{text}'),
        Column(
            SwitchTo(Const('🕝Изменить время поста'), id='change_time_switcher', state=startSG.change_time),
            SwitchTo(Const('🗑Удалить канал'), id='del_channel_switcher', state=startSG.del_channel),
        ),
        SwitchTo(Const('⬅️Назад'), id='back_channels', state=startSG.channels),
        getter=getters.channel_menu_getter,
        state=startSG.channel_menu
    ),
    Window(
        Const('Вы уверены, что хотите удалить данный канал?'),
        Row(
            Button(Const('Удалить❓'), id='del_channel', on_click=getters.del_channel),
            SwitchTo(Const('❌Отмена'), id='back_channel_menu', state=startSG.channel_menu),
        ),
        state=startSG.del_channel
    ),
    Window(
        Const('Введите новое время в которое каждый день в канале будет выходить пост о погоде (hh:mm)'),
        TextInput(
            id='change_time',
            on_success=getters.change_time
        ),
        SwitchTo(Const('⬅️Назад'), id='back_channel_menu', state=startSG.channel_menu),
        state=startSG.change_time
    ),
    Window(
        Format('{text}'),
        Column(
            SwitchTo(Const('➕Добавить медиа'), id='get_medias_switcher', state=startSG.get_medias),
            SwitchTo(Const('🏞Просмотр медиа'), id='watch_medias_switcher', state=startSG.watch_medias),
        ),
        SwitchTo(Const('⬅️Назад'), id='back', state=startSG.start),
        getter=getters.medias_getter,
        state=startSG.medias
    ),
    Window(
        Const('Отправляйте одиночные медиафайлы и после того как отправите все необходимые '
              'медиа нажмите кнопку "✅Добавить"'),
        Format('Медиа в базе: {medias}'),
        MessageInput(
            func=getters.get_media,
            content_types=ContentType.ANY
        ),
        Column(
            Button(Const('✅Добавить'), id='add_media', on_click=getters.add_media),
            Button(Const('🗑Почистить загруженные медиа'), id='clean_media', on_click=getters.clean_media),
        ),
        SwitchTo(Const('⬅️Назад'), id='back_medias', state=startSG.medias),
        getter=getters.get_medias_getter,
        state=startSG.get_medias
    ),
    Window(
        DynamicMedia('media', when='media'),
        Const("Меню просмотра медиа"),
        Row(
            Button(Const('◀️'), id='back_medias_pager', on_click=getters.medias_pager, when='not_first'),
            Button(Format('{page}'), id='medias_pager', when='media'),
            Button(Const('▶️'), id='next_medias_pager', on_click=getters.medias_pager, when='not_last')
        ),
        Column(
            Button(Const('🗑Удалить'), id='del_media', on_click=getters.del_media, when='media'),
        ),
        SwitchTo(Const('⬅️Назад'), id='back_medias', state=startSG.medias),
        getter=getters.watch_medias_getter,
        state=startSG.watch_medias
    ),
)