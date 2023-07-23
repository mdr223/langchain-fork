from langchain.callbacks.manager import CallbackManagerForLLMRun
from langchain.llms.base import LLM

from pydantic import Field, root_validator
from transformers import AutoTokenizer
from typing import Any, Dict, List, Mapping, Optional

import transformers
import torch


class Llama2(LLM):
    """Wrapper around Llama2 large language model."""
    # 7b: "meta-llama/Llama-2-7b-chat-hf"
    # 13b: "meta-llama/Llama-2-13b-chat-hf"
    # 70b: "meta-llama/Llama-2-70b-chat-hf"
    model_name: str = Field("meta-llama/Llama-2-7b-chat-hf", alias="model")
    """Model name to use."""
    max_length: int = 4000
    """The maximum number of tokens to generate in the completion."""
    pred = None  #: :meta private:
    """LLM model object."""
    tokenizer = None
    """LLM tokenizer object."""

    @root_validator()
    def validate_environment(cls, values: Dict) -> Dict:
        """Initialize predictor using model_name."""
        values["tokenizer"] = AutoTokenizer.from_pretrained(values["model_name"])
        values["pred"] = transformers.pipeline(
            "text-generation",
            model=values["model_name"],
            torch_dtype=torch.float16,
            device_map="auto",
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
            "max_length": self.max_length,
        }

    def _call(
        self,
        prompt: str,
        stop: Optional[List[str]] = None,
        run_manager: Optional[CallbackManagerForLLMRun] = None,
    ) -> str:
        # if stop is not None:
        #     raise ValueError("stop kwargs are not permitted for now.")j

        # execute prediction for a single sequence
        sequences = self.pred(
            prompt,
            do_sample=True,
            top_k=1,
            num_return_sequences=1,
            eos_token_id=self.tokenizer.eos_token_id,
            max_length=self.max_length,
        )

        return sequences[0]['generated_text']
