import asyncio
import logging
import signal
import sys
from typing import Optional

import simplematrixbotlib as botlib
import tomllib
import os

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger("sticker-bot")

# TODO: make these configurable
mstickereditorbinary = os.path.expanduser("~/.cargo/bin/mstickereditor")
mstickereditorconfig = os.path.expanduser("~/.config/mstickereditor/config.toml")

pack_target_dir = "/app/packs"

# read the configuration file of mstickereditor, since it already has login credentials for sticker upload.
try:
    with open(mstickereditorconfig, "rb") as f:
        config = tomllib.load(f)
except FileNotFoundError:
    logger.error(f"Configuration file not found at {mstickereditorconfig}")
    sys.exit(1)
except tomllib.TOMLDecodeError:
    logger.error(f"Invalid TOML format in configuration file {mstickereditorconfig}")
    sys.exit(1)
except Exception as e:
    logger.error(f"Error reading configuration file: {str(e)}")
    sys.exit(1)

if "sticker-bot" in config:
    if "pack_target_dir" in config["sticker-bot"]:
        pack_target_dir = config["sticker-bot"]["pack_target_dir"]

# Check if mstickereditorbinary exists
if not os.path.exists(mstickereditorbinary):
    logger.error(f"mstickereditor binary not found at {mstickereditorbinary}")
    sys.exit(1)

try:
    creds = botlib.Creds(config["matrix"]["homeserver_url"], config["matrix"]["user"],
                        access_token=config["matrix"]["access_token"])
    bot = botlib.Bot(creds)
except KeyError as e:
    logger.error(f"Missing required configuration key: {e}")
    sys.exit(1)
except Exception as e:
    logger.error(f"Error initializing bot: {str(e)}")
    sys.exit(1)

PREFIX = '!'

# Subprocess timeout in seconds
SUBPROCESS_TIMEOUT = 300  # 5 minutes

# Maximum size for stdout/stderr to store in memory (in bytes)
MAX_OUTPUT_SIZE = 1024 * 1024  # 1 MB


@bot.listener.on_message_event
async def echo(room, message):
    try:
        match = botlib.MessageMatch(room, message, bot, PREFIX)

        if not match.is_not_from_this_bot() or not match.prefix():
            return

        if not match.is_from_allowed_user():
            logger.info(f"Unauthorized access attempt from {message.sender}")
            await bot.api.send_text_message(room.room_id, "Go Away.")
            return

        if match.command("help"):
            logger.info(f"Help command received from {message.sender}")
            await bot.api.send_text_message(room.room_id,
                                            "Use this bot to import Telegram sticker packs.\nE.g.: `!addpack https://t.me/addstickers/hotcherry`."
                                            )
            return

        if match.command("addpack"):
            logger.info(f"Addpack command received from {message.sender}")
            
            # Check, if pack_dir exists for this user. If not, create it
            user_pack_path = os.path.join(pack_target_dir, match.event.sender)
            logger.info(f"User pack path: {user_pack_path}")
            
            try:
                if not os.path.exists(user_pack_path):
                    logger.info(f"Creating user pack path at {user_pack_path}")
                    os.makedirs(user_pack_path)
            except OSError as e:
                logger.error(f"Failed to create directory {user_pack_path}: {str(e)}")
                await bot.api.send_text_message(room.room_id, f"Error: Failed to create directory: {str(e)}")
                return

            if not len(match.args()) == 1:
                logger.warning(f"Invalid number of arguments from {message.sender}")
                await bot.api.send_text_message(room.room_id, "You need to provide exactly one argument.")
                return

            arg = match.args()[0]
            if not arg.startswith("https://t.me/addstickers/"):
                logger.warning(f"Invalid URL format from {message.sender}: {arg}")
                await bot.api.send_text_message(room.room_id,
                                                "You need to provide a URL starting with https://t.me/addstickers/"
                                                )
                return
                
            await bot.api.send_text_message(room.room_id, "Starting Import")
            
            # Import stickers
            try:
                logger.info(f"Starting import process for {arg}")
                proc = await create_subprocess_with_tracking(mstickereditorbinary, "import", arg,
                                                        cwd=user_pack_path,
                                                        stdout=asyncio.subprocess.PIPE,
                                                        stderr=asyncio.subprocess.PIPE)
                
                try:
                    stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=SUBPROCESS_TIMEOUT)
                    
                    # Unregister the process since it's completed
                    unregister_process(proc)
                    
                    # Truncate output if too large
                    stdout_str = stdout.decode(errors='replace')
                    stderr_str = stderr.decode(errors='replace')
                    
                    if len(stdout_str) > MAX_OUTPUT_SIZE:
                        stdout_str = stdout_str[:MAX_OUTPUT_SIZE] + "\n... (output truncated)"
                    if len(stderr_str) > MAX_OUTPUT_SIZE:
                        stderr_str = stderr_str[:MAX_OUTPUT_SIZE] + "\n... (output truncated)"
                    
                    if proc.returncode != 0:
                        logger.error(f"Import process failed with return code {proc.returncode}")
                        await bot.api.send_text_message(
                            room.room_id, f'Import Failed with return code {proc.returncode}.\n\n[stdout]\n{stdout_str}\n[stderr]\n{stderr_str}'
                        )
                        return
                        
                    await bot.api.send_text_message(
                        room.room_id, f'Import Done.\n\nResult:\n\n[stdout]\n{stdout_str}\n[stderr]\n{stderr_str}'
                    )
                    
                except asyncio.TimeoutError:
                    logger.error(f"Import process timed out after {SUBPROCESS_TIMEOUT} seconds")
                    proc.kill()
                    # Unregister the process after killing it
                    unregister_process(proc)
                    await bot.api.send_text_message(
                        room.room_id, f'Import timed out after {SUBPROCESS_TIMEOUT} seconds.'
                    )
                    return
                    
            except Exception as e:
                logger.error(f"Error during import process: {str(e)}")
                # Make sure to unregister the process if it exists
                if 'proc' in locals() and proc is not None:
                    try:
                        if proc.returncode is None:  # Process is still running
                            proc.kill()
                        unregister_process(proc)
                    except Exception as cleanup_error:
                        logger.error(f"Error during process cleanup: {str(cleanup_error)}")
                await bot.api.send_text_message(room.room_id, f"Error during import: {str(e)}")
                return

            # Rebuild index
            try:
                logger.info("Starting index creation process")
                proc = await create_subprocess_with_tracking(mstickereditorbinary, "create-index",
                                                        cwd=user_pack_path,
                                                        stdout=asyncio.subprocess.PIPE,
                                                        stderr=asyncio.subprocess.PIPE)
                
                try:
                    stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=SUBPROCESS_TIMEOUT)
                    
                    # Unregister the process since it's completed
                    unregister_process(proc)
                    
                    # Truncate output if too large
                    stdout_str = stdout.decode(errors='replace')
                    stderr_str = stderr.decode(errors='replace')
                    
                    if len(stdout_str) > MAX_OUTPUT_SIZE:
                        stdout_str = stdout_str[:MAX_OUTPUT_SIZE] + "\n... (output truncated)"
                    if len(stderr_str) > MAX_OUTPUT_SIZE:
                        stderr_str = stderr_str[:MAX_OUTPUT_SIZE] + "\n... (output truncated)"
                    
                    if proc.returncode != 0:
                        logger.error(f"Index creation process failed with return code {proc.returncode}")
                        await bot.api.send_text_message(
                            room.room_id, f'Index Creation Failed with return code {proc.returncode}.\n\n[stdout]\n{stdout_str}\n[stderr]\n{stderr_str}'
                        )
                        return
                        
                    await bot.api.send_text_message(
                        room.room_id, f'Index Created.\n\nResult:\n\n[stdout]\n{stdout_str}\n[stderr]\n{stderr_str}'
                    )
                    
                except asyncio.TimeoutError:
                    logger.error(f"Index creation process timed out after {SUBPROCESS_TIMEOUT} seconds")
                    proc.kill()
                    # Unregister the process after killing it
                    unregister_process(proc)
                    await bot.api.send_text_message(
                        room.room_id, f'Index creation timed out after {SUBPROCESS_TIMEOUT} seconds.'
                    )
                    return
                    
            except Exception as e:
                logger.error(f"Error during index creation: {str(e)}")
                # Make sure to unregister the process if it exists
                if 'proc' in locals() and proc is not None:
                    try:
                        if proc.returncode is None:  # Process is still running
                            proc.kill()
                        unregister_process(proc)
                    except Exception as cleanup_error:
                        logger.error(f"Error during process cleanup: {str(cleanup_error)}")
                await bot.api.send_text_message(room.room_id, f"Error during index creation: {str(e)}")
                return
                
            return
    except Exception as e:
        logger.error(f"Unhandled exception in message handler: {str(e)}")
        try:
            await bot.api.send_text_message(room.room_id, f"An unexpected error occurred: {str(e)}")
        except:
            pass


# Global variable to track active subprocesses
active_processes = set()

# Function to register a subprocess
def register_process(proc):
    active_processes.add(proc)

# Function to unregister a subprocess
def unregister_process(proc):
    if proc in active_processes:
        active_processes.remove(proc)

# Function to terminate all active subprocesses
def terminate_all_processes():
    for proc in list(active_processes):
        try:
            if proc.returncode is None:  # Process is still running
                logger.info(f"Terminating subprocess during shutdown")
                proc.kill()
        except Exception as e:
            logger.error(f"Error terminating subprocess: {str(e)}")

# Signal handler for graceful shutdown
def signal_handler():
    logger.info("Received shutdown signal, cleaning up...")
    terminate_all_processes()
    # Allow the bot to perform any necessary cleanup
    sys.exit(0)

# Register signal handlers
try:
    # For graceful shutdown on Ctrl+C
    signal.signal(signal.SIGINT, lambda sig, frame: signal_handler())
    # For graceful shutdown on SIGTERM (e.g., when run as a service)
    signal.signal(signal.SIGTERM, lambda sig, frame: signal_handler())
    logger.info("Signal handlers registered")
except Exception as e:
    logger.warning(f"Failed to register signal handlers: {str(e)}")

# Update the subprocess creation to register processes
async def create_subprocess_with_tracking(*args, **kwargs):
    proc = await asyncio.create_subprocess_exec(*args, **kwargs)
    register_process(proc)
    return proc

# Start the bot
logger.info("Starting Matrix sticker bot")
bot.run()
