from crawler import GithubCrawler
import json


def crawler_from_json(path: str) -> GithubCrawler:
    data = json.load(open(path))
    return GithubCrawler(data["keywords"], data["proxies"], data["type"])


if __name__ == "__main__":
    print(crawler_from_json("example_data/data_1.json").crawl(1))
    print(crawler_from_json("example_data/data_2.json").crawl(1))
    print(crawler_from_json("example_data/data_3.json").crawl(1))
