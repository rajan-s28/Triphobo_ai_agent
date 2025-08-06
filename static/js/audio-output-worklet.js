// static/js/audio-output-worklet.js

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
    
    // The number of samples to process in this frame.
    const frameSize = channel.length;
    
    // Get the required number of samples from our buffer.
    const samplesToPlay = this.buffer.splice(0, Math.min(frameSize, this.buffer.length));

    // Convert Int16 PCM samples to Float32 and fill the output channel.
    for (let i = 0; i < samplesToPlay.length; i++) {
      channel[i] = samplesToPlay[i] / 32768.0;
    }

    // Fill the rest of the frame with silence if the buffer is empty.
    for (let i = samplesToPlay.length; i < frameSize; i++) {
      channel[i] = 0;
    }

    // Return true to keep the processor alive.
    return true;
  }
}

registerProcessor('audio-output-processor', AudioOutputProcessor);