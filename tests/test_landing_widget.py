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
