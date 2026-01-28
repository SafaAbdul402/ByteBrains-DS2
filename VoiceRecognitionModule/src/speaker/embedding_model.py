import torch
from speechbrain.inference import EncoderClassifier


class ECAPAEmbedder:
    def __init__(self):
        self.device = "cuda" if torch.cuda.is_available() else "cpu"

        self.model = EncoderClassifier.from_hparams(
            source="speechbrain/spkrec-ecapa-voxceleb",
            run_opts={"device": self.device}
        )

    def embed_waveform(self, waveform):
        with torch.no_grad():
            emb = self.model.encode_batch(waveform.to(self.device))
            return emb.squeeze().cpu().numpy()
