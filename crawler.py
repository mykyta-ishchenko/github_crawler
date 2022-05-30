import requests
from bs4 import BeautifulSoup
from threading import Thread
from typing import List
import json
from random import choice
import re
from queue import Queue


class GithubCrawler:
    """
    Class containing methods for handling github webpages.

    _username_valid_ascii - ascii character values suitable for name in github.
    _max_user_threads - max number of users to be processed in threads in one time.
    """

    _base_link = "https://github.com/"
    _wiki_link = "wiki/"
    _issues_link = "issues/"
    _repo_param = {"tab": "repositories"}
    _username_valid_ascii = tuple(range(97, 123)) + tuple(range(48, 58)) + (45,)
    _max_chr_num = 39
    _max_user_threads = 3

    def __init__(self, keywords: List[str], proxies: List[str], content_type: str):
        """Init method

        :param keywords: search keywords.
        :param proxies: list of proxies.
        :param content_type: Wikis, Issues ot Repositories.
        :return: githubCrawler object.
        """
        self.keywords = "|".join([".*" + keyword.lower() + r".*" for keyword in keywords])
        self.proxies = ["http://" + prox for prox in proxies]
        self.type = content_type.lower()
        self._results = []

    def crawl(self, needed: int = None) -> str:
        """Starting search method.

        :param needed: number of results you need.
        :return: JSON string with search results.
        """
        if self.type not in ["wikis", "issues", "repositories"]:
            return "Incorrect type"
        process = Thread(target=self._run_main_thread, args=(needed,))
        process.start()
        process.join()
        return json.dumps(self._results)

    def _run_main_thread(self, needed: int = None) -> None:
        """A method that monitors the number of threads and checks if the conditions are met:
        either there are already enough results, or all possible github users have already
        been processed.

        :param needed: number of results you need.
        :return: None.
        """
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
        """The method checks if there are repositories in the list that match the keywords.
        If so - adds a link to them in the results.

        :param username: github username.
        :return: None.
        """
        if self._are_keywords_matched(self._get_repos(username)):
            self._add_result(self._base_link + username)

    def _check_wiki(self, username: str) -> None:
        """Starts the process of checking all user wikis for keywords.

        :param username: github username.
        :return: None.
        """
        threads = []
        for repo in self._get_repos(username):
            self._start_thread(self._check_wiki_in_repo, (username, repo), threads)
        for el in threads:
            el.join()

    def _check_issues(self, username: str) -> None:
        """Starts the process of checking all user issues for keywords.

        :param username: github username.
        :return: None.
        """
        threads = []
        for repo in self._get_repos(username):
            self._start_thread(self._check_issues_in_repo, (username, repo), threads)
        for el in threads:
            el.join()

    def _search_by_user_num(self, user_num):
        """Starts a section search based on the "type".

        :param user_num: unique user number, which will be translated into a
            set of characters valid for github names.
        :return None.
        """
        try:
            username = self._num_to_user(user_num)
            print(username)
            if self.type == "repositories":
                self._check_repos(username)
            elif self.type == "wikis":
                self._check_wiki(username)
            elif self.type == "issues":
                self._check_issues(username)
        except requests.exceptions.ConnectTimeout as e:
            print("Problem with proxy", e)
        except TypeError as e:
            print("'user_num' must be positive int.")

    def _get_repos(self, username: str) -> List:
        """Returns user repositories.

        :param username: github username.
        :return: Returns a list of repositories by username.
        """
        repositories = []
        parsed = self._parsed_request(self._base_link + username, self._repo_param)
        if parsed is not None:
            repositories = [repo.get_text()[1:].replace(" ", "") for repo in
                            parsed.find_all("a", itemprop="name codeRepository")]
            parsed(repositories)
        return repositories

    def _get_wiki_list_in_repo(self, username: str, repo: str) -> List:
        """Returns repository wikis name.

        :param username: github username.
        :param repo: repository name.
        :return: returns a list of wiki by repository.
        """
        wikis = []
        parsed = self._parsed_request(self._base_link + username + "/" + repo + "/" + self._wiki_link)
        if parsed is not None:
            wikis = [wiki.get_text() for wiki in parsed.find_all("a", class_="flex-1 py-1 text-bold")]
        return wikis

    def _check_wiki_in_repo(self, username: str, repo: str):
        """Checks the list of wikis for keywords.

        :param: username: github username.
        :param repo: repository name.
        :return: None.
        """
        threads = []
        for wiki in self._get_wiki_list_in_repo(username, repo):
            self._start_thread(self._check_wiki_in_repo_by_name, (username, repo, wiki), threads)
        for el in threads:
            el.join()

    def _check_wiki_in_repo_by_name(self, username: str, repo: str, wiki: str):
        """Checks a wiki page for keywords.
        If yes - adds a link to the page in the results

        :param: username: github username.
        :param repo: repository name.
        :param wiki: wiki name.
        :return: None.
        """
        link = self._base_link + username + "/" + repo + "/" + self._wiki_link + wiki
        parsed = self._parsed_request(link)
        if parsed is not None:
            content = [wiki] + [el.get_text() for el in parsed.find("div", class_="markdown-body").find_all(
                ["a", "p", "span", "h1", "h2", "h3", "h4", "h5", "h6"])]
            if self._are_keywords_matched(content):
                self._add_result(link)

    def _get_issues_list_in_repo(self, username: str, repo: str) -> List:
        """Returns repository issues name.

        :param: username: github username.
        :param repo: repository name.
        :return: returns a list of issues by repository.
        """
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
        """Checks the list of issues for keywords.

        :param: username: github username.
        :param repo: repository name.
        :return: None.
        """
        thread = []
        for issue in self._get_issues_list_in_repo(username, repo):
            self._start_thread(self._check_issues_in_repo_by_name, (issue,), thread)
        for el in thread:
            el.join()

    def _check_issues_in_repo_by_name(self, issue_link: str):
        """Checks a issue page for keywords.
        If yes - adds a link to the page in the results.

        :param issue_link: issue link.
        :return: None.
        """
        link = self._base_link + issue_link
        parsed = self._parsed_request(link)
        if parsed is not None:
            title = parsed.find("span", class_="js-issue-title markdown-title")
            content = [title.get_text() if title is not None else title] + \
                      [el.find("p").get_text() for el in parsed.find_all("td", class_="comment-body") if
                       el.find("p") is not None]
            content = [el for el in content if el is not None]
            if self._are_keywords_matched(content):
                self._add_result(link)

    @classmethod
    def _num_to_user(cls, num: int) -> str:
        """
        :param num: user unique number
        :return: string corresponding to the number.
        """
        valid_ascii_len = len(cls._username_valid_ascii)
        if num < valid_ascii_len:
            return chr(cls._username_valid_ascii[num])
        else:
            return cls._num_to_user(num // valid_ascii_len) + \
                   chr(cls._username_valid_ascii[num % valid_ascii_len])

    def _parsed_request(self, link: str, params: dict = None):
        """
        :param link: link to web page.
        :param params: request parameters.
        :return: parsed response.
        """
        if params is None:
            params = {}
        resp = requests.get(link, proxies={"http": choice(self.proxies)}, params=params)
        if resp.status_code == 200:
            return BeautifulSoup(resp.content, "html.parser")
        return None

    def _add_result(self, el: str) -> None:
        """Adding a page to results.
        :param el: link to be added.
        :return: None.
        """
        self._results.append({"url": el})

    def _are_keywords_matched(self, txt_list: List[str]) -> bool:
        """Checking strings for key strings.
        :param txt_list: list of lines to check.
        :return: True - if the keywords are found, otherwise False.
        """
        for txt in txt_list:
            if re.match(self.keywords, txt.lower()) is not None:
                return True
        return False

    @staticmethod
    def _start_thread(func, args, temp):
        """Starting a stream, with its automatic addition to the buffer."""
        cur = Thread(target=func, args=args, daemon=True)
        cur.start()
        temp.append(cur)
