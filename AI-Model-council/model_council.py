import json
import os
from pathlib import Path
import subprocess
import tempfile
import textwrap


PERSONAS = [
    {"name": "Tree", "system": "Use tree-of-thought analysis internally. Explore a few strong branches and return only the best final answer."},
    {"name": "First Principles", "system": "Use first-principles reasoning internally. Break the problem into fundamentals and return only the final answer."},
    {"name": "Inversion", "system": "Use inversion thinking internally. Ask what would make the answer fail, improve it, and return only the final answer."},
    {"name": "Second Order", "system": "Reason from first principles, then examine second-order effects before deciding. Return only the final answer."},
]


def cursor_council(
    prompt: str,
    cwd: str = ".",
    api_key: str | None = None,
    persona_histories: list[list[dict]] | None = None,
) -> dict:
    sdk_root = Path(tempfile.gettempdir()) / "cursor-sdk-python-bridge"
    sdk_module = sdk_root / "node_modules/@cursor/sdk/dist/esm/index.js"
    if not sdk_module.exists():
        subprocess.run(["npm", "install", "--silent", "--prefix", str(sdk_root), "@cursor/sdk"], check=True)
    key = api_key or os.environ.get("CURSOR_API_KEY") or os.environ.get("CURSOR_SDK_API_KEYS")
    if not key:
        raise KeyError("CURSOR_API_KEY")
    histories = persona_histories or [[] for _ in PERSONAS]
    env = os.environ | {"CURSOR_API_KEY": key}
    js = textwrap.dedent(
        f"""
        import {{ Agent, Cursor }} from {json.dumps(sdk_module.as_uri())};
        const prompt = {json.dumps(prompt)};
        const cwd = {json.dumps(os.path.abspath(cwd))};
        const personas = {json.dumps(PERSONAS)};
        const histories = {json.dumps(histories)};
        const models = await Cursor.models.list({{ apiKey: process.env.CURSOR_API_KEY }});
        const model = models.find(m => m.id.includes("composer-2.5"))?.id
          ?? (models.find(m => m.aliases?.includes("composer-latest")) ? "composer-latest" : "composer-2.5");
        const opts = {{ apiKey: process.env.CURSOR_API_KEY, model: {{ id: model }}, local: {{ cwd }} }};
        const renderHistory = history => history.map(m => `${{m.role === "user" ? "User" : "Assistant"}}:\\n${{m.content}}`).join("\\n\\n");
        const personaPrompt = (persona, history) => `${{persona.system}}

Conversation so far:
${{renderHistory(history) || "(new chat)"}}

Latest user message:
${{prompt}}

Reply as the assistant and return only the answer.`;
        const drafts = await Promise.all(personas.map(async (persona, i) => {{
          const result = await Agent.prompt(personaPrompt(persona, histories[i] || []), opts);
          return (result.result || "").trim();
        }}));
        const updatedHistories = histories.map((history, i) => [
          ...history,
          {{ role: "user", content: prompt }},
          {{ role: "assistant", content: drafts[i] }},
        ]);
        const personaPrompts = personas.map((persona, i) => personaPrompt(persona, histories[i] || []));
        const candidates = drafts.map((draft, i) => `Candidate ${{i + 1}} (${{personas[i].name}}):\\n${{draft}}`).join("\\n\\n");
        const judgePrompt = `You are a Kapiti-style model council judge.
Review the candidate answers below for the latest user message only.
Pick the single best answer or merge the strongest ideas from 2-3 answers.
Return only the final response, with no preamble.

Latest user message:
${{prompt}}

${{candidates}}`;
        const final = await Agent.prompt(judgePrompt, opts);
        console.log(JSON.stringify({{
          model,
          personas: personas.map(p => p.name),
          drafts,
          final: (final.result || "").trim(),
          persona_histories: updatedHistories,
          persona_prompts: personaPrompts,
          judge_prompt: judgePrompt,
          history_before: histories.map(h => h.length),
          history_after: updatedHistories.map(h => h.length),
        }}));
        """
    )
    out = subprocess.run(
        ["node", "--input-type=module", "-e", js],
        env=env,
        text=True,
        capture_output=True,
        check=True,
    )
    return json.loads(out.stdout)
