// static/js/audio-input-worklet.js

class AudioInputProcessor extends AudioWorkletProcessor {
  process(inputs, outputs, parameters) {
    const input = inputs[0];
    if (input.length > 0) {
      const pcmData = this.float32ToInt16(input[0]);
      this.port.postMessage(pcmData.buffer, [pcmData.buffer]);
    }
    return true;
  }

  float32ToInt16(buffer) {
    let l = buffer.length;
    const buf = new Int16Array(l);
    while (l--) {
      buf[l] = Math.min(1, buffer[l]) * 0x7FFF;
    }
    return buf;
  }
}

registerProcessor('audio-input-processor', AudioInputProcessor);