import asyncio
import os
import re
from typing import Union

import yt_dlp
from pyrogram.enums import MessageEntityType
from pyrogram.types import Message
from youtubesearchpython.__future__ import VideosSearch

from AudifyMusic.utils.database import is_on_off
from AudifyMusic.utils.formatters import time_to_seconds

cookies_file = "cookies/cookies.txt"


async def shell_cmd(cmd):
    proc = await asyncio.create_subprocess_shell(
        cmd,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    out, errorz = await proc.communicate()
    if errorz:
        if "unavailable videos are hidden" in (errorz.decode("utf-8")).lower():
            return out.decode("utf-8")
        else:
            return errorz.decode("utf-8")
    return out.decode("utf-8")


class YouTubeAPI:
    def __init__(self):
        self.base = "https://www.youtube.com/watch?v="
        self.regex = r"(?:youtube\.com|youtu\.be)"
        self.listbase = "https://youtube.com/playlist?list="
        self.reg = re.compile(r"\x1B(?:[@-Z\\-_]|\[[0-?]*[ -/]*[@-~])")

    # ------------------ CHECK IF URL IS YOUTUBE ------------------ #
    async def exists(self, link: str, videoid: Union[bool, str] = None):
        if videoid:
            link = self.base + link
        return bool(re.search(self.regex, link))

    # ------------------ EXTRACT URL FROM MESSAGE ------------------ #
    async def url(self, message_1: Message) -> Union[str, None]:
        messages = [message_1]
        if message_1.reply_to_message:
            messages.append(message_1.reply_to_message)
        text = ""
        offset = None
        length = None
        for message in messages:
            if offset:
                break
            if message.entities:
                for entity in message.entities:
                    if entity.type == MessageEntityType.URL:
                        text = message.text or message.caption
                        offset, length = entity.offset, entity.length
                        break
            elif message.caption_entities:
                for entity in message.caption_entities:
                    if entity.type == MessageEntityType.TEXT_LINK:
                        return entity.url
        if offset is None:
            return None
        return text[offset : offset + length]

    # ------------------ VIDEO DETAILS ------------------ #
    async def details(self, link: str, videoid: Union[bool, str] = None):
        try:
            if videoid:
                link = self.base + link
            link = link.split("&")[0]

            # Convert Shorts to regular watch links
            if "shorts/" in link:
                link = link.replace("shorts/", "watch?v=")

            results = VideosSearch(link, limit=1)
            data = await results.next()
            if not data.get("result"):
                return None, None, None, None, None

            result = data["result"][0]
            title = result.get("title", "Unknown Title")
            duration_min = result.get("duration", "0:00")
            thumbnail = result["thumbnails"][0]["url"].split("?")[0]
            vidid = result["id"]
            duration_sec = int(time_to_seconds(duration_min)) if duration_min else 0

            return title, duration_min, duration_sec, thumbnail, vidid
        except Exception as e:
            print(f"[YouTubeAPI.details] Error: {e}")
            return None, None, None, None, None

    # ------------------ VIDEO TITLE ------------------ #
    async def title(self, link: str, videoid: Union[bool, str] = None):
        try:
            if videoid:
                link = self.base + link
            link = link.split("&")[0]
            if "shorts/" in link:
                link = link.replace("shorts/", "watch?v=")
            results = VideosSearch(link, limit=1)
            for result in (await results.next())["result"]:
                return result["title"]
        except:
            return None

    # ------------------ VIDEO DURATION ------------------ #
    async def duration(self, link: str, videoid: Union[bool, str] = None):
        try:
            if videoid:
                link = self.base + link
            link = link.split("&")[0]
            if "shorts/" in link:
                link = link.replace("shorts/", "watch?v=")
            results = VideosSearch(link, limit=1)
            for result in (await results.next())["result"]:
                return result["duration"]
        except:
            return None

    # ------------------ VIDEO THUMBNAIL ------------------ #
    async def thumbnail(self, link: str, videoid: Union[bool, str] = None):
        try:
            if videoid:
                link = self.base + link
            link = link.split("&")[0]
            if "shorts/" in link:
                link = link.replace("shorts/", "watch?v=")
            results = VideosSearch(link, limit=1)
            for result in (await results.next())["result"]:
                return result["thumbnails"][0]["url"].split("?")[0]
        except:
            return None

    # ------------------ VIDEO DIRECT LINK ------------------ #
    async def video(self, link: str, videoid: Union[bool, str] = None):
        if videoid:
            link = self.base + link
        link = link.split("&")[0]
        proc = await asyncio.create_subprocess_exec(
            "yt-dlp",
            "--cookies", cookies_file,
            "-g",
            "-f",
            "best[height<=?720][width<=?1280]",
            f"{link}",
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout, stderr = await proc.communicate()
        if stdout:
            return 1, stdout.decode().split("\n")[0]
        return 0, stderr.decode()

    # ------------------ PLAYLIST ------------------ #
    async def playlist(self, link, limit, user_id, videoid: Union[bool, str] = None):
        if videoid:
            link = self.listbase + link
        link = link.split("&")[0]
        playlist = await shell_cmd(
            f"yt-dlp --cookies {cookies_file} -i --get-id --flat-playlist --playlist-end {limit} --skip-download {link}"
        )
        try:
            result = [x for x in playlist.split("\n") if x]
        except:
            result = []
        return result

    # ------------------ TRACK INFO ------------------ #
    async def track(self, link: str, videoid: Union[bool, str] = None):
        if videoid:
            link = self.base + link
        link = link.split("&")[0]
        if "shorts/" in link:
            link = link.replace("shorts/", "watch?v=")
        results = VideosSearch(link, limit=1)
        data = await results.next()
        if not data.get("result"):
            return None, None
        result = data["result"][0]
        track_details = {
            "title": result["title"],
            "link": result["link"],
            "vidid": result["id"],
            "duration_min": result["duration"],
            "thumb": result["thumbnails"][0]["url"].split("?")[0],
        }
        return track_details, result["id"]

    # ------------------ AVAILABLE FORMATS ------------------ #
    async def formats(self, link: str, videoid: Union[bool, str] = None):
        if videoid:
            link = self.base + link
        link = link.split("&")[0]
        ytdl_opts = {"quiet": True, "cookiefile": cookies_file}
        ydl = yt_dlp.YoutubeDL(ytdl_opts)
        formats_available = []
        with ydl:
            r = ydl.extract_info(link, download=False)
            for format in r.get("formats", []):
                try:
                    if "dash" not in str(format["format"]).lower():
                        formats_available.append(
                            {
                                "format": format.get("format"),
                                "filesize": format.get("filesize"),
                                "format_id": format.get("format_id"),
                                "ext": format.get("ext"),
                                "format_note": format.get("format_note"),
                                "yturl": link,
                            }
                        )
                except:
                    continue
        return formats_available, link

    # ------------------ SLIDER / SEARCH ------------------ #
    async def slider(self, link: str, query_type: int, videoid: Union[bool, str] = None):
        if videoid:
            link = self.base + link
        link = link.split("&")[0]
        if "shorts/" in link:
            link = link.replace("shorts/", "watch?v=")
        a = VideosSearch(link, limit=10)
        result = (await a.next()).get("result")
        title = result[query_type]["title"]
        duration_min = result[query_type]["duration"]
        vidid = result[query_type]["id"]
        thumbnail = result[query_type]["thumbnails"][0]["url"].split("?")[0]
        return title, duration_min, thumbnail, vidid

    # ------------------ DOWNLOAD FUNCTION ------------------ #
    async def download(
        self,
        link: str,
        mystic,
        video: Union[bool, str] = None,
        videoid: Union[bool, str] = None,
        songaudio: Union[bool, str] = None,
        songvideo: Union[bool, str] = None,
        format_id: Union[bool, str] = None,
        title: Union[bool, str] = None,
    ) -> str:
        if videoid:
            link = self.base + link
        loop = asyncio.get_running_loop()

        def audio_dl():
            ydl_opts = {
                "format": "bestaudio/best",
                "outtmpl": "downloads/%(id)s.%(ext)s",
                "quiet": True,
                "nocheckcertificate": True,
                "geo_bypass": True,
                "cookiefile": cookies_file,
            }
            x = yt_dlp.YoutubeDL(ydl_opts)
            info = x.extract_info(link, False)
            xyz = os.path.join("downloads", f"{info['id']}.{info['ext']}")
            if os.path.exists(xyz):
                return xyz
            x.download([link])
            return xyz

        def video_dl():
            ydl_opts = {
                "format": "(bestvideo[height<=?720][width<=?1280][ext=mp4])+(bestaudio[ext=m4a])",
                "outtmpl": "downloads/%(id)s.%(ext)s",
                "quiet": True,
                "nocheckcertificate": True,
                "geo_bypass": True,
                "cookiefile": cookies_file,
            }
            x = yt_dlp.YoutubeDL(ydl_opts)
            info = x.extract_info(link, False)
            xyz = os.path.join("downloads", f"{info['id']}.{info['ext']}")
            if os.path.exists(xyz):
                return xyz
            x.download([link])
            return xyz

        if songvideo:
            await loop.run_in_executor(None, video_dl)
            fpath = f"downloads/{title}.mp4"
            return fpath
        elif songaudio:
            await loop.run_in_executor(None, audio_dl)
            fpath = f"downloads/{title}.mp3"
            return fpath
        elif video:
            if await is_on_off(1):
                downloaded_file = await loop.run_in_executor(None, video_dl)
                direct = True
            else:
                proc = await asyncio.create_subprocess_exec(
                    "yt-dlp",
                    "--cookies", cookies_file,
                    "-g",
                    "-f",
                    "best[height<=?720][width<=?1280]",
                    f"{link}",
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE,
                )
                stdout, stderr = await proc.communicate()
                if stdout:
                    downloaded_file = stdout.decode().split("\n")[0]
                    direct = None
                else:
                    return
            return downloaded_file, direct
        else:
            downloaded_file = await loop.run_in_executor(None, audio_dl)
            direct = True
        return downloaded_file, direct
