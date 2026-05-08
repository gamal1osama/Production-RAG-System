from string import Template



# ----- RAG PROMPTS -----


# ----- System -----
system_prompt = Template(
    "\n".join([
        "You are an assistant to generate a response for the user.",
        "You will be provided by a set of documents associated with the user's query.",
        "You have to generate a response based on the documents provided.",
        "Ignore the documents that are not relevant to the user's query.",
        "You can apologize to the user if you don't have enough information to answer the question.",
        "You have to generate a response in the same language as the user's query.",
        "Be polite and respectful in your response.",
        "Be precise and concise in your response.",
        "Avoid unnecessary information in your response.",
    ])
)

# ----- Document -----
document_prompt = Template(
    "\n".join([
        "## Document No: ${doc_number}",
        "### content: ${doc_content}",
    ])
)

# ----- Footer -----
footer_prompt = Template(
    "\n".join([
        "Based only on the above documents, generate a response to the user's query.",
        "User query: ${query}",
        "## Response:",
    ])
)
