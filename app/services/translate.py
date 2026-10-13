import json
import shutil
import subprocess
import tempfile
from pathlib import Path

from app.core.pools import is_rate


def parse_json_response(value: str) -> dict:
    """
    Parse JSON returned by Gemini.

    Supports:
    - Plain JSON
    - JSON wrapped in Markdown fences
    - Text containing a JSON object
    """
    text = (value or "").strip()

    if not text:
        raise ValueError(
            "Gemini CLI trả response rỗng."
        )

    if text.startswith("```"):
        lines = text.splitlines()

        if lines and lines[0].strip().startswith("```"):
            lines = lines[1:]

        if lines and lines[-1].strip() == "```":
            lines = lines[:-1]

        text = "\n".join(lines).strip()

    try:
        result = json.loads(text)

        if not isinstance(result, dict):
            raise ValueError(
                "JSON response không phải object."
            )

        return result

    except json.JSONDecodeError:
        object_start = text.find("{")
        object_end = text.rfind("}")

        if (
            object_start == -1
            or object_end == -1
            or object_end <= object_start
        ):
            raise ValueError(
                "Không tìm thấy JSON object trong response: "
                f"{text[:1000]!r}"
            )

        json_text = text[
            object_start:object_end + 1
        ]

        try:
            result = json.loads(json_text)

            if not isinstance(result, dict):
                raise ValueError(
                    "JSON response không phải object."
                )

            return result

        except json.JSONDecodeError as exception:
            raise ValueError(
                "Tìm thấy JSON object nhưng không parse được: "
                f"{json_text[:1000]!r}"
            ) from exception


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

    def resolve_cli_command(self) -> str:
        """
        Resolve Gemini CLI executable.

        On Windows, npm normally installs gemini.cmd.
        """
        configured = str(
            self.cmd or ""
        ).strip()

        if configured:
            configured_path = Path(configured)

            if configured_path.exists():
                return str(
                    configured_path.resolve()
                )

            resolved = shutil.which(configured)

            if resolved:
                return resolved

        windows_command = shutil.which(
            "gemini.cmd"
        )

        if windows_command:
            return windows_command

        normal_command = shutil.which(
            "gemini"
        )

        if normal_command:
            return normal_command

        raise RuntimeError(
            "Không tìm thấy Gemini CLI. "
            "Hãy đặt GEMINI_CLI_COMMAND bằng đường dẫn đầy đủ "
            "tới gemini.cmd. Ví dụ: "
            "C:/Users/daole/AppData/Roaming/npm/gemini.cmd"
        )

    def build_payload(self, segments) -> str:
        """
        Keep translation payload small.

        Translation does not need start/end timestamps.
        """
        payload = [
            {
                "id": segment.id,
                "source": segment.source,
            }
            for segment in segments
        ]

        instructions = {
            "task": (
                "Sửa lỗi transcript ASR và dịch từng segment "
                "sang tiếng Việt tự nhiên."
            ),
            "rules": [
                "Xử lý nhiệm vụ ngay, không xác nhận vai trò.",
                "Giữ nguyên tất cả ID.",
                "Không thay đổi số lượng segment.",
                "Không bịa nội dung ngoài transcript.",
                "Sửa source nếu ASR nhận sai theo ngữ cảnh.",
                "Bản tiếng Việt phải ngắn và dễ đọc bằng TTS.",
                "Không nhắc đến source code hoặc dự án.",
                "Không giải thích.",
                "Không sử dụng Markdown.",
                "Chỉ trả một JSON object hợp lệ.",
            ],
            "output_schema": {
                "segments": [
                    {
                        "id": 0,
                        "source_fixed": (
                            "Nguyên văn đã sửa"
                        ),
                        "vi": (
                            "Bản dịch tiếng Việt"
                        ),
                    }
                ]
            },
            "segments": payload,
        }

        return json.dumps(
            instructions,
            ensure_ascii=False,
            separators=(",", ":"),
        )

    def build_short_prompt(self) -> str:
        return (
            "Đọc JSON từ stdin và thực hiện trường task ngay. "
            "Không xác nhận vai trò, không chào hỏi. "
            "Sửa lỗi ASR và dịch từng segment sang tiếng Việt. "
            "Chỉ trả JSON đúng output_schema trong stdin. "
            "Không dùng Markdown hoặc code fence."
        )

    @staticmethod
    def is_invalid_key(message: str) -> bool:
        value = message.lower()

        markers = (
            "api_key_invalid",
            "api key not valid",
            "invalid api key",
            "unauthenticated",
            "permission_denied",
        )

        return any(
            marker in value
            for marker in markers
        )

    def run_cli(
        self,
        cli_command: str,
        key: str,
        payload: str,
    ) -> subprocess.CompletedProcess:
        command = [
            cli_command,
            "--model",
            self.model,
            "--prompt",
            self.build_short_prompt(),
            "--output-format",
            "json",
        ]

        print("=" * 70)
        print(
            "[TRANSLATE] Command:",
            cli_command,
        )
        print(
            "[TRANSLATE] Model:",
            self.model,
        )
        print(
            "[TRANSLATE] Payload length:",
            len(payload),
        )
        print(
            "[TRANSLATE] Payload preview:",
            repr(payload[:1000]),
        )
        print("=" * 70)

        environment = self.pool.env(key)

        # Prevent another authentication variable from
        # overriding the selected translation key.
        environment.pop(
            "GOOGLE_API_KEY",
            None,
        )

        environment["GEMINI_API_KEY"] = (
            key.strip()
            .strip('"')
            .strip("'")
        )

        environment["NO_COLOR"] = "1"

        with tempfile.TemporaryDirectory(
            prefix="dv-video-translate-"
        ) as temporary_directory:
            return subprocess.run(
                command,
                input=payload,
                cwd=temporary_directory,
                env=environment,
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                timeout=300,
            )

    def apply_translation(
        self,
        segments,
        translated_data: dict,
    ):
        translated_items = translated_data.get(
            "segments",
            [],
        )

        if not isinstance(
            translated_items,
            list,
        ):
            raise ValueError(
                "Gemini trả JSON nhưng trường "
                "'segments' không phải array."
            )

        translated_by_id = {}

        for item in translated_items:
            if not isinstance(item, dict):
                continue

            try:
                item_id = int(item["id"])
            except (
                KeyError,
                TypeError,
                ValueError,
            ):
                continue

            translated_by_id[item_id] = item

        if not translated_by_id:
            raise ValueError(
                "Gemini trả JSON nhưng không có "
                "segment ID hợp lệ."
            )

        missing_ids = []

        for segment in segments:
            item = translated_by_id.get(
                segment.id
            )

            if item is None:
                missing_ids.append(
                    segment.id
                )
                continue

            source_fixed = str(
                item.get(
                    "source_fixed",
                    "",
                )
            ).strip()

            vietnamese = str(
                item.get(
                    "vi",
                    "",
                )
            ).strip()

            if source_fixed:
                segment.source = source_fixed

            segment.vi = vietnamese

        if missing_ids:
            raise ValueError(
                "Gemini không trả đủ segment. "
                f"Thiếu ID: {missing_ids}"
            )

        empty_translation_ids = [
            segment.id
            for segment in segments
            if not segment.vi.strip()
        ]

        if empty_translation_ids:
            raise ValueError(
                "Một số segment không có bản dịch tiếng Việt. "
                f"ID: {empty_translation_ids}"
            )

        return segments

    def run(self, segments):
        if not segments:
            raise ValueError(
                "Không có segment để dịch."
            )

        cli_command = (
            self.resolve_cli_command()
        )

        payload = self.build_payload(
            segments
        )

        tried = set()
        last_error = None

        while len(tried) < len(
            self.pool.keys
        ):
            index, key = self.pool.take(
                self.model,
                tried,
            )

            tried.add(index)

            print("=" * 70)
            print(
                f"[TRANSLATE] "
                f"model={self.model} "
                f"key_slot={index + 1}"
            )
            print("=" * 70)

            try:
                process = self.run_cli(
                    cli_command=cli_command,
                    key=key,
                    payload=payload,
                )

            except subprocess.TimeoutExpired as exception:
                print(
                    "[TRANSLATE] Timeout:",
                    repr(exception),
                )

                self.pool.suspend(
                    self.model,
                    index,
                    "CLI timeout",
                )

                last_error = exception
                continue

            except FileNotFoundError as exception:
                raise RuntimeError(
                    "Không tìm thấy Gemini CLI. "
                    f"Command={cli_command!r}"
                ) from exception

            stdout = (
                process.stdout or ""
            ).strip()

            stderr = (
                process.stderr or ""
            ).strip()

            print(
                "[TRANSLATE] Return code:",
                process.returncode,
            )

            print(
                "[TRANSLATE] STDOUT:",
                repr(stdout[:3000]),
            )

            print(
                "[TRANSLATE] STDERR:",
                repr(stderr[:3000]),
            )

            combined = "\n".join(
                value
                for value in (
                    stdout,
                    stderr,
                )
                if value
            )

            if process.returncode != 0:
                if is_rate(combined):
                    reason = "429/quota"

                elif self.is_invalid_key(
                    combined
                ):
                    reason = (
                        "invalid API key"
                    )

                else:
                    reason = (
                        "CLI exit "
                        f"{process.returncode}"
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
                last_error = ValueError(
                    "Gemini CLI kết thúc thành công "
                    "nhưng stdout bị rỗng. "
                    f"stderr={stderr[:2000]!r}"
                )

                # Đây có thể là lỗi CLI tạm thời,
                # nên cooldown slot.
                self.pool.suspend(
                    self.model,
                    index,
                    "empty CLI stdout",
                )

                continue

            try:
                envelope = (
                    parse_json_response(
                        stdout
                    )
                )

            except Exception as exception:
                print(
                    "[TRANSLATE] "
                    "CLI envelope không hợp lệ:",
                    repr(stdout[:3000]),
                )

                last_error = exception

                # Không treo key chỉ vì output format sai.
                continue

            cli_error = envelope.get(
                "error"
            )

            if cli_error:
                error_text = json.dumps(
                    cli_error,
                    ensure_ascii=False,
                )

                if is_rate(error_text):
                    reason = "429/quota"

                elif self.is_invalid_key(
                    error_text
                ):
                    reason = (
                        "invalid API key"
                    )

                else:
                    reason = (
                        "CLI response error"
                    )

                self.pool.suspend(
                    self.model,
                    index,
                    reason,
                )

                last_error = RuntimeError(
                    error_text
                )

                continue

            answer = envelope.get(
                "response"
            )

            if (
                not isinstance(answer, str)
                or not answer.strip()
            ):
                last_error = ValueError(
                    "Gemini CLI envelope không có "
                    "trường response hợp lệ. "
                    f"Envelope={envelope!r}"
                )

                continue

            print(
                "[TRANSLATE] Model response:",
                repr(answer[:3000]),
            )

            try:
                translated_data = (
                    parse_json_response(
                        answer
                    )
                )

            except Exception as exception:
                print(
                    "[TRANSLATE] Model trả sai định dạng:",
                    repr(answer[:3000]),
                )

                last_error = exception

                # Không cooldown key vì model không tuân thủ JSON
                # không có nghĩa credential bị lỗi.
                continue

            try:
                return self.apply_translation(
                    segments,
                    translated_data,
                )

            except Exception as exception:
                print(
                    "[TRANSLATE] JSON hợp lệ "
                    "nhưng dữ liệu không hợp lệ:",
                    repr(translated_data),
                )

                last_error = exception
                continue

        raise RuntimeError(
            "Không còn translation key khả dụng. "
            f"Lỗi cuối: {last_error}"
        )