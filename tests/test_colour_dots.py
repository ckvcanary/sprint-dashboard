"""One pattern for colour dots across the whole app.
A coloured dot appears only where it means something that the data also shows:
  .rfcard .dot   beside the refresh time: green fresh, amber old, blue refreshing
  .chip i        Pull status chip (Pulled, Failed, Missed, Upcoming, Not scheduled)
  .capl2 i       legend of the capacity bar (Used, Left)
  .legend i      Map legend, the colours of the Epic, User story and Task cards
  .td            only inside the refresh info box, the same three dots as beside the time
Everything else that looks like a marker is a plain grey bullet (.bl) or has no marker."""
import pytest

pytestmark = pytest.mark.guard
ALLOWED = [".rfcard .dot", ".chip i", ".capl2 i", ".legend i", ".ttn .bl", "#gtip .ttg .td", "#gtip .tt .td"]

SCAN = """(allowed) => [...document.querySelectorAll('body *')].filter(e => {
  const r = e.getBoundingClientRect(), c = getComputedStyle(e); if (r.width === 0 || r.width > 13 || Math.abs(r.width - r.height) > 1.5) return false;
  const round = parseFloat(c.borderTopLeftRadius) >= r.width / 2 - 0.5 || c.borderTopLeftRadius.includes('%'); if (!round) return false;
  const filled = c.backgroundColor !== 'rgba(0, 0, 0, 0)'; const ring = parseFloat(c.borderTopWidth) >= 1.5 && c.borderTopStyle !== 'none';
  if (!(filled || ring)) return false; if (e.closest('#gate, .gbg, .gprev, .ibtn, .tabs, .nav, #tabs, svg, button')) return false;
  return !allowed.some(s => e.matches(s));
}).map(e => e.outerHTML.slice(0, 120))"""

TABS = ["map", "cap", "bd", "leave", "log", "who", "how"]


@pytest.mark.parametrize("tab", TABS)
def test_every_coloured_dot_on_each_page_is_in_the_pattern(page, tab):
    page.click(f'[data-tab="{tab}"]'); page.wait_for_timeout(500)
    odd = page.evaluate(SCAN, ALLOWED); assert not odd, (tab, odd)


def test_burndown_person_view_and_open_info_boxes_follow_the_pattern(page):
    page.click('[data-tab="bd"]'); page.click('[data-bdview="person"]'); page.wait_for_timeout(500)
    assert not page.evaluate(SCAN, ALLOWED)
    for sel in (".rfcard .ibtn", "#tlog th .ibtn", "#tplan th .ibtn"):
        b = page.locator(sel).first
        if b.count(): b.hover(); page.wait_for_timeout(250); assert not page.evaluate(SCAN, ALLOWED), sel; page.mouse.move(2, 2)


def test_the_dots_that_exist_mean_the_same_colour_everywhere(page):
    c = page.evaluate("""() => { const q = (cls, host) => { const e = document.createElement('i'); e.className = cls; (document.querySelector(host) || document.body).appendChild(e); const v = getComputedStyle(e).backgroundColor; e.remove(); return v; };
      return { fresh: q('dot', '.rfcard'), old: q('dot old', '.rfcard'), busy: q('dot busy', '.rfcard'), tdOk: q('td ok'), tdWarn: q('td warn'), tdBlue: q('td blue'),
        used: getComputedStyle(document.documentElement).getPropertyValue('--green'), left: getComputedStyle(document.documentElement).getPropertyValue('--blue') }; }""")
    assert c["fresh"] == c["tdOk"] and c["old"] == c["tdWarn"] and c["busy"] == c["tdBlue"], c
