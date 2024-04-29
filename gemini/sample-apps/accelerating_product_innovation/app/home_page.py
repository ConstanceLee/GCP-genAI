"""
Entry page of the streamlit application.
"""

import app.pages_utils.utils as utils
from app.pages_utils.utils_config import PAGES_CFG
from st_pages import show_pages_from_config
import streamlit as st

# Initialize session state if not already initialized
if "initialize_session_state" not in st.session_state:
    st.session_state.initialize_session_state = False

# Initialize session state if not already initialized
if st.session_state.initialize_session_state is False:
    utils.initialize_all_session_state()
    st.session_state.initialize_session_state = True

# get the page configuration for the home page
page_cfg = PAGES_CFG["home"]
utils.page_setup(page_cfg)


show_pages_from_config()


st.image(page_cfg["home_img_1"])
st.divider()
st.image(page_cfg["home_img_2"])
