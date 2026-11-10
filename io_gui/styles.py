"""
styles.py

All PASSAY CSS lives here. inject_css() is called once at app start
from io_gui.py. Pure styling - no data, no logic.
"""

import streamlit as st

def inject_css():
    st.markdown(
        """
        <style>
        @import url('https://fonts.googleapis.com/css2?family=Quicksand:wght@500;600;700&family=Baloo+2:wght@500;600;700;800&display=swap');

        html, body, [class*="css"] {
            font-family: 'Quicksand', sans-serif;
            font-weight: 600;
        }
        .stApp p,
        .stApp label,
        .stApp input,
        .stApp textarea,
        .stApp button,
        .stApp li,
        .stApp [data-testid="stMarkdownContainer"] {
            font-family: 'Quicksand', sans-serif;
        }
        [data-testid="stIconMaterial"],
        .material-symbols-rounded,
        .material-symbols-outlined {
            font-family: "Material Symbols Rounded" !important;
            font-weight: normal !important;
            font-style: normal !important;
            letter-spacing: normal !important;
            text-transform: none !important;
            white-space: nowrap !important;
            word-wrap: normal !important;
            direction: ltr !important;
            -webkit-font-feature-settings: "liga" !important;
            font-feature-settings: "liga" !important;
            -webkit-font-smoothing: antialiased !important;
        }
        h1,h2,h3,h4 { font-family: 'Baloo 2', cursive !important; letter-spacing: 0 !important; }

        @keyframes fadeUp { from { opacity: 0; transform: translateY(20px); } to { opacity: 1; transform: translateY(0); } }
        @keyframes fadeIn { from { opacity: 0; } to { opacity: 1; } }
        @keyframes springIn {
            0% { opacity: 0; transform: translateY(24px) scale(0.94); }
            60% { opacity: 1; transform: translateY(-4px) scale(1.01); }
            100% { opacity: 1; transform: translateY(0) scale(1); }
        }
        @keyframes slideInLeft { from { opacity: 0; transform: translateX(-18px); } to { opacity: 1; transform: translateX(0); } }
        @keyframes floaty { 0% { transform: translate(0,0) scale(1); } 50% { transform: translate(40px,-30px) scale(1.12); } 100% { transform: translate(0,0) scale(1); } }
        @keyframes floaty2 { 0% { transform: translate(0,0) scale(1); } 50% { transform: translate(-34px,30px) scale(1.1); } 100% { transform: translate(0,0) scale(1); } }
        @keyframes bob { 0%,100% { transform: translateY(0); } 50% { transform: translateY(-6px); } }

        :root {
            --app-bg-1: #2a1958;
            --app-bg-2: #10344a;
            --app-bg-3a: #0a0e1e;
            --app-bg-3b: #0e1226;
            --blob-1: rgba(167,139,250,0.5);
            --blob-2: rgba(94,234,212,0.4);
            --text-main: #cdd6ee;
            --text-strong: #f4f6ff;
            --text-muted: #a6b0d0;
            --surface: rgba(255,255,255,0.05);
            --surface-2: rgba(255,255,255,0.06);
            --border: rgba(255,255,255,0.12);
            --border-soft: rgba(255,255,255,0.09);
            --border-strong: rgba(255,255,255,0.14);
            --shadow: rgba(0,0,0,0.4);
            --shadow-soft: rgba(0,0,0,0.36);
            --input-bg: rgba(255,255,255,0.05);
            --input-border: rgba(255,255,255,0.14);
            --sidebar-bg: linear-gradient(180deg, #120a2e 0%, #131a38 60%, #16224a 130%);
            --sidebar-border: rgba(255,255,255,0.06);
            --accent: #a78bfa;
            --accent-2: #5eead4;
            --accent-ring: rgba(167,139,250,0.22);
            --accent-glow: rgba(167,139,250,0.3);
            --hero-grad: linear-gradient(115deg,#2a1958 0%,#6d28d9 50%,#0e7490 120%);
            --hero-shadow: rgba(109,40,217,0.42);
            --on-hero: #ffffff;
            --on-hero-soft: rgba(255,255,255,0.9);
            --metric-bg: rgba(255,255,255,0.05);
        }

        .stApp {
            background:
              radial-gradient(1000px 600px at 8% -5%, var(--app-bg-1) 0%, transparent 55%),
              radial-gradient(900px 600px at 100% 0%, var(--app-bg-2) 0%, transparent 55%),
              linear-gradient(180deg, var(--app-bg-3a) 0%, var(--app-bg-3b) 100%);
            overflow-x: hidden;
        }
        .stApp:before, .stApp:after {
            content: ""; position: fixed; border-radius: 50%; filter: blur(90px); z-index: 0; pointer-events: none;
        }
        .stApp:before {
            width: 560px; height: 560px;
            background: radial-gradient(circle at 30% 30%, var(--blob-1), transparent 70%);
            top: -140px; left: -100px; animation: floaty 18s ease-in-out infinite;
        }
        .stApp:after {
            width: 500px; height: 500px;
            background: radial-gradient(circle at 60% 40%, var(--blob-2), transparent 70%);
            bottom: -160px; right: -80px; animation: floaty2 22s ease-in-out infinite;
        }
        section.main .block-container { position: relative; z-index: 1; }

        section.main .block-container > div { animation: springIn 0.55s cubic-bezier(0.34,1.56,0.64,1) both; }
        section.main .block-container > div:nth-child(1) { animation-delay: 0.02s; }
        section.main .block-container > div:nth-child(2) { animation-delay: 0.10s; }
        section.main .block-container > div:nth-child(3) { animation-delay: 0.18s; }
        section.main .block-container > div:nth-child(4) { animation-delay: 0.26s; }
        section.main .block-container > div:nth-child(5) { animation-delay: 0.34s; }
        section.main .block-container > div:nth-child(6) { animation-delay: 0.42s; }
        section.main .block-container > div:nth-child(7) { animation-delay: 0.50s; }
        section.main .block-container > div:nth-child(n+8) { animation-delay: 0.58s; }

        div[data-testid="stMetric"] { animation: springIn 0.6s cubic-bezier(0.34,1.56,0.64,1) both; }
        section[data-testid="stSidebar"] .stButton { animation: slideInLeft 0.4s ease both; }

        #MainMenu, footer { visibility: hidden; }

        [data-testid="stStatusWidget"],
        [data-testid="stDecoration"] { display: none !important; }

        [data-testid="stToolbar"] { display: flex !important; visibility: visible !important; }

        [data-testid="stExpandSidebarButton"] {
            display: flex !important; visibility: visible !important;
            opacity: 1 !important; pointer-events: auto !important;
        }

        .block-container { padding-top: 2rem; max-width: 1150px; }

        .stApp, .stApp p, .stApp span, .stApp label, .stApp li,
        .main .block-container { color: var(--text-main) !important; }
        .stApp h1, .stApp h2, .stApp h3, .stApp h4 { color: var(--text-strong) !important; font-weight: 700 !important; }

        .stTextInput input, .stNumberInput input, .stDateInput input,
        div[data-baseweb="input"] input, textarea, div[data-baseweb="select"] > div {
            background-color: var(--input-bg) !important;
            color: var(--text-strong) !important;
            border: 1.5px solid var(--input-border) !important;
            border-radius: 16px !important;
            transition: border-color 0.25s ease, box-shadow 0.25s ease !important;
        }
        .stTextInput input:focus, div[data-baseweb="input"]:focus-within {
            border-color: var(--accent) !important;
            box-shadow: 0 0 0 4px var(--accent-ring) !important;
        }
        .stTextInput label, .stSelectbox label, .stNumberInput label {
            color: var(--text-muted) !important; font-weight: 700 !important; font-size: 0.82rem !important;
        }

        div[data-testid="stVerticalBlockBorderWrapper"] {
            background: var(--surface) !important;
            backdrop-filter: blur(16px);
            -webkit-backdrop-filter: blur(16px);
            border: 1.5px solid var(--border) !important;
            border-radius: 26px !important;
            box-shadow: 0 16px 50px var(--shadow) !important;
            transition: transform 0.3s cubic-bezier(0.34,1.56,0.64,1), box-shadow 0.3s ease, border-color 0.3s ease;
        }
        div[data-testid="stVerticalBlockBorderWrapper"]:hover {
            transform: translateY(-6px);
            border-color: rgba(167,139,250,0.5) !important;
            box-shadow: 0 28px 62px rgba(167,139,250,0.24) !important;
        }

        section[data-testid="stSidebar"] {
            background: var(--sidebar-bg);
            border-right: 1px solid var(--sidebar-border);
        }
        section[data-testid="stSidebar"] * { color: var(--text-main) !important; }
        section[data-testid="stSidebar"] .stButton > button {
            background: var(--surface);
            border: 1.5px solid var(--border-soft);
            color: var(--text-strong) !important;
            border-radius: 16px;
            text-align: left;
            font-weight: 700;
            padding: 0.65rem 0.95rem;
            transition: all 0.25s cubic-bezier(0.34,1.56,0.64,1);
        }
        section[data-testid="stSidebar"] .stButton > button:hover {
            background: rgba(167,139,250,0.2);
            border-color: rgba(167,139,250,0.55);
            transform: translateX(6px) scale(1.02);
            box-shadow: 0 0 20px var(--accent-glow);
        }

        .stButton > button {
            border-radius: 16px;
            border: 1.5px solid var(--border-strong);
            padding: 0.6rem 1.15rem;
            font-weight: 700;
            background: var(--surface-2);
            color: var(--text-strong) !important;
            transition: all 0.25s cubic-bezier(0.34,1.56,0.64,1);
        }
        .stButton > button:hover {
            border-color: var(--accent);
            color: var(--text-strong) !important;
            transform: translateY(-2px) scale(1.02);
            box-shadow: 0 12px 28px rgba(167,139,250,0.34);
        }
        button[kind="primary"] {
            background: linear-gradient(100deg,#a78bfa,#8b5cf6 45%,#5eead4) !important;
            border: none !important;
            color: #17123a !important;
            box-shadow: 0 12px 30px rgba(167,139,250,0.5) !important;
            background-size: 200% 100% !important;
            transition: background-position 0.5s ease, transform 0.25s ease, box-shadow 0.25s ease !important;
            font-weight: 800 !important;
        }
        button[kind="primary"]:hover {
            transform: translateY(-2px) scale(1.02);
            background-position: 100% 0 !important;
            box-shadow: 0 18px 42px rgba(167,139,250,0.65) !important;
        }

        div[data-testid="stMetric"] {
            background: var(--metric-bg);
            border: 1.5px solid var(--border);
            border-radius: 24px;
            padding: 18px 20px;
            box-shadow: 0 14px 40px var(--shadow-soft);
            transition: transform 0.3s cubic-bezier(0.34,1.56,0.64,1), box-shadow 0.3s ease, border-color 0.3s ease;
        }
        div[data-testid="stMetric"]:hover {
            transform: translateY(-6px) scale(1.02);
            border-color: rgba(167,139,250,0.5);
            box-shadow: 0 24px 54px rgba(167,139,250,0.26);
        }
        div[data-testid="stMetricValue"] { color: var(--text-strong) !important; font-weight: 800; font-family: 'Baloo 2'; }
        div[data-testid="stMetricLabel"] { color: var(--text-muted) !important; font-weight: 700; }

        hr { margin: 1rem 0; border: none; border-top: 1px solid var(--border-soft); }
        div[data-testid="stDataFrame"] { border-radius: 18px; overflow: hidden; box-shadow: 0 8px 26px var(--shadow-soft); }

        .vt-hero { animation: springIn 0.6s cubic-bezier(0.34,1.56,0.64,1) both; }
        .vt-badge { animation: fadeIn 0.7s ease both; }
        .vt-bob { display:inline-block; animation: bob 3s ease-in-out infinite; }
        [data-testid="stHeader"] {
            display: block !important;
            visibility: visible !important;
            background: transparent !important;
        }

        [data-testid="stSidebarCollapseButton"],
        [data-testid="collapsedControl"] {
            display: flex !important;
            visibility: visible !important;
            opacity: 1 !important;
            pointer-events: auto !important;
        }

        @media (prefers-color-scheme: light) {
            :root {
                --app-bg-1: #ede9fe;
                --app-bg-2: #cffafe;
                --app-bg-3a: #f7f8ff;
                --app-bg-3b: #eef1fb;
                --blob-1: rgba(167,139,250,0.35);
                --blob-2: rgba(45,212,191,0.28);
                --text-main: #3b3f58;
                --text-strong: #1e2140;
                --text-muted: #6b7290;
                --surface: rgba(255,255,255,0.75);
                --surface-2: rgba(255,255,255,0.85);
                --border: rgba(30,33,64,0.10);
                --border-soft: rgba(30,33,64,0.08);
                --border-strong: rgba(30,33,64,0.12);
                --shadow: rgba(79,70,139,0.14);
                --shadow-soft: rgba(79,70,139,0.12);
                --input-bg: rgba(255,255,255,0.9);
                --input-border: rgba(30,33,64,0.14);
                --sidebar-bg: linear-gradient(180deg, #f3eefe 0%, #eaf0fb 60%, #e4f3f6 130%);
                --sidebar-border: rgba(30,33,64,0.08);
                --accent: #7c3aed;
                --accent-2: #0d9488;
                --accent-ring: rgba(124,58,237,0.18);
                --accent-glow: rgba(124,58,237,0.22);
                --hero-grad: linear-gradient(115deg,#8b5cf6 0%,#7c3aed 50%,#0e7490 120%);
                --hero-shadow: rgba(124,58,237,0.28);
                --on-hero: #ffffff;
                --on-hero-soft: rgba(255,255,255,0.92);
                --metric-bg: rgba(255,255,255,0.8);
            }
            div[data-testid="stVerticalBlockBorderWrapper"]:hover {
                border-color: rgba(124,58,237,0.5) !important;
                box-shadow: 0 28px 62px rgba(124,58,237,0.18) !important;
            }
            section[data-testid="stSidebar"] .stButton > button:hover {
                background: rgba(124,58,237,0.12);
                border-color: rgba(124,58,237,0.4);
            }
            .stButton > button:hover {
                box-shadow: 0 12px 28px rgba(124,58,237,0.22);
            }
            div[data-testid="stMetric"]:hover {
                border-color: rgba(124,58,237,0.45);
                box-shadow: 0 24px 54px rgba(124,58,237,0.18);
            }
            button[kind="primary"] { color: #1e1240 !important; }
        }
        </style>
        """,
        unsafe_allow_html=True,
    )
