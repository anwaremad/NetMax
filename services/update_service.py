import requests

APP_VERSION = "1.0.1"

GITHUB_REPO = "anwaremad/NetMax"


class UpdateService:
    @staticmethod
    def check_for_updates():
        try:
            url = f"https://api.github.com/repos/{GITHUB_REPO}/releases/latest"

            response = requests.get(url, timeout=5)
            response.raise_for_status()

            data = response.json()

            latest_version = data["tag_name"].replace("v", "")
            release_url = data["html_url"]

            if latest_version != APP_VERSION:
                return {
                    "available": True,
                    "version": latest_version,
                    "url": release_url,
                }

        except Exception as e:
            print("Update check failed:", e)

        return {
            "available": False
        }