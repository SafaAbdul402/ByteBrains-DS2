from src.audio.preprocess import preprocess_latest_to_wav16k
from src.audio.segmentation import segment_latest_processed
from src.speaker.embedding_model import extract_latest_embeddings
from src.speaker.clustering import cluster_latest_embeddings
from src.speaker.diarization_pipeline import diarize_latest


def main():
    preprocess_latest_to_wav16k()
    segment_latest_processed()
    extract_latest_embeddings()
    cluster_latest_embeddings()
    diarize_latest()

    print("✅ Latest-file diarization pipeline complete")


if __name__ == "__main__":
    main()
