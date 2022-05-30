import unittest
from unittest.mock import patch, Mock

from crawler import GithubCrawler


class TestGithubCrawler(unittest.TestCase):
    def setUp(self):
        self.gc = GithubCrawler(["css", "html"], ["44.233.12.234:1080", "164.155.151.1:80"], "wikis")

    @staticmethod
    def _mock_response(status=200, content="CONTENT"):
        mock_resp = Mock()
        mock_resp.status_code = status
        mock_resp.content = content
        return mock_resp

    def test_start_thread(self):
        temp = []
        for i in range(3):
            self.gc._start_thread(str, (i,), temp)
        self.assertEqual(len(temp), 3)
        self.assertFalse(temp[0].is_alive())

    def test_are_keywords_matched(self):
        self.assertTrue(self.gc._are_keywords_matched(["html", "css", "code"]))
        self.assertFalse(self.gc._are_keywords_matched(["python"]))

    def test_add_result(self):
        self.gc._add_result("github.com")
        self.assertEqual(self.gc._results, [{"url": "github.com"}])

    @patch("requests.get")
    def test_parsed_request(self, mock_get):
        mock_get.return_value = self._mock_response(content="<h1>Test</h1>")
        res = self.gc._parsed_request("https://github.com/mykyta-ishchenko/").find("h1").get_text()
        self.assertEqual(res, "Test")

    def test_num_to_user(self):
        self.assertEqual(self.gc._num_to_user(1), "b")
        self.assertEqual(self.gc._num_to_user(100), "c0")

    @patch("requests.get")
    def test_check_issues_in_repo(self, mock_get):
        mock_get.return_value = self._mock_response(content="<span class='js-issue-title markdown-title'>Css"
                                                            "</span><p class='comment-body'>html</p>")
        self.gc._check_issues_in_repo_by_name("1")
        self.assertTrue({"url": "https://github.com/1"} in self.gc._results)

    @patch("requests.get")
    def test_get_issues_list_in_repo(self, mock_get):
        mock_get.return_value = self._mock_response(content="<a class='d-block d-md-none position-absolute "
                                                            "top-0 bottom-0 left-0 right-0' href='test/issues/1'></a>")
        self.assertEqual(self.gc._get_issues_list_in_repo("", ""), ['test/issues/1'])

    @patch("requests.get")
    def test_check_wiki_in_repo_by_name(self, mock_get):
        mock_get.return_value = self._mock_response(content="<div class='markdown-body'><p>html</p></div>")
        self.gc._check_wiki_in_repo_by_name('1', '2', '3')
        self.assertEqual(self.gc._results, [{"url": "https://github.com/1/2/wiki/3"}])

    @patch("requests.get")
    def test_get_wiki_list_in_repo(self, mock_get):
        mock_get.return_value = self._mock_response(content="<a class='flex-1 py-1 text-bold'>1</a>"
                                                            "<a class='flex-1 py-1 text-bold'>2</a>")
        self.assertEqual(self.gc._get_wiki_list_in_repo("", ""), ["1", "2"])
        mock_get.return_value = self._mock_response()
        self.assertEqual(self.gc._get_wiki_list_in_repo("", ""), [])

    @patch("requests.get")
    def test_get_repos(self, mock_get):
        mock_get.return_value = self._mock_response(content="<a itemprop='name codeRepository'>\n 1</a>")
        self.assertEqual(self.gc._get_repos(""), ["1"])

    @patch("crawler.GithubCrawler._get_repos")
    def test_check_repos(self, mock_obj):
        mock_obj.return_value = ["html", "code"]
        self.gc._check_repos("1")
        self.assertEqual(self.gc._results, [{"url": "https://github.com/1"}])

    @patch("threading.Thread.start")
    @patch("threading.Thread.join")
    def test_crawl(self, mock_f1, mock_f2):
        mock_f1.side_effect = lambda: self.gc._add_result("1")
        self.gc.crawl(1)
        self.assertEqual(self.gc._results, [{"url": "1"}])

    @patch("threading.Thread.start")
    def test_run_main_thread(self, mock_f1):
        mock_f1.side_effect = lambda: self.gc._add_result("1")
        self.gc._run_main_thread(1)
        self.assertTrue(len(self.gc._results) >= 0)

    @patch("crawler.GithubCrawler._start_thread")
    def test_check_wikis(self, mock_f1):
        mock_f1.shadow_effect = lambda: self.gc._add_result("1")
        self.gc._check_wiki("")
        self.assertTrue(len(self.gc._results) >= 0)

    @patch("crawler.GithubCrawler._start_thread")
    def test_check_issues(self, mock_f1):
        mock_f1.shadow_issues = lambda: self.gc._add_result("1")
        self.gc._check_issues("")
        self.assertTrue(len(self.gc._results) >= 0)

    def test_search_by_user_num(self):
        self.gc.type = "other"
        self.assertIsNone(self.gc._search_by_user_num(0))
        self.assertRaises(TypeError, self.gc._search_by_user_num(""))


if __name__ == "__main__":
    unittest.main()
