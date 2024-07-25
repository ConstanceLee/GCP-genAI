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


def compliance_search():
    """This function implements Compliance Check Graph feature"""
    st.header("FinVest Fund Advisor")
    st.subheader("Exposure Check")

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
    query_params.append(sectorOption)
    query_params.append(exposurePercentage)
    with st.spinner("Querying Spanner..."):
        # start_time = time.time()
        # data_load_state = st.text("Loading data...")
        return_vals = compliance_query(query_params)
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
    with st.form("Compliance Search"):
        st.subheader("Search Criteria")
        sectorOption = st.selectbox(
            "Which sector would you want to focus on?",
            ("Technology", "Pharma", "Semiconductors"),
            index=None,
            placeholder="Select sector ...",
        )
        exposurePercentage = st.select_slider(
            "How much exposure to this sector would you prefer",
            options=["10%", "20%", "30%", "40%", "50%", "60%", "70%"],
        )
        exposurePercentage = exposurePercentage[:2]
        compliance_search_submitted = st.form_submit_button("Submit")
if compliance_search_submitted:
    compliance_search()

st.markdown(footer, unsafe_allow_html=True)
