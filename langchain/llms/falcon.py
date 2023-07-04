from langchain.callbacks.manager import CallbackManagerForLLMRun
from langchain.llms.base import LLM
from sagemaker.predictor import Predictor
from sagemaker.serializers import JSONSerializer
from sagemaker.deserializers import JSONDeserializer

from pydantic import Field, root_validator
from typing import Any, Dict, List, Mapping, Optional


class Falcon(LLM):
    """Wrapper around falcon large language model."""
    # 7b: falcon-7b-instruct-bf16-2023-06-08-17-59-43-889
    # 40b: falcon-40b-instruct-bf16-2023-07-03-17-06-57-631
    # ----
    # bedrock 7b: falcon-7b-instruct-bf16-2023-07-03-19-51-07-347
    # bedrock 40b: falcon-40b-instruct-bf16-2023-07-04-19-55-13-674
    model_name: str = Field("falcon-7b-instruct-bf16-2023-07-03-19-51-07-347", alias="model")
    """Model name to use."""
    max_tokens: int = 512
    """The maximum number of tokens to generate in the completion.
    -1 returns as many tokens as possible given the prompt and
    the models maximal context size."""
    pred: Predictor = None  #: :meta private:
    """LLM model object."""

    @root_validator()
    def validate_environment(cls, values: Dict) -> Dict:
        """Initialize predictor using model_name."""
        values["pred"] = Predictor(
            values["model_name"],
            sagemaker_session=None,
            serializer=JSONSerializer(), 
            deserializer=JSONDeserializer(),
            content_type = "application/json",
        )

        return values

    @property
    def _llm_type(self) -> str:
        return "custom"

    @property
    def _identifying_params(self) -> Mapping[str, Any]:
        """Get the identifying parameters."""
        return {
            "model_name": self.model_name,
            "max_tokens": self.max_tokens,
        }

    def _call(
        self,
        prompt: str,
        stop: Optional[List[str]] = None,
        run_manager: Optional[CallbackManagerForLLMRun] = None,
    ) -> str:
        # if stop is not None:
        #     raise ValueError("stop kwargs are not permitted for now.")

        # construct payload to send to predictor
        payload = {
            "text_inputs": prompt,
            "max_new_tokens": self.max_tokens,
            "return_full_text": False,
            "do_sample": True,
            "top_k": 10,
        }
        response = self.pred.predict(payload)

        return response["generated_texts"][0]
