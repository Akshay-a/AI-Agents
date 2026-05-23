import gradio as gr

from db import create_chat, ensure_chat, load_chat, save_chat
from model_council import PERSONAS, cursor_council


INITIAL_CHAT_ID, INITIAL_CHOICES, INITIAL_HISTORY, INITIAL_PERSONAS = ensure_chat()

SCENARIOS = {
    "Context carry (codeword)": [
        "Remember this codeword exactly: QUARTZ. Reply with only: stored.",
        "What codeword did I ask you to remember? Reply with only the codeword.",
        "Without repeating the codeword, confirm you still know it by describing its first and last letters.",
    ],
    "Deep reasoning chain": [
        "A tank holds 120L. Pipe A fills it in 6h, pipe B in 4h. How long to fill together? Show reasoning, then give one final number.",
        "Now the tank starts 30% full. How long to fill the rest with both pipes? Use your prior setup.",
        "Pipe B slows by 50%. Recalculate fill time from empty with both pipes.",
    ],
    "Constraint stacking": [
        "Design a Python function to dedupe a list while preserving order. No set(). Return only the function.",
        "Same function, but O(1) extra space besides output. Keep order.",
        "Same function, but also handle nested lists one level deep.",
    ],
}

PERSONA_COLORS = ["#10b981", "#3b82f6", "#f59e0b", "#8b5cf6"]

THEME_CSS = """
:root, .gradio-container {
  --body-background-fill: #ffffff !important;
  --background-fill-primary: #ffffff !important;
  --background-fill-secondary: #f8f9fb !important;
  --block-background-fill: #ffffff !important;
  --block-border-color: #e6e8ec !important;
  --border-color-primary: #e6e8ec !important;
  --color-accent: #10a37f !important;
  --color-accent-soft: rgba(16,163,127,0.06) !important;
  --link-text-color: #10a37f !important;
  --body-text-color: #1a1a2e !important;
  --block-label-text-color: #8b8fa3 !important;
  --block-label-text-weight: 500 !important;
  --input-background-fill: #ffffff !important;
  font-family: "Inter", -apple-system, BlinkMacSystemFont, "Segoe UI",
    Roboto, "Helvetica Neue", Arial, sans-serif !important;
}
.gradio-container { max-width: 100% !important; }
body { background: #f8f9fb !important; }

/* ── Header ── */
.header-bar {
  padding: 0.85rem 1.25rem;
  margin-bottom: 0.25rem;
  display: flex;
  align-items: baseline;
  gap: 0.6rem;
}
.header-bar h1 {
  margin: 0;
  font-size: 1.05rem;
  font-weight: 700;
  color: #1a1a2e;
  letter-spacing: -0.02em;
}
.header-bar .subtitle {
  font-size: 0.78rem;
  color: #8b8fa3;
  font-weight: 400;
}

/* ── Welcome placeholder (shown in empty chatbot) ── */
.welcome-placeholder {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  text-align: center;
  padding: 3.5rem 2rem 2.5rem;
}
.welcome-icon {
  width: 52px;
  height: 52px;
  border-radius: 14px;
  background: linear-gradient(135deg, #10a37f 0%, #0d8c6d 100%);
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 0.85rem;
  font-weight: 700;
  color: #ffffff;
  letter-spacing: 0.02em;
  margin-bottom: 1.25rem;
}
.welcome-placeholder h2 {
  font-size: 1.2rem;
  font-weight: 700;
  color: #1a1a2e;
  margin: 0 0 0.4rem 0;
  letter-spacing: -0.02em;
}
.welcome-placeholder .desc {
  font-size: 0.84rem;
  color: #8b8fa3;
  max-width: 400px;
  line-height: 1.6;
  margin: 0 0 1.5rem 0;
}
.welcome-hints {
  display: flex;
  gap: 0.45rem;
  flex-wrap: wrap;
  justify-content: center;
}
.hint {
  padding: 0.35rem 0.8rem;
  border: 1px solid #e6e8ec;
  border-radius: 999px;
  font-size: 0.76rem;
  color: #8b8fa3;
  background: #ffffff;
  transition: border-color 0.15s, color 0.15s;
}

/* ── Sidebar ── */
.sidebar-card {
  background: #f8f9fb;
  border: 1px solid #e6e8ec;
  border-radius: 12px;
  padding: 0.7rem 0.85rem;
}
.sidebar-card h3 {
  font-size: 0.68rem;
  font-weight: 600;
  text-transform: uppercase;
  letter-spacing: 0.06em;
  color: #8b8fa3;
  margin: 0 0 0.5rem 0;
}

/* ── Panel cards ── */
.panel-card {
  background: #ffffff;
  border: 1px solid #e6e8ec;
  border-radius: 12px;
  padding: 0.75rem 1rem;
}

/* ── Turn metadata strip ── */
.turn-meta {
  display: flex;
  gap: 0.4rem;
  flex-wrap: wrap;
  padding: 0.3rem 0;
}
.meta-tag {
  display: inline-flex;
  align-items: center;
  gap: 0.2rem;
  padding: 0.18rem 0.55rem;
  border-radius: 6px;
  font-size: 0.68rem;
  font-weight: 500;
}
.meta-model { background: #f0fdf4; color: #15803d; }
.meta-saved { background: #f0fdf4; color: #10a37f; }
.meta-info  { background: #f8f9fb; color: #8b8fa3; }

/* ── Chatbot ── */
.gradio-chatbot .message { font-size: 0.9rem; line-height: 1.7; }

/* ── Tabs ── */
.gradio-container .tabs > .tab-nav button {
  font-size: 0.76rem !important;
  font-weight: 500 !important;
  color: #8b8fa3 !important;
  padding: 0.4rem 0.7rem !important;
}
.gradio-container .tabs > .tab-nav button.selected {
  color: #1a1a2e !important;
  border-bottom-color: #10a37f !important;
}

/* ── Buttons ── */
.gradio-container button.primary {
  background: #10a37f !important;
  border: none !important;
  color: #ffffff !important;
  font-weight: 500 !important;
  border-radius: 8px !important;
  font-size: 0.84rem !important;
}
.gradio-container button.primary:hover {
  background: #0d8c6d !important;
}
.gradio-container button.secondary {
  background: #ffffff !important;
  border: 1px solid #e6e8ec !important;
  color: #1a1a2e !important;
  font-weight: 500 !important;
  border-radius: 8px !important;
  font-size: 0.8rem !important;
}
.gradio-container button.secondary:hover {
  background: #f8f9fb !important;
}

/* ── Input textbox ── */
.gradio-container textarea {
  border: 1px solid #e6e8ec !important;
  border-radius: 10px !important;
  font-size: 0.88rem !important;
  padding: 0.65rem 0.85rem !important;
  background: #ffffff !important;
  color: #1a1a2e !important;
}
.gradio-container textarea:focus {
  border-color: #10a37f !important;
  box-shadow: 0 0 0 2px rgba(16,163,127,0.1) !important;
}

/* ── Persona cards ── */
.persona-card {
  padding: 0.45rem 0;
  border-bottom: 1px solid #f0f0f5;
}
.persona-card:last-child { border-bottom: none; }
.persona-dot {
  display: inline-block;
  width: 7px;
  height: 7px;
  border-radius: 50%;
  margin-right: 0.3rem;
  vertical-align: middle;
}
.persona-name {
  font-weight: 600;
  color: #1a1a2e;
  font-size: 0.82rem;
}
.persona-desc {
  font-size: 0.74rem;
  color: #8b8fa3;
  line-height: 1.5;
  margin: 0.1rem 0 0 0;
}

/* ── Clean up Gradio defaults ── */
footer { display: none !important; }
.gradio-container .block { border: none !important; box-shadow: none !important; }
"""

WELCOME_PLACEHOLDER = (
    '<div class="welcome-placeholder">'
    '<div class="welcome-icon">MC</div>'
    "<h2>Ask anything</h2>"
    '<p class="desc">Four reasoning personas analyze your question in parallel, '
    "then a judge synthesizes the best answer.</p>"
    '<div class="welcome-hints">'
    '<span class="hint">Coding question</span>'
    '<span class="hint">Math puzzle</span>'
    '<span class="hint">Architecture review</span>'
    "</div>"
    "</div>"
)

INSPECTOR_DEFAULTS = (
    "",   # turn_meta
    "",   # context_audit
    "",   # judge_drafts
    "",   # judge_prompt
    "",   # tree_prompt
    "",   # fp_prompt
    "",   # inv_prompt
    "",   # so_prompt
    [],   # tree_chat
    [],   # fp_chat
    [],   # inv_chat
    [],   # so_chat
)


def format_prompt(prompt: str) -> str:
    if not prompt:
        return ""
    return f"**Prompt sent this turn**\n\n```\n{prompt}\n```"


def render_context_audit(
    histories_before: list[list[dict]], persona_prompts: list[str], persona_names: list[str]
) -> str:
    lines = ["| Persona | Prior turns | Messages in prompt | Audit |", "| --- | --- | --- | --- |"]
    for name, history, prompt in zip(persona_names, histories_before, persona_prompts):
        prior = len(history)
        if prior == 0:
            lines.append(f"| {name} | 0 | n/a | First turn |")
            continue
        found = sum(1 for msg in history if msg.get("content") and msg["content"] in prompt)
        if found == prior:
            status = f"All {prior} prior messages appear in prompt"
        else:
            status = f"{found}/{prior} prior messages found in prompt"
        lines.append(f"| {name} | {prior // 2} | {found}/{prior} | {status} |")
    return "\n".join(lines)


def render_turn_meta(result: dict) -> str:
    before = result.get("history_before", [])
    after = result.get("history_after", [])
    deltas = [f"{b}→{a}" for b, a in zip(before, after)]
    return (
        f'<div class="turn-meta">'
        f'<span class="meta-tag meta-model">{result.get("model", "unknown")}</span>'
        f'<span class="meta-tag meta-saved">Saved</span>'
        f'<span class="meta-tag meta-info">Msgs: {", ".join(deltas)}</span>'
        f'<span class="meta-tag meta-info">Judge: stateless</span>'
        f"</div>"
    )


def persona_histories_to_chatbots(persona_histories: list[list[dict]]) -> list[list[dict]]:
    return [persona_histories[i] if i < len(persona_histories) else [] for i in range(4)]


def load_selected_chat(chat_id: str):
    chat_history, persona_histories = load_chat(chat_id)
    chats = persona_histories_to_chatbots(persona_histories)
    return (
        chat_history,
        persona_histories,
        "",
        "",
        "",
        "",
        INSPECTOR_DEFAULTS[4],
        INSPECTOR_DEFAULTS[5],
        INSPECTOR_DEFAULTS[6],
        INSPECTOR_DEFAULTS[7],
        *chats,
    )


def new_chat():
    chat_id = str(create_chat())
    choices = ensure_chat()[1]
    return (
        gr.update(choices=choices, value=chat_id),
        chat_id,
        [],
        [[], [], [], []],
        "",
        *INSPECTOR_DEFAULTS,
    )


def apply_scenario_step(scenario_name: str, step_index: int):
    steps = SCENARIOS.get(scenario_name, [])
    if not steps or step_index >= len(steps):
        return "", gr.update(maximum=max(len(steps) - 1, 0), value=0)
    return steps[step_index], gr.update(maximum=max(len(steps) - 1, 0), value=step_index)


def council_turn(message: str, chat_id: str, chat_history: list, persona_histories: list):
    if not message.strip():
        return tuple(gr.update() for _ in range(16))
    histories_before = [history[:] for history in persona_histories]
    result = cursor_council(message, persona_histories=persona_histories)
    updated_chat = chat_history + [
        {"role": "user", "content": message},
        {"role": "assistant", "content": result["final"]},
    ]
    save_chat(chat_id, updated_chat, result["persona_histories"])
    chats = persona_histories_to_chatbots(result["persona_histories"])
    prompts = [format_prompt(p) for p in result["persona_prompts"]]
    return (
        "",
        updated_chat,
        result["persona_histories"],
        gr.update(choices=ensure_chat()[1], value=chat_id),
        render_turn_meta(result),
        render_context_audit(histories_before, result["persona_prompts"], result["personas"]),
        "\n\n".join(f"**{name}**\n\n{draft}" for name, draft in zip(result["personas"], result["drafts"])),
        format_prompt(result.get("judge_prompt", "")),
        *prompts,
        *chats,
    )


# ── Layout ──────────────────────────────────────────────────────────────────

with gr.Blocks(title="Model Council", css=THEME_CSS, theme=gr.themes.Base()) as demo:
    gr.HTML(
        '<div class="header-bar">'
        "<h1>Model Council</h1>"
        '<span class="subtitle">Multi-persona reasoning with a synthesizing judge</span>'
        "</div>"
    )

    with gr.Row(equal_height=False):

        # ── Sidebar ──
        with gr.Column(scale=2, min_width=220):
            with gr.Group(elem_classes=["sidebar-card"]):
                gr.Markdown("### Sessions")
                chat_picker = gr.Dropdown(
                    INITIAL_CHOICES, value=INITIAL_CHAT_ID, label="Chat", show_label=False
                )
                new_chat_btn = gr.Button("+ New chat", variant="secondary", size="sm")

            with gr.Group(elem_classes=["sidebar-card"]):
                gr.Markdown("### Scenarios")
                scenario = gr.Dropdown(
                    list(SCENARIOS.keys()),
                    label="Scenario",
                    value=list(SCENARIOS.keys())[0],
                    show_label=False,
                )
                scenario_step = gr.Slider(
                    minimum=0,
                    maximum=max(len(next(iter(SCENARIOS.values()))) - 1, 0),
                    step=1,
                    value=0,
                    label="Step",
                )
                load_step_btn = gr.Button("Load step", variant="secondary", size="sm")

            with gr.Group(elem_classes=["sidebar-card"]):
                gr.Markdown("### Personas")
                for i, persona in enumerate(PERSONAS):
                    color = PERSONA_COLORS[i % len(PERSONA_COLORS)]
                    gr.HTML(
                        f'<div class="persona-card">'
                        f'<span class="persona-dot" style="background:{color}"></span>'
                        f'<span class="persona-name">{persona["name"]}</span>'
                        f'<div class="persona-desc">{persona["system"]}</div>'
                        f"</div>"
                    )

        # ── Main chat ──
        with gr.Column(scale=6):
            with gr.Group(elem_classes=["panel-card"]):
                turn_meta = gr.HTML("")
                chatbot = gr.Chatbot(
                    value=INITIAL_HISTORY,
                    type="messages",
                    height=540,
                    show_label=False,
                    placeholder=WELCOME_PLACEHOLDER,
                )
                with gr.Row():
                    message = gr.Textbox(
                        placeholder="Ask a coding or reasoning question\u2026",
                        lines=2,
                        scale=9,
                        show_label=False,
                        container=False,
                    )
                    send = gr.Button("Send", variant="primary", scale=1, min_width=80)

        # ── Inspector ──
        with gr.Column(scale=4):
            with gr.Group(elem_classes=["panel-card"]):
                with gr.Tabs():
                    with gr.Tab("Audit"):
                        context_audit = gr.Markdown("")
                    with gr.Tab("Tree"):
                        tree_chat = gr.Chatbot(
                            value=persona_histories_to_chatbots(INITIAL_PERSONAS)[0],
                            type="messages",
                            height=240,
                            show_label=False,
                        )
                        tree_prompt = gr.Markdown("")
                    with gr.Tab("First Principles"):
                        fp_chat = gr.Chatbot(
                            value=persona_histories_to_chatbots(INITIAL_PERSONAS)[1],
                            type="messages",
                            height=240,
                            show_label=False,
                        )
                        fp_prompt = gr.Markdown("")
                    with gr.Tab("Inversion"):
                        inv_chat = gr.Chatbot(
                            value=persona_histories_to_chatbots(INITIAL_PERSONAS)[2],
                            type="messages",
                            height=240,
                            show_label=False,
                        )
                        inv_prompt = gr.Markdown("")
                    with gr.Tab("2nd Order"):
                        so_chat = gr.Chatbot(
                            value=persona_histories_to_chatbots(INITIAL_PERSONAS)[3],
                            type="messages",
                            height=240,
                            show_label=False,
                        )
                        so_prompt = gr.Markdown("")
                    with gr.Tab("Judge"):
                        judge_drafts = gr.Markdown("")
                        judge_prompt = gr.Markdown("")

    # ── State ──
    chat_id = gr.State(INITIAL_CHAT_ID)
    personas = gr.State(INITIAL_PERSONAS)

    inspector_outputs = [
        turn_meta,
        context_audit,
        judge_drafts,
        judge_prompt,
        tree_prompt,
        fp_prompt,
        inv_prompt,
        so_prompt,
        tree_chat,
        fp_chat,
        inv_chat,
        so_chat,
    ]
    turn_outputs = [message, chatbot, personas, chat_picker, *inspector_outputs]

    # ── Events ──
    chat_picker.change(load_selected_chat, chat_picker, [chatbot, personas, *inspector_outputs]).then(
        lambda value: value, chat_picker, chat_id
    )
    new_chat_btn.click(new_chat, outputs=[chat_picker, chat_id, chatbot, personas, message, *inspector_outputs])
    load_step_btn.click(apply_scenario_step, [scenario, scenario_step], [message, scenario_step])
    scenario.change(
        lambda name: gr.update(maximum=max(len(SCENARIOS.get(name, [])) - 1, 0), value=0),
        scenario,
        scenario_step,
    )
    send.click(council_turn, [message, chat_id, chatbot, personas], turn_outputs)
    message.submit(council_turn, [message, chat_id, chatbot, personas], turn_outputs)


if __name__ == "__main__":
    demo.launch(quiet=True)
