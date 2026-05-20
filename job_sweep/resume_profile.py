"""
Gokul's structured resume profile used for job match scoring.
Update this file when the resume changes — the scorer reads from here.
"""

RESUME_TEXT = """
CANDIDATE: V Gokul
HEADLINE: People Leader | Operations Architect | Stakeholder Governance | AI-Native Transformation
LOCATION: Bengaluru, India
EXPERIENCE: 8 years (all at McKinsey & Company, Bengaluru)

PROFESSIONAL SUMMARY:
People and operations leader with 8 years at McKinsey & Company, scaling teams and operating systems
that scaling organisations rely on. Led 17 direct reports through full talent lifecycle with zero
unplanned attrition across 3 high-attrition cycles. Architected an India-based GCC-equivalent
overnight service line from zero to 75 FTEs across 3 time zones in 14 months, with the operating
model adopted as enterprise SOP. Owns the senior operations leadership interface across 200+
quarterly deliverables and drove 94% leadership-overhead reduction through LLM-native workflows.
Targeting Director or Head of Operations and Strategy mandates at GCCs and high-growth organisations
where the brief is to build the operating system from the ground up.

CORE IMPACT METRICS:
- Zero unplanned attrition across 3 consecutive high-attrition cycles (17 direct reports)
- Built GCC-equivalent service line: 0 → 75 FTEs across US + India time zones in 14 months
- 97.5% defect reduction in first operating cycle
- 94% leadership overhead cut via LLM-assisted automation (5 hrs/week → 30 min/month)
- 10% profitability improvement across McKinsey India (55-person unit)
- 85% manual effort reduction validated pre-deployment on LLM workflows
- 95% completion rate across 360+ professionals in L&D programmes

ROLES HELD:
1. Operations Team Lead, McKinsey & Company (Feb 2021 – Present)
2. Project Coach, McKinsey & Company (Jan 2020 – Feb 2021)
3. Visual Analyst, McKinsey & Company (Apr 2018 – Dec 2019)

KEY COMPETENCIES:
People Leadership (17 Directs) | Talent Management & Succession Planning | Stakeholder Management
Operating Model Design | OKR Governance & QBR Architecture | GCC Operations | Change Management
AI-Native Operations & LLM Automation | Service Excellence | L&D Programme Design
People Analytics & Performance Management | Cross-Timezone Leadership | P&L-Adjacent Operations
Decision Support | Executive Reporting | Coaching & High-Performance Culture

TARGET ROLES: Director of Operations | Head of Operations | Head of GCC Operations |
              Director – People & Operations | VP Operations | Head of Strategy & Operations |
              Director Delivery Operations

EDUCATION: B.Sc. Mathematics

CERTIFICATIONS:
- Lean Six Sigma Black Belt (Expected May 2026)
- Foundations of Business Strategy (UVA Darden)
- ICP-ATF Agile Team Facilitation (ICAgile, 2024)
- PAL I Professional Agile Leadership (Scrum.org, 2024)
- Agile Training Facilitator (McKinsey Certified)
- Duarte Data Storytelling Certified

TECHNICAL: Power BI | Advanced Excel | LLM-Assisted Coding | HTML Prototyping |
           MIS Dashboard Architecture | Expert PowerPoint | Advanced Word

PEDIGREE NOTE: 8 continuous years at McKinsey & Company — strong signal of rigour,
stakeholder management, and operating in high-ambiguity, high-stakes environments.
"""

# Search queries tuned to Gokul's target roles in BLR
TARGET_QUERIES = [
    "Director of Operations",
    "Head of Operations",
    "Head of GCC Operations",
    "Director People Operations",
    "VP Operations",
    "Head Strategy Operations",
    "Director Delivery Operations",
    "Head of Capability Centre",
    "Senior Manager Operations GCC",
    "Director Employee Experience Operations",
]

# Hard thresholds for verdict classification
SURE_SHOT_THRESHOLD = 75
STRONG_MATCH_THRESHOLD = 60
