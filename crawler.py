import requests
from bs4 import BeautifulSoup
from threading import Thread
from typing import List
import json
from random import choice
import re
from queue import Queue


class GithubCrawler:
    _base_link = "https://github.com/"
    _wiki_link = "wiki/"
    _issues_link = "issues/"
    _repo_param = {"tab": "repositories"}
    _username_valid_ascii = tuple(range(48, 58)) + tuple(range(97, 123)) + (45,)
    _max_chr_num = 39
    _max_user_threads = 3

    def __init__(self, keywords: List[str], proxies: List[str], content_type: str):
        self.keywords = "|".join([".*" + keyword.lower() + r".*" for keyword in keywords])
        self.proxies = ["http://" + prox for prox in proxies]
        self.type = content_type.lower()
        self._results = []

    def crawl(self, needed: int = None) -> str:
        process = Thread(target=self._run_main_thread, args=(needed,))
        process.start()
        process.join()
        return json.dumps(self._results)

    def _run_main_thread(self, needed: int = None) -> None:
        counter = 0
        threads = []
        max_length = len(self._username_valid_ascii) ** (self._max_chr_num + 1)

        while counter < max_length and (needed is None or len(self._results) < needed):
            threads = list(filter(lambda el: el.is_alive(), threads))

            if len(threads) < self._max_user_threads:
                cur = Thread(target=self._search_by_user_num, args=(counter,), daemon=True)
                cur.start()
                threads.append(cur)

                counter += 1

    def _check_repos(self, username: str) -> None:
        if self._are_keywords_matched(self._get_repos(username)):
            self._add_result(self._base_link + username)

    def _check_wikis(self, username: str) -> None:
        threads = []
        for repo in self._get_repos(username):
            self._start_thread(_check_wikis_text_by_repo, (username, repo), threads)
        for el in threads:
            el.join()

    def _check_issues(self, username: str) -> None:
        threads = []
        for repo in self._get_repos(username):
            self._start_thread(_check_issues_by_repo, (username, repo), threads)
        for el in threads:
            el.join()

    def _search_by_user_num(self, user_num):
        try:
            username = self._num_to_user(user_num)
            if self.type == "repositories":
                self._check_repos(username)
            elif self.type == "wikis":
                self._check_wikis(username)
            elif self.type == "issues":
                self._check_issues(username)
            else:
                return
        except requests.exceptions.ConnectTimeout as e:
            print("Problem with proxy", e)

    def _get_repos(self, username: str) -> List:
        repositories = []
        parsed = self._parsed_request(self._base_link + username, self._repo_param)
        if parsed is not None:
            repositories = [repo.get_text()[1:].replace(" ", "") for repo in
                            parsed.find_all("a", itemprop="name codeRepository")]
            parsed(repositories)
        return repositories

    def _get_wiki_list_in_repo(self, username: str, repo: str) -> List:
        wikis = []
        parsed = self._parsed_request(self._base_link + username + "/" + repo + "/" + self._wiki_link)
        if parsed is not None:
            wikis = [wiki.get_text() for wiki in parsed.find_all("a", class_="flex-1 py-1 text-bold")]
        return wikis

    def _check_wiki_in_repo(self, username: str, repo: str):
        threads = []
        for wiki in self._get_wiki_list_in_repo(username, repo):
            self._start_thread(_check_wiki_in_repo_by_name, (username, repo, wiki), threads)
        for el in threads:
            el.join()

    def _check_wiki_in_repo_by_name(self, username: str, repo: str, wiki: str):
        link = self._base_link + username + "/" + repo + "/" + self._wiki_link + wiki
        parsed = self._parsed_request(link)
        if parsed is not None:
            content = [wiki] + [el.get_text() for el in parsed.find("div", class_="markdown-body").find_all(
                ["a", "p", "span", "h1", "h2", "h3", "h4", "h5", "h6"])]
            if self._are_keywords_matched(content):
                self._add_result(link)

    def _get_issues_list_in_repo(self, username: str, repo: str) -> List:
        link = self._base_link + username + "/" + repo + "/" + self._issues_link
        issues_link = []
        while True:
            parsed = self._parsed_request(link)
            if parsed is None:
                break
            issues_link += [issue.get("href") for issue in
                            parsed.find_all("a", class_="d-block d-md-none position-absolute "
                                                        "top-0 bottom-0 left-0 right-0")]
            if parsed.find("a", class_="next_page") is None:
                break
            link = self._base_link + parsed.find("a", class_="next_page").get("href")
        return issues_link

    def _check_issues_in_repo(self, username: str, repo: str):
        for issue in self._get_issues_list_in_repo(username, repo):
            self._check_issues_in_repo_by_name(issue)

    def _check_issues_in_repo_by_name(self, issue_link: str):
        link = self._base_link + issue_link
        parsed = self._parsed_request(link)
        if parsed is not None:
            content = [parsed.find("span", class_="js-issue-title markdown-title").get_text()] + \
                      [el.find("p").get_text() for el in parsed.find_all("td", class_="comment-body")]
            if self._are_keywords_matched(content):
                self._add_result(link)

    @classmethod
    def _num_to_user(cls, num: int) -> str:
        valid_ascii_len = len(cls._username_valid_ascii)
        if num < valid_ascii_len:
            return chr(cls._username_valid_ascii[num])
        else:
            return cls._num_to_user(num // valid_ascii_len) + \
                   chr(cls._username_valid_ascii[num % valid_ascii_len])

    def _parsed_request(self, link: str, params: dict = None):
        if params is None:
            params = {}
        resp = requests.get(link, proxies={"http": choice(self.proxies)}, params=params)
        if resp.status_code == 200:
            return BeautifulSoup(resp.content, "html.parser")
        return None

    def _add_result(self, el: str) -> None:
        self._results.append({"url": el})

    def _are_keywords_matched(self, txt_list: List[str]) -> bool:
        for txt in txt_list:
            if re.match(self.keywords, txt.lower()) is not None:
                return True
        return False

    @staticmethod
    def _start_thread(func, args, temp):
        cur = Thread(target=func, args=args, daemon=True)
        cur.start()
        temp.append(cur)

    def __str__(self) -> str:
        return f"Crawler(keywords: {self.keywords}, proxies: {self.proxies}, content_type: {self.content_type})"
