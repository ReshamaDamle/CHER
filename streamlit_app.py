from openai import OpenAI
import time
import streamlit as st


def main():
    st.set_page_config(
        page_title="OpenAI Assistant with Image Upload",
        page_icon="🖼️",
    )

    api_key = st.secrets["OPENAI_API_KEY"]
    assistant_id = st.secrets["ASSISTANT_ID"]
    st.session_state.client = OpenAI(api_key=api_key)

    if "messages" not in st.session_state:
        st.session_state.messages = []

    st.title("Chat with Your Assistant (Image Support)")

    # Upload image file
    uploaded_file = st.file_uploader("Upload an image", type=["jpg", "png", "jpeg"])

    if uploaded_file is not None:
        with open(f"/tmp/{uploaded_file.name}", "wb") as f:
            f.write(uploaded_file.read())

        # Upload to OpenAI
        with st.spinner("Uploading image..."):
            openai_file = st.session_state.client.files.create(
                file=open(f"/tmp/{uploaded_file.name}", "rb"),
                purpose="assistants"
            )
            st.success("Image uploaded to OpenAI!")

    if prompt := st.chat_input("Ask something (optionally based on the image)"):
        st.session_state.messages.append({"role": "user", "content": prompt})
        with st.chat_message("user"):
            st.markdown(prompt)

        # Create thread and add message (with file if uploaded)
        if "thread" not in st.session_state:
            st.session_state.thread = st.session_state.client.beta.threads.create()

        if uploaded_file is not None:
            message = st.session_state.client.beta.threads.messages.create(
                thread_id=st.session_state.thread.id,
                role="user",
                content=prompt,
                file_ids=[openai_file.id]
            )
        else:
            message = st.session_state.client.beta.threads.messages.create(
                thread_id=st.session_state.thread.id,
                role="user",
                content=prompt
            )

        run = st.session_state.client.beta.threads.runs.create(
            thread_id=st.session_state.thread.id,
            assistant_id=assistant_id,
        )

        # Poll for completion
        def wait_for_complete(run, thread):
            while run.status in ["queued", "in_progress"]:
                run = st.session_state.client.beta.threads.runs.retrieve(
                    thread_id=thread.id, run_id=run.id
                )
                time.sleep(1)
            return run

        run = wait_for_complete(run, st.session_state.thread)

        replies = st.session_state.client.beta.threads.messages.list(
            thread_id=st.session_state.thread.id
        )

        # Display the assistant's response
        for reply in reversed(replies.data):
            if reply.role == "assistant":
                content = reply.content[0].text.value
                st.session_state.messages.append({"role": "assistant", "content": content})
                with st.chat_message("assistant"):
                    st.markdown(content)

                    # If assistant included files, render download links
                    for file_obj in reply.content:
                        if hasattr(file_obj, "image_file"):
                            file_id = file_obj.image_file.file_id
                            file_info = st.session_state.client.files.retrieve(file_id)
                            download_url = f"https://api.openai.com/v1/files/{file_id}/content"
                            st.markdown(
                                f"📎 [Download {file_info.filename}]({download_url})"
                            )


if __name__ == "__main__":
    main()
