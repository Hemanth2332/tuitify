import time
import yt_dlp
import vlc


class YTStreamVLC:
    def __init__(self, url: str):
        self.url = url
        self.instance = vlc.Instance("--no-video")
        self.player = self.instance.media_player_new()
        self.current_time = 0  # milliseconds
        self.duration = None

    def get_stream_info(self):
        ydl_opts = {
            "quiet": True,
            "no_warnings": True,
            "format": "bestaudio/best",
        }

        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(self.url, download=False)
            return info["url"], info.get("duration")

    def play(self, stream_url):
        media = self.instance.media_new(stream_url)
        self.player.set_media(media)
        self.player.play()

        # wait for VLC to start
        time.sleep(1)

        if self.current_time > 0:
            print(f"Resuming at {self.current_time/1000:.2f}s")
            self.player.set_time(int(self.current_time))

    def start(self):
        while True:
            try:
                print("Fetching stream URL...")
                stream_url, duration = self.get_stream_info()

                if duration:
                    self.duration = duration * 1000  # ms

                self.play(stream_url)

                while True:
                    state = self.player.get_state()

                    if state in [vlc.State.Ended, vlc.State.Error]:
                        raise Exception("Stream ended or error")

                    # update current playback time
                    t = self.player.get_time()
                    if t > 0:
                        self.current_time = t

                    time.sleep(1)

            except Exception as e:
                print(f"Reconnecting... last position {self.current_time/1000:.2f}s")
                time.sleep(1)


if __name__ == "__main__":
    url = "https://www.youtube.com/watch?v=RMbFjeVonyg"
    player = YTStreamVLC(url)
    player.start()
    