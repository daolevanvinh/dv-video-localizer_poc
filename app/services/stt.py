import json
import time

from app.models.schema import Segment


def parse_json_response(raw_response: str) -> dict:
    text = (raw_response or "").strip()

    if not text:
        raise RuntimeError(
            "Gemini STT trả response rỗng."
        )

    # Xử lý response dạng:
    # ```json
    # {"segments": [...]}
    # ```
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
        # Nếu model viết thêm nội dung ngoài JSON,
        # lấy object JSON đầu tiên đến dấu } cuối cùng.
        object_start = text.find("{")
        object_end = text.rfind("}")

        if (
            object_start == -1
            or object_end == -1
            or object_end <= object_start
        ):
            raise RuntimeError(
                "Gemini STT trả nội dung không phải JSON. "
                f"Response={text[:2000]!r}"
            )

        json_text = text[
            object_start:object_end + 1
        ]

        try:
            return json.loads(json_text)

        except json.JSONDecodeError as exception:
            raise RuntimeError(
                "Không parse được JSON từ Gemini STT. "
                f"Response={text[:2000]!r}"
            ) from exception


class STT:
    def __init__(
        self,
        pool,
        model,
    ):
        self.pool = pool
        self.model = model

    def run(self, path):
        def operation(client):
            uploaded_file = client.files.upload(
                file=str(path)
            )

            try:
                while True:
                    file_info = client.files.get(
                        name=uploaded_file.name
                    )

                    state = getattr(
                        file_info.state,
                        "name",
                        str(file_info.state),
                    )

                    print(
                        "[STT] File state:",
                        state,
                    )

                    if state == "ACTIVE":
                        break

                    if state == "FAILED":
                        raise RuntimeError(
                            "Gemini Files API xử lý video thất bại."
                        )

                    time.sleep(2)

                response = client.models.generate_content(
                    model=self.model,
                    contents=[
                        uploaded_file,
                        """
Bạn là chuyên gia bóc băng video.

Hãy nghe toàn bộ video và chép chính xác lời nói
hoặc lời hát.

Yêu cầu:
- Giữ nguyên ngôn ngữ gốc.
- Có timestamp start và end theo giây.
- Bỏ tiếng nhạc hoặc âm thanh vô nghĩa.
- Không giải thích.
- Không dùng Markdown.
- Chỉ trả JSON hợp lệ.

Cấu trúc bắt buộc:

{
  "segments": [
    {
      "id": 0,
      "start": 0.0,
      "end": 2.0,
      "source": "nguyên văn"
    }
  ]
}
""".strip(),
                    ],
                )

                response_text = (
                    response.text or ""
                ).strip()

                print("=" * 80)
                print("[STT] Model:", self.model)
                print(
                    "[STT] Response length:",
                    len(response_text),
                )
                print(
                    "[STT] Raw response:",
                    repr(response_text[:3000]),
                )
                print("=" * 80)

                return response_text

            finally:
                try:
                    client.files.delete(
                        name=uploaded_file.name
                    )
                except Exception as exception:
                    print(
                        "[STT] Delete uploaded file failed:",
                        repr(exception),
                    )

        raw_response = self.pool.call(
            self.model,
            operation,
        )

        data = parse_json_response(
            raw_response
        )

        raw_segments = data.get(
            "segments",
            [],
        )

        if not isinstance(raw_segments, list):
            raise RuntimeError(
                "Gemini STT trả JSON nhưng "
                "'segments' không phải array."
            )

        segments = []

        for index, item in enumerate(
            raw_segments
        ):
            source = str(
                item.get("source", "")
            ).strip()

            if not source:
                continue

            try:
                start = float(item["start"])
                end = float(item["end"])
            except (
                KeyError,
                TypeError,
                ValueError,
            ) as exception:
                print(
                    "[STT] Bỏ segment timestamp lỗi:",
                    repr(item),
                    repr(exception),
                )
                continue

            segments.append(
                Segment(
                    id=int(
                        item.get("id", index)
                    ),
                    start=start,
                    end=end,
                    source=source,
                )
            )

        if not segments:
            raise RuntimeError(
                "Gemini STT không trả segment hợp lệ. "
                f"Parsed response={data!r}"
            )

        return segments