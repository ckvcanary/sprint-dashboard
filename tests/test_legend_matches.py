"""Every legend dot must look like the chip, tag or dot it explains"""
import pytest

pytestmark = pytest.mark.guard

PROBE = """() => {
  const host = document.createElement('div'); host.id = 'probe'; host.style.cssText = 'position:fixed;left:0;top:0;opacity:0;pointer-events:none';
  document.body.appendChild(host); const out = {};
  const dot = e => { const c = getComputedStyle(e); return { fill: c.backgroundColor, ring: c.borderTopWidth !== '0px' && c.borderTopStyle !== 'none' ? c.borderTopColor : 'none' }; };
  for (const k of ['ok', 'bad', 'warn', 'up', 'nil']) {
    host.insertAdjacentHTML('beforeend', `<i class="td ${k}" id="t_${k}"></i><span class="chip ${k === 'nil' ? 'na' : k}" id="c_${k}"><i></i>x</span><span class="tag ${k}" id="g_${k}">x</span>`);
    const t = document.getElementById('t_' + k), c = document.getElementById('c_' + k), g = document.getElementById('g_' + k);
    out[k] = { legend: dot(t), chipDot: dot(c.querySelector('i')), chipText: getComputedStyle(c).color, tagText: getComputedStyle(g).color };
  }
  host.remove(); return out;
}"""


def test_chip_dot_has_the_same_look_as_its_legend_dot(page):
    r = page.evaluate(PROBE)
    for k in ("ok", "bad", "warn", "up", "nil"):
        a, b = r[k]["legend"], r[k]["chipDot"]
        assert (a["fill"], a["ring"]) == (b["fill"], b["ring"]) or (k in ("ok", "bad", "warn") and a["fill"] == r[k]["chipText"]), (k, a, b)


def test_upcoming_is_blue_ring_everywhere(page):
    r = page.evaluate(PROBE)
    assert r["up"]["legend"]["fill"] == "rgba(0, 0, 0, 0)" and r["up"]["legend"]["ring"] != "none"
    assert r["up"]["chipDot"]["ring"] == r["up"]["legend"]["ring"] and r["up"]["chipText"] == r["up"]["legend"]["ring"]


def test_ok_warn_bad_text_matches_legend_colour(page):
    r = page.evaluate(PROBE)
    for k in ("ok", "warn", "bad"):
        assert r[k]["tagText"] == r[k]["chipText"] == r[k]["legend"]["fill"], (k, r[k])
