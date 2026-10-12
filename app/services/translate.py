import json
import subprocess

from app.core.pools import is_rate


def parse_json_response(value: str) -> dict:
    text = (value or "").strip()

    if not text:
        raise ValueError("Gemini CLI trả response rỗng.")

    if text.startswith("```"):
        lines = text.splitlines()

        if lines and lines[0].strip().startswith("```"):
            lines = lines[1:]

        if lines and lines[-1].strip() == "```":
            lines = lines[:-1]

        text = "\n".join(lines).strip()

    try:
        return json.loads(text)
    except json.JSONDecodeError:
        start = text.find("{")
        end = text.rfind("}")

        if start == -1 or end == -1 or end <= start:
            raise ValueError(
                "Không tìm thấy JSON object trong response: "
                f"{text[:500]!r}"
            )

        return json.loads(text[start:end + 1])


class Translator:
    def __init__(
        self,
        pool,
        model,
        cmd="gemini",
    ):
        self.pool = pool
        self.model = model
        self.cmd = cmd

    def build_prompt(self, segments) -> str:
        payload = [
            segment.dict()
            for segment in segments
        ]

        return f"""
Bạn là biên tập viên phụ đề video ngắn.

Transcript bên dưới có thể bị nhận dạng sai do:
- nhạc nền
- lời hát
- từ đồng âm
- nhiều ngôn ngữ
- lỗi ASR

Nhiệm vụ:
1. Hiểu toàn bộ ngữ cảnh.
2. Sửa lại nguyên văn nếu ASR nhận sai.
3. Dịch sang tiếng Việt tự nhiên.
4. Viết câu tiếng Việt ngắn, dễ đọc bằng TTS.
5. Giữ nguyên ID.
6. Không bịa thêm nội dung.

Chỉ trả về JSON hợp lệ, không giải thích,
không dùng Markdown và không dùng code fence.

Cấu trúc bắt buộc:

{{
  "segments": [
    {{
      "id": 0,
      "source_fixed": "Nguyên văn đã sửa",
      "vi": "Bản dịch tiếng Việt"
    }}
  ]
}}

Dữ liệu:

{json.dumps(payload, ensure_ascii=False)}
""".strip()

    def run(self, segments):
        prompt = self.build_prompt(segments)

        tried = set()
        last_error = None

        while len(tried) < len(self.pool.keys):
            index, key = self.pool.take(
                self.model,
                tried,
            )
            tried.add(index)

            command = [
                self.cmd,
                "--model",
                self.model,
                "--prompt",
                prompt,
                "--output-format",
                "json",
            ]

            print("=" * 70)
            print(
                f"TRANSLATE model={self.model} "
                f"key_slot={index + 1}"
            )
            print("=" * 70)

            try:
                process = subprocess.run(
                    command,
                    env=self.pool.env(key),
                    capture_output=True,
                    text=True,
                    encoding="utf-8",
                    errors="replace",
                    timeout=300,
                )
            except subprocess.TimeoutExpired as exception:
                last_error = exception

                self.pool.suspend(
                    self.model,
                    index,
                    "CLI timeout",
                )
                continue
            except FileNotFoundError as exception:
                raise RuntimeError(
                    "Không tìm thấy lệnh 'gemini'. "
                    "Kiểm tra Gemini CLI đã được cài và có trong PATH."
                ) from exception

            stdout = (process.stdout or "").strip()
            stderr = (process.stderr or "").strip()

            print("RETURN CODE:", process.returncode)
            print("STDOUT:", repr(stdout[:2000]))
            print("STDERR:", repr(stderr[:2000]))

            combined = "\n".join(
                value
                for value in [stdout, stderr]
                if value
            )

            if process.returncode != 0:
                reason = (
                    "429/quota"
                    if is_rate(combined)
                    else f"CLI exit {process.returncode}"
                )

                self.pool.suspend(
                    self.model,
                    index,
                    reason,
                )

                last_error = RuntimeError(
                    combined or reason
                )
                continue

            if not stdout:
                self.pool.suspend(
                    self.model,
                    index,
                    "empty stdout",
                )

                last_error = ValueError(
                    "Gemini CLI kết thúc thành công "
                    "nhưng stdout bị rỗng."
                )
                continue

            try:
                envelope = parse_json_response(stdout)
            except Exception as exception:
                self.pool.suspend(
                    self.model,
                    index,
                    "invalid CLI envelope",
                )

                last_error = exception
                continue

            cli_error = envelope.get("error")

            if cli_error:
                cli_error_text = json.dumps(
                    cli_error,
                    ensure_ascii=False,
                )

                reason = (
                    "429/quota"
                    if is_rate(cli_error_text)
                    else "CLI response error"
                )

                self.pool.suspend(
                    self.model,
                    index,
                    reason,
                )

                last_error = RuntimeError(
                    cli_error_text
                )
                continue

            answer = envelope.get("response")

            if not isinstance(answer, str) or not answer.strip():
                self.pool.suspend(
                    self.model,
                    index,
                    "empty model response",
                )

                last_error = ValueError(
                    "Gemini CLI envelope không có "
                    "trường response hợp lệ. "
                    f"Envelope: {envelope}"
                )
                continue

            try:
                translated_data = parse_json_response(
                    answer
                )
            except Exception as exception:
                self.pool.suspend(
                    self.model,
                    index,
                    "invalid translation JSON",
                )

                last_error = exception
                continue

            translated_items = (
                translated_data.get("segments", [])
            )

            if not isinstance(translated_items, list):
                self.pool.suspend(
                    self.model,
                    index,
                    "segments is not a list",
                )

                last_error = ValueError(
                    "Gemini trả JSON nhưng segments "
                    "không phải array."
                )
                continue

            translated_by_id = {}

            for item in translated_items:
                try:
                    item_id = int(item["id"])
                except (
                    KeyError,
                    TypeError,
                    ValueError,
                ):
                    continue

                translated_by_id[item_id] = item

            for segment in segments:
                item = translated_by_id.get(
                    segment.id,
                    {},
                )

                source_fixed = str(
                    item.get("source_fixed", "")
                ).strip()

                vietnamese = str(
                    item.get("vi", "")
                ).strip()

                if source_fixed:
                    segment.source = source_fixed

                segment.vi = vietnamese

            return segments

        raise RuntimeError(
            "Không còn translation key khả dụng. "
            f"Lỗi cuối: {last_error}"
        )