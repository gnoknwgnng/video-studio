"""Craft helpers for the script writer.

  EXAMPLES      a bank of example scenes in many visual types; each video is shown a few, so the visuals vary
  ai_phrases()  phrases that make a script sound machine-written (blocked by an automatic check)
"""
import re

# example scenes in many visual types (format and quality only, never the content)
EXAMPLES = [
    '{"type":"number","kicker":"Every second","value":11000,"suffix":"+","label":"UPI payments","label_em":"in India","cue":"eleven","lines":[{"say":"Every single second, more than eleven thousand UPI payments go through in India.","sub":"Every single second, more than 11,000 UPI payments go through in India.","seed":42}]}',
    '{"type":"chat","kicker":"Sound familiar?","name":"Boss","messages":[{"from":"them","text":"Report ready?","cue":"report"},{"from":"me","text":"Almost... 5 more mins","cue":"almost"},{"from":"them","text":"You said that at 3","cue":"three"}],"lines":[{"say":"Report ready? Almost, five more minutes. You said that at three.","seed":42}]}',
    '{"type":"map","kicker":"Where it started","title":"One small lab","places":[{"country":"Switzerland","label":"CERN, 1989","cue":"switzerland"}],"lines":[{"say":"It started in one small lab in Switzerland, in nineteen eighty-nine.","sub":"It started in one small lab in Switzerland, in 1989.","seed":42}]}',
    '{"type":"gauge","kicker":"Your sleep score","title":"After 4 pm coffee","value":38,"suffix":"/100","zones":["Poor","Okay","Great"],"label":"deep sleep","label_em":"cut by a third","cue":"third","lines":[{"say":"One cup after four PM can cut your deep sleep by about a third.","seed":43}]}',
    '{"type":"reveal","kicker":"Same street","title":"Ten years apart","before":{"label":"2014","image_query":"crowded cash market stall","cue":"cash"},"after":{"label":"2024","image_query":"phone scanning qr code at shop","cue":"phone"},"caption":"No cash. Just scan.","lines":[{"say":"Ten years ago, it was all cash. Today, everyone just scans with a phone.","seed":44}]}',
    '{"type":"pictogram","kicker":"Right now","total":10,"highlight":7,"icon":"user","display":"7 in 10","label":"skip breakfast","label_em":"on workdays","cue":"seven","lines":[{"say":"Seven in ten people skip breakfast on a workday. Maybe you did today.","seed":45}]}',
    '{"type":"bubbles","kicker":"Size check","title":"Daily users","unit":"M","items":[{"label":"App A","value":500,"display":"500M","icon":"smartphone","cue":"five"},{"label":"App B","value":90,"display":"90M","icon":"tablet","cue":"ninety"}],"note":"Not even close","lines":[{"say":"App A has five hundred million daily users. App B? Just ninety million.","seed":46}]}',
    '{"type":"cycle","kicker":"The loop","title":"Why you stay hooked","center":"Habit","nodes":[{"label":"Trigger","icon":"bell","cue":"buzz"},{"label":"Scroll","icon":"smartphone","cue":"scroll"},{"label":"Reward","icon":"gift","cue":"reward"},{"label":"Repeat","icon":"repeat","cue":"again"}],"lines":[{"say":"Your phone buzzes, you scroll, you get a tiny reward, and you do it all over again.","seed":47}]}',
    '{"type":"funnel","kicker":"The real odds","title":"From apply to hired","stages":[{"label":"Applied","value":1000,"display":"1,000","icon":"file-text","cue":"thousand"},{"label":"Interview","value":60,"display":"60","icon":"users","cue":"sixty"},{"label":"Hired","value":3,"display":"3","icon":"badge-check","cue":"three"}],"lines":[{"say":"A thousand people apply. Sixty get an interview. Three get the job.","seed":48}]}',
    '{"type":"spotlight","kicker":"Here\'s the catch","icon":"lock","mood":"bad","satellites":[{"icon":"key","label":"Passwords","cue":"passwords"},{"icon":"mail","label":"Emails","cue":"emails"},{"icon":"credit-card","label":"Cards","cue":"cards"}],"climax_cue":"one","lines":[{"say":"Here\'s the catch. Your passwords, your emails, your cards. All behind one weak lock.","seed":49}]}',
    '{"type":"versus","kicker":"Round one","title":"Speed","left":{"label":"Train","image_query":"high speed train","points":["3 hours","City centre"],"cue":"train"},"right":{"label":"Plane","image_query":"airplane takeoff","points":["1 hour flying","+2 hours airport"],"cue":"plane"},"lines":[{"say":"The train takes three hours. The plane flies in one, but the airport eats two more.","seed":50}]}',
    '{"type":"kpis","kicker":"In one year","title":"The scale","items":[{"value":131,"suffix":"B","label":"payments","icon":"zap","cue":"billion"},{"value":350,"suffix":"M","label":"users","icon":"users","cue":"million"}],"lines":[{"say":"A hundred and thirty-one billion payments, from three hundred and fifty million people.","sub":"131 billion payments, from 350 million people.","seed":51}]}',
    '{"type":"gallery","kicker":"Where you see it","title":"Everywhere","tiles":[{"label":"Tea stall","icon":"coffee","image_query":"indian tea stall","cue":"tea"},{"label":"Auto","icon":"car","image_query":"auto rickshaw street","cue":"auto"},{"label":"Mall","icon":"shopping-bag","image_query":"shopping mall counter","cue":"mall"}],"lines":[{"say":"The tea stall, the auto, the mall. It\'s everywhere now.","seed":52}]}',
    '{"type":"flow","kicker":"Behind the scenes","title":"Two seconds","nodes":[{"label":"You scan","icon":"scan-line","cue":"scan"},{"label":"Your bank","icon":"landmark","cue":"bank"},{"label":"NPCI","icon":"network","cue":"switch"},{"label":"Their bank","icon":"building-2","cue":"theirs"}],"lines":[{"say":"You scan, your bank checks, the national switch routes it, and their bank says yes. Two seconds.","seed":53}]}',
    '{"type":"end","tagline":"Seven in ten.","tagline_em":"Not anymore.","logo_cue":"breakfast","tagline_cue":"seven","lines":[{"say":"Seven in ten skip it. Now you know why you shouldn\'t. That\'s breakfast.","seed":60}]}',
]

AI_PHRASES = [
    "in today's fast-paced world", "in today's world", "in today's digital age", "fast-paced world", "game-changer", "game changer",
    "delve", "dive into", "let's dive", "deep dive", "unlock the", "unleash", "revolutionize", "revolutionise", "seamless", "seamlessly",
    "cutting-edge", "cutting edge", "harness the power", "the power of", "elevate your", "embark", "journey of", "tapestry",
    "navigate the", "landscape of", "realm of", "it's important to note", "it is important to note", "in conclusion", "in summary",
    "furthermore", "moreover", "ever-evolving", "ever evolving", "plays a crucial role", "crucial role", "paradigm", "synergy",
    "leverage", "robust", "a testament to", "stay tuned", "without further ado", "welcome back", "hey guys", "in this video",
    "buckle up", "look no further", "whether you're", "transformative", "unparalleled", "state-of-the-art", "next level",
]


def ai_phrases(cfg):
    """AI-sounding phrases found in the spoken text (lower-case)."""
    text = " ".join(ln.get("say", "") for s in cfg.get("scenes", []) if isinstance(s, dict) for ln in s.get("lines", []) if isinstance(ln, dict)).lower()
    text = text.replace("’", "'")
    return sorted({p for p in AI_PHRASES if re.search(r"(?<![a-z])" + re.escape(p) + r"(?![a-z])", text)})
