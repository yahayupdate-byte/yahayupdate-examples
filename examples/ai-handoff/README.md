# Local AI role handoff

Python standard library + local Ollama + qwen3:4b. Two calls to the same model with different roles; this is not independent model consensus or A2A.

## Run

Install Ollama from its official site and keep its service bound to loopback. Configure OLLAMA_BASE_URL privately in your shell with your own local service origin before running the example. No endpoint value, port number or credentials are distributed. The script rejects non-loopback origins, credentials, query strings and URL paths.

```sh
ollama pull qwen3:4b
python3 -m unittest -v test_contract
python3 agent_handoff.py integration-result.json > my-result.json
```

No external AI API credentials or paid API calls. Local model tokens, memory, electricity and the initial download are still required.

## Evidence

The input is a saved real local cache integration result from October 22. The October 27 run called Ollama twice; it did NOT rerun Redis or SQLite. The analyst summarized the counts correctly, but the reviewer objected to compatible request/read counts. Full observed output is included. Tests validate the trust boundary, not factual accuracy. Both advisory verdicts terminate at human_review_required. Same-model roles may share errors. Temperature zero is not a cross-platform reproducibility guarantee.

## Limits

No production benchmark, external tools, deployment or publication authority. No network A2A implementation. The script checks types, permitted references and enums, not arbitrary natural-language truth. Timeouts stop the caller; the server may still consume compute after disconnect. Production needs authentication, isolation, budgets, logging/redaction, retention policy and prompt-injection evaluations. Do not expose the local model endpoint to the Internet. 

Sources: https://docs.ollama.com/api/chat ; https://docs.ollama.com/capabilities/structured-outputs ; https://a2a-protocol.org/latest/topics/what-is-a2a/

Cache source repository: https://github.com/yahayupdate-byte/yahayupdate-examples/tree/main/examples/cache-stampede.

Article: [Spanish](https://www.yahayupdate.com/por-dentro/comunicacion-entre-ias/) · [English](https://www.yahayupdate.com/en/inside/ai-handoff/)

Requires Python 3.10 or newer. Run the commands from this folder. The archived run used qwen3:4b, Q4_K_M, model digest 359d7dd4bcdab3d86b87d73ac27966f4dbb9f5efdfcc75d34a8764a09474fae7. The model tag may change; use the saved digest to identify the tested model.


## Publication configuration

The archived October 27 model output predates the change from a fixed local endpoint to OLLAMA_BASE_URL. Prompts and model settings are unchanged. Seven offline checks pass after that change: five contract checks and two configuration checks. The model integration was not rerun for this configuration-only update. Tests patch the process environment, never substitute a model response. Keep local configuration and private logs out of commits, downloads and screenshots.
