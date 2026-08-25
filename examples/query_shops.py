"""Query WangDian shops using credentials from environment variables."""

import os

from wangdian import WangdianClient


def main() -> None:
    with WangdianClient(
        sid=os.environ["WDT_SID"],
        app_key=os.environ["WDT_APP_KEY"],
        app_secret=os.environ["WDT_APP_SECRET"],
        environment=os.getenv("WDT_ENV", "test"),
    ) as client:
        result = client.call("shop", {"page_no": 0, "page_size": 100})
        print(result)


if __name__ == "__main__":
    main()

