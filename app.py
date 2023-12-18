import os
from dotenv import load_dotenv
import openai
import requests
import json

import time
import logging
from datetime import datetime
import streamlit as st


#### ==== Video source: https://youtu.be/SaJxbuKehpc?si=CsPzyU4OXehzMZhn ###
### Code source: https://github.com/donwany/openai-tutorials/blob/main/gpt_weather_assistant-yt.py ###

load_dotenv()
# openai.api_key = os.environ.get("OPENAI_API_KEY")
news_api_key = os.environ.get("NEWS_API_KEY")

client = openai.OpenAI()

model = "gpt-3.5-turbo-16k"


def get_news(topic):
    url = (
        f"https://newsapi.org/v2/everything?q={topic}&apiKey={news_api_key}&pageSize=5"
    )
    try:
        response = requests.get(url)

        if response.status_code == 200:
            # news = response.json()
            news = json.dumps(response.json(), indent=4)
            # Convert JSON string to a Python dictionary
            news_json = json.loads(news)

            data = news_json

            # Accessing individual fields
            status = data["status"]
            total_results = data["totalResults"]
            articles = data["articles"]

            final_news = []

            # Loop through articles
            for article in articles:
                source_name = article["source"]["name"]
                author = article["author"]
                title = article["title"]
                description = article["description"]
                url = article["url"]
                published_at = article["publishedAt"]
                content = article["content"]
                title_description = f"""Title: {title}, Author: {author}, Source: {source_name}, 
                 description: {description}  URL: {url}"""

                final_news.append(title_description)

                # You can now process these fields as needed
                # print(
                #     f"""Title: {title}, \nAuthor: {author}, \n Source: {source_name},
                # \n description: {description} \n URL: {url}"""
                # )
                # print("\n")

            return final_news
        else:
            return []

    except requests.exceptions.RequestException as e:
        print("Error occured during API Rquest:", e)


# tesla_news = get_news(topic="bitcoin")

# print(f"{tesla_news}, length {len(tesla_news)} ")


class AssistantManager:
    # Static variables to store the thread and assistant IDs
    thread_id = "thread_oeRkA9IC6zbBVEmHZQNCEAzU"
    assistant_id = "asst_PsObkvAZre9LWLO2GHUQnaCl"
    # thread_id = None
    # assistant_id = None

    def __init__(self, model: str = "gpt-3.5-turbo-16k"):
        self.client = openai.OpenAI()
        self.model = model
        self.assistant = None
        self.thread = None
        self.run = None

        # Add later for streamlit
        self.summary = (
            None  # Add an instance variable to store the summary for streamlit
        )

        # Retrieve existing assistant and thread if IDs are already set
        if AssistantManager.assistant_id:
            self.assistant = self.client.beta.assistants.retrieve(
                AssistantManager.assistant_id
            )
        if AssistantManager.thread_id:
            self.thread = self.client.beta.threads.retrieve(AssistantManager.thread_id)

    def create_assistant(self, name, instructions, tools):
        if not self.assistant:
            assistant_obj = self.client.beta.assistants.create(
                name=name, instructions=instructions, tools=tools, model=self.model
            )
            AssistantManager.assistant_id = assistant_obj.id
            self.assistant = assistant_obj
            print(f"AssisID: {self.assistant.id}")

    def create_thread(self):
        if not self.thread:
            thread_obj = self.client.beta.threads.create()
            AssistantManager.thread_id = thread_obj.id
            self.thread = thread_obj
            print(f"ThreadID: {self.thread.id}")

    def add_message_to_thread(self, role, content):
        if self.thread:
            self.client.beta.threads.messages.create(
                thread_id=self.thread.id,
                role=role,
                content=content,
            )

    def run_assistant(self, instructions):
        if self.thread and self.assistant:
            self.run = self.client.beta.threads.runs.create(
                thread_id=self.thread.id,
                assistant_id=self.assistant.id,
                instructions=instructions,
            )

    def process_messages(self):
        if self.thread:
            messages = self.client.beta.threads.messages.list(thread_id=self.thread.id)
            summary = []
            # just get the last message of the thread
            last_message = messages.data[0]
            role = last_message.role
            response = last_message.content[0].text.value
            print(f"SUMMARY: {role.capitalize()}: ==> {response}")
            summary.append(response)
            self.summary = "\n".join(summary)

            # loop through all messages in this thread
            # for msg in messages.data:
            #     role = msg.role
            #     content = msg.content[0].text.value
            #     print(f"SUMMARY:: {role.capitalize()}: {content}")

    def wait_for_completion(self):
        if self.thread and self.run:
            while True:
                time.sleep(5)
                run_status = self.client.beta.threads.runs.retrieve(
                    thread_id=self.thread.id,
                    run_id=self.run.id,
                )

                print(f"RUN STATUS: {run_status.model_dump_json(indent=4)}")

                if run_status.status == "completed":
                    self.process_messages()
                    break
                elif run_status.status == "requires_action":
                    print("Function calling now....")
                    self.call_required_functions(
                        run_status.required_action.submit_tool_outputs.model_dump()
                    )
                else:
                    print("Waiting for the Assistant to process...")

    # for streamlit
    def get_summary(self):
        return self.summary

    # Run the steps
    def run_steps(self):
        run_steps = self.client.beta.threads.runs.steps.list(
            thread_id=self.thread.id, run_id=self.run.id
        )
        print(f"Run-Steps: {run_steps}")
        return run_steps.data

    def call_required_functions(self, required_actions):
        if not self.run:
            return

        tool_outputs = []

        for action in required_actions["tool_calls"]:
            func_name = action["function"]["name"]
            arguments = json.loads(action["function"]["arguments"])

            if func_name == "get_news":
                output = get_news(topic=arguments["topic"])
                print(f"STUFF ===> {output}")
                final_str = ""
                for item in output:
                    final_str += "".join(item)

                tool_outputs.append({"tool_call_id": action["id"], "output": final_str})
            else:
                raise ValueError(f"Unknown function: {func_name}")

        print("Submitting outputs back to the Assistant...")

        self.client.beta.threads.runs.submit_tool_outputs(
            thread_id=self.thread.id,
            run_id=self.run.id,
            tool_outputs=tool_outputs,
        )


def main():
    manager = AssistantManager()

    # Streamlit interface
    st.title("News Summarizer")

    # Form for user input
    with st.form(key="user_input_form"):
        instructions = st.text_area("Enter topic:")
        submit_button = st.form_submit_button(label="Run Assistant")
    # Handling the button click
    if submit_button:
        # Create the assistant and thread if they don't exist
        manager.create_assistant(
            name="News Summarizer",
            instructions="You are a personal article summarizer Assistant who knows how to take a list of article's titles and descriptions and then write a short summary of all the news articles",
            tools=[
                {
                    "type": "function",
                    "function": {
                        "name": "get_news",
                        "description": "Get the list of articles/news for the given topic",
                        "parameters": {
                            "type": "object",
                            "properties": {
                                "topic": {
                                    "type": "string",
                                    "description": "The topic for the news, e.g. bitcoin",
                                }
                            },
                            "required": ["topic"],
                        },
                    },
                }
            ],
        )
        manager.create_thread()

        # Add the message and run the assistant
        manager.add_message_to_thread(
            role="user", content=f"summarize the news on this topic {instructions}?"
        )
        manager.run_assistant(instructions="Summarize the news")

        # Wait for completion and process messages
        manager.wait_for_completion()

        summary = (
            manager.get_summary()
        )  # Implement get_summary() in your AssistantManager
        st.write(summary)

        st.text("Run Steps:")
        st.code(manager.run_steps(), line_numbers=True)

    # Create an assistant and tools
    # process 1
    # manager.create_assistant(
    #     name="News Summarizer",
    #     instructions="You are a personal article summarizer Assistant who knows how to take a list of article's titles and descriptions and then write a short summary of all the news articles",
    #     tools=[
    #         {
    #             "type": "function",
    #             "function": {
    #                 "name": "get_news",
    #                 "description": "Get the list of articles/news for the given topic",
    #                 "parameters": {
    #                     "type": "object",
    #                     "properties": {
    #                         "topic": {
    #                             "type": "string",
    #                             "description": "The topic for the news, e.g. bitcoin",
    #                         }
    #                     },
    #                     "required": ["topic"],
    #                 },
    #             },
    #         }
    #     ],
    # )
    # topic = input("Enter your topic (bitcoin):")

    # # process 2
    # manager.create_thread()
    # # process 3
    # manager.add_message_to_thread(
    #     role="user", content=f"summarize the news on this topic {topic}?"
    # )
    # # process 4
    # manager.run_assistant(instructions="Summarize the news")
    # # final
    # manager.wait_for_completion()

    # manager.process_messages()


if __name__ == "__main__":
    main()
