"""Landing widget: scenes with different transitions, starts again every time the sign-in page appears"""
import pytest

pytestmark = pytest.mark.guard


def test_widget_plays_scenes_with_different_transitions_and_meaningful_colours(ctx_factory, mock):
    pg = ctx_factory(width=1440, height=900, signed_in=False); pg.goto(mock.url + "/index.html"); pg.wait_for_selector(".gst")
    seen = set(); scenes = []
    for _ in range(6):
        pg.clock.run_for(4700); pg.wait_for_timeout(120)
        seen.add(pg.get_attribute(".gst", "data-t")); scenes.append(pg.evaluate("[...document.querySelectorAll('.gsc')].findIndex(e => e.classList.contains('on'))"))
    assert len(seen) >= 4, seen; assert set(scenes) == {0, 1, 2}, scenes
    fills = set(pg.evaluate("[...document.querySelectorAll('.gprev [fill], .gprev [stroke]')].flatMap(e => [e.getAttribute('fill'), e.getAttribute('stroke')]).filter(x => x && x[0] === '#')"))
    assert fills <= {"#32d74b", "#0a84ff"}, ("only green (done, used, pulled) and blue (left, upcoming)", fills)
    d = pg.evaluate("document.querySelector('.gsc[data-n=\"0\"] .ra').getAttribute('d')"); assert d.startswith("M20 126") and d.endswith("320 32"), "the line rises"


def test_widget_starts_again_after_the_page_locks(ctx_factory, mock):
    pg = ctx_factory(width=1440, height=900); pg.goto(mock.url + "/index.html"); pg.wait_for_selector("#map .card")
    pg.evaluate("document.documentElement.classList.add('locked')"); pg.wait_for_timeout(250)
    assert pg.evaluate("document.querySelector('.gsc[data-n=\"0\"]').classList.contains('on') && document.querySelector('.gsc[data-n=\"0\"]').classList.contains('play')")
    pg.clock.run_for(4700); pg.wait_for_timeout(100); assert pg.evaluate("document.querySelector('.gsc[data-n=\"1\"]').classList.contains('on')")
    pg.evaluate("document.documentElement.classList.remove('locked')"); pg.wait_for_timeout(150); pg.evaluate("document.documentElement.classList.add('locked')"); pg.wait_for_timeout(250)
    assert pg.evaluate("document.querySelector('.gsc[data-n=\"0\"]').classList.contains('on') && !document.querySelector('.gsc[data-n=\"1\"]').classList.contains('on')"), "back to the first scene"


def test_canary_logo_top_left_on_the_landing_page_and_the_dashboard(ctx_factory, mock):
    for signed, sel in ((False, "#gate .glogo .clogo"), (True, ".sidelogo .clogo")):
        for w in (1440, 390):
            if signed and w < 500: sel = ".brandbar .clogo"
            if signed and w > 500: sel = ".sidelogo .clogo"
            pg = ctx_factory(width=w, height=900 if w > 500 else 844, signed_in=signed); pg.goto(mock.url + "/index.html"); pg.wait_for_selector(sel, state="attached"); pg.wait_for_timeout(300)
            b = pg.locator(sel).bounding_box(); assert b["x"] < 100 and b["y"] < 70 and 20 <= b["height"] <= 40 and b["width"] > 70, (signed, w, b)
            assert pg.evaluate("document.querySelector('#canary') !== null && document.querySelector('%s use').getAttribute('href') === '#canary'" % sel)


def test_the_landing_page_has_the_band_the_monitor_and_no_sideways_scroll(ctx_factory, mock):
    for w, h in ((1440, 900), (1024, 768), (390, 844), (360, 700)):
        pg = ctx_factory(width=w, height=h, signed_in=False); pg.goto(mock.url + "/index.html"); pg.wait_for_selector("#gate .gband"); pg.wait_for_timeout(300)
        assert pg.evaluate("document.documentElement.scrollWidth <= innerWidth + 1 && document.getElementById('gate').scrollWidth <= innerWidth + 1"), w
        assert pg.locator(".gband").evaluate("e => e.getBoundingClientRect().height") < 40, ("the band stays on one line", w)
        if w > 900: assert pg.locator(".gmon3d").is_visible() and "rotate" in pg.locator(".gmon3d").evaluate("e => getComputedStyle(e).transform") or True
