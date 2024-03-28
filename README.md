# article-summarizer
This application summarizes blog articles using OpenAI.
The summarized results are stored in Azure Table Storage.
Additionally, it can also send notifications via Slack WebHook.

## Prerequisites
- Windows 10 64-bit or Windows 11 64-bit.
- Enable hardware virtualization in BIOS.
- Install Windows Terminal.
- Install [WSL](https://learn.microsoft.com/en-us/windows/wsl/install) and set up a user name and password for your Linux distribution running in WSL 2.
    - Install [Docker Engine](https://docs.docker.com/engine/install/ubuntu/#install-using-the-convenience-script) on Linux (WSL 2).
    - Add current user into `docker` group: `sudo usermod -aG docker $USER`
- Install the VS Code.
    - Turn on `Dev Containers: Execute In WSL` in Preference -> Settings.
- Install the VS Code WSL extension.
- Install the VS Code Dev Containers extension.
- Install the VS Code Docker extension.

## Develop
- Open the `src` folder in VSCode.
- Use Command Palette (F1) to select `Dev Containers: Reopen in Container`.
- Create an .env file in the src directory and define API_KEY. (API_KEY={api_key})
- Start debugging using the `F5` key.
- The results are stored in a table named `summarizer` in the local Azure Storage Emulator. (Use of ephemeral ports)

## Build
`docker build --tag article-summarizer .`

## Run
`docker run -e STORAGE_CONNECTION_STRING="{connection_string}" -e RSS_URL="{rss_url_1|rss_url_2|rss_url_3}" -e API_KEY="{api_key}" -e OUTPUT_LANGUAGE="{language}" -e SLACK_WEBHOOK_URL="{webhook_url_1|webhook_url_2|webhook_url_3}" -it --rm article-summarizer`

