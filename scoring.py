import re
from difflib import SequenceMatcher

from sklearn.feature_extraction.text import ENGLISH_STOP_WORDS, TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity

# Extend this list for your target market.
SKILL_SET = sorted(set("""python,java,javascript,typescript,c++,c#,php,ruby,go,rust,sql,mysql,postgresql,mongodb,nosql,
html,css,react,angular,vue,node.js,django,flask,fastapi,spring,laravel,.net,git,github,docker,kubernetes,aws,azure,gcp,
linux,rest api,graphql,machine learning,deep learning,nlp,data analysis,data science,pandas,numpy,tensorflow,pytorch,
scikit-learn,power bi,tableau,excel,statistics,spss,agile,scrum,jira,ci/cd,devops,testing,unit testing,selenium,
cybersecurity,networking,cisco,project management,communication,leadership,teamwork,problem solving,customer service,
sales,marketing,seo,social media,content writing,accounting,bookkeeping,quickbooks,sage,payroll,auditing,budgeting,
financial reporting,research,teaching,training,microsoft office,word,powerpoint,human resources,recruitment,
procurement,logistics,supply chain""".replace("\n", "").split(",")), key=lambda x: (-len(x), x))

DEGREES = [("phd", 4, r"\b(ph\.?d|doctorate)\b"), ("masters", 3, r"\b(master'?s?|msc|mba|m\.sc)\b"),
           ("bachelors", 2, r"\b(bachelor'?s?|bsc|b\.sc|honours|degree|beng|b\.eng)\b"),
           ("diploma", 1, r"\b(diploma|national certificate|hnd)\b")]
SECTIONS = {"experience": r"\b(experience|employment|work history)\b", "education": r"\beducation\b",
            "skills": r"\bskills?\b", "summary": r"\b(summary|profile|objective)\b"}
EXTRA_STOP = {"work", "working", "role", "team", "ability", "strong", "experience", "years", "required",
              "responsibilities", "requirements", "looking", "candidate", "company", "job", "position",
              "including", "etc", "must", "will", "skills", "knowledge", "good", "excellent", "plus"}


def norm(t: str) -> str:
    return re.sub(r"\s+", " ", t.lower())


def has_term(term: str, text: str) -> bool:
    return re.search(r"(?<![\w+#.])" + re.escape(term) + r"(?![\w+#])", text) is not None


def fuzzy_has(term: str, cv_words: set) -> bool:
    return any(len(w) > 4 and SequenceMatcher(None, term, w).ratio() >= 0.88 for w in cv_words)


def job_keywords(job: str, limit: int = 25):
    j = norm(job)
    found = [s for s in SKILL_SET if has_term(s, j)]
    # add top frequent terms not already covered
    words = [w for w in re.findall(r"[a-z][a-z+#.\-]{2,}", j)
             if w not in ENGLISH_STOP_WORDS and w not in EXTRA_STOP]
    freq = {}
    for w in words:
        freq[w] = freq.get(w, 0) + 1
    covered = " ".join(found)
    extras = [w for w, c in sorted(freq.items(), key=lambda x: -x[1])
              if c >= 2 and w not in covered][: max(0, limit - len(found))]
    return found, extras


def years_required(job: str):
    m = [int(x) for x in re.findall(r"(\d{1,2})\+?\s*(?:-\s*\d+\s*)?years?", norm(job))]
    return max(m) if m else None


def years_in_cv(cv: str) -> float:
    c = norm(cv)
    explicit = [int(x) for x in re.findall(r"(\d{1,2})\+?\s*years?", c)]
    spans, total = re.findall(r"((?:19|20)\d{2})\s*(?:-|–|to)\s*((?:19|20)\d{2}|present|current|now)", c), 0
    for a, b in spans:
        end = 2026 if b in ("present", "current", "now") else int(b)
        total += max(0, end - int(a))
    return float(max(max(explicit, default=0), min(total, 40)))


def degree_level(t: str) -> int:
    t = norm(t)
    return max([lvl for _, lvl, rx in DEGREES if re.search(rx, t)], default=0)


def analyze(cv: str, job: str) -> dict:
    cvn, jobn = norm(cv), norm(job)
    cv_words = set(re.findall(r"[a-z][a-z+#.\-]{2,}", cvn))

    skills, extras = job_keywords(job)
    kws = skills + extras
    matched, missing = [], []
    for k in kws:
        (matched if has_term(k, cvn) or (" " not in k and fuzzy_has(k, cv_words)) else missing).append(k)
    kw_cov = len(matched) / len(kws) if kws else 0.0
    try:
        vec = TfidfVectorizer(stop_words="english", ngram_range=(1, 2)).fit_transform([cvn, jobn])
        sim = float(cosine_similarity(vec[0], vec[1])[0][0])
    except ValueError:
        sim = 0.0
    keyword_score = min(1.0, 0.75 * kw_cov + 0.25 * min(1.0, sim * 2.5))

    need, have = years_required(job), years_in_cv(cv)
    exp_score = 1.0 if not need else min(1.0, have / need)

    jd, cd = degree_level(job), degree_level(cv)
    edu_score = 1.0 if jd == 0 else (1.0 if cd >= jd else (0.6 if cd == jd - 1 and cd > 0 else 0.2 if cd else 0.0))

    fmt, tips = 0, []
    checks = [
        (re.search(r"[\w.+-]+@[\w-]+\.[\w.]+", cv), "Add a professional email address."),
        (re.search(r"(\+?\d[\d\s\-()]{8,})", cv), "Add a phone number."),
        (re.search(SECTIONS["experience"], cvn), "Add a clear 'Experience' heading."),
        (re.search(SECTIONS["education"], cvn), "Add a clear 'Education' heading."),
        (re.search(SECTIONS["skills"], cvn), "Add a 'Skills' section."),
        (re.search(r"(19|20)\d{2}", cv), "Add dates (years) to roles and education."),
        (400 <= len(cv.split()) <= 1500 or len(cv.split()) > 150, "Aim for roughly 1-2 pages of content."),
    ]
    for ok, tip in checks:
        if ok:
            fmt += 1
        else:
            tips.append(tip)
    fmt_score = fmt / len(checks)

    parts = {"keywords": round(keyword_score * 50), "experience": round(exp_score * 25),
             "education": round(edu_score * 15), "format": round(fmt_score * 10)}
    total = sum(parts.values())

    advice = []
    if missing:
        advice.append("Add these job keywords where they truthfully apply: " + ", ".join(missing[:10]) + ".")
    if need and have < need:
        advice.append(f"Job asks for about {need} years; your CV shows about {int(have)}. Make dates and durations explicit.")
    if jd > cd:
        advice.append("The job lists a higher qualification than your CV shows. State your qualification clearly.")
    advice += tips

    return {"score": total, "breakdown": parts, "matched": matched, "missing": missing,
            "advice": advice, "similarity": round(sim, 2),
            "note": "ATS match estimate. Real ATS systems differ, so treat this as guidance, not a guarantee."}
