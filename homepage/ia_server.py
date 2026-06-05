import json
import sys

from gpt4all import GPT4All


MODEL_NAME = "Meta-Llama-3-8B-Instruct.Q4_0.gguf"
SYSTEM_PROMPT = (
    "Responde en espanol de forma breve, clara y util. "
    "Si la pregunta trata sobre residuos, reciclaje o Ecovigilante, prioriza ese contexto."
)


def main():
    try:
      model = GPT4All(MODEL_NAME)
      session = model.chat_session(system_prompt=SYSTEM_PROMPT)
      session.__enter__()
    except Exception as err:
      print(json.dumps({"ok": False, "error": f"Error al cargar la IA local: {err}"}, ensure_ascii=False), flush=True)
      raise SystemExit(1)

    try:
      for raw_line in sys.stdin:
        line = raw_line.strip()
        if not line:
          continue

        try:
          payload = json.loads(line)
          prompt = (payload.get("prompt") or "").strip()
          if not prompt:
            raise ValueError("No se recibió ninguna pregunta.")

          answer = model.generate(
            prompt,
            max_tokens=180,
            temp=0.4,
            top_k=40,
            top_p=0.9,
            repeat_penalty=1.1,
          ).strip()

          print(json.dumps({"ok": True, "answer": answer}, ensure_ascii=False), flush=True)
        except Exception as err:
          print(json.dumps({"ok": False, "error": str(err)}, ensure_ascii=False), flush=True)
    finally:
      session.__exit__(None, None, None)


if __name__ == "__main__":
    main()
