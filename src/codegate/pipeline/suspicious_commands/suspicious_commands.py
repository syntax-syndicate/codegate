"""
A module for spotting suspicious commands using the embeddings
from our local LLM and a futher ANN categorisier.

The code in here is used for inference. The training code is in
SuspiciousCommandsTrainer. The split is because we don't want to
install torch on a docker, it is too big. So we train the model on
a local machine and then use the generated onnx file for inference.
"""

import os

import numpy as np  # Add this import
import onnxruntime as ort
import structlog

from codegate.config import Config
from codegate.inference.inference_engine import LlamaCppInferenceEngine

logger = structlog.get_logger("codegate")


class SuspiciousCommands:
    """
    Class to handle suspicious command detection using a neural network.

    Attributes:
        model_path (str): Path to the model.
        inference_engine (LlamaCppInferenceEngine): Inference engine for embedding.
        simple_nn (SimpleNN): Neural network model.
    """

    _instance = None

    @staticmethod
    def get_instance(model_file=None):
        """
        Get the singleton instance of SuspiciousCommands. Initialize and load
        from file on the first call if it has not been done.

        Args:
            model_file (str, optional): The file name to load the model from.

        Returns:
            SuspiciousCommands: The singleton instance.
        """
        if SuspiciousCommands._instance is None:
            SuspiciousCommands._instance = SuspiciousCommands()
            if model_file is None:
                current_file_path = os.path.dirname(os.path.abspath(__file__))
                model_file = os.path.join(current_file_path, "simple_nn_model.onnx")
            SuspiciousCommands._instance.load_trained_model(model_file)
        return SuspiciousCommands._instance

    def __init__(self):
        """
        Initialize the SuspiciousCommands class.
        """
        conf = Config.get_config()
        if conf and conf.model_base_path and conf.embedding_model:
            self.model_path = f"{conf.model_base_path}/{conf.embedding_model}"
        else:
            self.model_path = ""
        self.inference_engine = LlamaCppInferenceEngine()
        self.simple_nn = None  # Initialize to None, will be created in train

    def load_trained_model(self, file_name):
        """
        Load a trained model from a file.

        Args:
            file_name (str): The file name to load the model from.
        """
        self.inference_session = ort.InferenceSession(file_name)

    async def compute_embeddings(self, phrases):
        """
        Compute embeddings for a list of phrases.

        Args:
            phrases (list of str): List of phrases to compute embeddings for.

        Returns:
            torch.Tensor: Tensor of embeddings.
        """
        embeddings = await self.inference_engine.embed(
            self.model_path, phrases, n_gpu_layers=Config.get_config().chat_model_n_gpu_layers
        )
        return embeddings

    async def classify_phrase(self, phrase, embeddings=None):
        """
        Classify a single phrase as suspicious or not.

        Args:
            phrase (str): The phrase to classify.
            embeddings (torch.Tensor, optional): Precomputed embeddings for
            the phrase.

        Returns:
            tuple: The predicted class (0 or 1) and its probability.
        """
        if embeddings is None:
            embeddings = await self.compute_embeddings([phrase])

        input_name = self.inference_session.get_inputs()[0].name
        ort_inputs = {input_name: embeddings}

        # Run the inference session
        ort_outs = self.inference_session.run(None, ort_inputs)

        # Process the output
        prediction = np.argmax(ort_outs[0])
        probability = np.max(ort_outs[0])
        return prediction, probability


async def check_suspicious_code(code, language=None):
    """
    Check if the given code is suspicious and return a comment if it is.

    Args:
        code (str): The code to check.
        language (str, optional): The language of the code.

    Returns:
        tuple: A comment string and a boolean indicating if the code is suspicious.
    """
    if language is None:
        language = "code"
    if language in [
        "python",
        "javascript",
        "typescript",
        "go",
        "rust",
        "java",
    ]:
        logger.debug(f"Skipping suspicious command check for {language}")
        return "", False
    logger.debug("Checking code for suspicious commands")
    sc = SuspiciousCommands.get_instance()
    comment = ""
    class_, prob = await sc.classify_phrase(code)
    is_suspicious = class_ == 1
    if is_suspicious:
        liklihood = "possibly"
        if prob > 0.9:
            liklihood = "likely"
        comment = f"{comment}\n\n🛡️ CodeGate: The {language} supplied is {liklihood} unsafe. Please check carefully!\n\n"  # noqa: E501
        logger.info(f"Suspicious: {code}")
    else:
        logger.debug("Not Suspicious")
    return comment, is_suspicious
