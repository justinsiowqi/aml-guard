"""
AML Guard — Streamlit chat UI.

TODO: implement once AMLAgent.run() is working end-to-end.
      Mirror of loanguard-ai/app.py but simplified for single-agent output.

UI structure:
  Sidebar  — connection status, tools list
  Main     — chat input → AMLRiskResponse display
               ├─ Risk verdict banner (HIGH_RISK / MEDIUM_RISK / LOW_RISK / CLEARED)
               ├─ Risk score gauge
               ├─ Findings panel (severity-sorted)
               ├─ Triggered typologies panel
               └─ Evidence panel (cited sections + chunks)
"""

import streamlit as st

st.set_page_config(page_title="AML Guard", page_icon="🔍", layout="wide")
st.title("AML Guard — Financial Crime Investigation")
st.info("UI not yet implemented. Build AMLAgent.run() first, then wire it up here.")

# TODO: implement
# 1. @st.cache_resource — Neo4jConnection + make_execute_tool(conn)
# 2. Chat input → AMLAgent(execute_tool).run(question)
# 3. Display AMLRiskResponse fields
