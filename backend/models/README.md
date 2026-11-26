Silero VAD (MIT), from https://github.com/snakers4/silero-vad

Pinned upstream commit: `bfa5f8cef40abb5de2bd4a2f4c3f22778172dfec`.
File: `src/silero_vad/data/silero_vad.onnx`.
SHA-256: `f6f4407b41e05e277e7f5cfd9b9ae957b1dfe763c6076a934734c0b448e09b31`.

The accompanying `silero-LICENSE` contains the upstream license. This is a
speech activity detector, not a transcription model. It runs on CPU and needs
neither PyTorch nor a GPU. Recurrent state is separate for each call. The model
is packaged with the app; startup does not download executable code or weights.
