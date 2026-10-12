<script setup>
import { onMounted, ref } from "vue"

const health = ref(null)
const selectedFile = ref(null)
const result = ref(null)
const error = ref("")
const busy = ref(false)

async function refreshHealth() {
  try {
    const response = await fetch("/api/health")
    health.value = await response.json()
  } catch (exception) {
    error.value = `Không kết nối được backend: ${exception.message}`
  }
}

async function processVideo() {
  if (!selectedFile.value || !health.value?.can_process) {
    return
  }

  busy.value = true
  error.value = ""
  result.value = null

  try {
    const formData = new FormData()
    formData.append("video", selectedFile.value)

    const response = await fetch("/api/process", {
      method: "POST",
      body: formData,
    })

    const data = await response.json()

    if (!response.ok) {
      throw new Error(data.detail || "Xử lý video thất bại")
    }

    result.value = data
    await refreshHealth()
  } catch (exception) {
    error.value = exception.message
  } finally {
    busy.value = false
  }
}

onMounted(refreshHealth)
</script>

<template>
  <main class="shell">
    <header class="header">
      <div>
        <p class="eyebrow">DOUBLEV LAB</p>
        <h1>Video Localizer</h1>
        <p class="subtitle">
          Gemini STT · Gemma Translate · Gemini TTS · FFmpeg
        </p>
      </div>

      <span :class="['status', { online: health?.ok }]">
        {{ health?.ok ? "System online" : "Checking" }}
      </span>
    </header>

    <section class="grid">
      <article class="panel">
        <h2>Tạo bản Việt hóa</h2>

        <label class="upload-box">
          <input
            type="file"
            accept="video/*"
            @change="selectedFile = $event.target.files[0]"
          />

          <strong>
            {{ selectedFile?.name || "Chọn video MP4" }}
          </strong>

          <small>
            {{
              selectedFile
                ? `${(selectedFile.size / 1024 / 1024).toFixed(2)} MB`
                : "Chọn file video từ máy"
            }}
          </small>
        </label>

        <button
          :disabled="
            !selectedFile ||
            busy ||
            !health?.can_process
          "
          @click="processVideo"
        >
          {{ busy ? "Đang xử lý..." : "Bắt đầu xử lý" }}
        </button>

        <p
          v-if="health && !health.can_process"
          class="warning"
        >
          Chưa có đủ key sẵn sàng cho STT, TTS và translate.
        </p>

        <p v-if="error" class="error">
          {{ error }}
        </p>
      </article>

      <article class="panel">
        <h2>Key status</h2>

        <h3>Gemini API</h3>

        <div
          v-for="item in health?.api_keys || []"
          :key="`${item.model}-${item.slot}`"
          class="key-row"
        >
          <div>
            <strong>{{ item.model }}</strong>
            <small>Key {{ item.slot + 1 }}</small>
          </div>

          <span :class="{ ready: item.ready }">
            {{
              item.ready
                ? `${item.calls_in_window}/${item.rpm} RPM`
                : `Chờ ${item.ready_in_seconds}s`
            }}
          </span>
        </div>

        <h3>Gemini CLI Translate</h3>

        <div
          v-for="item in health?.translate_keys || []"
          :key="`${item.model}-${item.slot}`"
          class="key-row"
        >
          <div>
            <strong>{{ item.model }}</strong>
            <small>Key {{ item.slot + 1 }}</small>
          </div>

          <span :class="{ ready: item.ready }">
            {{
              item.ready
                ? `${item.calls_in_window}/${item.rpm} RPM`
                : `Chờ ${item.ready_in_seconds}s`
            }}
          </span>
        </div>
      </article>
    </section>

    <section v-if="result" class="grid result">
      <article class="panel">
        <h2>Video đầu ra</h2>

        <video
          :src="result.video_url"
          controls
        />
      </article>

      <article class="panel">
        <h2>Timeline</h2>

        <div
          v-for="segment in result.segments"
          :key="segment.id"
          class="segment"
        >
          <small>
            {{ segment.start }}s → {{ segment.end }}s
          </small>

          <p>{{ segment.source }}</p>
          <strong>{{ segment.vi }}</strong>
        </div>
      </article>
    </section>
  </main>
</template>