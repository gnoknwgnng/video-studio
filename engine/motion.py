"""Shared motion effects for the scenes (the energy of the original Video Studio, applied everywhere).

  draw(sel, t)            icons/line art inside `sel` draw themselves stroke by stroke (like a pen)
  burst(c, x, y, t)       a ring + particles flying out from (x, y): for a number landing, a winner, a reveal
  shake(sel, t)           a short impact shake
The camera punch-in on key moments is added automatically by make_video.py for every picture-first scene.
"""
import math

_n = [0]


def draw(sel, t, dur=0.6, stagger=0.0):
    """JS: every stroke inside the matched SVG icons draws itself from t."""
    return f'      drawIn(tl, "{sel}", {t:.3f}, {dur:.2f}, {stagger:.3f});\n'


def shake(sel, t, amp=10, n=5):
    return f'      tl.fromTo("{sel}", {{ x: {-amp} }}, {{ x: 0, duration: {0.06 * n:.2f}, ease: "elastic.out(1.2, 0.25)" }}, {t:.3f});\n'


def burst(c, x, y, t, color="var(--accent)", n=12, radius=170, size=18):
    """(html, js) for a particle burst centred at (x, y) in scene pixels, starting at time t."""
    _n[0] += 1
    bid = f"bs{c.i}_{_n[0]}"
    html = f'<div class="burst-fx" id="{bid}" style="left:{x:.0f}px;top:{y:.0f}px"><i class="ring" style="border-color:{color}"></i>'
    js = f'      tl.fromTo("#{bid} .ring", {{ scale: 0.2, opacity: 0.9 }}, {{ scale: 2.6, opacity: 0, duration: 0.7, ease: "power2.out" }}, {t:.3f});\n'
    for k in range(n):
        a = 2 * math.pi * k / n + (0.3 if k % 2 else 0)
        r = radius * (0.75 if k % 2 else 1.0)
        col = color if k % 3 else "var(--highlight)"
        html += f'<b style="width:{size}px;height:{size}px;margin:{-size // 2}px 0 0 {-size // 2}px;background:{col}"></b>'
        js += (f'      tl.fromTo("#{bid} b:nth-of-type({k + 1})", {{ x: 0, y: 0, scale: 1, opacity: 1 }}, '
               f'{{ x: {r * math.cos(a):.0f}, y: {r * math.sin(a):.0f}, scale: 0.2, opacity: 0, duration: 0.75, ease: "power3.out" }}, {t:.3f});\n')
    html += "</div>"
    c.sfx("shimmer", t, 0.35)
    return html, js


CSS = """
.cam { position: absolute; inset: 0; transform-origin: 50% 22%; }
.pace { position: absolute; inset: 0; transform-origin: 50% 40%; }
.burst-fx { position: absolute; width: 0; height: 0; z-index: 20; pointer-events: none; }
.burst-fx .ring { position: absolute; left: -90px; top: -90px; width: 180px; height: 180px; border-radius: 50%; border: 10px solid; opacity: 0; }
.burst-fx b { position: absolute; left: 0; top: 0; border-radius: 50%; opacity: 0; }
"""

JS = """
      // icons and line art draw themselves stroke by stroke
      function drawIn(tl, sel, at, dur, stagger) {
        let k = 0;
        document.querySelectorAll(sel).forEach((svg) => {
          const off = (stagger || 0) * k++;
          svg.querySelectorAll("path, circle, rect, line, polyline, polygon, ellipse").forEach((p) => {
            let L = 0; try { L = p.getTotalLength(); } catch (e) {}
            if (!L) return;
            tl.fromTo(p, { strokeDasharray: L + 1, strokeDashoffset: L + 1 }, { strokeDashoffset: 0, duration: dur, ease: "power2.inOut" }, at + off);
          });
        });
      }
"""
