import unittest

from webquiz.parse import parse_questions

HTML = """
<div class="TiMu newTiMu" data="111">
  <div class="Zy_TItle"><i>1</i>
    <div><span class="newZy_TItle">【Single Choice】</span><p>中国的首都是（ ）。</p>（3.3score）</div>
  </div>
  <ul class="Zy_ulTop">
    <li><span class="num_option" data="A">A</span><a><p>上海</p></a></li>
    <li><span class="num_option" data="C">B</span><a><p>北京</p></a></li>
  </ul>
</div>
<div class="TiMu newTiMu" data="222">
  <div class="Zy_TItle"><i>2</i>
    <div><span class="newZy_TItle">【True or False】</span>地球是圆的。（3.4score）</div>
  </div>
</div>
"""


class ParseTest(unittest.TestCase):
    def test_single_and_tf(self):
        qs = parse_questions(HTML, {})
        self.assertEqual(len(qs), 2)
        self.assertEqual(qs[0]["no"], 1)
        self.assertEqual(qs[0]["type"], "Single Choice")
        self.assertEqual(qs[0]["stem"], "中国的首都是（ ）。")
        self.assertEqual(qs[0]["options"], {"A": "上海", "B": "北京"})
        self.assertEqual(qs[1]["type"], "True or False")
        self.assertEqual(qs[1]["options"], {"A": "True", "B": "False"})

    def test_multi_option_dx(self):
        html = HTML.replace("num_option", "num_option_dx")
        qs = parse_questions(html, {})
        self.assertEqual(qs[0]["options"]["B"], "北京")


if __name__ == "__main__":
    unittest.main()
