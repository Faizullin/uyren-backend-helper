import os, pathlib, time
from playwright.sync_api import sync_playwright


def get_content_ml_auth_file_path():
    """Get the path to the content ML auth file."""
    root = pathlib.Path(__file__).parent.parent.parent
    auth_path = root / "content-ml-helper" / "notebooklm.json"
    if not auth_path.exists():
        raise FileNotFoundError(f"Auth state directory {auth_path} does not exist. Please create it.")
    return auth_path

GOOGLE_EMAIL="osman.faizulla@nu.edu.kz"
GOOGLE_PASSWORD="OF.password@1234"

auth_path = get_content_ml_auth_file_path()
if not auth_path.parent.exists():
    raise FileNotFoundError(f"Auth state directory {auth_path} does not exist. Please create it.")

def google_login():
    EMAIL = GOOGLE_EMAIL
    PASSWORD = GOOGLE_PASSWORD

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True, args=['--disable-blink-features=AutomationControlled'])
        page = browser.new_page(locale="en-US")
        page.goto("https://notebooklm.google.com/")
        page.locator('input[type="email"]').fill(EMAIL)
        page.locator('button:has-text(\"Next\")').click()
        page.locator('input[type=\"password\"]').fill(PASSWORD)
        page.locator('button:has-text(\"Next\")').click()
        page.wait_for_url("https://notebooklm.google.com/*")
        page.context.storage_state(path=auth_path)
        browser.close()
    return f"Auth state saved to {auth_path}"



class ContentRenderer:
    SPECIAL_TAGS = {"a": "link", "button": "button", "code": "code"}

    def render(self, node):
        tag = node.get("tag")
        content = node.get("content", None)
        if content is None:
            content = ""
        content = content.strip()
        children = node.get("children", [])
        child_strs = [self.render(child) for child in children if child]
        if tag == "root":
            joined_children = "\n\n\n".join(filter(None, child_strs))
        elif tag == "div":
            joined_children = "\n".join(filter(None, child_strs))
        else:
            joined_children = " ".join(filter(None, child_strs))
        # Avoid duplication: if content is the same as joined_children, only use one
        if content and joined_children:
            if content == joined_children:
                base = content
            else:
                base = f"{content} {joined_children}"
        elif content:
            base = content
        else:
            base = joined_children
        if tag in self.SPECIAL_TAGS:
            return f"<{self.SPECIAL_TAGS[tag]}: {base}>".strip()
        return base

def extract_element_tree(element_handle):
    tag = element_handle.evaluate("el => el.tagName.toLowerCase()")
    children = element_handle.query_selector_all(":scope > *")
    content = None
    if tag in ["p", "span", "h1", "h2", "h3", "h4", "h5", "h6", ]:
        content = element_handle.inner_text()
    return {
        "tag": tag,
        "children": [extract_element_tree(child) for child in children],
        "content": content,
    }

def request_notebook_lm(page, prompt_text):
    chat_panel = page.query_selector(".chat-panel-content")
    prompt_input = page.query_selector("textarea")
    if not chat_panel or not prompt_input:
        raise Exception("Missing chat panel or prompt input.")
    children = chat_panel.query_selector_all(":scope > *")
    if len(children) != 1:
        raise Exception("Chat panel should initially have one child.")
    prompt_input.fill(prompt_text)
    prompt_input.dispatch_event("input")
    time.sleep(0.5)
    page.click("button[type=submit]")
    time.sleep(0.5)
    last_message = chat_panel.query_selector_all(":scope > *")[-1]
    time.sleep(1)
    max_wait = 60
    elapsed = 0
    while True:
        loading = last_message.query_selector("loading-component")
        if not loading:
            break
        if elapsed >= max_wait:
            raise TimeoutError("Loading state too long.")
        time.sleep(1)
        elapsed += 1
    structural_elements = last_message.query_selector_all("chat-message")
    if not structural_elements:
        print("Error", last_message.inner_html())
        raise Exception("No structured elements found. structural_elements: " + str(structural_elements))
    # print("output", last_message.inner_html())
    result = {"tag": "root", "children": []}
    result["children"] = [extract_element_tree(structural_elements[1])]
    renderer = ContentRenderer()
    output_str = renderer.render(result)
    splitted = output_str.split("\n", 1)

    return {
        "first_line": splitted[0] if len(splitted) > 0 else "",
        "rest": splitted[1] if len(splitted) > 1 else "",
        "chat-message-length": len(structural_elements),
        "raw-input": last_message.inner_html(),
    }

def run_notebook_lm(note_id, question, state_path):
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(storage_state=state_path)
        page = context.new_page()
        page.goto(f"https://notebooklm.google.com/notebook/{note_id}", timeout=60000)
        try:
            output = request_notebook_lm(page, generate_notebooklm_prompt(question))
        finally:
            context.close()
            browser.close()
    return output

def generate_notebooklm_prompt(user_prompt: str) -> str:
    """
    Generate a prompt for NotebookLM with the first line referencing the file name.
    """
    new_prompt = f"""
Answer the question based on the content of the notebook.
Answer format MUST be: first line is filename only while from second is content asnwer.
If not found then first line is "No content found". If could not process or could not answer send "Could not answer".
Prompt: {user_prompt}"""
    return new_prompt