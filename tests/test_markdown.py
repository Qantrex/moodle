"""Moodle HTML -> Markdown for task texts."""
import unittest

from fakemoodle import SITE, cleanup, load


class Markdown(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.m = load()

    @classmethod
    def tearDownClass(cls):
        cleanup(cls.m)

    def md(self, h):
        return self.m.text_of(h)

    def test_basics(self):
        self.assertEqual(self.md(""), "")
        self.assertEqual(self.md(None), "")
        self.assertEqual(self.md("<p>a&nbsp;b</p><p>c<br>d</p>"), "a b\n\nc\nd")
        self.assertEqual(self.md("<h3>Ziel</h3><p>x</p>"), "**Ziel**\n\nx")
        self.assertEqual(self.md("<p><strong>fett</strong> und <em>schräg</em></p>"), "**fett** und *schräg*")
        self.assertEqual(self.md("<p>a<script>alert(1)</script><style>p{}</style>b</p>"), "ab")
        self.assertEqual(self.md("<hr><p>x</p>"), "---\n\nx")

    def test_lists(self):
        self.assertEqual(self.md("<ol><li>eins</li><li>zwei<ul><li>a</li></ul></li></ol>"), "1. eins\n2. zwei\n  - a")
        self.assertEqual(self.md("<ul><li><p>one</p></li><li><p>two</p></li></ul>"), "- one\n- two")

    def test_list_items_without_closing_tags(self):
        self.assertEqual(self.md("<ul><li>one<li>two</ul><p>after</p>"), "- one\n- two\n\nafter")
        self.assertEqual(self.md("<ul><li><p>one</p><li><p>two</p></ul>"), "- one\n- two")

    def test_code(self):
        self.assertEqual(self.md("<p>run <code>ls -l</code></p>"), "run `ls -l`")
        self.assertEqual(self.md("<pre>a  b\n<c></pre>"), "```\na  b\n<c>\n```")

    def test_links(self):
        self.assertEqual(self.md('<a href="https://x.invalid/a">site</a>'), "[site](https://x.invalid/a)")
        self.assertEqual(self.md('<a href="https://x.invalid/a">https://x.invalid/a</a>'), "https://x.invalid/a")
        self.assertEqual(self.md('<a href="#top">up</a> <a href="javascript:x()">js</a>'), "up js")
        self.assertEqual(self.md('<p>Use <b>bold <a href="https://x.invalid/">l</a></b></p>'),
                         "Use **bold [l](https://x.invalid/)**")

    def test_file_links_lose_webservice_and_token(self):
        u = SITE + "/webservice/pluginfile.php/1/mod_assign/intro/f.pdf"
        self.assertEqual(self.md('<a href="%s">f</a>' % u), "[f](%s/pluginfile.php/1/mod_assign/intro/f.pdf)" % SITE)
        self.assertEqual(self.m.browser_url(u + "?token=abc123&forcedownload=1"),
                         SITE + "/pluginfile.php/1/mod_assign/intro/f.pdf?forcedownload=1")
        self.assertEqual(self.m.browser_url(u + "?forcedownload=1&wstoken=abc123"),
                         SITE + "/pluginfile.php/1/mod_assign/intro/f.pdf?forcedownload=1")
        self.assertEqual(self.m.browser_url(u + "?token=abc123"), SITE + "/pluginfile.php/1/mod_assign/intro/f.pdf")

    def test_images(self):
        self.assertEqual(self.md('<img src="https://x.invalid/a.png" alt="UML">'), "![UML](https://x.invalid/a.png)")
        self.assertEqual(self.md('<p><img src="data:image/png;base64,%s" alt="Screenshot"></p>' % ("A" * 5000)),
                         "*(image: Screenshot)*")

    def test_placeholders_survive(self):
        self.assertEqual(self.md("<p>Abgabe: &lt;Name&gt;_Aufgabe.zip</p>"), "Abgabe: \\<Name>_Aufgabe.zip")
        self.assertEqual(self.md("<p>Datei <Nachname>.pdf</p>"), "Datei \\<Nachname>.pdf")

    def test_tables(self):
        self.assertEqual(self.md("<table><tr><th>A</th><th>B</th></tr><tr><td>1|2</td><td><p>x</p></td></tr></table>"),
                         "| A | B |\n|---|---|\n| 1\\|2 | x |")

    def test_table_cells_without_closing_tags(self):
        self.assertEqual(self.md("<table><tr><td>a<td>b</tr><tr><td>c<td>d</table>"), "| a | b |\n|---|---|\n| c | d |")
        self.assertEqual(self.md("<table><tr><td>a<tr><td>b</table>"), "| a |\n|---|\n| b |")

    def test_unclosed_table_keeps_its_text(self):
        self.assertEqual(self.md("<p>Punkte:</p><table><tr><td>A<td>10"), "Punkte:\n\n| A | 10 |\n|---|---|")

    def test_nested_table_is_flattened(self):
        out = self.md("<table><tr><td>outer<table><tr><td>in1</td><td>in2</td></tr></table></td><td>z</td></tr>"
                      "<tr><td>2</td><td>3</td></tr></table>")
        self.assertEqual(out, "| outer in1 in2 | z |\n|---|---|\n| 2 | 3 |")


if __name__ == "__main__":
    unittest.main()
