class AudioOutputProcessor extends AudioWorkletProcessor {
  constructor() {
    super();
    this.buffer = [];
    this.port.onmessage = (event) => {
      if (event.data) {
        this.buffer.push(...new Int16Array(event.data));
      }
    };
  }

  process(inputs, outputs, parameters) {
    const output = outputs[0];
    const channel = output[0];
    const frameSize = channel.length;
    const samplesToPlay = this.buffer.splice(0, Math.min(frameSize, this.buffer.length));

    for (let i = 0; i < samplesToPlay.length; i++) {
      channel[i] = samplesToPlay[i] / 32768.0;
    }

    for (let i = samplesToPlay.length; i < frameSize; i++) {
      channel[i] = 0;
    }

    return true;
  }
}

registerProcessor('audio-output-processor', AudioOutputProcessor);