# Matrix Sticker Import Bot

Matrix Sticker Import Bot is an open-source project that enables users to import Telegram stickers into their Stickerpicker instance using a Matrix bot. This project leverages the capabilities of the [Stickerpicker](https://github.com/maunium/stickerpicker) and [MStickerEditor](https://github.com/LuckyTurtleDev/mstickereditor) open-source projects, providing an easy-to-use Docker container that includes both projects. It hosts Stickerpicker, allowing each user to have their own personalized sticker packs.

## Features

- **Matrix Bot Integration**: Listens to Matrix chats and imports Telegram stickers into Stickerpicker.
- **Simple Docker Hosting**: Provides a straightforward Docker container setup that includes Stickerpicker, MStickerEditor, and the Sticker Import Bot.
- **User-Specific Sticker Packs**: Hosts Stickerpicker instances for each user, enabling individual management of sticker packs.

## Prerequisites

- Docker installed on your system.
- A Telegram bot key for fetching the stickers.
- Matrix account credentials (bot user account with access token, homeserver URL).

## Configuration

Configuration is similar to MStickerEditor, utilizing the same configuration file. Just use your bot credentials in the Matrix section, and you are set.

Example `config.toml` file:

```toml
[telegram]
bot_key = "your-telegram-bot-token"

[matrix]
user = "@sticker-bot:example.com"
homeserver_url = "https://example.com"
access_token = "your_matrix_access_token_for_sticker_bot_user"
```

## Running the Container

The container image is built on ghcr.io, so you can simply run it using `docker run`. Ensure to expose the port for the HTTP server, mount a directory where the JSON files for the sticker packs are stored, and mount the `config.toml` file into the container.

Example command:

```sh
docker run -d \
  -p 8080:8080 \
  -v /path/to/sticker-packs:/app/packs \
  -v /path/to/config.toml:/root/.config/mstickereditor/config.toml \
  ghcr.io/ClemensElflein/matrix-sticker-import-bot:latest
```

Replace `/path/to/sticker-packs` and `/path/to/config.toml` with the actual paths on your host system.

## Usage

- **Enable the Stickerpicker Widget**: In order to see the Stickerpicker Widget, send `/devtools` in any chat in Element. Then select `Explore account data`->`m.widgets` and set the content to this JSON:

  ```json
  {
    "stickerpicker": {
      "content": {
        "type": "m.stickerpicker",
        "url": "http://example.com:8080/stickerpicker/@you:example.com/?theme=$theme",
        "name": "Stickerpicker",
        "creatorUserId": "@you:example.com",
        "data": {}
      },
      "sender": "@you:example.com",
      "state_key": "stickerpicker",
      "type": "m.widget",
      "id": "stickerpicker"
    }
  }
  ```

  

- **Matrix Bot Commands**: Interact with the bot in Matrix chats to add new sticker packs to your Stickerpicker instance. Send `!help` to get the available commands.

## Technologies Used

- [Stickerpicker](https://github.com/maunium/stickerpicker): A fast and simple Matrix sticker picker widget.
- [MStickerEditor](https://github.com/LuckyTurtleDev/mstickereditor): A tool to import Telegram stickers for use in Stickerpicker.



## License

This project is licensed under the MIT License. See the [LICENSE](LICENSE) file for more details.



## Acknowledgments

Special thanks to the maintainers of [Stickerpicker](https://github.com/maunium/stickerpicker) and [MStickerEditor](https://github.com/LuckyTurtleDev/mstickereditor) for their amazing projects.

