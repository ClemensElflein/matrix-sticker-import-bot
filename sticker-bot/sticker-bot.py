import asyncio

import simplematrixbotlib as botlib
import tomllib
import os

# TODO: make these configurable
mstickereditorbinary = os.path.expanduser("~/.cargo/bin/mstickereditor")
mstickereditorconfig = os.path.expanduser("~/.config/mstickereditor/config.toml")

pack_target_dir = "/app/packs"

# read the configuration file of mstickereditor, since it already has login credentials for sticker upload.
with open(mstickereditorconfig, "rb") as f:
    config = tomllib.load(f)

if "sticker-bot" in config:
    if "pack_target_dir" in config["sticker-bot"]:
        pack_target_dir = config["sticker-bot"]["pack_target_dir"]

creds = botlib.Creds(config["matrix"]["homeserver_url"], config["matrix"]["user"],
                     access_token=config["matrix"]["access_token"])
bot = botlib.Bot(creds)
PREFIX = '!'


@bot.listener.on_message_event
async def echo(room, message):
    match = botlib.MessageMatch(room, message, bot, PREFIX)

    if not match.is_not_from_this_bot() or not match.prefix():
        return

    if not match.is_from_allowed_user():
        await bot.api.send_text_message(room.room_id, "Go Away.")
        return

    if match.command("help"):
        await bot.api.send_text_message(room.room_id,
                                        "Use this bot to import Telegram sticker packs.\nE.g.: `!addsticker https://t.me/addstickers/hotcherry`."
                                        )
        return

    if match.command("addpack"):
        # Check, if pack_dir exists for this user. If not, create it
        user_pack_path = os.path.join(pack_target_dir, match.event.sender)
        print("user_pack_path", user_pack_path)
        if not os.path.exists(user_pack_path):
            print("creating user_pack_path at ", user_pack_path)
            os.makedirs(user_pack_path)

        if not len(match.args()) == 1:
            await bot.api.send_text_message(room.room_id, "You need to provide exactly one argument.")
            return

        arg = match.args()[0]
        if not arg.startswith("https://t.me/addstickers/"):
            await bot.api.send_text_message(room.room_id,
                                            "You need to provide a URL starting with https://t.me/addstickers/"
                                            )
            return
        await bot.api.send_text_message(room.room_id, "Starting Import")
        proc = await asyncio.create_subprocess_exec(mstickereditorbinary, "import", arg,
                                                    cwd=user_pack_path,
                                                    stdout=asyncio.subprocess.PIPE,
                                                    stderr=asyncio.subprocess.PIPE)

        stdout, stderr = await proc.communicate()

        await bot.api.send_text_message(
            room.room_id, f'Import Done.\n\nResult:\n\n[stdout]\n{stdout.decode()}\n[stderr]\n{stderr.decode()}'
        )

        # rebuild index
        proc = await asyncio.create_subprocess_exec(mstickereditorbinary, "create-index",
                                                    cwd=user_pack_path,
                                                    stdout=asyncio.subprocess.PIPE,
                                                    stderr=asyncio.subprocess.PIPE)

        stdout, stderr = await proc.communicate()

        await bot.api.send_text_message(
            room.room_id, f'Index Created.\n\nResult:\n\n[stdout]\n{stdout.decode()}\n[stderr]\n{stderr.decode()}'
        )
        return


bot.run()
