import streamlit as st

welcome_page = st.Page(
    page = "pages/welcome.py",
    title = "Welcome to Bird Tagging",
    default = True
)


file_upload_page = st.Page(
    page = "pages/file_upload.py",
    title = "File Upload"
)


api_interface_page = st.Page(
    page="pages/api_interface.py",
    title="API Interface"
)

pg = st.navigation(
    {
        "Welcome" : [welcome_page],
        "File Upload" : [file_upload_page],
        "API": [api_interface_page]
    }
)


pg.run()
