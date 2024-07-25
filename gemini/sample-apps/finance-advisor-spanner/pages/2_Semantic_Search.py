import time

from css import *
from database import *
from itables.streamlit import interactive_table
import streamlit as st
from streamlit_extras.stylable_container import stylable_container

st.set_page_config(
    layout="wide",
    page_title="FinVest Advisor",
    page_icon=favicon,
    initial_sidebar_state="expanded",
)
st.logo("images/investments.png")


def asset_semantic_search():
    """This function implements Semantic Search feature"""

    st.header("FinVest Fund Advisor")
    st.subheader("Semantic Search")

    classes_col, buttons_col, style_col, render_with_col = st.columns(
        [0.25, 0.25, 0.20, 0.10]
    )
    classes = ["display", "compact", "cell-border", "stripe"]
    buttons = ["pageLength", "csvHtml5", "excelHtml5", "colvis"]
    style = "table-layout:auto;width:auto;margin:auto;caption-side:bottom"
    it_args = dict(
        classes=classes,
        style=style,
    )

    if buttons:
        it_args["buttons"] = buttons

    # st.subheader('Funds Matching your Search')
    query_params = []
    query_params.append(investment_strategy.strip())
    query_params.append(investment_manager.strip())
    with st.spinner("Querying Spanner..."):
        # start_time = time.time()
        # data_load_state = st.text("Loading data...")
        if annVsKNN == "KNN":
            return_vals = semantic_query(query_params)
        else:
            return_vals = semantic_query_ann(query_params)
        spanner_query = return_vals.get("query")
        data = return_vals.get("data")
        # time_spent = time.time() - start_time
        with st.expander("Spanner Query"):
            with stylable_container(
                "codeblock",
                """
            code {
                white-space: pre-wrap !important;
            }
            """,
            ):
                st.code(spanner_query, language="sql", line_numbers=False)
        # formatted_time = f"{time_spent:.3f}"  # f-string for formatted output
        # st.text(f"The Query took {formatted_time} seconds to complete.")
        # data_load_state.text("Loading data...done!")
    interactive_table(data, caption="", **it_args)


with st.sidebar:
    with st.form("Asset Semantic Search"):
        st.subheader("Search Criteria")
        annVsKNN = st.radio("", ["ANN", "KNN"], horizontal=True)
        investment_strategy = st.text_area(
            "Search for me",
            value="Invest in companies which also subscribe to my ideas around climate change, doing good for the planet",
        )
        investment_manager = st.text_input("Investment Manager", value="Maarten")
        asset_semantic_search_submitted = st.form_submit_button("Submit")
if asset_semantic_search_submitted:
    asset_semantic_search()

st.markdown(footer, unsafe_allow_html=True)
