"""
Audio and video downloader using Youtube-dl
.yta To Download in mp3 format
.ytv To Download in mp4 format
"""
import asyncio
import logging
import os
import re
import shutil
import time

from hachoir.metadata import extractMetadata
from hachoir.parser import createParser
from pymongo import MongoClient
from telethon import TelegramClient, events
from telethon.sync import TelegramClient
from telethon.tl.custom import Button
from telethon.tl.functions.users import GetFullUserRequest
from telethon.tl.types import DocumentAttributeVideo
from telethon.utils import get_display_name
from yt_dlp import YoutubeDL
from yt_dlp.utils import (ContentTooShortError, DownloadError, ExtractorError,
                          GeoRestrictedError, MaxDownloadsReached,
                          PostProcessingError, UnavailableVideoError,
                          XAttrMetadataError)

from config import APP_HASH, APP_ID, BOT_TOKEN, MONGO_DB
from util import (file_size, get_lst_of_files, take_screen_shot,
                  youtube_url_validation)

logging.basicConfig(format="%(name)s: %(message)s", level=logging.ERROR)
logger = logging.getLogger(__name__)

DELETE_TIMEOUT = 5
TMP_DOWNLOAD_DIRECTORY = "./DOWNLOADS/"
if not os.path.isdir(TMP_DOWNLOAD_DIRECTORY):
    os.makedirs(TMP_DOWNLOAD_DIRECTORY)


bot = TelegramClient("botasda", APP_ID, APP_HASH).start(bot_token=BOT_TOKEN)

loop = asyncio.get_event_loop()

# yasaklanan = []


SESSION_ADI = "playlist"


class playlist_db:
    def __init__(self):
        client = MongoClient(MONGO_DB)
        db = client["Telegram"]
        self.collection = db[SESSION_ADI]

    def ara(self, sorgu: dict):
        say = self.collection.count_documents(sorgu)
        if say == 1:
            return self.collection.find_one(sorgu, {"_id": 0})
        elif say > 1:
            cursor = self.collection.find(sorgu, {"_id": 0})
            return {
                bak["uye_id"]: {"uye_nick": bak["uye_nick"],
                                "uye_adi": bak["uye_adi"]}
                for bak in cursor
            }
        else:
            return None

    def ekle(self, uye_id, uye_nick, uye_adi):
        return (
            None
            if self.ara({"uye_id": {"$in": [str(uye_id), int(uye_id)]}})
            else self.collection.insert_one(
                {
                    "uye_id": uye_id,
                    "uye_nick": uye_nick,
                    "uye_adi": uye_adi,
                }
            )
        )

    def sil(self, uye_id):
        if not self.ara({"uye_id": {"$in": [str(uye_id), int(uye_id)]}}):
            return None

        self.collection.delete_one(
            {"uye_id": {"$in": [str(uye_id), int(uye_id)]}})
        return True

    @property
    def kullanici_idleri(self):
        return list(self.ara({"uye_id": {"$exists": True}}).keys())


@bot.on(events.NewMessage(pattern="/kul_say"))
async def say(event):
    j = await event.client(GetFullUserRequest(event.chat_id))

    db = playlist_db()
    db.ekle(j.user.id, j.user.username, j.user.first_name)

    def KULLANICILAR():
        return db.kullanici_idleri

    await event.client.send_message(
        "By_Azade", f"ℹ️ `{len(KULLANICILAR())}` __Adet Kullanıcıya Sahipsin..__"
    )


async def log_yolla(event):
    j = await event.client(GetFullUserRequest(event.chat_id))
    uye_id = j.user.id
    uye_nick = f"@{j.user.username}" if j.user.username else None
    uye_adi = f"{j.user.first_name or ''} {j.user.last_name or ''}".strip()
    komut = event.text

    # Kullanıcı Kaydet
    db = playlist_db()
    db.ekle(uye_id, uye_nick, uye_adi)


@bot.on(events.NewMessage(pattern="/duyuru ?(.*)"))
async def duyuru(event):
    # < Başlangıç
    await log_yolla(event)

    ilk_mesaj = await event.client.send_message(
        event.chat_id, "⌛️ `Hallediyorum..`", reply_to=event.chat_id, link_preview=False
    )
    # ------------------------------------------------------------- Başlangıç >

    db = playlist_db()

    def KULLANICILAR():
        return db.kullanici_idleri

    if not KULLANICILAR():
        await ilk_mesaj.edit("ℹ️ __Start vermiş kimse yok kanka..__")
        return

    if not event.message.reply_to:
        await ilk_mesaj.edit("⚠️ __Duyurmak için mesaj yanıtlayın..__")
        return

    basarili = 0
    hatalar = []
    mesaj_giden_kisiler = []
    get_reply_msg = await event.get_reply_message()
    for kullanici_id in KULLANICILAR():
        try:
            await event.client.send_message(
                entity=kullanici_id,
                message=get_reply_msg.message or get_reply_msg.media,
                link_preview=False,
            )
            mesaj_giden_kisiler.append(kullanici_id)
            basarili += 1
        except Exception as hata:
            hatalar.append(type(hata).__name__)
            db.sil(kullanici_id)

    mesaj = (
        f"⁉️ `{len(hatalar)}` __Adet Kişiye Mesaj Atamadım ve DB'den Sildim..__\n\n"
        if hatalar
        else ""
    )
    mesaj += f"📜 `{basarili}` __Adet Kullanıcıya Mesaj Attım..__"

    await ilk_mesaj.edit(mesaj)


@bot.on(events.NewMessage(pattern="/ekle ?(.*)", func=lambda e: e.is_private))
async def ekle(event):
    client = MongoClient(MONGO_DB)
    cli = client["Telegram"]["playlist_yasaklanan"]
    if event.chat_id == 184752635:
        user_kimlik = int(event.pattern_match.group(1))
        if user_kimlik != cli.find_one(
            {"uye_id": {"$in": [str(user_kimlik), user_kimlik]}}
        ):
            cli.insert_one({"uye_id": user_kimlik})
            # yasaklanan.append(int(user_kimlik))
            msg = "Yasaklanan: `{}`".format(user_kimlik)
            await bot.send_message("By_Azade", msg)


@bot.on(events.NewMessage(pattern="/kaldir ?(.*)", func=lambda e: e.is_private))
async def kaldir(event):
    client = MongoClient(MONGO_DB)
    cli = client["Telegram"]["playlist_yasaklanan"]
    if event.chat_id != 184752635:
        return
    user_kimlik = event.pattern_match.group(1)
    who_ = await event.client.get_entity(int(user_kimlik))
    name = get_display_name(who_)
    msg = "Yasağı kalkan:\n\n"
    msg += (
        f"İsim: [{name}](tg://user?id={int(user_kimlik)})\nID: `{int(user_kimlik)}`\n"
    )
    # if len(yasaklanan) == 0:
    if cli.find({"uye_id": {"$in": [str(user_kimlik), int(user_kimlik)]}}).count() == 0:
        msg += "**Yasaklanan kimse yok kanka..**"
        return
    cli.delete_one({"uye_id": user_kimlik})
    # yasaklanan.remove(int(user_kimlik))
    await bot.send_message("By_Azade", msg)


@bot.on(events.NewMessage(pattern="/liste", func=lambda e: e.is_private))
async def liste(event):
    client = MongoClient(MONGO_DB)
    cli = client["Telegram"]["playlist_yasaklanan"]
    msg = "Yasaklanan:\n\n"
    for j in cli.find():
        who_ = await event.client.get_entity(int(j["uye_id"]))
        name = get_display_name(who_)
        msg += (
            f"İsim: [{name}](tg://user?id={int(j['uye_id'])})\nID: `{j['uye_id']}`\n\n"
        )
    await bot.send_message("By_Azade", msg)


@bot.on(events.NewMessage(func=lambda e: e.is_private))
async def _(event):
    client = MongoClient(MONGO_DB)
    cli = client["Telegram"]["playlist_yasaklanan"]
    if cli.find_one({"uye_id": {"$in": [int(event.chat_id)]}}):
        await event.respond("🚫 Yasaklandın..\n🚫 You have been restricted.")
        return
    if event.message.message != ["/start", "/ekle", "/kaldir", "/liste"]:
        members = await event.client.get_entity(event.chat_id)
        isim = members.first_name
        kimlik = members.id
        mesaj = f"Gönderen [{isim}](tg://user?id={kimlik})\nMesaj: {event.text}\nID: {event.chat_id}"
        await bot.send_message(entity="By_Azade", message=mesaj, link_preview=False)
        kont = youtube_url_validation(event.message.message)
        if kont != "basarili":
            return
        markup = bot.build_reply_markup(
            [
                Button.inline(text="MP3", data="mp3"),
                Button.inline(text="Video", data="vid"),
                Button.url(text="Open", url=event.text),
            ]
            # [
            # ]
        )
        await bot.send_message(
            event.chat_id,
            "İndirmek istediğiniz türü seçin\n\nChoose the genre you want to download",
            buttons=markup,
        )


@bot.on(events.CallbackQuery(data=re.compile(b"vid")))
async def vid(event):
    x = await event.get_message()
    link = x.reply_markup.rows[-1].buttons[-1].url

    markup = bot.build_reply_markup(
        [
            Button.url(text="📍 Kanallar Gruplar", url="t.me/KanalLinkleri"),
            Button.url(text="👤 Yapımcı", url="t.me/By_Azade"),
        ]
    )
    out_folder = TMP_DOWNLOAD_DIRECTORY + "youtubedl/" + str(time.time()) + "/"
    thumb_image_path = TMP_DOWNLOAD_DIRECTORY + "/thumb_image.jpg"
    if not os.path.isdir(out_folder):
        os.makedirs(out_folder)
    opts = {
        "format": "best",
        "addmetadata": True,
        "noplaylist": False,
        "getthumbnail": True,
        "embedthumbnail": True,
        "xattrs": True,
        "writethumbnail": True,
        "key": "FFmpegMetadata",
        "prefer_ffmpeg": True,
        "geo_bypass": True,
        "nocheckcertificate": True,
        "postprocessors": [
            {"key": "FFmpegVideoConvertor", "preferedformat": "mp4"},
        ],
        "outtmpl": out_folder + "%(title)s.%(ext)s",
        "logtostderr": False,
        "quiet": True,
    }
    song = False
    video = True
    try:
        # await v_url.edit("`Playlist indiriliyor, lütfen bekleyin..`")
        bir = await bot.send_message(
            entity=event.original_update.user_id,
            message="`Playlist indiriliyor, lütfen bekleyin..`\nPlaylist downloading.. Please wait.",
        )
        await event.delete()
        with YoutubeDL(opts) as ytdl:
            ytdl_data = await loop.run_in_executor(None, ytdl.extract_info, link)
            logger.info(ytdl_data)

        filename = sorted(get_lst_of_files(out_folder, []))
    except DownloadError as DE:
        await bot.send_message(entity=event.original_update.user_id, message=f"`{DE}`")
        return
    except ContentTooShortError:
        # await v_url.edit("`İndirilecek dosya çok kısa`")
        await bot.send_message(
            entity=event.original_update.user_id,
            message="`İndirilecek dosya çok kısa`\nDownladed file too short",
        )
        return
    except GeoRestrictedError:
        # await v_url.edit(
        #     "`Video ülkenizde aktif değil`"
        # )
        await bot.send_message(
            entity=event.original_update.user_id,
            message="`İndirilecek dosya çok kısa`\nDownloaded file too short",
        )
        return
    except MaxDownloadsReached:
        # await v_url.edit("`Maksimum indirme limitine ulaştınız`")
        await bot.send_message(
            entity=event.original_update.user_id,
            message="`Maksimum indirme limitine ulaştınız`\nYoure reached out maximum limit",
        )
        return
    except PostProcessingError:
        # await v_url.edit("`There was an error during post processing.`")
        await bot.send_message(
            entity=event.original_update.user_id,
            message="`There was an error during post processing.`",
        )
        return
    except UnavailableVideoError:
        # await v_url.edit("`Media is not available in the requested format.`")
        await bot.send_message(
            entity=event.original_update.user_id,
            message="`Media is not available in the requested format.`",
        )
        return
    except XAttrMetadataError as XAME:
        await bot.send_message(
            entity=event.original_update.user_id,
            message=f"`{XAME.code}: {XAME.msg}\n{XAME.reason}`",
        )

        return
    except ExtractorError:

        await bot.send_message(
            entity=event.original_update.user_id,
            message="`There was an error during info extraction.`",
        )
        return
    except Exception as e:
        return
    c_time = time.time()
    await bir.edit(
        "`Playlist gönderiliyor, bekleyin...`\nPlaylist sending.. Please wait"
    )
    if video:
        for single_file in filename:
            if os.path.exists(single_file):
                caption_rts = os.path.basename(single_file)
                document_attributes = []
                if single_file.endswith((".mp4", ".mp3", ".flac", ".webm")):
                    metadata = extractMetadata(createParser(single_file))
                    duration = 0
                    if metadata.has("duration"):
                        duration = metadata.get("duration").seconds
                        width = 0
                        height = 0
                        document_attributes = [
                            DocumentAttributeVideo(
                                duration=duration,
                                w=width,
                                h=height,
                                round_message=False,
                                supports_streaming=True,
                            )
                        ]
                    file_path = single_file
                    video_size = file_size(file_path)
                    force_document = False
                    supports_streaming = True
                    try:
                        ytdl_data_name_video = os.path.basename(single_file)
                        thumb_image_path = await take_screen_shot(
                            single_file,
                            os.path.dirname(os.path.abspath(single_file)),
                            (duration / 2),
                        )
                        await bot.send_file(
                            event.original_update.user_id,
                            single_file,
                            caption=f"`{ytdl_data_name_video}`"
                            + "\n"
                            + f"`{video_size}`",
                            force_document=force_document,
                            supports_streaming=supports_streaming,
                            thumb=thumb_image_path,
                            allow_cache=False,
                            attributes=document_attributes,
                        )
                    except Exception as e:
                        await bot.send_message(
                            event.original_update.user_id,
                            "{} caused `{}`".format(caption_rts, str(e)),
                        )
                        continue
                    os.remove(single_file)
                    await asyncio.sleep(DELETE_TIMEOUT)
                    # await v_url.delete()
                    await bot.delete_messages(event.original_update.user_id, bir)

        shutil.rmtree(out_folder)
        await bot.send_message(
            entity=event.original_update.user_id,
            message="`Tüm playlist gönderildi.`\nAll playlist posted.",
        )


@bot.on(events.CallbackQuery(data=re.compile(b"mp3")))
async def mp3(event):
    x = await event.get_message()
    link = x.reply_markup.rows[-1].buttons[-1].url
    markup = bot.build_reply_markup(
        [
            Button.url(text="📍 Kanallar Gruplar", url="t.me/KanalLinkleri"),
            Button.url(text="👤 Yapımcı", url="t.me/By_Azade"),
        ]
    )

    out_folder = TMP_DOWNLOAD_DIRECTORY + "youtubedl/" + str(time.time()) + "/"
    thumb_image_path = TMP_DOWNLOAD_DIRECTORY + "/thumb_image.jpg"
    if not os.path.isdir(out_folder):
        os.makedirs(out_folder)
    opts = {
        "format": "bestaudio",
        "addmetadata": True,
        "noplaylist": False,
        "key": "FFmpegMetadata",
        "writethumbnail": True,
        "embedthumbnail": True,
        "prefer_ffmpeg": True,
        "geo_bypass": True,
        "nocheckcertificate": True,
        "postprocessors": [
            {
                "key": "FFmpegExtractAudio",
                "preferredcodec": "mp3",
                "preferredquality": "192",
            }
        ],
        "outtmpl": out_folder + "%(title)s.%(ext)s",
        "quiet": True,
        "logtostderr": False,
    }
    video = False
    song = True

    try:
        # await v_url.edit("`Playlist indiriliyor, lütfen bekleyin..`")
        bir = await bot.send_message(
            entity=event.original_update.user_id,
            message="`Playlist indiriliyor, lütfen bekleyin..`\nPlaylist downloading.. Please wait.",
        )
        await event.delete()

        with YoutubeDL(opts) as ytdl:
            # ytdl_data = ytdl.extract_info(link['link'])
            ytdl_data = await loop.run_in_executor(None, ytdl.extract_info, link)
            logger.info(ytdl_data)
            # print(ytdl_data['thumbnail'])
        filename = sorted(get_lst_of_files(out_folder, []))
    except DownloadError as DE:
        await bot.send_message(
            entity=event.original_update.user_id, message=f"`{DE}`"
        )
        return
    except ContentTooShortError:
        # await v_url.edit("`İndirilecek dosya çok kısa`")
        await bot.send_message(
            entity=event.original_update.user_id,
            message="`İndirilecek dosya çok kısa`\nDownloaded file too short",
        )
        return
    except GeoRestrictedError:
        # await v_url.edit(
        #     "`Video ülkenizde aktif değil`"
        # )
        await bot.send_message(
            entity=event.original_update.user_id,
            message="`İndirilecek dosya çok kısa`\nDownloaded file too short",
        )
        return
    except MaxDownloadsReached:
        # await v_url.edit("`Maksimum indirme limitine ulaştınız`")
        await bot.send_message(
            entity=event.original_update.user_id,
            message="`Maksimum indirme limitine ulaştınız`\nYoure reached out maximum limit",
        )
        return
    except PostProcessingError:
        # await v_url.edit("`There was an error during post processing.`")
        await bot.send_message(
            entity=event.original_update.user_id,
            message="`There was an error during post processing.`",
        )
        return
    except UnavailableVideoError:
        # await v_url.edit("`Media is not available in the requested format.`")
        await bot.send_message(
            entity=event.original_update.user_id,
            message="`Media is not available in the requested format.`",
        )
        return
    except XAttrMetadataError as XAME:
        await bot.send_message(
            entity=event.original_update.user_id,
            message=f"`{XAME.code}: {XAME.msg}\n{XAME.reason}`",
        )

        return
    except ExtractorError:

        await bot.send_message(
            entity=event.original_update.user_id,
            message="`There was an error during info extraction.`",
        )
        return
    except Exception as e:
        return
    c_time = time.time()

    await bir.edit(
        "`Playlist gönderiliyor, bekleyin...`\nPlaylist sending please wait."
    )

    if song:
        for single_file in filename:
            if os.path.exists(single_file):
                caption_rts = os.path.basename(single_file)
                force_document = True
                supports_streaming = False
                document_attributes = []
                if single_file.endswith((".mp4", ".mp3", ".flac", ".webm")):
                    metadata = extractMetadata(createParser(single_file))
                    duration = 0
                    if metadata.has("duration"):
                        duration = metadata.get("duration").seconds
                        width = 0
                        height = 180
                        document_attributes = [
                            DocumentAttributeVideo(
                                duration=duration,
                                w=width,
                                h=height,
                                round_message=False,
                                supports_streaming=True,
                            )
                        ]
                    try:
                        ytdl_data_name_audio = os.path.basename(single_file)
                        thumb_image_path = await take_screen_shot(
                            single_file,
                            os.path.dirname(os.path.abspath(single_file)),
                            (duration / 2),
                        )
                        file_path = single_file
                        song_size = file_size(file_path)
                        await bot.send_file(
                            event.original_update.user_id,
                            single_file,
                            caption=f"`{ytdl_data_name_audio}`"
                            + "\n"
                            + f"`{song_size}`",
                            supports_streaming=True,
                            allow_cache=False,
                            thumb=thumb_image_path,
                            attributes=document_attributes,
                        )
                    except Exception as e:

                        await bot.send_message(
                            event.original_update.user_id,
                            "{} caused `{}`".format(caption_rts, str(e)),
                        )
                        continue
                    os.remove(single_file)
                    await asyncio.sleep(DELETE_TIMEOUT)
                    # await v_url.delete()
        shutil.rmtree(out_folder)
        await bot.send_message(
            entity=event.original_update.user_id,
            message="`Tüm playlist gönderildi.`\nAll playlist posted.",
        )


@bot.on(events.NewMessage(pattern="(/|!).*start ?(.*)"))
async def _(event):
    await log_yolla(event)
    client = MongoClient(MONGO_DB)
    cli = client["Telegram"]["playlist_yasaklanan"]
    if cli.find_one({"uye_id": {"$in": [str(event.chat_id), event.chat_id]}}):
        return
    first_message = event.pattern_match.group(0)
    markup = bot.build_reply_markup(
        [
            [
                Button.url(text="📍 Kanal Linki", url="t.me/KanalLinkleri"),
                Button.url(text="👤 Yapımcı", url="t.me/By_Azade"),
            ],
            [
                Button.url(
                    text="🔗 GitHub Repo",
                    url="https://github.com/muhammedfurkan/pinterest_downloader_telegram",
                )
            ],
        ]
    )
    if first_message:
        mesaj = """
Merhaba! Bana belirtilen formatta bir YouTube playlist linki ver bunu senin için mp3 veya video olarak indireyim.
Hi! Give me a YouTube playlist link in the specified format and I'll download it as mp3 or video for you.


**Aktif komutlar:**
**Active commands:**

👉İndirmek istediğiniz playlist linkini atın ve indirmek istediğiniz formatı seçin (video/mp3)
👉Take the playlist link you want to download and choose the format you want to download (video / mp3)


🔹Bir işlem çalışırken ikinci bir işlem yaptırmayınız.
🔹Do not make a second operation while a process is running.

🔹[Kanallar Gruplar](t.me/KanalLinkleri)
🔹[My Channel](t.me/KanalLinkleri)

"""
        await event.client.send_message(event.chat_id, mesaj, buttons=markup)


bot.start()
bot.run_until_disconnected()
